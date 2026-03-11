# SPDX-License-Identifier: Apache-2.0
"""Tests: routing_health_score signal in GovernanceHealthAggregator — Phase 23 / PR-23-01"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.health_aggregator import (
    HEALTH_DEGRADED_THRESHOLD,
    SIGNAL_WEIGHTS,
    GovernanceHealthAggregator,
    HealthSnapshot,
)


# ---------------------------------------------------------------------------
# Weight invariant tests
# ---------------------------------------------------------------------------


class TestSignalWeights:
    def test_weights_sum_to_one(self):
        total = sum(SIGNAL_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_weights_has_five_keys(self):
        assert len(SIGNAL_WEIGHTS) == 5

    def test_routing_health_score_present(self):
        assert "routing_health_score" in SIGNAL_WEIGHTS

    def test_routing_health_score_weight(self):
        assert abs(SIGNAL_WEIGHTS["routing_health_score"] - 0.15) < 1e-9

    def test_avg_reviewer_reputation_rebalanced(self):
        assert abs(SIGNAL_WEIGHTS["avg_reviewer_reputation"] - 0.25) < 1e-9

    def test_amendment_gate_pass_rate_rebalanced(self):
        assert abs(SIGNAL_WEIGHTS["amendment_gate_pass_rate"] - 0.22) < 1e-9

    def test_federation_divergence_clean_rebalanced(self):
        assert abs(SIGNAL_WEIGHTS["federation_divergence_clean"] - 0.22) < 1e-9

    def test_epoch_health_score_rebalanced(self):
        assert abs(SIGNAL_WEIGHTS["epoch_health_score"] - 0.16) < 1e-9


# ---------------------------------------------------------------------------
# Routing engine integration tests
# ---------------------------------------------------------------------------


def _make_engine_mock(health_score: float):
    report = MagicMock()
    report.health_score = health_score
    report.status = "green" if health_score >= 0.65 else ("amber" if health_score >= 0.35 else "red")
    report.dominant_strategy = "conservative_hold"
    report.report_digest = "sha256:" + "a" * 64
    engine = MagicMock()
    engine.generate_report.return_value = report
    return engine


class TestRoutingHealthSignal:
    def test_no_engine_defaults_to_one(self):
        agg = GovernanceHealthAggregator()
        snap = agg.compute("epoch-1")
        assert snap.signal_breakdown["routing_health_score"] == 1.0

    def test_engine_value_used(self):
        engine = _make_engine_mock(0.7)
        agg = GovernanceHealthAggregator(routing_analytics_engine=engine)
        snap = agg.compute("epoch-1")
        assert abs(snap.signal_breakdown["routing_health_score"] - 0.7) < 1e-9

    def test_engine_exception_defaults_to_one(self):
        engine = MagicMock()
        engine.generate_report.side_effect = RuntimeError("engine failure")
        agg = GovernanceHealthAggregator(routing_analytics_engine=engine)
        snap = agg.compute("epoch-1")
        assert snap.signal_breakdown["routing_health_score"] == 1.0

    def test_engine_value_clamped_above(self):
        engine = _make_engine_mock(1.5)  # OOB
        agg = GovernanceHealthAggregator(routing_analytics_engine=engine)
        snap = agg.compute("epoch-1")
        assert snap.signal_breakdown["routing_health_score"] <= 1.0

    def test_engine_value_clamped_below(self):
        engine = _make_engine_mock(-0.2)  # OOB
        agg = GovernanceHealthAggregator(routing_analytics_engine=engine)
        snap = agg.compute("epoch-1")
        assert snap.signal_breakdown["routing_health_score"] >= 0.0

    def test_routing_health_in_signal_breakdown(self):
        agg = GovernanceHealthAggregator()
        snap = agg.compute("epoch-1")
        assert "routing_health_score" in snap.signal_breakdown

    def test_routing_health_report_none_without_engine(self):
        agg = GovernanceHealthAggregator()
        snap = agg.compute("epoch-1")
        assert snap.routing_health_report is None

    def test_routing_health_report_dict_with_engine(self):
        engine = _make_engine_mock(0.82)
        agg = GovernanceHealthAggregator(routing_analytics_engine=engine)
        snap = agg.compute("epoch-1")
        assert isinstance(snap.routing_health_report, dict)
        assert snap.routing_health_report["available"] is True

    def test_routing_health_report_fields(self):
        engine = _make_engine_mock(0.82)
        agg = GovernanceHealthAggregator(routing_analytics_engine=engine)
        snap = agg.compute("epoch-1")
        rhr = snap.routing_health_report
        assert "status" in rhr
        assert "health_score" in rhr
        assert "dominant_strategy" in rhr
        assert "report_digest" in rhr

    def test_health_score_in_bounds(self):
        engine = _make_engine_mock(0.5)
        agg = GovernanceHealthAggregator(routing_analytics_engine=engine)
        snap = agg.compute("epoch-1")
        assert 0.0 <= snap.health_score <= 1.0

    def test_degraded_threshold_unchanged(self):
        assert HEALTH_DEGRADED_THRESHOLD == 0.60

    def test_degraded_flag_set_correctly(self):
        agg = GovernanceHealthAggregator()
        snap = agg.compute("epoch-1")
        # All signals degrade: reputation=0, amendment=0, epoch=0,
        # federation=1.0 (default), routing=1.0 (default)
        expected_h = (
            0.25 * 0.0   # reputation
            + 0.22 * 0.0   # amendment
            + 0.22 * 1.0   # federation default
            + 0.16 * 0.0   # epoch
            + 0.15 * 1.0   # routing default
        )
        assert abs(snap.health_score - expected_h) < 1e-9
        assert snap.degraded == (expected_h < HEALTH_DEGRADED_THRESHOLD)

    def test_full_aggregation_deterministic(self):
        engine = _make_engine_mock(0.75)
        agg1 = GovernanceHealthAggregator(routing_analytics_engine=engine)
        agg2 = GovernanceHealthAggregator(routing_analytics_engine=engine)
        snap1 = agg1.compute("epoch-det")
        snap2 = agg2.compute("epoch-det")
        assert abs(snap1.health_score - snap2.health_score) < 1e-12

    def test_weight_snapshot_digest_changes_with_rebalance(self):
        old_weights = {
            "avg_reviewer_reputation":     0.30,
            "amendment_gate_pass_rate":    0.25,
            "federation_divergence_clean": 0.25,
            "epoch_health_score":          0.20,
            "routing_health_score":        0.00,
        }
        # New weights (Phase 23) should produce a different digest
        new_weights = SIGNAL_WEIGHTS
        # Both produce valid snapshots; check digests differ
        agg_old = GovernanceHealthAggregator(weights={
            "avg_reviewer_reputation":     0.30,
            "amendment_gate_pass_rate":    0.25,
            "federation_divergence_clean": 0.25,
            "epoch_health_score":          0.15,
            "routing_health_score":        0.05,
        })
        agg_new = GovernanceHealthAggregator()
        snap_old = agg_old.compute("e")
        snap_new = agg_new.compute("e")
        assert snap_old.weight_snapshot_digest != snap_new.weight_snapshot_digest

    def test_journal_events_still_emitted(self):
        events = []
        agg = GovernanceHealthAggregator(
            journal_emit=lambda et, p: events.append(et)
        )
        agg.compute("epoch-j")
        assert any("snapshot" in e or "health" in e for e in events)

    def test_snapshot_is_dataclass(self):
        agg = GovernanceHealthAggregator()
        snap = agg.compute("epoch-1")
        assert isinstance(snap, HealthSnapshot)

    def test_existing_four_signals_still_collected(self):
        agg = GovernanceHealthAggregator()
        snap = agg.compute("epoch-1")
        for key in ("avg_reviewer_reputation", "amendment_gate_pass_rate",
                    "federation_divergence_clean", "epoch_health_score"):
            assert key in snap.signal_breakdown

    def test_routing_default_does_not_overinflate(self):
        """routing=1.0 default should not push h above expected ceiling."""
        agg = GovernanceHealthAggregator()
        snap = agg.compute("epoch-1")
        # max possible h with routing=1.0, federation=1.0, others=0.0
        max_h = SIGNAL_WEIGHTS["federation_divergence_clean"] + SIGNAL_WEIGHTS["routing_health_score"]
        assert snap.health_score <= max_h + 1e-9
