# SPDX-License-Identifier: Apache-2.0
"""Phase 105 — INNOV-20 Constitutional Stress Testing (CST) acceptance tests.

T105-CST-01 … T105-CST-30  — 30/30 must pass.
"""
from __future__ import annotations

import json
import tempfile
import hashlib
from pathlib import Path

import pytest

from runtime.innovations30.constitutional_stress_test import (
    ConstitutionalGap,
    ConstitutionalStressTester,
    ConstitutionalViolation,
    StressReport,
    StressTestCase,
    STRESS_PATTERNS,
    CST_GAP_MARGIN_THRESHOLD,
    CST_VERSION,
)


# ── fixtures ──────────────────────────────────────────────

@pytest.fixture
def tmp_paths(tmp_path):
    return tmp_path / "reports.jsonl", tmp_path / "feed.jsonl"


def _make_tester(tmp_paths, scenarios=None):
    rp, fp = tmp_paths
    return ConstitutionalStressTester(report_path=rp, discovery_feed_path=fp,
                                      scenarios=scenarios)


def _always_pass(_case):
    return True, []


def _always_fail(_case):
    return False, [_case.target_rule]


def _raising(_case):
    raise RuntimeError("eval exploded")


# ── T105-CST-01: module imports cleanly ──────────────────
def test_T105_CST_01_import():
    assert ConstitutionalStressTester is not None


# ── T105-CST-02: CST_VERSION is set ──────────────────────
def test_T105_CST_02_version():
    assert CST_VERSION == "1.0.0"


# ── T105-CST-03: catalogue has >= 10 patterns ────────────
def test_T105_CST_03_catalogue_size():
    assert len(STRESS_PATTERNS) >= 10


# ── T105-CST-04: all catalogue entries have required fields
def test_T105_CST_04_catalogue_fields():
    for s in STRESS_PATTERNS:
        assert s.case_id and s.target_rule and s.description and s.mutation_pattern
        assert 0.0 < s.expected_threshold_margin <= 1.0


# ── T105-CST-05: run() returns StressReport ──────────────
def test_T105_CST_05_run_returns_report(tmp_paths):
    t = _make_tester(tmp_paths)
    r = t.run("epoch-001", _always_fail)
    assert isinstance(r, StressReport)


# ── T105-CST-06: cases_tested == len(scenarios) ──────────
def test_T105_CST_06_cases_tested(tmp_paths):
    t = _make_tester(tmp_paths)
    r = t.run("epoch-002", _always_fail)
    assert r.cases_tested == len(STRESS_PATTERNS)


# ── T105-CST-07: all-fail → no gaps ──────────────────────
def test_T105_CST_07_all_fail_no_gaps(tmp_paths):
    t = _make_tester(tmp_paths)
    r = t.run("epoch-003", _always_fail)
    assert r.gaps_found == 0
    assert r.gaps == []


# ── T105-CST-08: CST-GAP-0 — thin margin + pass → gap ───
def test_T105_CST_08_gap_emitted_for_thin_margin(tmp_paths):
    thin = [StressTestCase("X-001", "r1", "desc", "pat", 0.02)]
    t = _make_tester(tmp_paths, scenarios=thin)
    r = t.run("epoch-004", _always_pass)
    assert r.gaps_found == 1
    assert r.gaps[0].gap_id.startswith("GAP-epoch-00")


# ── T105-CST-09: CST-GAP-0 — wide margin + pass → no gap ─
def test_T105_CST_09_no_gap_wide_margin(tmp_paths):
    wide = [StressTestCase("X-002", "r2", "desc", "pat", 0.20)]
    t = _make_tester(tmp_paths, scenarios=wide)
    r = t.run("epoch-005", _always_pass)
    assert r.gaps_found == 0


# ── T105-CST-10: CST-PERSIST-0 — ledger file created ─────
def test_T105_CST_10_ledger_created(tmp_paths):
    rp, _ = tmp_paths
    t = _make_tester(tmp_paths)
    t.run("epoch-006", _always_fail)
    assert rp.exists()


