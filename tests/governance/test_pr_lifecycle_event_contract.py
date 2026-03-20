# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.pr_lifecycle_event_contract import (
    CURRENT_PR_LIFECYCLE_SCHEMA_VERSION,
    attach_replay_bundle_metadata,
    build_event_digest,
    build_merge_attestation_event,
    build_merge_attestation_payload,
    classify_retry,
    derive_idempotency_key,
    is_schema_version_compatible,
    validate_append_only_invariants,
    validate_merge_attestation_payload,
)


def _base_event(*, sequence: int, previous_event_digest: str, payload: dict) -> dict:
    event = {
        "schema_version": CURRENT_PR_LIFECYCLE_SCHEMA_VERSION,
        "event_type": "replay_verified",
        "pr_number": 42,
        "commit_sha": "a" * 40,
        "idempotency_key": derive_idempotency_key(pr_number=42, commit_sha="a" * 40, event_type="replay_verified"),
        "attempt": 1,
        "sequence": sequence,
        "previous_event_digest": previous_event_digest,
        "payload": payload,
    }
    event["event_digest"] = build_event_digest(event)
    return event


def test_duplicate_emission_semantics() -> None:
    first = {
        "event_type": "replay_verified",
        "pr_number": 17,
        "commit_sha": "b" * 40,
        "idempotency_key": derive_idempotency_key(pr_number=17, commit_sha="b" * 40, event_type="replay_verified"),
        "payload": {"replay_run_id": "r1", "verification_result": "pass"},
    }
    duplicate_same = dict(first)
    duplicate_conflict = {**first, "payload": {"replay_run_id": "r1", "verification_result": "fail"}}
    distinct = {
        **first,
        "event_type": "promotion_policy_evaluated",
        "idempotency_key": derive_idempotency_key(
            pr_number=17,
            commit_sha="b" * 40,
            event_type="promotion_policy_evaluated",
        ),
    }

    assert classify_retry(first, duplicate_same) == "duplicate_ack"
    assert classify_retry(first, duplicate_conflict) == "duplicate_conflict"
    assert classify_retry(first, distinct) == "distinct"


def test_duplicate_emission_ignores_ephemeral_payload_fields() -> None:
    first = {
        "event_type": "replay_verified",
        "pr_number": 17,
        "commit_sha": "b" * 40,
        "idempotency_key": derive_idempotency_key(pr_number=17, commit_sha="b" * 40, event_type="replay_verified"),
        "payload": {
            "replay_digest": "sha256:" + ("c" * 64),
            "verification_result": "pass",
            "nonce": "nonce-1",
            "generated_at": "2026-02-01T00:00:01Z",
            "run_id": "run-a",
        },
    }
    retried = {
        **first,
        "payload": {
            "replay_digest": "sha256:" + ("c" * 64),
            "verification_result": "pass",
            "nonce": "nonce-2",
            "generated_at": "2026-02-01T00:00:02Z",
            "run_id": "run-b",
        },
    }

    assert classify_retry(first, retried) == "duplicate_ack"


def test_schema_version_compatibility_policy() -> None:
    assert is_schema_version_compatible("1.0")
    assert is_schema_version_compatible("1.7")
    assert not is_schema_version_compatible("2.0")


def test_append_only_invariants_detect_tampering() -> None:
    valid = [
        _base_event(
            sequence=1,
            previous_event_digest="sha256:" + ("0" * 64),
            payload={"replay_run_id": "run-1", "replay_digest": "sha256:" + ("1" * 64), "verification_result": "pass"},
        ),
        _base_event(
            sequence=2,
            previous_event_digest="",
            payload={"replay_run_id": "run-2", "replay_digest": "sha256:" + ("2" * 64), "verification_result": "pass"},
        ),
    ]

    valid[1]["previous_event_digest"] = valid[0]["event_digest"]
    valid[1]["event_digest"] = build_event_digest(valid[1])

    assert validate_append_only_invariants(valid) == []

    tampered = [dict(valid[0]), dict(valid[1])]
    tampered[1]["previous_event_digest"] = "sha256:" + ("f" * 64)

    errors = validate_append_only_invariants(tampered)
    assert "event[1]:previous_event_digest_mismatch" in errors


