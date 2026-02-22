import os
import time

import pytest

from runtime.governance.validators.resource_bounds import ResourceBoundsExceeded, enforce_resource_bounds


def memory_heavy():
    chunks = []
    while True:
        chunks.append("x" * 5_000_000)


def timeout_function():
    time.sleep(2)


def quick_function():
    return 42


def test_wall_time_exceeded(monkeypatch):
    monkeypatch.setenv("ADAAD_MAX_WALL_SECONDS", "0.5")
    with pytest.raises(ResourceBoundsExceeded):
        enforce_resource_bounds(timeout_function)


def test_memory_exceeded(monkeypatch):
    monkeypatch.setenv("ADAAD_MAX_MEMORY_MB", "64")
    with pytest.raises(ResourceBoundsExceeded):
        enforce_resource_bounds(memory_heavy)


def test_success_within_bounds(monkeypatch):
    monkeypatch.setenv("ADAAD_MAX_WALL_SECONDS", "5")
    monkeypatch.setenv("ADAAD_MAX_MEMORY_MB", "256")
    monkeypatch.setenv("ADAAD_MAX_CPU_SECONDS", "5")
    assert enforce_resource_bounds(quick_function) == 42
