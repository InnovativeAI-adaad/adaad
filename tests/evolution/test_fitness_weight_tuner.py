# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.fitness_weight_tuner import (
    FitnessWeightGovernanceError,
    apply_weight_update_with_governance,
    propose_weights_from_history,
)
from runtime.governance.foundation import canonical_json, sha256_prefixed_digest


def _replay_bundle() -> dict:
    return {
        "schema_version": "replay_attestation.v1",
        "epoch_id": "epoch-1",
        "baseline_digest": "sha256:" + ("1" * 64),
        "ledger_state_hash": "sha256:" + ("2" * 64),
        "mutation_graph_fingerprint": "sha256:" + ("3" * 64),
        "constitution_version": "1.0.0",
        "sandbox_policy_hash": "sha256:" + ("4" * 64),
        "checkpoint_chain": [],
        "checkpoint_chain_digest": "sha256:" + ("5" * 64),
        "replay_digest": "sha256:" + ("6" * 64),
        "canonical_digest": "sha256:" + ("7" * 64),
        "policy_hashes": {
            "promotion_policy_hash": "sha256:" + ("8" * 64),
            "entropy_policy_hash": "sha256:" + ("9" * 64),
            "sandbox_policy_hash": "sha256:" + ("a" * 64),
        },
        "fitness_weight_snapshot_hash": "sha256:" + ("b" * 64),
        "proof_digest": "sha256:" + ("c" * 64),
        "signature_bundle": {
            "key_id": "replay-proof-dev",
            "algorithm": "hmac-sha256",
            "signed_digest": "sha256:" + ("c" * 64),
            "signature": "sha256:" + ("d" * 64),
        },
        "signatures": [
            {
                "key_id": "replay-proof-dev",
                "algorithm": "hmac-sha256",
                "signed_digest": "sha256:" + ("c" * 64),
                "signature": "sha256:" + ("d" * 64),
            }
        ],
    }


def test_propose_weights_from_history_emits_signed_artifact() -> None:
    proposal = propose_weights_from_history(
        {
            "correctness_score": 0.3,
            "efficiency_score": 0.2,
            "policy_compliance_score": 0.2,
            "goal_alignment_score": 0.15,
            "simulated_market_score": 0.15,
        },
        [
            {
                "goal_score_delta": 0.4,
                "fitness_component_scores": {"correctness_score": 0.9, "efficiency_score": 0.2},
            }
        ],
        replay_proof_bundle=_replay_bundle(),
        proposal_id="proposal-1",
        signer_key_id="fitness-weight-dev",
    )

    assert proposal["schema_version"] == "fitness_weight_update_proposal.v1"
    assert proposal["signature"]["value"].startswith("sha256:")
    assert sum(proposal["payload"]["proposed_weights"].values()) == pytest.approx(1.0)


def test_apply_weight_update_requires_replay_proof_and_signature(monkeypatch) -> None:
    replay_bundle = _replay_bundle()
    proposal = propose_weights_from_history(
        {
            "correctness_score": 0.3,
            "efficiency_score": 0.2,
            "policy_compliance_score": 0.2,
            "goal_alignment_score": 0.15,
            "simulated_market_score": 0.15,
        },
        [],
        replay_proof_bundle=replay_bundle,
        proposal_id="proposal-2",
        signer_key_id="fitness-weight-dev",
    )

    monkeypatch.setattr("runtime.evolution.fitness_weight_tuner.verify_replay_proof_bundle", lambda _bundle: {"ok": True})
    updated = apply_weight_update_with_governance(
        proposal,
        replay_proof=replay_bundle,
        current_config={"version": 5, "weights": proposal["payload"]["proposed_weights"]},
    )

    assert updated["version"] == 6
    assert sum(updated["weights"].values()) == pytest.approx(1.0)

    tampered = {
        **proposal,
        "payload": {
            **proposal["payload"],
            "replay_proof_digest": sha256_prefixed_digest(canonical_json({"tampered": True})),
        },
    }
    monkeypatch.setattr("runtime.evolution.fitness_weight_tuner.cryovant.verify_hmac_digest_signature", lambda **_kwargs: True)
    with pytest.raises(FitnessWeightGovernanceError, match="replay_proof_digest_mismatch"):
        apply_weight_update_with_governance(
            tampered,
            replay_proof=replay_bundle,
            current_config={"version": 5, "weights": proposal["payload"]["proposed_weights"]},
        )
