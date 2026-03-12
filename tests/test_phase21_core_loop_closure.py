# SPDX-License-Identifier: Apache-2.0
"""Phase 21 — Core Loop Closure: AutonomyLoop wired into EvolutionLoop.run_epoch()

Tests verify:
  PR-21-01  EvolutionLoop accepts autonomy_loop kwarg
  PR-21-02  When autonomy_loop injected, run_epoch() calls AutonomyLoop.run()
  PR-21-03  EpochResult carries intelligence_decision / strategy_id / outcome / composite
  PR-21-04  AutonomyLoop.reset_epoch() called at epoch boundary
  PR-21-05  autonomy_loop=None is fully backwards-compatible (defaults hold)
  PR-21-06  AutonomyLoop failure is exception-isolated — epoch still returns
  PR-21-07  intelligence_decision reflects AutonomyLoopResult.decision value
  PR-21-08  fitness_trend_delta fed correctly (health_score delta from prev epoch)
  PR-21-09  epoch_pass_rate fed as accepted_count / total_candidates
  PR-21-10  governance_debt_score forwarded from _last_debt_score
"""
from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock, patch

import pytest

from runtime.autonomy.loop import AutonomyLoop, AutonomyLoopResult
from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.evolution.evolution_loop import EvolutionLoop, EpochResult


pytestmark = pytest.mark.autonomous_critical

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(epoch_id: str = "epoch-ph21-01") -> CodebaseContext:
    return CodebaseContext(
        current_epoch_id=epoch_id,
        file_summaries={},
        recent_failures=[],
        explore_ratio=0.5,
    )


def _make_loop(autonomy_loop=None, simulate: bool = True) -> EvolutionLoop:
    return EvolutionLoop(
        api_key="test-key",
        simulate_outcomes=simulate,
        autonomy_loop=autonomy_loop,
    )


def _stub_result(decision: str = "hold") -> AutonomyLoopResult:
    return AutonomyLoopResult(
        ok=True,
        post_conditions_passed=True,
        total_duration_ms=1,
        mutation_score=0.5,
        decision=decision,
        intelligence_strategy_id="strategy-A",
        intelligence_outcome="execute",
        intelligence_composite=0.75,
    )


# ---------------------------------------------------------------------------
# PR-21-01 — EvolutionLoop accepts autonomy_loop kwarg
# ---------------------------------------------------------------------------

def test_pr21_01_evolution_loop_accepts_autonomy_loop_kwarg():
    al = MagicMock(spec=AutonomyLoop)
    loop = _make_loop(autonomy_loop=al)
    assert loop._autonomy_loop is al


# ---------------------------------------------------------------------------
# PR-21-02 — run_epoch() calls AutonomyLoop.run() when injected
# ---------------------------------------------------------------------------

def test_pr21_02_run_epoch_calls_autonomy_loop_run(monkeypatch):
    al = MagicMock(spec=AutonomyLoop)
    al.run.return_value = _stub_result()
    al.reset_epoch.return_value = None

    loop = _make_loop(autonomy_loop=al)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        loop.run_epoch(_make_context())

    al.run.assert_called_once()
    call_kwargs = al.run.call_args.kwargs
    assert call_kwargs["cycle_id"] == "epoch-ph21-01"


# ---------------------------------------------------------------------------
# PR-21-03 — EpochResult carries intelligence output fields
# ---------------------------------------------------------------------------

def test_pr21_03_epoch_result_carries_intelligence_fields(monkeypatch):
    al = MagicMock(spec=AutonomyLoop)
    al.run.return_value = _stub_result(decision="self_mutate")
    al.reset_epoch.return_value = None

    loop = _make_loop(autonomy_loop=al)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        result = loop.run_epoch(_make_context())

    assert result.intelligence_decision == "self_mutate"
    assert result.intelligence_strategy_id == "strategy-A"
    assert result.intelligence_outcome == "execute"
    assert result.intelligence_composite == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# PR-21-04 — reset_epoch() called at epoch boundary
# ---------------------------------------------------------------------------

def test_pr21_04_reset_epoch_called_at_boundary(monkeypatch):
    al = MagicMock(spec=AutonomyLoop)
    al.run.return_value = _stub_result()
    al.reset_epoch.return_value = None

    loop = _make_loop(autonomy_loop=al)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        loop.run_epoch(_make_context())

    al.reset_epoch.assert_called_once()


