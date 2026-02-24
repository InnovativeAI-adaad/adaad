# SPDX-License-Identifier: Apache-2.0

from runtime.fitness_pipeline import FitnessPipeline, RiskEvaluator, TestOutcomeEvaluator


def test_fitness_pipeline_composes_weighted_score() -> None:
    pipeline = FitnessPipeline([TestOutcomeEvaluator(), RiskEvaluator()])
    result = pipeline.evaluate({"tests_ok": True, "impact_risk_score": 0.2, "epoch_id": "epoch-1"})
    assert 0.0 <= result["overall_score"] <= 1.0
    assert "tests" in result["breakdown"]
    assert "risk" in result["breakdown"]


def test_fitness_pipeline_exposes_unified_orchestrator_metadata() -> None:
    pipeline = FitnessPipeline([TestOutcomeEvaluator(), RiskEvaluator()])
    result = pipeline.evaluate({"tests_ok": True, "impact_risk_score": 0.1, "epoch_id": "epoch-42", "mutation_tier": "production"})

    assert result["orchestrator"]["regime"] == "survival_only"
    assert result["orchestrator"]["config_hash"].startswith("sha256:")
    assert "correctness_score" in result["orchestrator"]["component_breakdown"]
    assert result["orchestrator"]["weight_snapshot_hash"].startswith("sha256:")
