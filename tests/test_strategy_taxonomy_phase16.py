# SPDX-License-Identifier: Apache-2.0
"""Phase 16 — StrategyModule Taxonomy tests (18 tests, T16-01-01..18)."""

import pytest

from runtime.intelligence.strategy import (
    STRATEGY_TAXONOMY,
    StrategyDecision,
    StrategyInput,
    StrategyModule,
)

module = StrategyModule()


# ---------------------------------------------------------------------------
# T16-01-01  STRATEGY_TAXONOMY contains exactly 6 strategies
# ---------------------------------------------------------------------------
def test_taxonomy_has_six_strategies() -> None:
    assert len(STRATEGY_TAXONOMY) == 6
    expected = {
        "adaptive_self_mutate",
        "conservative_hold",
        "structural_refactor",
        "test_coverage_expansion",
        "performance_optimization",
        "safety_hardening",
    }
    assert STRATEGY_TAXONOMY == expected


# ---------------------------------------------------------------------------
# T16-01-02  StrategyDecision rejects unknown strategy_id
# ---------------------------------------------------------------------------
def test_strategy_decision_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="not in STRATEGY_TAXONOMY"):
        StrategyDecision(
            strategy_id="ghost_strategy",
            rationale="test",
            confidence=0.8,
        )


# ---------------------------------------------------------------------------
# T16-01-03  safety_hardening fires on critical debt (>= 0.70)
# ---------------------------------------------------------------------------
def test_safety_hardening_fires_on_critical_debt() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-safety",
            mutation_score=0.50,
            governance_debt_score=0.75,
            horizon_cycles=3,
            resource_budget=0.60,
            lineage_health=0.85,
        )
    )
    assert decision.strategy_id == "safety_hardening"


# ---------------------------------------------------------------------------
# T16-01-04  safety_hardening beats structural_refactor when both qualify
# ---------------------------------------------------------------------------
def test_safety_hardening_beats_structural_refactor() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-priority",
            mutation_score=0.40,
            governance_debt_score=0.80,  # critical -> safety_hardening
            horizon_cycles=2,
            resource_budget=0.50,
            lineage_health=0.20,  # low -> structural_refactor also qualifies
        )
    )
    assert decision.strategy_id == "safety_hardening"
    assert "structural_refactor" in decision.priority_queue


# ---------------------------------------------------------------------------
# T16-01-05  structural_refactor fires when lineage_health < 0.50
# ---------------------------------------------------------------------------
def test_structural_refactor_fires_on_low_lineage() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-refactor",
            mutation_score=0.40,
            governance_debt_score=0.30,
            horizon_cycles=3,
            resource_budget=0.50,
            lineage_health=0.25,
        )
    )
    assert decision.strategy_id == "structural_refactor"


# ---------------------------------------------------------------------------
# T16-01-06  test_coverage_expansion fires on elevated (not critical) debt
# ---------------------------------------------------------------------------
def test_test_coverage_expansion_on_elevated_debt() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-test-cov",
            mutation_score=0.30,
            governance_debt_score=0.62,  # >= 0.55 but < 0.70
            horizon_cycles=4,
            resource_budget=0.45,
            lineage_health=0.72,
        )
    )
    assert decision.strategy_id == "test_coverage_expansion"


# ---------------------------------------------------------------------------
# T16-01-07  performance_optimization fires on high mutation + market pressure
#             Fixture: mutation_score in [0.60, 0.70) so adaptive_self_mutate
#             does NOT qualify; market pressure ensures perf_opt fires.
# ---------------------------------------------------------------------------
def test_performance_optimization_fires_on_market_pressure() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-perf",
            mutation_score=0.65,  # >= 0.60 (perf_opt) but < 0.70 (adaptive)
            governance_debt_score=0.10,
            horizon_cycles=2,
            resource_budget=0.80,
            lineage_health=0.90,
            signals={"market_fitness_score": 0.65},
        )
    )
    assert decision.strategy_id == "performance_optimization"


# ---------------------------------------------------------------------------
# T16-01-08  adaptive_self_mutate fires when no higher-priority strategy qualifies
# ---------------------------------------------------------------------------
def test_adaptive_self_mutate_fires_in_isolation() -> None:
    """Fixture isolates adaptive_self_mutate: debt < 0.55, lineage >= 0.50,
    no market pressure, high mutation + budget."""
    decision = module.select(
        StrategyInput(
            cycle_id="c-adaptive",
            mutation_score=0.90,
            governance_debt_score=0.10,  # below test_coverage threshold
            horizon_cycles=2,
            resource_budget=0.85,
            goal_backlog={"fast_patch": 0.3},
            lineage_health=0.65,  # above structural_refactor threshold
            signals={},  # no market pressure
        )
    )
    assert decision.strategy_id == "adaptive_self_mutate"
    assert decision.confidence >= 0.55


# ---------------------------------------------------------------------------
# T16-01-09  conservative_hold preserved under original trigger conditions
# ---------------------------------------------------------------------------
def test_conservative_hold_preserved_for_long_horizon_stable_lineage() -> None:
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


