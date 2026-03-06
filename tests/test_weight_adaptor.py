# SPDX-License-Identifier: Apache-2.0
"""Test suite for runtime/autonomy/weight_adaptor.py"""

from __future__ import annotations

import pytest
from pathlib import Path

from runtime.autonomy.weight_adaptor import (
    MAX_WEIGHT,
    MIN_WEIGHT,
    MutationOutcome,
    WeightAdaptor,
)
from runtime.autonomy.mutation_scaffold import ScoringWeights


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _outcome(accepted: bool, improved: bool, predicted: bool, mid: str = "mc") -> MutationOutcome:
    return MutationOutcome(
        mutation_id=mid,
        accepted=accepted,
        improved=improved,
        predicted_accept=predicted,
    )


@pytest.fixture
def adaptor(tmp_path):
    return WeightAdaptor(state_path=tmp_path / "weights.json")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_default_weights_match_v1(adaptor) -> None:
    w = adaptor.current_weights
    assert w.gain_weight == pytest.approx(0.35)
    assert w.coverage_weight == pytest.approx(0.25)
    assert w.acceptance_threshold == pytest.approx(0.24)  # DEFAULT_ACCEPTANCE_THRESHOLD = 0.24


def test_adapt_increases_accuracy(adaptor) -> None:
    # 5 epochs of perfect predictions
    for _ in range(5):
        outcomes = [
            _outcome(True, True, True,  f"mc-{i}") for i in range(5)
        ] + [
            _outcome(False, False, False, f"mc-rej-{i}") for i in range(5)
        ]
        adaptor.adapt(outcomes)
    assert adaptor.prediction_accuracy > 0.60


def test_weight_bounds_enforced(adaptor) -> None:
    # Send extreme alternating signals across many epochs
    for i in range(30):
        sign = 1 if i % 2 == 0 else -1
        outcomes = [
            _outcome(True, sign > 0, True, f"mc-{i}")
        ]
        adaptor.adapt(outcomes)
    w = adaptor.current_weights
    assert MIN_WEIGHT <= w.gain_weight <= MAX_WEIGHT
    assert MIN_WEIGHT <= w.coverage_weight <= MAX_WEIGHT


def test_empty_outcomes_noop(adaptor) -> None:
    w_before = adaptor.current_weights
    ec_before = adaptor.epoch_count
    adaptor.adapt([])
    assert adaptor.epoch_count == ec_before
    assert adaptor.current_weights.gain_weight == pytest.approx(w_before.gain_weight)


def test_persistence_roundtrip(tmp_path) -> None:
    path = tmp_path / "weights.json"
    a1 = WeightAdaptor(state_path=path)
    outcomes = [_outcome(True, True, True, f"mc-{i}") for i in range(5)]
    a1.adapt(outcomes)
    a2 = WeightAdaptor(state_path=path)
    assert a2.epoch_count == 1
    assert a2.current_weights.gain_weight == pytest.approx(a1.current_weights.gain_weight)


def test_momentum_smoothing_convergence(adaptor) -> None:
    """Alternating signals should produce bounded velocity (momentum dampens oscillation)."""
    weights_over_time = []
    for i in range(20):
        improved = i % 2 == 0
        adaptor.adapt([_outcome(True, improved, True, f"mc-{i}")])
        weights_over_time.append(adaptor.current_weights.gain_weight)
    # Weight should not oscillate more than ±0.15 from start (0.35)
    assert all(0.35 - 0.15 <= w <= 0.35 + 0.15 for w in weights_over_time)
