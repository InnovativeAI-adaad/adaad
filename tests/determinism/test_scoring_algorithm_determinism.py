# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy
import json

import pytest
pytestmark = pytest.mark.autonomous_critical

from runtime.evolution.economic_fitness import EconomicFitnessEvaluator
from runtime.evolution.scoring_algorithm import (
    RISK_WEIGHTS,
    SEVERITY_WEIGHTS,
    ScoringValidationError,
    compute_score,
)
from runtime.governance.foundation import SeededDeterminismProvider, sha256_prefixed_digest


def _sample() -> dict:
    return {
        "mutation_id": "mut-1",
        "epoch_id": "epoch-1",
        "constitution_hash": "sha256:" + ("a" * 64),
        "test_results": {"total": 10, "failed": 0},
        "static_analysis": {
            "issues": [
                {"rule_id": "R2", "severity": "LOW"},
                {"rule_id": "R1", "severity": "HIGH"},
            ]
        },
        "code_diff": {
            "loc_added": 5,
            "loc_deleted": 3,
            "files_touched": 1,
            "risk_tags": ["API", "SECURITY"],
        },
        "sustainability": {"score": 120},
        "resource_efficiency": {"score": 80},
        "cross_agent_synergy": {"score": 55},
    }


def test_scoring_determinism_1000_iterations() -> None:
    provider = SeededDeterminismProvider(seed="score-seed")
    sample = _sample()
    seen = set()
    for _ in range(1000):
        result = compute_score(sample, provider=provider, replay_mode="strict")
        record_hash = sha256_prefixed_digest({k: v for k, v in result.items() if k != "timestamp"})
        seen.add((result["score"], result["input_hash"], record_hash))
    assert len(seen) == 1


def test_input_not_mutated() -> None:
    sample = _sample()
    before = copy.deepcopy(sample)
    compute_score(sample, provider=SeededDeterminismProvider(seed="immut"), replay_mode="strict")
    assert sample == before


def test_hard_limits_enforced() -> None:
    sample = _sample()
    sample["code_diff"]["loc_added"] = 200_000
    with pytest.raises(ScoringValidationError):
        compute_score(sample, provider=SeededDeterminismProvider(seed="limit"), replay_mode="strict")


def test_score_floor_non_negative() -> None:
    sample = _sample()
    sample["test_results"]["failed"] = 1
    sample["code_diff"]["loc_added"] = 50_000
    result = compute_score(sample, provider=SeededDeterminismProvider(seed="floor"), replay_mode="strict")
    assert result["score"] >= 0


def test_weight_tables_immutable() -> None:
    with pytest.raises(TypeError):
        SEVERITY_WEIGHTS["NEW"] = 1
    with pytest.raises(TypeError):
        RISK_WEIGHTS["NEW"] = 1


def test_scoring_algorithm_clamps_new_terms() -> None:
    sample = _sample()
    sample["sustainability"]["score"] = 99999
    sample["resource_efficiency"]["score"] = -5
    sample["cross_agent_synergy"]["score"] = "invalid"

    result = compute_score(sample, provider=SeededDeterminismProvider(seed="clamp"), replay_mode="strict")
    components = result["components"]

    assert components["long_horizon_sustainability_term"] == 300
    assert components["resource_efficiency_term"] == 0
    assert components["cross_agent_synergy_term"] == 0


def test_identical_tuned_weights_produce_identical_scores(tmp_path) -> None:
    tuned_weights = {
        "version": 3,
        "weights": {
            "correctness_score": 0.28,
            "efficiency_score": 0.22,
            "policy_compliance_score": 0.21,
            "goal_alignment_score": 0.14,
            "simulated_market_score": 0.15,
        },
    }
    config_path = tmp_path / "fitness_weights.json"
    config_path.write_text(json.dumps(tuned_weights), encoding="utf-8")

    evaluator_a = EconomicFitnessEvaluator(config_path=config_path)
    evaluator_b = EconomicFitnessEvaluator(config_path=config_path)
    payload = {
        "tests_ok": True,
        "sandbox_ok": True,
        "constitution_ok": True,
        "policy_valid": True,
        "task_value_proxy": {"value_score": 0.7},
        "platform": {"memory_mb": 1024, "cpu_percent": 30, "runtime_ms": 5000},
    }
    assert evaluator_a.evaluate(payload).score == evaluator_b.evaluate(payload).score
