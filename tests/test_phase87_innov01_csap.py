# SPDX-License-Identifier: Apache-2.0
"""INNOV-01 CSAP — Test Suite
Tests: T87-CSAP-01 through T87-CSAP-20

Invariants under test:
  CSAP-0  Hard-class amendment blocked without HUMAN-0 co-signature.
  CSAP-1  Ledger written before matrix mutation.
  Gate-0  All six eligibility checks.
  Gate-1  All six ratification checks.
  Failure modes: AMENDMENT_INELIGIBLE, RATIFICATION_DENIED,
                 AMENDMENT_CONFLICT, AMENDMENT_REPLAY_BROKEN,
                 INVARIANT_PARSER_REJECT.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from runtime.evolution.csap_protocol import (
    AMENDMENT_CONFLICT,
    AMENDMENT_INELIGIBLE,
    AMENDMENT_REPLAY_BROKEN,
    INVARIANT_PARSER_REJECT,
    RATIFICATION_DENIED,
    AmendmentStatus,
    ConstitutionalAmendmentLedger,
    ConstitutionalAmendmentProposal,
    ConstitutionalAmendmentQueue,
    ConstitutionalSelfAmendmentProtocol,
    CSAPGateOutcome,
    InvariantClass,
    InvariantEntry,
    InvariantParser,
    InvariantsMatrix,
    evaluate_csap_gate_0,
    evaluate_csap_gate_1,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_queue(tmp_path):
    return ConstitutionalAmendmentQueue(tmp_path / "amendment_queue.jsonl")


@pytest.fixture
def tmp_ledger(tmp_path):
    return ConstitutionalAmendmentLedger(tmp_path / "amendment_ledger.jsonl")


@pytest.fixture
def sample_matrix():
    return InvariantsMatrix(
        entries={
            "PROP-AUTO-0": InvariantEntry(
                rule_id="PROP-AUTO-0",
                statement="ProposalEngine MUST NOT activate unless API key is present",
                invariant_class=InvariantClass.CLASS_B_ELIGIBLE,
                phase=57,
                enforcement="startup check",
            ),
            "HARD-INV-0": InvariantEntry(
                rule_id="HARD-INV-0",
                statement="GovernanceGate MUST reject mutations lacking evidence bundle",
                invariant_class=InvariantClass.HARD,
                phase=63,
                enforcement="GovernanceGateV2 pre-check",
            ),
        }
    )


def _make_proposal(
    target_rule_id: str = "PROP-AUTO-0",
    evidence_count: int = 3,
    proposed_text: str = "ProposalEngine MUST NOT activate unless ADAAD_ANTHROPIC_API_KEY is validated",
    human_0_cosignature: str | None = None,
    epoch_id: str = "epoch-42",
) -> ConstitutionalAmendmentProposal:
    refs = tuple(f"eb-{i:03d}" for i in range(evidence_count))
    pid_src = f"{target_rule_id}|{proposed_text}|{epoch_id}"
    pid = "csap-prop-" + hashlib.sha256(pid_src.encode()).hexdigest()[:12]
    return ConstitutionalAmendmentProposal(
        proposal_id=pid,
        target_rule_id=target_rule_id,
        intent="Strengthen API key validation wording",
        proposed_text=proposed_text,
        rationale="Three epochs of evidence show ambiguity in key validation semantics",
        evidence_refs=refs,
        author="ProposalEngine",
        epoch_id=epoch_id,
        human_0_cosignature=human_0_cosignature,
    )


# ---------------------------------------------------------------------------
# InvariantParser tests
# ---------------------------------------------------------------------------


def test_T87_CSAP_01_parser_valid_statement():
    """T87-CSAP-01: Valid invariant statement parses successfully."""
    ok, reason = InvariantParser.parse(
        "ProposalEngine MUST NOT activate unless key is present and validated"
    )
    assert ok is True
    assert reason == "OK"


def test_T87_CSAP_02_parser_rejects_empty():
    """T87-CSAP-02: Empty statement is rejected."""
    ok, reason = InvariantParser.parse("")
    assert ok is False
    assert "INVARIANT_PARSER_REJECT" in reason


def test_T87_CSAP_03_parser_rejects_placeholder():
    """T87-CSAP-03: Statement with placeholder tokens is rejected."""
    ok, reason = InvariantParser.parse("Component MUST do <action> with [value]")
    assert ok is False
    assert "placeholder" in reason.lower()


def test_T87_CSAP_04_parser_rejects_no_modal():
    """T87-CSAP-04: Statement without modal verb is rejected."""
    ok, reason = InvariantParser.parse(
        "The component activates when the key is present and available"
    )
    assert ok is False
    assert "modal" in reason.lower()


def test_T87_CSAP_05_parser_rejects_too_short():
    """T87-CSAP-05: Statement with fewer than 6 tokens is rejected."""
    ok, reason = InvariantParser.parse("Component MUST validate")
    assert ok is False
    assert "tokens" in reason.lower()


# ---------------------------------------------------------------------------
# CSAP-GATE-0 tests
# ---------------------------------------------------------------------------


def test_T87_CSAP_06_gate0_pass_class_b(sample_matrix, tmp_ledger):
    """T87-CSAP-06: Gate-0 passes for a valid Class-B proposal."""
    proposal = _make_proposal()
    report = evaluate_csap_gate_0(proposal, sample_matrix, 0.1, tmp_ledger)
    assert report.outcome == CSAPGateOutcome.PASS
    assert report.failure_code is None
    assert len(report.checks_failed) == 0


def test_T87_CSAP_07_gate0_fail_missing_rule_id(sample_matrix, tmp_ledger):
    """T87-CSAP-07: Gate-0 fails when target_rule_id is not in matrix."""
    proposal = _make_proposal(target_rule_id="NONEXISTENT-RULE")
    report = evaluate_csap_gate_0(proposal, sample_matrix, 0.1, tmp_ledger)
    assert report.outcome == CSAPGateOutcome.FAIL
    assert report.failure_code == AMENDMENT_INELIGIBLE
    assert "CHECK-1-TARGET-EXISTS" in report.checks_failed


def test_T87_CSAP_08_gate0_fail_insufficient_evidence(sample_matrix, tmp_ledger):
    """T87-CSAP-08: Gate-0 fails when fewer than 3 evidence refs."""
    proposal = _make_proposal(evidence_count=2)
    report = evaluate_csap_gate_0(proposal, sample_matrix, 0.1, tmp_ledger)
    assert report.outcome == CSAPGateOutcome.FAIL
    assert report.failure_code == AMENDMENT_INELIGIBLE
    assert "CHECK-2-EVIDENCE-REFS" in report.checks_failed


def test_T87_CSAP_09_gate0_fail_unparseable_text(sample_matrix, tmp_ledger):
    """T87-CSAP-09: Gate-0 fails when proposed_text is unparseable."""
    proposal = _make_proposal(proposed_text="bad text")
    report = evaluate_csap_gate_0(proposal, sample_matrix, 0.1, tmp_ledger)
    assert report.outcome == CSAPGateOutcome.FAIL
    assert report.failure_code == INVARIANT_PARSER_REJECT


def test_T87_CSAP_10_gate0_fail_high_debt(sample_matrix, tmp_ledger):
    """T87-CSAP-10: Gate-0 fails when governance_debt_score >= 0.4 (conflict of interest)."""
    proposal = _make_proposal()
    report = evaluate_csap_gate_0(proposal, sample_matrix, 0.5, tmp_ledger)
    assert report.outcome == CSAPGateOutcome.FAIL
    assert "CHECK-4-DEBT-SCORE" in report.checks_failed


def test_T87_CSAP_11_gate0_fail_hard_class_no_cosign(sample_matrix, tmp_ledger):
    """T87-CSAP-11 / CSAP-0: Gate-0 fails targeting Hard-class without HUMAN-0 co-signature."""
    proposal = _make_proposal(target_rule_id="HARD-INV-0")
    report = evaluate_csap_gate_0(proposal, sample_matrix, 0.1, tmp_ledger)
    assert report.outcome == CSAPGateOutcome.FAIL
    assert report.failure_code == AMENDMENT_CONFLICT
    assert "CHECK-6-HARD-CLASS-COSIGN" in report.checks_failed


def test_T87_CSAP_12_gate0_hard_class_with_cosign_passes(sample_matrix, tmp_ledger):
    """T87-CSAP-12: Gate-0 passes Hard-class amendment when HUMAN-0 co-signature is present."""
    proposal = _make_proposal(
        target_rule_id="HARD-INV-0",
        human_0_cosignature="Dustin L. Reid · 2026-03-23",
    )
    report = evaluate_csap_gate_0(proposal, sample_matrix, 0.1, tmp_ledger)
    assert report.outcome == CSAPGateOutcome.PASS


# ---------------------------------------------------------------------------
# CSAP-GATE-1 tests
# ---------------------------------------------------------------------------


def test_T87_CSAP_13_gate1_pass(sample_matrix):
    """T87-CSAP-13: Gate-1 passes with valid fitness delta and epoch count."""
    proposal = _make_proposal()
    report = evaluate_csap_gate_1(proposal, sample_matrix, 0.02, 10, acse_evidence_available=True)
    assert report.outcome == CSAPGateOutcome.PASS
    assert report.failure_code is None


def test_T87_CSAP_14_gate1_fail_regression_delta(sample_matrix):
    """T87-CSAP-14: Gate-1 fails when fitness_regression_delta >= 0.05."""
    proposal = _make_proposal()
    report = evaluate_csap_gate_1(proposal, sample_matrix, 0.07, 10)
    assert report.outcome == CSAPGateOutcome.FAIL
    assert report.failure_code == RATIFICATION_DENIED
    assert "CHECK-4-FITNESS-REGRESSION" in report.checks_failed


def test_T87_CSAP_15_gate1_fail_insufficient_epochs(sample_matrix):
    """T87-CSAP-15: Gate-1 fails when epoch_simulation_count < 10."""
    proposal = _make_proposal()
    report = evaluate_csap_gate_1(proposal, sample_matrix, 0.01, 5)
    assert report.outcome == CSAPGateOutcome.FAIL
    assert "CHECK-4-FITNESS-REGRESSION" in report.checks_failed


# ---------------------------------------------------------------------------
# Full CSAP protocol — orchestrator tests
# ---------------------------------------------------------------------------


def test_T87_CSAP_16_full_ratification(sample_matrix, tmp_queue, tmp_ledger):
    """T87-CSAP-16: Full pipeline produces RATIFIED status."""
    protocol = ConstitutionalSelfAmendmentProtocol(queue=tmp_queue, ledger=tmp_ledger)
    proposal = _make_proposal()
    status, record = protocol.evaluate(
        proposal, sample_matrix,
        governance_debt_score=0.1,
        fitness_regression_delta=0.02,
        epoch_simulation_count=10,
        acse_evidence_available=True,
    )
    assert status == AmendmentStatus.RATIFIED
    assert record.status == AmendmentStatus.RATIFIED
    assert record.gate_1_report is not None
    assert record.gate_1_report.outcome == CSAPGateOutcome.PASS


def test_T87_CSAP_17_csap1_ledger_written_before_matrix(sample_matrix, tmp_queue, tmp_ledger):
    """T87-CSAP-17 / CSAP-1: Ledger is written during evaluate(); matrix is NOT mutated by protocol."""
    protocol = ConstitutionalSelfAmendmentProtocol(queue=tmp_queue, ledger=tmp_ledger)
    proposal = _make_proposal()
    original_hash = sample_matrix.matrix_hash
    status, record = protocol.evaluate(
        proposal, sample_matrix,
        governance_debt_score=0.1,
        fitness_regression_delta=0.02,
        epoch_simulation_count=10,
    )
    # CSAP-1: ledger must contain the record
    lines = tmp_ledger._path.read_text().strip().splitlines()
    assert len(lines) == 1
    ledger_record = json.loads(lines[0])
    assert ledger_record["proposal_id"] == proposal.proposal_id
    # Matrix hash unchanged — protocol does NOT mutate matrix (caller applies amendment)
    assert sample_matrix.matrix_hash == original_hash


def test_T87_CSAP_18_rejected_on_gate0_failure(sample_matrix, tmp_queue, tmp_ledger):
    """T87-CSAP-18: Protocol returns REJECTED when gate-0 fails."""
    protocol = ConstitutionalSelfAmendmentProtocol(queue=tmp_queue, ledger=tmp_ledger)
    proposal = _make_proposal(evidence_count=1)
    status, record = protocol.evaluate(
        proposal, sample_matrix,
        governance_debt_score=0.1,
        fitness_regression_delta=0.02,
        epoch_simulation_count=10,
    )
    assert status == AmendmentStatus.REJECTED
    assert record.gate_1_report is None  # gate-1 never reached


def test_T87_CSAP_19_ratification_hash_deterministic(sample_matrix, tmp_queue, tmp_ledger):
    """T87-CSAP-19: Same inputs produce the same ratification_hash (determinism invariant)."""
    class FixedClock:
        def now_utc(self):
            return "2026-03-23T00:00:00Z"

    p1 = _make_proposal(epoch_id="epoch-99")
    p2 = _make_proposal(epoch_id="epoch-99")

    proto1 = ConstitutionalSelfAmendmentProtocol(
        queue=tmp_queue, ledger=tmp_ledger, timestamp_provider=FixedClock()
    )
    _, r1 = proto1.evaluate(
        p1, sample_matrix,
        governance_debt_score=0.1,
        fitness_regression_delta=0.02,
        epoch_simulation_count=10,
    )

    tmp_queue2 = ConstitutionalAmendmentQueue(tmp_ledger._path.parent / "q2.jsonl")
    tmp_ledger2 = ConstitutionalAmendmentLedger(tmp_ledger._path.parent / "l2.jsonl")
    proto2 = ConstitutionalSelfAmendmentProtocol(
        queue=tmp_queue2, ledger=tmp_ledger2, timestamp_provider=FixedClock()
    )
    _, r2 = proto2.evaluate(
        p2, sample_matrix,
        governance_debt_score=0.1,
        fitness_regression_delta=0.02,
        epoch_simulation_count=10,
    )

    # Same inputs → same ratification_hash (replay-verifiable)
    assert r1.ratification_hash == r2.ratification_hash


def test_T87_CSAP_20_apply_amendment_produces_new_matrix(sample_matrix):
    """T87-CSAP-20: apply_amendment() returns new matrix with updated statement; original unchanged."""
    original_statement = sample_matrix.get("PROP-AUTO-0").statement
    new_statement = "ProposalEngine MUST NOT activate unless ADAAD_ANTHROPIC_API_KEY is present and endpoint-validated"
    new_matrix = sample_matrix.apply_amendment(
        "PROP-AUTO-0",
        new_statement,
        ratification_hash="sha256:abc123",
    )
    # New matrix has updated statement
    assert new_matrix.get("PROP-AUTO-0").statement == new_statement
    # Original matrix is unchanged
    assert sample_matrix.get("PROP-AUTO-0").statement == original_statement
    # Matrix hashes differ
    assert new_matrix.matrix_hash != sample_matrix.matrix_hash
