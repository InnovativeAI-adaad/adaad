import time

import pytest

from app.agents.mutation_request import MutationRequest, MutationTarget
from runtime import constitution
from runtime.governance.validators.resource_bounds import ResourceBoundsExceeded, enforce_resource_bounds
from runtime.platform.android_monitor import ResourceSnapshot


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


def test_constitution_resource_bounds_blocks_on_android_oom(monkeypatch: pytest.MonkeyPatch) -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[{"op": "replace", "path": "runtime/constitution.py", "value": "x"}],
        signature="cryovant-dev-test",
        nonce="n",
        targets=[MutationTarget(agent_id="test_subject", path="runtime/constitution.py", target_type="file", ops=[])],
    )
    monkeypatch.setenv("ADAAD_RESOURCE_MEMORY_MB", "1024")
    monkeypatch.setattr(
        constitution.AndroidMonitor,
        "snapshot",
        lambda self: ResourceSnapshot(battery_percent=80.0, memory_mb=4096.0, storage_mb=8_192.0, cpu_percent=20.0),
    )

    verdict = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)
    rule_verdict = next(item for item in verdict["verdicts"] if item["rule"] == "resource_bounds")

    assert rule_verdict["passed"] is False
    assert rule_verdict["details"]["reason"] == "resource_bounds_exceeded"
    assert "memory" in rule_verdict["details"]["details"]["violations"]


def test_constitution_resource_bounds_missing_telemetry_fails_for_strict_tier() -> None:
    validator = constitution.VALIDATOR_REGISTRY["resource_bounds"]
    request = MutationRequest(agent_id="test_subject", generation_ts="now", intent="test", ops=[], signature="", nonce="n")
    with constitution.deterministic_envelope_scope({"tier": constitution.Tier.PRODUCTION.name}):
        result = validator(request)

    assert result["ok"] is False
    assert result["reason"] == "resource_measurements_missing"
    assert result["details"]["has_observed"] is False
    assert result["details"]["has_telemetry"] is False