# ── T105-CST-11: ledger line is valid JSON ────────────────
def test_T105_CST_11_ledger_is_valid_json(tmp_paths):
    rp, _ = tmp_paths
    t = _make_tester(tmp_paths)
    t.run("epoch-007", _always_fail)
    line = rp.read_text().strip().split("\n")[0]
    data = json.loads(line)
    assert data["epoch_id"] == "epoch-007"


# ── T105-CST-12: multiple runs append, don't overwrite ───
def test_T105_CST_12_ledger_appends(tmp_paths):
    rp, _ = tmp_paths
    t = _make_tester(tmp_paths)
    t.run("epoch-008a", _always_fail)
    t.run("epoch-008b", _always_fail)
    lines = [l for l in rp.read_text().strip().split("\n") if l]
    assert len(lines) == 2


# ── T105-CST-13: CST-HALT-0 — unwritable ledger raises ───
def test_T105_CST_13_halt_on_unwritable(tmp_paths):
    from unittest.mock import patch
    import pathlib
    rp, fp = tmp_paths
    t = ConstitutionalStressTester(report_path=rp, discovery_feed_path=fp)
    with patch.object(pathlib.Path, "open", side_effect=OSError("permission denied")):
        with pytest.raises(ConstitutionalViolation, match="CST-HALT-0"):
            t.run("epoch-009", _always_fail)


# ── T105-CST-14: CST-DIGEST-0 — report_digest is set ─────
def test_T105_CST_14_report_digest_set(tmp_paths):
    t = _make_tester(tmp_paths)
    r = t.run("epoch-010", _always_fail)
    assert r.report_digest.startswith("sha256:")


# ── T105-CST-15: digest is deterministic ─────────────────
def test_T105_CST_15_report_digest_deterministic(tmp_paths):
    t = _make_tester(tmp_paths)
    r1 = t.run("epoch-011a", _always_fail)
    r2 = t.run("epoch-011b", _always_fail)
    # same content modulo epoch_id — digests differ
    assert r1.report_digest != r2.report_digest


# ── T105-CST-16: ConstitutionalGap digest set ────────────
def test_T105_CST_16_gap_digest_set(tmp_paths):
    thin = [StressTestCase("X-003", "r3", "d", "p", 0.01)]
    t = _make_tester(tmp_paths, scenarios=thin)
    r = t.run("epoch-012", _always_pass)
    assert r.gaps[0].gap_digest.startswith("sha256:")


# ── T105-CST-17: gap digest changes with gap_id ──────────
def test_T105_CST_17_gap_digest_varies_with_id():
    g1 = ConstitutionalGap("GAP-A", ["r1"], "pat", "risk", "rec")
    g2 = ConstitutionalGap("GAP-B", ["r1"], "pat", "risk", "rec")
    assert g1.gap_digest != g2.gap_digest


# ── T105-CST-18: CST-FEED-0 — feed file written on gap ───
def test_T105_CST_18_feed_written_on_gap(tmp_paths):
    _, fp = tmp_paths
    thin = [StressTestCase("X-004", "r4", "d", "p", 0.01)]
    t = _make_tester(tmp_paths, scenarios=thin)
    t.run("epoch-013", _always_pass)
    assert fp.exists()


# ── T105-CST-19: feed row has required keys ───────────────
def test_T105_CST_19_feed_row_keys(tmp_paths):
    _, fp = tmp_paths
    thin = [StressTestCase("X-005", "r5", "d", "p", 0.01)]
    t = _make_tester(tmp_paths, scenarios=thin)
    t.run("epoch-014", _always_pass)
    row = json.loads(fp.read_text().strip())
    for key in ("source", "gap_id", "bypassed_rules", "pattern", "risk",
                "proposed_rule", "gap_digest"):
        assert key in row, f"missing key: {key}"
    assert row["source"] == "CST"


# ── T105-CST-20: no feed file when no gaps ───────────────
def test_T105_CST_20_no_feed_when_no_gaps(tmp_paths):
    _, fp = tmp_paths
    t = _make_tester(tmp_paths)
    t.run("epoch-015", _always_fail)
    assert not fp.exists()


# ── T105-CST-21: CST-0 — empty epoch_id raises ──────────
def test_T105_CST_21_empty_epoch_id_raises(tmp_paths):
    t = _make_tester(tmp_paths)
    with pytest.raises(ConstitutionalViolation, match="CST-0"):
        t.run("", _always_fail)


