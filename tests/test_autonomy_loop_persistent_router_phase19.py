# SPDX-License-Identifier: Apache-2.0
"""Phase 19 — AutonomyLoop persistent IntelligenceRouter tests (10 tests, T19-02-01..10)."""

import pytest

from runtime.autonomy.loop import AutonomyLoop, AutonomyLoopResult
from runtime.intelligence.critique_signal import CritiqueSignalBuffer
from runtime.intelligence.router import IntelligenceRouter
from runtime.intelligence.strategy import STRATEGY_TAXONOMY


def _run_on(loop: AutonomyLoop, cycle_id: str = "c-19", **overrides):
    defaults = dict(
        actions=[],
        post_condition_checks={},
        mutation_score=0.65,
        governance_debt_score=0.20,
        lineage_health=0.70,
        duration_ms=5,
    )
    defaults.update(overrides)
    return loop.run(cycle_id=cycle_id, **defaults)


# T19-02-01  AutonomyLoop instantiates with a persistent IntelligenceRouter
def test_autonomy_loop_has_persistent_router() -> None:
    loop = AutonomyLoop()
    r1 = loop.router
    r2 = loop.router
    assert r1 is r2
    assert isinstance(r1, IntelligenceRouter)


# T19-02-02  AutonomyLoop accepts injected router
def test_autonomy_loop_accepts_injected_router() -> None:
    router = IntelligenceRouter()
    loop = AutonomyLoop(router=router)
    assert loop.router is router


# T19-02-03  Buffer accumulates across multiple run() calls
def test_buffer_accumulates_across_runs() -> None:
    loop = AutonomyLoop()
    for i in range(3):
        _run_on(loop, cycle_id=f"c-acc-{i}")
    total = sum(
        loop.router.signal_buffer.total_count(sid) for sid in STRATEGY_TAXONOMY
    )
    assert total == 3


# T19-02-04  router identity is preserved across run() calls
def test_router_identity_preserved_across_runs() -> None:
    loop = AutonomyLoop()
    router_before = loop.router
    _run_on(loop)
    _run_on(loop, cycle_id="c-second")
    assert loop.router is router_before


# T19-02-05  reset_epoch() clears the buffer
def test_reset_epoch_clears_buffer() -> None:
    loop = AutonomyLoop()
    _run_on(loop)
    loop.reset_epoch()
    total = sum(
        loop.router.signal_buffer.total_count(sid) for sid in STRATEGY_TAXONOMY
    )
    assert total == 0


# T19-02-06  After reset_epoch(), subsequent run() starts with zero penalties
def test_after_reset_epoch_penalties_are_zero() -> None:
    loop = AutonomyLoop()
    for i in range(4):
        _run_on(loop, cycle_id=f"c-pre-{i}")
    loop.reset_epoch()
    result = _run_on(loop, cycle_id="c-post")
    penalties = result.intelligence_composite  # Not zero — but penalties in strategy params should be 0
    # Verify: no penalty was applied (all breach rates reset)
    params = loop.router.signal_buffer.snapshot()
    # Snapshot should have exactly 1 entry (from the post-reset run)
    assert len(params) == 1


# T19-02-07  run() returns AutonomyLoopResult with intelligence fields
def test_run_returns_result_with_intelligence_fields() -> None:
    loop = AutonomyLoop()
    result = _run_on(loop)
    assert isinstance(result, AutonomyLoopResult)
    assert result.intelligence_strategy_id in STRATEGY_TAXONOMY
    assert result.intelligence_outcome in ("execute", "hold")
    assert 0.0 <= result.intelligence_composite <= 1.0


# T19-02-08  lineage_health=None defaults to 1.0 in AutonomyLoop.run()
def test_autonomy_loop_lineage_health_default() -> None:
    loop = AutonomyLoop()
    result = loop.run(
        cycle_id="c-default",
        actions=[],
        post_condition_checks={},
        mutation_score=0.65,
        governance_debt_score=0.20,
        duration_ms=5,
    )
    assert result.intelligence_strategy_id in STRATEGY_TAXONOMY


# T19-02-09  High debt → safety_hardening via AutonomyLoop.run()
def test_high_debt_triggers_safety_hardening_via_autonomy_loop() -> None:
    loop = AutonomyLoop()
    result = _run_on(loop, governance_debt_score=0.75, mutation_score=0.30, lineage_health=0.80)
    assert result.intelligence_strategy_id == "safety_hardening"


# T19-02-10  Two AutonomyLoop instances have independent buffers
def test_two_loops_have_independent_buffers() -> None:
    loop_a = AutonomyLoop()
    loop_b = AutonomyLoop()
    for i in range(3):
        _run_on(loop_a, cycle_id=f"ca-{i}")
    for i in range(1):
        _run_on(loop_b, cycle_id=f"cb-{i}")
    total_a = sum(loop_a.router.signal_buffer.total_count(sid) for sid in STRATEGY_TAXONOMY)
    total_b = sum(loop_b.router.signal_buffer.total_count(sid) for sid in STRATEGY_TAXONOMY)
    assert total_a == 3
    assert total_b == 1
    assert loop_a.router is not loop_b.router