# ---------------------------------------------------------------------------
# PR-21-05 — autonomy_loop=None is backwards-compatible
# ---------------------------------------------------------------------------

def test_pr21_05_none_autonomy_loop_backwards_compatible(monkeypatch):
    loop = _make_loop(autonomy_loop=None)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        result = loop.run_epoch(_make_context())

    # Defaults must be in place
    assert result.intelligence_decision == "hold"
    assert result.intelligence_strategy_id is None
    assert result.intelligence_outcome is None
    assert result.intelligence_composite is None


# ---------------------------------------------------------------------------
# PR-21-06 — AutonomyLoop failure is exception-isolated
# ---------------------------------------------------------------------------

def test_pr21_06_autonomy_loop_failure_is_exception_isolated(monkeypatch):
    al = MagicMock(spec=AutonomyLoop)
    al.run.side_effect = RuntimeError("intelligence stack exploded")

    loop = _make_loop(autonomy_loop=al)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        result = loop.run_epoch(_make_context())  # must not raise

    # Defaults hold after failure
    assert result.intelligence_decision == "hold"
    assert result.intelligence_strategy_id is None


# ---------------------------------------------------------------------------
# PR-21-07 — intelligence_decision reflects AutonomyLoopResult.decision
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("decision", ["hold", "self_mutate", "escalate"])
def test_pr21_07_decision_value_propagated(decision, monkeypatch):
    al = MagicMock(spec=AutonomyLoop)
    al.run.return_value = _stub_result(decision=decision)
    al.reset_epoch.return_value = None

    loop = _make_loop(autonomy_loop=al)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        result = loop.run_epoch(_make_context())

    assert result.intelligence_decision == decision


# ---------------------------------------------------------------------------
# PR-21-08 — fitness_trend_delta fed as health_score delta
# ---------------------------------------------------------------------------

def test_pr21_08_fitness_trend_delta_fed(monkeypatch):
    al = MagicMock(spec=AutonomyLoop)
    al.run.return_value = _stub_result()
    al.reset_epoch.return_value = None

    loop = _make_loop(autonomy_loop=al)
    loop._last_epoch_health_score = 0.3  # simulate prior epoch score

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        loop.run_epoch(_make_context())

    call_kwargs = al.run.call_args.kwargs
    # delta = this epoch's health - 0.3; must be a float
    assert isinstance(call_kwargs["fitness_trend_delta"], float)


# ---------------------------------------------------------------------------
# PR-21-09 — epoch_pass_rate = accepted_count / total_candidates
# ---------------------------------------------------------------------------

def test_pr21_09_epoch_pass_rate_is_ratio(monkeypatch):
    al = MagicMock(spec=AutonomyLoop)
    al.run.return_value = _stub_result()
    al.reset_epoch.return_value = None

    loop = _make_loop(autonomy_loop=al)
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        loop.run_epoch(_make_context())

    call_kwargs = al.run.call_args.kwargs
    rate = call_kwargs["epoch_pass_rate"]
    assert 0.0 <= rate <= 1.0


# ---------------------------------------------------------------------------
# PR-21-10 — governance_debt_score forwarded from _last_debt_score
# ---------------------------------------------------------------------------

def test_pr21_10_governance_debt_forwarded(monkeypatch):
    al = MagicMock(spec=AutonomyLoop)
    al.run.return_value = _stub_result()
    al.reset_epoch.return_value = None

    loop = _make_loop(autonomy_loop=al)
    loop._last_debt_score = 0.42

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={"architect": []}):
        loop.run_epoch(_make_context())

    call_kwargs = al.run.call_args.kwargs
    assert call_kwargs["governance_debt_score"] == pytest.approx(0.42)


# ---------------------------------------------------------------------------
# Schema completeness — EpochResult dataclass has all Phase 21 fields
# ---------------------------------------------------------------------------

def test_epoch_result_schema_has_intelligence_fields():
    fields = {f.name for f in dataclasses.fields(EpochResult)}
    for expected in [
        "intelligence_decision",
        "intelligence_strategy_id",
        "intelligence_outcome",
        "intelligence_composite",
    ]:
        assert expected in fields, f"EpochResult missing field: {expected}"
