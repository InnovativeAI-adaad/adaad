# SPDX-License-Identifier: Apache-2.0
"""T113-SELF-AWARE-01..30 — Phase 113 acceptance tests for INNOV-28 Self-Awareness Invariant."""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from runtime.innovations30.self_awareness_invariant import (
    SelfAwarenessInvariant, SelfAwarenessVerdict, self_aware_guard,
    SELF_AWARE_INVARIANTS, PROTECTED_OBSERVABILITY_MODULES, OBSERVABILITY_REDUCTION_PATTERNS,
)

CLEAN_DIFF = "+def foo():\n+    return 42\n"
VIOLATION_DIFF = "-metrics.log(event)\n-journal.append(row)\n"
PROTECTED = "runtime/metrics.py"

def make_inv(**kw):
    return SelfAwarenessInvariant(**kw)

# T113-SELF-AWARE-01: module imports
def test_T113_01_import():
    assert SelfAwarenessInvariant is not None

# T113-SELF-AWARE-02: SELF_AWARE_INVARIANTS has three entries
def test_T113_02_invariant_registry():
    assert set(SELF_AWARE_INVARIANTS.keys()) == {
        "SELF-AWARE-0", "SELF-AWARE-DETERM-0", "SELF-AWARE-AUDIT-0"
    }

# T113-SELF-AWARE-03: clean mutation passes
def test_T113_03_clean_pass():
    inv = make_inv()
    v = inv.evaluate("MUT-001", CLEAN_DIFF, ["unrelated.py"])
    assert v.passed is True
    assert v.violations == []

# T113-SELF-AWARE-04: violation when protected module touched and calls removed
def test_T113_04_violation_on_protected_removal():
    inv = make_inv()
    v = inv.evaluate("MUT-002", VIOLATION_DIFF, [PROTECTED])
    assert v.passed is False
    assert len(v.violations) > 0

# T113-SELF-AWARE-05: touching protected module without removing calls = pass
def test_T113_05_touch_no_removal_passes():
    inv = make_inv()
    diff = "+def helper():\n+    pass\n"
    v = inv.evaluate("MUT-003", diff, [PROTECTED])
    assert v.passed is True

# T113-SELF-AWARE-06: removing calls without touching protected = pass
def test_T113_06_removal_without_protected_passes():
    inv = make_inv()
    v = inv.evaluate("MUT-004", VIOLATION_DIFF, ["unrelated.py"])
    assert v.passed is True

# T113-SELF-AWARE-07: SELF-AWARE-AUDIT-0 — verdict_digest non-empty
def test_T113_07_digest_nonempty():
    inv = make_inv()
    v = inv.evaluate("MUT-005", CLEAN_DIFF, [])
    assert v.verdict_digest.startswith("sha256:")

# T113-SELF-AWARE-08: SELF-AWARE-DETERM-0 — identical inputs = identical digest
def test_T113_08_determinism():
    inv1 = make_inv()
    inv2 = make_inv()
    v1 = inv1.evaluate("MUT-DET", CLEAN_DIFF, ["foo.py"])
    v2 = inv2.evaluate("MUT-DET", CLEAN_DIFF, ["foo.py"])
    assert v1.verdict_digest == v2.verdict_digest

# T113-SELF-AWARE-09: different mutation_id → different digest
def test_T113_09_different_id_different_digest():
    inv = make_inv()
    v1 = inv.evaluate("MUT-A", CLEAN_DIFF, [])
    v2 = inv.evaluate("MUT-B", CLEAN_DIFF, [])
    assert v1.verdict_digest != v2.verdict_digest

# T113-SELF-AWARE-10: invariants_verified lists all three
def test_T113_10_invariants_listed():
    inv = make_inv()
    v = inv.evaluate("MUT-X", CLEAN_DIFF, [])
    assert set(v.invariants_verified) == {
        "SELF-AWARE-0", "SELF-AWARE-DETERM-0", "SELF-AWARE-AUDIT-0"
    }

# T113-SELF-AWARE-11: to_ledger_row produces valid JSON
def test_T113_11_ledger_row_json():
    inv = make_inv()
    v = inv.evaluate("MUT-LR", CLEAN_DIFF, [])
    parsed = json.loads(v.to_ledger_row())
    assert parsed["mutation_id"] == "MUT-LR"

# T113-SELF-AWARE-12: to_ledger_row is single-line
def test_T113_12_ledger_row_single_line():
    inv = make_inv()
    v = inv.evaluate("MUT-SL", CLEAN_DIFF, [])
    assert "\n" not in v.to_ledger_row()

# T113-SELF-AWARE-13: self_aware_guard passes on clean verdict
def test_T113_13_guard_pass_clean():
    inv = make_inv()
    v = inv.evaluate("MUT-GUARD", CLEAN_DIFF, [])
    self_aware_guard(v)  # must not raise

# T113-SELF-AWARE-14: self_aware_guard raises on empty digest
def test_T113_14_guard_empty_digest():
    inv = make_inv()
    v = inv.evaluate("MUT-G2", CLEAN_DIFF, [])
    v.verdict_digest = ""
    with pytest.raises(RuntimeError, match="SELF-AWARE-AUDIT-0"):
        self_aware_guard(v)

