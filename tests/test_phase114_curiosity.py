# SPDX-License-Identifier: Apache-2.0
"""T114-CURIOSITY-01..30 — Phase 114 acceptance tests for INNOV-29 Curiosity Engine."""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from runtime.innovations30.curiosity_engine import (
    CuriosityEngine, CuriosityState, CuriosityEvent, curiosity_guard,
    CURIOSITY_INVARIANTS, CURIOSITY_INTERVAL, CURIOSITY_DURATION,
    HARD_STOP_HEALTH, HARD_STOP_PATTERNS,
)

def make_eng(**kw):
    td = Path(tempfile.mkdtemp())
    return CuriosityEngine(state_path=td/"state.json", **kw)

# T114-CURIOSITY-01: module imports
def test_T114_01_import():
    assert CuriosityEngine is not None

# T114-CURIOSITY-02: CURIOSITY_INVARIANTS has three entries
def test_T114_02_invariant_registry():
    assert set(CURIOSITY_INVARIANTS.keys()) == {
        "CURIOSITY-0", "CURIOSITY-STOP-0", "CURIOSITY-AUDIT-0"
    }

# T114-CURIOSITY-03: constants correct
def test_T114_03_constants():
    assert CURIOSITY_INTERVAL == 25
    assert CURIOSITY_DURATION == 3
    assert HARD_STOP_HEALTH == 0.50

# T114-CURIOSITY-04: not active by default
def test_T114_04_not_active_default():
    eng = make_eng()
    assert eng.in_curiosity is False

# T114-CURIOSITY-05: should_enter at interval epoch
def test_T114_05_should_enter_at_interval():
    eng = make_eng()
    assert eng.should_enter_curiosity(25) is True

# T114-CURIOSITY-06: should_enter False at non-interval epoch
def test_T114_06_should_not_enter_off_interval():
    eng = make_eng()
    assert eng.should_enter_curiosity(26) is False

# T114-CURIOSITY-07: should_enter False at epoch 0
def test_T114_07_no_enter_at_zero():
    eng = make_eng()
    assert eng.should_enter_curiosity(0) is False

# T114-CURIOSITY-08: enter_curiosity sets active
def test_T114_08_enter_sets_active():
    eng = make_eng()
    eng.enter_curiosity("e-25")
    assert eng.in_curiosity is True

# T114-CURIOSITY-09: enter_curiosity sets epochs_remaining to DURATION
def test_T114_09_enter_sets_remaining():
    eng = make_eng()
    s = eng.enter_curiosity("e-25")
    assert s.epochs_remaining == CURIOSITY_DURATION

# T114-CURIOSITY-10: CURIOSITY-AUDIT-0 — enter appends to discoveries
def test_T114_10_enter_audit_discovery():
    eng = make_eng()
    eng.enter_curiosity("e-25")
    assert any("enter" in d for d in eng._state.discoveries)

# T114-CURIOSITY-11: tick returns True while epochs remain
def test_T114_11_tick_true_while_remaining():
    eng = make_eng(duration=3)
    eng.enter_curiosity("e-25")
    still, _ = eng.tick("e-26", 0.9, [])
    assert still is True

# T114-CURIOSITY-12: tick returns False after all epochs consumed
def test_T114_12_tick_false_after_duration():
    eng = make_eng(duration=1)
    eng.enter_curiosity("e-25")
    still, reason = eng.tick("e-26", 0.9, [])
    assert still is False
    assert "complete" in reason

# T114-CURIOSITY-13: CURIOSITY-STOP-0 — health stop exits immediately
def test_T114_13_hard_stop_health():
    eng = make_eng()
    eng.enter_curiosity("e-25")
    still, reason = eng.tick("e-26", 0.3, [])  # below 0.50
    assert still is False
    assert "health" in reason.lower()

# T114-CURIOSITY-14: hard stop deactivates engine
def test_T114_14_health_stop_deactivates():
    eng = make_eng()
    eng.enter_curiosity("e-25")
    eng.tick("e-26", 0.2, [])
    assert eng.in_curiosity is False

# T114-CURIOSITY-15: CURIOSITY-STOP-0 — protected file hard stop
def test_T114_15_hard_stop_protected_file():
    eng = make_eng()
    eng.enter_curiosity("e-25")
    still, reason = eng.tick("e-26", 0.9, ["runtime/governance/gate.py"])
    assert still is False
    assert "protected" in reason.lower()

# T114-CURIOSITY-16: HARD_STOP_PATTERNS contains required files
def test_T114_16_hard_stop_patterns():
    assert "runtime/constitution.py" in HARD_STOP_PATTERNS
    assert "security/ledger/journal.py" in HARD_STOP_PATTERNS

