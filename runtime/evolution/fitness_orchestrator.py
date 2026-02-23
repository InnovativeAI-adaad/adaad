# SPDX-License-Identifier: Apache-2.0
"""Deterministic epoch-frozen fitness orchestration across scoring regimes."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, MutableMapping

from runtime.governance.foundation import canonical_json, sha256_prefixed_digest

_COMPONENT_KEYS = (
    "correctness_score",
    "efficiency_score",
    "policy_compliance_score",
    "goal_alignment_score",
    "simulated_market_score",
)

_REGIME_WEIGHTS: Dict[str, Dict[str, float]] = {
    "survival_only": {
        "correctness_score": 0.45,
        "efficiency_score": 0.0,
        "policy_compliance_score": 0.45,
        "goal_alignment_score": 0.10,
        "simulated_market_score": 0.0,
    },
    "hybrid": {
        "correctness_score": 0.35,
        "efficiency_score": 0.20,
        "policy_compliance_score": 0.25,
        "goal_alignment_score": 0.15,
        "simulated_market_score": 0.05,
    },
    "economic_full": {
        "correctness_score": 0.30,
        "efficiency_score": 0.20,
        "policy_compliance_score": 0.20,
        "goal_alignment_score": 0.15,
        "simulated_market_score": 0.15,
    },
}


@dataclass(frozen=True)
class _Snapshot:
    regime: str
    weights: Mapping[str, float]
    config_hash: str


@dataclass(frozen=True)
class _ScoreResult:
    total_score: float
    breakdown: Mapping[str, float]
    regime: str
    config_hash: str


class FitnessOrchestrator:
    """Single-entry fitness scoring with deterministic epoch snapshots."""

    def __init__(self) -> None:
        self._epoch_snapshots: MutableMapping[str, _Snapshot] = {}

    def score(self, context: Mapping[str, Any]) -> _ScoreResult:
        epoch_id = str(context.get("epoch_id") or "")
        if not epoch_id:
            raise ValueError("fitness_context_missing_epoch_id")

        snapshot = self._epoch_snapshots.get(epoch_id)
        if snapshot is None:
            snapshot = self._create_snapshot(context)
            self._epoch_snapshots[epoch_id] = snapshot
            self._append_snapshot_event(epoch_id=epoch_id, context=context, snapshot=snapshot)

        breakdown = self._normalize_breakdown(context)
        weighted = sum(breakdown[name] * snapshot.weights[name] for name in _COMPONENT_KEYS)
        total_score = max(0.0, min(1.0, weighted))
        return _ScoreResult(
            total_score=total_score,
            breakdown=MappingProxyType(dict(breakdown)),
            regime=snapshot.regime,
            config_hash=snapshot.config_hash,
        )

    def _create_snapshot(self, context: Mapping[str, Any]) -> _Snapshot:
        regime = self._regime_for_tier(context.get("mutation_tier"))
        canonical_weights = self._canonicalize_weights(_REGIME_WEIGHTS[regime])
        config_material = {"regime": regime, "weights": canonical_weights}
        config_hash = sha256_prefixed_digest(canonical_json(config_material))
        return _Snapshot(
            regime=regime,
            weights=MappingProxyType(canonical_weights),
            config_hash=config_hash,
        )

    @staticmethod
    def _regime_for_tier(tier: Any) -> str:
        normalized = str(tier or "").strip().lower()
        if normalized in {"critical", "high", "production"}:
            return "survival_only"
        if normalized in {"medium", "staging", "stable"}:
            return "hybrid"
        return "economic_full"

    @staticmethod
    def _append_snapshot_event(*, epoch_id: str, context: Mapping[str, Any], snapshot: _Snapshot) -> None:
        ledger = context.get("ledger")
        if ledger is None or not hasattr(ledger, "append_event"):
            return
        payload = {
            "epoch_id": epoch_id,
            "regime": snapshot.regime,
            "weights": dict(snapshot.weights),
            "config_hash": snapshot.config_hash,
        }
        ledger.append_event("fitness_regime_snapshot", payload)

    @staticmethod
    def _canonicalize_weights(weights: Mapping[str, Any]) -> Dict[str, float]:
        canonical = {key: max(0.0, float(weights.get(key, 0.0) or 0.0)) for key in _COMPONENT_KEYS}
        total = sum(canonical.values())
        if total <= 0.0:
            raise ValueError("fitness_orchestrator_zero_weight_sum")
        return {key: canonical[key] / total for key in sorted(canonical.keys())}

    @staticmethod
    def _normalize_breakdown(context: Mapping[str, Any]) -> Dict[str, float]:
        breakdown: Dict[str, float] = {}
        for key in _COMPONENT_KEYS:
            breakdown[key] = FitnessOrchestrator._clamp(context.get(key, 0.0))
        return breakdown

    @staticmethod
    def _clamp(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0


__all__ = ["FitnessOrchestrator"]
