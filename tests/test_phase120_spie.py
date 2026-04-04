# SPDX-License-Identifier: Apache-2.0
"""Phase 120 — INNOV-35 Self-Proposing Innovation Engine (SPIE) tests.

T120-SPIE-01..30  (30/30)
pytest mark: phase120
"""
from __future__ import annotations

import hashlib
import json
import pytest
from pathlib import Path

from runtime.innovations30.self_proposing_innovation_engine import (
    ConstitutionalGapSignal,
    FailureSignal,
    InnovationProposal,
    MirrorAccuracySignal,
    SelfProposingInnovationEngine,
    SPIEDuplicateError,
    SPIEPersistError,
    SPIERatifyError,
    SPIESourceError,
    SPIEViolation,
    SPIE_INVARIANTS,
    VALID_SIGNAL_SOURCES,
    spie_guard,
)

pytestmark = pytest.mark.phase120

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_ledger(tmp_path: Path) -> Path:
    return tmp_path / "spie_test.jsonl"


@pytest.fixture()
def engine(tmp_ledger: Path) -> SelfProposingInnovationEngine:
    return SelfProposingInnovationEngine(
        instance_id="test-instance-spie",
        ledger_path=tmp_ledger,
    )


@pytest.fixture()
def failure_sig() -> FailureSignal:
    return FailureSignal(
        pattern="entropy_budget_exceeded_on_large_diff",
        frequency=12,
        affected_module="runtime/evolution/entropy.py",
        example_mutation_id="mut-epoch9-0042",
    )


@pytest.fixture()
def gap_sig() -> ConstitutionalGapSignal:
    return ConstitutionalGapSignal(
        category="federation",
        current_count=3,
        min_expected=7,
        gap_score=round((7 - 3) / 7, 4),
    )


@pytest.fixture()
def mirror_sig() -> MirrorAccuracySignal:
    return MirrorAccuracySignal(
        epoch_id="epoch-042",
        accuracy_current=0.71,
        accuracy_baseline=0.88,
        decay_delta=0.17,
        affected_dimension="mutation_intent",
    )


@pytest.fixture()
def proposal_from_failure(
    engine: SelfProposingInnovationEngine,
    failure_sig: FailureSignal,
) -> InnovationProposal:
    return engine.propose("epoch-001", failure=failure_sig)


# ── T120-SPIE-01: module imports ──────────────────────────────────────────────

def test_spie_01_imports() -> None:
    """T120-SPIE-01: all public names importable."""
    assert SelfProposingInnovationEngine is not None
    assert InnovationProposal is not None
    assert FailureSignal is not None
    assert ConstitutionalGapSignal is not None
    assert MirrorAccuracySignal is not None


# ── T120-SPIE-02: engine instantiation ───────────────────────────────────────

def test_spie_02_instantiation(tmp_ledger: Path) -> None:
    """T120-SPIE-02: engine constructs without error."""
    eng = SelfProposingInnovationEngine(
        instance_id="alpha", ledger_path=tmp_ledger
    )
    assert eng is not None


# ── T120-SPIE-03: invariant registry completeness ────────────────────────────

def test_spie_03_invariant_registry() -> None:
    """T120-SPIE-03: SPIE_INVARIANTS contains all 7 expected invariants."""
    expected = {
        "SPIE-0", "SPIE-DETERM-0", "SPIE-PERSIST-0", "SPIE-CHAIN-0",
        "SPIE-GATE-0", "SPIE-SOURCE-0", "SPIE-HUMAN0-0",
    }
    assert expected == set(SPIE_INVARIANTS.keys())


# ── T120-SPIE-04: valid signal sources set ────────────────────────────────────

def test_spie_04_valid_signal_sources() -> None:
    """T120-SPIE-04: VALID_SIGNAL_SOURCES contains the three expected sources."""
    assert "failure_history" in VALID_SIGNAL_SOURCES
    assert "constitutional_gap" in VALID_SIGNAL_SOURCES
    assert "mirror_accuracy" in VALID_SIGNAL_SOURCES
    assert len(VALID_SIGNAL_SOURCES) == 3


# ── T120-SPIE-05: propose from failure signal ─────────────────────────────────

