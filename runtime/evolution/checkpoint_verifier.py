# SPDX-License-Identifier: Apache-2.0
"""Checkpoint chain verification helpers.

Fail-close verification APIs raise deterministic errors with stable codes when
checkpoint chain links or hashes are missing/mismatched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from runtime.evolution.checkpoint_registry import CheckpointRegistry
from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.governance.foundation import ZERO_HASH, sha256_prefixed_digest


@dataclass(frozen=True)
class CheckpointVerificationError(RuntimeError):
    """Deterministic checkpoint verification error with stable code."""

    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}:{self.detail}"


class CheckpointVerifier:
    """Verifier for epoch checkpoint materialization in append-only ledgers."""

    @staticmethod
    def _checkpoint_material(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "epoch_id": payload.get("epoch_id"),
            "epoch_digest": payload.get("epoch_digest"),
            "baseline_digest": payload.get("baseline_digest"),
            "mutation_count": payload.get("mutation_count"),
            "promotion_event_count": payload.get("promotion_event_count"),
            "scoring_event_count": payload.get("scoring_event_count"),
            "promotion_policy_hash": payload.get("promotion_policy_hash"),
            "entropy_policy_hash": payload.get("entropy_policy_hash"),
            "evidence_hash": payload.get("evidence_hash"),
            "sandbox_policy_hash": payload.get("sandbox_policy_hash"),
            "prev_checkpoint_hash": payload.get("prev_checkpoint_hash"),
        }

    @staticmethod
    def verify_all_checkpoints(ledger_path: str | Path) -> Dict[str, Any]:
        ledger = LineageLedgerV2(Path(ledger_path))
        inventory = CheckpointRegistry(ledger).list_checkpoints()

        for epoch in inventory["epochs"]:
            epoch_id = str(epoch.get("epoch_id") or "")
            checkpoints = epoch.get("checkpoints") or []
            for checkpoint in checkpoints:
                index = int(checkpoint.get("index", 0))
                if not checkpoint.get("chain_linked", False):
                    raise CheckpointVerificationError(
                        code="checkpoint_prev_missing",
                        detail=f"epoch={epoch_id};index={index}",
                    )

                expected_hash = str(checkpoint.get("expected_checkpoint_hash") or "")
                actual_hash = str(checkpoint.get("checkpoint_hash") or "")
                if not actual_hash:
                    raise CheckpointVerificationError(
                        code="checkpoint_hash_missing",
                        detail=f"epoch={epoch_id};index={index}",
                    )
                if actual_hash != expected_hash:
                    raise CheckpointVerificationError(
                        code="checkpoint_hash_mismatch",
                        detail=f"epoch={epoch_id};index={index}",
                    )

        return {
            "epoch_count": int(inventory.get("epoch_count", 0)),
            "checkpoint_count": int(inventory.get("checkpoint_count", 0)),
            "verified": True,
        }

    @staticmethod
    def verify_all_epochs(ledger_path: str | Path) -> Dict[str, Any]:
        return CheckpointVerifier.verify_all_checkpoints(ledger_path)


def verify_checkpoint_chain(ledger: LineageLedgerV2, epoch_id: str) -> Dict[str, Any]:
    checkpoints: List[Dict[str, Any]] = [
        dict(entry.get("payload") or {})
        for entry in ledger.read_epoch(epoch_id)
        if entry.get("type") == "EpochCheckpointEvent"
    ]
    previous = ZERO_HASH
    errors: List[str] = []
    for index, cp in enumerate(checkpoints):
        prev = str(cp.get("prev_checkpoint_hash") or "")
        if prev != previous:
            errors.append(f"prev_checkpoint_mismatch:{index}")
        expected_hash = sha256_prefixed_digest(CheckpointVerifier._checkpoint_material(cp))
        if str(cp.get("checkpoint_hash") or "") != expected_hash:
            errors.append(f"checkpoint_hash_mismatch:{index}")
        previous = str(cp.get("checkpoint_hash") or previous)
    return {"epoch_id": epoch_id, "count": len(checkpoints), "passed": not errors, "errors": errors}


__all__ = ["CheckpointVerifier", "CheckpointVerificationError", "verify_checkpoint_chain"]
