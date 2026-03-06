# SPDX-License-Identifier: Apache-2.0
"""
WeightAdaptor — self-calibrating scoring weight learner.

Algorithm: coordinate descent with momentum (EMA smoothing).
- For gain_weight and coverage_weight: momentum-based gradient descent keyed
  on prediction accuracy error signal.
- risk_penalty and complexity_penalty remain static in v1 (see design note).
- Prediction accuracy tracked as rolling EMA (alpha=0.3).
- State persisted to JSON after every adapt() call for cross-session learning.

Design note — why risk/complexity weights are static:
  Adapting them requires outcome signals ("was this actually risky?", "was this
  actually complex?") that a test runner does not produce automatically. This
  requires structured post-merge telemetry. Deferred to Phase 2.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from runtime.autonomy.mutation_scaffold import ScoringWeights

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEARNING_RATE: float = 0.05
MOMENTUM:      float = 0.85
MIN_WEIGHT:    float = 0.05
MAX_WEIGHT:    float = 0.70
EMA_ALPHA:     float = 0.30

DEFAULT_STATE_PATH = Path("data/weight_adaptor_state.json")


# ---------------------------------------------------------------------------
# Outcome type
# ---------------------------------------------------------------------------


@dataclass
class MutationOutcome:
    """
    Post-evaluation result for a single MutationCandidate.

    accepted: was the candidate accepted by the scorer?
    improved: did the mutation actually improve the codebase (post-merge signal)?
    predicted_accept: what did the scorer predict?
    """
    mutation_id:       str
    accepted:          bool
    improved:          bool
    predicted_accept:  bool


# ---------------------------------------------------------------------------
# WeightAdaptor
# ---------------------------------------------------------------------------


class WeightAdaptor:
    """
    Epoch-level weight learner using momentum coordinate descent.

    Usage:
        adaptor = WeightAdaptor()
        outcomes = [MutationOutcome(...), ...]
        new_weights = adaptor.adapt(outcomes)
    """

    def __init__(self, state_path: Path = DEFAULT_STATE_PATH) -> None:
        self._path = state_path
        self._weights = ScoringWeights()
        self._epoch_count   = 0
        self._total_outcomes = 0
        self._prediction_accuracy: float = 0.5  # neutral prior
        self._velocity_gain:     float = 0.0
        self._velocity_coverage: float = 0.0
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_weights(self) -> ScoringWeights:
        """Return a snapshot of the current weights (caller should not mutate)."""
        return ScoringWeights(
            gain_weight=self._weights.gain_weight,
            coverage_weight=self._weights.coverage_weight,
            horizon_weight=self._weights.horizon_weight,
            risk_penalty=self._weights.risk_penalty,
            complexity_penalty=self._weights.complexity_penalty,
            acceptance_threshold=self._weights.acceptance_threshold,
        )

    @property
    def prediction_accuracy(self) -> float:
        return self._prediction_accuracy

    @property
    def epoch_count(self) -> int:
        return self._epoch_count

    def adapt(self, outcomes: List[MutationOutcome]) -> ScoringWeights:
        """
        Update weights based on prediction outcomes for one epoch.

        A prediction is 'correct' when:
          (predicted_accept=True  AND improved=True)  OR
          (predicted_accept=False AND improved=False)

        Args:
            outcomes: List of MutationOutcome from the epoch. Empty list is a
                      no-op — weights and counters unchanged.

        Returns:
            Updated ScoringWeights snapshot.
        """
        if not outcomes:
            return self.current_weights

        # Compute epoch accuracy
        correct = sum(
            1 for o in outcomes
            if o.predicted_accept == o.improved
        )
        epoch_accuracy = correct / len(outcomes)

        # Rolling EMA accuracy
        self._prediction_accuracy = (
            EMA_ALPHA * epoch_accuracy + (1.0 - EMA_ALPHA) * self._prediction_accuracy
        )

        # Error signal: positive = under-predicting gains (need higher weight)
        #               negative = over-predicting gains (need lower weight)
        gain_error = epoch_accuracy - 0.5  # centred at chance level

        # Momentum update for gain_weight
        self._velocity_gain = (
            MOMENTUM * self._velocity_gain + LEARNING_RATE * gain_error
        )
        new_gain = self._clamp(self._weights.gain_weight + self._velocity_gain)

        # Coverage weight: inversely proportional signal
        # If gain prediction improves, coverage may be over-weighted; balance.
        coverage_error = -gain_error * 0.5
        self._velocity_coverage = (
            MOMENTUM * self._velocity_coverage + LEARNING_RATE * coverage_error
        )
        new_coverage = self._clamp(self._weights.coverage_weight + self._velocity_coverage)

        self._weights = ScoringWeights(
            gain_weight=new_gain,
            coverage_weight=new_coverage,
            horizon_weight=self._weights.horizon_weight,     # static v1
            risk_penalty=self._weights.risk_penalty,         # static v1
            complexity_penalty=self._weights.complexity_penalty,  # static v1
            acceptance_threshold=self._weights.acceptance_threshold,
        )

        self._epoch_count    += 1
        self._total_outcomes += len(outcomes)
        self._save()
        return self.current_weights

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "weights": {
                "gain_weight":          self._weights.gain_weight,
                "coverage_weight":      self._weights.coverage_weight,
                "horizon_weight":       self._weights.horizon_weight,
                "risk_penalty":         self._weights.risk_penalty,
                "complexity_penalty":   self._weights.complexity_penalty,
                "acceptance_threshold": self._weights.acceptance_threshold,
            },
            "epoch_count":        self._epoch_count,
            "total_outcomes":     self._total_outcomes,
            "prediction_accuracy": round(self._prediction_accuracy, 6),
            "velocity_gain":      self._velocity_gain,
            "velocity_coverage":  self._velocity_coverage,
            "saved_at":           time.time(),
        }
        self._path.write_text(json.dumps(state, indent=2))

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            state = json.loads(self._path.read_text())
            w = state.get("weights", {})
            self._weights = ScoringWeights(
                gain_weight=w.get("gain_weight",          self._weights.gain_weight),
                coverage_weight=w.get("coverage_weight",  self._weights.coverage_weight),
                horizon_weight=w.get("horizon_weight",    self._weights.horizon_weight),
                risk_penalty=w.get("risk_penalty",        self._weights.risk_penalty),
                complexity_penalty=w.get("complexity_penalty", self._weights.complexity_penalty),
                acceptance_threshold=w.get("acceptance_threshold", self._weights.acceptance_threshold),
            )
            self._epoch_count         = state.get("epoch_count", 0)
            self._total_outcomes      = state.get("total_outcomes", 0)
            self._prediction_accuracy = state.get("prediction_accuracy", 0.5)
            self._velocity_gain       = state.get("velocity_gain", 0.0)
            self._velocity_coverage   = state.get("velocity_coverage", 0.0)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Corrupt state — start fresh, do not raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clamp(value: float) -> float:
        return round(min(MAX_WEIGHT, max(MIN_WEIGHT, value)), 6)
