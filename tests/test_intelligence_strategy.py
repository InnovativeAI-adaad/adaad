import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from runtime.intelligence.strategy import StrategyInput, StrategyModule


def test_select_prioritizes_immediate_gain_when_mutation_signal_is_dominant() -> None:
    """Phase 16 note: fixture uses debt=0.30 and lineage=0.65 to isolate
    adaptive_self_mutate — avoiding safety_hardening (debt>=0.70) and
    structural_refactor (lineage<0.50) triggers."""
    module = StrategyModule()

    decision = module.select(
        StrategyInput(
            cycle_id="cycle-immediate",
            mutation_score=0.95,
            governance_debt_score=0.30,  # below safety_hardening threshold
            horizon_cycles=2,
            resource_budget=0.90,
            goal_backlog={"fast_patch": 0.5, "cleanup": 0.2},
            lineage_health=0.65,  # above structural_refactor threshold
        )
    )

    assert decision.strategy_id == "adaptive_self_mutate"
    assert decision.goal_plan[0] == "deliver_immediate_mutation_gain"
    assert decision.priority_queue[0] == "adaptive_self_mutate"
    assert decision.confidence > 0.55


def test_select_prioritizes_medium_term_stability_under_long_horizon_pressure() -> None:
    module = StrategyModule()

    decision = module.select(
        StrategyInput(
            cycle_id="cycle-medium",
            mutation_score=0.35,
            governance_debt_score=0.05,
            horizon_cycles=12,
            resource_budget=0.4,
            goal_backlog={"refactor": 0.1},
            lineage_health=0.98,
        )
    )

    assert decision.strategy_id == "conservative_hold"
    assert "preserve_lineage_health" in decision.goal_plan[:2]
    assert decision.priority_queue[0] == "conservative_hold"
    assert 0.55 <= decision.confidence <= 1.0
