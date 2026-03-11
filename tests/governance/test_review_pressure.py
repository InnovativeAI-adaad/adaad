# SPDX-License-Identifier: Apache-2.0
"""Tests for PR-7-03: Tier Calibration + Constitutional Floor.

Validates:
- validate_tier_config rejects configs violating constitutional floor
- compute_tier_reviewer_count adjusts counts correctly per reputation
- Constitutional floor is never breached
- Clamping to [min_count, max_count] is enforced
- Calibration digest is deterministic
- Panel calibration produces per-tier records
- Unknown tier raises ValueError
- Score is clamped to [0.0, 1.0]
"""
from __future__ import annotations

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.review_pressure import (
    CONSTITUTIONAL_FLOOR_MIN_REVIEWERS,
    DEFAULT_TIER_CONFIG,
    HIGH_REPUTATION_THRESHOLD,
    LOW_REPUTATION_THRESHOLD,
    compute_panel_calibration,
    compute_tier_reviewer_count,
    validate_tier_config,
)


# ---------------------------------------------------------------------------
# validate_tier_config
# ---------------------------------------------------------------------------

def test_default_tier_config_is_valid() -> None:
    cfg = validate_tier_config(DEFAULT_TIER_CONFIG)
    assert set(cfg.keys()) == {"low", "standard", "critical", "governance"}


def test_tier_config_min_below_constitutional_floor_raises() -> None:
    bad = {"low": {"base_count": 1, "min_count": 0, "max_count": 2}}
    with pytest.raises(ValueError, match="constitutional floor"):
        validate_tier_config(bad)


def test_tier_config_base_below_min_raises() -> None:
    bad = {"standard": {"base_count": 0, "min_count": 1, "max_count": 3}}
    with pytest.raises(ValueError, match="min_count <= base_count"):
        validate_tier_config(bad)


def test_tier_config_base_above_max_raises() -> None:
    bad = {"standard": {"base_count": 5, "min_count": 1, "max_count": 3}}
    with pytest.raises(ValueError, match="min_count <= base_count"):
        validate_tier_config(bad)


# ---------------------------------------------------------------------------
# Nominal band (no adjustment)
# ---------------------------------------------------------------------------

def test_nominal_score_no_adjustment() -> None:
    score = (HIGH_REPUTATION_THRESHOLD + LOW_REPUTATION_THRESHOLD) / 2
    result = compute_tier_reviewer_count("standard", score)
    assert result["adjustment"] == 0
    assert result["adjusted_count"] == DEFAULT_TIER_CONFIG["standard"]["base_count"]


# ---------------------------------------------------------------------------
# High reputation: count reduced
# ---------------------------------------------------------------------------

def test_high_reputation_reduces_count() -> None:
    result = compute_tier_reviewer_count("standard", HIGH_REPUTATION_THRESHOLD)
    assert result["adjustment"] == -1
    assert result["adjusted_count"] == DEFAULT_TIER_CONFIG["standard"]["base_count"] - 1


def test_high_reputation_respects_min_count() -> None:
    # "low" tier: base=1, min=1 — cannot go below 1
    result = compute_tier_reviewer_count("low", 1.0)
    assert result["adjusted_count"] >= result["min_count"]
    assert result["adjusted_count"] >= CONSTITUTIONAL_FLOOR_MIN_REVIEWERS


# ---------------------------------------------------------------------------
# Low reputation: count increased
# ---------------------------------------------------------------------------

def test_low_reputation_increases_count() -> None:
    result = compute_tier_reviewer_count("standard", LOW_REPUTATION_THRESHOLD)
    assert result["adjustment"] == 1
    assert result["adjusted_count"] == DEFAULT_TIER_CONFIG["standard"]["base_count"] + 1


