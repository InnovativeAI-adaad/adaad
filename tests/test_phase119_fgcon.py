# SPDX-License-Identifier: Apache-2.0
"""Phase 119 — INNOV-34 Federation Governance Consensus (FGCON) tests.

T119-FGCON-01..30  (30/30)
pytest mark: phase119
"""
from __future__ import annotations

import hashlib
import hmac
import json
import pytest
from pathlib import Path

from runtime.innovations30.federation_governance_consensus import (
    AmendmentProposal,
    FGCONChainError,
    FGCONGateError,
    FGCONPersistError,
    FGCONQuorumError,
    FGCONUnilateralError,
    FederationGovernanceConsensus,
    FederationMember,
    VoteRecord,
    fgcon_guard,
)

pytestmark = pytest.mark.phase119

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_ledger(tmp_path: Path) -> Path:
    return tmp_path / "fgcon_test.jsonl"


@pytest.fixture()
def engine(tmp_ledger: Path) -> FederationGovernanceConsensus:
    eng = FederationGovernanceConsensus(
        instance_id="instance-alpha",
        ledger_path=tmp_ledger,
    )
    # Register 5 federation members for quorum=3
    for i in range(1, 6):
        eng.register_member(FederationMember(instance_id=f"instance-{i:03d}"))
    return eng


@pytest.fixture()
def proposal(engine: FederationGovernanceConsensus) -> AmendmentProposal:
    return engine.propose_amendment(
        epoch_id="epoch-001",
        amendment_id="amend-no-unilateral",
        amendment_text="No single instance may amend federation invariants.",
        human0_acknowledged=True,
    )


# ── T119-FGCON-01: module imports ─────────────────────────────────────────────

def test_fgcon_01_module_imports() -> None:
    """T119-FGCON-01: all public names importable."""
    assert FederationGovernanceConsensus is not None
    assert AmendmentProposal is not None
    assert FederationMember is not None
    assert VoteRecord is not None


# ── T119-FGCON-02: engine instantiates ───────────────────────────────────────

def test_fgcon_02_engine_instantiates(tmp_ledger: Path) -> None:
    """T119-FGCON-02: engine constructs without error."""
    eng = FederationGovernanceConsensus(
        instance_id="test-instance", ledger_path=tmp_ledger
    )
    assert eng is not None


# ── T119-FGCON-03: member registration ───────────────────────────────────────

def test_fgcon_03_member_registration(tmp_ledger: Path) -> None:
    """T119-FGCON-03: members register and federation_size reflects count."""
    eng = FederationGovernanceConsensus(instance_id="alpha", ledger_path=tmp_ledger)
    assert eng.federation_size() == 0
    eng.register_member(FederationMember(instance_id="node-a"))
    eng.register_member(FederationMember(instance_id="node-b"))
    assert eng.federation_size() == 2


# ── T119-FGCON-04: idempotent registration ───────────────────────────────────

def test_fgcon_04_idempotent_registration(tmp_ledger: Path) -> None:
    """T119-FGCON-04: re-registering the same instance_id does not double-count."""
    eng = FederationGovernanceConsensus(instance_id="alpha", ledger_path=tmp_ledger)
    eng.register_member(FederationMember(instance_id="node-a"))
    eng.register_member(FederationMember(instance_id="node-a"))
    assert eng.federation_size() == 1


# ── T119-FGCON-05: FGCON-QUORUM-0 threshold ──────────────────────────────────

def test_fgcon_05_quorum_threshold(tmp_ledger: Path) -> None:
    """T119-FGCON-05: FGCON-QUORUM-0 — quorum = floor(N/2)+1."""
    eng = FederationGovernanceConsensus(instance_id="alpha", ledger_path=tmp_ledger)
    assert eng.quorum_for_size(1) == 1
    assert eng.quorum_for_size(2) == 2
    assert eng.quorum_for_size(3) == 2
    assert eng.quorum_for_size(5) == 3
    assert eng.quorum_for_size(6) == 4


# ── T119-FGCON-06: FGCON-DETERM-0 proposal_id determinism ────────────────────

def test_fgcon_06_proposal_id_determinism(engine: FederationGovernanceConsensus) -> None:
    """T119-FGCON-06: FGCON-DETERM-0 — identical inputs produce identical proposal_id."""
    p1 = engine.propose_amendment(
        epoch_id="ep-x", amendment_id="amend-x",
        amendment_text="text", human0_acknowledged=True,
    )
    p2 = engine.propose_amendment(
        epoch_id="ep-x", amendment_id="amend-x",
        amendment_text="text", human0_acknowledged=True,
    )
    assert p1.proposal_id == p2.proposal_id


# ── T119-FGCON-07: proposal_id starts with fgcon: ────────────────────────────

def test_fgcon_07_proposal_id_prefix(proposal: AmendmentProposal) -> None:
    """T119-FGCON-07: proposal_id carries fgcon: namespace prefix."""
    assert proposal.proposal_id.startswith("fgcon:")


