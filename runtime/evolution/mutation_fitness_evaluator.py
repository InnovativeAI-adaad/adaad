# SPDX-License-Identifier: Apache-2.0
"""Deterministic mutation fitness evaluator for EvolutionKernel."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from runtime import fitness
from runtime.evolution.roi_attribution import ROIAttributionEngine


class MutationFitnessEvaluator:
    """Evaluate mutation fitness against an optional goal graph."""

    def __init__(self) -> None:
        self._attribution_engine = ROIAttributionEngine()

    def evaluate(self, agent_id: str, mutation: Mapping[str, Any], goal_graph: Mapping[str, Any] | None = None) -> Dict[str, Any]:
        attribution = self._attribution_engine.attribute(mutation, goal_graph)
        scored_payload = dict(mutation)
        scored_payload["goal_graph"] = attribution.to_goal_graph_payload()
        explanation = fitness.explain_score(agent_id, scored_payload)
        base_score = float(explanation.get("score", 0.0) or 0.0)

        objective_weight = 1.0
        if goal_graph and isinstance(goal_graph, Mapping):
            objectives = goal_graph.get("objectives")
            if isinstance(objectives, list):
                objective_weight = min(1.0, max(0.0, float(len(objectives)) / 10.0))

        weighted_score = max(0.0, min(1.0, base_score * objective_weight))
        acceptance_threshold = float(explanation.get("fitness_threshold", 0.7) or 0.7)
        accepted = base_score >= acceptance_threshold

        return {
            "score": weighted_score,
            "base_score": base_score,
            "objective_weight": objective_weight,
            "acceptance_threshold": acceptance_threshold,
            "accepted": accepted,
            "passed": accepted,
            "reasons": explanation.get("reasons", {}),
            "weights": explanation.get("weights", {}),
            "weighted_contributions": explanation.get("weighted_contributions", {}),
            "explainability": explanation.get("explainability", {}),
            "attribution": {
                "pre_goal_completion": attribution.pre_goal_completion,
                "post_goal_completion": attribution.post_goal_completion,
                "capability_delta": attribution.capability_delta,
                "coverage_delta": attribution.coverage_delta,
                "fitness_delta": attribution.fitness_delta,
                "attribution_hash": attribution.attribution_hash,
                "goal_graph": attribution.to_goal_graph_payload(),
            },
            "config_version": explanation.get("config_version"),
            "config_hash": explanation.get("config_hash"),
            "ranking_rationale": "ranking uses objective_weight adjusted score; acceptance uses base score threshold",
        }


__all__ = ["MutationFitnessEvaluator"]
