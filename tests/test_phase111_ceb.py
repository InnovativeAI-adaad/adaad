# SPDX-License-Identifier: Apache-2.0
"""T111-CEB-01..30 — Phase 111 acceptance tests for INNOV-26 Constitutional Entropy Budget.

Constitutional invariants under test:
    CEB-0        — drift_ratio computed correctly; requires_double_signoff enforced at >= 0.30
    CEB-DETERM-0 — check_drift() deterministic for identical inputs
    CEB-AUDIT-0  — report_digest non-empty; record_amendment() writes to DriftLedger
"""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from runtime.innovations30.constitutional_entropy_budget import (
    ConstitutionalEntropyBudget, ConstitutionalDriftReport, AmendmentRecord,
    DriftLedger, drift_guard,
    CEB_INVARIANTS, DRIFT_WARNING_THRESHOLD, DRIFT_CRITICAL_THRESHOLD,
    COOLING_PERIOD_EPOCHS,
)

GENESIS = ["RULE-A", "RULE-B", "RULE-C", "RULE-D", "RULE-E"]


def make_ceb(tmp_path=None, genesis=None):
    td = tmp_path or Path(tempfile.mkdtemp())
    ledger = DriftLedger(td / "ledger.jsonl")
    ceb = ConstitutionalEntropyBudget(
        state_path=td / "state.json",
        ledger=ledger,
    )
    if genesis is not None:
        ceb.snapshot_genesis(genesis)
    return ceb, ledger, td


# ══════════════════════════════════════════════════════════════════════════════
# T111-CEB-01: module imports without error
def test_T111_CEB_01_import():
    assert ConstitutionalEntropyBudget is not None

# T111-CEB-02: CEB_INVARIANTS has exactly three entries
def test_T111_CEB_02_invariant_registry():
    assert set(CEB_INVARIANTS.keys()) == {"CEB-0", "CEB-DETERM-0", "CEB-AUDIT-0"}

# T111-CEB-03: thresholds have correct values
def test_T111_CEB_03_threshold_values():
    assert DRIFT_WARNING_THRESHOLD == 0.20
    assert DRIFT_CRITICAL_THRESHOLD == 0.30
    assert COOLING_PERIOD_EPOCHS == 10

# T111-CEB-04: zero drift when current equals genesis
def test_T111_CEB_04_zero_drift():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    r = ceb.check_drift(GENESIS, 1)
    assert r.drift_ratio == 0.0
    assert r.requires_double_signoff is False

# T111-CEB-05: drift_ratio = 1/5 = 0.2 when one rule added
def test_T111_CEB_05_single_add_drift():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    r = ceb.check_drift(GENESIS + ["RULE-F"], 1)
    assert abs(r.drift_ratio - round(1/5, 6)) < 1e-5
    assert "RULE-F" in r.added_rules

# T111-CEB-06: drift_ratio = 1/5 = 0.2 when one rule removed
def test_T111_CEB_06_single_remove_drift():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    r = ceb.check_drift(GENESIS[:-1], 1)
    assert abs(r.drift_ratio - round(1/5, 6)) < 1e-5
    assert "RULE-E" in r.removed_rules

# T111-CEB-07: CEB-0 — requires_double_signoff True at 30% drift
def test_T111_CEB_07_double_signoff_at_30pct():
    ceb, _, _ = make_ceb(genesis=GENESIS)  # 5 rules
    # add 2 rules: 2/5 = 0.40 >= 0.30
    current = GENESIS + ["RULE-F", "RULE-G"]
    r = ceb.check_drift(current, 1)
    assert r.drift_ratio >= 0.30
    assert r.requires_double_signoff is True

# T111-CEB-08: CEB-0 — requires_double_signoff False below 30% drift
def test_T111_CEB_08_no_double_signoff_below_30pct():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    # add 1 rule: 1/5 = 0.20 < 0.30
    r = ceb.check_drift(GENESIS + ["RULE-F"], 1)
    assert r.requires_double_signoff is False

# T111-CEB-09: CEB-0 — exactly 30% triggers double signoff
def test_T111_CEB_09_exactly_30pct():
    ten_rules = [f"RULE-{i}" for i in range(10)]
    ceb, _, _ = make_ceb(genesis=ten_rules)
    current = ten_rules + ["RULE-NEW-A", "RULE-NEW-B", "RULE-NEW-C"]  # 3/10 = 0.30
    r = ceb.check_drift(current, 1)
    assert r.drift_ratio == pytest.approx(0.30, abs=1e-5)
    assert r.requires_double_signoff is True

