# SPDX-License-Identifier: Apache-2.0
"""
PenaltyAdaptor — Phase 3 adaptive risk_penalty and complexity_penalty learner.

Purpose:
    Extends WeightAdaptor's static v1 penalty weights with outcome-driven
    momentum descent. Activates only after MIN_EPOCHS_FOR_PENALTY epochs
    of outcome data to prevent premature adaptation on sparse signals.

Algorithm:
    risk_penalty adapts toward observed_risk_rate:
        velocity_risk = MOMENTUM * velocity_risk + LR * (observed_risk_rate - risk_penalty)
        risk_penalty  = clamp(risk_penalty + velocity_risk)

    complexity_penalty adapts toward observed_complexity_rate:
        velocity_complexity = MOMENTUM * velocity_complexity
                            + LR * (observed_complexity_rate - complexity_penalty)
        complexity_penalty  = clamp(complexity_penalty + velocity_complexity)

    observed_risk_rate:
        Fraction of accepted mutations that had risk_score > RISK_SIGNAL_THRESHOLD.
        High rate = risk_penalty was under-penalizing; signal is positive (push up).
        Low rate  = risk_penalty was over-penalizing; signal is negative (push down).

    observed_complexity_rate: analogous for complexity field.

Constitutional invariants:
    - PenaltyAdaptor is ADVISORY. It returns updated ScoringWeights for
      WeightAdaptor to apply. GovernanceGate is never invoked here.
    - All weights stay in [MIN_WEIGHT, MAX_WEIGHT] = [0.05, 0.70].
    - Inactive below MIN_EPOCHS_FOR_PENALTY (returns unchanged weights).
    - Deterministic: pure float arithmetic on deterministic inputs.

Activation contract:
    PenaltyAdaptor.is_active(epoch_count) → True when epoch_count >= 5.
    Below threshold: adapt() is a no-op pass-through (weights unchanged).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from runtime.autonomy.mutation_scaffold import ScoringWeights

# --- Constants ----------------------------------------------------------------

LEARNING_RATE: float         = 0.04    # Slightly lower than gain LR — penalty signals noisier
MOMENTUM: float              = 0.80
MIN_WEIGHT: float            = 0.05
MAX_WEIGHT: float            = 0.70
EMA_ALPHA: float             = 0.25    # Smoother EMA for noisy penalty signals

MIN_EPOCHS_FOR_PENALTY: int  = 5       # Wait for baseline outcome data
RISK_SIGNAL_THRESHOLD: float = 0.50    # risk_score above this = mutation "was risky"
COMPLEXITY_SIGNAL_THRESHOLD: float = 0.50  # complexity above this = mutation "was complex"

DEFAULT_STATE_PATH = Path("data/penalty_adaptor_state.json")


# --- Outcome type -------------------------------------------------------------

@dataclass
class PenaltyOutcome:
    """
    Outcome signal for a single mutation — what penalty signals did it produce?

    Fields:
        mutation_id:       Unique identifier.
        accepted:          Was this mutation accepted by GovernanceGate?
        risk_score:        Observed risk_score from MutationCandidate (0–1).
        complexity_score:  Observed complexity from MutationCandidate (0–1).
        actually_risky:    Post-merge signal — did the mutation cause regression?
                           None = unknown (no post-merge data yet; use heuristic).
        actually_complex:  Post-merge signal — did the mutation require rollback?
                           None = unknown.
    """
    mutation_id:      str
    accepted:         bool
    risk_score:       float
    complexity_score: float
    actually_risky:   Optional[bool] = None
    actually_complex: Optional[bool] = None


# --- PenaltyAdaptor ----------------------------------------------------------

class PenaltyAdaptor:
    """
    Phase 3 adaptive penalty weight learner.

    Usage:
        adaptor = PenaltyAdaptor()
        outcomes = [PenaltyOutcome(...), ...]
        updated = adaptor.adapt(weights, outcomes, epoch_count=12)
        # updated.risk_penalty and updated.complexity_penalty are now adaptive
    """

    def __init__(self, state_path: Path = DEFAULT_STATE_PATH) -> None:
        self._path = state_path
        self._velocity_risk:       float = 0.0
        self._velocity_complexity: float = 0.0
        self._ema_risk_rate:       float = 0.5   # neutral prior
        self._ema_complexity_rate: float = 0.5
        self._epoch_count:         int   = 0
        self._total_outcomes:      int   = 0
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def is_active(epoch_count: int) -> bool:
        """True when enough epochs have passed to activate penalty adaptation."""
        return epoch_count >= MIN_EPOCHS_FOR_PENALTY

    @property
    def epoch_count(self) -> int:
        return self._epoch_count

    def adapt(
        self,
        current_weights: ScoringWeights,
        outcomes: List[PenaltyOutcome],
        epoch_count: int,
    ) -> ScoringWeights:
        """
        Return updated ScoringWeights with adapted risk_penalty and complexity_penalty.

        Below MIN_EPOCHS_FOR_PENALTY: returns current_weights unchanged (no-op).
        Empty outcomes: returns current_weights unchanged.

        Args:
            current_weights: Current ScoringWeights (from WeightAdaptor).
            outcomes:        PenaltyOutcome list for this epoch.
            epoch_count:     Total epochs completed (drives activation gate).

        Returns:
            New ScoringWeights with updated risk_penalty and complexity_penalty.
            All other fields copied from current_weights unchanged.
        """
        if not outcomes or not self.is_active(epoch_count):
            return current_weights

        # Derive risk signal
        observed_risk_rate = self._compute_risk_rate(outcomes)
        observed_complexity_rate = self._compute_complexity_rate(outcomes)

        # EMA smooth the observed rates
        self._ema_risk_rate = (
            EMA_ALPHA * observed_risk_rate + (1.0 - EMA_ALPHA) * self._ema_risk_rate
        )
        self._ema_complexity_rate = (
            EMA_ALPHA * observed_complexity_rate
            + (1.0 - EMA_ALPHA) * self._ema_complexity_rate
        )

        # Momentum update for risk_penalty
        # Signal: if observed_risk_rate > current risk_penalty → push up (risky mutations slipping through)
        # Signal: if observed_risk_rate < current risk_penalty → push down (over-penalizing)
        risk_error = self._ema_risk_rate - current_weights.risk_penalty
        self._velocity_risk = (
            MOMENTUM * self._velocity_risk + LEARNING_RATE * risk_error
        )
        new_risk_penalty = _clamp(current_weights.risk_penalty + self._velocity_risk)

        # Momentum update for complexity_penalty
        complexity_error = self._ema_complexity_rate - current_weights.complexity_penalty
        self._velocity_complexity = (
            MOMENTUM * self._velocity_complexity + LEARNING_RATE * complexity_error
        )
        new_complexity_penalty = _clamp(
            current_weights.complexity_penalty + self._velocity_complexity
        )

        self._epoch_count    += 1
        self._total_outcomes += len(outcomes)
        self._save(current_weights, new_risk_penalty, new_complexity_penalty)

        return ScoringWeights(
            gain_weight=current_weights.gain_weight,
            coverage_weight=current_weights.coverage_weight,
            horizon_weight=current_weights.horizon_weight,
            risk_penalty=new_risk_penalty,
            complexity_penalty=new_complexity_penalty,
            acceptance_threshold=current_weights.acceptance_threshold,
        )

    def summary(self) -> dict:
        """Serialisable state for health endpoints and telemetry."""
        return {
            "algorithm":             "momentum_penalty_descent",
            "epoch_count":           self._epoch_count,
            "total_outcomes":        self._total_outcomes,
            "ema_risk_rate":         round(self._ema_risk_rate, 4),
            "ema_complexity_rate":   round(self._ema_complexity_rate, 4),
            "velocity_risk":         round(self._velocity_risk, 6),
            "velocity_complexity":   round(self._velocity_complexity, 6),
            "min_epochs_for_activation": MIN_EPOCHS_FOR_PENALTY,
        }

    # ------------------------------------------------------------------
    # Signal derivation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_risk_rate(outcomes: List[PenaltyOutcome]) -> float:
        """
        Observed risk rate: fraction of mutations where risk signal fired.

        Priority:
          1. Use actually_risky if available (post-merge signal, highest quality).
          2. Heuristic: risk_score > RISK_SIGNAL_THRESHOLD AND accepted
             (accepted high-risk mutations are the ones we care about most).
        """
        if not outcomes:
            return 0.5  # neutral prior
        signals = []
        for o in outcomes:
            if o.actually_risky is not None:
                signals.append(1.0 if o.actually_risky else 0.0)
            elif o.accepted:
                # Heuristic for accepted mutations only — rejected ones already penalized
                signals.append(1.0 if o.risk_score > RISK_SIGNAL_THRESHOLD else 0.0)
        if not signals:
            return 0.5
        return round(sum(signals) / len(signals), 4)

    @staticmethod
    def _compute_complexity_rate(outcomes: List[PenaltyOutcome]) -> float:
        """Observed complexity rate, analogous to risk rate."""
        if not outcomes:
            return 0.5
        signals = []
        for o in outcomes:
            if o.actually_complex is not None:
                signals.append(1.0 if o.actually_complex else 0.0)
            elif o.accepted:
                signals.append(1.0 if o.complexity_score > COMPLEXITY_SIGNAL_THRESHOLD else 0.0)
        if not signals:
            return 0.5
        return round(sum(signals) / len(signals), 4)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(
        self,
        current_weights: ScoringWeights,
        new_risk: float,
        new_complexity: float,
    ) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "velocity_risk":        self._velocity_risk,
            "velocity_complexity":  self._velocity_complexity,
            "ema_risk_rate":        self._ema_risk_rate,
            "ema_complexity_rate":  self._ema_complexity_rate,
            "epoch_count":          self._epoch_count,
            "total_outcomes":       self._total_outcomes,
            "last_risk_penalty":    new_risk,
            "last_complexity_penalty": new_complexity,
            "saved_at":             time.time(),
        }
        self._path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            state = json.loads(self._path.read_text(encoding="utf-8"))
            self._velocity_risk       = float(state.get("velocity_risk",       0.0))
            self._velocity_complexity = float(state.get("velocity_complexity", 0.0))
            self._ema_risk_rate       = float(state.get("ema_risk_rate",       0.5))
            self._ema_complexity_rate = float(state.get("ema_complexity_rate", 0.5))
            self._epoch_count         = int(state.get("epoch_count",   0))
            self._total_outcomes      = int(state.get("total_outcomes", 0))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass  # Corrupt state — start fresh


# --- Helpers -----------------------------------------------------------------

def _clamp(value: float) -> float:
    return round(min(MAX_WEIGHT, max(MIN_WEIGHT, value)), 6)


def build_penalty_outcomes_from_scores(
    scored_candidates: list,
    simulate: bool = True,
) -> List[PenaltyOutcome]:
    """
    Build PenaltyOutcome list from scored MutationScore objects.

    simulate=True:  Use heuristic (score > 0.40 → assumed not actually_risky).
                    Safe for offline / CI use.
    simulate=False: Returns outcomes with actually_risky=None (post-merge signal
                    not yet available). Caller must inject real outcomes later.
    """
    outcomes = []
    for score in scored_candidates:
        risk_score = 0.5
        complexity_score = 0.5
        bd = getattr(score, "dimension_breakdown", {}) or {}
        # Reverse the breakdown to recover risk_score input
        risk_contrib = abs(float(bd.get("risk_penalty_contrib", 0.0)))
        complexity_contrib = abs(float(bd.get("complexity_penalty_contrib", 0.0)))
        # Approximate: contrib ≈ score * weight → score ≈ contrib / weight
        if risk_contrib > 0:
            risk_score = min(1.0, risk_contrib / 0.20)
        if complexity_contrib > 0:
            complexity_score = min(1.0, complexity_contrib / 0.10)

        actually_risky: Optional[bool] = None
        actually_complex: Optional[bool] = None
        if simulate:
            # Heuristic: if accepted with high risk_score, treat as a signal
            actually_risky   = bool(score.accepted and risk_score > RISK_SIGNAL_THRESHOLD)
            actually_complex = bool(score.accepted and complexity_score > COMPLEXITY_SIGNAL_THRESHOLD)

        outcomes.append(PenaltyOutcome(
            mutation_id=str(getattr(score, "mutation_id", "")),
            accepted=bool(getattr(score, "accepted", False)),
            risk_score=risk_score,
            complexity_score=complexity_score,
            actually_risky=actually_risky,
            actually_complex=actually_complex,
        ))
    return outcomes


__all__ = [
    "PenaltyAdaptor",
    "PenaltyOutcome",
    "build_penalty_outcomes_from_scores",
    "MIN_EPOCHS_FOR_PENALTY",
    "RISK_SIGNAL_THRESHOLD",
    "COMPLEXITY_SIGNAL_THRESHOLD",
]
