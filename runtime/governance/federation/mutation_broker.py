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
6. **Audit persistence is explicit**: write outcomes are structured and critical events are fail-closed by default.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
from runtime.governance.federation.consensus import FederationConsensusEngine
from pathlib import Path
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


class FederationAuditFailureMode(str, Enum):
    FAIL_OPEN = "fail_open"
    FAIL_CLOSED_CRITICAL = "fail_closed_critical"


@dataclass(frozen=True)
class FederationAuditStatus:
    event_type: str
    ok: bool
    reason: str
    error_type: Optional[str] = None


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
        appending broker events to the evidence ledger.
    audit_failure_mode:
        Audit persistence mode. Critical events are fail-closed by default,
        and may be set to ``"fail_open"`` for test/development ergonomics.
    """

    def __init__(
        self,
        *,
        local_repo: str,
        governance_gate: Any,
        lineage_chain_digest_fn: Any,
        audit_writer: Optional[Any] = None,
        audit_failure_mode: FederationAuditFailureMode = FederationAuditFailureMode.FAIL_CLOSED_CRITICAL,
        consensus_engine: Optional[FederationConsensusEngine] = None,
    ) -> None:
        self._local_repo = local_repo
        self._gate = governance_gate
        self._chain_digest_fn = lineage_chain_digest_fn
        self._audit = audit_writer
        self._audit_failure_mode = FederationAuditFailureMode(audit_failure_mode)
        self._critical_audit_events = {
            "federated_amendment_propagated",
            "federated_amendment_rollback",
            "federation_mutation_quarantined",
            "federation_partition_detected.v1",
        }
        self._last_audit_status: Optional[FederationAuditStatus] = None
        # Phase 50 (PR-50-01): FederationConsensusEngine wired for log replication.
        # When injected, every dual-gate-accepted mutation is appended to the
        # consensus log via append_entry(). None = consensus skipped silently
        # (backwards-compatible for single-node deployments).
        self._consensus_engine: Optional[FederationConsensusEngine] = consensus_engine
        self._outbound: List[FederatedMutationProposal] = []
        self._inbound: List[Dict[str, Any]] = []
        self._accepted: List[AcceptedFederatedMutation] = []
        self._quarantined: List[Dict[str, Any]] = []

    @property
    def last_audit_status(self) -> Optional[FederationAuditStatus]:
        return self._last_audit_status

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
            # Phase 50 (PR-50-01): replicate acceptance into consensus log.
            # Exception-isolated — consensus failure never quarantines an already
            # dual-gate-approved mutation. GovernanceGate retains execution authority.
            if self._consensus_engine is not None:
                try:
                    self._consensus_engine.append_entry(
                        entry_type="federation_mutation_accepted",
                        payload={
                            "proposal_id": proposal.proposal_id,
                            "source_mutation_id": proposal.source_mutation_id,
                            "source_repo": proposal.source_repo,
                            "acceptance_digest": acceptance_digest,
                            "federation_gate_id": proposal.federation_gate_id,
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass  # consensus failure must never revoke an accepted mutation
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

    def propagate_amendment(
        self,
        *,
        proposal_id: str,
        source_node: str,
        destination_nodes: List[Any],
        mutation_payload: Dict[str, Any],
        source_gate_decision_payload: Dict[str, Any],
        propagation_timestamp: str,
        evidence_bundle_hash: str,
        federation_hmac_key_path: str,
        authority_level: str = "governor-review",
        replay_lineage_consistent: bool = True,
        destination_mutation_writer: Optional[Any] = None,
        destination_state_reader: Optional[Any] = None,
        destination_state_writer: Optional[Any] = None,
        destination_gate_evaluator: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Propagate a Phase 6 roadmap amendment to destination nodes atomically.

        Constitutional constraints
        -------------------------
        - **INVARIANT PHASE6-FED-0**: source-node approval is provenance only and
          never binds destination nodes; each destination must evaluate through an
          independent gate decision.
        - **Phase 5 dual-gate invariant (unchanged)**: destination gate approval
          remains mandatory per destination before any mutation write.
        - **``federation_hmac_required`` behavior (unchanged)**: missing/invalid
          federation HMAC key path is a fail-closed hard stop.
        """
        self._validate_federation_hmac_key_path(federation_hmac_key_path)

        if authority_level != "governor-review":
            raise FederationMutationBrokerError("PHASE6_FEDERATED_AUTHORITY_VIOLATION")
        if not replay_lineage_consistent:
            raise FederationMutationBrokerError("PHASE6_FEDERATED_REPLAY_LINEAGE_INCONSISTENT")

        writer = destination_mutation_writer or self._default_destination_mutation_writer
        state_reader = destination_state_reader or self._default_destination_state_reader
        state_writer = destination_state_writer or self._default_destination_state_writer
        gate_evaluator = destination_gate_evaluator or self._default_destination_gate_evaluator

        ordered_destinations = self._ordered_destination_nodes(destination_nodes)
        rollback_entries: List[Dict[str, Any]] = []
        applied_destinations: List[str] = []
        failed_destination_id = "unknown"

        try:
            for destination in ordered_destinations:
                destination_id = self._destination_id(destination)
                failed_destination_id = destination_id
                snapshot = state_reader(destination)

                gate_payload = gate_evaluator(
                    destination,
                    mutation_payload,
                    {
                        "federation_source": source_node,
                        "source_gate_approved": bool(source_gate_decision_payload.get("approved")),
                        "phase6_invariant": "PHASE6-FED-0",
                        "authority_level": authority_level,
                    },
                )
                if not gate_payload.get("approved"):
                    raise FederationDualGateError(
                        f"destination_gate_rejected:{destination_id}:{gate_payload.get('decision', '')}"
                    )

                writer(destination, mutation_payload, gate_payload)
                rollback_entries.append({"destination": destination, "snapshot": snapshot})
                applied_destinations.append(destination_id)
        except Exception as exc:  # noqa: BLE001
            for rollback_entry in reversed(rollback_entries):
                state_writer(rollback_entry["destination"], rollback_entry["snapshot"])

            rollback_payload = {
                "proposal_id": proposal_id,
                "source_node": source_node,
                "failed_destination": failed_destination_id,
                "rolled_back_destinations": sorted(applied_destinations),
            }
            self._emit_audit("federated_amendment_rollback", rollback_payload)
            raise FederationMutationBrokerError(
                f"federated_propagation_rolled_back:{proposal_id}:{exc}"
            ) from exc

        propagation_payload = {
            "proposal_id": proposal_id,
            "source_node": source_node,
            "destination_nodes": [self._destination_id(node) for node in ordered_destinations],
            "propagation_timestamp": propagation_timestamp,
            "evidence_bundle_hash": evidence_bundle_hash,
        }
        self._emit_audit("federated_amendment_propagated", propagation_payload)
        return propagation_payload

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

    def _emit_audit(self, event_type: str, payload: Dict[str, Any]) -> FederationAuditStatus:
        if self._audit is None:
            self._last_audit_status = FederationAuditStatus(
                event_type=event_type,
                ok=True,
                reason="audit_writer_not_configured",
            )
            return self._last_audit_status

        try:
            self._audit(event_type, payload)
            self._last_audit_status = FederationAuditStatus(
                event_type=event_type,
                ok=True,
                reason="persisted",
            )
            return self._last_audit_status
        except Exception as exc:  # noqa: BLE001
            self._last_audit_status = FederationAuditStatus(
                event_type=event_type,
                ok=False,
                reason="audit_persistence_failed",
                error_type=exc.__class__.__name__,
            )
            fail_closed_triggered = (
                self._audit_failure_mode == FederationAuditFailureMode.FAIL_CLOSED_CRITICAL
                and event_type in self._critical_audit_events
            )
            log.error(
                "federation_audit_write_failed event_type=%s reason=%s error_type=%s error=%s mode=%s fail_closed=%s payload=%s",
                event_type,
                self._last_audit_status.reason,
                self._last_audit_status.error_type,
                str(exc),
                self._audit_failure_mode.value,
                fail_closed_triggered,
                payload,
            )
            if fail_closed_triggered:
                raise FederationMutationBrokerError(
                    f"audit_persistence_failed:{event_type}:{exc.__class__.__name__}:{exc}"
                ) from exc
            return self._last_audit_status

    def _validate_federation_hmac_key_path(self, federation_hmac_key_path: str) -> None:
        key_path = Path(federation_hmac_key_path) if federation_hmac_key_path else None
        if key_path is None or not key_path.is_file():
            raise FederationMutationBrokerError("federation_hmac_required")

    def _ordered_destination_nodes(self, destination_nodes: List[Any]) -> List[Any]:
        return sorted(destination_nodes, key=self._destination_id)

    def _destination_id(self, destination_node: Any) -> str:
        if isinstance(destination_node, str):
            return destination_node
        if isinstance(destination_node, dict):
            return str(destination_node.get("node_id", destination_node.get("id", "unknown")))
        return str(getattr(destination_node, "node_id", getattr(destination_node, "id", "unknown")))

    def _default_destination_gate_evaluator(
        self,
        destination_node: Any,
        mutation_payload: Dict[str, Any],
        mutation_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        gate_decision = self._gate.approve_mutation(
            mutation_id=mutation_payload.get("mutation_id", "federated-amendment"),
            mutation_payload=mutation_payload,
            mutation_context={**mutation_context, "destination_node": self._destination_id(destination_node)},
        )
        return gate_decision.to_payload() if hasattr(gate_decision, "to_payload") else dict(gate_decision)

    def _default_destination_state_reader(self, destination_node: Any) -> Any:
        return deepcopy(destination_node)

    def _default_destination_state_writer(self, destination_node: Any, snapshot: Any) -> None:
        if isinstance(destination_node, dict) and isinstance(snapshot, dict):
            destination_node.clear()
            destination_node.update(snapshot)
            return
        if isinstance(destination_node, list) and isinstance(snapshot, list):
            destination_node[:] = snapshot
            return
        if hasattr(destination_node, "__dict__") and hasattr(snapshot, "__dict__"):
            destination_node.__dict__.clear()
            destination_node.__dict__.update(snapshot.__dict__)
            return
        raise FederationMutationBrokerError("destination_state_restore_unsupported")

    def _default_destination_mutation_writer(
        self,
        destination_node: Any,
        mutation_payload: Dict[str, Any],
        destination_gate_payload: Dict[str, Any],
    ) -> None:
        if isinstance(destination_node, dict):
            applied = destination_node.setdefault("applied_mutations", [])
            applied.append(
                {
                    "mutation": mutation_payload,
                    "destination_gate_decision_id": destination_gate_payload.get("decision_id", ""),
                }
            )
            return
        if hasattr(destination_node, "apply_federated_mutation"):
            destination_node.apply_federated_mutation(
                mutation_payload=mutation_payload,
                destination_gate_payload=destination_gate_payload,
            )
            return
        raise FederationMutationBrokerError("destination_mutation_writer_required")


__all__ = [
    "AcceptedFederatedMutation",
    "FederatedMutationProposal",
    "FederationAuditFailureMode",
    "FederationAuditStatus",
    "FederationDualGateError",
    "FederationMutationBroker",
    "FederationMutationBrokerError",
    "FederationProposalValidationError",
]
