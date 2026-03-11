# SPDX-License-Identifier: Apache-2.0
"""Tests for PR-7-02: Reviewer Reputation Scoring Engine.

Validates:
- Weight validation (required dimensions, sum-to-1, no negatives)
- Snapshot digest determinism
- Per-dimension scorer correctness
- Composite score weighting and clamping
- Epoch scoping (only matching epoch_id consumed)
- Reviewer scoping (only matching reviewer_id consumed)
- scoring_algorithm_version binding
- Batch compute produces per-reviewer records
- Score digest is deterministic
- Empty event stream yields neutral/default scores
"""
from __future__ import annotations

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.reviewer_reputation import (
    DEFAULT_EPOCH_WEIGHTS,
    SCORING_ALGORITHM_VERSION,
    compute_epoch_reputation_batch,
    compute_reviewer_reputation,
    snapshot_digest,
    validate_epoch_weights,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _outcome_event(
    reviewer_id: str,
    epoch_id: str,
    *,
    latency_seconds: float = 3600.0,
    sla_seconds: int = 86400,
    overridden_by_authority: bool = False,
    long_term_mutation_impact_score: float | None = None,
    governance_alignment_score: float | None = None,
) -> dict:
    payload: dict = {
        "reviewer_id": reviewer_id,
        "review_id": f"rv-{reviewer_id}-{epoch_id}",
        "mutation_id": "mut-test",
        "decision": "approve",
        "latency_seconds": latency_seconds,
        "sla_seconds": sla_seconds,
        "epoch_id": epoch_id,
        "scoring_algorithm_version": SCORING_ALGORITHM_VERSION,
        "overridden_by_authority": overridden_by_authority,
    }
    if long_term_mutation_impact_score is not None:
        payload["long_term_mutation_impact_score"] = long_term_mutation_impact_score
    if governance_alignment_score is not None:
        payload["governance_alignment_score"] = governance_alignment_score
    return {"event_type": "reviewer_action_outcome", "payload": payload}


# ---------------------------------------------------------------------------
# Weight validation
# ---------------------------------------------------------------------------

def test_default_weights_are_valid() -> None:
    validated = validate_epoch_weights(DEFAULT_EPOCH_WEIGHTS)
    assert abs(sum(validated.values()) - 1.0) < 0.001


def test_weights_missing_dimension_raises() -> None:
    bad = {"latency": 0.5, "override_rate": 0.5}
    with pytest.raises(ValueError, match="missing required dimensions"):
        validate_epoch_weights(bad)


def test_negative_weight_raises() -> None:
    bad = {**DEFAULT_EPOCH_WEIGHTS, "latency": -0.1, "override_rate": 0.5}
    with pytest.raises(ValueError, match="must be >= 0"):
        validate_epoch_weights(bad)


def test_weights_not_summing_to_one_raises() -> None:
    bad = {"latency": 0.5, "override_rate": 0.5, "long_term_mutation_impact": 0.5, "governance_alignment": 0.5}
    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_epoch_weights(bad)


# ---------------------------------------------------------------------------
# Snapshot digest
# ---------------------------------------------------------------------------

def test_snapshot_digest_deterministic() -> None:
    d1 = snapshot_digest("epoch-7", DEFAULT_EPOCH_WEIGHTS)
    d2 = snapshot_digest("epoch-7", DEFAULT_EPOCH_WEIGHTS)
    assert d1 == d2
    assert d1.startswith("sha256:")


def test_snapshot_digest_differs_for_different_epoch() -> None:
    d1 = snapshot_digest("epoch-7", DEFAULT_EPOCH_WEIGHTS)
    d2 = snapshot_digest("epoch-8", DEFAULT_EPOCH_WEIGHTS)
    assert d1 != d2


def test_snapshot_digest_differs_for_different_weights() -> None:
    w2 = {**DEFAULT_EPOCH_WEIGHTS, "latency": 0.25, "override_rate": 0.25}
    d1 = snapshot_digest("epoch-7", DEFAULT_EPOCH_WEIGHTS)
    d2 = snapshot_digest("epoch-7", w2)
    assert d1 != d2


# ---------------------------------------------------------------------------
# Epoch scoping
# ---------------------------------------------------------------------------

def test_events_from_different_epoch_ignored() -> None:
    events = [
        _outcome_event("alice", "epoch-7"),
        _outcome_event("alice", "epoch-8"),  # different epoch — must be ignored
    ]
    result = compute_reviewer_reputation("alice", events, epoch_id="epoch-7")
    assert result["event_count"] == 1


def test_events_from_different_reviewer_ignored() -> None:
    events = [
        _outcome_event("alice", "epoch-7"),
        _outcome_event("bob", "epoch-7"),
    ]
    result = compute_reviewer_reputation("alice", events, epoch_id="epoch-7")
    assert result["event_count"] == 1


# ---------------------------------------------------------------------------
# Empty event stream
# ---------------------------------------------------------------------------

def test_empty_event_stream_returns_neutral_score() -> None:
    result = compute_reviewer_reputation("alice", [], epoch_id="epoch-7")
    assert result["event_count"] == 0
    assert 0.0 <= result["composite_score"] <= 1.0
    assert result["reviewer_id"] == "alice"
    assert result["epoch_id"] == "epoch-7"


# ---------------------------------------------------------------------------
# Composite score correctness
# ---------------------------------------------------------------------------

def test_perfect_reviewer_gets_high_score() -> None:
    """Reviewer who: answers instantly, never overridden, perfect impact/alignment."""
    events = [
        _outcome_event(
            "alice", "epoch-7",
            latency_seconds=0.0,
            overridden_by_authority=False,
            long_term_mutation_impact_score=1.0,
            governance_alignment_score=1.0,
        )
        for _ in range(5)
    ]
    result = compute_reviewer_reputation("alice", events, epoch_id="epoch-7")
    assert result["composite_score"] >= 0.95


def test_poor_reviewer_gets_low_score() -> None:
    """Reviewer: always late, always overridden, low impact/alignment."""
    events = [
        _outcome_event(
            "bob", "epoch-7",
            latency_seconds=200_000.0,
            sla_seconds=86400,
            overridden_by_authority=True,
            long_term_mutation_impact_score=0.0,
            governance_alignment_score=0.0,
        )
        for _ in range(5)
    ]
    result = compute_reviewer_reputation("bob", events, epoch_id="epoch-7")
    assert result["composite_score"] <= 0.20


def test_composite_is_clamped_to_unit_interval() -> None:
    events = [_outcome_event("alice", "epoch-7")]
    result = compute_reviewer_reputation("alice", events, epoch_id="epoch-7")
    assert 0.0 <= result["composite_score"] <= 1.0


def test_override_count_tracked() -> None:
    events = [
        _outcome_event("alice", "epoch-7", overridden_by_authority=True),
        _outcome_event("alice", "epoch-7", overridden_by_authority=False),
        _outcome_event("alice", "epoch-7", overridden_by_authority=True),
    ]
    result = compute_reviewer_reputation("alice", events, epoch_id="epoch-7")
    assert result["override_count"] == 2
    assert result["event_count"] == 3


# ---------------------------------------------------------------------------
# Custom epoch weights
# ---------------------------------------------------------------------------

def test_custom_weights_affect_score() -> None:
    events = [
        _outcome_event("alice", "epoch-7", latency_seconds=0.0, overridden_by_authority=True,
                       long_term_mutation_impact_score=0.0, governance_alignment_score=0.0)
    ]
    # Weight latency very high → latency=1.0 should produce higher composite
    weights_latency_heavy = {
        "latency": 0.97,
        "override_rate": 0.01,
        "long_term_mutation_impact": 0.01,
        "governance_alignment": 0.01,
    }
    weights_override_heavy = {
        "latency": 0.01,
        "override_rate": 0.97,
        "long_term_mutation_impact": 0.01,
        "governance_alignment": 0.01,
    }
    score_latency = compute_reviewer_reputation(
        "alice", events, epoch_id="epoch-7", epoch_weights=weights_latency_heavy
    )["composite_score"]
    score_override = compute_reviewer_reputation(
        "alice", events, epoch_id="epoch-7", epoch_weights=weights_override_heavy
    )["composite_score"]
    # Latency=perfect but override=overridden → latency-heavy should be higher
    assert score_latency > score_override


def test_weight_snapshot_digest_in_record() -> None:
    result = compute_reviewer_reputation("alice", [], epoch_id="epoch-7")
    expected_digest = snapshot_digest("epoch-7", DEFAULT_EPOCH_WEIGHTS)
    assert result["epoch_weight_snapshot_digest"] == expected_digest


# ---------------------------------------------------------------------------
# scoring_algorithm_version binding
# ---------------------------------------------------------------------------

def test_scoring_algorithm_version_recorded() -> None:
    result = compute_reviewer_reputation("alice", [], epoch_id="epoch-7")
    assert result["scoring_algorithm_version"] == SCORING_ALGORITHM_VERSION


def test_custom_scoring_algorithm_version_recorded() -> None:
    result = compute_reviewer_reputation(
        "alice", [], epoch_id="epoch-7", scoring_algorithm_version="2.0"
    )
    assert result["scoring_algorithm_version"] == "2.0"


# ---------------------------------------------------------------------------
# Score digest determinism
# ---------------------------------------------------------------------------

def test_score_digest_is_deterministic() -> None:
    events = [_outcome_event("alice", "epoch-7")]
    r1 = compute_reviewer_reputation("alice", events, epoch_id="epoch-7")
    r2 = compute_reviewer_reputation("alice", list(events), epoch_id="epoch-7")
    assert r1["score_digest"] == r2["score_digest"]


def test_score_digest_differs_for_different_events() -> None:
    e1 = [_outcome_event("alice", "epoch-7", latency_seconds=100.0)]
    e2 = [_outcome_event("alice", "epoch-7", latency_seconds=500.0)]
    r1 = compute_reviewer_reputation("alice", e1, epoch_id="epoch-7")
    r2 = compute_reviewer_reputation("alice", e2, epoch_id="epoch-7")
    assert r1["score_digest"] != r2["score_digest"]


# ---------------------------------------------------------------------------
# Batch compute
# ---------------------------------------------------------------------------

def test_batch_compute_returns_per_reviewer_records() -> None:
    events = [
        _outcome_event("alice", "epoch-7"),
        _outcome_event("bob", "epoch-7"),
        _outcome_event("carol", "epoch-7"),
    ]
    results = compute_epoch_reputation_batch(
        ["alice", "bob", "carol"], events, epoch_id="epoch-7"
    )
    assert set(results.keys()) == {"alice", "bob", "carol"}
    for reviewer_id, record in results.items():
        assert record["reviewer_id"] == reviewer_id
        assert record["event_count"] == 1


def test_batch_compute_empty_reviewers() -> None:
    results = compute_epoch_reputation_batch([], [], epoch_id="epoch-7")
    assert results == {}


def test_non_outcome_events_ignored() -> None:
    events = [
        {"event_type": "pr_merged", "payload": {"reviewer_id": "alice", "epoch_id": "epoch-7"}},
        {"event_type": "constitution_evaluated", "payload": {}},
        _outcome_event("alice", "epoch-7"),
    ]
    result = compute_reviewer_reputation("alice", events, epoch_id="epoch-7")
    assert result["event_count"] == 1
