# SPDX-License-Identifier: Apache-2.0
"""Deterministic mutation fitness evaluator for EvolutionKernel."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping

from runtime import ROOT_DIR, fitness
from runtime.evolution.roi_attribution import ROIAttributionEngine
from runtime.governance.foundation import canonical_json, sha256_prefixed_digest
from runtime.evolution.semantic_diff import enrich_code_diff_with_semantic

_POLICY_VERSION = "mutation_policy_profile.v1"
_MAX_ROI_HISTORY = 32
_META_BOUNDS = {
    "exploration_rate": (0.05, 0.95),
    "reward_discount": (0.5, 0.99),
}


class MutationFitnessEvaluator:
    """Evaluate mutation fitness against an optional goal graph."""

    def __init__(self, *, policy_profile_path: Path | None = None, forecast_gate_threshold: float = 0.45) -> None:
        self._attribution_engine = ROIAttributionEngine()
        self._policy_profile_path = Path(policy_profile_path or (ROOT_DIR / "data" / "mutation_policy_profile.v1.json"))
        self._forecast_gate_threshold = self._clamp(forecast_gate_threshold)
        self._policy_profile = self._load_policy_profile()

    def update_policy_from_completed_cycles(self, completed_cycles: List[Mapping[str, Any]]) -> Dict[str, Any]:
        """Deterministically update bandit policy from completed historical cycles only."""
        if not completed_cycles:
            return self._policy_artifact()

        profiles = dict(self._policy_profile.get("profiles") or {})
        for cycle in completed_cycles:
            if not self._is_completed_cycle(cycle):
                continue
            key = self._profile_key(str(cycle.get("agent_type") or "unknown"), str(cycle.get("mutation_family") or "unknown"))
            profile = dict(profiles.get(key) or self._empty_profile())
            roi_history = [float(v) for v in profile.get("roi_history") or []]
            roi_value = self._roi_from_cycle(cycle)
            roi_history.append(roi_value)
            roi_history = roi_history[-_MAX_ROI_HISTORY:]
            acceptance_history = [1 if bool(v) else 0 for v in profile.get("acceptance_history") or []]
            acceptance_history.append(1 if bool(cycle.get("accepted")) else 0)
            acceptance_history = acceptance_history[-_MAX_ROI_HISTORY:]
            profile["roi_history"] = roi_history
            profile["acceptance_history"] = acceptance_history
            profile.update(self._summarize_profile(roi_history, acceptance_history))
            profiles[key] = profile

        meta_mutation = self._mutate_meta_channel(profiles)
        self._policy_profile = {
            "version": _POLICY_VERSION,
            "meta_mutation": meta_mutation,
            "profiles": profiles,
        }
        self._persist_policy_profile()
        return self._policy_artifact()

    def forecast(self, mutation: Mapping[str, Any], *, agent_type: str = "unknown") -> Dict[str, Any]:
        mutation_family = self._mutation_family(mutation)
        profile = self._profile_for(agent_type=agent_type, mutation_family=mutation_family)
        total_completed = sum(int((entry or {}).get("completed_cycles", 0)) for entry in (self._policy_profile.get("profiles") or {}).values())
        forecast_score = self._forecast_score(mutation=mutation, profile=profile, total_completed=max(total_completed, 1))
        return {
            "forecast_score": forecast_score,
            "forecast_gate_threshold": self._forecast_gate_threshold,
            "forecast_passed": forecast_score >= self._forecast_gate_threshold,
            "policy_profile": {
                "agent_type": agent_type,
                "mutation_family": mutation_family,
                "rolling_roi": profile.get("rolling_roi", 0.0),
                "acceptance_rate": profile.get("acceptance_rate", 0.0),
                "roi_variance": profile.get("roi_variance", 0.0),
                "completed_cycles": profile.get("completed_cycles", 0),
            },
            "policy_artifact": self._policy_artifact(),
        }

    def evaluate(self, agent_id: str, mutation: Mapping[str, Any], goal_graph: Mapping[str, Any] | None = None) -> Dict[str, Any]:
        attribution = self._attribution_engine.attribute(mutation, goal_graph)
        scored_payload = dict(mutation)

        # PR-PHASE4-02: Semantic enrichment — replace heuristic risk/complexity
        # with AST-derived scores when python_content is available.
        _python_content = scored_payload.get("python_content")
        if _python_content is not None:
            try:
                scored_payload["code_diff"] = enrich_code_diff_with_semantic(
                    scored_payload.get("code_diff") or {},
                    before_source=None,
                    after_source=_python_content,
                )
                scored_payload["scoring_algorithm_version"] = "semantic_diff_v1.0"
            except Exception:  # noqa: BLE001 — graceful degradation
                pass
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
        forecast_payload = self.forecast(mutation, agent_type=str(mutation.get("agent_type") or "unknown"))

        return {
            "score": weighted_score,
            "base_score": base_score,
            "objective_weight": objective_weight,
            "acceptance_threshold": acceptance_threshold,
            "accepted": accepted,
            "passed": accepted,
            "forecast_score": forecast_payload["forecast_score"],
            "forecast_gate_threshold": forecast_payload["forecast_gate_threshold"],
            "forecast_passed": forecast_payload["forecast_passed"],
            "policy_profile": forecast_payload["policy_profile"],
            "policy_artifact": forecast_payload["policy_artifact"],
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

    def _profile_for(self, *, agent_type: str, mutation_family: str) -> Dict[str, Any]:
        key = self._profile_key(agent_type, mutation_family)
        profile = dict((self._policy_profile.get("profiles") or {}).get(key) or self._empty_profile())
        roi_history = [float(v) for v in profile.get("roi_history") or []]
        acceptance_history = [1 if bool(v) else 0 for v in profile.get("acceptance_history") or []]
        profile.update(self._summarize_profile(roi_history, acceptance_history))
        profile["roi_history"] = roi_history
        profile["acceptance_history"] = acceptance_history
        return profile

    def _load_policy_profile(self) -> Dict[str, Any]:
        if self._policy_profile_path.exists():
            try:
                payload = json.loads(self._policy_profile_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and payload.get("version") == _POLICY_VERSION:
                    return payload
            except json.JSONDecodeError:
                pass
        return {
            "version": _POLICY_VERSION,
            "meta_mutation": {"exploration_rate": 0.2, "reward_discount": 0.9},
            "profiles": {},
        }

    def _persist_policy_profile(self) -> None:
        self._policy_profile_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(self._policy_profile, sort_keys=True, separators=(",", ":"))
        self._policy_profile_path.write_text(serialized + "\n", encoding="utf-8")

    def _policy_artifact(self) -> Dict[str, Any]:
        canonical_payload = canonical_json(self._policy_profile)
        return {
            "version": self._policy_profile.get("version", _POLICY_VERSION),
            "hash": sha256_prefixed_digest(canonical_payload),
        }

    @staticmethod
    def _empty_profile() -> Dict[str, Any]:
        return {
            "roi_history": [],
            "acceptance_history": [],
            "rolling_roi": 0.0,
            "acceptance_rate": 0.0,
            "roi_variance": 0.0,
            "completed_cycles": 0,
        }

    def _mutate_meta_channel(self, profiles: Mapping[str, Mapping[str, Any]]) -> Dict[str, float]:
        baseline = dict(self._policy_profile.get("meta_mutation") or {"exploration_rate": 0.2, "reward_discount": 0.9})
        mean_roi = 0.0
        acceptance = 0.0
        if profiles:
            count = float(len(profiles))
            mean_roi = sum(float((p or {}).get("rolling_roi", 0.0)) for p in profiles.values()) / count
            acceptance = sum(float((p or {}).get("acceptance_rate", 0.0)) for p in profiles.values()) / count
        exploration_shift = (0.5 - acceptance) * 0.1
        discount_shift = mean_roi * 0.05
        exploration = self._bounded(
            float(baseline.get("exploration_rate", 0.2)) + exploration_shift,
            *_META_BOUNDS["exploration_rate"],
        )
        reward_discount = self._bounded(
            float(baseline.get("reward_discount", 0.9)) + discount_shift,
            *_META_BOUNDS["reward_discount"],
        )
        return {
            "exploration_rate": round(exploration, 6),
            "reward_discount": round(reward_discount, 6),
        }

    @staticmethod
    def _summarize_profile(roi_history: List[float], acceptance_history: List[int]) -> Dict[str, Any]:
        if not roi_history:
            return {
                "rolling_roi": 0.0,
                "acceptance_rate": 0.0,
                "roi_variance": 0.0,
                "completed_cycles": 0,
            }
        mean_roi = sum(roi_history) / float(len(roi_history))
        variance = sum((value - mean_roi) ** 2 for value in roi_history) / float(len(roi_history))
        acceptance_rate = sum(acceptance_history) / float(len(acceptance_history)) if acceptance_history else 0.0
        return {
            "rolling_roi": round(mean_roi, 6),
            "acceptance_rate": round(acceptance_rate, 6),
            "roi_variance": round(variance, 6),
            "completed_cycles": len(roi_history),
        }

    @staticmethod
    def _profile_key(agent_type: str, mutation_family: str) -> str:
        return f"{agent_type.strip().lower()}::{mutation_family.strip().lower()}"

    @staticmethod
    def _mutation_family(mutation: Mapping[str, Any]) -> str:
        if mutation.get("mutation_family"):
            return str(mutation.get("mutation_family"))
        intent = str(mutation.get("intent") or "")
        if intent:
            return intent.split(":", 1)[0]
        ops = mutation.get("ops")
        if isinstance(ops, list) and ops:
            op = ops[0]
            if isinstance(op, Mapping):
                return str(op.get("op") or "unknown")
        return "unknown"

    @staticmethod
    def _complexity_proxy(mutation: Mapping[str, Any]) -> float:
        ops = mutation.get("ops")
        count = len(ops) if isinstance(ops, list) else 1
        return 1.0 / float(max(1, count))

    def _forecast_score(self, *, mutation: Mapping[str, Any], profile: Mapping[str, Any], total_completed: int) -> float:
        meta = dict(self._policy_profile.get("meta_mutation") or {})
        exploration = float(meta.get("exploration_rate", 0.2))
        reward_discount = float(meta.get("reward_discount", 0.9))
        rolling_roi = float(profile.get("rolling_roi", 0.0))
        roi_norm = self._clamp((rolling_roi + 1.0) / 2.0)
        failure_risk = self._clamp((1.0 - float(profile.get("acceptance_rate", 0.0))) + float(profile.get("roi_variance", 0.0)))
        complexity_term = self._complexity_proxy(mutation)
        bandit_bonus = self._bandit_score(profile, total_completed=total_completed, exploration=exploration, reward_discount=reward_discount)
        blended = (0.45 * roi_norm) + (0.3 * (1.0 - failure_risk)) + (0.15 * complexity_term) + (0.1 * bandit_bonus)
        return round(self._clamp(blended), 6)

    @staticmethod
    def _bandit_score(profile: Mapping[str, Any], *, total_completed: int, exploration: float, reward_discount: float) -> float:
        pulls = max(1, int(profile.get("completed_cycles", 0) or 0))
        roi = float(profile.get("rolling_roi", 0.0))
        acceptance = float(profile.get("acceptance_rate", 0.0))
        variance = float(profile.get("roi_variance", 0.0))
        exploitation = (reward_discount * roi) + ((1.0 - reward_discount) * acceptance)
        exploration_bonus = exploration * math.sqrt(math.log(max(total_completed, 1) + 1.0) / float(pulls))
        penalized = exploitation + exploration_bonus - (variance * (1.0 - reward_discount))
        return max(0.0, min(1.0, penalized))

    @staticmethod
    def _is_completed_cycle(cycle: Mapping[str, Any]) -> bool:
        if bool(cycle.get("completed")):
            return True
        return str(cycle.get("status") or "").strip().lower() in {"completed", "applied", "accepted"}

    @staticmethod
    def _roi_from_cycle(cycle: Mapping[str, Any]) -> float:
        if cycle.get("roi") is not None:
            return float(cycle.get("roi") or 0.0)
        if cycle.get("fitness_delta") is not None:
            return float(cycle.get("fitness_delta") or 0.0)
        return 0.0

    @staticmethod
    def _clamp(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _bounded(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))


__all__ = ["MutationFitnessEvaluator"]
