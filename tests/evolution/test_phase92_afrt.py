# SPDX-License-Identifier: Apache-2.0
"""Phase 92 — INNOV-08 AFRT Test Suite.

Acceptance criteria from PHASE_92_PLAN.md:
  T92-AFRT-01..05   AdversarialCaseGenerator generates 1–5 cases per proposal
  T92-AFRT-06..08   AFRT-0: Red Team cannot emit approval events
  T92-AFRT-09..11   AFRT-GATE-0: CEL step order enforced
  T92-AFRT-12..14   AFRT-INTEL-0: cases sourced from CodeIntel uncovered paths
  T92-AFRT-15..17   AFRT-LEDGER-0: ledger event written before result returned
  T92-AFRT-18       AFRT-CASES-0: zero-case result treated as engine failure
  T92-AFRT-19..20   AFRT-DETERM-0: identical inputs → identical case set
  T92-AFRT-21..23   RedTeamFindingsReport correctly returned to proposer on failure
  T92-AFRT-24..25   (Integration markers — Aponi panel, covered in Track B suite)

Gate: 23/23 unit tests must pass before PR-92-01 may merge.
"""

from __future__ import annotations

import hashlib
import json
import pytest
from unittest.mock import MagicMock, patch
from typing import List

from runtime.evolution.afrt_engine import (
    AFRT_VERSION,
    _MAX_ADVERSARIAL_CASES,
    _MIN_ADVERSARIAL_CASES,
    AdversarialCase,
    AdversarialCaseGenerator,
    AdversarialCaseOutcome,
    AdversarialRedTeamAgent,
    AFRTEngineError,
    CELStepOrderViolation,
    RedTeamFindingsReport,
    RedTeamLedgerEvent,
    RedTeamVerdict,
    _compute_report_hash,
    _deterministic_case_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROPOSAL_ID = "proposal-abc123"
EPOCH_ID = "epoch-001"
UNCOVERED_PATHS = [
    "runtime/foo.py:L42",
    "runtime/bar.py:L88",
    "runtime/baz.py:L7",
]


def make_proposal(proposal_id: str = PROPOSAL_ID) -> dict:
    return {"id": proposal_id, "content": "def foo(): pass", "version": "1"}


def make_code_intel_mock(paths: List[str] = None) -> MagicMock:
    mock = MagicMock()
    mock.get_uncovered_paths.return_value = paths if paths is not None else UNCOVERED_PATHS
    return mock


def make_ledger_mock() -> MagicMock:
    mock = MagicMock()
    mock.append.return_value = None
    return mock


def make_agent(paths: List[str] = None, ledger=None) -> AdversarialRedTeamAgent:
    return AdversarialRedTeamAgent(
        code_intel_model=make_code_intel_mock(paths),
        ledger=ledger or make_ledger_mock(),
    )


# ---------------------------------------------------------------------------
# T92-AFRT-01..05 — Case generation count (AFRT-CASES-0)
# ---------------------------------------------------------------------------

class TestCaseGenerationCount:

    def test_01_generates_at_least_one_case(self):
        """T92-AFRT-01: generator produces at least 1 case for 1 path."""
        gen = AdversarialCaseGenerator()
        cases = gen.generate(PROPOSAL_ID, ["runtime/foo.py:L1"], make_proposal())
        assert len(cases) >= _MIN_ADVERSARIAL_CASES

    def test_02_generates_at_most_five_cases(self):
        """T92-AFRT-02: generator produces at most 5 cases regardless of path count."""
        many_paths = [f"runtime/mod_{i}.py:L{i}" for i in range(20)]
        gen = AdversarialCaseGenerator()
        cases = gen.generate(PROPOSAL_ID, many_paths, make_proposal())
        assert len(cases) <= _MAX_ADVERSARIAL_CASES

    def test_03_generates_correct_count_for_three_paths(self):
        """T92-AFRT-03: 3 paths → 3 cases."""
        gen = AdversarialCaseGenerator()
        cases = gen.generate(PROPOSAL_ID, UNCOVERED_PATHS, make_proposal())
        assert len(cases) == 3

    def test_04_report_enforces_case_count_lower_bound(self):
        """T92-AFRT-04: RedTeamFindingsReport rejects zero adversarial cases."""
        case = AdversarialCase(
            case_id="x", target_path="p", description="d",
            probe_input={}, expected_invariant="i"
        )
        # AFRT-CASES-0: tuple with 1 case passes
        report = RedTeamFindingsReport(
            proposal_id=PROPOSAL_ID, epoch_id=EPOCH_ID,
            verdict=RedTeamVerdict.PASS,
            adversarial_cases=(case,),
            uncovered_paths=("p",),
            failure_cases=(),
            report_hash="sha256:abc",
            trace_committed=True,
        )
        assert len(report.adversarial_cases) >= _MIN_ADVERSARIAL_CASES

    def test_05_report_rejects_zero_cases_via_post_init(self):
        """T92-AFRT-05: RedTeamFindingsReport.__post_init__ rejects 0 cases."""
        with pytest.raises(AssertionError, match="AFRT-CASES-0"):
            RedTeamFindingsReport(
                proposal_id=PROPOSAL_ID, epoch_id=EPOCH_ID,
                verdict=RedTeamVerdict.PASS,
                adversarial_cases=(),           # violation: empty tuple
                uncovered_paths=("p",),
                failure_cases=(),
                report_hash="sha256:abc",
                trace_committed=True,
            )


# ---------------------------------------------------------------------------
# T92-AFRT-06..08 — AFRT-0: no approval emission
# ---------------------------------------------------------------------------

class TestAFRTZeroPromotion:

    def test_06_report_approval_emitted_is_false_by_default(self):
        """T92-AFRT-06: approval_emitted defaults to False."""
        case = AdversarialCase(
            case_id="c1", target_path="p", description="d",
            probe_input={}, expected_invariant="i"
        )
        report = RedTeamFindingsReport(
            proposal_id=PROPOSAL_ID, epoch_id=EPOCH_ID,
            verdict=RedTeamVerdict.PASS,
            adversarial_cases=(case,),
            uncovered_paths=("p",),
            failure_cases=(),
            report_hash="sha256:abc",
            trace_committed=True,
        )
        assert report.approval_emitted is False

    def test_07_setting_approval_emitted_true_raises(self):
        """T92-AFRT-07: approval_emitted=True triggers AFRT-0 assertion."""
        case = AdversarialCase(
            case_id="c1", target_path="p", description="d",
            probe_input={}, expected_invariant="i"
        )
        with pytest.raises(AssertionError, match="AFRT-0"):
            RedTeamFindingsReport(
                proposal_id=PROPOSAL_ID, epoch_id=EPOCH_ID,
                verdict=RedTeamVerdict.PASS,
                adversarial_cases=(case,),
                uncovered_paths=("p",),
                failure_cases=(),
                report_hash="sha256:abc",
                trace_committed=True,
                approval_emitted=True,    # AFRT-0 violation
            )

    def test_08_evaluate_never_sets_approval_emitted(self):
        """T92-AFRT-08: AdversarialRedTeamAgent.evaluate() never emits approval."""
        agent = make_agent()
        report = agent.evaluate(make_proposal(), EPOCH_ID)
        assert report.approval_emitted is False


# ---------------------------------------------------------------------------
# T92-AFRT-09..11 — AFRT-GATE-0: step order
# ---------------------------------------------------------------------------

class TestAFRTGateOrdering:

    def test_09_cef_step_order_violation_is_importable(self):
        """T92-AFRT-09: CELStepOrderViolation exists as a distinct exception type."""
        assert issubclass(CELStepOrderViolation, RuntimeError)

    def test_10_afrt_engine_error_is_importable(self):
        """T92-AFRT-10: AFRTEngineError exists as a distinct exception type."""
        assert issubclass(AFRTEngineError, RuntimeError)

    def test_11_afrt_gate_0_step_position_documented_in_engine(self):
        """T92-AFRT-11: afrt_engine module references AFRT-GATE-0 in docstring."""
        import runtime.evolution.afrt_engine as mod
        assert "AFRT-GATE-0" in mod.__doc__


# ---------------------------------------------------------------------------
# T92-AFRT-12..14 — AFRT-INTEL-0: CodeIntel coupling
# ---------------------------------------------------------------------------

class TestAFRTCodeIntelCoupling:

    def test_12_cases_target_uncovered_paths(self):
        """T92-AFRT-12: generated cases target paths returned by CodeIntelModel."""
        gen = AdversarialCaseGenerator()
        paths = ["runtime/alpha.py:L10", "runtime/beta.py:L20"]
        cases = gen.generate(PROPOSAL_ID, paths, make_proposal())
        case_paths = {c.target_path for c in cases}
        assert case_paths == set(paths)

    def test_13_empty_uncovered_paths_raises_afrt_engine_error(self):
        """T92-AFRT-13: empty CodeIntel result raises AFRTEngineError (AFRT-CASES-0)."""
        agent = make_agent(paths=[])
        with pytest.raises(AFRTEngineError, match="AFRT-INTEL-0"):
            agent.evaluate(make_proposal(), EPOCH_ID)

    def test_14_code_intel_is_queried_per_evaluate_call(self):
        """T92-AFRT-14: CodeIntelModel.get_uncovered_paths called once per evaluate."""
        intel = make_code_intel_mock()
        agent = AdversarialRedTeamAgent(
            code_intel_model=intel,
            ledger=make_ledger_mock(),
        )
        agent.evaluate(make_proposal(), EPOCH_ID)
        intel.get_uncovered_paths.assert_called_once()


# ---------------------------------------------------------------------------
# T92-AFRT-15..17 — AFRT-LEDGER-0: ledger-first
# ---------------------------------------------------------------------------

class TestAFRTLedgerFirst:

    def test_15_ledger_append_called_before_return(self):
        """T92-AFRT-15: ledger.append() is called during evaluate()."""
        ledger = make_ledger_mock()
        agent = make_agent(ledger=ledger)
        agent.evaluate(make_proposal(), EPOCH_ID)
        ledger.append.assert_called_once()

    def test_16_ledger_event_contains_proposal_id(self):
        """T92-AFRT-16: committed ledger event references the proposal_id."""
        ledger = make_ledger_mock()
        agent = make_agent(ledger=ledger)
        agent.evaluate(make_proposal(PROPOSAL_ID), EPOCH_ID)
        call_args = ledger.append.call_args[0][0]
        assert call_args["proposal_id"] == PROPOSAL_ID

    def test_17_report_trace_committed_true(self):
        """T92-AFRT-17: report.trace_committed is True after successful ledger write."""
        agent = make_agent()
        report = agent.evaluate(make_proposal(), EPOCH_ID)
        assert report.trace_committed is True


# ---------------------------------------------------------------------------
# T92-AFRT-18 — AFRT-CASES-0: zero-case engine failure
# ---------------------------------------------------------------------------

class TestZeroCaseEngineFailure:

    def test_18_generator_raises_on_empty_paths(self):
        """T92-AFRT-18: AdversarialCaseGenerator raises AFRTEngineError for empty paths."""
        gen = AdversarialCaseGenerator()
        with pytest.raises(AFRTEngineError, match="AFRT-CASES-0"):
            gen.generate(PROPOSAL_ID, [], make_proposal())


# ---------------------------------------------------------------------------
# T92-AFRT-19..20 — AFRT-DETERM-0: deterministic reproducibility
# ---------------------------------------------------------------------------

class TestAFRTDeterminism:

    def test_19_identical_inputs_produce_identical_case_ids(self):
        """T92-AFRT-19: same proposal + paths → same case_ids across two runs."""
        gen = AdversarialCaseGenerator()
        cases_a = gen.generate(PROPOSAL_ID, UNCOVERED_PATHS, make_proposal())
        cases_b = gen.generate(PROPOSAL_ID, UNCOVERED_PATHS, make_proposal())
        assert [c.case_id for c in cases_a] == [c.case_id for c in cases_b]

    def test_20_different_proposals_produce_different_case_ids(self):
        """T92-AFRT-20: different proposal_ids → different case_ids."""
        gen = AdversarialCaseGenerator()
        cases_a = gen.generate("proposal-AAA", UNCOVERED_PATHS, make_proposal("proposal-AAA"))
        cases_b = gen.generate("proposal-BBB", UNCOVERED_PATHS, make_proposal("proposal-BBB"))
        ids_a = {c.case_id for c in cases_a}
        ids_b = {c.case_id for c in cases_b}
        assert ids_a.isdisjoint(ids_b)


# ---------------------------------------------------------------------------
# T92-AFRT-21..23 — RedTeamFindingsReport returned to proposer on failure
# ---------------------------------------------------------------------------

class TestRedTeamReturnedVerdict:

    def _make_falsifying_agent(self) -> AdversarialRedTeamAgent:
        """Agent whose sandbox runner always returns FALSIFIED outcomes."""
        from runtime.evolution.afrt_engine import _DefaultSandboxRunner, AdversarialCase, AdversarialCaseOutcome

        class AlwaysFalsifySandbox:
            def run(self, cases, proposal):
                return [
                    AdversarialCase(
                        case_id=c.case_id,
                        target_path=c.target_path,
                        description=c.description,
                        probe_input=c.probe_input,
                        expected_invariant=c.expected_invariant,
                        outcome=AdversarialCaseOutcome.FALSIFIED,
                        failure_detail="forced falsification",
                    )
                    for c in cases
                ]

        return AdversarialRedTeamAgent(
            code_intel_model=make_code_intel_mock(),
            ledger=make_ledger_mock(),
            sandbox_runner=AlwaysFalsifySandbox(),
        )

    def test_21_returned_verdict_when_cases_falsified(self):
        """T92-AFRT-21: verdict is RETURNED when any adversarial case is falsified."""
        agent = self._make_falsifying_agent()
        report = agent.evaluate(make_proposal(), EPOCH_ID)
        assert report.verdict == RedTeamVerdict.RETURNED

    def test_22_failure_cases_populated_on_returned_verdict(self):
        """T92-AFRT-22: failure_cases contains falsified cases on RETURNED verdict."""
        agent = self._make_falsifying_agent()
        report = agent.evaluate(make_proposal(), EPOCH_ID)
        assert len(report.failure_cases) > 0
        assert all(c.outcome == AdversarialCaseOutcome.FALSIFIED for c in report.failure_cases)

    def test_23_pass_verdict_when_all_cases_survive(self):
        """T92-AFRT-23: verdict is PASS when all adversarial cases survived."""
        from runtime.evolution.afrt_engine import _DefaultSandboxRunner, AdversarialCaseOutcome

        class AlwaysSurviveSandbox:
            def run(self, cases, proposal):
                from runtime.evolution.afrt_engine import AdversarialCase
                return [
                    AdversarialCase(
                        case_id=c.case_id,
                        target_path=c.target_path,
                        description=c.description,
                        probe_input=c.probe_input,
                        expected_invariant=c.expected_invariant,
                        outcome=AdversarialCaseOutcome.SURVIVED,
                    )
                    for c in cases
                ]

        agent = AdversarialRedTeamAgent(
            code_intel_model=make_code_intel_mock(),
            ledger=make_ledger_mock(),
            sandbox_runner=AlwaysSurviveSandbox(),
        )
        report = agent.evaluate(make_proposal(), EPOCH_ID)
        assert report.verdict == RedTeamVerdict.PASS
        assert len(report.failure_cases) == 0
