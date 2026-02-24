# SPDX-License-Identifier: Apache-2.0
"""Deterministic ROI attribution records for mutation-to-goal evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

from runtime.governance.foundation import canonical_json, sha256_prefixed_digest


@dataclass(frozen=True)
class ROIAttributionRecord:
    pre_goal_completion: float
    post_goal_completion: float
    capability_delta: float
    coverage_delta: float
    fitness_delta: float
    attribution_hash: str
    total_goals: float

    @staticmethod
    def _clamp(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @property
    def completed_goals(self) -> float:
        return self.post_goal_completion

    @property
    def goal_completion_delta(self) -> float:
        return self.post_goal_completion - self.pre_goal_completion

    def to_goal_graph_payload(self) -> Dict[str, float | str]:
        total_goals = max(1.0, float(self.total_goals))
        completion_ratio = self._clamp(self.post_goal_completion / total_goals)
        alignment_score = self._clamp(
            (
                completion_ratio
                + self._clamp(self.capability_delta)
                + self._clamp(self.coverage_delta)
                + self._clamp(self.fitness_delta)
            )
            / 4.0
        )
        return {
            "completed_goals": round(self.post_goal_completion, 6),
            "total_goals": round(total_goals, 6),
            "alignment_score": round(alignment_score, 6),
            "goal_completion_delta": round(self.goal_completion_delta, 6),
            "capability_delta": round(self.capability_delta, 6),
            "coverage_delta": round(self.coverage_delta, 6),
            "fitness_delta": round(self.fitness_delta, 6),
            "attribution_hash": self.attribution_hash,
        }


class ROIAttributionEngine:
    """Build hash-stable ROI attribution records from mutation + goal snapshots."""

    @staticmethod
    def _float_from(payload: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
        for key in keys:
            if key in payload:
                try:
                    return float(payload.get(key) or 0.0)
                except (TypeError, ValueError):
                    return default
        return default

    @staticmethod
    def _goals_total(goal_graph: Mapping[str, Any], post_goal_completion: float) -> float:
        objectives = goal_graph.get("objectives")
        if isinstance(objectives, list) and objectives:
            return float(len(objectives))
        explicit_total = ROIAttributionEngine._float_from(goal_graph, "total_goals", default=0.0)
        if explicit_total > 0:
            return explicit_total
        return max(1.0, float(post_goal_completion))

    def attribute(self, mutation: Mapping[str, Any], goal_graph: Mapping[str, Any] | None = None) -> ROIAttributionRecord:
        graph = goal_graph if isinstance(goal_graph, Mapping) else {}

        post_completion = self._float_from(
            graph,
            "post_completed_goals",
            "completed_goals",
            default=self._float_from(mutation, "post_completed_goals", "completed_goals", default=0.0),
        )
        pre_completion = self._float_from(
            graph,
            "pre_completed_goals",
            default=self._float_from(mutation, "pre_completed_goals", default=post_completion),
        )

        capability_post = self._float_from(
            graph,
            "post_capability_score",
            "capability_score",
            default=self._float_from(mutation, "post_capability_score", "capability_score", default=0.0),
        )
        capability_pre = self._float_from(
            graph,
            "pre_capability_score",
            default=self._float_from(mutation, "pre_capability_score", default=capability_post),
        )

        coverage_post = self._float_from(
            graph,
            "post_coverage_score",
            "coverage_score",
            default=self._float_from(mutation, "post_coverage_score", "coverage_score", default=0.0),
        )
        coverage_pre = self._float_from(
            graph,
            "pre_coverage_score",
            default=self._float_from(mutation, "pre_coverage_score", default=coverage_post),
        )

        fitness_post = self._float_from(
            graph,
            "post_fitness_score",
            default=self._float_from(mutation, "post_fitness_score", "fitness_score", default=0.0),
        )
        fitness_pre = self._float_from(
            graph,
            "pre_fitness_score",
            default=self._float_from(mutation, "pre_fitness_score", default=fitness_post),
        )

        total_goals = self._goals_total(graph, post_completion)
        fingerprint_payload = {
            "pre_goal_completion": round(pre_completion, 6),
            "post_goal_completion": round(post_completion, 6),
            "capability_delta": round(capability_post - capability_pre, 6),
            "coverage_delta": round(coverage_post - coverage_pre, 6),
            "fitness_delta": round(fitness_post - fitness_pre, 6),
            "total_goals": round(total_goals, 6),
        }
        attribution_hash = sha256_prefixed_digest(canonical_json(fingerprint_payload))

        return ROIAttributionRecord(
            pre_goal_completion=pre_completion,
            post_goal_completion=post_completion,
            capability_delta=capability_post - capability_pre,
            coverage_delta=coverage_post - coverage_pre,
            fitness_delta=fitness_post - fitness_pre,
            attribution_hash=attribution_hash,
            total_goals=total_goals,
        )


__all__ = ["ROIAttributionEngine", "ROIAttributionRecord"]