# ── T105-CST-22: whitespace epoch_id raises ──────────────
def test_T105_CST_22_whitespace_epoch_id_raises(tmp_paths):
    t = _make_tester(tmp_paths)
    with pytest.raises(ConstitutionalViolation, match="CST-0"):
        t.run("   ", _always_fail)


# ── T105-CST-23: raising eval_fn produces gap ────────────
def test_T105_CST_23_raising_eval_fn_produces_gap(tmp_paths):
    thin = [StressTestCase("X-006", "r6", "d", "p", 0.01)]
    t = _make_tester(tmp_paths, scenarios=thin)
    r = t.run("epoch-016", _raising)
    assert r.gaps_found == 1
    assert "eval_error" in r.gaps[0].rules_bypassed


# ── T105-CST-24: patterns_run tracks all case_ids ────────
def test_T105_CST_24_patterns_run_complete(tmp_paths):
    t = _make_tester(tmp_paths)
    r = t.run("epoch-017", _always_fail)
    expected = {s.case_id for s in STRESS_PATTERNS}
    assert set(r.patterns_run) == expected


# ── T105-CST-25: catalogue() returns list of dicts ───────
def test_T105_CST_25_catalogue_returns_dicts(tmp_paths):
    t = _make_tester(tmp_paths)
    cat = t.catalogue()
    assert isinstance(cat, list)
    assert all(isinstance(c, dict) for c in cat)
    assert len(cat) == len(STRESS_PATTERNS)


# ── T105-CST-26: gaps_for_epoch — missing file → [] ──────
def test_T105_CST_26_gaps_for_epoch_missing_file(tmp_paths):
    rp, fp = tmp_paths
    t = ConstitutionalStressTester(report_path=rp / "nonexistent.jsonl",
                                   discovery_feed_path=fp)
    assert t.gaps_for_epoch("epoch-018") == []


# ── T105-CST-27: gaps_for_epoch — correct epoch returned ─
def test_T105_CST_27_gaps_for_epoch_filtered(tmp_paths):
    thin = [StressTestCase("X-007", "r7", "d", "p", 0.01)]
    t = _make_tester(tmp_paths, scenarios=thin)
    t.run("epAAA-019", _always_pass)
    t.run("epBBB-019", _always_pass)
    gaps_a = t.gaps_for_epoch("epAAA-019")
    gaps_b = t.gaps_for_epoch("epBBB-019")
    assert len(gaps_a) == 1
    assert len(gaps_b) == 1
    assert gaps_a[0]["gap_id"] != gaps_b[0]["gap_id"]


# ── T105-CST-28: ConstitutionalViolation is RuntimeError ─
def test_T105_CST_28_violation_is_runtime_error():
    exc = ConstitutionalViolation("test")
    assert isinstance(exc, RuntimeError)


# ── T105-CST-29: multiple gaps in single report ──────────
def test_T105_CST_29_multiple_gaps(tmp_paths):
    thin = [
        StressTestCase("X-008", "rA", "d", "p", 0.01),
        StressTestCase("X-009", "rB", "d", "p", 0.02),
        StressTestCase("X-010", "rC", "d", "p", 0.08),  # wide — no gap
    ]
    t = _make_tester(tmp_paths, scenarios=thin)
    r = t.run("epoch-020", _always_pass)
    assert r.gaps_found == 2
    assert r.cases_tested == 3


# ── T105-CST-30: CST-DETERM-0 — same inputs → same digest
def test_T105_CST_30_determ_digest(tmp_paths):
    thin = [StressTestCase("X-011", "rD", "d", "p", 0.01)]
    t1 = _make_tester(tmp_paths, scenarios=thin)
    rp2 = tmp_paths[0].parent / "r2.jsonl"
    fp2 = tmp_paths[0].parent / "f2.jsonl"
    t2 = ConstitutionalStressTester(report_path=rp2, discovery_feed_path=fp2,
                                    scenarios=thin)
    r1 = t1.run("epoch-determ", _always_pass)
    r2 = t2.run("epoch-determ", _always_pass)
    assert r1.report_digest == r2.report_digest
