# SPDX-License-Identifier: Apache-2.0
"""Deterministic resource bound enforcement for mutation execution."""

from __future__ import annotations

import multiprocessing as mp
import os
import resource
import time
from dataclasses import dataclass
from typing import Any, Callable

from runtime import metrics


@dataclass(frozen=True)
class ResourceLimitEvent:
    event: str
    resource: str
    limit: float
    observed: float


class ResourceBoundsExceeded(RuntimeError):
    """Raised when runtime resource envelope is exceeded."""

    def __init__(self, message: str, *, event: ResourceLimitEvent) -> None:
        super().__init__(message)
        self.event = event


class _ChildError(RuntimeError):
    pass


def _read_limit_with_deprecated_alias(
    *,
    canonical_env: str,
    deprecated_alias_env: str,
    default: str,
    caster: Callable[[str], float | int],
) -> float | int:
    canonical_raw = os.getenv(canonical_env, "").strip()
    if canonical_raw:
        return caster(canonical_raw)

    alias_raw = os.getenv(deprecated_alias_env, "").strip()
    if alias_raw:
        metrics.log(
            event_type="resource_limit_env_alias_deprecated",
            payload={
                "canonical_env": canonical_env,
                "deprecated_alias_env": deprecated_alias_env,
                "validator": "resource_bounds",
            },
            level="WARNING",
        )
        return caster(alias_raw)

    return caster(default)


def _run_target(queue: mp.Queue, func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any], memory_mb: int) -> None:
    if memory_mb > 0:
        limit_bytes = memory_mb * 1024 * 1024
        # RLIMIT_AS is available on Linux/WSL; if unavailable, we still execute and
        # report deterministic fallback semantics through parent-side observations.
        if hasattr(resource, "RLIMIT_AS"):
            resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    start_cpu = time.process_time()
    try:
        result = func(*args, **kwargs)
        queue.put(("ok", result, time.process_time() - start_cpu))
    except MemoryError:
        queue.put(("error", "memory", time.process_time() - start_cpu))
    except Exception as exc:  # noqa: BLE001
        queue.put(("error", f"{type(exc).__name__}:{exc}", time.process_time() - start_cpu))


def enforce_resource_bounds(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    max_wall = float(
        _read_limit_with_deprecated_alias(
            canonical_env="ADAAD_RESOURCE_WALL_SECONDS",
            deprecated_alias_env="ADAAD_MAX_WALL_SECONDS",
            default="30",
            caster=float,
        )
    )
    max_memory = int(
        float(
            _read_limit_with_deprecated_alias(
                canonical_env="ADAAD_RESOURCE_MEMORY_MB",
                deprecated_alias_env="ADAAD_MAX_MEMORY_MB",
                default="512",
                caster=float,
            )
        )
    )
    max_cpu = float(
        _read_limit_with_deprecated_alias(
            canonical_env="ADAAD_RESOURCE_CPU_SECONDS",
            deprecated_alias_env="ADAAD_MAX_CPU_SECONDS",
            default="30",
            caster=float,
        )
    )

    queue: mp.Queue = mp.Queue()
    proc = mp.Process(target=_run_target, args=(queue, func, args, kwargs, max_memory))
    proc.start()
    proc.join(timeout=max_wall)

    if proc.is_alive():
        proc.terminate()
        proc.join()
        event = ResourceLimitEvent("resource_bounds_exceeded", "wall_seconds", max_wall, max_wall + 0.001)
        raise ResourceBoundsExceeded("resource_bounds_exceeded:wall_seconds", event=event)

    if proc.exitcode not in (0, None):
        event = ResourceLimitEvent("resource_bounds_exceeded", "memory_mb", max_memory, max_memory + 1)
        raise ResourceBoundsExceeded("resource_bounds_exceeded:process_exit", event=event)

    if queue.empty():
        raise _ChildError("child_result_missing")

    status, payload, cpu_used = queue.get()
    if float(cpu_used) > max_cpu:
        event = ResourceLimitEvent("resource_bounds_exceeded", "cpu_seconds", max_cpu, float(cpu_used))
        raise ResourceBoundsExceeded("resource_bounds_exceeded:cpu_seconds", event=event)
    if status == "error":
        event = ResourceLimitEvent("resource_bounds_exceeded", "memory_mb", max_memory, max_memory + 1)
        raise ResourceBoundsExceeded("resource_bounds_exceeded:child_error", event=event)
    return payload


__all__ = ["ResourceBoundsExceeded", "enforce_resource_bounds", "_read_limit_with_deprecated_alias"]
