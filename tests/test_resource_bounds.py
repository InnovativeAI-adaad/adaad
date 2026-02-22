# SPDX-License-Identifier: Apache-2.0

import time

import pytest

from runtime.governance.validators.resource_bounds import ResourceBoundsExceeded, enforce_resource_bounds


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
    monkeypatch.setenv("ADAAD_MAX_WALL_SECONDS", "5")
    monkeypatch.setenv("ADAAD_MAX_MEMORY_MB", "256")
    monkeypatch.setenv("ADAAD_MAX_CPU_SECONDS", "5")
    assert enforce_resource_bounds(_quick_function) == 42
