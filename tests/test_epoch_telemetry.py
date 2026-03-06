# SPDX-License-Identifier: Apache-2.0
"""Tests for EpochTelemetry analytics engine."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from runtime.autonomy.epoch_telemetry import (
    ACCEPTANCE_RATE_HEALTHY_MAX,
    ACCEPTANCE_RATE_HEALTHY_MIN,
    PLATEAU_FREQUENCY_HEALTHY_MAX,
    EpochRecord,
    EpochTelemetry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    epoch_id: str = "epoch-0",
    epoch_index: int = 0,
    total: int = 10,
    accepted: int = 5,
    duration: float = 1.0,
    gain_weight: float = 0.50,
    coverage_weight: float = 0.30,
    recommended_agent: str = "beast",
    bandit_active: bool = False,
    bandit_total_pulls: int = 0,
    bandit_scores: dict | None = None,
    is_plateau: bool = False,
) -> EpochRecord:
    return EpochRecord(
        epoch_id=epoch_id,
        epoch_index=epoch_index,
        total_candidates=total,
        accepted_count=accepted,
        rejected_count=total - accepted,
        duration_seconds=duration,
        gain_weight=gain_weight,
        coverage_weight=coverage_weight,
        recommended_agent=recommended_agent,
        bandit_active=bandit_active,
        bandit_total_pulls=bandit_total_pulls,
        bandit_scores=bandit_scores or {},
        is_plateau=is_plateau,
    )


# ---------------------------------------------------------------------------
# EpochRecord basics
# ---------------------------------------------------------------------------

class TestEpochRecord:
    def test_acceptance_rate(self):
        r = _make_record(total=10, accepted=4)
        assert r.acceptance_rate == pytest.approx(0.4)

    def test_acceptance_rate_zero_candidates(self):
        r = _make_record(total=0, accepted=0)
        assert r.acceptance_rate == 0.0

    def test_to_dict_has_required_keys(self):
        r = _make_record()
        d = r.to_dict()
        for key in ("epoch_id", "epoch_index", "total_candidates", "accepted_count",
                    "acceptance_rate", "gain_weight", "coverage_weight",
                    "recommended_agent", "bandit_active", "is_plateau"):
            assert key in d


# ---------------------------------------------------------------------------
# EpochTelemetry — basic append and series
# ---------------------------------------------------------------------------

class TestEpochTelemetryBasic:
    def test_empty_epoch_count(self):
        t = EpochTelemetry()
        assert t.epoch_count() == 0

    def test_append_increments_count(self):
        t = EpochTelemetry()
        t.append(_make_record())
        assert t.epoch_count() == 1

    def test_acceptance_rate_series(self):
        t = EpochTelemetry()
        t.append(_make_record(total=10, accepted=3))
        t.append(_make_record(total=10, accepted=7))
        rates = t.acceptance_rate_series()
        assert rates == [pytest.approx(0.3), pytest.approx(0.7)]

    def test_rolling_acceptance_rate_window_1(self):
        t = EpochTelemetry()
        t.append(_make_record(total=10, accepted=4))
        t.append(_make_record(total=10, accepted=6))
        rolling = t.rolling_acceptance_rate(window=1)
        assert rolling[0] == pytest.approx(0.4)
        assert rolling[1] == pytest.approx(0.6)

    def test_rolling_acceptance_rate_window(self):
        t = EpochTelemetry()
        for i in range(4):
            t.append(_make_record(total=10, accepted=5, epoch_index=i, epoch_id=f"e{i}"))
        rolling = t.rolling_acceptance_rate(window=2)
        assert rolling[1] == pytest.approx(0.5)

    def test_weight_trajectory_keys(self):
        t = EpochTelemetry()
        t.append(_make_record(gain_weight=0.55, coverage_weight=0.35))
        traj = t.weight_trajectory()
        assert traj["gain_weight"] == [pytest.approx(0.55)]
        assert traj["coverage_weight"] == [pytest.approx(0.35)]


# ---------------------------------------------------------------------------
# Agent distribution and plateau
# ---------------------------------------------------------------------------

class TestAgentDistributionAndPlateau:
    def test_agent_distribution_count(self):
        t = EpochTelemetry()
        for agent in ["architect", "beast", "beast", "dream", "architect"]:
            t.append(_make_record(recommended_agent=agent))
        dist = t.agent_distribution()
        assert dist["architect"] == 2
        assert dist["beast"] == 2
        assert dist["dream"] == 1

    def test_plateau_events_empty(self):
        t = EpochTelemetry()
        t.append(_make_record(is_plateau=False))
        assert t.plateau_events() == []

    def test_plateau_events_detected(self):
        t = EpochTelemetry()
        t.append(_make_record(epoch_id="e0", epoch_index=0, is_plateau=False))
        t.append(_make_record(epoch_id="e1", epoch_index=1, is_plateau=True))
        events = t.plateau_events()
        assert len(events) == 1
        assert events[0]["epoch_id"] == "e1"

    def test_bandit_activation_epoch(self):
        t = EpochTelemetry()
        t.append(_make_record(bandit_active=False, epoch_index=0))
        t.append(_make_record(bandit_active=True,  epoch_index=1))
        assert t.bandit_activation_epoch() == 1

    def test_bandit_activation_epoch_none(self):
        t = EpochTelemetry()
        t.append(_make_record(bandit_active=False))
        assert t.bandit_activation_epoch() is None


# ---------------------------------------------------------------------------
# Health indicators
# ---------------------------------------------------------------------------

class TestHealthIndicators:
    def test_healthy_acceptance_rate(self):
        t = EpochTelemetry()
        t.append(_make_record(total=10, accepted=4))  # 40% — healthy
        hi = t.health_indicators()
        assert hi["acceptance_rate"]["status"] == "healthy"

    def test_warning_acceptance_rate_too_low(self):
        t = EpochTelemetry()
        t.append(_make_record(total=10, accepted=1))  # 10% — below 20%
        hi = t.health_indicators()
        assert hi["acceptance_rate"]["status"] == "warning"

    def test_warning_acceptance_rate_too_high(self):
        t = EpochTelemetry()
        t.append(_make_record(total=10, accepted=9))  # 90% — above 60%
        hi = t.health_indicators()
        assert hi["acceptance_rate"]["status"] == "warning"

    def test_healthy_weight_bounds(self):
        t = EpochTelemetry()
        t.append(_make_record(gain_weight=0.50, coverage_weight=0.30))
        hi = t.health_indicators()
        assert hi["weight_bounds"]["status"] == "healthy"

    def test_warning_weight_out_of_bounds(self):
        t = EpochTelemetry()
        t.append(_make_record(gain_weight=0.80, coverage_weight=0.30))  # 0.80 > 0.70
        hi = t.health_indicators()
        assert hi["weight_bounds"]["status"] == "warning"

    def test_plateau_frequency_healthy(self):
        t = EpochTelemetry()
        for i in range(10):
            t.append(_make_record(epoch_index=i, epoch_id=f"e{i}", is_plateau=(i == 3)))
        hi = t.health_indicators()
        assert hi["plateau_frequency"]["status"] == "healthy"
        assert hi["plateau_frequency"]["value"] == 1

    def test_plateau_frequency_warning(self):
        t = EpochTelemetry()
        for i in range(10):
            t.append(_make_record(epoch_index=i, epoch_id=f"e{i}", is_plateau=True))
        hi = t.health_indicators()
        assert hi["plateau_frequency"]["status"] == "warning"

    def test_insufficient_data_below_1(self):
        t = EpochTelemetry()
        hi = t.health_indicators()
        assert hi["acceptance_rate"]["status"] == "insufficient_data"

    def test_bandit_activation_indicator(self):
        t = EpochTelemetry()
        t.append(_make_record(bandit_active=True, epoch_index=0))
        hi = t.health_indicators()
        assert hi["bandit_activation"]["status"] == "active"
        assert hi["bandit_activation"]["activated_at_epoch"] == 0


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_report_structure(self):
        t = EpochTelemetry()
        t.append(_make_record())
        r = t.generate_report()
        for key in ("report_version", "epoch_count", "summary", "series",
                    "agent_distribution", "plateau_events", "health_indicators", "epochs"):
            assert key in r

    def test_report_version(self):
        t = EpochTelemetry()
        assert t.generate_report()["report_version"] == "1.0"

    def test_report_deterministic(self):
        """Identical records → identical reports (modulo generated_at timestamp)."""
        t1, t2 = EpochTelemetry(), EpochTelemetry()
        for _ in range(3):
            t1.append(_make_record(total=10, accepted=4))
            t2.append(_make_record(total=10, accepted=4))
        r1 = t1.generate_report()
        r2 = t2.generate_report()
        # Remove timestamp before comparison
        r1.pop("generated_at"); r2.pop("generated_at")
        # Remove recorded_at from epochs
        for ep in r1["epochs"]: ep.pop("recorded_at")
        for ep in r2["epochs"]: ep.pop("recorded_at")
        assert r1 == r2

    def test_summary_totals(self):
        t = EpochTelemetry()
        t.append(_make_record(total=10, accepted=3))
        t.append(_make_record(total=10, accepted=7))
        s = t.generate_report()["summary"]
        assert s["total_candidates"] == 20
        assert s["total_accepted"] == 10
        assert s["overall_acceptance_rate"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Persistence (save / load round-trip)
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load_round_trip(self):
        t = EpochTelemetry()
        t.append(_make_record(epoch_id="e-0", epoch_index=0, total=12, accepted=5))
        t.append(_make_record(epoch_id="e-1", epoch_index=1, total=8,  accepted=4, is_plateau=True))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "telemetry.json"
            t.save(path)
            restored = EpochTelemetry.load(path)

        assert restored.epoch_count() == 2
        assert restored._records[0].epoch_id == "e-0"
        assert restored._records[1].is_plateau is True

    def test_load_missing_file_returns_empty(self):
        t = EpochTelemetry.load(Path("/nonexistent/path.json"))
        assert t.epoch_count() == 0

    def test_load_corrupt_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("not valid json{{{")
            t = EpochTelemetry.load(path)
        assert t.epoch_count() == 0


# ---------------------------------------------------------------------------
# append_from_result integration
# ---------------------------------------------------------------------------

class TestAppendFromResult:
    def test_append_from_result_basic(self):
        t = EpochTelemetry()

        result = MagicMock()
        result.epoch_id = "epoch-42"
        result.total_candidates = 8
        result.accepted_count = 3
        result.duration_seconds = 2.5

        record = t.append_from_result(result)
        assert record.epoch_id == "epoch-42"
        assert record.total_candidates == 8
        assert record.accepted_count == 3
        assert t.epoch_count() == 1

    def test_append_from_result_with_landscape(self):
        t = EpochTelemetry()

        result = MagicMock()
        result.epoch_id = "epoch-1"
        result.total_candidates = 5
        result.accepted_count = 2
        result.duration_seconds = 1.0

        landscape = MagicMock()
        landscape.summary.return_value = {
            "recommended_agent": "architect",
            "is_plateau": False,
            "bandit": {
                "is_active": True,
                "total_pulls": 15,
                "ucb1_scores": {"architect": 0.9, "beast": 0.7, "dream": 0.5},
            },
        }

        record = t.append_from_result(result, landscape=landscape)
        assert record.recommended_agent == "architect"
        assert record.bandit_active is True
        assert record.bandit_total_pulls == 15
