# SPDX-License-Identifier: Apache-2.0
"""Stateless deterministic mutation analyzer."""

from __future__ import annotations

from typing import Any, Dict

from runtime.evolution.fitness_orchestrator import FitnessOrchestrator


WEIGHTS = {
    "constitutional_compliance": 0.25,
    "stability_heuristics": 0.25,
    "performance_delta": 0.20,
    "resource_efficiency": 0.15,
    "lineage_distance": 0.15,
}


def analyze_mutation(payload: Dict[str, Any]) -> Dict[str, Any]:
    orchestrator = FitnessOrchestrator()
    result = orchestrator.score(
        {
            "epoch_id": str(payload.get("epoch_id") or "mcp-static-epoch"),
            "mutation_tier": payload.get("mutation_tier", "low"),
            "correctness_score": payload.get("constitutional_compliance", 0.5),
            "efficiency_score": payload.get("resource_efficiency", 0.5),
            "policy_compliance_score": payload.get("constitutional_compliance", 0.5),
            "goal_alignment_score": payload.get("performance_delta", 0.5),
            "simulated_market_score": payload.get("lineage_distance", 0.5),
        }
    )
    score = float(result.total_score)
    components = {
        key: float(payload.get(key, 0.5)) if isinstance(payload.get(key), (int, float)) else 0.5
        for key in WEIGHTS
    }
    if score >= 0.70:
        risk_tier = "low"
        recommendation = "proceed_to_human_review"
    elif score >= 0.40:
        risk_tier = "medium"
        recommendation = "revise_before_submission"
    else:
        risk_tier = "high"
        recommendation = "do_not_submit"

    blocking_predictions = []
    if components["constitutional_compliance"] < 0.5:
        blocking_predictions.append("constitutional_non_compliance_risk")
    if components["stability_heuristics"] < 0.4:
        blocking_predictions.append("stability_regression_risk")

    return {
        "predicted_fitness_score": round(score, 6),
        "risk_tier": risk_tier,
        "component_scores": components,
        "blocking_predictions": blocking_predictions,
        "recommendation": recommendation,
        "fitness_regime": result.regime,
        "fitness_config_hash": result.config_hash,
    }


__all__ = ["analyze_mutation", "WEIGHTS"]
