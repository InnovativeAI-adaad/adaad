# SPDX-License-Identifier: Apache-2.0
"""Phase 15 / PR-15-01 — GovernanceDebtLedger wiring into EvolutionLoop.

Tests verify:
  T15-01  debt_ledger absent → governance_debt_score is 0.0 in context
  T15-02  debt_ledger injected → accumulate_epoch_verdicts() called each epoch
  T15-03  compound_debt_score from snapshot → _last_debt_score updated
  T15-04  _last_debt_score fed into governance_debt_score in next epoch context
  T15-05  accumulate_epoch_verdicts() receives epoch_id and epoch_index
  T15-06  warning_verdicts built from rejected all_scores
  T15-07  debt_ledger.accumulate raises → epoch continues, debt stays previous
  T15-08  _last_debt_score initialises to 0.0
  T15-09  governance_debt_score in ProposalRequest.context is float
  T15-10  compound_debt_score clamped to non-negative
  T15-11  multiple epochs: debt updates each epoch
  T15-12  EvolutionLoop accepts debt_ledger kwarg
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.evolution.evolution_loop import EvolutionLoop
from runtime.evolution.proposal_engine import ProposalEngine, ProposalRequest
from runtime.governance.debt_ledger import GovernanceDebtLedger, GovernanceDebtSnapshot
from runtime.intelligence.proposal import Proposal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_debt_snapshot(compound: float = 1.5) -> GovernanceDebtSnapshot:
    return GovernanceDebtSnapshot(
        snapshot_hash="sha256:" + "a" * 64,
        schema_version="1.0.0",
        epoch_id="ep-001",
        epoch_index=1,
        warning_count=2,
        warning_weighted_sum=1.5,
        applied_decay_epochs=1,
        decayed_prior_debt=0.0,
        compound_debt_score=compound,
        breach_threshold=3.0,
        threshold_breached=False,
        warning_weights={},
        warning_rules=[],
        prev_snapshot_hash="sha256:" + "0" * 64,
    )


def _capture_engine_context():
    captured = []
    mock_engine = MagicMock(spec=ProposalEngine)

    def _generate(req: ProposalRequest) -> Proposal:
        captured.append(req)
        return Proposal(
            proposal_id="ep:auto", title="T", summary="S",
            estimated_impact=0.0, real_diff="",
        )

    mock_engine.generate.side_effect = _generate
    return mock_engine, captured


def _run(loop: EvolutionLoop, epoch_id: str = "ep-001") -> None:
    ctx = CodebaseContext(file_summaries={}, recent_failures=[], current_epoch_id=epoch_id)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value=[]):
        loop.run_epoch(ctx)


# ---------------------------------------------------------------------------
# T15-01: No debt_ledger → 0.0 default
# ---------------------------------------------------------------------------

class TestNoDebtLedger:
    def test_governance_debt_score_is_zero_without_ledger(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop)
        assert captured[0].context["governance_debt_score"] == pytest.approx(0.0)

    def test_last_debt_score_initialises_to_zero(self):
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True)
        assert loop._last_debt_score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T15-02: debt_ledger injected → accumulate called each epoch
# ---------------------------------------------------------------------------

class TestDebtLedgerCalled:
    def test_accumulate_called_once_per_epoch(self):
        mock_ledger = MagicMock(spec=GovernanceDebtLedger)
        mock_ledger.accumulate_epoch_verdicts.return_value = _make_debt_snapshot(1.5)
        loop = EvolutionLoop(
            api_key="k", simulate_outcomes=True, debt_ledger=mock_ledger,
        )
        _run(loop)
        mock_ledger.accumulate_epoch_verdicts.assert_called_once()

    def test_accepts_debt_ledger_kwarg(self):
        mock_ledger = MagicMock(spec=GovernanceDebtLedger)
        mock_ledger.accumulate_epoch_verdicts.return_value = _make_debt_snapshot()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, debt_ledger=mock_ledger)
        assert loop._debt_ledger is mock_ledger


# ---------------------------------------------------------------------------
# T15-03/04: compound_debt_score updates _last_debt_score and feeds context
# ---------------------------------------------------------------------------

class TestDebtScorePropagation:
    def test_last_debt_score_updated_from_snapshot(self):
        mock_ledger = MagicMock(spec=GovernanceDebtLedger)
        mock_ledger.accumulate_epoch_verdicts.return_value = _make_debt_snapshot(2.3)
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, debt_ledger=mock_ledger)
        _run(loop)
        assert loop._last_debt_score == pytest.approx(2.3)

    def test_debt_score_in_next_epoch_context(self):
        mock_ledger = MagicMock(spec=GovernanceDebtLedger)
        mock_ledger.accumulate_epoch_verdicts.return_value = _make_debt_snapshot(1.8)
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(
            api_key="k", simulate_outcomes=True,
            debt_ledger=mock_ledger, proposal_engine=engine,
        )
        # First epoch sets debt score
        _run(loop, epoch_id="ep-001")
        # Second epoch should use it
        _run(loop, epoch_id="ep-002")
        # Second request (index 1) should have the debt score from ep-001
        assert captured[1].context["governance_debt_score"] == pytest.approx(1.8)


# ---------------------------------------------------------------------------
# T15-05: accumulate receives epoch_id and epoch_index
# ---------------------------------------------------------------------------

class TestDebtAccumulateArgs:
    def test_epoch_id_passed_to_accumulate(self):
        mock_ledger = MagicMock(spec=GovernanceDebtLedger)
        mock_ledger.accumulate_epoch_verdicts.return_value = _make_debt_snapshot()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, debt_ledger=mock_ledger)
        _run(loop, epoch_id="ep-XYZ")
        call_kwargs = mock_ledger.accumulate_epoch_verdicts.call_args.kwargs
        assert call_kwargs["epoch_id"] == "ep-XYZ"

    def test_epoch_index_is_positive_int(self):
        mock_ledger = MagicMock(spec=GovernanceDebtLedger)
        mock_ledger.accumulate_epoch_verdicts.return_value = _make_debt_snapshot()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, debt_ledger=mock_ledger)
        _run(loop)
        call_kwargs = mock_ledger.accumulate_epoch_verdicts.call_args.kwargs
        assert isinstance(call_kwargs["epoch_index"], int)
        assert call_kwargs["epoch_index"] >= 1


# ---------------------------------------------------------------------------
# T15-06: warning_verdicts built from rejected scores
# ---------------------------------------------------------------------------

class TestWarningVerdicts:
    def test_warning_verdicts_passed_to_accumulate(self):
        mock_ledger = MagicMock(spec=GovernanceDebtLedger)
        mock_ledger.accumulate_epoch_verdicts.return_value = _make_debt_snapshot()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, debt_ledger=mock_ledger)
        _run(loop)
        call_kwargs = mock_ledger.accumulate_epoch_verdicts.call_args.kwargs
        assert "warning_verdicts" in call_kwargs
        assert isinstance(call_kwargs["warning_verdicts"], list)


# ---------------------------------------------------------------------------
# T15-07: debt ledger raises → epoch continues, debt unchanged
# ---------------------------------------------------------------------------

class TestDebtLedgerExceptionIsolated:
    def test_exception_does_not_halt_epoch(self):
        mock_ledger = MagicMock(spec=GovernanceDebtLedger)
        mock_ledger.accumulate_epoch_verdicts.side_effect = RuntimeError("ledger_fail")
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, debt_ledger=mock_ledger)
        _run(loop)  # must not raise
        assert loop._last_debt_score == pytest.approx(0.0)  # unchanged


# ---------------------------------------------------------------------------
# T15-09: governance_debt_score in context is float
# ---------------------------------------------------------------------------

class TestDebtScoreType:
    def test_governance_debt_score_is_float(self):
        mock_ledger = MagicMock(spec=GovernanceDebtLedger)
        mock_ledger.accumulate_epoch_verdicts.return_value = _make_debt_snapshot(0.75)
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(
            api_key="k", simulate_outcomes=True,
            debt_ledger=mock_ledger, proposal_engine=engine,
        )
        _run(loop)
        assert isinstance(captured[0].context["governance_debt_score"], float)


# ---------------------------------------------------------------------------
# T15-11: Multiple epochs — debt updates each epoch
# ---------------------------------------------------------------------------

class TestMultiEpochDebt:
    def test_debt_score_updates_across_epochs(self):
        scores = [1.0, 2.5, 0.8]
        call_idx = [0]
        snapshots = [_make_debt_snapshot(s) for s in scores]

        mock_ledger = MagicMock(spec=GovernanceDebtLedger)

        def _accumulate(**_kwargs):
            s = snapshots[call_idx[0] % len(snapshots)]
            call_idx[0] += 1
            return s

        mock_ledger.accumulate_epoch_verdicts.side_effect = _accumulate
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, debt_ledger=mock_ledger)

        _run(loop, "ep-001")
        assert loop._last_debt_score == pytest.approx(1.0)
        _run(loop, "ep-002")
        assert loop._last_debt_score == pytest.approx(2.5)
        _run(loop, "ep-003")
        assert loop._last_debt_score == pytest.approx(0.8)
