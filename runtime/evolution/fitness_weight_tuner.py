# SPDX-License-Identifier: Apache-2.0
"""Historical fitness-weight tuning and governance-gated update helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from runtime.evolution.economic_fitness import ALLOWED_WEIGHT_KEYS
from runtime.evolution.replay_attestation import load_replay_proof, verify_replay_proof_bundle
from runtime.governance.foundation import canonical_json, sha256_prefixed_digest
from security import cryovant


class FitnessWeightGovernanceError(ValueError):
    """Raised when a proposed fitness-weight update fails governance checks."""


def _clamp_weight(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _normalize_weights(raw: Mapping[str, Any]) -> Dict[str, float]:
    weights = {key: _clamp_weight(raw.get(key, 0.0)) for key in ALLOWED_WEIGHT_KEYS}
    total = sum(weights.values())
    if total <= 0.0:
        raise FitnessWeightGovernanceError("fitness_weight_total_must_be_positive")
    return {key: value / total for key, value in weights.items()}


def propose_weights_from_history(
    current_weights: Mapping[str, Any],
    historical_outcomes: Sequence[Mapping[str, Any]],
    *,
    replay_proof_bundle: Mapping[str, Any],
    proposal_id: str,
    signer_key_id: str,
) -> Dict[str, Any]:
    """Create deterministic proposal artifact from replayed historical outcomes."""

    base_weights = _normalize_weights(current_weights)
    adjustments = {key: 0.0 for key in ALLOWED_WEIGHT_KEYS}
    counts = {key: 0 for key in ALLOWED_WEIGHT_KEYS}

    for row in historical_outcomes:
        goal_delta = float(row.get("goal_score_delta", 0.0) or 0.0)
        component_scores = row.get("fitness_component_scores")
        if not isinstance(component_scores, Mapping):
            continue
        for key in ALLOWED_WEIGHT_KEYS:
            if key not in component_scores:
                continue
            adjustments[key] += goal_delta * _clamp_weight(component_scores.get(key))
            counts[key] += 1

    tuned = dict(base_weights)
    for key in ALLOWED_WEIGHT_KEYS:
        if counts[key] <= 0:
            continue
        avg_signal = adjustments[key] / float(counts[key])
        if avg_signal > 0:
            tuned[key] = tuned[key] * 1.05
        elif avg_signal < 0:
            tuned[key] = tuned[key] * 0.95

    proposed_weights = _normalize_weights(tuned)
    replay_digest = sha256_prefixed_digest(dict(replay_proof_bundle))
    proposal_payload = {
        "proposal_id": str(proposal_id),
        "base_weight_snapshot_hash": sha256_prefixed_digest({"weights": base_weights}),
        "proposed_weight_snapshot_hash": sha256_prefixed_digest({"weights": proposed_weights}),
        "replay_proof_digest": replay_digest,
        "proposed_weights": proposed_weights,
    }
    payload_bytes = canonical_json(proposal_payload).encode("utf-8")
    signature = cryovant.sign_hmac_digest(
        key_id=signer_key_id,
        signed_digest=sha256_prefixed_digest(payload_bytes),
        specific_env_prefix="ADAAD_FITNESS_WEIGHT_KEY_",
        generic_env_var="ADAAD_FITNESS_WEIGHT_SIGNING_KEY",
        fallback_namespace="adaad-fitness-weight-dev-secret",
    )
    return {
        "schema_version": "fitness_weight_update_proposal.v1",
        "payload": proposal_payload,
        "signature": {
            "key_id": signer_key_id,
            "algorithm": "hmac-sha256",
            "value": signature,
        },
    }


def apply_weight_update_with_governance(
    proposal_artifact: Mapping[str, Any],
    *,
    replay_proof: Mapping[str, Any],
    current_config: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate proposal + signature + replay proof before returning updated config payload."""

    if str(proposal_artifact.get("schema_version") or "") != "fitness_weight_update_proposal.v1":
        raise FitnessWeightGovernanceError("proposal_schema_version_invalid")

    payload = proposal_artifact.get("payload")
    signature = proposal_artifact.get("signature")
    if not isinstance(payload, Mapping) or not isinstance(signature, Mapping):
        raise FitnessWeightGovernanceError("proposal_missing_payload_or_signature")

    signer_key_id = str(signature.get("key_id") or "")
    signature_value = str(signature.get("value") or "")
    payload_bytes = canonical_json(dict(payload)).encode("utf-8")
    signed_digest = sha256_prefixed_digest(payload_bytes)

    signature_ok = cryovant.verify_hmac_digest_signature(
        key_id=signer_key_id,
        signed_digest=signed_digest,
        signature=signature_value,
        specific_env_prefix="ADAAD_FITNESS_WEIGHT_KEY_",
        generic_env_var="ADAAD_FITNESS_WEIGHT_SIGNING_KEY",
        fallback_namespace="adaad-fitness-weight-dev-secret",
    ) or cryovant.dev_signature_allowed(signature_value)
    if not signature_ok:
        raise FitnessWeightGovernanceError("proposal_signature_verification_failed")

    proof_verification = verify_replay_proof_bundle(dict(replay_proof))
    if not proof_verification.get("ok"):
        raise FitnessWeightGovernanceError("replay_proof_verification_failed")

    expected_replay_digest = sha256_prefixed_digest(dict(replay_proof))
    if str(payload.get("replay_proof_digest") or "") != expected_replay_digest:
        raise FitnessWeightGovernanceError("replay_proof_digest_mismatch")

    proposed_weights = payload.get("proposed_weights")
    if not isinstance(proposed_weights, Mapping):
        raise FitnessWeightGovernanceError("proposal_missing_proposed_weights")

    normalized = _normalize_weights(proposed_weights)
    next_version = max(1, int(current_config.get("version", 1) or 1)) + 1
    return {"version": next_version, "weights": normalized}


def propose_weights_job(
    *,
    history_path: Path,
    config_path: Path,
    replay_proof_path: Path,
    proposal_output_path: Path,
    signer_key_id: str,
    proposal_id: str,
) -> Path:
    """Optional historical tuner job that writes proposal artifact only."""

    history_payload = json.loads(history_path.read_text(encoding="utf-8"))
    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    replay_bundle = load_replay_proof(replay_proof_path)

    entries = history_payload.get("entries") if isinstance(history_payload, Mapping) else None
    historical_outcomes = [item for item in (entries or []) if isinstance(item, Mapping)]

    proposal = propose_weights_from_history(
        config_payload.get("weights") if isinstance(config_payload, Mapping) else {},
        historical_outcomes,
        replay_proof_bundle=replay_bundle,
        proposal_id=proposal_id,
        signer_key_id=signer_key_id,
    )
    proposal_output_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_output_path.write_text(canonical_json(proposal) + "\n", encoding="utf-8")
    return proposal_output_path


__all__ = [
    "FitnessWeightGovernanceError",
    "apply_weight_update_with_governance",
    "propose_weights_from_history",
    "propose_weights_job",
]
