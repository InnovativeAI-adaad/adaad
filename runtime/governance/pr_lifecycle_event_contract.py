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
    "merge_attestation.v1",
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

MERGE_ATTESTATION_REQUIRED_FIELDS: tuple[str, ...] = (
    "pr_id",
    "merge_sha",
    "tier_0_digest",
    "tier_1_tests_passed",
    "tier_1_tests_failed",
    "tier_2_replay_digest",
    "tier_3_evidence_complete",
    "tier_m_working_code",
    "triggered_by",
    "operator_session",
    "timestamp_utc",
    "human_signoff_token",
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


def attach_replay_bundle_metadata(
    payload: Mapping[str, Any],
    *,
    manifest_path: str,
    bundle_digest: str,
    verification_result: str,
    verified_sha: str,
    schema_valid: bool,
    signature_valid: bool,
    divergence: bool,
) -> dict[str, Any]:
    """Attach replay bundle metadata to a PR governance artifact payload.

    Rationale: keep merge-tier replay evidence binding explicit and deterministic
    for downstream governance gate evaluation.
    Invariants: function is pure (no side effects), preserves existing payload
    keys, and always emits normalized replay metadata fields.
    """
    attached = dict(payload)
    replay_metadata = {
        "manifest_path": str(manifest_path).strip(),
        "bundle_digest": str(bundle_digest).strip(),
        "verification_result": str(verification_result).strip(),
        "verified_sha": str(verified_sha).strip().lower(),
        "schema_valid": bool(schema_valid),
        "signature_valid": bool(signature_valid),
        "divergence": bool(divergence),
    }
    attached["replay_bundle_metadata"] = replay_metadata
    return attached


def _normalize_non_empty_string(value: object, *, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"merge_attestation.v1: {field_name} must be a non-empty string")
    return normalized


def _normalize_sha256_digest(value: object, *, field_name: str) -> str:
    normalized = _normalize_non_empty_string(value, field_name=field_name).lower()
    prefix, _, digest = normalized.partition(":")
    if prefix != "sha256" or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"merge_attestation.v1: {field_name} must be a sha256-prefixed digest")
    return normalized


