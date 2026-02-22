# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from app.main import Orchestrator
from runtime.evolution.checkpoint_registry import CheckpointRegistry
from runtime.evolution.lineage_v2 import LineageLedgerV2


class _WarmPoolStub:
    def start(self) -> None:
        return


class _RuntimeStub:
    def __init__(self, ledger: LineageLedgerV2) -> None:
        self.ledger = ledger


def test_orchestrator_init_runtime_halts_on_tampered_checkpoint_before_mutation(monkeypatch, tmp_path: Path) -> None:
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    epoch_id = "epoch-tampered"
    ledger.append_event("MutationBundleEvent", {"epoch_id": epoch_id, "epoch_digest": "sha256:abc"})
    CheckpointRegistry(ledger).create_checkpoint(epoch_id)

    ledger.append_event(
        "EpochCheckpointEvent",
        {
            "epoch_id": epoch_id,
            "checkpoint_id": "chk_tampered",
            "checkpoint_hash": "sha256:" + ("0" * 64),
            "prev_checkpoint_hash": "sha256:" + ("f" * 64),
            "epoch_digest": "sha256:abc",
            "baseline_digest": "sha256:abc",
            "mutation_count": 1,
            "promotion_event_count": 0,
            "scoring_event_count": 0,
            "entropy_policy_hash": "sha256:" + ("0" * 64),
            "promotion_policy_hash": "sha256:" + ("0" * 64),
            "evidence_hash": "sha256:" + ("0" * 64),
            "sandbox_policy_hash": "sha256:" + ("0" * 64),
        },
    )

    monkeypatch.setattr("app.main.verify_all", lambda: (True, []))

    orchestrator = object.__new__(Orchestrator)
    orchestrator.state = {"status": "initializing", "mutation_enabled": False}
    orchestrator.warm_pool = _WarmPoolStub()
    orchestrator.evolution_runtime = _RuntimeStub(ledger)

    def _fail(reason: str) -> None:
        raise RuntimeError(reason)

    orchestrator._fail = _fail

    with pytest.raises(RuntimeError, match=r"^checkpoint_verification_failed:checkpoint_prev_missing:epoch=epoch-tampered;index=1$"):
        orchestrator._init_runtime()

    assert orchestrator.state["mutation_enabled"] is False