def test_spie_05_propose_failure(
    engine: SelfProposingInnovationEngine, failure_sig: FailureSignal
) -> None:
    """T120-SPIE-05: propose() returns InnovationProposal from failure signal."""
    p = engine.propose("epoch-001", failure=failure_sig)
    assert isinstance(p, InnovationProposal)


# ── T120-SPIE-06: propose from gap signal ─────────────────────────────────────

def test_spie_06_propose_gap(
    engine: SelfProposingInnovationEngine, gap_sig: ConstitutionalGapSignal
) -> None:
    """T120-SPIE-06: propose() returns InnovationProposal from gap signal."""
    p = engine.propose("epoch-001", gap=gap_sig)
    assert isinstance(p, InnovationProposal)


# ── T120-SPIE-07: propose from mirror signal ──────────────────────────────────

def test_spie_07_propose_mirror(
    engine: SelfProposingInnovationEngine, mirror_sig: MirrorAccuracySignal
) -> None:
    """T120-SPIE-07: propose() returns InnovationProposal from mirror signal."""
    p = engine.propose("epoch-001", mirror=mirror_sig)
    assert isinstance(p, InnovationProposal)


# ── T120-SPIE-08: SPIE-0 proposal_digest non-empty ───────────────────────────

def test_spie_08_digest_nonempty(proposal_from_failure: InnovationProposal) -> None:
    """T120-SPIE-08: SPIE-0 — proposal_digest is non-empty and sha256-prefixed."""
    assert proposal_from_failure.proposal_digest
    assert proposal_from_failure.proposal_digest.startswith("sha256:")


# ── T120-SPIE-09: SPIE-DETERM-0 identical inputs → identical ID ──────────────

def test_spie_09_determinism(tmp_path: Path, failure_sig: FailureSignal) -> None:
    """T120-SPIE-09: SPIE-DETERM-0 — same inputs produce same proposal_id."""
    eng1 = SelfProposingInnovationEngine(
        instance_id="node-x", ledger_path=tmp_path / "ledger_a.jsonl"
    )
    eng2 = SelfProposingInnovationEngine(
        instance_id="node-x", ledger_path=tmp_path / "ledger_b.jsonl"
    )
    p1 = eng1.propose("ep-determ", failure=failure_sig)
    p2 = eng2.propose("ep-determ", failure=failure_sig)
    assert p1.proposal_id == p2.proposal_id
    assert p1.proposal_digest == p2.proposal_digest


# ── T120-SPIE-10: proposal_id namespace prefix ───────────────────────────────

def test_spie_10_proposal_id_prefix(proposal_from_failure: InnovationProposal) -> None:
    """T120-SPIE-10: proposal_id carries 'spie:' namespace prefix."""
    assert proposal_from_failure.proposal_id.startswith("spie:")


# ── T120-SPIE-11: SPIE-SOURCE-0 at least one source ─────────────────────────

def test_spie_11_source_present(proposal_from_failure: InnovationProposal) -> None:
    """T120-SPIE-11: SPIE-SOURCE-0 — signal_sources list is non-empty."""
    assert len(proposal_from_failure.signal_sources) >= 1


# ── T120-SPIE-12: SPIE-SOURCE-0 no signal raises ─────────────────────────────

def test_spie_12_no_signal_raises(engine: SelfProposingInnovationEngine) -> None:
    """T120-SPIE-12: SPIE-SOURCE-0 — propose() with no signal raises SPIEViolation."""
    with pytest.raises(SPIEViolation):
        engine.propose("epoch-bad")


# ── T120-SPIE-13: SPIE-PERSIST-0 ledger written ──────────────────────────────

def test_spie_13_ledger_written(
    engine: SelfProposingInnovationEngine,
    failure_sig: FailureSignal,
    tmp_ledger: Path,
) -> None:
    """T120-SPIE-13: SPIE-PERSIST-0 — ledger exists and has content after propose."""
    engine.propose("epoch-001", failure=failure_sig)
    assert tmp_ledger.exists()
    assert tmp_ledger.stat().st_size > 0


# ── T120-SPIE-14: ledger line is valid JSON ───────────────────────────────────

