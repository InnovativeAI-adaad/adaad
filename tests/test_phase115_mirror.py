# SPDX-License-Identifier: Apache-2.0
"""T115-MIRROR-01..30 — Phase 115 acceptance tests for INNOV-30 The Mirror Test."""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from runtime.innovations30.mirror_test import (
    MirrorTestEngine, MirrorTestResult, MirrorPrediction, mirror_guard,
    MIRROR_INVARIANTS, MIRROR_TEST_INTERVAL, CALIBRATION_THRESHOLD, MIRROR_TEST_SAMPLE,
)

def make_eng(tmp=None, **kw):
    td = tmp or Path(tempfile.mkdtemp())
    return MirrorTestEngine(state_path=td/"state.jsonl", **kw)

def perfect_predictor(record):
    return MirrorPrediction(
        mutation_id=record["id"],
        predicted_pass=record["actual_pass"],
        predicted_rules_fired=record["actual_rules"],
        predicted_fitness=record["actual_fitness"],
        actual_pass=record["actual_pass"],
        actual_rules_fired=record["actual_rules"],
        actual_fitness=record["actual_fitness"],
    )

def bad_predictor(record):
    return MirrorPrediction(
        mutation_id=record["id"],
        predicted_pass=not record["actual_pass"],
        predicted_rules_fired=[],
        predicted_fitness=1.0 - record["actual_fitness"],
        actual_pass=record["actual_pass"],
        actual_rules_fired=record["actual_rules"],
        actual_fitness=record["actual_fitness"],
    )

RECORDS = [
    {"id": f"M-{i}", "actual_pass": i % 2 == 0,
     "actual_rules": ["RULE-A"], "actual_fitness": round(0.5 + i*0.01, 2)}
    for i in range(5)
]

# T115-MIRROR-01: module imports
def test_T115_01_import():
    assert MirrorTestEngine is not None

# T115-MIRROR-02: MIRROR_INVARIANTS has three entries
def test_T115_02_invariant_registry():
    assert set(MIRROR_INVARIANTS.keys()) == {
        "MIRROR-0", "MIRROR-DETERM-0", "MIRROR-AUDIT-0"
    }

# T115-MIRROR-03: constants correct
def test_T115_03_constants():
    assert MIRROR_TEST_INTERVAL == 50
    assert CALIBRATION_THRESHOLD == 0.60
    assert MIRROR_TEST_SAMPLE == 20

# T115-MIRROR-04: should_run True at interval
def test_T115_04_should_run_at_interval():
    eng = make_eng()
    assert eng.should_run(50) is True

# T115-MIRROR-05: should_run False at non-interval
def test_T115_05_should_run_off_interval():
    eng = make_eng()
    assert eng.should_run(51) is False

# T115-MIRROR-06: should_run False at epoch 0
def test_T115_06_should_run_not_zero():
    eng = make_eng()
    assert eng.should_run(0) is False

# T115-MIRROR-07: run returns MirrorTestResult
def test_T115_07_run_returns_result():
    eng = make_eng()
    r = eng.run("e-50", RECORDS, perfect_predictor)
    assert isinstance(r, MirrorTestResult)

# T115-MIRROR-08: MIRROR-0 — overall_score in [0.0, 1.0]
def test_T115_08_score_in_bounds():
    eng = make_eng()
    r = eng.run("e-50", RECORDS, perfect_predictor)
    assert 0.0 <= r.overall_score <= 1.0

# T115-MIRROR-09: MIRROR-0 — perfect predictor scores high
def test_T115_09_perfect_predictor_high_score():
    eng = make_eng()
    r = eng.run("e-50", RECORDS, perfect_predictor)
    assert r.overall_score >= 0.60

# T115-MIRROR-10: MIRROR-0 — bad predictor triggers calibration
def test_T115_10_bad_predictor_calibration():
    eng = make_eng()
    r = eng.run("e-50", RECORDS, bad_predictor)
    assert r.requires_calibration is True

# T115-MIRROR-11: MIRROR-0 — requires_calibration consistent with score
def test_T115_11_requires_calibration_consistent():
    eng = make_eng()
    r = eng.run("e-50", RECORDS, bad_predictor)
    assert r.requires_calibration == (r.overall_score < CALIBRATION_THRESHOLD)

# T115-MIRROR-12: MIRROR-AUDIT-0 — result_digest non-empty
def test_T115_12_digest_nonempty():
    eng = make_eng()
    r = eng.run("e-50", RECORDS, perfect_predictor)
    assert r.result_digest.startswith("sha256:")

# T115-MIRROR-13: MIRROR-DETERM-0 — identical inputs produce identical digest
def test_T115_13_determinism():
    td = Path(tempfile.mkdtemp())
    r1 = make_eng(td).run("e-50", RECORDS, perfect_predictor)
    r2 = make_eng(td).run("e-50", RECORDS, perfect_predictor)
    assert r1.result_digest == r2.result_digest

# T115-MIRROR-14: different epoch_id → different digest
def test_T115_14_different_epoch_different_digest():
    td = Path(tempfile.mkdtemp())
    r1 = make_eng(td).run("e-50", RECORDS, perfect_predictor)
    r2 = make_eng(td).run("e-100", RECORDS, perfect_predictor)
    assert r1.result_digest != r2.result_digest

