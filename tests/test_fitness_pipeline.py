import pytest
pytestmark = pytest.mark.regression_standard
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


def test_fitness_pipeline_non_regression_identical_inputs_identical_outputs() -> None:
    pipeline = FitnessPipeline([TestOutcomeEvaluator(), RiskEvaluator()])
    payload = {"tests_ok": True, "impact_risk_score": 0.2, "epoch_id": "epoch-same", "mutation_id": "m-1"}

    first = pipeline.evaluate(dict(payload))
    second = pipeline.evaluate(dict(payload))

    assert first["overall_score"] == second["overall_score"]
    assert first["breakdown"] == second["breakdown"]
    assert first["orchestrator"] == second["orchestrator"]
    assert first["material_hash"] == second["material_hash"]


def test_fitness_pipeline_caches_canonicalization_hot_path() -> None:
    from runtime import fitness_pipeline as fp

    fp._cached_canonical_json.cache_clear()
    fp._cached_json_digest.cache_clear()

    pipeline = FitnessPipeline([TestOutcomeEvaluator(), RiskEvaluator()])
    payload = {"tests_ok": True, "impact_risk_score": 0.2, "epoch_id": "epoch-cache", "mutation_id": "m-cache"}

    pipeline.evaluate(dict(payload))
    pipeline.evaluate(dict(payload))

    canon_info = fp._cached_canonical_json.cache_info()
    digest_info = fp._cached_json_digest.cache_info()

    assert canon_info.hits >= 1
    assert digest_info.hits >= 1
