# SPDX-License-Identifier: Apache-2.0
"""FederationMutationBroker — Phase 5 governed cross-repo mutation propagation.

This module is the canonical Phase 5 primitive that upgrades the federation layer
from **read-only signal ingestion** (``FederatedSignalBroker``) to **governed
mutation propagation**.

Architecture
------------
::

    FederationMutationBroker
         ├── propose_federated_mutation()   — package + sign a local gate-approved
         │                                     mutation for downstream delivery
         ├── receive_federated_proposals()  — drain inbound proposals from transport
         ├── evaluate_inbound_proposal()    — run destination GovernanceGate over
         │                                     inbound proposal (dual-gate contract)
         └── accepted_proposals()           — read-only audit view of accepted list

Invariants (constitutional requirements)
-----------------------------------------
1. **Dual-gate**: a federated mutation requires ``GovernanceGate.approve_mutation()``
   to pass in **both** source and destination repos.  The broker never bypasses a
   gate decision.
2. **Fail-closed**: any contract violation, serialisation error, or gate rejection
   causes the proposal to be quarantined — it is never silently discarded.
3. **Provenance chain**: every accepted inbound proposal is recorded with a full
   ``FederationOrigin`` so ``LineageLedgerV2`` can reconstruct cross-repo lineage.
4. **Deterministic serialisation**: proposal envelopes use canonical JSON
   (sort_keys=True, no floats without decimal representation).
5. **No GovernanceGate calls in broadcast path**: ``propose_federated_mutation``
   packages an *already-approved* gate decision; it does not re-evaluate it.
6. **Audit ledger write failures never block decisions** (fail-open on audit only).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Contract errors
# ---------------------------------------------------------------------------


class FederationMutationBrokerError(RuntimeError):
    """Base class for FederationMutationBroker contract violations."""


class FederationProposalValidationError(FederationMutationBrokerError):
    """Raised when an inbound proposal envelope fails structural validation."""


class FederationDualGateError(FederationMutationBrokerError):
    """Raised when the destination GovernanceGate rejects an inbound proposal."""


# ---------------------------------------------------------------------------
# Proposal envelope dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FederatedMutationProposal:
    """Canonical wire envelope for a cross-repo governed mutation.

    Fields
    ------
    proposal_id:
        Stable UUID-4 identifier for this envelope.  Identical across retries —
        derive from ``source_mutation_id`` + ``source_epoch_id`` for idempotency.
    source_repo:
        Canonical repository identifier of the originating node.
    source_epoch_id:
        Epoch at which the mutation was accepted in the source repo.
    source_mutation_id:
        Mutation identifier in the source repo's GovernanceGate approval record.
    source_chain_digest:
        SHA-256 tip of the source repo's lineage ledger at epoch boundary.
        Required for cross-repo determinism verification.
    destination_repo:
        Target repository that must evaluate this proposal through its own
        GovernanceGate before accepting.
    mutation_payload:
        The actual mutation content (diff, strategy, metadata).  Opaque to the
        broker; validated structurally but not semantically.
    gate_decision_payload:
        Serialised ``GateDecision.to_payload()`` from the source repo's approval.
        Required for audit trail completeness.
    federation_gate_id:
        Broker-assigned identifier for this propagation event.
    schema_version:
        Envelope schema version — always ``"federation_mutation_proposal.v1"``.
    """

    proposal_id: str
    source_repo: str
    source_epoch_id: str
    source_mutation_id: str
    source_chain_digest: str
    destination_repo: str
    mutation_payload: Dict[str, Any]
    gate_decision_payload: Dict[str, Any]
    federation_gate_id: str = ""
    schema_version: str = "federation_mutation_proposal.v1"

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Canonical deterministic serialisation (sort_keys applied by caller)."""
        return {
            "destination_repo": self.destination_repo,
            "federation_gate_id": self.federation_gate_id,
            "gate_decision_payload": self.gate_decision_payload,
            "mutation_payload": self.mutation_payload,
            "proposal_id": self.proposal_id,
            "schema_version": self.schema_version,
            "source_chain_digest": self.source_chain_digest,
            "source_epoch_id": self.source_epoch_id,
            "source_mutation_id": self.source_mutation_id,
            "source_repo": self.source_repo,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)

    def digest(self) -> str:
        """SHA-256 digest of the canonical JSON envelope."""
        return "sha256:" + hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FederatedMutationProposal":
        required = {
            "proposal_id", "source_repo", "source_epoch_id", "source_mutation_id",
            "source_chain_digest", "destination_repo", "mutation_payload",
            "gate_decision_payload",
        }
        missing = required - set(data)
        if missing:
            raise FederationProposalValidationError(
                f"federation_proposal:missing_fields:{sorted(missing)}"
            )
        return cls(
            proposal_id=str(data["proposal_id"]),
            source_repo=str(data["source_repo"]),
            source_epoch_id=str(data["source_epoch_id"]),
            source_mutation_id=str(data["source_mutation_id"]),
            source_chain_digest=str(data["source_chain_digest"]),
            destination_repo=str(data["destination_repo"]),
            mutation_payload=dict(data["mutation_payload"]),
            gate_decision_payload=dict(data["gate_decision_payload"]),
            federation_gate_id=str(data.get("federation_gate_id", "")),
            schema_version=str(data.get("schema_version",
                                         "federation_mutation_proposal.v1")),
        )

    def to_federation_origin(self) -> Any:
        """Convert to a ``FederationOrigin`` for lineage ledger recording.

        Import is deferred to avoid circular dependency between
        ``runtime.evolution`` and ``runtime.governance.federation``.
        """
        from runtime.evolution.lineage_v2 import FederationOrigin  # noqa: PLC0415
        return FederationOrigin(
            source_repo=self.source_repo,
            source_epoch_id=self.source_epoch_id,
            source_mutation_id=self.source_mutation_id,
            source_chain_digest=self.source_chain_digest,
            federation_gate_id=self.federation_gate_id,
        )


