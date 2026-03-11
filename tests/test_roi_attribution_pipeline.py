import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.economic_fitness import EconomicFitnessEvaluator
from runtime.evolution.mutation_fitness_evaluator import MutationFitnessEvaluator
from runtime.evolution.roi_attribution import ROIAttributionEngine


def test_roi_attribution_engine_produces_deterministic_hash_and_goal_graph_payload() -> None:
    engine = ROIAttributionEngine()
    mutation = {
        "pre_completed_goals": 1,
        "post_completed_goals": 3,
        "pre_capability_score": 0.2,
        "post_capability_score": 0.6,
        "pre_coverage_score": 0.3,
        "post_coverage_score": 0.5,
        "pre_fitness_score": 0.4,
        "post_fitness_score": 0.8,
    }
    goal_graph = {"objectives": ["a", "b", "c", "d"]}

    first = engine.attribute(mutation, goal_graph)
    second = engine.attribute(mutation, goal_graph)

    assert first.attribution_hash == second.attribution_hash
    payload = first.to_goal_graph_payload()
    assert payload["alignment_score"] > 0.0
    assert payload["completed_goals"] == 3.0
    assert payload["total_goals"] == 4.0


def test_mutation_fitness_evaluator_injects_goal_graph_from_attribution() -> None:
    evaluator = MutationFitnessEvaluator()
    result = evaluator.evaluate(
        "agent-1",
        {
            "tests_ok": True,
            "sandbox_ok": True,
            "constitution_ok": True,
            "policy_valid": True,
            "task_value_proxy": {"value_score": 0.8},
            "pre_completed_goals": 1,
            "post_completed_goals": 2,
            "pre_capability_score": 0.1,
            "post_capability_score": 0.6,
            "pre_coverage_score": 0.1,
            "post_coverage_score": 0.7,
            "pre_fitness_score": 0.2,
            "post_fitness_score": 0.9,
        },
        {"objectives": ["g1", "g2", "g3"]},
    )

    assert result["reasons"]["goal_alignment"] > 0.0
    assert result["attribution"]["goal_graph"]["alignment_score"] > 0.0
    assert result["attribution"]["attribution_hash"].startswith("sha256:")


def test_evaluate_content_requires_signal_or_derived_proxy() -> None:
    evaluator = EconomicFitnessEvaluator(rebalance_interval=1000)

    explicit = evaluator.evaluate_content(
        "mutation: candidate",
        source_signal={"simulated_market_score": 0.9, "goal_graph": {"alignment_score": 0.7}},
    )
    derived = evaluator.evaluate_content("mutation: candidate")

    assert explicit.simulated_market_score == 0.9
    assert derived.simulated_market_score > 0.0
    assert derived.simulated_market_score != 0.5
