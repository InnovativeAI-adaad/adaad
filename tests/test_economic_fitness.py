# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.economic_fitness import EconomicFitnessEvaluator
from runtime.evolution.fitness import FitnessEvaluator


def test_economic_fitness_is_deterministic() -> None:
    evaluator = EconomicFitnessEvaluator()
    payload = {
        "content": "mutation: candidate",
        "tests_ok": True,
        "sandbox_ok": True,
        "constitution_ok": True,
        "policy_valid": True,
        "goal_graph": {"alignment_score": 0.8},
        "task_value_proxy": {"value_score": 0.75},
        "platform": {"memory_mb": 2048, "cpu_percent": 20, "runtime_ms": 2000},
    }
    first = evaluator.evaluate(payload)
    second = evaluator.evaluate(payload)
    assert first.to_dict() == second.to_dict()


def test_legacy_fitness_facade_keeps_old_schema() -> None:
    legacy = FitnessEvaluator().evaluate_content("mutation: candidate", constitution_ok=True)
    payload = legacy.to_dict()
    assert set(payload) == {
        "score",
        "passed_syntax",
        "passed_tests",
        "passed_constitution",
        "performance_delta",
    }


def test_economic_fitness_rebalances_weights_from_history() -> None:
    evaluator = EconomicFitnessEvaluator(rebalance_interval=1)
    original = dict(evaluator.weights)
    history = [
        {
            "goal_score_delta": 0.5,
            "fitness_component_scores": {
                "correctness_score": 1.0,
                "efficiency_score": 0.0,
                "policy_compliance_score": 0.0,
                "goal_alignment_score": 0.0,
                "simulated_market_score": 0.0,
            },
        }
    ]
    tuned = evaluator.rebalance_from_history(history)
    assert tuned["correctness_score"] >= original["correctness_score"]
    assert abs(sum(tuned.values()) - 1.0) < 1e-9


def test_economic_fitness_snapshots_weights_per_epoch() -> None:
    evaluator = EconomicFitnessEvaluator(rebalance_interval=1000)

    baseline = evaluator.evaluate({
        "epoch_id": "epoch-1",
        "correctness_score": 0.8,
        "efficiency_score": 0.4,
        "policy_compliance_score": 0.9,
        "goal_alignment_score": 0.5,
        "simulated_market_score": 0.7,
    })

    evaluator.weights = {
        "correctness_score": 1.0,
        "efficiency_score": 0.0,
        "policy_compliance_score": 0.0,
        "goal_alignment_score": 0.0,
        "simulated_market_score": 0.0,
    }

    same_epoch = evaluator.evaluate({
        "epoch_id": "epoch-1",
        "correctness_score": 0.8,
        "efficiency_score": 0.4,
        "policy_compliance_score": 0.9,
        "goal_alignment_score": 0.5,
        "simulated_market_score": 0.7,
    })
    next_epoch = evaluator.evaluate({
        "epoch_id": "epoch-2",
        "correctness_score": 0.8,
        "efficiency_score": 0.4,
        "policy_compliance_score": 0.9,
        "goal_alignment_score": 0.5,
        "simulated_market_score": 0.7,
    })

    assert baseline.weights == same_epoch.weights
    assert baseline.score == same_epoch.score
    assert next_epoch.weights["correctness_score"] == 1.0


def test_economic_fitness_replay_equivalence_across_reinstantiation() -> None:
    payload = {
        "epoch_id": "epoch-replay",
        "content": "mutation: candidate",
        "tests_ok": True,
        "sandbox_ok": True,
        "constitution_ok": True,
        "policy_valid": True,
        "goal_graph": {"alignment_score": 0.8},
        "task_value_proxy": {"value_score": 0.75},
        "platform": {"memory_mb": 2048, "cpu_percent": 20, "runtime_ms": 2000},
        "epoch_metadata": {},
    }

    first = EconomicFitnessEvaluator().evaluate(dict(payload))
    second = EconomicFitnessEvaluator().evaluate(dict(payload))

    assert first.to_dict() == second.to_dict()
    assert payload["epoch_metadata"]["fitness_weight_snapshot_hash"].startswith("sha256:")