# T113-SELF-AWARE-15: self_aware_guard raises on passed=True with violations
def test_T113_15_guard_inconsistent_pass_with_violations():
    v = SelfAwarenessVerdict(
        mutation_id="MUT-BAD", passed=True,
        violations=["SELF-AWARE-0: bogus violation"],
    )
    with pytest.raises(RuntimeError, match="SELF-AWARE-0"):
        self_aware_guard(v)

# T113-SELF-AWARE-16: self_aware_guard raises on passed=False with no violations
def test_T113_16_guard_inconsistent_fail_no_violations():
    v = SelfAwarenessVerdict(mutation_id="MUT-BAD2", passed=False, violations=[])
    with pytest.raises(RuntimeError, match="SELF-AWARE-0"):
        self_aware_guard(v)

# T113-SELF-AWARE-17: register_protected_module expands surface
def test_T113_17_register_protected_expands():
    inv = make_inv()
    before = len(inv._protected)
    inv.register_protected_module("new/monitor.py")
    assert len(inv._protected) == before + 1

# T113-SELF-AWARE-18: registered module triggers violation
def test_T113_18_registered_module_triggers_violation():
    inv = make_inv()
    inv.register_protected_module("custom/observer.py")
    v = inv.evaluate("MUT-REG", VIOLATION_DIFF, ["custom/observer.py"])
    assert v.passed is False

# T113-SELF-AWARE-19: protected_surface_score 1.0 when no protected touched
def test_T113_19_surface_score_clean():
    inv = make_inv()
    s = inv.protected_surface_score(["unrelated.py"])
    assert s == 1.0

# T113-SELF-AWARE-20: protected_surface_score < 1.0 when protected touched
def test_T113_20_surface_score_touched():
    inv = make_inv()
    s = inv.protected_surface_score([PROTECTED])
    assert s < 1.0

# T113-SELF-AWARE-21: surface_score 0.0 when all protected touched
def test_T113_21_surface_score_zero():
    protected_list = list(_DEFAULT_PROTECTED())
    inv = make_inv()
    s = inv.protected_surface_score(list(inv._protected))
    assert s == 0.0

# T113-SELF-AWARE-22: summary returns required keys
def test_T113_22_summary_keys():
    inv = make_inv()
    s = inv.summary()
    for k in ["rule_id", "protected_module_count", "total_evaluations",
               "total_violations", "violation_rate", "invariants"]:
        assert k in s

# T113-SELF-AWARE-23: summary tracks evaluation count
def test_T113_23_summary_eval_count():
    inv = make_inv()
    inv.evaluate("A", CLEAN_DIFF, [])
    inv.evaluate("B", CLEAN_DIFF, [])
    assert inv.summary()["total_evaluations"] == 2

# T113-SELF-AWARE-24: summary tracks violation count
def test_T113_24_summary_violation_count():
    inv = make_inv()
    inv.evaluate("V1", VIOLATION_DIFF, [PROTECTED])
    inv.evaluate("V2", CLEAN_DIFF, [])
    assert inv.summary()["total_violations"] == 1

# T113-SELF-AWARE-25: audit trail written when path provided
def test_T113_25_audit_trail_written():
    td = Path(tempfile.mkdtemp())
    apath = td / "audit.jsonl"
    inv = make_inv(audit_path=apath)
    inv.evaluate("MUT-AUD", CLEAN_DIFF, [])
    assert apath.exists()
    rows = [json.loads(l) for l in apath.read_text().splitlines() if l]
    assert rows[0]["mutation_id"] == "MUT-AUD"

# T113-SELF-AWARE-26: multiple verdicts accumulate in audit trail
def test_T113_26_audit_trail_accumulates():
    td = Path(tempfile.mkdtemp())
    apath = td / "audit.jsonl"
    inv = make_inv(audit_path=apath)
    inv.evaluate("M1", CLEAN_DIFF, [])
    inv.evaluate("M2", CLEAN_DIFF, [])
    rows = [l for l in apath.read_text().splitlines() if l]
    assert len(rows) == 2

# T113-SELF-AWARE-27: PROTECTED_OBSERVABILITY_MODULES contains default set
def test_T113_27_protected_modules_default():
    assert "runtime/metrics.py" in PROTECTED_OBSERVABILITY_MODULES
    assert "security/ledger/journal.py" in PROTECTED_OBSERVABILITY_MODULES

# T113-SELF-AWARE-28: OBSERVABILITY_REDUCTION_PATTERNS is non-empty list
def test_T113_28_reduction_patterns_nonempty():
    assert len(OBSERVABILITY_REDUCTION_PATTERNS) >= 5

# T113-SELF-AWARE-29: extra_protected constructor arg extends surface
def test_T113_29_extra_protected_constructor():
    inv = SelfAwarenessInvariant(extra_protected=frozenset(["extra/module.py"]))
    assert "extra/module.py" in inv._protected

# T113-SELF-AWARE-30: full integration — violation path end-to-end
def test_T113_30_integration():
    td = Path(tempfile.mkdtemp())
    inv = make_inv(audit_path=td / "audit.jsonl")
    diff = "-journal.append(event)\n-log.error('x')\n"
    v = inv.evaluate("MUT-INT", diff, ["security/ledger/journal.py"])
    assert v.passed is False
    self_aware_guard(v)  # consistent verdict, should not raise despite fail
    assert (td / "audit.jsonl").exists()

def _DEFAULT_PROTECTED():
    from runtime.innovations30.self_awareness_invariant import _DEFAULT_PROTECTED as D
    return D
