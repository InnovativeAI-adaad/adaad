# SPDX-License-Identifier: Apache-2.0
"""Deterministic epoch-frozen fitness orchestration across scoring regimes."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, MutableMapping

from runtime.evolution.fitness_signal_adapter import FitnessSignalInput, adapt_context_to_fitness_signal_input
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
    weight_snapshot_hash: str
    weight_digest: str
    seed_fingerprint: str
    algorithm_version: str
    divergence_rejected: bool


@dataclass(frozen=True)
class _ScoreResult:
    total_score: float
    breakdown: Mapping[str, float]
    regime: str
    config_hash: str
    weight_snapshot_hash: str
    algorithm_version: str
    weight_digest: str
    divergence_rejected: bool


class FitnessOrchestrator:
    """Single-entry fitness scoring with deterministic epoch snapshots.

    Live market signal injection
    ----------------------------
    ``inject_live_signal(payload)`` accepts a dict from ``MarketFitnessIntegrator``
    and stores an advisory ``live_market_score`` override keyed by epoch_id.
    On the next ``score()`` call for that epoch the override replaces
    ``simulated_market_score`` in the context before weight application.
    Overrides are advisory — GovernanceGate retains final authority.
    """

    def __init__(self) -> None:
        self._epoch_snapshots: MutableMapping[str, _Snapshot] = {}
        self._live_signal_overrides: MutableMapping[str, Dict[str, Any]] = {}

    def inject_live_signal(self, payload: Dict[str, Any]) -> None:
        """Advisory live market signal override from MarketFitnessIntegrator.

        Stores the payload keyed by epoch_id.  The next ``score()`` call for
        that epoch will substitute ``payload['live_market_score']`` for
        ``simulated_market_score`` in the scoring context.

        Never raises — failures are logged and silently dropped.
        """
        try:
            epoch_id = str(payload.get("epoch_id") or "")
            if not epoch_id:
                return
            self._live_signal_overrides[epoch_id] = dict(payload)
        except Exception:  # pragma: no cover
            pass

    def _apply_live_override(
        self, epoch_id: str, context: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Return a context with live_market_score substituted when available."""
        override = self._live_signal_overrides.get(epoch_id)
        if override is None:
            return context
        live_score = override.get("live_market_score")
        if live_score is None:
            return context
        merged: Dict[str, Any] = dict(context)
        merged["simulated_market_score"] = max(0.0, min(1.0, float(live_score)))
        return merged

    def score(self, context: Mapping[str, Any]) -> _ScoreResult:
        epoch_id = str(context.get("epoch_id") or "")
        if not epoch_id:
            raise ValueError("fitness_context_missing_epoch_id")

        # Apply live market signal override (advisory — no authority change)
        context = self._apply_live_override(epoch_id, context)
        signal_input = adapt_context_to_fitness_signal_input(context)

        snapshot = self._epoch_snapshots.get(epoch_id)
        if snapshot is None:
            snapshot = self._create_snapshot(context, signal_input=signal_input)
            self._epoch_snapshots[epoch_id] = snapshot
            self._append_snapshot_event(epoch_id=epoch_id, context=context, snapshot=snapshot)

        breakdown = self._normalize_breakdown(signal_input)
        weighted = sum(breakdown[name] * snapshot.weights[name] for name in _COMPONENT_KEYS)
        total_score = max(0.0, min(1.0, weighted))
        if snapshot.divergence_rejected:
            total_score = 0.0
        return _ScoreResult(
            total_score=total_score,
            breakdown=MappingProxyType(dict(breakdown)),
            regime=snapshot.regime,
            config_hash=snapshot.config_hash,
            weight_snapshot_hash=snapshot.weight_snapshot_hash,
            algorithm_version=snapshot.algorithm_version,
            weight_digest=snapshot.weight_digest,
            divergence_rejected=snapshot.divergence_rejected,
        )

    def _create_snapshot(self, context: Mapping[str, Any], *, signal_input: FitnessSignalInput) -> _Snapshot:
        regime = self._regime_for_tier(signal_input.mutation_tier)
        canonical_weights = self._canonicalize_weights(_REGIME_WEIGHTS[regime])
        deterministic_seed = str(context.get("deterministic_seed") or "").strip()
        seed_fingerprint = sha256_prefixed_digest(canonical_json({"deterministic_seed": deterministic_seed})) if deterministic_seed else "sha256:0"
        weight_snapshot_hash = sha256_prefixed_digest(canonical_json({"regime": regime, "weights": canonical_weights}))
        weight_digest = sha256_prefixed_digest(canonical_json(canonical_weights))
        config_material = {
            "regime": regime,
            "weights": canonical_weights,
            "seed_fingerprint": seed_fingerprint,
            "algorithm_version": signal_input.algorithm_version,
            "divergence_rejected": bool(signal_input.divergence_rejected),
        }
        config_hash = sha256_prefixed_digest(canonical_json(config_material))
        return _Snapshot(
            regime=regime,
            weights=MappingProxyType(canonical_weights),
            config_hash=config_hash,
            weight_snapshot_hash=weight_snapshot_hash,
            weight_digest=weight_digest,
            seed_fingerprint=seed_fingerprint,
            algorithm_version=signal_input.algorithm_version,
            divergence_rejected=bool(signal_input.divergence_rejected),
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
            "weight_snapshot_hash": snapshot.weight_snapshot_hash,
            "weight_digest": snapshot.weight_digest,
            "seed_fingerprint": snapshot.seed_fingerprint,
            "algorithm_version": snapshot.algorithm_version,
            "divergence_rejected": bool(snapshot.divergence_rejected),
        }
        ledger.append_event("fitness_regime_snapshot", payload)
        ledger.append_event(
            "EpochMetadataEvent",
            {
                "epoch_id": epoch_id,
                "metadata": {
                    "fitness_weight_snapshot_hash": snapshot.weight_snapshot_hash,
                    "fitness_weight_digest": snapshot.weight_digest,
                    "fitness_config_hash": snapshot.config_hash,
                    "fitness_seed_fingerprint": snapshot.seed_fingerprint,
                    "fitness_algorithm_version": snapshot.algorithm_version,
                    "fitness_divergence_rejected": bool(snapshot.divergence_rejected),
                },
            },
        )

    @staticmethod
    def _canonicalize_weights(weights: Mapping[str, Any]) -> Dict[str, float]:
        canonical = {key: max(0.0, float(weights.get(key, 0.0) or 0.0)) for key in _COMPONENT_KEYS}
        total = sum(canonical.values())
        if total <= 0.0:
            raise ValueError("fitness_orchestrator_zero_weight_sum")
        return {key: canonical[key] / total for key in sorted(canonical.keys())}

    @staticmethod
    def _normalize_breakdown(signal_input: Any) -> Dict[str, float]:
        return {
            "correctness_score": signal_input.correctness_score,
            "efficiency_score": signal_input.efficiency_score,
            "policy_compliance_score": signal_input.policy_compliance_score,
            "goal_alignment_score": signal_input.goal_alignment_score,
            "simulated_market_score": signal_input.simulated_market_score,
        }


__all__ = ["FitnessOrchestrator"]