def test_spie_14_ledger_json(
    engine: SelfProposingInnovationEngine,
    failure_sig: FailureSignal,
    tmp_ledger: Path,
) -> None:
    """T120-SPIE-14: each ledger line is valid JSON with required fields."""
    engine.propose("epoch-001", failure=failure_sig)
    rec = json.loads(tmp_ledger.read_text().splitlines()[0])
    assert "proposal_id" in rec
    assert "proposal_digest" in rec
    assert "chain_link" in rec


# ── T120-SPIE-15: SPIE-CHAIN-0 chain_link format ─────────────────────────────

def test_spie_15_chain_link_format(
    engine: SelfProposingInnovationEngine,
    failure_sig: FailureSignal,
    tmp_ledger: Path,
) -> None:
    """T120-SPIE-15: SPIE-CHAIN-0 — chain_link starts with 'hmac-sha256:'."""
    engine.propose("epoch-001", failure=failure_sig)
    rec = json.loads(tmp_ledger.read_text().splitlines()[0])
    assert rec["chain_link"].startswith("hmac-sha256:")


# ── T120-SPIE-16: verify_chain_integrity on empty ledger ─────────────────────

def test_spie_16_chain_empty(tmp_ledger: Path) -> None:
    """T120-SPIE-16: verify_chain_integrity returns True on empty/absent ledger."""
    eng = SelfProposingInnovationEngine(
        instance_id="alpha", ledger_path=tmp_ledger
    )
    assert eng.verify_chain_integrity() is True


# ── T120-SPIE-17: verify_chain_integrity after multiple proposals ─────────────

def test_spie_17_chain_multi(
    engine: SelfProposingInnovationEngine,
    failure_sig: FailureSignal,
    gap_sig: ConstitutionalGapSignal,
    mirror_sig: MirrorAccuracySignal,
) -> None:
    """T120-SPIE-17: chain integrity holds after 3 proposals."""
    engine.propose("ep-a", failure=failure_sig)
    engine.propose("ep-b", gap=gap_sig)
    engine.propose("ep-c", mirror=mirror_sig)
    assert engine.verify_chain_integrity() is True


# ── T120-SPIE-18: SPIE-GATE-0 duplicate fingerprint rejected ─────────────────

def test_spie_18_gate_duplicate(
    engine: SelfProposingInnovationEngine,
    failure_sig: FailureSignal,
) -> None:
    """T120-SPIE-18: SPIE-GATE-0 — same failure signal twice raises SPIEDuplicateError."""
    engine.propose("epoch-001", failure=failure_sig)
    with pytest.raises(SPIEDuplicateError):
        engine.propose("epoch-001", failure=failure_sig)


# ── T120-SPIE-19: different epoch_id with same signal still deduplicated ──────

def test_spie_19_gate_epoch_variant(
    engine: SelfProposingInnovationEngine,
    failure_sig: FailureSignal,
) -> None:
    """T120-SPIE-19: SPIE-GATE-0 — fingerprint is signal-based not epoch-based."""
    engine.propose("epoch-001", failure=failure_sig)
    with pytest.raises(SPIEDuplicateError):
        engine.propose("epoch-999", failure=failure_sig)


# ── T120-SPIE-20: SPIE-HUMAN0-0 ratified=False at construction ───────────────

def test_spie_20_ratified_false_at_construction(
    proposal_from_failure: InnovationProposal,
) -> None:
    """T120-SPIE-20: SPIE-HUMAN0-0 — ratified is False immediately after propose."""
    assert proposal_from_failure.ratified is False
    assert proposal_from_failure.ratified_by == ""


# ── T120-SPIE-21: ratify() sets ratified=True ────────────────────────────────

def test_spie_21_ratify(
    engine: SelfProposingInnovationEngine,
    proposal_from_failure: InnovationProposal,
) -> None:
    """T120-SPIE-21: ratify() sets ratified=True and records ratified_by."""
    ratified = engine.ratify(proposal_from_failure.proposal_id, "DUSTIN L REID")
    assert ratified.ratified is True
    assert ratified.ratified_by == "DUSTIN L REID"