# ---------------------------------------------------------------------------
# T16-01-10  priority_queue always includes all evaluated candidates
# ---------------------------------------------------------------------------
def test_priority_queue_lists_all_candidates() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-all",
            mutation_score=0.80,
            governance_debt_score=0.75,
            horizon_cycles=10,
            resource_budget=0.85,
            lineage_health=0.20,
            signals={"market_fitness_score": 0.70},
        )
    )
    # Should have multiple candidates
    assert len(decision.priority_queue) >= 3
    assert decision.strategy_id == decision.priority_queue[0]


# ---------------------------------------------------------------------------
# T16-01-11  determinism — same input always yields same decision
# ---------------------------------------------------------------------------
def test_strategy_selection_is_deterministic() -> None:
    inp = StrategyInput(
        cycle_id="c-det",
        mutation_score=0.65,
        governance_debt_score=0.40,
        horizon_cycles=6,
        resource_budget=0.70,
        lineage_health=0.55,
        signals={"market_fitness_score": 0.50},
    )
    results = [module.select(inp) for _ in range(5)]
    strategy_ids = {r.strategy_id for r in results}
    assert len(strategy_ids) == 1


# ---------------------------------------------------------------------------
# T16-01-12  confidence is always in [0.55, 1.0]
# ---------------------------------------------------------------------------
def test_confidence_bounds() -> None:
    inputs = [
        StrategyInput(cycle_id="b1", mutation_score=s, governance_debt_score=d,
                      lineage_health=l, horizon_cycles=h, resource_budget=0.5)
        for s, d, l, h in [
            (0.0, 0.0, 1.0, 12),
            (1.0, 1.0, 0.0, 1),
            (0.5, 0.5, 0.5, 6),
            (0.8, 0.72, 0.8, 9),
        ]
    ]
    for inp in inputs:
        dec = module.select(inp)
        assert 0.55 <= dec.confidence <= 1.0, f"confidence {dec.confidence} out of range"


# ---------------------------------------------------------------------------
# T16-01-13  parameters contains strategy_taxonomy_version "16.0"
# ---------------------------------------------------------------------------
def test_parameters_include_taxonomy_version() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-params",
            mutation_score=0.5,
            governance_debt_score=0.3,
            lineage_health=0.7,
        )
    )
    assert decision.parameters["strategy_taxonomy_version"] == "16.0"


# ---------------------------------------------------------------------------
# T16-01-14  test_coverage_expansion does NOT fire when debt >= 0.70
# ---------------------------------------------------------------------------
def test_test_coverage_expansion_excluded_on_critical_debt() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-no-test-cov",
            mutation_score=0.30,
            governance_debt_score=0.80,
            horizon_cycles=3,
            resource_budget=0.50,
            lineage_health=0.75,
        )
    )
    # safety_hardening should win; test_coverage_expansion excluded by debt threshold
    assert decision.strategy_id == "safety_hardening"
    assert "test_coverage_expansion" not in decision.priority_queue


# ---------------------------------------------------------------------------
# T16-01-15  performance_optimization does NOT fire without market pressure
#             when mutation_score < 0.80
# ---------------------------------------------------------------------------
def test_performance_optimization_requires_market_pressure_below_0_80() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-no-perf",
            mutation_score=0.65,  # >= 0.60 but < 0.80
            governance_debt_score=0.10,
            horizon_cycles=3,
            resource_budget=0.70,
            lineage_health=0.85,
            signals={"market_fitness_score": 0.20},  # < 0.40 threshold
        )
    )
    assert "performance_optimization" not in decision.priority_queue


# ---------------------------------------------------------------------------
# T16-01-16  performance_optimization fires when mutation >= 0.80 regardless
#             of market signal
# ---------------------------------------------------------------------------
def test_performance_optimization_fires_on_very_high_mutation_score() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-perf-hi",
            mutation_score=0.85,
            governance_debt_score=0.05,
            horizon_cycles=2,
            resource_budget=0.75,
            lineage_health=0.85,
            signals={},  # no market signal
        )
    )
    assert "performance_optimization" in decision.priority_queue


# ---------------------------------------------------------------------------
# T16-01-17  goal_plan is never empty
# ---------------------------------------------------------------------------
def test_goal_plan_never_empty() -> None:
    for inp in [
        StrategyInput(cycle_id="gp1", mutation_score=0.1, governance_debt_score=0.9, lineage_health=0.1),
        StrategyInput(cycle_id="gp2", mutation_score=0.9, governance_debt_score=0.0, lineage_health=0.9),
    ]:
        dec = module.select(inp)
        assert len(dec.goal_plan) > 0


# ---------------------------------------------------------------------------
# T16-01-18  safety_hardening at boundary (exactly 0.70) fires
# ---------------------------------------------------------------------------
def test_safety_hardening_fires_at_exact_boundary() -> None:
    decision = module.select(
        StrategyInput(
            cycle_id="c-boundary",
            mutation_score=0.50,
            governance_debt_score=0.70,
            horizon_cycles=3,
            resource_budget=0.50,
            lineage_health=0.75,
        )
    )
    assert decision.strategy_id == "safety_hardening"
