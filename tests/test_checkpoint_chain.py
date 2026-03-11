# SPDX-License-Identifier: Apache-2.0

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.checkpoint_registry import CheckpointRegistry
from runtime.evolution.checkpoint_verifier import (
    CheckpointVerificationError,
    CheckpointVerifier,
    verify_epoch_checkpoint_continuity,
)
from runtime.evolution.lineage_v2 import LineageLedgerV2


def _seed_epoch(ledger: LineageLedgerV2, epoch_id: str) -> None:
    ledger.append_event("MutationBundleEvent", {"epoch_id": epoch_id, "epoch_digest": "sha256:abc"})


def test_checkpoint_chain_verified_event_emitted(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    registry = CheckpointRegistry(ledger)
    _seed_epoch(ledger, "epoch-1")
    registry.create_checkpoint("epoch-1")

    result = CheckpointVerifier.verify_chain(ledger)

    assert result["verified"] is True
    events = [entry for entry in ledger.read_all() if entry.get("type") == "checkpoint_chain_verified"]
    assert events
    assert events[-1]["payload"]["chain_depth"] >= 1


def test_checkpoint_chain_violated_on_bad_previous_hash(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    registry = CheckpointRegistry(ledger)
    _seed_epoch(ledger, "epoch-1")
    registry.create_checkpoint("epoch-1")
    ledger.append_event(
        "checkpoint_created",
        {
            "checkpoint_id": "chk_bad",
            "epoch_id": "epoch-1",
            "manifest_hash": "sha256:" + "1" * 64,
            "previous_checkpoint_hash": "sha256:" + "f" * 64,
            "snapshot_path": "checkpoints/chk_bad",
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
    )

    with pytest.raises(CheckpointVerificationError, match="checkpoint_chain_violated"):
        CheckpointVerifier.verify_chain(ledger)

    violations = [entry for entry in ledger.read_all() if entry.get("type") == "checkpoint_chain_violated"]
    assert violations


def test_epoch_checkpoint_continuity_verified(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    registry = CheckpointRegistry(ledger)
    _seed_epoch(ledger, "epoch-1")
    registry.create_checkpoint("epoch-1")
    _seed_epoch(ledger, "epoch-2")

    result = verify_epoch_checkpoint_continuity(ledger, current_epoch_id="epoch-2")

    assert result["verified"] is True
    continuity_events = [entry for entry in ledger.read_all() if entry.get("type") == "epoch_checkpoint_continuity_verified"]
    assert continuity_events
