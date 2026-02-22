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


def _normalize_hash_link(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ZERO_HASH
    if raw.startswith("sha256:"):
        return raw
    return f"sha256:{raw}"



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

    @staticmethod
    def verify_checkpoint_chain_with_event(ledger: LineageLedgerV2, epoch_id: str) -> Dict[str, Any]:
        checkpoints: List[Dict[str, Any]] = [
            dict(entry.get("payload") or {})
            for entry in ledger.read_epoch(epoch_id)
            if entry.get("type") == "EpochCheckpointEvent"
        ]
        previous = ZERO_HASH
        errors: List[str] = []
        halt_reason_code = ""
        halt_reason_detail = ""
        for index, cp in enumerate(checkpoints):
            prev = str(cp.get("prev_checkpoint_hash") or "")
            if prev != previous:
                errors.append(f"prev_checkpoint_mismatch:{index}")
                if not halt_reason_code:
                    halt_reason_code = "prev_checkpoint_mismatch"
                    halt_reason_detail = f"epoch={epoch_id};index={index}"
            expected_hash = sha256_prefixed_digest(CheckpointVerifier._checkpoint_material(cp))
            if str(cp.get("checkpoint_hash") or "") != expected_hash:
                errors.append(f"checkpoint_hash_mismatch:{index}")
                if not halt_reason_code:
                    halt_reason_code = "checkpoint_hash_mismatch"
                    halt_reason_detail = f"epoch={epoch_id};index={index}"
            previous = str(cp.get("checkpoint_hash") or previous)

        chain_event_type = "checkpoint_chain_verified" if not errors else "checkpoint_chain_violated"
        chain_event_payload = {
            "schema_version": "1.0",
            "event_type": chain_event_type,
            "epoch_id": epoch_id,
            "checkpoint_count": len(checkpoints),
            "verified": not errors,
            "halt_reason_code": halt_reason_code,
            "halt_reason_detail": halt_reason_detail,
            "last_verified_checkpoint_hash": previous,
            "prior_checkpoint_chain_event_hash": ZERO_HASH,
        }

        for entry in ledger.read_epoch(epoch_id):
            if entry.get("type") != "CheckpointChainGovernanceEvent":
                continue
            payload = dict(entry.get("payload") or {})
            if str(payload.get("event_type") or "") not in {"checkpoint_chain_verified", "checkpoint_chain_violated"}:
                continue
            chain_event_payload["prior_checkpoint_chain_event_hash"] = _normalize_hash_link(str(entry.get("hash") or ""))

        ledger.append_event("CheckpointChainGovernanceEvent", chain_event_payload)
        return {
            "epoch_id": epoch_id,
            "count": len(checkpoints),
            "passed": not errors,
            "errors": errors,
            "event_type": chain_event_type,
            "halt_reason_code": halt_reason_code,
            "halt_reason_detail": halt_reason_detail,
        }

    @staticmethod
    def verify_chain(ledger: LineageLedgerV2, epoch_id: str) -> Dict[str, Any]:
        """Deterministically verify checkpoint chain and emit governance event."""
        return CheckpointVerifier.verify_checkpoint_chain_with_event(ledger, epoch_id)

    @staticmethod
    def verify_epoch_checkpoint_continuity(ledger: LineageLedgerV2, epoch_id: str) -> Dict[str, Any]:
        checkpoints: List[Dict[str, Any]] = [
            dict(entry.get("payload") or {})
            for entry in ledger.read_epoch(epoch_id)
            if entry.get("type") == "EpochCheckpointEvent"
        ]
        hashed = [checkpoint for checkpoint in checkpoints if str(checkpoint.get("checkpoint_hash") or "")]
        if not hashed:
            result = {
                "ok": False,
                "reason": "prior_checkpoint_missing",
                "epoch_id": epoch_id,
                "terminal_checkpoint_hash": "",
            }
            ledger.append_event("epoch_checkpoint_continuity_failed", result)
            raise CheckpointVerificationError(code="prior_checkpoint_missing", detail=f"epoch={epoch_id}")

        previous_hash = ZERO_HASH
        for index, checkpoint in enumerate(hashed):
            prev_checkpoint_hash = str(checkpoint.get("prev_checkpoint_hash") or "")
            if prev_checkpoint_hash != previous_hash:
                result = {
                    "ok": False,
                    "reason": f"checkpoint_prev_mismatch:{index}",
                    "epoch_id": epoch_id,
                    "expected_prev_checkpoint_hash": previous_hash,
                    "actual_prev_checkpoint_hash": prev_checkpoint_hash,
                }
                ledger.append_event("epoch_checkpoint_continuity_failed", result)
                raise CheckpointVerificationError(code="checkpoint_prev_mismatch", detail=f"epoch={epoch_id};index={index}")
            expected_hash = sha256_prefixed_digest(CheckpointVerifier._checkpoint_material(checkpoint))
            checkpoint_hash = str(checkpoint.get("checkpoint_hash") or "")
            if checkpoint_hash != expected_hash:
                result = {
                    "ok": False,
                    "reason": f"checkpoint_hash_mismatch:{index}",
                    "epoch_id": epoch_id,
                    "checkpoint_hash": checkpoint_hash,
                    "expected_checkpoint_hash": expected_hash,
                }
                ledger.append_event("epoch_checkpoint_continuity_failed", result)
                raise CheckpointVerificationError(code="checkpoint_hash_mismatch", detail=f"epoch={epoch_id};index={index}")
            previous_hash = checkpoint_hash

        terminal_checkpoint_hash = str(hashed[-1].get("checkpoint_hash") or "")
        result = {
            "ok": True,
            "epoch_id": epoch_id,
            "terminal_checkpoint_hash": terminal_checkpoint_hash,
            "checkpoint_count": len(hashed),
        }
        ledger.append_event("epoch_checkpoint_continuity_verified", result)
        return result


def verify_checkpoint_chain(ledger: LineageLedgerV2, epoch_id: str) -> Dict[str, Any]:
    return CheckpointVerifier.verify_chain(ledger, epoch_id)


__all__ = [
    "CheckpointVerifier",
    "CheckpointVerificationError",
    "verify_checkpoint_chain",
]
