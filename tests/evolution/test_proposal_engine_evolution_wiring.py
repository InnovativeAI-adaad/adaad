# SPDX-License-Identifier: Apache-2.0
"""Phase 14 / PR-14-01 — ProposalEngine → EvolutionLoop Phase 1e wiring.

Tests verify:
  T14-01  proposal_engine absent → Phase 1e skipped; existing proposals unchanged
  T14-02  proposal_engine injected → generate() called once per run_epoch()
  T14-03  noop proposal (empty real_diff) → silently skipped, not added to candidates
  T14-04  valid proposal with real_diff → MutationCandidate appended to all_proposals
  T14-05  generate() raises → exception isolated, epoch continues, no crash
  T14-06  _proposal_to_candidate: field mapping (mutation_id, agent_origin, expected_gain)
  T14-07  _proposal_to_candidate: risk_score from projected_impact
  T14-08  _proposal_to_candidate: returns None on empty diff
  T14-09  _proposal_to_candidate: operator_category == "llm_strategy"
  T14-10  _proposal_to_candidate: operator_version == "14.0.0"
  T14-11  MutationCandidate from engine has agent_origin == "proposal_engine"
  T14-12  total_candidates incremented when engine proposal accepted
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.autonomy.mutation_scaffold import MutationCandidate
from runtime.evolution.evolution_loop import EvolutionLoop, _proposal_to_candidate, EpochResult
from runtime.evolution.proposal_engine import ProposalEngine, ProposalRequest
from runtime.intelligence.proposal import Proposal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proposal(real_diff: str = "", estimated_impact: float = 0.5) -> Proposal:
    return Proposal(
        proposal_id="ep-001:auto",
        title="Test proposal",
        summary="Test summary",
        estimated_impact=estimated_impact,
        real_diff=real_diff,
        projected_impact={"risk": 0.3, "complexity": 0.4, "coverage_delta": 0.05},
        metadata={"cycle_id": "ep-001", "strategy_id": "auto"},
    )


def _make_loop(proposal_engine=None) -> EvolutionLoop:
    return EvolutionLoop(
        api_key="test",
        simulate_outcomes=True,
        proposal_engine=proposal_engine,
    )


def _run_loop(loop: EvolutionLoop) -> EpochResult:
    ctx = CodebaseContext(
        file_summaries={},
        recent_failures=[],
        current_epoch_id="ep-001",
    )
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value=[]):
        return loop.run_epoch(ctx)


# ---------------------------------------------------------------------------
# T14-01: No proposal_engine → unchanged behaviour
# ---------------------------------------------------------------------------

class TestNoProposalEngine:
    def test_no_engine_epoch_completes(self):
        loop = _make_loop(proposal_engine=None)
        result = _run_loop(loop)
        assert isinstance(result, EpochResult)

    def test_no_engine_no_engine_proposals_in_result(self):
        loop = _make_loop(proposal_engine=None)
        result = _run_loop(loop)
        # No crash; total_candidates == 0 from empty propose_from_all_agents
        assert result.total_candidates == 0


# ---------------------------------------------------------------------------
# T14-02: Engine injected → generate() called once per epoch
# ---------------------------------------------------------------------------

class TestEngineCalledPerEpoch:
    def test_generate_called_once(self):
        mock_engine = MagicMock(spec=ProposalEngine)
        mock_engine.generate.return_value = _make_proposal(real_diff="")
        loop = _make_loop(proposal_engine=mock_engine)
        _run_loop(loop)
        mock_engine.generate.assert_called_once()

    def test_generate_called_with_proposal_request(self):
        mock_engine = MagicMock(spec=ProposalEngine)
        mock_engine.generate.return_value = _make_proposal(real_diff="")
        loop = _make_loop(proposal_engine=mock_engine)
        _run_loop(loop)
        call_args = mock_engine.generate.call_args
        req = call_args[0][0] if call_args[0] else call_args.args[0]
        assert isinstance(req, ProposalRequest)
        assert req.strategy_id == "auto"
        assert req.cycle_id == "ep-001"


# ---------------------------------------------------------------------------
# T14-03: Noop proposal → silently skipped
# ---------------------------------------------------------------------------

class TestNoopProposalSkipped:
    def test_noop_not_added_to_candidates(self):
        mock_engine = MagicMock(spec=ProposalEngine)
        mock_engine.generate.return_value = _make_proposal(real_diff="")
        loop = _make_loop(proposal_engine=mock_engine)
        result = _run_loop(loop)
        assert result.total_candidates == 0

    def test_noop_epoch_still_completes(self):
        mock_engine = MagicMock(spec=ProposalEngine)
        mock_engine.generate.return_value = _make_proposal(real_diff="")
        loop = _make_loop(proposal_engine=mock_engine)
        result = _run_loop(loop)
        assert isinstance(result, EpochResult)


# ---------------------------------------------------------------------------
# T14-04: Valid proposal → MutationCandidate in candidates
# ---------------------------------------------------------------------------

class TestValidProposalAddedToCandidates:
    def test_candidate_count_incremented(self):
        mock_engine = MagicMock(spec=ProposalEngine)
        mock_engine.generate.return_value = _make_proposal(
            real_diff="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new",
        )
        loop = _make_loop(proposal_engine=mock_engine)
        result = _run_loop(loop)
        assert result.total_candidates >= 1


# ---------------------------------------------------------------------------
# T14-05: generate() raises → epoch continues, no crash
# ---------------------------------------------------------------------------

class TestEngineRaisesIsolated:
    def test_exception_does_not_halt_epoch(self):
        mock_engine = MagicMock(spec=ProposalEngine)
        mock_engine.generate.side_effect = RuntimeError("llm_timeout")
        loop = _make_loop(proposal_engine=mock_engine)
        result = _run_loop(loop)  # must not raise
        assert isinstance(result, EpochResult)

    def test_candidates_unchanged_on_engine_failure(self):
        mock_engine = MagicMock(spec=ProposalEngine)
        mock_engine.generate.side_effect = RuntimeError("llm_timeout")
        loop = _make_loop(proposal_engine=mock_engine)
        result = _run_loop(loop)
        assert result.total_candidates == 0


# ---------------------------------------------------------------------------
# T14-06 to T14-11: _proposal_to_candidate bridge
# ---------------------------------------------------------------------------

class TestProposalToCandidateBridge:
    def _make(self, **kwargs) -> Proposal:
        defaults = dict(
            proposal_id="ep-001:auto",
            title="T",
            summary="S",
            estimated_impact=0.75,
            real_diff="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new",
            projected_impact={"risk": 0.3, "complexity": 0.4, "coverage_delta": 0.02},
            metadata={},
        )
        defaults.update(kwargs)
        return Proposal(**defaults)

    def test_returns_none_on_empty_diff(self):
        proposal = self._make(real_diff="")
        result = _proposal_to_candidate(proposal, epoch_id="ep-001")
        assert result is None

    def test_mutation_id_matches_proposal_id(self):
        proposal = self._make()
        result = _proposal_to_candidate(proposal, epoch_id="ep-001")
        assert result is not None
        assert result.mutation_id == "ep-001:auto"

    def test_agent_origin_is_proposal_engine(self):
        proposal = self._make()
        result = _proposal_to_candidate(proposal, epoch_id="ep-001")
        assert result is not None
        assert result.agent_origin == "proposal_engine"

    def test_expected_gain_from_estimated_impact(self):
        proposal = self._make(estimated_impact=0.72)
        result = _proposal_to_candidate(proposal, epoch_id="ep-001")
        assert result is not None
        assert result.expected_gain == pytest.approx(0.72)

    def test_risk_score_from_projected_impact(self):
        proposal = self._make(projected_impact={"risk": 0.65})
        result = _proposal_to_candidate(proposal, epoch_id="ep-001")
        assert result is not None
        assert result.risk_score == pytest.approx(0.65)

    def test_operator_category_is_llm_strategy(self):
        proposal = self._make()
        result = _proposal_to_candidate(proposal, epoch_id="ep-001")
        assert result is not None
        assert result.operator_category == "llm_strategy"

    def test_operator_version_is_14(self):
        proposal = self._make()
        result = _proposal_to_candidate(proposal, epoch_id="ep-001")
        assert result is not None
        assert result.operator_version == "14.0.0"

    def test_epoch_id_propagated(self):
        proposal = self._make()
        result = _proposal_to_candidate(proposal, epoch_id="ep-XYZ")
        assert result is not None
        assert result.epoch_id == "ep-XYZ"

    def test_python_content_is_real_diff(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new"
        proposal = self._make(real_diff=diff)
        result = _proposal_to_candidate(proposal, epoch_id="ep-001")
        assert result is not None
        assert result.python_content == diff

    def test_returns_mutation_candidate_instance(self):
        proposal = self._make()
        result = _proposal_to_candidate(proposal, epoch_id="ep-001")
        assert isinstance(result, MutationCandidate)
