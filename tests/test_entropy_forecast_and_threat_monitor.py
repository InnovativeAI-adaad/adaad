# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.entropy_forecast import EntropyBudgetForecaster
from runtime.governance.threat_monitor import ThreatMonitor, default_detectors


def test_entropy_forecaster_advisories() -> None:
    forecaster = EntropyBudgetForecaster()

    clear = forecaster.forecast(
        epoch_id="epoch-1",
        mutation_count=1,
        epoch_entropy_bits=100,
        per_mutation_ceiling_bits=128,
        per_epoch_ceiling_bits=4096,
    )
    assert clear["advisory"] == "clear"

    warn = forecaster.forecast(
        epoch_id="epoch-1",
        mutation_count=10,
        epoch_entropy_bits=3500,
        per_mutation_ceiling_bits=128,
        per_epoch_ceiling_bits=4096,
    )
    assert warn["advisory"] == "warn"

    block = forecaster.forecast(
        epoch_id="epoch-1",
        mutation_count=10,
        epoch_entropy_bits=4096,
        per_mutation_ceiling_bits=128,
        per_epoch_ceiling_bits=4096,
    )
    assert block["advisory"] == "block"


def test_threat_monitor_runs_detectors_in_deterministic_order() -> None:
    calls: list[str] = []

    def z_detector(_context: dict[str, object]) -> dict[str, object]:
        calls.append("z")
        return {"triggered": False, "severity": 0.1, "recommendation": "continue"}

    def a_detector(_context: dict[str, object]) -> dict[str, object]:
        calls.append("a")
        return {"triggered": True, "severity": 0.7, "recommendation": "escalate", "reason": "signal"}

    monitor = ThreatMonitor(detectors={"z": z_detector, "a": a_detector})
    result = monitor.scan(epoch_id="epoch-1", mutation_count=3, events=[{"status": "ok"}], window_size=1)

    assert calls == ["a", "z"]
    assert result["recommendation"] == "escalate"


def test_default_threat_monitor_halts_on_failure_spike() -> None:
    monitor = ThreatMonitor(detectors=default_detectors())
    result = monitor.scan(
        epoch_id="epoch-1",
        mutation_count=5,
        events=[
            {"status": "failed"},
            {"status": "rejected"},
            {"status": "error"},
        ],
        window_size=3,
    )

    assert result["recommendation"] == "halt"
