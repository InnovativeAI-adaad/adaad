# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard

from adaad.agents.mutation_request import MutationRequest, MutationTarget
from runtime.platform import android_monitor
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
    constitution = pytest.importorskip("runtime.constitution")

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




def test_resource_snapshot_tightens_thresholds_with_dynamic_agent_pressure() -> None:
    snap = ResourceSnapshot(
        battery_percent=60.0,
        memory_mb=1300.0,
        storage_mb=2400.0,
        cpu_percent=72.0,
        dynamic_agent_pressure=1.0,
    )
    assert snap.is_constrained()
    assert snap.should_throttle()

def test_probe_fallback_values_unchanged_and_diagnostics_emitted(monkeypatch) -> None:
    signals: list[dict[str, str]] = []

    def _capture_signal(
        *,
        probe: str,
        reason_code: str,
        fallback_value: float,
        source_path: str | None = None,
        error: Exception | None = None,
    ) -> None:
        payload = {"probe": probe, "reason_code": reason_code, "fallback_value": fallback_value}
        if source_path is not None:
            payload["source_path"] = source_path
        if error is not None:
            payload["error_type"] = type(error).__name__
        signals.append(payload)

    monkeypatch.setattr(android_monitor, "_emit_probe_fallback", _capture_signal)

    monkeypatch.setattr(Path, "read_text", lambda self, encoding="utf-8": (_ for _ in ()).throw(OSError("boom")))
    monkeypatch.setattr(android_monitor.os, "getloadavg", lambda: (_ for _ in ()).throw(OSError("no loadavg")))

    assert AndroidMonitor._read_battery() == 100.0
    assert AndroidMonitor._read_memory() == 8192.0
    assert AndroidMonitor._read_cpu() == 0.0

    assert [signal["reason_code"] for signal in signals] == [
        "battery_probe_unreadable",
        "meminfo_unreadable",
        "cpu_probe_unavailable",
    ]
    assert [signal["fallback_value"] for signal in signals] == [100.0, 8192.0, 0.0]
    assert signals[0]["source_path"] == "/sys/class/power_supply/battery/capacity"
    assert signals[1]["source_path"] == "/proc/meminfo"
    assert "source_path" not in signals[2]


def test_no_crash_on_partial_platform_unavailability(tmp_path: Path, monkeypatch) -> None:
    monitor = AndroidMonitor(tmp_path)
    monkeypatch.setattr(monitor, "is_android", True)
    monkeypatch.setattr(AndroidMonitor, "_read_battery", staticmethod(lambda: 100.0))
    monkeypatch.setattr(AndroidMonitor, "_read_memory", staticmethod(lambda: 8192.0))
    monkeypatch.setattr(AndroidMonitor, "_read_cpu", staticmethod(lambda: 0.0))
    monkeypatch.setattr(AndroidMonitor, "_read_storage", lambda self: 1024.0)

    snapshot = monitor.snapshot()

    assert snapshot == ResourceSnapshot(battery_percent=100.0, memory_mb=8192.0, storage_mb=1024.0, cpu_percent=0.0)


def test_emit_probe_fallback_logs_structured_warning_and_metric(monkeypatch) -> None:
    records: list[tuple[str, dict[str, object], str]] = []

    monkeypatch.setattr(
        android_monitor.metrics,
        "log",
        lambda event_type, payload, level="INFO": records.append((event_type, payload, level)),
    )

    android_monitor._emit_probe_fallback(
        probe="memory",
        reason_code="meminfo_parse_error",
        fallback_value=8192.0,
        source_path="/proc/meminfo",
        error=ValueError("bad"),
    )

    assert len(records) == 1
    event_type, payload, level = records[0]
    assert event_type == android_monitor.METRIC_EVENT
    assert level == "WARNING"
    assert payload == {
        "probe": "memory",
        "reason_code": "meminfo_parse_error",
        "fallback_value": 8192.0,
        "source_path": "/proc/meminfo",
        "error_type": "ValueError",
    }
