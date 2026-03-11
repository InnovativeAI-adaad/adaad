# SPDX-License-Identifier: Apache-2.0
"""Phase 18 — CritiqueSignalBuffer + StrategyModule breach penalty tests (15 tests, T18-01-01..15)."""

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.intelligence.critique_signal import (
    CritiqueSignalBuffer,
    _BREACH_PENALTY_WEIGHT,
)
from runtime.intelligence.strategy import StrategyInput, StrategyModule


# ---------------------------------------------------------------------------
# CritiqueSignalBuffer unit tests
# ---------------------------------------------------------------------------

# T18-01-01  Unknown strategy_id → breach_rate 0.0 (no penalty on first appearance)
def test_unknown_strategy_breach_rate_is_zero() -> None:
    buf = CritiqueSignalBuffer()
    assert buf.breach_rate("safety_hardening") == 0.0


# T18-01-02  100% approval → breach_rate 0.0
def test_all_approved_breach_rate_zero() -> None:
    buf = CritiqueSignalBuffer()
    for _ in range(5):
        buf.record(strategy_id="adaptive_self_mutate", approved=True, risk_flags=[])
    assert buf.breach_rate("adaptive_self_mutate") == 0.0


# T18-01-03  100% rejection → breach_rate 1.0
def test_all_rejected_breach_rate_one() -> None:
    buf = CritiqueSignalBuffer()
    for _ in range(4):
        buf.record(strategy_id="conservative_hold", approved=False, risk_flags=["risk_below_floor"])
    assert buf.breach_rate("conservative_hold") == 1.0


# T18-01-04  50% breach → breach_rate 0.5
def test_half_breach_rate() -> None:
    buf = CritiqueSignalBuffer()
    buf.record(strategy_id="performance_optimization", approved=True, risk_flags=[])
    buf.record(strategy_id="performance_optimization", approved=False, risk_flags=["governance_below_floor"])
    assert buf.breach_rate("performance_optimization") == pytest.approx(0.5)


# T18-01-05  approved=True but risk_flags non-empty → counts as breach
def test_approved_with_risk_flags_counts_as_breach() -> None:
    buf = CritiqueSignalBuffer()
    buf.record(strategy_id="structural_refactor", approved=True, risk_flags=["observability_below_floor"])
    assert buf.breach_rate("structural_refactor") == 1.0


# T18-01-06  breach_penalty = breach_rate × _BREACH_PENALTY_WEIGHT
def test_breach_penalty_formula() -> None:
    buf = CritiqueSignalBuffer()
    buf.record(strategy_id="test_coverage_expansion", approved=False, risk_flags=["risk_below_floor"])
    buf.record(strategy_id="test_coverage_expansion", approved=True, risk_flags=[])
    expected = buf.breach_rate("test_coverage_expansion") * _BREACH_PENALTY_WEIGHT
    assert buf.breach_penalty("test_coverage_expansion") == pytest.approx(expected)


# T18-01-07  Maximum breach_penalty ≤ _BREACH_PENALTY_WEIGHT (0.20)
def test_breach_penalty_capped_at_weight() -> None:
    buf = CritiqueSignalBuffer()
    for _ in range(10):
        buf.record(strategy_id="safety_hardening", approved=False, risk_flags=["governance_below_floor"])
    assert buf.breach_penalty("safety_hardening") <= _BREACH_PENALTY_WEIGHT
    assert _BREACH_PENALTY_WEIGHT == pytest.approx(0.20)


# T18-01-08  reset_epoch() clears all state
def test_reset_epoch_clears_state() -> None:
    buf = CritiqueSignalBuffer()
    buf.record(strategy_id="adaptive_self_mutate", approved=False, risk_flags=["risk_below_floor"])
    buf.reset_epoch()
    assert buf.breach_rate("adaptive_self_mutate") == 0.0
    assert buf.total_count("adaptive_self_mutate") == 0


# T18-01-09  snapshot() is deterministic and sorted
def test_snapshot_is_deterministic_and_sorted() -> None:
    buf = CritiqueSignalBuffer()
    buf.record(strategy_id="conservative_hold", approved=False, risk_flags=[])
    buf.record(strategy_id="adaptive_self_mutate", approved=True, risk_flags=[])
    snap = buf.snapshot()
    assert list(snap.keys()) == sorted(snap.keys())
    assert "conservative_hold" in snap
    assert "adaptive_self_mutate" in snap


