# SPDX-License-Identifier: Apache-2.0
"""Epoch checkpoint registry for deterministic governance evidence.

Fail-close consumers should rely on :meth:`list_checkpoints` inventory output for
deterministic checkpoint replay material and chain linkage status.
"""

from __future__ import annotations

from typing import Any, Dict

from runtime.evolution.checkpoint_events import EpochCheckpointEvent
from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.governance.foundation import (
    RuntimeDeterminismProvider,
    ZERO_HASH,
    default_provider,
    require_replay_safe_provider,
    safe_get,
    sha256_prefixed_digest,
)


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


class CheckpointRegistry:
    def __init__(
        self,
        ledger: LineageLedgerV2,
        *,
        provider: RuntimeDeterminismProvider | None = None,
        replay_mode: str = "off",
        recovery_tier: str | None = None,
        promotion_policy_hash: str = ZERO_HASH,
        entropy_policy_hash: str = ZERO_HASH,
        sandbox_policy_hash: str = ZERO_HASH,
    ) -> None:
        self.ledger = ledger
        self.provider = provider or default_provider()
        self.replay_mode = replay_mode
        self.recovery_tier = recovery_tier
        self.promotion_policy_hash = promotion_policy_hash
        self.entropy_policy_hash = entropy_policy_hash
        self.sandbox_policy_hash = sandbox_policy_hash

    def _latest_checkpoint_hash(self, epoch_id: str) -> str:
        latest = ZERO_HASH
        for entry in self.ledger.read_epoch(epoch_id):
            if safe_get(entry, "type", default="") != "EpochCheckpointEvent":
                continue
            candidate = safe_get(entry, "payload", "checkpoint_hash")
            if isinstance(candidate, str) and candidate:
                latest = candidate
        return latest

    def _latest_checkpoint_event_hash(self) -> str:
        latest = ZERO_HASH
        for entry in self.ledger.read_all():
            if safe_get(entry, "type", default="") != "checkpoint_created":
                continue
            event_hash = str(safe_get(entry, "hash", default=""))
            if event_hash:
                latest = f"sha256:{event_hash}"
        return latest

    def create_checkpoint(self, epoch_id: str) -> Dict[str, Any]:
        require_replay_safe_provider(self.provider, replay_mode=self.replay_mode, recovery_tier=self.recovery_tier)
        epoch_events = self.ledger.read_epoch(epoch_id)
        mutation_count = sum(1 for e in epoch_events if safe_get(e, "type", default="") == "MutationBundleEvent")
        promotion_count = sum(1 for e in epoch_events if safe_get(e, "type", default="") == "PromotionEvent")
        scoring_count = sum(1 for e in epoch_events if safe_get(e, "type", default="") == "ScoringEvent")
        sandbox_evidence = [
            safe_get(e, "payload", "evidence_hash")
            for e in epoch_events
            if safe_get(e, "type", default="") == "SandboxEvidenceEvent"
        ]
        evidence_hash = sha256_prefixed_digest(sorted(v for v in sandbox_evidence if isinstance(v, str)))

        epoch_digest = self.ledger.get_epoch_digest(epoch_id) or "sha256:0"
        baseline_digest = self.ledger.compute_incremental_epoch_digest(epoch_id)
        prev_checkpoint_hash = self._latest_checkpoint_hash(epoch_id)
        checkpoint_material = {
            "epoch_id": epoch_id,
            "epoch_digest": epoch_digest,
            "baseline_digest": baseline_digest,
            "mutation_count": mutation_count,
            "promotion_event_count": promotion_count,
            "scoring_event_count": scoring_count,
            "promotion_policy_hash": self.promotion_policy_hash,
            "entropy_policy_hash": self.entropy_policy_hash,
            "evidence_hash": evidence_hash,
            "sandbox_policy_hash": self.sandbox_policy_hash,
            "prev_checkpoint_hash": prev_checkpoint_hash,
        }
        checkpoint_hash = sha256_prefixed_digest(checkpoint_material)
        checkpoint_id_material = {"epoch_id": epoch_id, "manifest_hash": checkpoint_hash}
        checkpoint_id = f"chk_{sha256_prefixed_digest(checkpoint_id_material).split(':', 1)[1][:16]}"
        event = EpochCheckpointEvent(
            epoch_id=epoch_id,
            checkpoint_id=checkpoint_id,
            checkpoint_hash=checkpoint_hash,
            prev_checkpoint_hash=prev_checkpoint_hash,
            epoch_digest=epoch_digest,
            baseline_digest=baseline_digest,
            mutation_count=mutation_count,
            promotion_event_count=promotion_count,
            scoring_event_count=scoring_count,
            entropy_policy_hash=self.entropy_policy_hash,
            promotion_policy_hash=self.promotion_policy_hash,
            evidence_hash=evidence_hash,
            sandbox_policy_hash=self.sandbox_policy_hash,
            created_at=self.provider.iso_now(),
        )
        payload = event.to_payload()
        self.ledger.append_event("EpochCheckpointEvent", payload)

        # Governance audit event — required by checkpoint chain verifier and
        # test assertions that track `CheckpointGovernanceEvent` entries.
        prior_event_hash = self._latest_checkpoint_event_hash()
        governance_payload = {
            "event_type": "checkpoint_created",
            "checkpoint_id": checkpoint_id,
            "epoch_id": epoch_id,
            "manifest_hash": checkpoint_hash,
            "prior_checkpoint_event_hash": prior_event_hash,
            "snapshot_path": f"checkpoints/{checkpoint_id}",
            "timestamp": self.provider.iso_now(),
        }
        self.ledger.append_event("CheckpointGovernanceEvent", governance_payload)
        return payload

    def list_checkpoints(self) -> Dict[str, Any]:
        """Return deterministic checkpoint inventory grouped by epoch."""
        epoch_ids = self.ledger.list_epoch_ids()
        inventory: list[Dict[str, Any]] = []
        checkpoint_count = 0

        for epoch_id in epoch_ids:
            previous_hash = ZERO_HASH
            checkpoints: list[Dict[str, Any]] = []
            checkpoint_index = 0
            for entry in self.ledger.read_epoch(epoch_id):
                if safe_get(entry, "type", default="") != "EpochCheckpointEvent":
                    continue
                payload = dict(safe_get(entry, "payload", default={}) or {})
                checkpoint_hash = str(payload.get("checkpoint_hash") or "")
                prev_checkpoint_hash = str(payload.get("prev_checkpoint_hash") or "")
                material = _checkpoint_material(payload)
                checkpoints.append(
                    {
                        "index": checkpoint_index,
                        "checkpoint_id": str(payload.get("checkpoint_id") or ""),
                        "checkpoint_hash": checkpoint_hash,
                        "prev_checkpoint_hash": prev_checkpoint_hash,
                        "expected_prev_checkpoint_hash": previous_hash,
                        "chain_linked": prev_checkpoint_hash == previous_hash,
                        "verification_material": material,
                        "expected_checkpoint_hash": sha256_prefixed_digest(material),
                    }
                )
                previous_hash = checkpoint_hash or previous_hash
                checkpoint_count += 1
                checkpoint_index += 1
            inventory.append({"epoch_id": epoch_id, "checkpoints": checkpoints})

        return {
            "epoch_count": len(epoch_ids),
            "checkpoint_count": checkpoint_count,
            "epochs": inventory,
        }


__all__ = ["CheckpointRegistry"]
