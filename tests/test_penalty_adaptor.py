# SPDX-License-Identifier: Apache-2.0
"""Tests for PenaltyAdaptor — Phase 3 adaptive risk/complexity weights."""
from __future__ import annotations
import pytest
from pathlib import Path
from runtime.autonomy.penalty_adaptor import (
    PenaltyAdaptor, PenaltyOutcome,
    MIN_EPOCHS_FOR_PENALTY, RISK_SIGNAL_THRESHOLD,
    _clamp,
)
from runtime.autonomy.mutation_scaffold import ScoringWeights


def _w() -> ScoringWeights:
    return ScoringWeights()

def _o(accepted=True, risk=0.5, complexity=0.5, actually_risky=None, actually_complex=None, mid="m") -> PenaltyOutcome:
    return PenaltyOutcome(mutation_id=mid, accepted=accepted, risk_score=risk,
                          complexity_score=complexity, actually_risky=actually_risky,
                          actually_complex=actually_complex)

@pytest.fixture
def pa(tmp_path):
    return PenaltyAdaptor(state_path=tmp_path / "penalty.json")


class TestActivationGate:
    def test_inactive_below_threshold(self, pa):
        w = _w(); result = pa.adapt(w, [_o()], epoch_count=MIN_EPOCHS_FOR_PENALTY - 1)
        assert result.risk_penalty == pytest.approx(w.risk_penalty)

    def test_active_at_threshold(self, pa):
        result = pa.adapt(_w(), [_o()], epoch_count=MIN_EPOCHS_FOR_PENALTY)
        assert isinstance(result.risk_penalty, float)

    def test_empty_outcomes_noop(self, pa):
        w = _w(); result = pa.adapt(w, [], epoch_count=10)
        assert result.risk_penalty == pytest.approx(w.risk_penalty)
        assert result.complexity_penalty == pytest.approx(w.complexity_penalty)


class TestSignalDerivation:
    def test_high_risk_pushes_penalty_up(self, pa):
        outcomes = [_o(accepted=True, risk=0.9, mid=f"m{i}") for i in range(8)]
        w = _w()
        for _ in range(20):
            w = pa.adapt(w, outcomes, epoch_count=10)
        assert w.risk_penalty > ScoringWeights().risk_penalty

    def test_low_risk_pushes_penalty_down(self, pa):
        outcomes = [_o(accepted=True, risk=0.05, mid=f"m{i}") for i in range(8)]
        w = _w()
        for _ in range(20):
            w = pa.adapt(w, outcomes, epoch_count=10)
        assert w.risk_penalty < ScoringWeights().risk_penalty

    def test_high_complexity_pushes_penalty_up(self, pa):
        outcomes = [_o(accepted=True, complexity=0.9, mid=f"m{i}") for i in range(8)]
        w = _w()
        for _ in range(20):
            w = pa.adapt(w, outcomes, epoch_count=10)
        assert w.complexity_penalty > ScoringWeights().complexity_penalty

    def test_actually_risky_overrides_heuristic(self, pa):
        outcomes = [_o(risk=0.1, actually_risky=True, mid=f"m{i}") for i in range(8)]
        w = _w()
        for _ in range(20):
            w = pa.adapt(w, outcomes, epoch_count=10)
        assert w.risk_penalty > ScoringWeights().risk_penalty


class TestBounds:
    def test_risk_penalty_never_exceeds_max(self, pa):
        outcomes = [_o(accepted=True, risk=1.0, mid=f"m{i}") for i in range(5)]
        w = _w()
        for _ in range(100):
            w = pa.adapt(w, outcomes, epoch_count=10)
        assert w.risk_penalty <= 0.70

    def test_complexity_penalty_never_below_min(self, pa):
        outcomes = [_o(accepted=True, complexity=0.0, mid=f"m{i}") for i in range(5)]
        w = _w()
        for _ in range(100):
            w = pa.adapt(w, outcomes, epoch_count=10)
        assert w.complexity_penalty >= 0.05

    def test_other_weights_unchanged(self, pa):
        defaults = ScoringWeights()
        w = pa.adapt(_w(), [_o(risk=0.9)], epoch_count=10)
        assert w.gain_weight == pytest.approx(defaults.gain_weight)
        assert w.coverage_weight == pytest.approx(defaults.coverage_weight)
        assert w.acceptance_threshold == pytest.approx(defaults.acceptance_threshold)


class TestPersistence:
    def test_persists_across_instances(self, tmp_path):
        path = tmp_path / "p.json"
        a1 = PenaltyAdaptor(state_path=path)
        a1.adapt(_w(), [_o(risk=0.9, mid=f"m{i}") for i in range(5)], epoch_count=10)
        a2 = PenaltyAdaptor(state_path=path)
        assert a2.epoch_count == 1

    def test_corrupt_starts_fresh(self, tmp_path):
        p = tmp_path / "bad.json"; p.write_text("not{json")
        a = PenaltyAdaptor(state_path=p)
        assert a.epoch_count == 0


class TestSummary:
    def test_summary_has_required_keys(self, pa):
        s = pa.summary()
        for k in ("algorithm","epoch_count","ema_risk_rate","ema_complexity_rate",
                  "velocity_risk","velocity_complexity","min_epochs_for_activation"):
            assert k in s
    def test_algorithm_name(self, pa):
        assert pa.summary()["algorithm"] == "momentum_penalty_descent"


class TestClamp:
    def test_clamp_lower(self):  assert _clamp(-1.0) == pytest.approx(0.05)
    def test_clamp_upper(self):  assert _clamp(2.0) == pytest.approx(0.70)
    def test_passthrough(self):  assert _clamp(0.30) == pytest.approx(0.30)


class TestWeightAdaptorIntegration:
    def test_penalty_adaptor_called_after_epoch_5(self, tmp_path):
        from runtime.autonomy.weight_adaptor import WeightAdaptor, MutationOutcome
        wa = WeightAdaptor(state_path=tmp_path / "wa.json")
        wa._penalty_adaptor = PenaltyAdaptor(state_path=tmp_path / "pa.json")
        for _ in range(10):
            outcomes = [MutationOutcome(mutation_id=f"m{i}", accepted=True,
                        improved=True, predicted_accept=True) for i in range(5)]
            wa.adapt(outcomes)
        assert wa._penalty_adaptor.epoch_count >= 1