def test_economic_fitness_persists_snapshot_hash_into_epoch_metadata() -> None:
    evaluator = EconomicFitnessEvaluator()
    epoch_metadata = {}
    result = evaluator.evaluate({
        "epoch_id": "epoch-meta",
        "correctness_score": 0.8,
        "efficiency_score": 0.4,
        "policy_compliance_score": 0.9,
        "goal_alignment_score": 0.5,
        "simulated_market_score": 0.7,
        "epoch_metadata": epoch_metadata,
    })

    assert epoch_metadata["fitness_weight_snapshot_hash"] == result.weight_snapshot_hash
    assert result.weight_snapshot_hash.startswith("sha256:")


def test_weight_snapshot_hash_stable_within_epoch() -> None:
    evaluator = EconomicFitnessEvaluator(rebalance_interval=1000)
    payload = {
        "epoch_id": "epoch-hash-same",
        "correctness_score": 0.8,
        "efficiency_score": 0.4,
        "policy_compliance_score": 0.9,
        "goal_alignment_score": 0.5,
        "simulated_market_score": 0.7,
    }
    first = evaluator.evaluate(dict(payload))
    second = evaluator.evaluate(dict(payload))
    assert first.weight_snapshot_hash == second.weight_snapshot_hash


def test_weight_snapshot_hash_changes_next_epoch_when_weights_change() -> None:
    evaluator = EconomicFitnessEvaluator(rebalance_interval=1000)
    baseline = evaluator.evaluate(
        {
            "epoch_id": "epoch-hash-a",
            "correctness_score": 0.8,
            "efficiency_score": 0.4,
            "policy_compliance_score": 0.9,
            "goal_alignment_score": 0.5,
            "simulated_market_score": 0.7,
        }
    )
    evaluator.weights = {
        "correctness_score": 1.0,
        "efficiency_score": 0.0,
        "policy_compliance_score": 0.0,
        "goal_alignment_score": 0.0,
        "simulated_market_score": 0.0,
    }
    next_epoch = evaluator.evaluate(
        {
            "epoch_id": "epoch-hash-b",
            "correctness_score": 0.8,
            "efficiency_score": 0.4,
            "policy_compliance_score": 0.9,
            "goal_alignment_score": 0.5,
            "simulated_market_score": 0.7,
        }
    )
    assert baseline.weight_snapshot_hash != next_epoch.weight_snapshot_hash


def test_epoch_metadata_hash_mismatch_fails_closed() -> None:
    evaluator = EconomicFitnessEvaluator(rebalance_interval=1000)
    try:
        evaluator.evaluate(
            {
                "epoch_id": "epoch-mismatch",
                "correctness_score": 0.8,
                "efficiency_score": 0.4,
                "policy_compliance_score": 0.9,
                "goal_alignment_score": 0.5,
                "simulated_market_score": 0.7,
                "epoch_metadata": {"fitness_weight_snapshot_hash": "sha256:deadbeef"},
            }
        )
    except RuntimeError as exc:
        assert str(exc) == "fitness_weight_snapshot_hash_mismatch"
    else:
        raise AssertionError("expected RuntimeError")


def test_market_adapter_output_maps_to_simulated_market_score() -> None:
    evaluator = EconomicFitnessEvaluator()
    result = evaluator.evaluate(
        {
            "market_adapter_output": {
                "scoring_inputs": {"simulated_market_score": 0.83},
                "expected_roi": 0.12,
            }
        }
    )

    assert result.simulated_market_score == 0.83


def test_market_adapter_mapping_does_not_override_explicit_simulated_market_score() -> None:
    evaluator = EconomicFitnessEvaluator()
    result = evaluator.evaluate(
        {
            "simulated_market_score": 0.24,
            "market_adapter": {"simulated_market_score": 0.91},
        }
    )

    assert result.simulated_market_score == 0.24
