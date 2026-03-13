# SPDX-License-Identifier: Apache-2.0

import os
import time
import resource

import pytest

from runtime.governance.validators.resource_bounds import ResourceBoundsExceeded, enforce_resource_bounds

pytestmark = pytest.mark.regression_standard


_RESOURCE_ENV_KEYS = (
    "ADAAD_RESOURCE_WALL_SECONDS",
    "ADAAD_RESOURCE_MEMORY_MB",
    "ADAAD_RESOURCE_CPU_SECONDS",
    "ADAAD_MAX_WALL_SECONDS",
    "ADAAD_MAX_MEMORY_MB",
    "ADAAD_MAX_CPU_SECONDS",
)


@pytest.fixture(autouse=True)
def _restore_resource_process_state() -> None:
    env_snapshot = {key: os.environ.get(key) for key in _RESOURCE_ENV_KEYS}
    limits_snapshot = {
        name: resource.getrlimit(getattr(resource, name))
        for name in ("RLIMIT_AS", "RLIMIT_CPU", "RLIMIT_DATA")
        if hasattr(resource, name)
    }
    try:
        yield
    finally:
        for key, value in env_snapshot.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for name, limits in limits_snapshot.items():
            resource.setrlimit(getattr(resource, name), limits)


def _memory_heavy() -> None:
    chunks = []
    while True:
        chunks.append("x" * 5_000_000)


def _timeout_function() -> None:
    time.sleep(2)


def _cpu_heavy() -> int:
    total = 0
    for i in range(6_000_000):
        total += i
    return total


def _quick_function() -> int:
    return 42


def test_wall_time_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_MAX_WALL_SECONDS", "0.25")
    with pytest.raises(ResourceBoundsExceeded, match="resource_bounds_exceeded:wall_seconds") as exc:
        enforce_resource_bounds(_timeout_function)
    assert exc.value.event.resource == "wall_seconds"


def test_cpu_time_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_MAX_WALL_SECONDS", "3")
    monkeypatch.setenv("ADAAD_MAX_CPU_SECONDS", "0.05")
    with pytest.raises(ResourceBoundsExceeded, match="resource_bounds_exceeded:cpu_seconds") as exc:
        enforce_resource_bounds(_cpu_heavy)
    assert exc.value.event.resource == "cpu_seconds"


def test_memory_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_MAX_MEMORY_MB", "64")
    with pytest.raises(ResourceBoundsExceeded) as exc:
        enforce_resource_bounds(_memory_heavy)
    assert exc.value.event.resource == "memory_mb"


def test_success_within_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_RESOURCE_WALL_SECONDS", "5")
    monkeypatch.setenv("ADAAD_RESOURCE_MEMORY_MB", "256")
    monkeypatch.setenv("ADAAD_RESOURCE_CPU_SECONDS", "5")
    assert enforce_resource_bounds(_quick_function) == 42


def test_deprecated_aliases_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_MAX_WALL_SECONDS", "5")
    monkeypatch.setenv("ADAAD_MAX_MEMORY_MB", "256")
    monkeypatch.setenv("ADAAD_MAX_CPU_SECONDS", "5")
    assert enforce_resource_bounds(_quick_function) == 42


def test_canonical_vars_take_precedence_over_deprecated_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_RESOURCE_WALL_SECONDS", "5")
    monkeypatch.setenv("ADAAD_RESOURCE_CPU_SECONDS", "5")
    monkeypatch.setenv("ADAAD_MAX_WALL_SECONDS", "0.01")
    monkeypatch.setenv("ADAAD_MAX_CPU_SECONDS", "0.01")
    assert enforce_resource_bounds(_quick_function) == 42


def test_deprecated_alias_emits_warning_event(monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.governance.validators import resource_bounds

    events: list[dict[str, str]] = []

    def _capture_log(*, event_type: str, payload: dict, level: str = "INFO", element_id=None) -> None:
        del element_id
        events.append({"event_type": event_type, "level": level, "canonical": payload["canonical_env"]})

    monkeypatch.setattr(resource_bounds.metrics, "log", _capture_log)
    monkeypatch.setenv("ADAAD_MAX_WALL_SECONDS", "5")
    monkeypatch.delenv("ADAAD_RESOURCE_WALL_SECONDS", raising=False)

    assert enforce_resource_bounds(_quick_function) == 42
    assert any(e["event_type"] == "resource_limit_env_alias_deprecated" for e in events)
