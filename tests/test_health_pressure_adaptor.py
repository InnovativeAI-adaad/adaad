# SPDX-License-Identifier: Apache-2.0
"""Tests: HealthPressureAdaptor — Phase 24 / PR-24-01"""
from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.health_pressure_adaptor import (
    ADAPTOR_VERSION,
    DEFAULT_AMBER_THRESHOLD,
    DEFAULT_RED_THRESHOLD,
    HealthPressureAdaptor,
    PressureAdjustment,
)
from runtime.governance.review_pressure import (
    CONSTITUTIONAL_FLOOR_MIN_REVIEWERS,
    DEFAULT_TIER_CONFIG,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _adaptor() -> HealthPressureAdaptor:
    return HealthPressureAdaptor()


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_default_construction(self):
        a = _adaptor()
        assert a is not None

    def test_custom_tier_config_accepted(self):
        cfg = {
            "low":      {"base_count": 1, "min_count": 1, "max_count": 2},
            "standard": {"base_count": 2, "min_count": 1, "max_count": 3},
            "critical": {"base_count": 3, "min_count": 2, "max_count": 4},
            "governance": {"base_count": 3, "min_count": 3, "max_count": 5},
        }
        a = HealthPressureAdaptor(tier_config=cfg)
        assert a is not None

    def test_red_gte_amber_raises(self):
        with pytest.raises(ValueError):
            HealthPressureAdaptor(amber_threshold=0.60, red_threshold=0.80)

    def test_red_eq_amber_raises(self):
        with pytest.raises(ValueError):
            HealthPressureAdaptor(amber_threshold=0.70, red_threshold=0.70)


# ---------------------------------------------------------------------------
# Band classification tests
# ---------------------------------------------------------------------------


class TestBandClassification:
    def test_score_1_0_is_green_none(self):
        adj = _adaptor().compute(1.0)
        assert adj.health_band == "green"
        assert adj.pressure_tier == "none"

    def test_score_amber_threshold_is_green(self):
        adj = _adaptor().compute(DEFAULT_AMBER_THRESHOLD)
        assert adj.health_band == "green"
        assert adj.pressure_tier == "none"

    def test_score_just_below_amber_is_amber(self):
        adj = _adaptor().compute(DEFAULT_AMBER_THRESHOLD - 0.001)
        assert adj.health_band == "amber"
        assert adj.pressure_tier == "elevated"

    def test_score_red_threshold_is_amber(self):
        adj = _adaptor().compute(DEFAULT_RED_THRESHOLD)
        assert adj.health_band == "amber"
        assert adj.pressure_tier == "elevated"

    def test_score_just_below_red_is_red(self):
        adj = _adaptor().compute(DEFAULT_RED_THRESHOLD - 0.001)
        assert adj.health_band == "red"
        assert adj.pressure_tier == "critical"

    def test_score_0_0_is_red_critical(self):
        adj = _adaptor().compute(0.0)
        assert adj.health_band == "red"
        assert adj.pressure_tier == "critical"

    def test_score_clamped_above_1(self):
        adj = _adaptor().compute(1.5)
        assert adj.health_score == 1.0
        assert adj.pressure_tier == "none"

    def test_score_clamped_below_0(self):
        adj = _adaptor().compute(-0.5)
        assert adj.health_score == 0.0
        assert adj.pressure_tier == "critical"


# ---------------------------------------------------------------------------
# Adjustment correctness
# ---------------------------------------------------------------------------


class TestAdjustmentCorrectness:
    def test_green_no_adjustment(self):
        adj = _adaptor().compute(0.90)
        assert adj.adjusted_tiers == ()
        assert adj.proposed_tier_config["standard"]["min_count"] == \
               DEFAULT_TIER_CONFIG["standard"]["min_count"]

    def test_elevated_standard_min_count_raised(self):
        adj = _adaptor().compute(0.70)
        baseline = DEFAULT_TIER_CONFIG["standard"]["min_count"]
        assert adj.proposed_tier_config["standard"]["min_count"] == baseline + 1

    def test_elevated_critical_min_count_raised(self):
        adj = _adaptor().compute(0.70)
        baseline = DEFAULT_TIER_CONFIG["critical"]["min_count"]
        assert adj.proposed_tier_config["critical"]["min_count"] == baseline + 1

    def test_elevated_governance_unchanged(self):
        adj = _adaptor().compute(0.70)
        baseline = DEFAULT_TIER_CONFIG["governance"]["min_count"]
        assert adj.proposed_tier_config["governance"]["min_count"] == baseline

    def test_critical_standard_min_count_raised(self):
        adj = _adaptor().compute(0.50)
        baseline = DEFAULT_TIER_CONFIG["standard"]["min_count"]
        assert adj.proposed_tier_config["standard"]["min_count"] == baseline + 1

    def test_critical_critical_min_count_raised(self):
        adj = _adaptor().compute(0.50)
        baseline = DEFAULT_TIER_CONFIG["critical"]["min_count"]
        assert adj.proposed_tier_config["critical"]["min_count"] == baseline + 1

    def test_critical_governance_min_count_raised(self):
        adj = _adaptor().compute(0.50)
        baseline = DEFAULT_TIER_CONFIG["governance"]["min_count"]
        assert adj.proposed_tier_config["governance"]["min_count"] == baseline + 1

    def test_low_tier_never_adjusted_elevated(self):
        adj = _adaptor().compute(0.70)
        assert adj.proposed_tier_config["low"]["min_count"] == \
               DEFAULT_TIER_CONFIG["low"]["min_count"]

    def test_low_tier_never_adjusted_critical(self):
        adj = _adaptor().compute(0.10)
        assert adj.proposed_tier_config["low"]["min_count"] == \
               DEFAULT_TIER_CONFIG["low"]["min_count"]

    def test_proposed_min_never_exceeds_max(self):
        adj = _adaptor().compute(0.10)
        for tier, cfg in adj.proposed_tier_config.items():
            assert cfg["min_count"] <= cfg["max_count"], \
                f"tier {tier!r}: min_count {cfg['min_count']} > max_count {cfg['max_count']}"

    def test_proposed_min_never_below_floor(self):
        adj = _adaptor().compute(0.10)
        for tier, cfg in adj.proposed_tier_config.items():
            assert cfg["min_count"] >= CONSTITUTIONAL_FLOOR_MIN_REVIEWERS


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------


class TestStructuralInvariants:
    def test_advisory_only_always_true(self):
        for score in (0.0, 0.50, 0.70, 1.0):
            adj = _adaptor().compute(score)
            assert adj.advisory_only is True

    def test_adaptor_version(self):
        adj = _adaptor().compute(0.50)
        assert adj.adaptor_version == "24.0"
        assert adj.adaptor_version == ADAPTOR_VERSION

    def test_adjustment_digest_sha256_format(self):
        adj = _adaptor().compute(0.70)
        assert adj.adjustment_digest.startswith("sha256:")
        assert len(adj.adjustment_digest) == 7 + 64

    def test_adjustment_digest_deterministic(self):
        a1 = _adaptor().compute(0.70)
        a2 = _adaptor().compute(0.70)
        assert a1.adjustment_digest == a2.adjustment_digest

    def test_different_scores_different_digests(self):
        a1 = _adaptor().compute(0.70)
        a2 = _adaptor().compute(0.50)
        assert a1.adjustment_digest != a2.adjustment_digest

    def test_pressure_adjustment_is_frozen(self):
        adj = _adaptor().compute(0.70)
        with pytest.raises(Exception):
            adj.advisory_only = False  # type: ignore[misc]

    def test_baseline_tier_config_matches_default(self):
        adj = _adaptor().compute(0.70)
        for tier in DEFAULT_TIER_CONFIG:
            assert adj.baseline_tier_config[tier] == DEFAULT_TIER_CONFIG[tier]

    def test_adjusted_tiers_sorted(self):
        adj = _adaptor().compute(0.70)
        assert list(adj.adjusted_tiers) == sorted(adj.adjusted_tiers)

    def test_green_adjusted_tiers_empty(self):
        adj = _adaptor().compute(0.90)
        assert adj.adjusted_tiers == ()
