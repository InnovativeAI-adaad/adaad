# SPDX-License-Identifier: Apache-2.0
"""Phase 50 — Federation Consensus wired to mutation broker + EvolutionLoop

PR-50-01  FederationConsensusEngine wired into FederationMutationBroker
PR-50-02  EvolutionFederationBridge wired into EvolutionLoop.run_epoch()

Tests:
  PR-50-01-A  FederationMutationBroker accepts consensus_engine kwarg
  PR-50-01-B  Accepted mutation triggers consensus_engine.append_entry()
  PR-50-01-C  consensus_engine=None is backwards-compatible (no crash)
  PR-50-01-D  Consensus engine failure is exception-isolated (mutation still accepted)
  PR-50-01-E  append_entry payload contains proposal_id + acceptance_digest
  PR-50-02-A  EvolutionLoop accepts federation_bridge kwarg
  PR-50-02-B  run_epoch() calls on_epoch_rotation() with epoch_id + chain_digest
  PR-50-02-C  run_epoch() calls on_inbound_evaluation() with epoch_id
  PR-50-02-D  EpochResult carries federation_outbound_proposed field
  PR-50-02-E  EpochResult carries federation_inbound_accepted + quarantined fields
  PR-50-02-F  federation_bridge=None is backwards-compatible (defaults 0)
  PR-50-02-G  federation_bridge failure is exception-isolated (epoch still returns)
  Schema     EpochResult has all three federation fields
"""
from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock, call, patch

import pytest

from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.evolution.evolution_loop import EvolutionLoop, EpochResult
from runtime.governance.federation.consensus import FederationConsensusEngine
from runtime.governance.federation.evolution_federation_bridge import (
    BridgeResult,
    EvolutionFederationBridge,
)
from runtime.governance.federation.mutation_broker import FederationMutationBroker


pytestmark = pytest.mark.autonomous_critical

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gate(approved: bool = True):
    gate = MagicMock()
    decision = MagicMock()
    decision.to_payload.return_value = {"approved": approved, "decision": "approved", "decision_id": "d1"}
    gate.approve_mutation.return_value = decision
    return gate


def _make_broker(consensus_engine=None, approved: bool = True):
    return FederationMutationBroker(
        local_repo="repo-a",
        governance_gate=_make_gate(approved),
        lineage_chain_digest_fn=lambda: "sha256:" + "a" * 64,
        consensus_engine=consensus_engine,
    )


def _make_context(epoch_id: str = "epoch-ph50") -> CodebaseContext:
    return CodebaseContext(
        file_summaries={}, recent_failures=[],
        current_epoch_id=epoch_id, explore_ratio=0.5,
    )


def _make_loop(**kwargs) -> EvolutionLoop:
    return EvolutionLoop(api_key="test-key", simulate_outcomes=True, **kwargs)


def _stub_bridge_result(hook: str = "on_epoch_rotation", outbound: int = 1, inbound_accepted: int = 0, inbound_q: int = 0) -> BridgeResult:
    return BridgeResult(
        hook=hook, epoch_id="epoch-ph50", ok=True,
        outbound_proposed=outbound,
        inbound_accepted=inbound_accepted,
        inbound_quarantined=inbound_q,
    )


# ---------------------------------------------------------------------------
# PR-50-01-A — broker accepts consensus_engine kwarg
# ---------------------------------------------------------------------------

def test_pr50_01_a_broker_accepts_consensus_engine():
    engine = MagicMock(spec=FederationConsensusEngine)
    broker = _make_broker(consensus_engine=engine)
    assert broker._consensus_engine is engine


# ---------------------------------------------------------------------------
# PR-50-01-B — accepted mutation triggers append_entry
# ---------------------------------------------------------------------------

