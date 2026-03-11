import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0
"""Phase 20 — runtime.autonomy public API contract tests (8 tests, T20-02-01..08).

Imports exclusively via `from runtime.autonomy import X` — the public surface.
"""

# ---------------------------------------------------------------------------
# T20-02-01  AutonomyLoop importable from runtime.autonomy
# ---------------------------------------------------------------------------
def test_autonomy_loop_importable() -> None:
    from runtime.autonomy import AutonomyLoop
    loop = AutonomyLoop()
    assert loop is not None


# ---------------------------------------------------------------------------
# T20-02-02  AutonomyLoop in runtime.autonomy.__all__
# ---------------------------------------------------------------------------
def test_autonomy_loop_in_all() -> None:
    import runtime.autonomy as ra
    assert "AutonomyLoop" in ra.__all__


# ---------------------------------------------------------------------------
# T20-02-03  AutonomyLoop from public import is same class as direct import
# ---------------------------------------------------------------------------
def test_autonomy_loop_identity() -> None:
    from runtime.autonomy import AutonomyLoop as PubAL
    from runtime.autonomy.loop import AutonomyLoop as DirectAL
    assert PubAL is DirectAL


# ---------------------------------------------------------------------------
# T20-02-04  AutonomyLoop.run() returns AutonomyLoopResult from public import
# ---------------------------------------------------------------------------
def test_autonomy_loop_run_returns_loop_result() -> None:
    from runtime.autonomy import AutonomyLoop, AutonomyLoopResult
    loop = AutonomyLoop()
    result = loop.run(
        cycle_id="c-api",
        actions=[],
        post_condition_checks={},
        mutation_score=0.60,
        governance_debt_score=0.15,
        duration_ms=5,
    )
    assert isinstance(result, AutonomyLoopResult)


# ---------------------------------------------------------------------------
# T20-02-05  AutonomyLoopResult intelligence fields accessible from public import
# ---------------------------------------------------------------------------
def test_autonomy_loop_result_intelligence_fields() -> None:
    from runtime.autonomy import AutonomyLoop
    from runtime.intelligence import STRATEGY_TAXONOMY
    loop = AutonomyLoop()
    result = loop.run(
        cycle_id="c-fields",
        actions=[],
        post_condition_checks={},
        mutation_score=0.60,
        governance_debt_score=0.15,
        duration_ms=5,
    )
    assert result.intelligence_strategy_id in STRATEGY_TAXONOMY
    assert result.intelligence_outcome in ("execute", "hold")
    assert result.intelligence_composite is not None


# ---------------------------------------------------------------------------
# T20-02-06  Legacy symbols still present in runtime.autonomy.__all__
# ---------------------------------------------------------------------------
def test_legacy_autonomy_symbols_in_all() -> None:
    import runtime.autonomy as ra
    legacy = {
        "AutonomyLoopResult",
        "AutonomyBudgetEngine",
        "run_agm_cycle",
        "run_self_check_loop",
        "AGMStep",
    }
    missing = legacy - set(ra.__all__)
    assert not missing, f"Legacy symbols removed: {missing}"


# ---------------------------------------------------------------------------
# T20-02-07  strategy.py.bak absent from intelligence module directory
# ---------------------------------------------------------------------------
def test_strategy_bak_absent() -> None:
    import os, pathlib
    bak = pathlib.Path("runtime/intelligence/strategy.py.bak")
    assert not bak.exists(), "strategy.py.bak should have been deleted in Phase 20"


# ---------------------------------------------------------------------------
# T20-02-08  AutonomyLoop.reset_epoch() accessible from public import
# ---------------------------------------------------------------------------
def test_autonomy_loop_reset_epoch_accessible() -> None:
    from runtime.autonomy import AutonomyLoop
    loop = AutonomyLoop()
    loop.run(
        cycle_id="c-before",
        actions=[],
        post_condition_checks={},
        mutation_score=0.65,
        duration_ms=5,
    )
    loop.reset_epoch()  # Should not raise
    from runtime.intelligence.strategy import STRATEGY_TAXONOMY
    total = sum(loop.router.signal_buffer.total_count(s) for s in STRATEGY_TAXONOMY)
    assert total == 0