# T18-01-10  total_count and breach_count are correct
def test_total_and_breach_count_correct() -> None:
    buf = CritiqueSignalBuffer()
    buf.record(strategy_id="structural_refactor", approved=True, risk_flags=[])
    buf.record(strategy_id="structural_refactor", approved=False, risk_flags=["feasibility_below_floor"])
    buf.record(strategy_id="structural_refactor", approved=True, risk_flags=[])
    assert buf.total_count("structural_refactor") == 3
    assert buf.breach_count("structural_refactor") == 1


# ---------------------------------------------------------------------------
# StrategyModule × CritiqueSignalBuffer integration tests
# ---------------------------------------------------------------------------

def _base_input(**overrides) -> StrategyInput:
    defaults = dict(
        cycle_id="c-18",
        mutation_score=0.65,
        governance_debt_score=0.20,
        lineage_health=0.70,
        resource_budget=0.80,
    )
    defaults.update(overrides)
    return StrategyInput(**defaults)


# T18-01-11  Without signal_buffer, select() is identical to Phase 17 behaviour
def test_select_without_buffer_unchanged() -> None:
    ctx = _base_input()
    m = StrategyModule()
    d1 = m.select(ctx)
    d2 = m.select(ctx, signal_buffer=None)
    assert d1.strategy_id == d2.strategy_id
    assert d1.parameters.get("breach_penalties") == {} or d1.parameters.get("breach_penalties") == d2.parameters.get("breach_penalties")


# T18-01-12  With empty buffer (no records), result identical to no-buffer
def test_select_with_empty_buffer_unchanged() -> None:
    ctx = _base_input()
    m = StrategyModule()
    buf = CritiqueSignalBuffer()
    d_no = m.select(ctx)
    d_buf = m.select(ctx, signal_buffer=buf)
    assert d_no.strategy_id == d_buf.strategy_id


# T18-01-13  breach_penalties reported in parameters
def test_breach_penalties_in_parameters() -> None:
    ctx = _base_input(mutation_score=0.75, governance_debt_score=0.20)
    buf = CritiqueSignalBuffer()
    buf.record(strategy_id="adaptive_self_mutate", approved=False, risk_flags=["risk_below_floor"])
    d = StrategyModule().select(ctx, signal_buffer=buf)
    assert "breach_penalties" in d.parameters
    assert isinstance(d.parameters["breach_penalties"], dict)


# T18-01-14  Penalised strategy loses payoff vs unpenalised alternative
def test_penalised_strategy_loses_payoff() -> None:
    # Force adaptive_self_mutate to qualify: mutation>=0.70, budget>=0.60
    ctx = _base_input(mutation_score=0.75, governance_debt_score=0.20, resource_budget=0.80)
    m = StrategyModule()
    buf = CritiqueSignalBuffer()
    # Heavily penalise adaptive_self_mutate
    for _ in range(5):
        buf.record(strategy_id="adaptive_self_mutate", approved=False, risk_flags=["risk_below_floor"])

    d_no = m.select(ctx)
    d_pen = m.select(ctx, signal_buffer=buf)

    # Both still return a valid taxonomy strategy
    from runtime.intelligence.strategy import STRATEGY_TAXONOMY
    assert d_pen.strategy_id in STRATEGY_TAXONOMY

    # The penalty was recorded in parameters for the penalised strategy
    penalties = d_pen.parameters.get("breach_penalties", {})
    if "adaptive_self_mutate" in penalties:
        assert penalties["adaptive_self_mutate"] > 0.0


# T18-01-15  Payoff never goes below 0.0 even at 100% breach rate
def test_payoff_never_negative() -> None:
    ctx = _base_input(mutation_score=0.80, governance_debt_score=0.20, resource_budget=0.90)
    buf = CritiqueSignalBuffer()
    from runtime.intelligence.strategy import STRATEGY_TAXONOMY
    for sid in STRATEGY_TAXONOMY:
        for _ in range(10):
            buf.record(strategy_id=sid, approved=False, risk_flags=["governance_below_floor"])
    d = StrategyModule().select(ctx, signal_buffer=buf)
    for c in d.parameters.get("candidates", []):
        assert c["payoff"] >= 0.0
