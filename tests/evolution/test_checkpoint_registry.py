# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.checkpoint_registry import CheckpointRegistry
from runtime.evolution.checkpoint_verifier import verify_checkpoint_chain
from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.governance.foundation.determinism import SeededDeterminismProvider


def test_checkpoint_registry_emits_chain(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage.jsonl")
    epoch_id = "epoch-1"
    ledger.append_event("EpochStartEvent", {"epoch_id": epoch_id, "ts": "2026-01-01T00:00:00Z"})
    ledger.append_bundle_with_digest(epoch_id, {"epoch_id": epoch_id, "bundle_id": "b1", "impact": 0.1, "certificate": {}, "strategy_set": []})
    ledger.append_event("SandboxEvidenceEvent", {"epoch_id": epoch_id, "mutation_id": "m1", "evidence_hash": "sha256:" + ("1" * 64)})

    registry = CheckpointRegistry(ledger, provider=SeededDeterminismProvider("seed"), replay_mode="strict")
    cp1 = registry.create_checkpoint(epoch_id)
    cp2 = registry.create_checkpoint(epoch_id)
    epoch_entries = ledger.read_epoch(epoch_id)
    governance_events = [
        entry for entry in epoch_entries if entry.get("type") == "CheckpointGovernanceEvent"
    ]

    assert cp1["prev_checkpoint_hash"].startswith("sha256:")
    assert cp2["prev_checkpoint_hash"] == cp1["checkpoint_hash"]
    assert cp1["evidence_hash"].startswith("sha256:")
    assert cp1["sandbox_policy_hash"].startswith("sha256:")
    assert len(governance_events) == 2
    assert governance_events[0]["payload"]["event_type"] == "checkpoint_created"
    assert governance_events[1]["payload"]["prior_checkpoint_event_hash"].startswith("sha256:")

    verification = verify_checkpoint_chain(ledger, epoch_id)
    assert verification["passed"]
    assert verification["count"] == 2


def test_checkpoint_registry_lists_deterministic_inventory(tmp_path):
    ledger = LineageLedgerV2(tmp_path / "lineage.jsonl")
    epoch_id = "epoch-1"
    ledger.append_event("MutationBundleEvent", {"epoch_id": epoch_id, "epoch_digest": "sha256:abc"})

    registry = CheckpointRegistry(ledger)
    first = registry.create_checkpoint(epoch_id)
    second = registry.create_checkpoint(epoch_id)

    inventory = registry.list_checkpoints()

    assert inventory["epoch_count"] == 1
    assert inventory["checkpoint_count"] == 2
    checkpoints = inventory["epochs"][0]["checkpoints"]
    assert checkpoints[0]["chain_linked"] is True
    assert checkpoints[1]["prev_checkpoint_hash"] == first["checkpoint_hash"]
    assert checkpoints[1]["checkpoint_hash"] == second["checkpoint_hash"]