def test_low_reputation_respects_max_count() -> None:
    # Force all tiers to a narrow config to test ceiling
    narrow_config = {
        "critical": {"base_count": 3, "min_count": 2, "max_count": 3}
    }
    result = compute_tier_reviewer_count("critical", 0.0, tier_config=narrow_config)
    assert result["adjusted_count"] <= narrow_config["critical"]["max_count"]


# ---------------------------------------------------------------------------
# Constitutional floor invariant
# ---------------------------------------------------------------------------

def test_constitutional_floor_enforced_field_always_true() -> None:
    for score in [0.0, 0.5, 1.0]:
        for tier in DEFAULT_TIER_CONFIG:
            result = compute_tier_reviewer_count(tier, score)
            assert result["constitutional_floor_enforced"] is True


def test_adjusted_count_never_below_constitutional_floor() -> None:
    for score in [0.0, 0.01, 0.5, 0.99, 1.0]:
        for tier in DEFAULT_TIER_CONFIG:
            result = compute_tier_reviewer_count(tier, score)
            assert result["adjusted_count"] >= CONSTITUTIONAL_FLOOR_MIN_REVIEWERS, (
                f"tier={tier} score={score} adjusted={result['adjusted_count']}"
            )


# ---------------------------------------------------------------------------
# Score clamping
# ---------------------------------------------------------------------------

def test_score_above_1_clamped() -> None:
    result_over = compute_tier_reviewer_count("standard", 1.5)
    result_exact = compute_tier_reviewer_count("standard", 1.0)
    assert result_over["composite_score"] == result_exact["composite_score"]


def test_score_below_0_clamped() -> None:
    result_under = compute_tier_reviewer_count("standard", -0.5)
    result_exact = compute_tier_reviewer_count("standard", 0.0)
    assert result_under["composite_score"] == result_exact["composite_score"]


# ---------------------------------------------------------------------------
# Unknown tier
# ---------------------------------------------------------------------------

def test_unknown_tier_raises() -> None:
    with pytest.raises(ValueError, match="Unknown tier"):
        compute_tier_reviewer_count("nonexistent_tier", 0.5)


# ---------------------------------------------------------------------------
# Calibration digest determinism
# ---------------------------------------------------------------------------

def test_calibration_digest_deterministic() -> None:
    r1 = compute_tier_reviewer_count("standard", 0.85)
    r2 = compute_tier_reviewer_count("standard", 0.85)
    assert r1["calibration_digest"] == r2["calibration_digest"]
    assert r1["calibration_digest"].startswith("sha256:")


def test_calibration_digest_differs_for_different_score() -> None:
    r1 = compute_tier_reviewer_count("standard", 0.85)
    r2 = compute_tier_reviewer_count("standard", 0.30)
    assert r1["calibration_digest"] != r2["calibration_digest"]


def test_calibration_digest_differs_for_different_tier() -> None:
    r1 = compute_tier_reviewer_count("standard", 0.85)
    r2 = compute_tier_reviewer_count("critical", 0.85)
    assert r1["calibration_digest"] != r2["calibration_digest"]


# ---------------------------------------------------------------------------
# Panel calibration
# ---------------------------------------------------------------------------

def test_panel_calibration_returns_all_tiers() -> None:
    scores = {"low": 0.9, "standard": 0.5, "critical": 0.2}
    results = compute_panel_calibration(scores)
    assert set(results.keys()) == {"low", "standard", "critical"}
    for tier, record in results.items():
        assert record["tier"] == tier


def test_panel_calibration_empty() -> None:
    results = compute_panel_calibration({})
    assert results == {}


# ---------------------------------------------------------------------------
# All tiers: base count structure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tier", list(DEFAULT_TIER_CONFIG.keys()))
def test_all_tiers_return_valid_structure(tier: str) -> None:
    result = compute_tier_reviewer_count(tier, 0.6)
    assert "adjusted_count" in result
    assert "constitutional_floor_enforced" in result
    assert "calibration_digest" in result
    assert result["min_count"] >= CONSTITUTIONAL_FLOOR_MIN_REVIEWERS
