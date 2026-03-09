# SPDX-License-Identifier: Apache-2.0
"""Phase 19 — AutonomyLoopResult intelligence fields + lineage_health wire tests
(12 tests, T19-01-01..12)."""

import pytest

from runtime.autonomy.loop import AutonomyLoopResult, run_self_check_loop
from runtime.intelligence.strategy import STRATEGY_TAXONOMY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(**overrides):
    defaults = dict(
        cycle_id="c-19",
        actions=[],
        post_condition_checks={},
        mutation_score=0.65,
        governance_debt_score=0.20,
        lineage_health=0.70,
        duration_ms=10,
    )
    defaults.update(overrides)
    return run_self_check_loop(**defaults)


# ---------------------------------------------------------------------------
# T19-01-01  AutonomyLoopResult carries intelligence_strategy_id
# ---------------------------------------------------------------------------
def test_result_carries_intelligence_strategy_id() -> None:
    result = _run()
    assert result.intelligence_strategy_id is not None
    assert result.intelligence_strategy_id in STRATEGY_TAXONOMY


# ---------------------------------------------------------------------------
# T19-01-02  intelligence_strategy_id is a valid taxonomy member
# ---------------------------------------------------------------------------
def test_intelligence_strategy_id_in_taxonomy() -> None:
    result = _run(mutation_score=0.80, governance_debt_score=0.15)
    assert result.intelligence_strategy_id in STRATEGY_TAXONOMY


# ---------------------------------------------------------------------------
# T19-01-03  AutonomyLoopResult carries intelligence_outcome
# ---------------------------------------------------------------------------
def test_result_carries_intelligence_outcome() -> None:
    result = _run()
    assert result.intelligence_outcome in ("execute", "hold")


# ---------------------------------------------------------------------------
# T19-01-04  AutonomyLoopResult carries intelligence_composite (float, [0,1])
# ---------------------------------------------------------------------------
def test_result_carries_intelligence_composite() -> None:
    result = _run()
    assert result.intelligence_composite is not None
    assert 0.0 <= result.intelligence_composite <= 1.0


# ---------------------------------------------------------------------------
# T19-01-05  All three intelligence fields present in single call
# ---------------------------------------------------------------------------
def test_all_three_intelligence_fields_present() -> None:
    result = _run()
    assert result.intelligence_strategy_id is not None
    assert result.intelligence_outcome is not None
    assert result.intelligence_composite is not None


# ---------------------------------------------------------------------------
# T19-01-06  lineage_health=None defaults to 1.0 (backward compatible)
# ---------------------------------------------------------------------------
def test_lineage_health_none_is_backward_compatible() -> None:
    # Should not raise; lineage_health defaults to None → 1.0 inside loop
    result = run_self_check_loop(
        cycle_id="c-compat",
        actions=[],
        post_condition_checks={},
        mutation_score=0.65,
        governance_debt_score=0.20,
        duration_ms=10,
    )
    assert result.intelligence_strategy_id in STRATEGY_TAXONOMY


# ---------------------------------------------------------------------------
# T19-01-07  High governance_debt triggers safety_hardening strategy
# ---------------------------------------------------------------------------
def test_high_debt_triggers_safety_hardening() -> None:
    result = _run(governance_debt_score=0.75, mutation_score=0.40, lineage_health=0.80)
    assert result.intelligence_strategy_id == "safety_hardening"


# ---------------------------------------------------------------------------
# T19-01-08  Low lineage_health can trigger structural_refactor
# ---------------------------------------------------------------------------
def test_low_lineage_health_can_trigger_structural_refactor() -> None:
    # structural_refactor trigger: lineage_health < 0.50, debt < 0.70
    result = _run(lineage_health=0.30, governance_debt_score=0.20, mutation_score=0.30)
    assert result.intelligence_strategy_id == "structural_refactor"


# ---------------------------------------------------------------------------
# T19-01-09  Intelligence fields do not affect existing ok/decision fields
# ---------------------------------------------------------------------------
def test_intelligence_fields_do_not_affect_existing_fields() -> None:
    result = _run(mutation_score=0.50, governance_debt_score=0.10)
    assert isinstance(result.ok, bool)
    assert isinstance(result.decision, str)
    assert result.decision in ("self_mutate", "hold", "escalate")


# ---------------------------------------------------------------------------
# T19-01-10  intelligence_composite matches critique.weighted_aggregate type
# ---------------------------------------------------------------------------
def test_intelligence_composite_is_float() -> None:
    result = _run()
    assert isinstance(result.intelligence_composite, float)


# ---------------------------------------------------------------------------
# T19-01-11  AutonomyLoopResult is still frozen (immutable)
# ---------------------------------------------------------------------------
def test_autonomy_loop_result_is_frozen() -> None:
    result = _run()
    with pytest.raises((AttributeError, TypeError)):
        result.intelligence_strategy_id = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# T19-01-12  Default intelligence fields are None on manually constructed result
# ---------------------------------------------------------------------------
def test_default_intelligence_fields_are_none() -> None:
    result = AutonomyLoopResult(
        ok=True,
        post_conditions_passed=True,
        total_duration_ms=1,
        mutation_score=0.5,
        decision="hold",
    )
    assert result.intelligence_strategy_id is None
    assert result.intelligence_outcome is None
    assert result.intelligence_composite is None
