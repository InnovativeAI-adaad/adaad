# SPDX-License-Identifier: Apache-2.0
"""
Composable fitness pipeline for mutation scoring.

Senior-grade enhancements in this revision:
- EfficiencyEvaluator: real latency/memory telemetry scoring with op-complexity
  proxy fallback for Pydroid3 / CI environments. Never raises on missing data.
- PolicyComplianceEvaluator: validates required governance metadata fields.
  Circuit-breaker fallback to last-known score prevents infra failures from
  zeroing the fitness pipeline.
- Both evaluators are pluggable into FitnessPipeline and emit structured
  FitnessMetric objects with audit-grade metadata.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional

from runtime.evolution.fitness_orchestrator import FitnessOrchestrator

log = logging.getLogger(__name__)


@lru_cache(maxsize=8192)
def _cached_json_digest(payload: str) -> str:
    from runtime.governance.foundation import sha256_prefixed_digest

    return sha256_prefixed_digest(payload)


@lru_cache(maxsize=8192)
def _cached_canonical_json(material_key: str, payload_items: tuple[tuple[str, Any], ...]) -> str:
    from runtime.governance.foundation import canonical_json

    return canonical_json({"material_key": material_key, "payload": dict(payload_items)})


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


# -- Existing evaluators (unchanged API) --------------------------------------


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


# -- New evaluators -----------------------------------------------------------


class EfficiencyEvaluator(FitnessEvaluator):
    """
    Measures the performance delta of a mutated artifact vs its baseline.

    Scoring contract:
    - score = 1.0 when mutation shows no latency/memory regression.
    - score degrades proportionally beyond configured thresholds.
    - Falls back to op-complexity proxy when no telemetry is available.
      Proxy never blocks; it flags telemetry_missing=True for operator review.

    This evaluator never raises. Missing telemetry is a data gap, not a fault.
    """

    _LATENCY_REGRESSION_THRESHOLD = 0.15   # 15% slowdown triggers penalty
    _MEMORY_REGRESSION_THRESHOLD  = 0.10   # 10% memory increase triggers penalty
    _OP_COMPLEXITY_CAP = 5_000

    def evaluate(self, mutation_data: Dict[str, Any]) -> FitnessMetric:
        t_start = time.monotonic()
        telemetry = mutation_data.get("performance_telemetry") or {}
        telemetry_present = bool(telemetry)

        if telemetry_present:
            score, details = self._score_from_telemetry(telemetry)
        else:
            score, details = self._score_from_proxy(mutation_data)

        details["telemetry_missing"] = not telemetry_present
        details["eval_latency_ms"] = round((time.monotonic() - t_start) * 1000, 2)

        log.debug("EfficiencyEvaluator score=%.3f telemetry=%s", score, telemetry_present)
        return FitnessMetric(
            name="efficiency",
            weight=0.35,
            score=round(score, 4),
            metadata=details,
        )

    def _score_from_telemetry(self, telemetry: Dict[str, Any]):
        latency_delta = float(telemetry.get("latency_delta_pct", 0.0))
        memory_delta  = float(telemetry.get("memory_delta_pct", 0.0))
        flags: List[str] = []

        latency_penalty = 0.0
        if latency_delta > self._LATENCY_REGRESSION_THRESHOLD:
            latency_penalty = min(0.50, latency_delta * 2.0)
            flags.append(f"latency_regression:{latency_delta:.2%}")

        memory_penalty = 0.0
        if memory_delta > self._MEMORY_REGRESSION_THRESHOLD:
            memory_penalty = min(0.30, memory_delta * 1.5)
            flags.append(f"memory_regression:{memory_delta:.2%}")

        score = max(0.0, 1.0 - latency_penalty - memory_penalty)
        return score, {
            "source": "telemetry",
            "latency_delta_pct": latency_delta,
            "memory_delta_pct": memory_delta,
            "flags": flags,
        }

    def _score_from_proxy(self, mutation_data: Dict[str, Any]):
        ops = mutation_data.get("ops") or []
        op_count = len(ops) if isinstance(ops, list) else 0
        complexity = min(op_count * 50, self._OP_COMPLEXITY_CAP)
        score = max(0.0, 1.0 - (complexity / self._OP_COMPLEXITY_CAP))
        return score, {
            "source": "proxy",
            "op_count": op_count,
            "proxy_complexity": complexity,
        }


class PolicyComplianceEvaluator(FitnessEvaluator):
    """
    Validates a mutation against required governance metadata fields.

    Scoring contract:
    - score = 1.0 when all required fields present and governance_profile valid.
    - score degrades proportionally per missing or invalid field.
    - Circuit breaker: infra failures fall back to last-known score (never 0.0).
      Prevents a policy-layer outage from zeroing the fitness pipeline.

    Required fields: agent_id, intent, governance_profile, skill_profile.
    Valid profiles:  strict | high-assurance.
    """

    _REQUIRED_FIELDS = ["agent_id", "intent", "governance_profile", "skill_profile"]
    _VALID_PROFILES  = {"strict", "high-assurance"}
    _TIER_SCORE_MAP  = {"low": 1.0, "medium": 0.75, "high": 0.50, "critical": 0.25}
    _FALLBACK_SCORE  = 0.50

    def __init__(self) -> None:
        self._last_known_score: Optional[float] = None

    def evaluate(self, mutation_data: Dict[str, Any]) -> FitnessMetric:
        try:
            score, meta = self._evaluate_internal(mutation_data)
        except Exception as exc:
            fallback = (
                self._last_known_score
                if self._last_known_score is not None
                else self._FALLBACK_SCORE
            )
            log.warning(
                "PolicyComplianceEvaluator circuit-breaker: fallback=%.2f error=%s",
                fallback, exc,
            )
            return FitnessMetric(
                name="policy_compliance",
                weight=0.30,
                score=round(fallback, 4),
                metadata={"circuit_breaker": True, "error": str(exc)},
            )

        self._last_known_score = score
        return FitnessMetric(
            name="policy_compliance",
            weight=0.30,
            score=round(score, 4),
            metadata=meta,
        )

    def _evaluate_internal(self, mutation_data: Dict[str, Any]):
        field_scores: Dict[str, float] = {}
        flags: List[str] = []

        for f in self._REQUIRED_FIELDS:
            val = mutation_data.get(f)
            if val:
                field_scores[f] = 1.0
            else:
                field_scores[f] = 0.0
                flags.append(f"missing_field:{f}")

        profile = mutation_data.get("governance_profile", "")
        if profile not in self._VALID_PROFILES:
            flags.append(f"invalid_profile:{profile!r}")
            field_scores["governance_profile"] = 0.0

        tier = str(mutation_data.get("tier") or "low").lower()
        tier_score = self._TIER_SCORE_MAP.get(tier, 0.50)
        field_scores["tier"] = tier_score

        total_fields = len(self._REQUIRED_FIELDS) + 1
        composite = sum(field_scores.values()) / total_fields

        return composite, {
            "field_scores": field_scores,
            "flags": flags,
            "tier": tier,
            "passed": composite >= 0.60 and not any("missing_profile" in fl for fl in flags),
        }


# -- Pipeline -----------------------------------------------------------------


class FitnessPipeline:
    def __init__(self, evaluators: List[FitnessEvaluator]):
        self.evaluators = evaluators
        self._orchestrator = FitnessOrchestrator()

    def evaluate(self, mutation_data: Dict[str, Any]) -> Dict[str, Any]:
        # Deterministic materialization cache key for repeated mutation payloads.
        material_key = str(mutation_data.get("mutation_id") or mutation_data.get("epoch_id") or "")
        payload_items = tuple(sorted((str(k), repr(v)) for k, v in mutation_data.items()))
        canonical_payload = _cached_canonical_json(material_key, payload_items)
        payload_hash = _cached_json_digest(canonical_payload)

        metrics = [e.evaluate(mutation_data) for e in self.evaluators]
        total_weight = sum(m.weight for m in metrics) or 1.0
        legacy_weighted_score = sum(m.score * m.weight for m in metrics) / total_weight

        breakdown = {m.name: m.score for m in metrics}
        orchestrator_result = self._orchestrator.score(
            {
                "epoch_id": str(mutation_data.get("epoch_id") or "fitness-pipeline-default"),
                "mutation_tier": mutation_data.get("mutation_tier"),
                "correctness_score": breakdown.get("tests", legacy_weighted_score),
                "efficiency_score": breakdown.get(
                    "efficiency",
                    float(mutation_data.get("efficiency_score", 0.0) or 0.0),
                ),
                "policy_compliance_score": breakdown.get(
                    "policy_compliance",
                    float(mutation_data.get("policy_compliance_score", 1.0) or 0.0),
                ),
                "goal_alignment_score": float(mutation_data.get("goal_alignment_score", 0.0) or 0.0),
                "simulated_market_score": float(
                    mutation_data.get("simulated_market_score", breakdown.get("risk", 0.0)) or 0.0
                ),
                "replay_divergence": bool(mutation_data.get("replay_divergence") or mutation_data.get("divergence_rejected")),
            }
        )

        return {
            "overall_score": orchestrator_result.total_score,
            "material_hash": payload_hash,
            "metrics": [m.__dict__ for m in metrics],
            "breakdown": breakdown,
            "orchestrator": {
                "regime": orchestrator_result.regime,
                "config_hash": orchestrator_result.config_hash,
                "component_breakdown": dict(orchestrator_result.breakdown),
                "weight_snapshot_hash": orchestrator_result.weight_snapshot_hash,
                "algorithm_version": orchestrator_result.algorithm_version,
                "weight_digest": orchestrator_result.weight_digest,
                "divergence_rejected": orchestrator_result.divergence_rejected,
            },
        }


__all__ = [
    "FitnessMetric",
    "FitnessEvaluator",
    "TestOutcomeEvaluator",
    "RiskEvaluator",
    "EfficiencyEvaluator",
    "PolicyComplianceEvaluator",
    "FitnessPipeline",
]