# ── T119-FGCON-08: initial proposal status is pending ────────────────────────

def test_fgcon_08_initial_status_pending(proposal: AmendmentProposal) -> None:
    """T119-FGCON-08: newly created proposal has status='pending'."""
    assert proposal.status == "pending"


# ── T119-FGCON-09: quorum_required embedded in proposal ──────────────────────

def test_fgcon_09_quorum_in_proposal(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-09: proposal.quorum_required equals floor(N/2)+1 at creation."""
    assert proposal.quorum_required == engine.quorum_for_size(engine.federation_size())


# ── T119-FGCON-10: vote returns VoteRecord ────────────────────────────────────

def test_fgcon_10_vote_returns_record(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-10: vote() returns a VoteRecord instance."""
    rec = engine.vote(proposal.proposal_id, "instance-001", "for")
    assert isinstance(rec, VoteRecord)


# ── T119-FGCON-11: FGCON-PERSIST-0 ledger written ───────────────────────────

def test_fgcon_11_ledger_written(engine: FederationGovernanceConsensus, proposal: AmendmentProposal, tmp_ledger: Path) -> None:
    """T119-FGCON-11: FGCON-PERSIST-0 — ledger file exists and has content after vote."""
    engine.vote(proposal.proposal_id, "instance-001", "for")
    assert tmp_ledger.exists()
    assert tmp_ledger.stat().st_size > 0


# ── T119-FGCON-12: ledger record is valid JSON ───────────────────────────────

def test_fgcon_12_ledger_valid_json(engine: FederationGovernanceConsensus, proposal: AmendmentProposal, tmp_ledger: Path) -> None:
    """T119-FGCON-12: each ledger line is valid JSON with required fields."""
    engine.vote(proposal.proposal_id, "instance-001", "for")
    lines = tmp_ledger.read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert "record_id" in rec
    assert "chain_link" in rec
    assert "proposal_id" in rec


# ── T119-FGCON-13: FGCON-CHAIN-0 chain_link present ─────────────────────────

def test_fgcon_13_chain_link_present(engine: FederationGovernanceConsensus, proposal: AmendmentProposal, tmp_ledger: Path) -> None:
    """T119-FGCON-13: FGCON-CHAIN-0 — chain_link field starts with hmac-sha256:."""
    engine.vote(proposal.proposal_id, "instance-001", "for")
    rec = json.loads(tmp_ledger.read_text().splitlines()[0])
    assert rec["chain_link"].startswith("hmac-sha256:")


# ── T119-FGCON-14: verify_chain_integrity on empty ledger ────────────────────

def test_fgcon_14_chain_integrity_empty(tmp_ledger: Path) -> None:
    """T119-FGCON-14: verify_chain_integrity returns True on empty ledger."""
    eng = FederationGovernanceConsensus(instance_id="alpha", ledger_path=tmp_ledger)
    assert eng.verify_chain_integrity() is True


# ── T119-FGCON-15: verify_chain_integrity after multiple votes ───────────────

def test_fgcon_15_chain_integrity_multi_vote(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-15: chain integrity holds after multiple votes."""
    engine.vote(proposal.proposal_id, "instance-001", "for")
    engine.vote(proposal.proposal_id, "instance-002", "for")
    engine.vote(proposal.proposal_id, "instance-003", "against")
    assert engine.verify_chain_integrity() is True


# ── T119-FGCON-16: FGCON-UNILATERAL-0 duplicate vote blocked ─────────────────

def test_fgcon_16_unilateral_blocked(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-16: FGCON-UNILATERAL-0 — second vote from same instance raises."""
    engine.vote(proposal.proposal_id, "instance-001", "for")
    with pytest.raises(FGCONUnilateralError):
        engine.vote(proposal.proposal_id, "instance-001", "for")


# ── T119-FGCON-17: FGCON-UNILATERAL-0 against→for also blocked ───────────────

def test_fgcon_17_unilateral_flip_blocked(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-17: FGCON-UNILATERAL-0 — vote flip (against→for) also blocked."""
    engine.vote(proposal.proposal_id, "instance-001", "against")
    with pytest.raises(FGCONUnilateralError):
        engine.vote(proposal.proposal_id, "instance-001", "for")


# ── T119-FGCON-18: FGCON-GATE-0 ratify without human0 blocked ────────────────

def test_fgcon_18_gate_blocks_ratify(engine: FederationGovernanceConsensus) -> None:
    """T119-FGCON-18: FGCON-GATE-0 — ratify raises when human0_acknowledged=False."""
    p = engine.propose_amendment(
        epoch_id="ep-gate", amendment_id="amend-gate",
        amendment_text="test gate", human0_acknowledged=False,
    )
    engine.vote(p.proposal_id, "instance-001", "for")
    engine.vote(p.proposal_id, "instance-002", "for")
    engine.vote(p.proposal_id, "instance-003", "for")
    with pytest.raises(FGCONGateError):
        engine.ratify(p.proposal_id)


# ── T119-FGCON-19: FGCON-0 ratify without quorum blocked ─────────────────────

def test_fgcon_19_quorum_blocks_ratify(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-19: FGCON-0 — ratify with insufficient votes raises FGCONQuorumError."""
    # Only 2 votes for, but quorum=3 (5 members)
    engine.vote(proposal.proposal_id, "instance-001", "for")
    engine.vote(proposal.proposal_id, "instance-002", "for")
    with pytest.raises(FGCONQuorumError):
        engine.ratify(proposal.proposal_id)


# ── T119-FGCON-20: successful ratification ───────────────────────────────────

def test_fgcon_20_successful_ratify(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-20: proposal ratified when quorum met and human0_acknowledged."""
    engine.vote(proposal.proposal_id, "instance-001", "for")
    engine.vote(proposal.proposal_id, "instance-002", "for")
    engine.vote(proposal.proposal_id, "instance-003", "for")
    ratified = engine.ratify(proposal.proposal_id)
    assert ratified.status == "ratified"


# ── T119-FGCON-21: no further votes after ratification ───────────────────────

def test_fgcon_21_no_vote_after_ratify(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-21: vote() raises after proposal is ratified."""
    engine.vote(proposal.proposal_id, "instance-001", "for")
    engine.vote(proposal.proposal_id, "instance-002", "for")
    engine.vote(proposal.proposal_id, "instance-003", "for")
    engine.ratify(proposal.proposal_id)
    with pytest.raises(FGCONQuorumError):
        engine.vote(proposal.proposal_id, "instance-004", "for")


# ── T119-FGCON-22: reject sets status to rejected ────────────────────────────

def test_fgcon_22_reject(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-22: reject() sets proposal status to 'rejected'."""
    rejected = engine.reject(proposal.proposal_id)
    assert rejected.status == "rejected"


# ── T119-FGCON-23: get_proposal returns proposal ─────────────────────────────

def test_fgcon_23_get_proposal(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-23: get_proposal returns the correct proposal by ID."""
    retrieved = engine.get_proposal(proposal.proposal_id)
    assert retrieved is not None
    assert retrieved.proposal_id == proposal.proposal_id


# ── T119-FGCON-24: get_proposal unknown returns None ─────────────────────────

def test_fgcon_24_get_proposal_unknown(engine: FederationGovernanceConsensus) -> None:
    """T119-FGCON-24: get_proposal returns None for unknown proposal_id."""
    assert engine.get_proposal("fgcon:nonexistent") is None


# ── T119-FGCON-25: export_state shape ────────────────────────────────────────

def test_fgcon_25_export_state(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-25: export_state returns dict with required keys."""
    state = engine.export_state()
    assert "fgcon_version" in state
    assert "instance_id" in state
    assert "federation_size" in state
    assert "members" in state
    assert "proposals" in state
    assert state["federation_size"] == 5


# ── T119-FGCON-26: vote_value validation ─────────────────────────────────────

def test_fgcon_26_invalid_vote_value(engine: FederationGovernanceConsensus, proposal: AmendmentProposal) -> None:
    """T119-FGCON-26: vote() raises ValueError for invalid vote_value."""
    with pytest.raises(ValueError):
        engine.vote(proposal.proposal_id, "instance-001", "maybe")


# ── T119-FGCON-27: unknown proposal raises KeyError ──────────────────────────

def test_fgcon_27_unknown_proposal_vote(engine: FederationGovernanceConsensus) -> None:
    """T119-FGCON-27: vote() on unknown proposal_id raises KeyError."""
    with pytest.raises(KeyError):
        engine.vote("fgcon:unknown", "instance-001", "for")


# ── T119-FGCON-28: fgcon_guard pass ──────────────────────────────────────────

def test_fgcon_28_guard_pass() -> None:
    """T119-FGCON-28: fgcon_guard does not raise when condition is True."""
    fgcon_guard(True, "FGCON-0", "should not raise")


# ── T119-FGCON-29: fgcon_guard fail ──────────────────────────────────────────

def test_fgcon_29_guard_fail() -> None:
    """T119-FGCON-29: fgcon_guard raises FGCONQuorumError when condition is False."""
    with pytest.raises(FGCONQuorumError, match=r"\[FGCON-TEST\]"):
        fgcon_guard(False, "FGCON-TEST", "expected failure")


# ── T119-FGCON-30: proposal to_dict round-trip ───────────────────────────────

def test_fgcon_30_proposal_to_dict(proposal: AmendmentProposal) -> None:
    """T119-FGCON-30: AmendmentProposal.to_dict() produces JSON-serialisable dict."""
    d = proposal.to_dict()
    serialised = json.dumps(d)
    restored = json.loads(serialised)
    assert restored["proposal_id"] == proposal.proposal_id
    assert restored["quorum_required"] == proposal.quorum_required
    assert restored["status"] == "pending"