# T114-CURIOSITY-17: CURIOSITY-AUDIT-0 — hard stop appends to discoveries
def test_T114_17_hard_stop_audit():
    eng = make_eng()
    eng.enter_curiosity("e-25")
    eng.tick("e-26", 0.1, [])
    assert any("hard_stop" in d for d in eng._state.discoveries)

# T114-CURIOSITY-18: tick when not active returns False immediately
def test_T114_18_tick_not_active():
    eng = make_eng()
    still, reason = eng.tick("e-1", 0.9, [])
    assert still is False
    assert reason == ""

# T114-CURIOSITY-19: CURIOSITY-0 — invert_fitness active
def test_T114_19_invert_fitness_active():
    eng = make_eng()
    eng.enter_curiosity("e-25")
    assert eng.invert_fitness(0.8) == pytest.approx(0.2, abs=1e-4)

# T114-CURIOSITY-20: CURIOSITY-0 — invert_fitness passthrough when inactive
def test_T114_20_invert_fitness_inactive():
    eng = make_eng()
    assert eng.invert_fitness(0.7) == 0.7

# T114-CURIOSITY-21: CURIOSITY-0 — invert_fitness rejects out-of-bounds
def test_T114_21_invert_fitness_rejects_invalid():
    eng = make_eng()
    with pytest.raises(RuntimeError, match="CURIOSITY-0"):
        eng.invert_fitness(1.5)

# T114-CURIOSITY-22: invert_fitness rejects negative
def test_T114_22_invert_fitness_rejects_negative():
    eng = make_eng()
    with pytest.raises(RuntimeError, match="CURIOSITY-0"):
        eng.invert_fitness(-0.1)

# T114-CURIOSITY-23: curiosity_guard passes on valid state
def test_T114_23_guard_pass():
    s = CuriosityState(active=False, epochs_remaining=0)
    curiosity_guard(s)  # must not raise

# T114-CURIOSITY-24: curiosity_guard rejects active with zero remaining
def test_T114_24_guard_active_zero_remaining():
    s = CuriosityState(active=True, epochs_remaining=0)
    with pytest.raises(RuntimeError, match="CURIOSITY-0"):
        curiosity_guard(s)

# T114-CURIOSITY-25: curiosity_guard rejects negative remaining
def test_T114_25_guard_negative_remaining():
    s = CuriosityState(active=False, epochs_remaining=-1)
    with pytest.raises(RuntimeError, match="CURIOSITY-0"):
        curiosity_guard(s)

# T114-CURIOSITY-26: curiosity_guard rejects out-of-bounds fitness
def test_T114_26_guard_bad_fitness():
    s = CuriosityState()
    with pytest.raises(RuntimeError, match="CURIOSITY-0"):
        curiosity_guard(s, base_fitness=2.0)

# T114-CURIOSITY-27: state persists across reload
def test_T114_27_state_persistence():
    td = Path(tempfile.mkdtemp())
    eng1 = CuriosityEngine(state_path=td/"state.json")
    eng1.enter_curiosity("e-25")
    eng2 = CuriosityEngine(state_path=td/"state.json")
    assert eng2.in_curiosity is True
    assert eng2._state.cycle_number == 1

# T114-CURIOSITY-28: CuriosityEvent to_ledger_row valid JSON
def test_T114_28_event_ledger_row():
    ev = CuriosityEvent(
        event_type="enter", epoch_id="e-25", cycle_number=1,
        epochs_remaining=3, health_score=0.9, reason="test"
    )
    row = ev.to_ledger_row()
    parsed = json.loads(row)
    assert parsed["innovation"] == "INNOV-29"
    assert "\n" not in row

# T114-CURIOSITY-29: state_summary returns all CuriosityState fields
def test_T114_29_state_summary():
    eng = make_eng()
    s = eng.state_summary()
    assert "active" in s and "epochs_remaining" in s and "discoveries" in s

# T114-CURIOSITY-30: full integration — enter, ticks, exit by duration
def test_T114_30_integration():
    eng = make_eng(interval=10, duration=2)
    assert eng.should_enter_curiosity(10)
    eng.enter_curiosity("e-10")
    assert eng.in_curiosity

    # tick 1: still active
    still, _ = eng.tick("e-11", 0.9, [])
    assert still is True

    # tick 2: exits (duration=2, first tick consumed remaining to 1, second to 0)
    still, reason = eng.tick("e-12", 0.9, [])
    assert still is False
    assert not eng.in_curiosity
    assert any("exit" in d for d in eng._state.discoveries)
