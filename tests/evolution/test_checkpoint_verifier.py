# SPDX-License-Identifier: Apache-2.0

import pytest

from runtime.evolution.checkpoint_registry import CheckpointRegistry
from runtime.evolution.checkpoint_verifier import CheckpointVerificationError, CheckpointVerifier
from runtime.evolution.lineage_v2 import LineageLedgerV2


def _seed_epoch(ledger: LineageLedgerV2, epoch_id: str) -> None:
    ledger.append_event("MutationBundleEvent", {"epoch_id": epoch_id, "epoch_digest": "sha256:abc"})
    ledger.append_event("PromotionEvent", {"epoch_id": epoch_id, "payload": {"entropy_declared_bits": 2}})


def test_verify_all_checkpoints_passes_for_valid_checkpoint_chain(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    epoch_id = "epoch-1"
    _seed_epoch(ledger, epoch_id)
    registry = CheckpointRegistry(ledger)
    registry.create_checkpoint(epoch_id)
    registry.create_checkpoint(epoch_id)

    result = CheckpointVerifier.verify_all_checkpoints(ledger.ledger_path)

    assert result["verified"] is True
    assert result["epoch_count"] == 1
    assert result["checkpoint_count"] == 2


def test_verify_all_checkpoints_raises_on_prev_missing(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    epoch_id = "epoch-prev"
    _seed_epoch(ledger, epoch_id)
    registry = CheckpointRegistry(ledger)
    registry.create_checkpoint(epoch_id)

    ledger.append_event(
        "EpochCheckpointEvent",
        {
            "epoch_id": epoch_id,
            "checkpoint_id": "chk_bad_prev",
            "checkpoint_hash": "sha256:" + ("1" * 64),
            "prev_checkpoint_hash": "sha256:" + ("f" * 64),
            "epoch_digest": "sha256:abc",
            "baseline_digest": "sha256:abc",
            "mutation_count": 1,
            "promotion_event_count": 1,
            "scoring_event_count": 0,
            "entropy_policy_hash": "sha256:" + ("0" * 64),
            "promotion_policy_hash": "sha256:" + ("0" * 64),
            "evidence_hash": "sha256:" + ("0" * 64),
            "sandbox_policy_hash": "sha256:" + ("0" * 64),
        },
    )

    with pytest.raises(CheckpointVerificationError, match=r"^checkpoint_prev_missing:epoch=epoch-prev;index=1$"):
        CheckpointVerifier.verify_all_checkpoints(ledger.ledger_path)


def test_verify_all_checkpoints_raises_on_hash_mismatch(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    epoch_id = "epoch-hash"
    _seed_epoch(ledger, epoch_id)
    registry = CheckpointRegistry(ledger)
    registry.create_checkpoint(epoch_id)
    prev = registry.create_checkpoint(epoch_id)["checkpoint_hash"]

    ledger.append_event(
        "EpochCheckpointEvent",
        {
            "epoch_id": epoch_id,
            "checkpoint_id": "chk_bad_hash",
            "checkpoint_hash": "sha256:" + ("0" * 64),
            "prev_checkpoint_hash": prev,
            "epoch_digest": "sha256:abc",
            "baseline_digest": "sha256:abc",
            "mutation_count": 1,
            "promotion_event_count": 1,
            "scoring_event_count": 0,
            "entropy_policy_hash": "sha256:" + ("0" * 64),
            "promotion_policy_hash": "sha256:" + ("0" * 64),
            "evidence_hash": "sha256:" + ("0" * 64),
            "sandbox_policy_hash": "sha256:" + ("0" * 64),
        },
    )

    with pytest.raises(CheckpointVerificationError, match=r"^checkpoint_hash_mismatch:epoch=epoch-hash;index=2$"):
        CheckpointVerifier.verify_all_checkpoints(ledger.ledger_path)


def test_verify_checkpoint_chain_emits_verified_governance_event(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    epoch_id = "epoch-chain-ok"
    _seed_epoch(ledger, epoch_id)
    registry = CheckpointRegistry(ledger)
    registry.create_checkpoint(epoch_id)

    result = CheckpointVerifier.verify_checkpoint_chain_with_event(ledger, epoch_id)

    assert result["passed"] is True
    assert result["event_type"] == "checkpoint_chain_verified"
    events = [
        entry for entry in ledger.read_epoch(epoch_id) if entry.get("type") == "CheckpointChainGovernanceEvent"
    ]
    assert len(events) == 1
    assert events[0]["payload"]["event_type"] == "checkpoint_chain_verified"


def test_verify_checkpoint_chain_emits_violation_with_halt_reason(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    epoch_id = "epoch-chain-bad"
    _seed_epoch(ledger, epoch_id)
    registry = CheckpointRegistry(ledger)
    registry.create_checkpoint(epoch_id)

    ledger.append_event(
        "EpochCheckpointEvent",
        {
            "epoch_id": epoch_id,
            "checkpoint_id": "chk_bad_prev",
            "checkpoint_hash": "sha256:" + ("1" * 64),
            "prev_checkpoint_hash": "sha256:" + ("f" * 64),
            "epoch_digest": "sha256:abc",
            "baseline_digest": "sha256:abc",
            "mutation_count": 1,
            "promotion_event_count": 1,
            "scoring_event_count": 0,
            "entropy_policy_hash": "sha256:" + ("0" * 64),
            "promotion_policy_hash": "sha256:" + ("0" * 64),
            "evidence_hash": "sha256:" + ("0" * 64),
            "sandbox_policy_hash": "sha256:" + ("0" * 64),
        },
    )

    result = CheckpointVerifier.verify_checkpoint_chain_with_event(ledger, epoch_id)

    assert result["passed"] is False
    assert result["event_type"] == "checkpoint_chain_violated"
    assert result["halt_reason_code"] == "prev_checkpoint_mismatch"
    events = [
        entry for entry in ledger.read_epoch(epoch_id) if entry.get("type") == "CheckpointChainGovernanceEvent"
    ]
    assert events[-1]["payload"]["event_type"] == "checkpoint_chain_violated"
    assert events[-1]["payload"]["halt_reason_code"] == "prev_checkpoint_mismatch"
