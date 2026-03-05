# SPDX-License-Identifier: Apache-2.0
"""Contract helpers for PR lifecycle governance events."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from runtime.governance.foundation.canonical import canonical_json_bytes
from runtime.governance.foundation.hashing import ZERO_HASH, sha256_prefixed_digest
from runtime.governance_surface import strip_version_comparison_ephemerals

REQUIRED_PR_LIFECYCLE_EVENT_TYPES: tuple[str, ...] = (
    "pr_merged",
    "constitution_evaluated",
    "replay_verified",
    "promotion_policy_evaluated",
    "sandbox_preflight_passed",
    "forensic_bundle_exported",
    "reviewer_action_outcome",
)

# Fields required in reviewer_action_outcome payload for reputation calibration input.
REVIEWER_ACTION_OUTCOME_REQUIRED_FIELDS: tuple[str, ...] = (
    "reviewer_id",
    "review_id",
    "mutation_id",
    "decision",
    "latency_seconds",
    "epoch_id",
    "scoring_algorithm_version",
)

CURRENT_PR_LIFECYCLE_SCHEMA_VERSION = "1.0"


def is_schema_version_compatible(schema_version: str) -> bool:
    """Return True when ``schema_version`` is backward compatible with current readers.

    Policy: major version changes are breaking; minor/patch changes are additive.
    """

    try:
        major, *_ = schema_version.split(".")
        current_major, *_ = CURRENT_PR_LIFECYCLE_SCHEMA_VERSION.split(".")
    except ValueError:
        return False
    return major == current_major


def derive_idempotency_key(*, pr_number: int, commit_sha: str, event_type: str) -> str:
    """Derive deterministic idempotency key for a PR lifecycle event."""

    normalized_event_type = event_type.strip().lower()
    normalized_commit_sha = commit_sha.strip().lower()
    material = {
        "event_type": normalized_event_type,
        "pr_number": int(pr_number),
        "commit_sha": normalized_commit_sha,
    }
    return sha256_prefixed_digest(canonical_json_bytes(material))


def build_event_digest(event: Mapping[str, Any]) -> str:
    """Compute deterministic digest for append-only event entries."""

    canonical_event = {
        "schema_version": event["schema_version"],
        "event_type": event["event_type"],
        "pr_number": event["pr_number"],
        "commit_sha": event["commit_sha"],
        "idempotency_key": event["idempotency_key"],
        "attempt": event["attempt"],
        "sequence": event["sequence"],
        "previous_event_digest": event["previous_event_digest"],
        "payload": event["payload"],
    }
    return sha256_prefixed_digest(canonical_json_bytes(canonical_event))


def classify_retry(existing_event: Mapping[str, Any], incoming_event: Mapping[str, Any]) -> str:
    """Classify duplicate handling for retries.

    Returns one of:
    - ``distinct``: idempotency keys differ.
    - ``duplicate_ack``: same key and semantically identical event.
    - ``duplicate_conflict``: same key but conflicting payload.
    """

    if existing_event["idempotency_key"] != incoming_event["idempotency_key"]:
        return "distinct"

    existing_material = {
        "event_type": existing_event["event_type"],
        "pr_number": existing_event["pr_number"],
        "commit_sha": existing_event["commit_sha"],
        "payload": strip_version_comparison_ephemerals(existing_event["payload"]),
    }
    incoming_material = {
        "event_type": incoming_event["event_type"],
        "pr_number": incoming_event["pr_number"],
        "commit_sha": incoming_event["commit_sha"],
        "payload": strip_version_comparison_ephemerals(incoming_event["payload"]),
    }
    return "duplicate_ack" if existing_material == incoming_material else "duplicate_conflict"


def validate_append_only_invariants(events: Sequence[Mapping[str, Any]]) -> list[str]:
    """Validate append-only ordering and hash-link invariants."""

    errors: list[str] = []
    previous_digest = ZERO_HASH
    previous_sequence = 0

    for idx, event in enumerate(events):
        sequence = int(event["sequence"])
        if sequence != previous_sequence + 1:
            errors.append(f"event[{idx}]:non_contiguous_sequence")
        if event["previous_event_digest"] != previous_digest:
            errors.append(f"event[{idx}]:previous_event_digest_mismatch")
        expected_digest = build_event_digest(event)
        if event["event_digest"] != expected_digest:
            errors.append(f"event[{idx}]:event_digest_mismatch")

        previous_sequence = sequence
        previous_digest = event["event_digest"]

    return errors



def build_reviewer_action_outcome_payload(
    *,
    reviewer_id: str,
    review_id: str,
    mutation_id: str,
    decision: str,
    latency_seconds: float,
    epoch_id: str,
    scoring_algorithm_version: str,
    overridden_by_authority: bool = False,
    override_authority_level: str = "",
    long_term_mutation_impact_score: float | None = None,
    governance_alignment_score: float | None = None,
    sla_seconds: int = 86400,
    tier: str = "",
    constitutional_floor_enforced: bool = True,
) -> Mapping[str, Any]:
    """Build a validated reviewer_action_outcome payload.

    All reputation calibration inputs route through this builder to enforce
    schema invariants at the point of construction. Callers must not bypass
    this function to write raw payloads; the schema contract is the single
    source of truth.
    """
    valid_decisions = {"approve", "reject", "abstain", "escalate"}
    if decision not in valid_decisions:
        raise ValueError(f"reviewer_action_outcome: invalid decision {decision!r}; must be one of {valid_decisions}")
    if latency_seconds < 0:
        raise ValueError("reviewer_action_outcome: latency_seconds must be >= 0")
    payload: dict[str, Any] = {
        "reviewer_id": str(reviewer_id).strip(),
        "review_id": str(review_id).strip(),
        "mutation_id": str(mutation_id).strip(),
        "decision": decision,
        "latency_seconds": float(latency_seconds),
        "epoch_id": str(epoch_id).strip(),
        "scoring_algorithm_version": str(scoring_algorithm_version).strip(),
        "overridden_by_authority": bool(overridden_by_authority),
        "sla_seconds": int(max(1, sla_seconds)),
        "constitutional_floor_enforced": bool(constitutional_floor_enforced),
    }
    if override_authority_level:
        payload["override_authority_level"] = str(override_authority_level).strip()
    if long_term_mutation_impact_score is not None:
        score = float(long_term_mutation_impact_score)
        if not (0.0 <= score <= 1.0):
            raise ValueError("long_term_mutation_impact_score must be in [0.0, 1.0]")
        payload["long_term_mutation_impact_score"] = score
    if governance_alignment_score is not None:
        score = float(governance_alignment_score)
        if not (0.0 <= score <= 1.0):
            raise ValueError("governance_alignment_score must be in [0.0, 1.0]")
        payload["governance_alignment_score"] = score
    if tier:
        payload["tier"] = str(tier).strip()
    return payload

__all__ = [
    "CURRENT_PR_LIFECYCLE_SCHEMA_VERSION",
    "REQUIRED_PR_LIFECYCLE_EVENT_TYPES",
    "build_event_digest",
    "classify_retry",
    "derive_idempotency_key",
    "is_schema_version_compatible",
    "validate_append_only_invariants",
    "build_reviewer_action_outcome_payload",
    "REVIEWER_ACTION_OUTCOME_REQUIRED_FIELDS",
]