# ---------------------------------------------------------------------------
# Accepted proposal record
# ---------------------------------------------------------------------------


@dataclass
class AcceptedFederatedMutation:
    """Record of a federated proposal that passed the destination GovernanceGate."""

    proposal: FederatedMutationProposal
    destination_gate_decision_payload: Dict[str, Any]
    acceptance_digest: str  # sha256 of (proposal.digest + destination_gate_id)


# ---------------------------------------------------------------------------
# FederationMutationBroker
# ---------------------------------------------------------------------------


class FederationMutationBroker:
    """Governed cross-repo mutation propagation broker.

    Parameters
    ----------
    local_repo:
        Canonical identifier for the repository running this broker instance.
    governance_gate:
        The local ``GovernanceGate`` instance.  Used to evaluate inbound
        proposals (destination-side dual-gate).
    lineage_chain_digest_fn:
        Zero-arg callable that returns the current SHA-256 tip of the local
        lineage ledger.  Called at proposal packaging time to stamp
        ``source_chain_digest``.
    audit_writer:
        Optional callable ``(event_type: str, payload: dict) -> None`` for
        appending broker events to the evidence ledger.  Failures are
        logged but never re-raised (fail-open on audit).
    """

    def __init__(
        self,
        *,
        local_repo: str,
        governance_gate: Any,
        lineage_chain_digest_fn: Any,
        audit_writer: Optional[Any] = None,
    ) -> None:
        self._local_repo = local_repo
        self._gate = governance_gate
        self._chain_digest_fn = lineage_chain_digest_fn
        self._audit = audit_writer
        self._outbound: List[FederatedMutationProposal] = []
        self._inbound: List[Dict[str, Any]] = []
        self._accepted: List[AcceptedFederatedMutation] = []
        self._quarantined: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Source-side: package and enqueue a local GovernanceGate-approved mutation
    # ------------------------------------------------------------------

    def propose_federated_mutation(
        self,
        *,
        source_epoch_id: str,
        source_mutation_id: str,
        destination_repo: str,
        mutation_payload: Dict[str, Any],
        gate_decision_payload: Dict[str, Any],
    ) -> FederatedMutationProposal:
        """Package a locally-approved mutation for cross-repo propagation.

        This method does **not** re-evaluate the GovernanceGate — it packages an
        *already-approved* gate decision.  The caller is responsible for ensuring
        ``gate_decision_payload["approved"]`` is ``True`` before calling this.

        Invariant
        ---------
        - ``gate_decision_payload["approved"]`` must be ``True``; raises if not.
        - ``source_chain_digest`` is captured at call time from
          ``lineage_chain_digest_fn()``.
        - A ``federation_gate_id`` is minted as a stable hash of the key inputs
          for idempotent replay.
        """
        if not gate_decision_payload.get("approved"):
            raise FederationMutationBrokerError(
                "federation_broker:source_gate_not_approved — "
                "only mutations approved by the source GovernanceGate may be propagated"
            )

        chain_digest = str(self._chain_digest_fn() or "sha256:" + "0" * 64)

        # Stable deterministic gate ID — same inputs always produce same ID
        gate_material = "|".join([
            self._local_repo, source_epoch_id, source_mutation_id, destination_repo,
        ])
        federation_gate_id = "fgate-" + hashlib.sha256(
            gate_material.encode("utf-8")
        ).hexdigest()[:16]

        proposal_id = str(uuid.UUID(
            hashlib.sha256(
                (federation_gate_id + source_mutation_id).encode("utf-8")
            ).hexdigest()[:32]
        ))

        proposal = FederatedMutationProposal(
            proposal_id=proposal_id,
            source_repo=self._local_repo,
            source_epoch_id=source_epoch_id,
            source_mutation_id=source_mutation_id,
            source_chain_digest=chain_digest,
            destination_repo=destination_repo,
            mutation_payload=mutation_payload,
            gate_decision_payload=gate_decision_payload,
            federation_gate_id=federation_gate_id,
        )

        self._outbound.append(proposal)
        self._emit_audit("federation_mutation_proposed", {
            "proposal_id": proposal.proposal_id,
            "source_mutation_id": source_mutation_id,
            "destination_repo": destination_repo,
            "federation_gate_id": federation_gate_id,
            "source_chain_digest": chain_digest,
        })
        log.info(
            "FederationMutationBroker: proposed mutation=%s → %s (gate=%s)",
            source_mutation_id, destination_repo, federation_gate_id,
        )
        return proposal

    # ------------------------------------------------------------------
    # Destination-side: evaluate inbound proposals through local GovernanceGate
    # ------------------------------------------------------------------

    def receive_proposal(self, envelope: Dict[str, Any]) -> None:
        """Buffer an inbound proposal envelope for evaluation.

        The envelope must be a ``FederatedMutationProposal.to_dict()``-compatible
        payload.  Structural validation is performed immediately; malformed
        envelopes are quarantined with an audit event.
        """
        try:
            FederatedMutationProposal.from_dict(envelope)
        except FederationProposalValidationError as exc:
            log.warning("FederationMutationBroker: quarantined malformed inbound proposal — %s", exc)
            self._quarantine(envelope, reason=str(exc))
            return
        self._inbound.append(envelope)

    def evaluate_inbound_proposals(self) -> List[AcceptedFederatedMutation]:
        """Drain and evaluate all buffered inbound proposals.

        Each proposal is run through the *destination* ``GovernanceGate``
        (constitutional dual-gate requirement).  Approved proposals are appended
        to ``_accepted``; rejected proposals are quarantined.

        Returns
        -------
        list[AcceptedFederatedMutation]
            The newly accepted proposals from this evaluation pass.
        """
        newly_accepted: List[AcceptedFederatedMutation] = []
        pending = self._inbound.copy()
        self._inbound.clear()

        for envelope in pending:
            try:
                proposal = FederatedMutationProposal.from_dict(envelope)
            except FederationProposalValidationError as exc:
                self._quarantine(envelope, reason=str(exc))
                continue

            # Dual-gate: run the destination GovernanceGate
            try:
                gate_decision = self._gate.approve_mutation(
                    mutation_id=proposal.source_mutation_id,
                    mutation_payload=proposal.mutation_payload,
                    mutation_context={"federation_source": proposal.source_repo},
                )
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "FederationMutationBroker: destination gate raised for proposal=%s — %s",
                    proposal.proposal_id, exc,
                )
                self._quarantine(envelope, reason=f"destination_gate_raised:{exc}")
                continue

            dest_payload = gate_decision.to_payload() if hasattr(gate_decision, "to_payload") else dict(gate_decision)
            if not dest_payload.get("approved"):
                reason = "destination_gate_rejected:" + str(dest_payload.get("decision", ""))
                log.warning(
                    "FederationMutationBroker: destination gate rejected proposal=%s reason=%s",
                    proposal.proposal_id, reason,
                )
                self._quarantine(envelope, reason=reason)
                self._emit_audit("federation_mutation_destination_rejected", {
                    "proposal_id": proposal.proposal_id,
                    "source_mutation_id": proposal.source_mutation_id,
                    "source_repo": proposal.source_repo,
                    "reason": reason,
                })
                continue

            # Both gates approved — compute acceptance digest
            acceptance_material = proposal.digest() + dest_payload.get("decision_id", "")
            acceptance_digest = "sha256:" + hashlib.sha256(
                acceptance_material.encode("utf-8")
            ).hexdigest()

            accepted = AcceptedFederatedMutation(
                proposal=proposal,
                destination_gate_decision_payload=dest_payload,
                acceptance_digest=acceptance_digest,
            )
            self._accepted.append(accepted)
            newly_accepted.append(accepted)

            self._emit_audit("federation_mutation_accepted", {
                "proposal_id": proposal.proposal_id,
                "source_mutation_id": proposal.source_mutation_id,
                "source_repo": proposal.source_repo,
                "acceptance_digest": acceptance_digest,
                "federation_gate_id": proposal.federation_gate_id,
            })
            log.info(
                "FederationMutationBroker: ACCEPTED proposal=%s from %s (digest=%s)",
                proposal.proposal_id, proposal.source_repo, acceptance_digest[:20],
            )

        return newly_accepted

    # ------------------------------------------------------------------
    # Read-only state accessors
    # ------------------------------------------------------------------

    def pending_outbound(self) -> List[FederatedMutationProposal]:
        """Return a snapshot of outbound proposals not yet dispatched."""
        return list(self._outbound)

    def accepted_proposals(self) -> List[AcceptedFederatedMutation]:
        """Return the full accepted mutation log (append-only view)."""
        return list(self._accepted)

    def quarantined_proposals(self) -> List[Dict[str, Any]]:
        """Return proposals that failed validation or gate evaluation."""
        return list(self._quarantined)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _quarantine(self, envelope: Dict[str, Any], *, reason: str) -> None:
        record = {"envelope": envelope, "reason": reason}
        self._quarantined.append(record)
        self._emit_audit("federation_mutation_quarantined", {
            "proposal_id": envelope.get("proposal_id", "unknown"),
            "reason": reason,
        })

    def _emit_audit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._audit is None:
            return
        try:
            self._audit(event_type, payload)
        except Exception as exc:  # noqa: BLE001 — audit writes are fail-open
            log.warning("FederationMutationBroker: audit write failed (%s) — %s", event_type, exc)


__all__ = [
    "AcceptedFederatedMutation",
    "FederatedMutationProposal",
    "FederationDualGateError",
    "FederationMutationBroker",
    "FederationMutationBrokerError",
    "FederationProposalValidationError",
]