# T111-CEB-10: CEB-DETERM-0 — identical inputs produce identical report
def test_T111_CEB_10_determinism():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    r1 = ceb.check_drift(GENESIS + ["RULE-X"], 5)
    r2 = ceb.check_drift(GENESIS + ["RULE-X"], 5)
    assert r1.report_digest == r2.report_digest
    assert r1.drift_ratio == r2.drift_ratio

# T111-CEB-11: CEB-AUDIT-0 — report_digest is non-empty
def test_T111_CEB_11_report_digest_nonempty():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    r = ceb.check_drift(GENESIS, 1)
    assert r.report_digest.startswith("sha256:")
    assert len(r.report_digest) > 10

# T111-CEB-12: different drift produces different report_digest
def test_T111_CEB_12_digest_differs_for_different_drift():
    ceb1, _, _ = make_ceb(genesis=GENESIS)
    ceb2, _, _ = make_ceb(genesis=GENESIS)
    r1 = ceb1.check_drift(GENESIS, 1)
    r2 = ceb2.check_drift(GENESIS + ["RULE-X"], 1)
    assert r1.report_digest != r2.report_digest

# T111-CEB-13: ConstitutionalDriftReport.invariants_verified includes all three
def test_T111_CEB_13_report_invariants_listed():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    r = ceb.check_drift(GENESIS, 1)
    assert set(r.invariants_verified) == {"CEB-0", "CEB-DETERM-0", "CEB-AUDIT-0"}

# T111-CEB-14: to_ledger_row produces valid single-line JSON
def test_T111_CEB_14_report_ledger_row():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    r = ceb.check_drift(GENESIS, 1)
    row = r.to_ledger_row()
    parsed = json.loads(row)
    assert "drift_ratio" in parsed
    assert "\n" not in row

# T111-CEB-15: cooling_period_active True when within COOLING_PERIOD_EPOCHS
def test_T111_CEB_15_cooling_period_active():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    ceb.record_amendment("epoch-1", 5)
    r = ceb.check_drift(GENESIS, 10)   # seq 10, last amendment seq 5, diff=5 < 10
    assert r.cooling_period_active is True

# T111-CEB-16: cooling_period_active False when beyond COOLING_PERIOD_EPOCHS
def test_T111_CEB_16_cooling_period_inactive():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    ceb.record_amendment("epoch-1", 1)
    r = ceb.check_drift(GENESIS, 12)   # seq 12, last amendment seq 1, diff=11 >= 10
    assert r.cooling_period_active is False

# T111-CEB-17: record_amendment persists to DriftLedger [CEB-AUDIT-0]
def test_T111_CEB_17_amendment_writes_ledger():
    ceb, ledger, _ = make_ceb(genesis=GENESIS)
    ceb.record_amendment("epoch-42", 42)
    rows = ledger.rows()
    assert len(rows) == 1
    assert rows[0]["epoch_id"] == "epoch-42"

# T111-CEB-18: multiple amendments accumulate in ledger
def test_T111_CEB_18_multiple_amendments_accumulate():
    ceb, ledger, _ = make_ceb(genesis=GENESIS)
    ceb.record_amendment("e1", 1)
    ceb.record_amendment("e2", 2)
    ceb.record_amendment("e3", 3)
    assert len(ledger.rows()) == 3

# T111-CEB-19: AmendmentRecord to_ledger_row is valid JSON
def test_T111_CEB_19_amendment_record_json():
    rec = AmendmentRecord(
        epoch_id="e99", epoch_seq=99,
        drift_ratio_at_amendment=0.1, required_double_signoff=False,
        timestamp_utc="2026-04-03T00:00:00Z",
    )
    row = rec.to_ledger_row()
    parsed = json.loads(row)
    assert parsed["innovation"] == "INNOV-26"
    assert parsed["phase"] == 111

