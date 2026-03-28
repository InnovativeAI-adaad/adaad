# SPDX-License-Identifier: Apache-2.0
"""Phase 62 — Multi-Horizon Fitness Engine v2.

Constitutional invariants enforced here:
  FIT-BOUND-0  All signal weights in [0.05, 0.70]; composite in [0.0, 1.0].
  FIT-DET-0    Composite score deterministic given identical inputs.
  FIT-DIV-0    Replay divergence → composite = 0.0; total rejection; overrides all.
  FIT-ARCH-0   Architectural signal returns 0.5 (neutral) until PHASE62_ARCH_SIGNAL=true.

Forbidden imports: runtime.governance.gate (direct), app.*, adaad.orchestrator.*
All timestamps via RuntimeDeterminismProvider — no direct datetime calls.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WEIGHT_FLOOR: float = 0.05
_WEIGHT_CEILING: float = 0.70
_WEIGHT_SUM_TOLERANCE: float = 1e-9
_COMPOSITE_FLOOR: float = 0.0
_COMPOSITE_CEILING: float = 1.0

# Signal keys in fixed canonical order (required for FIT-DET-0).
# Phase 93 (INNOV-09 AFIT): aesthetic_fitness added as 7th signal.
_SIGNAL_KEYS: tuple[str, ...] = (
    "test_fitness",
    "complexity_fitness",
    "performance_fitness",
    "governance_compliance",
    "architectural_fitness",
    "determinism_fitness",
    "aesthetic_fitness",   # INNOV-09 — Phase 93
)

# Default weights (must sum to 1.0; each in [0.05, 0.70]).
# Phase 93: aesthetic_fitness introduced at 0.05; prior six signals
# rebalanced proportionally to absorb the 0.05 reduction.
_DEFAULT_WEIGHTS: Dict[str, float] = {
    "test_fitness":          0.28,
    "complexity_fitness":    0.19,
    "performance_fitness":   0.14,
    "governance_compliance": 0.14,
    "architectural_fitness": 0.11,
    "determinism_fitness":   0.09,
    "aesthetic_fitness":     0.05,   # AFIT-WEIGHT-0: range [0.05, 0.30]
}

# code_pressure is a modifier (−0.05 × net_node_additions), not a signal weight.
_CODE_PRESSURE_MULTIPLIER: float = -0.05


# ---------------------------------------------------------------------------
# FitnessConfig — immutable; FIT-BOUND-0 enforced at construction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FitnessConfig:
    """Immutable fitness weight configuration.

    Raises ValueError on any FIT-BOUND-0 violation so that FitnessEngineV2
    instantiation is aborted — epoch does not proceed with invalid weights.
    """

    weights: Mapping[str, float]
    code_pressure_multiplier: float = _CODE_PRESSURE_MULTIPLIER

    def __post_init__(self) -> None:
        # Validate keys
        missing = set(_SIGNAL_KEYS) - set(self.weights)
        if missing:
            raise ValueError(
                f"FIT-BOUND-0 violation: missing signal keys {missing}"
            )
        extra = set(self.weights) - set(_SIGNAL_KEYS)
        if extra:
            raise ValueError(
                f"FIT-BOUND-0 violation: unknown signal keys {extra}"
            )
        # Validate individual bounds
        for key in _SIGNAL_KEYS:
            w = float(self.weights[key])
            if not (_WEIGHT_FLOOR <= w <= _WEIGHT_CEILING):
                raise ValueError(
                    f"FIT-BOUND-0 violation: weight {key}={w} outside "
                    f"[{_WEIGHT_FLOOR}, {_WEIGHT_CEILING}]"
                )
        # Validate sum (explicit ordered accumulation — FIT-DET-0)
        total: float = 0.0
        for key in _SIGNAL_KEYS:
            total = total + float(self.weights[key])
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(
                f"FIT-BOUND-0 violation: weights sum to {total}, expected 1.0"
            )
        # Validate code_pressure_multiplier bounds
        if not (-0.15 <= self.code_pressure_multiplier <= 0.0):
            raise ValueError(
                f"FIT-BOUND-0 violation: code_pressure_multiplier "
                f"{self.code_pressure_multiplier} outside [-0.15, 0.0]"
            )

    @classmethod
    def default(cls) -> "FitnessConfig":
        return cls(weights=dict(_DEFAULT_WEIGHTS))


# ---------------------------------------------------------------------------
# FitnessContext — input bundle consumed by FitnessEngineV2
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReplayResult:
    """Minimal replay verification result consumed for FIT-DIV-0."""
    diverged: bool
    divergence_class: str = "none"
    epoch_fingerprint: str = ""


@dataclass(frozen=True)
class FitnessContext:
    """Canonical input bundle for FitnessEngineV2.score().

    All fields are required for deterministic scoring (FIT-DET-0).
    Advisory fields (code_intel_model_hash, epoch_memory_snapshot) are
    consumed as opaque strings — no re-computation during scoring.
    """

    epoch_id: str
    # Per-epoch signal inputs (all bounded [0.0, 1.0] by caller)
    test_fitness: float = 0.0
    complexity_fitness: float = 0.0
    performance_fitness: float = 0.0
    governance_compliance: float = 0.0
    # FIT-ARCH-0: only consumed when _architecture_active=True in engine
    architectural_fitness: float = 0.5
    determinism_fitness: float = 1.0
    # INNOV-09 Phase 93: aesthetic readability score from AestheticFitnessScorer.
    # Defaults to 0.5 (neutral) — AFIT-0 fallback semantics when source unavailable.
    aesthetic_fitness: float = 0.5
    # Code pressure: net AST node additions (positive = additions, negative = deletions)
    net_node_additions: int = 0
    # Replay result for FIT-DIV-0
    replay_result: ReplayResult = field(
        default_factory=lambda: ReplayResult(diverged=False)
    )
    # Determinism evidence (opaque keys consumed for score_hash)
    code_intel_model_hash: str = ""
    epoch_memory_snapshot: str = ""
    policy_config_hash: str = ""


# ---------------------------------------------------------------------------
# FitnessScores — frozen output; includes score_hash for EpochEvidence
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FitnessScores:
    """Deterministic output record from FitnessEngineV2.

    score_hash = sha256(json.dumps(scores_dict, sort_keys=True))
    Must be included in EpochEvidence.fitness_summary (CEL Step 12).
    """

    epoch_id: str
    test_fitness: float
    complexity_fitness: float
    performance_fitness: float
    governance_compliance: float
    architectural_fitness: float
    determinism_fitness: float
    aesthetic_fitness: float          # INNOV-09 Phase 93
    code_pressure_adjustment: float
    composite_score: float
    # FIT-DIV-0 override flag
    determinism_override: bool
    # FIT-ARCH-0 activation flag
    architecture_active: bool
    # Deterministic evidence hash
    score_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch_id": self.epoch_id,
            "test_fitness": self.test_fitness,
            "complexity_fitness": self.complexity_fitness,
            "performance_fitness": self.performance_fitness,
            "governance_compliance": self.governance_compliance,
            "architectural_fitness": self.architectural_fitness,
            "determinism_fitness": self.determinism_fitness,
            "aesthetic_fitness": self.aesthetic_fitness,
            "code_pressure_adjustment": self.code_pressure_adjustment,
            "composite_score": self.composite_score,
            "determinism_override": self.determinism_override,
            "architecture_active": self.architecture_active,
            "score_hash": self.score_hash,
        }


def _compute_score_hash(
    epoch_id: str,
    signals: Dict[str, float],
    composite: float,
    determinism_override: bool,
    architecture_active: bool,
    context: FitnessContext,
) -> str:
    """Deterministic sha256 over all scoring inputs and outputs (FIT-DET-0)."""
    payload: Dict[str, Any] = {
        "epoch_id": epoch_id,
        "signals": {k: signals[k] for k in sorted(signals)},
        "composite_score": composite,
        "determinism_override": determinism_override,
        "architecture_active": architecture_active,
        "code_intel_model_hash": context.code_intel_model_hash,
        "epoch_memory_snapshot": context.epoch_memory_snapshot,
        "policy_config_hash": context.policy_config_hash,
        "net_node_additions": context.net_node_additions,
        "replay_diverged": context.replay_result.diverged,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# FitnessEngineV2 — stateless evaluator
# ---------------------------------------------------------------------------

class FitnessEngineV2:
    """Canonical Phase 62 multi-horizon fitness evaluator.

    Stateless: no mutable internal state after construction.
    Accepts FitnessContext; returns FitnessScores.

    FIT-ARCH-0: architectural signal activation is controlled by the
    PHASE62_ARCH_SIGNAL environment variable. Set to 'true' only after
    Phase 62 calibration is complete. Do not set prematurely.
    """

    _TRUTHY = {"1", "true", "yes", "on"}

    def __init__(
        self,
        config: Optional[FitnessConfig] = None,
    ) -> None:
        # FIT-BOUND-0: validated at FitnessConfig construction above.
        self._config: FitnessConfig = config if config is not None else FitnessConfig.default()
        # FIT-ARCH-0: activation flag — read once at construction; not mutable.
        self._architecture_active: bool = (
            os.getenv("PHASE62_ARCH_SIGNAL", "").strip().lower() in self._TRUTHY
        )

    @property
    def architecture_active(self) -> bool:
        return self._architecture_active

    def score(self, context: FitnessContext) -> FitnessScores:
        """Compute multi-horizon fitness scores.

        Evaluation order (fixed — FIT-DET-0):
          1. FIT-DIV-0 check  (determinism override applied first)
          2. Signal collection
          3. FIT-ARCH-0 neutral substitution
          4. Code pressure modifier
          5. Weighted composite accumulation (explicit order)
          6. Composite clamp
          7. score_hash computation
        """
        # ------------------------------------------------------------------ #
        # Step 1 — FIT-DIV-0: replay divergence → total rejection
        # ------------------------------------------------------------------ #
        determinism_override = context.replay_result.diverged

        # ------------------------------------------------------------------ #
        # Step 2 — Collect per-signal scores (bounded [0.0, 1.0] by clamping)
        # ------------------------------------------------------------------ #
        raw_signals: Dict[str, float] = {
            "test_fitness": _clamp(context.test_fitness),
            "complexity_fitness": _clamp(context.complexity_fitness),
            "performance_fitness": _clamp(context.performance_fitness),
            "governance_compliance": _clamp(context.governance_compliance),
            "architectural_fitness": _clamp(context.architectural_fitness),
            "determinism_fitness": _clamp(context.determinism_fitness),
            "aesthetic_fitness": _clamp(context.aesthetic_fitness),   # INNOV-09
        }

        # ------------------------------------------------------------------ #
        # Step 3 — FIT-ARCH-0: neutral substitution when not active
        # ------------------------------------------------------------------ #
        if not self._architecture_active:
            raw_signals["architectural_fitness"] = 0.5

        # ------------------------------------------------------------------ #
        # Step 4 — Code pressure modifier (bounded [-0.15, 0.0])
        # ------------------------------------------------------------------ #
        net_additions = max(0, context.net_node_additions)  # only positive additions penalised
        code_pressure_adjustment = max(
            -0.15,
            self._config.code_pressure_multiplier * net_additions
        )

        # ------------------------------------------------------------------ #
        # Step 5 — Weighted composite (explicit ordered accumulation — FIT-DET-0)
        # ------------------------------------------------------------------ #
        composite: float = 0.0
        weights = self._config.weights
        for key in _SIGNAL_KEYS:
            composite = composite + float(weights[key]) * raw_signals[key]
        composite = composite + code_pressure_adjustment

        # ------------------------------------------------------------------ #
        # Step 6 — Clamp composite; FIT-DIV-0 override
        # ------------------------------------------------------------------ #
        composite = _clamp(composite)
        if determinism_override:
            composite = 0.0

        # ------------------------------------------------------------------ #
        # Step 7 — score_hash (FIT-DET-0 evidence)
        # ------------------------------------------------------------------ #
        score_hash = _compute_score_hash(
            epoch_id=context.epoch_id,
            signals=raw_signals,
            composite=composite,
            determinism_override=determinism_override,
            architecture_active=self._architecture_active,
            context=context,
        )

        return FitnessScores(
            epoch_id=context.epoch_id,
            test_fitness=raw_signals["test_fitness"],
            complexity_fitness=raw_signals["complexity_fitness"],
            performance_fitness=raw_signals["performance_fitness"],
            governance_compliance=raw_signals["governance_compliance"],
            architectural_fitness=raw_signals["architectural_fitness"],
            determinism_fitness=raw_signals["determinism_fitness"],
            aesthetic_fitness=raw_signals["aesthetic_fitness"],
            code_pressure_adjustment=code_pressure_adjustment,
            composite_score=composite,
            determinism_override=determinism_override,
            architecture_active=self._architecture_active,
            score_hash=score_hash,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp to [lo, hi]. Used in scoring path — must not import random/time."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return lo
    return lo if v < lo else (hi if v > hi else v)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "FitnessConfig",
    "FitnessContext",
    "FitnessEngineV2",
    "FitnessScores",
    "ReplayResult",
    "_DEFAULT_WEIGHTS",
    "_SIGNAL_KEYS",
    "_WEIGHT_FLOOR",
    "_WEIGHT_CEILING",
]
