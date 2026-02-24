# SPDX-License-Identifier: Apache-2.0
"""Composable fitness pipeline for mutation scoring."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List

from runtime.evolution.fitness_orchestrator import FitnessOrchestrator


@dataclass
class FitnessMetric:
    name: str
    weight: float
    score: float
    metadata: Dict[str, Any]


class FitnessEvaluator(ABC):
    @abstractmethod
    def evaluate(self, mutation_data: Dict[str, Any]) -> FitnessMetric:
        raise NotImplementedError


class TestOutcomeEvaluator(FitnessEvaluator):
    def evaluate(self, mutation_data: Dict[str, Any]) -> FitnessMetric:
        tests_ok = bool(mutation_data.get("tests_ok"))
        return FitnessMetric(
            name="tests",
            weight=0.5,
            score=1.0 if tests_ok else 0.0,
            metadata={"tests_ok": tests_ok},
        )


class RiskEvaluator(FitnessEvaluator):
    def evaluate(self, mutation_data: Dict[str, Any]) -> FitnessMetric:
        risk_score = float(mutation_data.get("impact_risk_score", 0.0) or 0.0)
        return FitnessMetric(
            name="risk",
            weight=0.5,
            score=max(0.0, min(1.0, 1.0 - risk_score)),
            metadata={"impact_risk_score": risk_score},
        )


class FitnessPipeline:
    def __init__(self, evaluators: List[FitnessEvaluator]):
        self.evaluators = evaluators
        self._orchestrator = FitnessOrchestrator()

    def evaluate(self, mutation_data: Dict[str, Any]) -> Dict[str, Any]:
        metrics = [e.evaluate(mutation_data) for e in self.evaluators]
        total_weight = sum(m.weight for m in metrics) or 1.0
        legacy_weighted_score = sum(m.score * m.weight for m in metrics) / total_weight

        breakdown = {m.name: m.score for m in metrics}
        orchestrator_result = self._orchestrator.score(
            {
                "epoch_id": str(mutation_data.get("epoch_id") or "fitness-pipeline-default"),
                "mutation_tier": mutation_data.get("mutation_tier"),
                "correctness_score": breakdown.get("tests", legacy_weighted_score),
                "efficiency_score": float(mutation_data.get("efficiency_score", 0.0) or 0.0),
                "policy_compliance_score": float(mutation_data.get("policy_compliance_score", 1.0) or 0.0),
                "goal_alignment_score": float(mutation_data.get("goal_alignment_score", 0.0) or 0.0),
                "simulated_market_score": float(mutation_data.get("simulated_market_score", breakdown.get("risk", 0.0)) or 0.0),
            }
        )

        return {
            "overall_score": orchestrator_result.total_score,
            "metrics": [m.__dict__ for m in metrics],
            "breakdown": breakdown,
            "orchestrator": {
                "regime": orchestrator_result.regime,
                "config_hash": orchestrator_result.config_hash,
                "component_breakdown": dict(orchestrator_result.breakdown),
                "weight_snapshot_hash": orchestrator_result.weight_snapshot_hash,
            },
        }


__all__ = [
    "FitnessMetric",
    "FitnessEvaluator",
    "TestOutcomeEvaluator",
    "RiskEvaluator",
    "FitnessPipeline",
]
