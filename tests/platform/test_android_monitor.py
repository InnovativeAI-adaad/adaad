# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from app.agents.mutation_request import MutationRequest, MutationTarget
from runtime import constitution
from runtime.platform.android_monitor import AndroidMonitor, ResourceSnapshot


def test_resource_snapshot_flags() -> None:
    snap = ResourceSnapshot(battery_percent=10.0, memory_mb=2000.0, storage_mb=5000.0, cpu_percent=10.0)
    assert snap.is_constrained()
    assert snap.should_throttle()


def test_android_monitor_snapshot_non_android(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(AndroidMonitor, "_detect_android", staticmethod(lambda: False))
    monitor = AndroidMonitor(tmp_path)
    snapshot = monitor.snapshot()
    assert snapshot.battery_percent == 100.0
    assert snapshot.storage_mb >= 0.0


def test_evaluation_state_merges_android_telemetry(monkeypatch) -> None:
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[{"op": "replace", "path": "runtime/constitution.py", "value": "x"}],
        signature="cryovant-dev-test",
        nonce="n",
        targets=[MutationTarget(agent_id="test_subject", path="runtime/constitution.py", target_type="file", ops=[])],
    )

    monkeypatch.setattr(
        constitution.AndroidMonitor,
        "snapshot",
        lambda self: ResourceSnapshot(battery_percent=22.0, memory_mb=1536.0, storage_mb=900.0, cpu_percent=81.0),
    )

    with constitution.deterministic_envelope_scope(
        {"platform_telemetry": {"memory_mb": 512.0, "cpu_percent": 10.0, "battery_percent": 90.0, "storage_mb": 4096.0}}
    ):
        verdict = constitution.evaluate_mutation(request, constitution.Tier.SANDBOX)

    resource_verdict = next(item for item in verdict["verdicts"] if item["rule"] == "resource_bounds")
    telemetry = resource_verdict["details"]["details"]["telemetry"]
    assert telemetry["memory_mb"] == 1536.0
    assert telemetry["cpu_percent"] == 81.0
    assert telemetry["battery_percent"] == 22.0
    assert telemetry["storage_mb"] == 900.0
