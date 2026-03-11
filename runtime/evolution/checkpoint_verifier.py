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
from runtime.governance.foundation import ZERO_HASH, RuntimeDeterminismProvider, default_provider, sha256_prefixed_digest


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
                    CheckpointVerifier._emit_tamper_escalation(
                        ledger=ledger,
                        reason_code="checkpoint_prev_missing",
                        epoch_id=epoch_id,
                        checkpoint=checkpoint,
                    )
                    raise CheckpointVerificationError(
                        code="checkpoint_prev_missing",
                        detail=f"epoch={epoch_id};index={index}",
                    )

                expected_hash = str(checkpoint.get("expected_checkpoint_hash") or "")
                actual_hash = str(checkpoint.get("checkpoint_hash") or "")
                if not actual_hash:
                    CheckpointVerifier._emit_tamper_escalation(
                        ledger=ledger,
                        reason_code="checkpoint_hash_missing",
                        epoch_id=epoch_id,
                        checkpoint=checkpoint,
                    )
                    raise CheckpointVerificationError(
                        code="checkpoint_hash_missing",
                        detail=f"epoch={epoch_id};index={index}",
                    )
                if actual_hash != expected_hash:
                    CheckpointVerifier._emit_tamper_escalation(
                        ledger=ledger,
                        reason_code="checkpoint_hash_mismatch",
                        epoch_id=epoch_id,
                        checkpoint=checkpoint,
                    )
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
    def _tamper_escalation_payload(
        *,
        reason_code: str,
        epoch_id: str,
        checkpoint: Dict[str, Any],
    ) -> Dict[str, Any]:
        checkpoint_id = str(checkpoint.get("checkpoint_id") or "")
        checkpoint_index = int(checkpoint.get("index", 0))
        expected_checkpoint_hash = str(checkpoint.get("expected_checkpoint_hash") or "")
        actual_checkpoint_hash = str(checkpoint.get("checkpoint_hash") or "")
        expected_prev_checkpoint_hash = str(checkpoint.get("expected_prev_checkpoint_hash") or ZERO_HASH)
        actual_prev_checkpoint_hash = str(checkpoint.get("prev_checkpoint_hash") or ZERO_HASH)

        checkpoint_locator = {
            "epoch_id": epoch_id,
            "checkpoint_id": checkpoint_id,
            "checkpoint_index": checkpoint_index,
        }
        hash_material = {
            "expected_checkpoint_hash": expected_checkpoint_hash,
            "actual_checkpoint_hash": actual_checkpoint_hash,
            "expected_prev_checkpoint_hash": expected_prev_checkpoint_hash,
            "actual_prev_checkpoint_hash": actual_prev_checkpoint_hash,
        }
        evidence_material = {
            "reason_code": reason_code,
            "checkpoint_locator": checkpoint_locator,
            "hash_material": hash_material,
        }
        return {
            "schema_version": "1.0",
            "event_type": "checkpoint_tamper_escalation",
            "reason_code": reason_code,
            "checkpoint_locator": checkpoint_locator,
            "deterministic_hashes": {
                "checkpoint_locator_hash": sha256_prefixed_digest(checkpoint_locator),
                "hash_material_hash": sha256_prefixed_digest(hash_material),
                "evidence_payload_hash": sha256_prefixed_digest(evidence_material),
            },
            "expected_checkpoint_hash": expected_checkpoint_hash,
            "actual_checkpoint_hash": actual_checkpoint_hash,
            "expected_prev_checkpoint_hash": expected_prev_checkpoint_hash,
            "actual_prev_checkpoint_hash": actual_prev_checkpoint_hash,
        }

    @staticmethod
    def _emit_tamper_escalation(
        *,
        ledger: LineageLedgerV2,
        reason_code: str,
        epoch_id: str,
        checkpoint: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = CheckpointVerifier._tamper_escalation_payload(
            reason_code=reason_code,
            epoch_id=epoch_id,
            checkpoint=checkpoint,
        )
        ledger.append_event("CheckpointTamperEscalationEvent", payload)
        return payload

    @staticmethod
    def _is_checkpoint_entry(entry: Dict[str, Any]) -> bool:
        """Return True if entry is a checkpoint materialization record."""
        t = entry.get("type") or ""
        if t == "checkpoint_created":
            return True
        if t == "CheckpointGovernanceEvent":
            payload = dict(entry.get("payload") or {})
            return str(payload.get("event_type") or "") == "checkpoint_created"
        return False

    @staticmethod
    def _prev_hash_from_entry(entry: Dict[str, Any]) -> str:
        """Normalize the prev-hash field across entry types."""
        payload = dict(entry.get("payload") or {})
        t = entry.get("type") or ""
        if t == "CheckpointGovernanceEvent":
            return str(payload.get("prior_checkpoint_event_hash") or ZERO_HASH)
        return str(payload.get("previous_checkpoint_hash") or ZERO_HASH)

    @staticmethod
    def verify_chain(ledger: LineageLedgerV2, *, provider: RuntimeDeterminismProvider | None = None) -> Dict[str, Any]:
        provider = provider or default_provider()
        checkpoint_entries = [
            entry for entry in ledger.read_all()
            if CheckpointVerifier._is_checkpoint_entry(entry)
        ]
        previous_hash = ZERO_HASH
        for entry in checkpoint_entries:
            payload = dict(entry.get("payload") or {})
            checkpoint_id = str(payload.get("checkpoint_id") or "")
            actual_prev = CheckpointVerifier._prev_hash_from_entry(entry)
            if actual_prev != previous_hash:
                ledger.append_event(
                    "checkpoint_chain_violated",
                    {
                        "checkpoint_id": checkpoint_id,
                        "expected_hash": previous_hash,
                        "actual_hash": actual_prev,
                        "halt_reason": "missing_genesis" if previous_hash == ZERO_HASH else "chain_gap",
                        "timestamp": provider.iso_now(),
                    },
                )
                raise CheckpointVerificationError("checkpoint_chain_violated", f"checkpoint_id={checkpoint_id}")

            expected_id_material = {"epoch_id": payload.get("epoch_id"), "manifest_hash": payload.get("manifest_hash")}
            expected_id = f"chk_{sha256_prefixed_digest(expected_id_material).split(':', 1)[1][:16]}"
            if checkpoint_id != expected_id:
                ledger.append_event(
                    "checkpoint_chain_violated",
                    {
                        "checkpoint_id": checkpoint_id,
                        "expected_hash": expected_id,
                        "actual_hash": checkpoint_id,
                        "halt_reason": "hash_mismatch",
                        "timestamp": provider.iso_now(),
                    },
                )
                raise CheckpointVerificationError("checkpoint_chain_violated", f"checkpoint_id={checkpoint_id}")

            entry_hash = str(entry.get("hash") or "")
            previous_hash = f"sha256:{entry_hash}" if entry_hash else previous_hash

        if checkpoint_entries:
            latest_payload = dict(checkpoint_entries[-1].get("payload") or {})
            ledger.append_event(
                "checkpoint_chain_verified",
                {
                    "chain_depth": len(checkpoint_entries),
                    "latest_checkpoint_id": latest_payload.get("checkpoint_id", ""),
                    "latest_manifest_hash": latest_payload.get("manifest_hash", ""),
                    "timestamp": provider.iso_now(),
                },
            )
        return {"verified": True, "chain_depth": len(checkpoint_entries)}

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


def verify_checkpoint_chain(ledger: LineageLedgerV2, epoch_id: str) -> Dict[str, Any]:
    return CheckpointVerifier.verify_checkpoint_chain_with_event(ledger, epoch_id)


def verify_epoch_checkpoint_continuity(
    ledger: LineageLedgerV2,
    *,
    current_epoch_id: str,
    provider: RuntimeDeterminismProvider | None = None,
) -> Dict[str, Any]:
    provider = provider or default_provider()
    epoch_ids = ledger.list_epoch_ids()
    if current_epoch_id not in epoch_ids:
        return {"verified": True, "reason": "epoch_untracked"}
    idx = epoch_ids.index(current_epoch_id)
    if idx == 0:
        return {"verified": True, "reason": "genesis_epoch"}

    prior_epoch_id = epoch_ids[idx - 1]
    prior_checkpoints = [
        dict(entry.get("payload") or {})
        for entry in ledger.read_epoch(prior_epoch_id)
        if entry.get("type") == "EpochCheckpointEvent"
    ]
    if not prior_checkpoints:
        ledger.append_event(
            "epoch_checkpoint_continuity_failed",
            {
                "prior_epoch_id": prior_epoch_id,
                "new_epoch_id": current_epoch_id,
                "halt_reason": "missing_terminal_checkpoint",
                "timestamp": provider.iso_now(),
            },
        )
        raise CheckpointVerificationError("epoch_checkpoint_continuity_failed", f"prior_epoch={prior_epoch_id}")

    prior_terminal = prior_checkpoints[-1]
    verification = verify_checkpoint_chain(ledger, prior_epoch_id)
    if not verification.get("passed", False):
        ledger.append_event(
            "epoch_checkpoint_continuity_failed",
            {
                "prior_epoch_id": prior_epoch_id,
                "prior_terminal_checkpoint_id": prior_terminal.get("checkpoint_id", ""),
                "new_epoch_id": current_epoch_id,
                "halt_reason": "hash_mismatch",
                "timestamp": provider.iso_now(),
            },
        )
        raise CheckpointVerificationError("epoch_checkpoint_continuity_failed", f"prior_epoch={prior_epoch_id}")

    ledger.append_event(
        "epoch_checkpoint_continuity_verified",
        {
            "prior_epoch_id": prior_epoch_id,
            "prior_terminal_checkpoint_id": prior_terminal.get("checkpoint_id", ""),
            "new_epoch_id": current_epoch_id,
            "timestamp": provider.iso_now(),
        },
    )
    return {"verified": True, "prior_epoch_id": prior_epoch_id}


__all__ = [
    "CheckpointVerifier",
    "CheckpointVerificationError",
    "verify_checkpoint_chain",
    "verify_epoch_checkpoint_continuity",
]