def test_pr50_01_b_accepted_mutation_triggers_append_entry():
    engine = MagicMock(spec=FederationConsensusEngine)
    engine.append_entry.return_value = MagicMock()
    broker = _make_broker(consensus_engine=engine)

    # Buffer and evaluate an inbound proposal
    proposal = broker.propose_federated_mutation(
        source_epoch_id="ep-1", source_mutation_id="mut-1",
        destination_repo="repo-b",
        mutation_payload={"type": "patch"},
        gate_decision_payload={"approved": True, "decision_id": "src-gate"},
    )
    broker.receive_proposal(proposal.to_dict())
    broker.evaluate_inbound_proposals()

    engine.append_entry.assert_called_once()
    _, kwargs = engine.append_entry.call_args
    assert kwargs["entry_type"] == "federation_mutation_accepted"


# ---------------------------------------------------------------------------
# PR-50-01-C — consensus_engine=None is backwards-compatible
# ---------------------------------------------------------------------------

def test_pr50_01_c_none_consensus_engine_backwards_compatible():
    broker = _make_broker(consensus_engine=None)
    proposal = broker.propose_federated_mutation(
        source_epoch_id="ep-1", source_mutation_id="mut-2",
        destination_repo="repo-b",
        mutation_payload={"type": "patch"},
        gate_decision_payload={"approved": True, "decision_id": "sg"},
    )
    broker.receive_proposal(proposal.to_dict())
    accepted = broker.evaluate_inbound_proposals()
    assert len(accepted) == 1  # accepted without consensus, no crash


# ---------------------------------------------------------------------------
# PR-50-01-D — consensus failure is exception-isolated
# ---------------------------------------------------------------------------

def test_pr50_01_d_consensus_failure_exception_isolated():
    engine = MagicMock(spec=FederationConsensusEngine)
    engine.append_entry.side_effect = RuntimeError("consensus exploded")
    broker = _make_broker(consensus_engine=engine)

    proposal = broker.propose_federated_mutation(
        source_epoch_id="ep-1", source_mutation_id="mut-3",
        destination_repo="repo-b",
        mutation_payload={"type": "patch"},
        gate_decision_payload={"approved": True, "decision_id": "sg"},
    )
    broker.receive_proposal(proposal.to_dict())
    accepted = broker.evaluate_inbound_proposals()  # must not raise
    assert len(accepted) == 1  # mutation still accepted despite consensus failure


# ---------------------------------------------------------------------------
# PR-50-01-E — append_entry payload contains key fields
# ---------------------------------------------------------------------------

def test_pr50_01_e_append_entry_payload_fields():
    engine = MagicMock(spec=FederationConsensusEngine)
    engine.append_entry.return_value = MagicMock()
    broker = _make_broker(consensus_engine=engine)

    proposal = broker.propose_federated_mutation(
        source_epoch_id="ep-1", source_mutation_id="mut-4",
        destination_repo="repo-b",
        mutation_payload={"type": "patch"},
        gate_decision_payload={"approved": True, "decision_id": "sg"},
    )
    broker.receive_proposal(proposal.to_dict())
    broker.evaluate_inbound_proposals()

    payload = engine.append_entry.call_args.kwargs["payload"]
    assert "proposal_id" in payload
    assert "acceptance_digest" in payload
    assert payload["acceptance_digest"].startswith("sha256:")


# ---------------------------------------------------------------------------
# PR-50-02-A — EvolutionLoop accepts federation_bridge kwarg
# ---------------------------------------------------------------------------

def test_pr50_02_a_evolution_loop_accepts_federation_bridge():
    bridge = MagicMock(spec=EvolutionFederationBridge)
    loop = _make_loop(federation_bridge=bridge)
    assert loop._federation_bridge is bridge


# ---------------------------------------------------------------------------
# PR-50-02-B — run_epoch() calls on_epoch_rotation
# ---------------------------------------------------------------------------

def test_pr50_02_b_run_epoch_calls_on_epoch_rotation(monkeypatch):
    bridge = MagicMock(spec=EvolutionFederationBridge)
    bridge.on_epoch_rotation.return_value = _stub_bridge_result("on_epoch_rotation", outbound=2)
    bridge.on_inbound_evaluation.return_value = _stub_bridge_result("on_inbound_evaluation")

    loop = _make_loop(federation_bridge=bridge)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        loop.run_epoch(_make_context())

    bridge.on_epoch_rotation.assert_called_once()
    kwargs = bridge.on_epoch_rotation.call_args.kwargs
    assert kwargs["epoch_id"] == "epoch-ph50"
    assert "chain_digest" in kwargs


