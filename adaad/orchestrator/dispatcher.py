# SPDX-License-Identifier: Apache-2.0
"""Dispatcher that executes registered handlers and appends latency metadata."""

from __future__ import annotations

import logging
import os
from time import monotonic_ns, perf_counter
from typing import Any

from adaad.orchestrator.registry import HandlerRegistry, get_tool

try:
    from runtime import metrics as runtime_metrics
except Exception:  # pragma: no cover - runtime package optional for isolated usage
    runtime_metrics = None

_LATENCY_BUDGET_ENV_VAR = "ADAAD_DISPATCH_LATENCY_BUDGET_MS"
_DEFAULT_MAX_LATENCY_MS = 50.0
_LOGGER = logging.getLogger("adaad.dispatcher")


def _resolve_max_latency_ms() -> float:
    configured = os.getenv(_LATENCY_BUDGET_ENV_VAR)
    source = "default"
    resolved = _DEFAULT_MAX_LATENCY_MS
    invalid_value = False

    if configured is not None:
        try:
            resolved = float(configured)
            source = "env"
        except (TypeError, ValueError):
            invalid_value = True

    if runtime_metrics is not None:
        try:
            runtime_metrics.log(
                event_type="dispatch_latency_budget_config_loaded",
                payload={
                    "config_key": _LATENCY_BUDGET_ENV_VAR,
                    "configured_value": configured,
                    "resolved_value": resolved,
                    "source": source,
                    "invalid_value": invalid_value,
                },
                level="WARNING" if invalid_value else "INFO",
            )
        except Exception as exc:
            _LOGGER.warning(
                "dispatcher latency config telemetry failed",
                extra={"exception": str(exc), "resolved_value": resolved},
            )

    return resolved


MAX_LATENCY_MS = _resolve_max_latency_ms()


def dispatch_result_or_raise(envelope: dict[str, Any]) -> Any:
    """Extract dispatcher result payload or fail-closed on envelope errors.

    Mutation rationale: ensure callers only continue on explicit successful
    dispatch outcomes and never consume ambiguous envelopes.
    Expected invariants: error envelopes, missing results, and explicit
    non-success result statuses raise deterministic RuntimeError values.
    """

    if not isinstance(envelope, dict):
        _LOGGER.error("dispatch_result_or_raise invalid_envelope")
        raise RuntimeError("dispatch failed:invalid_envelope")

    status = str(envelope.get("status") or "").strip().lower()
    if status == "error":
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        code = str(error.get("code") or "unknown")
        _LOGGER.error("dispatch_result_or_raise envelope_error", extra={"code": code})
        raise RuntimeError(f"dispatch failed:{code}")
    if status and status not in {"ok", "success"}:
        _LOGGER.error("dispatch_result_or_raise invalid_envelope_status", extra={"status": status})
        raise RuntimeError("dispatch failed:invalid_envelope_status")
    if "result" not in envelope:
        _LOGGER.error("dispatch_result_or_raise missing_result")
        raise RuntimeError("dispatch failed:missing_result")

    result = envelope["result"]
    if isinstance(result, dict) and "status" in result:
        result_status = str(result.get("status") or "").strip().lower()
        if result_status not in {"ok", "success"}:
            error_code = str(result.get("error_code") or "result_status_not_success")
            _LOGGER.error(
                "dispatch_result_or_raise non_success_result_status",
                extra={"result_status": result_status, "error_code": error_code},
            )
            raise RuntimeError(f"dispatch failed:{error_code}")
    return result