def _normalize_git_sha(value: object, *, field_name: str) -> str:
    normalized = _normalize_non_empty_string(value, field_name=field_name).lower()
    if len(normalized) != 40 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError(f"merge_attestation.v1: {field_name} must be a 40-character lowercase git sha")
    return normalized


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def validate_merge_attestation_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a merge_attestation.v1 payload."""

    missing = [field for field in MERGE_ATTESTATION_REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"merge_attestation.v1: missing required fields: {', '.join(missing)}")

    triggered_by = _normalize_non_empty_string(payload["triggered_by"], field_name="triggered_by")
    if triggered_by != "DEVADAAD":
        raise ValueError("merge_attestation.v1: triggered_by must be DEVADAAD")

    tier_1_tests_passed = int(payload["tier_1_tests_passed"])
    tier_1_tests_failed = int(payload["tier_1_tests_failed"])
    if tier_1_tests_passed < 0:
        raise ValueError("merge_attestation.v1: tier_1_tests_passed must be >= 0")
    if tier_1_tests_failed < 0:
        raise ValueError("merge_attestation.v1: tier_1_tests_failed must be >= 0")

    return {
        "pr_id": _normalize_non_empty_string(payload["pr_id"], field_name="pr_id"),
        "merge_sha": _normalize_git_sha(payload["merge_sha"], field_name="merge_sha"),
        "tier_0_digest": _normalize_sha256_digest(payload["tier_0_digest"], field_name="tier_0_digest"),
        "tier_1_tests_passed": tier_1_tests_passed,
        "tier_1_tests_failed": tier_1_tests_failed,
        "tier_2_replay_digest": _normalize_optional_string(payload["tier_2_replay_digest"]),
        "tier_3_evidence_complete": bool(payload["tier_3_evidence_complete"]),
        "tier_m_working_code": bool(payload["tier_m_working_code"]),
        "triggered_by": triggered_by,
        "operator_session": _normalize_non_empty_string(payload["operator_session"], field_name="operator_session"),
        "timestamp_utc": _normalize_non_empty_string(payload["timestamp_utc"], field_name="timestamp_utc"),
        "human_signoff_token": _normalize_optional_string(payload["human_signoff_token"]),
    }


def build_merge_attestation_payload(
    *,
    pr_id: str,
    merge_sha: str,
    tier_0_digest: str,
    tier_1_tests_passed: int,
    tier_1_tests_failed: int,
    tier_2_replay_digest: str | None,
    tier_3_evidence_complete: bool,
    tier_m_working_code: bool,
    triggered_by: str,
    operator_session: str,
    timestamp_utc: str,
    human_signoff_token: str | None,
) -> dict[str, Any]:
    """Build a validated merge_attestation.v1 payload."""

    return validate_merge_attestation_payload(
        {
            "pr_id": pr_id,
            "merge_sha": merge_sha,
            "tier_0_digest": tier_0_digest,
            "tier_1_tests_passed": tier_1_tests_passed,
            "tier_1_tests_failed": tier_1_tests_failed,
            "tier_2_replay_digest": tier_2_replay_digest,
            "tier_3_evidence_complete": tier_3_evidence_complete,
            "tier_m_working_code": tier_m_working_code,
            "triggered_by": triggered_by,
            "operator_session": operator_session,
            "timestamp_utc": timestamp_utc,
            "human_signoff_token": human_signoff_token,
        }
    )


def build_merge_attestation_event(
    *,
    pr_number: int,
    merge_sha: str,
    payload: Mapping[str, Any],
    sequence: int,
    previous_event_digest: str = ZERO_HASH,
    attempt: int = 1,
    correlation_id: str | None = None,
    causation_event_id: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic PR lifecycle merge attestation event envelope."""

    normalized_payload = validate_merge_attestation_payload(payload)
    normalized_merge_sha = _normalize_git_sha(merge_sha, field_name="merge_sha")
    if normalized_payload["merge_sha"] != normalized_merge_sha:
        raise ValueError("merge_attestation.v1: payload merge_sha must match envelope merge_sha")

    idempotency_key = derive_idempotency_key(
        pr_number=pr_number,
        commit_sha=normalized_merge_sha,
        event_type="merge_attestation.v1",
    )
    event_id_material = {
        "event_type": "merge_attestation.v1",
        "pr_number": int(pr_number),
        "merge_sha": normalized_merge_sha,
        "sequence": int(sequence),
        "attempt": int(attempt),
    }
    event_id = "prl_" + sha256_prefixed_digest(canonical_json_bytes(event_id_material)).split(":", 1)[1][:16]
    event = {
        "schema_version": CURRENT_PR_LIFECYCLE_SCHEMA_VERSION,
        "event_id": event_id,
        "event_type": "merge_attestation.v1",
        "pr_number": int(pr_number),
        "commit_sha": normalized_merge_sha,
        "idempotency_key": idempotency_key,
        "attempt": int(attempt),
        "sequence": int(sequence),
        "emitted_at": normalized_payload["timestamp_utc"],
        "correlation_id": correlation_id or f"merge-attestation:{normalized_payload['pr_id']}",
        "previous_event_digest": previous_event_digest,
        "event_digest": "",
        "payload": normalized_payload,
    }
    normalized_causation_event_id = _normalize_optional_string(causation_event_id)
    if normalized_causation_event_id is not None:
        event["causation_event_id"] = normalized_causation_event_id
    event["event_digest"] = build_event_digest(event)
    return event

__all__ = [
    "CURRENT_PR_LIFECYCLE_SCHEMA_VERSION",
    "MERGE_ATTESTATION_REQUIRED_FIELDS",
    "REQUIRED_PR_LIFECYCLE_EVENT_TYPES",
    "build_merge_attestation_event",
    "build_merge_attestation_payload",
    "build_event_digest",
    "classify_retry",
    "derive_idempotency_key",
    "is_schema_version_compatible",
    "validate_append_only_invariants",
    "validate_merge_attestation_payload",
    "build_reviewer_action_outcome_payload",
    "REVIEWER_ACTION_OUTCOME_REQUIRED_FIELDS",
    "attach_replay_bundle_metadata",
]
