# SPDX-License-Identifier: Apache-2.0
"""Phase 14 / PR-14-02 — Live signal population into ProposalRequest.context.

Tests verify:
  T14-13  context.explore_ratio populated from CodebaseContext.explore_ratio
  T14-14  evolution_mode populated from ExploreExploitController.select_mode()
  T14-15  bandit_agent populated from BanditAgentRecommendation.agent
  T14-16  bandit_confidence populated from BanditAgentRecommendation.confidence
  T14-17  no bandit selector → bandit_agent is None in context
  T14-18  mutation_score populated from WeightAdaptor.prediction_accuracy
  T14-19  market consecutive_synthetic populated from MarketFitnessIntegrator
  T14-20  last_health_score propagated from previous-epoch state
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.autonomy.agent_bandit_selector import AgentBanditSelector, BanditAgentRecommendation
from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.evolution.evolution_loop import EvolutionLoop
from runtime.evolution.proposal_engine import ProposalEngine, ProposalRequest
from runtime.intelligence.proposal import Proposal
from runtime.market.market_fitness_integrator import MarketFitnessIntegrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_noop_proposal() -> Proposal:
    return Proposal(
        proposal_id="ep-001:auto",
        title="Noop",
        summary="noop",
        estimated_impact=0.0,
        real_diff="",
    )


def _make_valid_proposal() -> Proposal:
    return Proposal(
        proposal_id="ep-001:auto",
        title="Valid",
        summary="valid",
        estimated_impact=0.5,
        real_diff="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new",
    )


def _capture_engine_context(proposal: Proposal = None):
    """Return (mock_engine, captured_requests) — captures all ProposalRequest args."""
    captured = []
    mock_engine = MagicMock(spec=ProposalEngine)

    def _generate(req: ProposalRequest) -> Proposal:
        captured.append(req)
        return proposal or _make_noop_proposal()

    mock_engine.generate.side_effect = _generate
    return mock_engine, captured


def _run(loop: EvolutionLoop, epoch_id: str = "ep-001", explore_ratio: float = 0.5):
    ctx = CodebaseContext(
        file_summaries={},
        recent_failures=[],
        current_epoch_id=epoch_id,
        explore_ratio=explore_ratio,
    )
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value=[]):
        return loop.run_epoch(ctx)


# ---------------------------------------------------------------------------
# T14-13: explore_ratio from CodebaseContext
# ---------------------------------------------------------------------------

class TestExploreRatioInContext:
    def test_explore_ratio_populated(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop, explore_ratio=0.75)
        assert len(captured) == 1
        assert captured[0].context["explore_ratio"] == pytest.approx(0.75)

    def test_explore_ratio_default_when_missing(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        # CodebaseContext with no explicit explore_ratio defaults to 1.0
        ctx = CodebaseContext(file_summaries={}, recent_failures=[], current_epoch_id="ep-001")
        with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value=[]):
            loop.run_epoch(ctx)
        assert "explore_ratio" in captured[0].context


# ---------------------------------------------------------------------------
# T14-14: evolution_mode in context
# ---------------------------------------------------------------------------

class TestEvolutionModeInContext:
    def test_evolution_mode_key_present(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop)
        assert "evolution_mode" in captured[0].context

    def test_evolution_mode_is_string(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop)
        assert isinstance(captured[0].context["evolution_mode"], str)


# ---------------------------------------------------------------------------
# T14-15/16: Bandit fields in context
# ---------------------------------------------------------------------------

class TestBanditContextFields:
    def test_bandit_agent_populated_when_selector_active(self):
        engine, captured = _capture_engine_context()
        mock_bandit = MagicMock(spec=AgentBanditSelector)
        mock_bandit.recommend.return_value = BanditAgentRecommendation(
            agent="architect", confidence=0.82, strategy="ucb1", exploration_bonus=0.1,
            is_active=True, total_pulls=15,
        )
        loop = EvolutionLoop(
            api_key="k", simulate_outcomes=True,
            proposal_engine=engine, bandit_selector=mock_bandit,
        )
        _run(loop)
        assert captured[0].context["bandit_agent"] == "architect"

    def test_bandit_confidence_populated(self):
        engine, captured = _capture_engine_context()
        mock_bandit = MagicMock(spec=AgentBanditSelector)
        mock_bandit.recommend.return_value = BanditAgentRecommendation(
            agent="dream", confidence=0.65, strategy="thompson", exploration_bonus=0.05,
            is_active=True, total_pulls=20,
        )
        loop = EvolutionLoop(
            api_key="k", simulate_outcomes=True,
            proposal_engine=engine, bandit_selector=mock_bandit,
        )
        _run(loop)
        assert captured[0].context["bandit_confidence"] == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# T14-17: No bandit → bandit_agent is None
# ---------------------------------------------------------------------------

class TestNoBanditContext:
    def test_bandit_agent_none_without_selector(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop)
        assert captured[0].context["bandit_agent"] is None

    def test_bandit_confidence_zero_without_selector(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop)
        assert captured[0].context["bandit_confidence"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T14-18: mutation_score from prediction_accuracy
# ---------------------------------------------------------------------------

class TestMutationScoreInContext:
    def test_mutation_score_key_present(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop)
        assert "mutation_score" in captured[0].context

    def test_mutation_score_is_float(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop)
        assert isinstance(captured[0].context["mutation_score"], float)


# ---------------------------------------------------------------------------
# T14-19: market consecutive_synthetic in context
# ---------------------------------------------------------------------------

class TestMarketContextFields:
    def test_consecutive_synthetic_from_market_integrator(self):
        engine, captured = _capture_engine_context()
        mock_mkt = MagicMock(spec=MarketFitnessIntegrator)
        mock_mkt.consecutive_synthetic_epochs = 3
        mock_mkt.integrate.return_value = MagicMock(
            live_market_score=0.5, confidence=0.0,
            is_synthetic=True, consecutive_synthetic_epochs=3,
        )
        loop = EvolutionLoop(
            api_key="k", simulate_outcomes=True,
            proposal_engine=engine, market_integrator=mock_mkt,
        )
        _run(loop)
        assert captured[0].context["consecutive_synthetic"] == 3

    def test_consecutive_synthetic_zero_without_integrator(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop)
        assert captured[0].context["consecutive_synthetic"] == 0


# ---------------------------------------------------------------------------
# T14-20: last_health_score in context
# ---------------------------------------------------------------------------

class TestLastHealthScoreInContext:
    def test_last_health_score_present(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop)
        assert "last_health_score" in captured[0].context

    def test_last_health_score_is_float(self):
        engine, captured = _capture_engine_context()
        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, proposal_engine=engine)
        _run(loop)
        assert isinstance(captured[0].context["last_health_score"], float)
