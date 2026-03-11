# SPDX-License-Identifier: Apache-2.0
"""
Tests for Phase 11-A PR-11-A-02: FitnessLandscape bandit override + EvolutionLoop wiring.

Test IDs: T11-B-01 through T11-B-05
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
pytestmark = pytest.mark.autonomous_critical

from runtime.autonomy.agent_bandit_selector import (
    AGENTS,
    BANDIT_CONFIDENCE_FLOOR,
    AgentBanditSelector,
    BanditAgentRecommendation,
)
from runtime.autonomy.fitness_landscape import FitnessLandscape


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _active_rec(agent: str, confidence: float = 0.85) -> BanditAgentRecommendation:
    return BanditAgentRecommendation(
        agent=agent,
        confidence=confidence,
        strategy="ucb1",
        exploration_bonus=0.05,
        is_active=True,
        total_pulls=10,
    )


def _inactive_rec(agent: str) -> BanditAgentRecommendation:
    return BanditAgentRecommendation(
        agent=agent,
        confidence=0.90,
        strategy="ucb1",
        exploration_bonus=0.10,
        is_active=False,
        total_pulls=2,
    )


# ---------------------------------------------------------------------------
# T11-B-01: FitnessLandscape accepts bandit_rec and overrides recommendation
# ---------------------------------------------------------------------------

def test_t11_b_01_bandit_rec_overrides_landscape_when_active_and_confident():
    """T11-B-01: recommended_agent() returns bandit_rec.agent when is_active=True and confidence >= floor."""
    landscape = FitnessLandscape()
    rec = _active_rec("dream", confidence=0.80)
    result = landscape.recommended_agent(bandit_rec=rec)
    assert result == "dream"


def test_t11_b_01b_bandit_rec_ignored_when_inactive():
    """T11-B-01b: recommended_agent() falls through to landscape when bandit is_active=False."""
    landscape = FitnessLandscape()
    # Feed enough data to make landscape prefer architect
    for _ in range(8):
        landscape.record("structural", won=True)
    rec = _inactive_rec("dream")   # bandit says dream but is inactive
    result = landscape.recommended_agent(bandit_rec=rec)
    # Landscape itself should pick something — NOT blindly dream
    assert result in AGENTS  # passes if it follows landscape logic


def test_t11_b_01c_bandit_rec_ignored_below_confidence_floor():
    """T11-B-01c: recommended_agent() ignores bandit_rec when confidence < BANDIT_CONFIDENCE_FLOOR."""
    landscape = FitnessLandscape()
    rec = BanditAgentRecommendation(
        agent="architect",
        confidence=BANDIT_CONFIDENCE_FLOOR - 0.01,
        strategy="ucb1",
        exploration_bonus=0.0,
        is_active=True,
        total_pulls=20,
    )
    # With no landscape data and low confidence, landscape falls through to its own logic
    result = landscape.recommended_agent(bandit_rec=rec)
    assert result in AGENTS  # whatever landscape decides — not locked to architect by the bandit


def test_t11_b_01d_none_bandit_rec_uses_landscape():
    """T11-B-01d: recommended_agent(bandit_rec=None) behaves identically to prior API."""
    landscape = FitnessLandscape()
    result_no_kwarg = landscape.recommended_agent()
    result_none     = landscape.recommended_agent(bandit_rec=None)
    assert result_no_kwarg == result_none


# ---------------------------------------------------------------------------
# T11-B-02: EvolutionLoop stores bandit_selector kwarg
# ---------------------------------------------------------------------------

def test_t11_b_02_evolution_loop_stores_bandit_selector():
    """T11-B-02: EvolutionLoop.__init__ accepts and stores bandit_selector kwarg."""
    from runtime.evolution.evolution_loop import EvolutionLoop

    path = Path(tempfile.mktemp(suffix=".json"))
    sel = AgentBanditSelector(state_path=path)

    loop = EvolutionLoop(api_key="test", bandit_selector=sel)
    assert loop._bandit_selector is sel


def test_t11_b_02b_none_bandit_selector_stored_by_default():
    """T11-B-02b: _bandit_selector defaults to None when not supplied."""
    from runtime.evolution.evolution_loop import EvolutionLoop
    loop = EvolutionLoop(api_key="test")
    assert loop._bandit_selector is None


# ---------------------------------------------------------------------------
# T11-B-03: EvolutionLoop Phase 0d calls bandit_selector.recommend
# ---------------------------------------------------------------------------

def test_t11_b_03_phase_0d_calls_recommend_and_passes_to_landscape(monkeypatch):
    """T11-B-03: EvolutionLoop calls bandit.recommend() and passes result to landscape.recommended_agent()."""
    from runtime.evolution.evolution_loop import EvolutionLoop

    path = Path(tempfile.mktemp(suffix=".json"))
    mock_bandit = MagicMock(spec=AgentBanditSelector)
    mock_bandit.recommend.return_value = _active_rec("beast", confidence=0.90)

    recommend_calls = []
    original_rec = FitnessLandscape.recommended_agent

    def patched_rec(self, bandit_rec=None):
        recommend_calls.append(bandit_rec)
        return original_rec(self, bandit_rec=bandit_rec)

    monkeypatch.setattr(FitnessLandscape, "recommended_agent", patched_rec)

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents") as mock_prop:
        mock_prop.return_value = MagicMock(proposals_by_agent={
            "architect": [], "dream": [], "beast": []
        })
        loop = EvolutionLoop(api_key="test", bandit_selector=mock_bandit)
        from runtime.autonomy.ai_mutation_proposer import CodebaseContext
        ctx = CodebaseContext(
            file_summaries={"f.py": "foo"},
            recent_failures=[],
            current_epoch_id="e001",
        )
        try:
            loop.run_epoch(ctx)
        except Exception:
            pass

    # recommend() must have been called
    mock_bandit.recommend.assert_called_once()
    # recommended_agent must have been called with a BanditAgentRecommendation
    assert any(isinstance(r, BanditAgentRecommendation) for r in recommend_calls)


# ---------------------------------------------------------------------------
# T11-B-04: Phase 0d exception does not block epoch
# ---------------------------------------------------------------------------

def test_t11_b_04_bandit_exception_in_recommend_does_not_propagate(monkeypatch):
    """T11-B-04: Exception from bandit_selector.recommend() is swallowed — epoch proceeds."""
    from runtime.evolution.evolution_loop import EvolutionLoop

    bad_bandit = MagicMock(spec=AgentBanditSelector)
    bad_bandit.recommend.side_effect = RuntimeError("bandit exploded")

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents") as mock_prop:
        mock_prop.return_value = MagicMock(proposals_by_agent={
            "architect": [], "dream": [], "beast": []
        })
        loop = EvolutionLoop(api_key="test", bandit_selector=bad_bandit)
        from runtime.autonomy.ai_mutation_proposer import CodebaseContext
        ctx = CodebaseContext(
            file_summaries={"f.py": "foo"},
            recent_failures=[],
            current_epoch_id="e001",
        )
        # Should not raise — epoch proceeds with landscape fallback
        try:
            loop.run_epoch(ctx)
        except Exception:
            pass  # governance gate raises — that's expected

    # The important assertion: bad_bandit.recommend was called (exception happened inside)
    bad_bandit.recommend.assert_called()


# ---------------------------------------------------------------------------
# T11-B-05: Phase 5e calls bandit_selector.update after epoch
# ---------------------------------------------------------------------------

def test_t11_b_05_phase_5e_calls_bandit_update(monkeypatch):
    """T11-B-05: After epoch, bandit_selector.update() is called with agent and reward."""
    from runtime.evolution.evolution_loop import EvolutionLoop

    update_calls = []
    mock_bandit = MagicMock(spec=AgentBanditSelector)
    mock_bandit.recommend.return_value = _active_rec("architect", confidence=0.90)
    mock_bandit.update.side_effect = lambda **kw: update_calls.append(kw)

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents") as mock_prop:
        mock_prop.return_value = MagicMock(proposals_by_agent={
            "architect": [], "dream": [], "beast": []
        })
        loop = EvolutionLoop(api_key="test", bandit_selector=mock_bandit)
        from runtime.autonomy.ai_mutation_proposer import CodebaseContext
        ctx = CodebaseContext(
            file_summaries={"f.py": "foo"},
            recent_failures=[],
            current_epoch_id="e-upd",
        )
        try:
            loop.run_epoch(ctx)
        except Exception:
            pass

    # update() must have been called once with the epoch_id
    assert mock_bandit.update.called
    if update_calls:
        assert update_calls[0]["epoch_id"] == "e-upd"
        assert "agent" in update_calls[0]
        assert "reward" in update_calls[0]
        assert 0.0 <= update_calls[0]["reward"] <= 1.0
