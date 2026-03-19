# SPDX-License-Identifier: Apache-2.0
"""Deterministic replay divergence classification + signed manifest contract."""

from __future__ import annotations

from typing import Any, Mapping

from runtime.governance.foundation import canonical_json, sha256_prefixed_digest
from security import cryovant

REPLAY_DIVERGENCE_REASON_CODES: tuple[str, ...] = (
    "missing_evidence",
    "hash_mismatch",
    "signature_mismatch",
    "nondeterministic_field_detected",
    "lineage_discontinuity",
    "reconstructed_state_mismatch",
)
_MANIFEST_KEY_ID = "replay-divergence-manifest-v1"


def classify_replay_divergence(result: Mapping[str, Any]) -> dict[str, Any]:
    """Map replay result diagnostics to one deterministic reason code."""

    expected_digest = str(result.get("expected_digest") or result.get("expected") or "")
    actual_digest = str(result.get("actual_digest") or result.get("digest") or "")
    cause_buckets = dict(result.get("cause_buckets") or {})
    integrity_error = str(result.get("integrity_error") or "")
    checkpoint_reason = str((result.get("checkpoint_verification") or {}).get("reason") or "")
    evidence_missing = bool(result.get("missing_evidence")) or bool(result.get("evidence_missing"))
    signature_mismatch = bool(result.get("signature_mismatch")) or (result.get("signature_valid") is False)
    reconstructed_state_match = bool(result.get("reconstructed_state_match", True))
    nondeterministic_fields = tuple(sorted(str(item) for item in (result.get("nondeterministic_fields") or [])))
    lineage_discontinuity = bool(result.get("lineage_discontinuity")) or "lineage" in integrity_error or "lineage" in checkpoint_reason
    hash_mismatch = bool(cause_buckets.get("digest_mismatch")) or (expected_digest and actual_digest and expected_digest != actual_digest)

    if evidence_missing:
        reason_code = "missing_evidence"
    elif hash_mismatch:
        reason_code = "hash_mismatch"
    elif signature_mismatch:
        reason_code = "signature_mismatch"
    elif nondeterministic_fields or bool(cause_buckets.get("time_input_variance")) or bool(cause_buckets.get("external_dependency_variance")):
        reason_code = "nondeterministic_field_detected"
    elif lineage_discontinuity:
        reason_code = "lineage_discontinuity"
    elif not reconstructed_state_match:
        reason_code = "reconstructed_state_mismatch"
    else:
        reason_code = "hash_mismatch"

    diagnostics = {
        "epoch_id": str(result.get("epoch_id") or result.get("baseline_epoch") or "unknown"),
        "expected_digest": expected_digest,
        "actual_digest": actual_digest,
        "cause_buckets": cause_buckets,
        "integrity_error": integrity_error,
        "checkpoint_reason": checkpoint_reason,
        "nondeterministic_fields": list(nondeterministic_fields),
    }
    return {"ok": False, "reason_code": reason_code, "diagnostics": diagnostics}


def build_signed_replay_manifest(outcome: Mapping[str, Any]) -> dict[str, Any]:
    """Attach canonical digest/signature contract for replay manifests."""

    manifest = dict(outcome)
    canonical_payload = canonical_json(manifest)
    manifest_digest = sha256_prefixed_digest(canonical_payload)
    signature_value = cryovant.sign_artifact_hmac_digest(
        artifact_type="replay_proof",
        key_id=_MANIFEST_KEY_ID,
        signed_digest=manifest_digest,
    )
    manifest["manifest_digest"] = manifest_digest
    manifest["signature"] = {
        "algorithm": "hmac-sha256",
        "key_id": _MANIFEST_KEY_ID,
        "signed_digest": manifest_digest,
        "value": signature_value,
    }
    return manifest


__all__ = [
    "REPLAY_DIVERGENCE_REASON_CODES",
    "build_signed_replay_manifest",
    "classify_replay_divergence",
]
