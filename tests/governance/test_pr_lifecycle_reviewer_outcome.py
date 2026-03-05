# SPDX-License-Identifier: Apache-2.0
"""Tests for PR-7-01: reviewer_action_outcome ledger extension.

Verifies:
- reviewer_action_outcome is a recognised event type
- build_reviewer_action_outcome_payload enforces required fields and value constraints
- Payload round-trips through build_event_digest deterministically
- Invalid decision and out-of-range scores are rejected at construction
- REVIEWER_ACTION_OUTCOME_REQUIRED_FIELDS contract is complete
"""
from __future__ import annotations

import pytest

from runtime.governance.pr_lifecycle_event_contract import (
    REQUIRED_PR_LIFECYCLE_EVENT_TYPES,
    REVIEWER_ACTION_OUTCOME_REQUIRED_FIELDS,
    build_event_digest,
    build_reviewer_action_outcome_payload,
    derive_idempotency_key,
)


# ---------------------------------------------------------------------------
# Contract: event type registration
# ---------------------------------------------------------------------------


def test_reviewer_action_outcome_in_required_types() -> None:
    assert "reviewer_action_outcome" in REQUIRED_PR_LIFECYCLE_EVENT_TYPES


def test_reviewer_action_outcome_required_fields_complete() -> None:
    required = set(REVIEWER_ACTION_OUTCOME_REQUIRED_FIELDS)
    expected = {
        "reviewer_id",
        "review_id",
        "mutation_id",
        "decision",
        "latency_seconds",
        "epoch_id",
        "scoring_algorithm_version",
    }
    assert required == expected, f"Field contract mismatch: {required ^ expected}"


# ---------------------------------------------------------------------------
# Builder: happy-path construction
# ---------------------------------------------------------------------------


def _minimal_payload() -> dict:
    return dict(
        reviewer_id="alice",
        review_id="rv-001",
        mutation_id="mut-42",
        decision="approve",
        latency_seconds=3600.0,
        epoch_id="epoch-7",
        scoring_algorithm_version="1.0",
    )


def test_build_minimal_payload_succeeds() -> None:
    payload = build_reviewer_action_outcome_payload(**_minimal_payload())
    assert payload["reviewer_id"] == "alice"
    assert payload["decision"] == "approve"
    assert payload["latency_seconds"] == 3600.0
    assert payload["constitutional_floor_enforced"] is True
    assert payload["overridden_by_authority"] is False


def test_build_payload_with_all_optional_fields() -> None:
    payload = build_reviewer_action_outcome_payload(
        **_minimal_payload(),
        overridden_by_authority=True,
        override_authority_level="governance_lead",
        long_term_mutation_impact_score=0.85,
        governance_alignment_score=0.92,
        sla_seconds=43200,
        tier="standard",
        constitutional_floor_enforced=True,
    )
    assert payload["overridden_by_authority"] is True
    assert payload["override_authority_level"] == "governance_lead"
    assert payload["long_term_mutation_impact_score"] == 0.85
    assert payload["governance_alignment_score"] == 0.92
    assert payload["sla_seconds"] == 43200
    assert payload["tier"] == "standard"


# ---------------------------------------------------------------------------
# Builder: constraint enforcement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_decision", ["unknown", "APPROVE", "merged", "", "pass"])
def test_invalid_decision_raises(bad_decision: str) -> None:
    kwargs = {**_minimal_payload(), "decision": bad_decision}
    with pytest.raises(ValueError, match="invalid decision"):
        build_reviewer_action_outcome_payload(**kwargs)


@pytest.mark.parametrize("valid_decision", ["approve", "reject", "abstain", "escalate"])
def test_all_valid_decisions_accepted(valid_decision: str) -> None:
    payload = build_reviewer_action_outcome_payload(**{**_minimal_payload(), "decision": valid_decision})
    assert payload["decision"] == valid_decision


def test_negative_latency_raises() -> None:
    with pytest.raises(ValueError, match="latency_seconds"):
        build_reviewer_action_outcome_payload(**{**_minimal_payload(), "latency_seconds": -1.0})


@pytest.mark.parametrize("bad_score", [-0.01, 1.01, 2.0, -1.0])
def test_impact_score_out_of_range_raises(bad_score: float) -> None:
    with pytest.raises(ValueError, match="long_term_mutation_impact_score"):
        build_reviewer_action_outcome_payload(
            **_minimal_payload(), long_term_mutation_impact_score=bad_score
        )


@pytest.mark.parametrize("bad_score", [-0.01, 1.01])
def test_alignment_score_out_of_range_raises(bad_score: float) -> None:
    with pytest.raises(ValueError, match="governance_alignment_score"):
        build_reviewer_action_outcome_payload(
            **_minimal_payload(), governance_alignment_score=bad_score
        )


def test_boundary_scores_accepted() -> None:
    payload = build_reviewer_action_outcome_payload(
        **_minimal_payload(),
        long_term_mutation_impact_score=0.0,
        governance_alignment_score=1.0,
    )
    assert payload["long_term_mutation_impact_score"] == 0.0
    assert payload["governance_alignment_score"] == 1.0


def test_sla_seconds_floor() -> None:
    # sla_seconds=0 must be clamped to 1 (never zero)
    payload = build_reviewer_action_outcome_payload(**{**_minimal_payload(), "sla_seconds": 0})
    assert payload["sla_seconds"] >= 1


# ---------------------------------------------------------------------------
# Determinism: digest is stable across identical payloads
# ---------------------------------------------------------------------------


def _build_full_event(payload: dict) -> dict:
    from runtime.governance.foundation.hashing import ZERO_HASH

    event = {
        "schema_version": "1.0",
        "event_type": "reviewer_action_outcome",
        "pr_number": 99,
        "commit_sha": "c" * 40,
        "idempotency_key": derive_idempotency_key(
            pr_number=99, commit_sha="c" * 40, event_type="reviewer_action_outcome"
        ),
        "attempt": 1,
        "sequence": 1,
        "previous_event_digest": ZERO_HASH,
        "payload": payload,
    }
    event["event_digest"] = build_event_digest(event)
    return event


def test_digest_is_deterministic_for_identical_payloads() -> None:
    payload = build_reviewer_action_outcome_payload(**_minimal_payload())
    ev1 = _build_full_event(dict(payload))
    ev2 = _build_full_event(dict(payload))
    assert ev1["event_digest"] == ev2["event_digest"]


def test_digest_differs_for_different_reviewer() -> None:
    p1 = build_reviewer_action_outcome_payload(**_minimal_payload())
    p2 = build_reviewer_action_outcome_payload(**{**_minimal_payload(), "reviewer_id": "bob"})
    ev1 = _build_full_event(dict(p1))
    ev2 = _build_full_event(dict(p2))
    assert ev1["event_digest"] != ev2["event_digest"]


def test_epoch_id_is_replay_scoped() -> None:
    """Epoch ID must be present and non-empty to guarantee replay scope."""
    payload = build_reviewer_action_outcome_payload(**_minimal_payload())
    assert payload["epoch_id"] == "epoch-7"
    assert payload["scoring_algorithm_version"] == "1.0"