# ---------------------------------------------------------------------------
# PR-50-02-C — run_epoch() calls on_inbound_evaluation
# ---------------------------------------------------------------------------

def test_pr50_02_c_run_epoch_calls_on_inbound_evaluation(monkeypatch):
    bridge = MagicMock(spec=EvolutionFederationBridge)
    bridge.on_epoch_rotation.return_value = _stub_bridge_result("on_epoch_rotation")
    bridge.on_inbound_evaluation.return_value = _stub_bridge_result("on_inbound_evaluation", inbound_accepted=3)

    loop = _make_loop(federation_bridge=bridge)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        loop.run_epoch(_make_context())

    bridge.on_inbound_evaluation.assert_called_once()
    assert bridge.on_inbound_evaluation.call_args.kwargs["epoch_id"] == "epoch-ph50"


# ---------------------------------------------------------------------------
# PR-50-02-D — EpochResult carries federation_outbound_proposed
# ---------------------------------------------------------------------------

def test_pr50_02_d_epoch_result_outbound_proposed(monkeypatch):
    bridge = MagicMock(spec=EvolutionFederationBridge)
    bridge.on_epoch_rotation.return_value = _stub_bridge_result("on_epoch_rotation", outbound=5)
    bridge.on_inbound_evaluation.return_value = _stub_bridge_result("on_inbound_evaluation")

    loop = _make_loop(federation_bridge=bridge)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        result = loop.run_epoch(_make_context())

    assert result.federation_outbound_proposed == 5


# ---------------------------------------------------------------------------
# PR-50-02-E — EpochResult carries inbound_accepted + quarantined
# ---------------------------------------------------------------------------

def test_pr50_02_e_epoch_result_inbound_fields(monkeypatch):
    bridge = MagicMock(spec=EvolutionFederationBridge)
    bridge.on_epoch_rotation.return_value = _stub_bridge_result("on_epoch_rotation")
    bridge.on_inbound_evaluation.return_value = _stub_bridge_result(
        "on_inbound_evaluation", inbound_accepted=4, inbound_q=2
    )

    loop = _make_loop(federation_bridge=bridge)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        result = loop.run_epoch(_make_context())

    assert result.federation_inbound_accepted == 4
    assert result.federation_inbound_quarantined == 2


# ---------------------------------------------------------------------------
# PR-50-02-F — federation_bridge=None backwards-compatible (defaults 0)
# ---------------------------------------------------------------------------

def test_pr50_02_f_none_bridge_backwards_compatible(monkeypatch):
    loop = _make_loop(federation_bridge=None)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        result = loop.run_epoch(_make_context())

    assert result.federation_outbound_proposed == 0
    assert result.federation_inbound_accepted == 0
    assert result.federation_inbound_quarantined == 0


# ---------------------------------------------------------------------------
# PR-50-02-G — bridge failure is exception-isolated
# ---------------------------------------------------------------------------

def test_pr50_02_g_bridge_failure_exception_isolated(monkeypatch):
    bridge = MagicMock(spec=EvolutionFederationBridge)
    bridge.on_epoch_rotation.side_effect = RuntimeError("federation exploded")
    bridge.on_inbound_evaluation.side_effect = RuntimeError("also exploded")

    loop = _make_loop(federation_bridge=bridge)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        result = loop.run_epoch(_make_context())  # must not raise

    assert result.federation_outbound_proposed == 0


# ---------------------------------------------------------------------------
# Schema — EpochResult has all three federation fields
# ---------------------------------------------------------------------------

def test_schema_epoch_result_has_federation_fields():
    fields = {f.name for f in dataclasses.fields(EpochResult)}
    for expected in ["federation_outbound_proposed", "federation_inbound_accepted", "federation_inbound_quarantined"]:
        assert expected in fields, f"EpochResult missing: {expected}"
