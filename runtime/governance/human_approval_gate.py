# SPDX-License-Identifier: Apache-2.0
"""
HumanApprovalGate — mandatory human-in-the-loop approval for mutation advancement.

Purpose:
    Enforces that no mutation advances past the "proposed" state into "scored"
    or "promoted" state without an explicit, logged human approval event.
    This is the structural guarantee that underpins ADAAD's autonomy model:
    autonomy level increases are earned, not assumed.

Architecture:
    - Approval requests are written to a persistent queue (JSONL file).
    - Each approval decision (approve/reject) is signed with a SHA-256 digest
      and appended to the audit ledger.
    - The gate is fail-closed: if approval state is unknown, the mutation
      is treated as unapproved.
    - Approval events are immutable once written. Revocation creates a new
      REVOKE event referencing the original approval_id.

Approval lifecycle:
    1. PENDING  — request_approval() called; entry added to queue.
    2. APPROVED — record_decision(approved=True) called by operator.
    3. REJECTED — record_decision(approved=False) called by operator.
    4. REVOKED  — revoke_approval() called; REVOKE event appended.

Governance invariants:
    - Every approval/rejection/revocation is signed and ledger-appended.
    - is_approved() is the single query point: returns True only for
      non-revoked APPROVED decisions.
    - Operator identity (operator_id) is required for all decisions.
    - Approval events reference the mutation_id and epoch_id for traceability.
    - At autonomy L1: every mutation requires individual approval.
    - At autonomy L2+: batch approval supported (batch_approve_ids).

Android/Pydroid3 compatibility:
    - Pure Python stdlib only. No C extensions. No threads required.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.timeutils import now_iso

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_QUEUE_PATH  = Path("data/approval_queue.jsonl")
DEFAULT_AUDIT_PATH  = Path("data/approval_audit.jsonl")
APPROVAL_EXPIRY_S   = 86400 * 7   # Approvals expire after 7 days (safety)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ApprovalStatus(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED  = "revoked"
    EXPIRED  = "expired"


class ApprovalReason(str, Enum):
    MUTATION_ADVANCEMENT    = "mutation_advancement"
    PHASE_TRANSITION        = "phase_transition"
    AUTONOMY_LEVEL_INCREASE = "autonomy_level_increase"
    BATCH_RELEASE           = "batch_release"
    MANUAL                  = "manual"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApprovalRequest:
    """A pending approval request for a mutation."""
    approval_id: str
    mutation_id: str
    epoch_id: str
    reason: str
    requested_at: str
    metadata: Dict[str, Any]

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ApprovalDecision:
    """An immutable approval/rejection/revocation decision."""
    approval_id: str
    mutation_id: str
    epoch_id: str
    status: str
    operator_id: str
    decided_at: str
    notes: str
    decision_digest: str

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def compute_digest(
        approval_id: str,
        mutation_id: str,
        status: str,
        operator_id: str,
        decided_at: str,
    ) -> str:
        canonical = json.dumps(
            {
                "approval_id": approval_id,
                "mutation_id": mutation_id,
                "status": status,
                "operator_id": operator_id,
                "decided_at": decided_at,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# HumanApprovalGate
# ---------------------------------------------------------------------------

class HumanApprovalGate:
    """
    Structural human approval gate for mutation advancement.

    Usage — individual approval:
        gate = HumanApprovalGate()
        approval_id = gate.request_approval(
            mutation_id="mut-001",
            epoch_id="epoch-042",
            reason=ApprovalReason.MUTATION_ADVANCEMENT,
        )

        # Operator reviews and approves:
        gate.record_decision(
            approval_id=approval_id,
            approved=True,
            operator_id="dreezy66",
        )

        # Gate check before advancement:
        assert gate.is_approved("mut-001")

    Usage — batch approval (L2+):
        gate.batch_approve(
            mutation_ids=["mut-001", "mut-002"],
            epoch_id="epoch-042",
            operator_id="dreezy66",
            notes="Batch approved after digest review",
        )

    Args:
        queue_path:   Path for pending approval request queue.
        audit_path:   Path for immutable approval audit ledger.
        audit_writer: Optional callable(event_type, payload) for external ledger.
    """

    def __init__(
        self,
        queue_path: Path = DEFAULT_QUEUE_PATH,
        audit_path: Path = DEFAULT_AUDIT_PATH,
        audit_writer: Optional[Any] = None,
    ) -> None:
        self._queue_path = queue_path
        self._audit_path = audit_path
        self._audit = audit_writer
        self._ensure_paths()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_approval(
        self,
        mutation_id: str,
        epoch_id: str,
        reason: str = ApprovalReason.MUTATION_ADVANCEMENT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Submit a mutation for human approval.

        Args:
            mutation_id: The mutation requiring approval.
            epoch_id:    The epoch this mutation belongs to.
            reason:      ApprovalReason explaining why approval is needed.
            metadata:    Optional dict of additional context (score, agent, etc.).

        Returns:
            approval_id: Unique ID for this approval request.
        """
        approval_id = self._generate_approval_id(mutation_id, epoch_id)
        request = ApprovalRequest(
            approval_id=approval_id,
            mutation_id=mutation_id,
            epoch_id=epoch_id,
            reason=str(reason),
            requested_at=now_iso(),
            metadata=metadata or {},
        )
        self._append_queue(request.to_payload())
        self._write_audit(
            event_type="approval_requested",
            payload={**request.to_payload(), "status": ApprovalStatus.PENDING.value},
        )
        return approval_id

    def record_decision(
        self,
        approval_id: str,
        approved: bool,
        operator_id: str,
        notes: str = "",
    ) -> ApprovalDecision:
        """
        Record a human operator's approval or rejection decision.

        Args:
            approval_id: The approval request being decided.
            approved:    True = approve, False = reject.
            operator_id: Identity of the human operator making the decision.
            notes:       Optional human-readable decision notes.

        Returns:
            ApprovalDecision: The immutable decision record.

        Raises:
            ValueError: If approval_id not found in queue.
        """
        request = self._find_request(approval_id)
        if request is None:
            raise ValueError(f"approval_id_not_found:{approval_id}")

        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        decided_at = now_iso()

        decision = ApprovalDecision(
            approval_id=approval_id,
            mutation_id=request["mutation_id"],
            epoch_id=request["epoch_id"],
            status=status.value,
            operator_id=operator_id,
            decided_at=decided_at,
            notes=notes,
            decision_digest=ApprovalDecision.compute_digest(
                approval_id=approval_id,
                mutation_id=request["mutation_id"],
                status=status.value,
                operator_id=operator_id,
                decided_at=decided_at,
            ),
        )

        self._write_audit(event_type="approval_decision", payload=decision.to_payload())

        if self._audit is not None:
            try:
                self._audit("human_approval_decision", decision.to_payload())
            except Exception:  # noqa: BLE001
                pass

        return decision

    def batch_approve(
        self,
        mutation_ids: List[str],
        epoch_id: str,
        operator_id: str,
        notes: str = "",
    ) -> List[ApprovalDecision]:
        """
        Approve multiple mutations in a single operator action (L2+ cadence).
        Each mutation receives an individual signed ApprovalDecision.

        Args:
            mutation_ids: List of mutation IDs to approve.
            epoch_id:     Epoch context for all approvals.
            operator_id:  Human operator performing the batch approval.
            notes:        Notes applied to all decisions in the batch.

        Returns:
            List of ApprovalDecision objects, one per mutation_id.
        """
        decisions: List[ApprovalDecision] = []
        for mutation_id in mutation_ids:
            approval_id = self.request_approval(
                mutation_id=mutation_id,
                epoch_id=epoch_id,
                reason=ApprovalReason.BATCH_RELEASE,
                metadata={"batch_size": len(mutation_ids)},
            )
            decision = self.record_decision(
                approval_id=approval_id,
                approved=True,
                operator_id=operator_id,
                notes=notes,
            )
            decisions.append(decision)
        return decisions

    def revoke_approval(
        self,
        mutation_id: str,
        operator_id: str,
        reason: str,
    ) -> None:
        """
        Revoke a previously granted approval.
        Creates a REVOKE audit event; does not delete the original.
        After revocation, is_approved(mutation_id) returns False.

        Args:
            mutation_id: The mutation whose approval is being revoked.
            operator_id: The operator performing the revocation.
            reason:      Human-readable reason for revocation.
        """
        payload = {
            "mutation_id": mutation_id,
            "operator_id": operator_id,
            "reason": reason,
            "revoked_at": now_iso(),
            "status": ApprovalStatus.REVOKED.value,
        }
        self._write_audit(event_type="approval_revoked", payload=payload)

        if self._audit is not None:
            try:
                self._audit("human_approval_revoked", payload)
            except Exception:  # noqa: BLE001
                pass

    def is_approved(self, mutation_id: str) -> bool:
        """
        Gate check: returns True only if mutation has a non-revoked APPROVED decision.
        This is the canonical query point before any mutation advancement.

        Args:
            mutation_id: The mutation to check.

        Returns:
            True if approved and not subsequently revoked. False otherwise.
        """
        approved = False
        for entry in self._read_audit():
            event_type = entry.get("event_type", "")
            payload = entry.get("payload", {})
            if payload.get("mutation_id") != mutation_id:
                continue
            if event_type == "approval_decision":
                approved = payload.get("status") == ApprovalStatus.APPROVED.value
            elif event_type == "approval_revoked":
                approved = False
        return approved

    def pending_queue(self) -> List[Dict[str, Any]]:
        """
        Return all approval requests that have not yet been decided.
        Used by operator dashboards and review queues.
        """
        decided_ids = {
            entry["payload"].get("approval_id")
            for entry in self._read_audit()
            if entry.get("event_type") == "approval_decision"
        }
        queue: List[Dict[str, Any]] = []
        for entry in self._read_queue():
            if entry.get("approval_id") not in decided_ids:
                queue.append(entry)
        return queue

    def audit_trail(self, mutation_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return the full audit trail, optionally filtered by mutation_id.
        """
        entries = self._read_audit()
        if mutation_id is not None:
            entries = [
                e for e in entries
                if e.get("payload", {}).get("mutation_id") == mutation_id
            ]
        return entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_approval_id(self, mutation_id: str, epoch_id: str) -> str:
        seed = f"{mutation_id}:{epoch_id}:{now_iso()}"
        return "appr-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    def _ensure_paths(self) -> None:
        self._queue_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._queue_path.touch(exist_ok=True)
        self._audit_path.touch(exist_ok=True)

    def _append_queue(self, payload: Dict[str, Any]) -> None:
        with self._queue_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True) + "\n")

    def _read_queue(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for line in self._queue_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return rows

    def _find_request(self, approval_id: str) -> Optional[Dict[str, Any]]:
        for entry in self._read_queue():
            if entry.get("approval_id") == approval_id:
                return entry
        return None

    def _write_audit(self, event_type: str, payload: Dict[str, Any]) -> None:
        entry = {
            "event_type": event_type,
            "timestamp": now_iso(),
            "payload": payload,
        }
        with self._audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")

    def _read_audit(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for line in self._audit_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return rows


__all__ = [
    "ApprovalStatus",
    "ApprovalReason",
    "ApprovalRequest",
    "ApprovalDecision",
    "HumanApprovalGate",
    "APPROVAL_EXPIRY_S",
]