def _latency_budget_meta(*, route: str, latency_ms: float) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "route": route,
        "latency_ms": round(latency_ms, 3),
        "latency_target_ms": MAX_LATENCY_MS,
        "within_target": latency_ms <= MAX_LATENCY_MS,
    }
    if not meta["within_target"]:
        meta["warning"] = "latency_budget_exceeded"
        _LOGGER.warning("dispatcher latency target exceeded", extra={"route": route, "latency_ms": latency_ms})
        if runtime_metrics is not None:
            try:
                runtime_metrics.log(
                    event_type="dispatch_latency_budget_exceeded",
                    payload={"route": route, "latency_ms": round(latency_ms, 3), "target_ms": MAX_LATENCY_MS},
                    level="WARNING",
                )
            except Exception as exc:
                _LOGGER.warning(
                    "dispatcher runtime metrics write failed",
                    extra={"route": route, "latency_ms": round(latency_ms, 3), "exception": str(exc)},
                )
    return meta


def _error_envelope(*, code: str, message: str, route: str, latency_ms: float) -> dict[str, Any]:
    return {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
        "metadata": _latency_budget_meta(route=route, latency_ms=latency_ms),
    }


class Dispatcher:
    """Route requests through a preloaded registry."""

    def __init__(self, registry: HandlerRegistry) -> None:
        self._registry = registry

    def dispatch(self, key: str, payload: Any = None) -> dict[str, Any]:
        started = perf_counter()
        try:
            handler = self._registry.get(key)
        except KeyError:
            latency_ms = (perf_counter() - started) * 1000.0
            return _error_envelope(code="route_not_found", message=f"unknown route: {key}", route=key, latency_ms=latency_ms)

        try:
            result = handler(payload)
        except Exception as exc:  # pragma: no cover
            latency_ms = (perf_counter() - started) * 1000.0
            return _error_envelope(code="handler_execution_failed", message=str(exc), route=key, latency_ms=latency_ms)

        latency_ms = (perf_counter() - started) * 1000.0
        meta = _latency_budget_meta(route=key, latency_ms=latency_ms)
        if isinstance(result, dict):
            response = dict(result)
            metadata = dict(response.get("metadata") or {})
            metadata.update(meta)
            response["metadata"] = metadata
            return response
        return {"result": result, "metadata": meta}


# Compatibility function-based API supporting prior *args/**kwargs use.
def dispatch(tool_name: str, /, *args: Any, **kwargs: Any) -> dict[str, Any]:
    started_ns = monotonic_ns()
    try:
        run_tool = get_tool(tool_name)
    except KeyError:
        now_ns = monotonic_ns()
        return _error_envelope(
            code="route_not_found",
            message=f"unknown route: {tool_name}",
            route=tool_name,
            latency_ms=(now_ns - started_ns) / 1_000_000,
        )

    try:
        result = run_tool(*args, **kwargs)
    except Exception as exc:  # pragma: no cover
        now_ns = monotonic_ns()
        envelope = _error_envelope(
            code="handler_execution_failed",
            message=str(exc),
            route=tool_name,
            latency_ms=(now_ns - started_ns) / 1_000_000,
        )
        envelope["_dispatch_meta"] = {
            "tool": tool_name,
            "started_mono_ns": started_ns,
            "finished_mono_ns": now_ns,
            "latency_ns": max(0, now_ns - started_ns),
        }
        return envelope

    finished_ns = monotonic_ns()
    latency_ms = (finished_ns - started_ns) / 1_000_000
    envelope: dict[str, Any] = {
        "result": result,
        "metadata": _latency_budget_meta(route=tool_name, latency_ms=latency_ms),
        "_dispatch_meta": {
            "tool": tool_name,
            "started_mono_ns": started_ns,
            "finished_mono_ns": finished_ns,
            "latency_ns": max(0, finished_ns - started_ns),
            "latency_target_ms": MAX_LATENCY_MS,
            "within_target": latency_ms <= MAX_LATENCY_MS,
        },
    }
    if latency_ms > MAX_LATENCY_MS:
        envelope["_dispatch_meta"]["warning"] = "latency_budget_exceeded"
    return envelope


__all__ = ["Dispatcher", "dispatch", "dispatch_result_or_raise", "MAX_LATENCY_MS"]