# ── T120-SPIE-22: ratify() unknown proposal raises KeyError ──────────────────

def test_spie_22_ratify_unknown(engine: SelfProposingInnovationEngine) -> None:
    """T120-SPIE-22: ratify() on unknown proposal_id raises KeyError."""
    with pytest.raises(KeyError):
        engine.ratify("spie:nonexistent", "DUSTIN L REID")


# ── T120-SPIE-23: ratify() empty ratified_by raises SPIEViolation ────────────

def test_spie_23_ratify_empty_governor(
    engine: SelfProposingInnovationEngine,
    proposal_from_failure: InnovationProposal,
) -> None:
    """T120-SPIE-23: SPIE-HUMAN0-0 — ratify() with empty ratified_by raises."""
    with pytest.raises(SPIEViolation):
        engine.ratify(proposal_from_failure.proposal_id, "")


# ── T120-SPIE-24: get_proposal returns correct proposal ──────────────────────

def test_spie_24_get_proposal(
    engine: SelfProposingInnovationEngine,
    proposal_from_failure: InnovationProposal,
) -> None:
    """T120-SPIE-24: get_proposal returns the correct proposal by ID."""
    retrieved = engine.get_proposal(proposal_from_failure.proposal_id)
    assert retrieved is not None
    assert retrieved.proposal_id == proposal_from_failure.proposal_id


# ── T120-SPIE-25: get_proposal unknown returns None ──────────────────────────

def test_spie_25_get_proposal_unknown(engine: SelfProposingInnovationEngine) -> None:
    """T120-SPIE-25: get_proposal returns None for unknown proposal_id."""
    assert engine.get_proposal("spie:nope") is None


# ── T120-SPIE-26: all_proposals count ────────────────────────────────────────

def test_spie_26_all_proposals(
    engine: SelfProposingInnovationEngine,
    failure_sig: FailureSignal,
    gap_sig: ConstitutionalGapSignal,
    mirror_sig: MirrorAccuracySignal,
) -> None:
    """T120-SPIE-26: all_proposals returns list of all proposals emitted."""
    engine.propose("ep-a", failure=failure_sig)
    engine.propose("ep-b", gap=gap_sig)
    engine.propose("ep-c", mirror=mirror_sig)
    assert len(engine.all_proposals()) == 3


# ── T120-SPIE-27: export_state shape ─────────────────────────────────────────

def test_spie_27_export_state(
    engine: SelfProposingInnovationEngine,
    proposal_from_failure: InnovationProposal,
) -> None:
    """T120-SPIE-27: export_state returns dict with required keys."""
    state = engine.export_state()
    assert "spie_version" in state
    assert "instance_id" in state
    assert "proposal_count" in state
    assert "proposals" in state
    assert state["proposal_count"] == 1


# ── T120-SPIE-28: spie_guard pass ────────────────────────────────────────────

def test_spie_28_guard_pass() -> None:
    """T120-SPIE-28: spie_guard does not raise when condition is True."""
    spie_guard(True, "SPIE-0", "should not raise")


# ── T120-SPIE-29: spie_guard fail ────────────────────────────────────────────

def test_spie_29_guard_fail() -> None:
    """T120-SPIE-29: spie_guard raises SPIEViolation when condition is False."""
    with pytest.raises(SPIEViolation, match=r"\[SPIE Hard-class violation\] SPIE-TEST"):
        spie_guard(False, "SPIE-TEST", "expected")


# ── T120-SPIE-30: multi-signal proposal carries all sources ──────────────────

def test_spie_30_multi_signal(
    engine: SelfProposingInnovationEngine,
    failure_sig: FailureSignal,
    gap_sig: ConstitutionalGapSignal,
    mirror_sig: MirrorAccuracySignal,
) -> None:
    """T120-SPIE-30: proposal from three signals records all three sources."""
    p = engine.propose(
        "epoch-multi",
        failure=failure_sig,
        gap=gap_sig,
        mirror=mirror_sig,
    )
    assert "failure_history" in p.signal_sources
    assert "constitutional_gap" in p.signal_sources
    assert "mirror_accuracy" in p.signal_sources
    assert len(p.signals) == 3