# T111-CEB-20: AmendmentRecord ledger row is single-line
def test_T111_CEB_20_amendment_record_single_line():
    rec = AmendmentRecord(
        epoch_id="e1", epoch_seq=1,
        drift_ratio_at_amendment=0.0, required_double_signoff=False,
        timestamp_utc="2026-04-03T00:00:00Z",
    )
    assert "\n" not in rec.to_ledger_row()

# T111-CEB-21: drift_guard passes when report is consistent (no double required)
def test_T111_CEB_21_drift_guard_pass_no_double():
    r = ConstitutionalDriftReport(
        current_rule_count=5, genesis_rule_count=5,
        drift_ratio=0.10, requires_double_signoff=False,
    )
    drift_guard(r)  # must not raise

# T111-CEB-22: drift_guard passes when double is correctly flagged
def test_T111_CEB_22_drift_guard_pass_with_double():
    r = ConstitutionalDriftReport(
        current_rule_count=7, genesis_rule_count=5,
        added_rules=["X", "Y"], drift_ratio=0.40, requires_double_signoff=True,
    )
    drift_guard(r)  # must not raise

# T111-CEB-23: drift_guard raises on inconsistent requires_double_signoff
def test_T111_CEB_23_drift_guard_rejects_inconsistent():
    # drift_ratio 0.40 should require double but flag is False
    r = ConstitutionalDriftReport(
        current_rule_count=7, genesis_rule_count=5,
        drift_ratio=0.40, requires_double_signoff=False,  # wrong!
    )
    with pytest.raises(RuntimeError, match="CEB-0"):
        drift_guard(r)

# T111-CEB-24: budget_status returns required keys
def test_T111_CEB_24_budget_status_keys():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    status = ceb.budget_status()
    for key in ["innovation", "genesis_rule_count", "drift_warning_threshold",
                "drift_critical_threshold", "cooling_period_epochs"]:
        assert key in status

# T111-CEB-25: budget_status reports correct genesis_rule_count
def test_T111_CEB_25_budget_status_genesis_count():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    assert ceb.budget_status()["genesis_rule_count"] == 5

# T111-CEB-26: state persists across reload
def test_T111_CEB_26_state_persistence():
    td = Path(tempfile.mkdtemp())
    ceb1 = ConstitutionalEntropyBudget(state_path=td / "state.json",
                                        ledger=DriftLedger(td / "l.jsonl"))
    ceb1.snapshot_genesis(GENESIS)
    ceb2 = ConstitutionalEntropyBudget(state_path=td / "state.json",
                                        ledger=DriftLedger(td / "l.jsonl"))
    assert ceb2._genesis_rules == set(GENESIS)

# T111-CEB-27: first call with no genesis auto-bootstraps
def test_T111_CEB_27_auto_bootstrap_genesis():
    ceb, _, _ = make_ceb()
    r = ceb.check_drift(GENESIS, 1)
    assert r.drift_ratio == 0.0  # auto-bootstrapped

# T111-CEB-28: added_rules and removed_rules are sorted (determinism)
def test_T111_CEB_28_sorted_rule_lists():
    ceb, _, _ = make_ceb(genesis=GENESIS)
    current = ["RULE-Z", "RULE-A", "RULE-B", "RULE-M"]  # removed C,D,E; added Z,M
    r = ceb.check_drift(current, 1)
    assert r.added_rules == sorted(r.added_rules)
    assert r.removed_rules == sorted(r.removed_rules)

# T111-CEB-29: DriftLedger returns empty list when no file exists
def test_T111_CEB_29_empty_ledger():
    td = Path(tempfile.mkdtemp())
    ledger = DriftLedger(td / "nonexistent.jsonl")
    assert ledger.rows() == []

# T111-CEB-30: full integration — genesis, drift check, amendment, ledger verify
def test_T111_CEB_30_integration():
    ceb, ledger, _ = make_ceb(genesis=GENESIS)
    current = GENESIS + ["RULE-NEW-1", "RULE-NEW-2"]  # 2/5 = 0.40 >= 0.30
    r = ceb.check_drift(current, 3)
    assert r.requires_double_signoff is True
    drift_guard(r)  # consistent — must not raise
    ceb.record_amendment("epoch-3", 3)
    rows = ledger.rows()
    assert len(rows) == 1
    assert rows[0]["epoch_seq"] == 3
    r2 = ceb.check_drift(current, 5)  # cooling active
    assert r2.cooling_period_active is True
