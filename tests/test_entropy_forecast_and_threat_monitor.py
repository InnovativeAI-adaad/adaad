import pytest
pytestmark = pytest.mark.regression_standard
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


def test_default_threat_monitor_reports_predicted_risk_and_attributions() -> None:
    monitor = ThreatMonitor(detectors=default_detectors(), default_window_size=6)
    result = monitor.scan(
        epoch_id="epoch-risk",
        mutation_count=6,
        events=[
            {"status": "ok", "divergence": False, "resource_pressure": 1.0},
            {"status": "failed", "divergence": False, "resource_pressure": 1.0},
            {"status": "ok", "divergence": False, "resource_pressure": 1.0},
            {"status": "failed", "divergence": True, "resource_pressure": 1.2},
            {"status": "failed", "divergence": True, "resource_pressure": 1.3},
            {"status": "failed", "divergence": True, "resource_pressure": 4.5},
        ],
        window_size=6,
    )

    assert "predicted_risk" in result
    assert result["predicted_risk"]["score"] > 0.0
    assert result["predicted_risk"]["risk_level"] in {"medium", "high", "critical"}
    assert len(result["predicted_risk"]["attributions"]) == len(result["findings"])
    assert result["predicted_risk"]["attributions"][0]["contribution"] >= result["predicted_risk"]["attributions"][-1]["contribution"]


def test_threat_monitor_anomaly_detectors_use_bounded_window() -> None:
    monitor = ThreatMonitor(detectors=default_detectors(), default_window_size=4)
    result = monitor.scan(
        epoch_id="epoch-window",
        mutation_count=8,
        events=[
            {"status": "failed", "divergence": False, "resource_pressure": 99.0},
            {"status": "failed", "divergence": False, "resource_pressure": 99.0},
            {"status": "ok", "divergence": False, "resource_pressure": 1.0},
            {"status": "ok", "divergence": False, "resource_pressure": 1.0},
            {"status": "ok", "divergence": False, "resource_pressure": 1.0},
            {"status": "ok", "divergence": True, "resource_pressure": 1.0},
            {"status": "failed", "divergence": True, "resource_pressure": 1.0},
            {"status": "failed", "divergence": True, "resource_pressure": 4.0},
        ],
    )

    assert result["window_event_count"] == 4
    findings = {item["detector"]: item for item in result["findings"]}
    assert findings["failure_density_shift"]["triggered"]
    assert findings["resource_spike"]["triggered"]