# T115-MIRROR-15: invariants_verified lists all three
def test_T115_15_invariants_listed():
    eng = make_eng()
    r = eng.run("e-50", RECORDS, perfect_predictor)
    assert set(r.invariants_verified) == {"MIRROR-0", "MIRROR-DETERM-0", "MIRROR-AUDIT-0"}

# T115-MIRROR-16: to_ledger_row valid JSON
def test_T115_16_ledger_row_json():
    eng = make_eng()
    r = eng.run("e-50", RECORDS, perfect_predictor)
    parsed = json.loads(r.to_ledger_row())
    assert parsed["epoch_id"] == "e-50"

# T115-MIRROR-17: to_ledger_row single-line
def test_T115_17_ledger_row_single_line():
    eng = make_eng()
    r = eng.run("e-50", RECORDS, perfect_predictor)
    assert "\n" not in r.to_ledger_row()

# T115-MIRROR-18: MIRROR-AUDIT-0 — state file written
def test_T115_18_state_file_written():
    td = Path(tempfile.mkdtemp())
    eng = make_eng(td)
    eng.run("e-50", RECORDS, perfect_predictor)
    assert (td / "state.jsonl").exists()

# T115-MIRROR-19: last_score returns None before any run
def test_T115_19_last_score_none():
    eng = make_eng()
    assert eng.last_score() is None

# T115-MIRROR-20: last_score returns correct value after run
def test_T115_20_last_score_after_run():
    td = Path(tempfile.mkdtemp())
    eng = make_eng(td)
    r = eng.run("e-50", RECORDS, perfect_predictor)
    assert eng.last_score() == r.overall_score

# T115-MIRROR-21: mirror_guard passes on valid high-score result
def test_T115_21_guard_pass():
    eng = make_eng()
    r = eng.run("e-50", RECORDS, perfect_predictor)
    mirror_guard(r)  # must not raise

# T115-MIRROR-22: mirror_guard rejects score > 1.0
def test_T115_22_guard_score_over():
    r = MirrorTestResult(epoch_id="e", sample_size=1,
        pass_accuracy=1.0, rules_precision=1.0, fitness_mae=0.0,
        overall_score=1.5, requires_calibration=False)
    with pytest.raises(RuntimeError, match="MIRROR-0"):
        mirror_guard(r)

# T115-MIRROR-23: mirror_guard rejects inconsistent calibration flag
def test_T115_23_guard_inconsistent_calibration():
    r = MirrorTestResult(epoch_id="e", sample_size=1,
        pass_accuracy=0.0, rules_precision=0.0, fitness_mae=1.0,
        overall_score=0.1, requires_calibration=False)  # should be True
    with pytest.raises(RuntimeError, match="MIRROR-0"):
        mirror_guard(r)

# T115-MIRROR-24: mirror_guard rejects empty digest
def test_T115_24_guard_empty_digest():
    r = MirrorTestResult(epoch_id="e", sample_size=1,
        pass_accuracy=1.0, rules_precision=1.0, fitness_mae=0.0,
        overall_score=0.9, requires_calibration=False)
    r.result_digest = ""
    with pytest.raises(RuntimeError, match="MIRROR-AUDIT-0"):
        mirror_guard(r)

# T115-MIRROR-25: MirrorPrediction.pass_correct True when matching
def test_T115_25_prediction_pass_correct():
    p = MirrorPrediction(mutation_id="M", predicted_pass=True, actual_pass=True)
    assert p.pass_correct is True

# T115-MIRROR-26: MirrorPrediction.rules_precision correct
def test_T115_26_prediction_rules_precision():
    p = MirrorPrediction(
        mutation_id="M", predicted_pass=True,
        predicted_rules_fired=["A", "B"], actual_rules_fired=["A", "C"],
        actual_pass=True,
    )
    # intersection {"A"} / union {"A","B","C"} = 1/3... wait max(2,2)=2 so 1/2
    assert p.rules_precision == pytest.approx(0.5, abs=1e-4)

# T115-MIRROR-27: MirrorPrediction.fitness_error correct
def test_T115_27_prediction_fitness_error():
    p = MirrorPrediction(mutation_id="M", predicted_pass=True,
        predicted_fitness=0.8, actual_fitness=0.6, actual_pass=True)
    assert p.fitness_error == pytest.approx(0.2, abs=1e-4)

# T115-MIRROR-28: empty records run produces score 0.0
def test_T115_28_empty_records():
    eng = make_eng()
    r = eng.run("e-50", [], perfect_predictor)
    assert r.sample_size == 0
    assert r.overall_score == 0.0

# T115-MIRROR-29: multiple runs accumulate in JSONL
def test_T115_29_multiple_runs_accumulate():
    td = Path(tempfile.mkdtemp())
    eng = make_eng(td)
    eng.run("e-50", RECORDS, perfect_predictor)
    eng.run("e-100", RECORDS, perfect_predictor)
    rows = [l for l in (td/"state.jsonl").read_text().splitlines() if l]
    assert len(rows) == 2

# T115-MIRROR-30: full integration — run, guard, persist, last_score
def test_T115_30_integration():
    td = Path(tempfile.mkdtemp())
    eng = make_eng(td)
    assert eng.should_run(50)
    r = eng.run("e-50", RECORDS, perfect_predictor)
    mirror_guard(r)
    assert eng.last_score() == r.overall_score
    assert r.requires_calibration == (r.overall_score < CALIBRATION_THRESHOLD)
    rows = [l for l in (td/"state.jsonl").read_text().splitlines() if l]
    assert len(rows) == 1