def test_attach_replay_bundle_metadata_preserves_payload_and_adds_normalized_metadata() -> None:
    payload = {"trigger": "DEVADAAD", "scenario": "merge_ready"}

    attached = attach_replay_bundle_metadata(
        payload,
        manifest_path=" security/replay_manifests/manifest.json ",
        bundle_digest=" sha256:" + ("a" * 64) + " ",
        verification_result="pass",
        verified_sha="ABCDEF1234",
        schema_valid=True,
        signature_valid=True,
        divergence=False,
    )

    assert attached["trigger"] == "DEVADAAD"
    assert attached["replay_bundle_metadata"] == {
        "manifest_path": "security/replay_manifests/manifest.json",
        "bundle_digest": "sha256:" + ("a" * 64),
        "verification_result": "pass",
        "verified_sha": "abcdef1234",
        "schema_valid": True,
        "signature_valid": True,
        "divergence": False,
    }


def test_build_merge_attestation_payload_normalizes_required_fields() -> None:
    payload = build_merge_attestation_payload(
        pr_id=" PR-PHASE65-01 ",
        merge_sha="A" * 40,
        tier_0_digest="SHA256:" + ("b" * 64),
        tier_1_tests_passed=12,
        tier_1_tests_failed=0,
        tier_2_replay_digest=" replay-digest-v1 ",
        tier_3_evidence_complete=True,
        tier_m_working_code=True,
        triggered_by="DEVADAAD",
        operator_session=" session-01 ",
        timestamp_utc="2026-03-20T00:00:00+00:00",
        human_signoff_token=" signoff-1 ",
    )

    assert payload == {
        "pr_id": "PR-PHASE65-01",
        "merge_sha": "a" * 40,
        "tier_0_digest": "sha256:" + ("b" * 64),
        "tier_1_tests_passed": 12,
        "tier_1_tests_failed": 0,
        "tier_2_replay_digest": "replay-digest-v1",
        "tier_3_evidence_complete": True,
        "tier_m_working_code": True,
        "triggered_by": "DEVADAAD",
        "operator_session": "session-01",
        "timestamp_utc": "2026-03-20T00:00:00+00:00",
        "human_signoff_token": "signoff-1",
    }


def test_build_merge_attestation_event_uses_deterministic_idempotency() -> None:
    payload = build_merge_attestation_payload(
        pr_id="PR-PHASE65-01",
        merge_sha="c" * 40,
        tier_0_digest="sha256:" + ("d" * 64),
        tier_1_tests_passed=120,
        tier_1_tests_failed=0,
        tier_2_replay_digest="sha256:" + ("e" * 64),
        tier_3_evidence_complete=True,
        tier_m_working_code=True,
        triggered_by="DEVADAAD",
        operator_session="session-merge-01",
        timestamp_utc="2026-03-20T00:00:00+00:00",
        human_signoff_token=None,
    )

    event = build_merge_attestation_event(
        pr_number=65,
        merge_sha="c" * 40,
        payload=payload,
        sequence=1,
    )

    assert event["event_type"] == "merge_attestation.v1"
    assert event["idempotency_key"] == derive_idempotency_key(
        pr_number=65,
        commit_sha="c" * 40,
        event_type="merge_attestation.v1",
    )
    assert event["event_digest"] == build_event_digest(event)


def test_validate_merge_attestation_payload_fails_closed_when_required_field_missing() -> None:
    with pytest.raises(ValueError, match="missing required fields: merge_sha"):
        validate_merge_attestation_payload(
            {
                "pr_id": "PR-PHASE65-01",
                "tier_0_digest": "sha256:" + ("d" * 64),
                "tier_1_tests_passed": 1,
                "tier_1_tests_failed": 0,
                "tier_2_replay_digest": None,
                "tier_3_evidence_complete": True,
                "tier_m_working_code": True,
                "triggered_by": "DEVADAAD",
                "operator_session": "session-1",
                "timestamp_utc": "2026-03-20T00:00:00+00:00",
                "human_signoff_token": None,
            }
        )
