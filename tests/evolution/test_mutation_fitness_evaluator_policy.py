import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.mutation_fitness_evaluator import MutationFitnessEvaluator


def test_policy_profile_update_is_deterministic_and_persistent(tmp_path) -> None:
    policy_path = tmp_path / "mutation_policy_profile.v1.json"
    evaluator = MutationFitnessEvaluator(policy_profile_path=policy_path, forecast_gate_threshold=0.4)

    cycles = [
        {"agent_type": "builder", "mutation_family": "refactor", "roi": 0.4, "accepted": True, "status": "completed"},
        {"agent_type": "builder", "mutation_family": "refactor", "roi": -0.2, "accepted": False, "completed": True},
        {"agent_type": "builder", "mutation_family": "refactor", "roi": 0.9, "accepted": True, "status": "running"},
    ]

    artifact = evaluator.update_policy_from_completed_cycles(cycles)
    assert artifact["version"] == "mutation_policy_profile.v1"
    assert artifact["hash"].startswith("sha256:")

    reloaded = MutationFitnessEvaluator(policy_profile_path=policy_path, forecast_gate_threshold=0.4)
    forecast = reloaded.forecast(
        {"intent": "refactor:cleanup", "ops": [{"op": "set"}, {"op": "set"}]},
        agent_type="builder",
    )

    profile = forecast["policy_profile"]
    assert profile["completed_cycles"] == 2
    assert profile["rolling_roi"] == 0.1
    assert profile["acceptance_rate"] == 0.5
    assert profile["roi_variance"] == 0.09


def test_evaluate_includes_forecast_and_policy_artifact_fields(tmp_path) -> None:
    policy_path = tmp_path / "mutation_policy_profile.v1.json"
    evaluator = MutationFitnessEvaluator(policy_profile_path=policy_path, forecast_gate_threshold=0.35)
    evaluator.update_policy_from_completed_cycles(
        [
            {"agent_type": "planner", "mutation_family": "dna.add_trait", "roi": 0.6, "accepted": True, "status": "completed"},
            {"agent_type": "planner", "mutation_family": "dna.add_trait", "roi": 0.1, "accepted": True, "status": "completed"},
        ]
    )

    mutation = {
        "agent_type": "planner",
        "mutation_family": "dna.add_trait",
        "tests_ok": True,
        "sandbox_ok": True,
        "constitution_ok": True,
        "policy_valid": True,
        "ops": [{"op": "dna.add_trait"}],
    }
    goal_graph = {"objectives": ["g1", "g2"]}

    first = evaluator.evaluate("agent-1", mutation, goal_graph)
    second = evaluator.evaluate("agent-1", mutation, goal_graph)

    assert first["forecast_score"] == second["forecast_score"]
    assert first["forecast_passed"] == second["forecast_passed"]
    assert first["policy_artifact"]["version"] == "mutation_policy_profile.v1"
    assert first["policy_artifact"]["hash"].startswith("sha256:")
