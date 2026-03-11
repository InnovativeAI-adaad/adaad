# SPDX-License-Identifier: Apache-2.0
"""Tests for FederationMutationBroker — Phase 5 governed mutation propagation.

Invariants under test
---------------------
- propose_federated_mutation() requires gate_decision_payload["approved"]=True.
- propose_federated_mutation() captures chain_digest from the digest_fn.
- Proposal IDs are stable / deterministic for identical inputs.
- receive_proposal() quarantines malformed envelopes immediately.
- evaluate_inbound_proposals() runs destination GovernanceGate (dual-gate).
- Approved proposals are recorded in accepted_proposals(); rejected are quarantined.
- Audit events are emitted for proposed / accepted / rejected / quarantined.
- Audit write failures never block broker decisions (fail-open on audit).
- to_federation_origin() returns a correct FederationOrigin instance.
- Broker state is append-only (accepted list never shrinks).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.federation.mutation_broker import (
    AcceptedFederatedMutation,
    FederatedMutationProposal,
    FederationMutationBroker,
    FederationMutationBrokerError,
    FederationProposalValidationError,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

_LOCAL_REPO = "InnovativeAI-adaad/ADAAD"
_DEST_REPO = "InnovativeAI-adaad/ADAAD-payments"
_CHAIN_DIGEST = "sha256:" + "a" * 64
_APPROVED_GATE_DECISION = {
    "approved": True,
    "decision": "approved",
    "decision_id": "gate-001",
    "mutation_id": "mut-001",
    "trust_mode": "full",
    "reason_codes": [],
    "failed_rules": [],
    "axis_results": [],
    "human_override": False,
    "gate_mode": "serial",
}
_REJECTED_GATE_DECISION = {**_APPROVED_GATE_DECISION, "approved": False, "decision": "rejected"}

_MUTATION_PAYLOAD = {"diff": "print('hello')", "strategy": "architect"}


@dataclass
class _MockGateDecision:
    approved: bool
    decision_id: str = "dest-gate-001"
    decision: str = "approved"

    def to_payload(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "decision": self.decision,
            "decision_id": self.decision_id,
            "mutation_id": "federated-mut",
            "trust_mode": "federated",
            "reason_codes": [],
            "failed_rules": [],
            "axis_results": [],
            "human_override": False,
            "gate_mode": "serial",
        }


class _ApproveGate:
    def approve_mutation(self, **_kwargs) -> _MockGateDecision:
        return _MockGateDecision(approved=True)


class _RejectGate:
    def approve_mutation(self, **_kwargs) -> _MockGateDecision:
        return _MockGateDecision(approved=False, decision="rejected")


class _RaisingGate:
    def approve_mutation(self, **_kwargs):
        raise RuntimeError("simulated gate crash")


def _make_broker(gate=None, audit=None) -> FederationMutationBroker:
    return FederationMutationBroker(
        local_repo=_LOCAL_REPO,
        governance_gate=gate or _ApproveGate(),
        lineage_chain_digest_fn=lambda: _CHAIN_DIGEST,
        audit_writer=audit,
    )


def _make_valid_envelope(source_mutation_id: str = "mut-001") -> Dict[str, Any]:
    broker = _make_broker()
    proposal = broker.propose_federated_mutation(
        source_epoch_id="epoch-001",
        source_mutation_id=source_mutation_id,
        destination_repo=_DEST_REPO,
        mutation_payload=_MUTATION_PAYLOAD,
        gate_decision_payload=_APPROVED_GATE_DECISION,
    )
    return proposal.to_dict()


# ---------------------------------------------------------------------------
# propose_federated_mutation
# ---------------------------------------------------------------------------


class TestProposeOutbound:
    def test_approved_gate_decision_returns_proposal(self) -> None:
        broker = _make_broker()
        p = broker.propose_federated_mutation(
            source_epoch_id="epoch-001",
            source_mutation_id="mut-001",
            destination_repo=_DEST_REPO,
            mutation_payload=_MUTATION_PAYLOAD,
            gate_decision_payload=_APPROVED_GATE_DECISION,
        )
        assert isinstance(p, FederatedMutationProposal)
        assert p.source_repo == _LOCAL_REPO
        assert p.destination_repo == _DEST_REPO
        assert p.source_mutation_id == "mut-001"

    def test_unapproved_gate_decision_raises(self) -> None:
        broker = _make_broker()
        with pytest.raises(FederationMutationBrokerError, match="source_gate_not_approved"):
            broker.propose_federated_mutation(
                source_epoch_id="epoch-001",
                source_mutation_id="mut-001",
                destination_repo=_DEST_REPO,
                mutation_payload=_MUTATION_PAYLOAD,
                gate_decision_payload=_REJECTED_GATE_DECISION,
            )

    def test_chain_digest_captured_from_fn(self) -> None:
        broker = _make_broker()
        p = broker.propose_federated_mutation(
            source_epoch_id="epoch-001",
            source_mutation_id="mut-001",
            destination_repo=_DEST_REPO,
            mutation_payload=_MUTATION_PAYLOAD,
            gate_decision_payload=_APPROVED_GATE_DECISION,
        )
        assert p.source_chain_digest == _CHAIN_DIGEST

    def test_proposal_id_stable_for_same_inputs(self) -> None:
        """Proposal IDs must be deterministic for identical inputs."""
        broker1 = _make_broker()
        broker2 = _make_broker()
        p1 = broker1.propose_federated_mutation(
            source_epoch_id="epoch-001",
            source_mutation_id="mut-001",
            destination_repo=_DEST_REPO,
            mutation_payload=_MUTATION_PAYLOAD,
            gate_decision_payload=_APPROVED_GATE_DECISION,
        )
        p2 = broker2.propose_federated_mutation(
            source_epoch_id="epoch-001",
            source_mutation_id="mut-001",
            destination_repo=_DEST_REPO,
            mutation_payload=_MUTATION_PAYLOAD,
            gate_decision_payload=_APPROVED_GATE_DECISION,
        )
        assert p1.proposal_id == p2.proposal_id

    def test_different_mutation_ids_produce_different_proposal_ids(self) -> None:
        broker = _make_broker()
        p1 = broker.propose_federated_mutation(
            source_epoch_id="epoch-001",
            source_mutation_id="mut-001",
            destination_repo=_DEST_REPO,
            mutation_payload=_MUTATION_PAYLOAD,
            gate_decision_payload=_APPROVED_GATE_DECISION,
        )
        p2 = broker.propose_federated_mutation(
            source_epoch_id="epoch-001",
            source_mutation_id="mut-002",
            destination_repo=_DEST_REPO,
            mutation_payload=_MUTATION_PAYLOAD,
            gate_decision_payload=_APPROVED_GATE_DECISION,
        )
        assert p1.proposal_id != p2.proposal_id

    def test_proposal_appended_to_pending_outbound(self) -> None:
        broker = _make_broker()
        broker.propose_federated_mutation(
            source_epoch_id="epoch-001",
            source_mutation_id="mut-001",
            destination_repo=_DEST_REPO,
            mutation_payload=_MUTATION_PAYLOAD,
            gate_decision_payload=_APPROVED_GATE_DECISION,
        )
        assert len(broker.pending_outbound()) == 1

    def test_audit_emitted_on_propose(self) -> None:
        events: List[str] = []
        broker = _make_broker(audit=lambda et, _p: events.append(et))
        broker.propose_federated_mutation(
            source_epoch_id="epoch-001",
            source_mutation_id="mut-001",
            destination_repo=_DEST_REPO,
            mutation_payload=_MUTATION_PAYLOAD,
            gate_decision_payload=_APPROVED_GATE_DECISION,
        )
        assert "federation_mutation_proposed" in events


# ---------------------------------------------------------------------------
# FederatedMutationProposal serialisation
# ---------------------------------------------------------------------------


class TestProposalSerialisation:
    def test_to_dict_from_dict_roundtrip(self) -> None:
        envelope = _make_valid_envelope()
        proposal = FederatedMutationProposal.from_dict(envelope)
        assert proposal.to_dict() == envelope

    def test_from_dict_missing_field_raises(self) -> None:
        envelope = _make_valid_envelope()
        del envelope["source_chain_digest"]
        with pytest.raises(FederationProposalValidationError, match="source_chain_digest"):
            FederatedMutationProposal.from_dict(envelope)

    def test_digest_is_deterministic(self) -> None:
        e1 = _make_valid_envelope()
        e2 = _make_valid_envelope()
        p1 = FederatedMutationProposal.from_dict(e1)
        p2 = FederatedMutationProposal.from_dict(e2)
        assert p1.digest() == p2.digest()

    def test_digest_changes_with_different_content(self) -> None:
        e1 = _make_valid_envelope("mut-001")
        e2 = _make_valid_envelope("mut-002")
        p1 = FederatedMutationProposal.from_dict(e1)
        p2 = FederatedMutationProposal.from_dict(e2)
        assert p1.digest() != p2.digest()


# ---------------------------------------------------------------------------
# receive_proposal — inbound buffering
# ---------------------------------------------------------------------------


class TestReceiveProposal:
    def test_valid_envelope_buffered(self) -> None:
        broker = _make_broker()
        broker.receive_proposal(_make_valid_envelope())
        # Buffered but not yet accepted — evaluate to accept
        assert len(broker.quarantined_proposals()) == 0

    def test_malformed_envelope_quarantined(self) -> None:
        broker = _make_broker()
        broker.receive_proposal({"garbage": True})
        assert len(broker.quarantined_proposals()) == 1

    def test_missing_field_quarantined(self) -> None:
        broker = _make_broker()
        envelope = _make_valid_envelope()
        del envelope["destination_repo"]
        broker.receive_proposal(envelope)
        assert len(broker.quarantined_proposals()) == 1


# ---------------------------------------------------------------------------
# evaluate_inbound_proposals — dual-gate
# ---------------------------------------------------------------------------


class TestEvaluateInbound:
    def test_approved_by_destination_gate_is_accepted(self) -> None:
        broker = _make_broker(gate=_ApproveGate())
        broker.receive_proposal(_make_valid_envelope())
        accepted = broker.evaluate_inbound_proposals()
        assert len(accepted) == 1
        assert len(broker.accepted_proposals()) == 1

    def test_rejected_by_destination_gate_is_quarantined(self) -> None:
        broker = _make_broker(gate=_RejectGate())
        broker.receive_proposal(_make_valid_envelope())
        accepted = broker.evaluate_inbound_proposals()
        assert len(accepted) == 0
        assert len(broker.quarantined_proposals()) == 1

    def test_raising_gate_quarantines_and_does_not_raise(self) -> None:
        broker = _make_broker(gate=_RaisingGate())
        broker.receive_proposal(_make_valid_envelope())
        accepted = broker.evaluate_inbound_proposals()
        assert len(accepted) == 0
        assert len(broker.quarantined_proposals()) == 1

    def test_acceptance_digest_is_present(self) -> None:
        broker = _make_broker(gate=_ApproveGate())
        broker.receive_proposal(_make_valid_envelope())
        accepted = broker.evaluate_inbound_proposals()
        assert accepted[0].acceptance_digest.startswith("sha256:")

    def test_inbound_buffer_drained_after_evaluate(self) -> None:
        broker = _make_broker()
        broker.receive_proposal(_make_valid_envelope())
        broker.evaluate_inbound_proposals()
        # Second call should return nothing
        accepted = broker.evaluate_inbound_proposals()
        assert len(accepted) == 0

    def test_audit_emitted_on_accept(self) -> None:
        events: List[str] = []
        broker = _make_broker(gate=_ApproveGate(), audit=lambda et, _p: events.append(et))
        broker.receive_proposal(_make_valid_envelope())
        broker.evaluate_inbound_proposals()
        assert "federation_mutation_accepted" in events

    def test_audit_emitted_on_destination_reject(self) -> None:
        events: List[str] = []
        broker = _make_broker(gate=_RejectGate(), audit=lambda et, _p: events.append(et))
        broker.receive_proposal(_make_valid_envelope())
        broker.evaluate_inbound_proposals()
        assert "federation_mutation_destination_rejected" in events

    def test_audit_failure_does_not_block_acceptance(self) -> None:
        def bad_audit(et, p):
            raise OSError("disk full")

        broker = _make_broker(gate=_ApproveGate(), audit=bad_audit)
        broker.receive_proposal(_make_valid_envelope())
        # Must not raise
        accepted = broker.evaluate_inbound_proposals()
        assert len(accepted) == 1


# ---------------------------------------------------------------------------
# to_federation_origin integration
# ---------------------------------------------------------------------------


class TestToFederationOrigin:
    def test_returns_correct_federation_origin(self) -> None:
        from runtime.evolution.lineage_v2 import FederationOrigin

        broker = _make_broker(gate=_ApproveGate())
        broker.receive_proposal(_make_valid_envelope())
        accepted = broker.evaluate_inbound_proposals()
        origin = accepted[0].proposal.to_federation_origin()
        assert isinstance(origin, FederationOrigin)
        assert origin.source_repo == _LOCAL_REPO
        assert origin.source_chain_digest == _CHAIN_DIGEST


# ---------------------------------------------------------------------------
# propagate_amendment — Phase 6 M6-04
# ---------------------------------------------------------------------------


def test_propagate_amendment_emits_contract_payload_and_applies_all() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    broker = _make_broker(audit=lambda et, payload: events.append((et, payload)))

    destinations = [{"node_id": "peer-b"}, {"node_id": "peer-a"}]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            broker,
            "_default_destination_gate_evaluator",
            lambda *_args, **_kwargs: {"approved": True, "decision_id": "dest-1", "decision": "approved"},
        )

        payload = broker.propagate_amendment(
            proposal_id="proposal-001",
            source_node="source-node",
            destination_nodes=destinations,
            mutation_payload={"mutation_id": "roadmap-001", "change": "delta"},
            source_gate_decision_payload={"approved": True, "decision_id": "src-1"},
            propagation_timestamp="2026-03-06T10:00:00Z",
            evidence_bundle_hash="sha256:" + "b" * 64,
            federation_hmac_key_path=__file__,
        )

    assert payload == {
        "proposal_id": "proposal-001",
        "source_node": "source-node",
        "destination_nodes": ["peer-a", "peer-b"],
        "propagation_timestamp": "2026-03-06T10:00:00Z",
        "evidence_bundle_hash": "sha256:" + "b" * 64,
    }
    assert destinations[0]["applied_mutations"]
    assert destinations[1]["applied_mutations"]
    assert ("federated_amendment_propagated", payload) in events


def test_propagate_amendment_fail_closed_when_hmac_key_missing() -> None:
    broker = _make_broker()
    with pytest.raises(FederationMutationBrokerError, match="federation_hmac_required"):
        broker.propagate_amendment(
            proposal_id="proposal-002",
            source_node="source-node",
            destination_nodes=[{"node_id": "peer-a"}],
            mutation_payload={"mutation_id": "roadmap-002"},
            source_gate_decision_payload={"approved": True},
            propagation_timestamp="2026-03-06T10:01:00Z",
            evidence_bundle_hash="sha256:" + "c" * 64,
            federation_hmac_key_path="",
        )


def test_propagate_amendment_rejects_invalid_authority_level() -> None:
    broker = _make_broker()
    with pytest.raises(FederationMutationBrokerError, match="PHASE6_FEDERATED_AUTHORITY_VIOLATION"):
        broker.propagate_amendment(
            proposal_id="proposal-003",
            source_node="source-node",
            destination_nodes=[{"node_id": "peer-a"}],
            mutation_payload={"mutation_id": "roadmap-003"},
            source_gate_decision_payload={"approved": True},
            propagation_timestamp="2026-03-06T10:02:00Z",
            evidence_bundle_hash="sha256:" + "d" * 64,
            federation_hmac_key_path=__file__,
            authority_level="agent-review",
        )


def test_propagate_amendment_rejects_replay_lineage_inconsistency() -> None:
    broker = _make_broker()
    with pytest.raises(FederationMutationBrokerError, match="PHASE6_FEDERATED_REPLAY_LINEAGE_INCONSISTENT"):
        broker.propagate_amendment(
            proposal_id="proposal-004",
            source_node="source-node",
            destination_nodes=[{"node_id": "peer-a"}],
            mutation_payload={"mutation_id": "roadmap-004"},
            source_gate_decision_payload={"approved": True},
            propagation_timestamp="2026-03-06T10:03:00Z",
            evidence_bundle_hash="sha256:" + "e" * 64,
            federation_hmac_key_path=__file__,
            replay_lineage_consistent=False,
        )


def test_propagate_amendment_rolls_back_previously_applied_destinations() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    broker = _make_broker(audit=lambda et, payload: events.append((et, payload)))
    destinations = [{"node_id": "peer-a"}, {"node_id": "peer-b"}]

    def fail_second_destination(node: dict[str, Any], mutation_payload: dict[str, Any], destination_gate_payload: dict[str, Any]) -> None:
        if node["node_id"] == "peer-b":
            raise RuntimeError("simulated write failure")
        broker._default_destination_mutation_writer(node, mutation_payload, destination_gate_payload)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            broker,
            "_default_destination_gate_evaluator",
            lambda *_args, **_kwargs: {"approved": True, "decision_id": "dest-1", "decision": "approved"},
        )

        with pytest.raises(FederationMutationBrokerError, match="federated_propagation_rolled_back"):
            broker.propagate_amendment(
                proposal_id="proposal-005",
                source_node="source-node",
                destination_nodes=destinations,
                mutation_payload={"mutation_id": "roadmap-005"},
                source_gate_decision_payload={"approved": True},
                propagation_timestamp="2026-03-06T10:04:00Z",
                evidence_bundle_hash="sha256:" + "f" * 64,
                federation_hmac_key_path=__file__,
                destination_mutation_writer=fail_second_destination,
            )

    assert "applied_mutations" not in destinations[0]
    assert "applied_mutations" not in destinations[1]
    rollback_event = [entry for entry in events if entry[0] == "federated_amendment_rollback"]
    assert rollback_event


def test_propagate_amendment_destination_gate_remains_independent() -> None:
    broker = _make_broker()
    with pytest.raises(FederationMutationBrokerError, match="federated_propagation_rolled_back"):
        broker.propagate_amendment(
            proposal_id="proposal-006",
            source_node="source-node",
            destination_nodes=[{"node_id": "peer-a"}],
            mutation_payload={"mutation_id": "roadmap-006"},
            source_gate_decision_payload={"approved": True, "decision_id": "source-approved"},
            propagation_timestamp="2026-03-06T10:05:00Z",
            evidence_bundle_hash="sha256:" + "1" * 64,
            federation_hmac_key_path=__file__,
            destination_gate_evaluator=lambda *_args, **_kwargs: {
                "approved": False,
                "decision": "rejected",
                "decision_id": "destination-reject",
            },
        )
