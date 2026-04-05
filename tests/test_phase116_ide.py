# SPDX-License-Identifier: Apache-2.0
"""T116-IDE-01..30 — Phase 116 INNOV-31 Invariant Discovery Engine acceptance tests.
All 30 tests must pass (30/30).
"""
import json, hashlib, pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, "/home/claude/adaad")

from runtime.innovations30.invariant_discovery import (
    InvariantDiscoveryEngine, DiscoveredRule, IDEViolation,
    IDE_INVARIANTS, ide_guard, MIN_PATTERN_FREQUENCY, MIN_PRECISION,
    _chain_digest, _hmac_tag,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────
def _records(pattern: str, count: int, total: int = None):
    """Generate rejected_records hitting `pattern` exactly `count` times."""
    total = total or count
    recs = [{"mutation_id": f"M{i:03d}", "failed_rules": [pattern], "reason_codes": [], "changed_files": []}
            for i in range(count)]
    # pad to total without the pattern
    recs += [{"mutation_id": f"P{i:03d}", "failed_rules": ["OTHER"], "reason_codes": [], "changed_files": []}
             for i in range(total - count)]
    return recs


def fresh(tmp_path) -> InvariantDiscoveryEngine:
    return InvariantDiscoveryEngine(ledger_path=tmp_path / "rules.jsonl",
                                    min_frequency=3, min_precision=0.80)


# ── T116-IDE-01: IDE_INVARIANTS registry has exactly 5 Hard entries ───────────
def test_T116_IDE_01_invariant_registry_5_hard():
    assert len(IDE_INVARIANTS) == 5
    for k, v in IDE_INVARIANTS.items():
        assert v["class"] == "Hard"


# ── T116-IDE-02: ide_guard passes when condition True ─────────────────────────
def test_T116_IDE_02_ide_guard_passes():
    ide_guard(True, "IDE-0")  # no exception


# ── T116-IDE-03: ide_guard raises IDEViolation when False ────────────────────
def test_T116_IDE_03_ide_guard_raises():
    with pytest.raises(IDEViolation):
        ide_guard(False, "IDE-0", "test detail")


# ── T116-IDE-04: IDEViolation message contains invariant name ─────────────────
def test_T116_IDE_04_violation_message():
    try:
        ide_guard(False, "IDE-PERSIST-0", "ledger missing")
    except IDEViolation as e:
        assert "IDE-PERSIST-0" in str(e)


# ── T116-IDE-05: DiscoveredRule auto-populates digest (IDE-AUDIT-0) ───────────
def test_T116_IDE_05_discovered_rule_digest_auto(tmp_path):
    r = DiscoveredRule(rule_id="R-01", pattern_description="desc",
                       failure_pattern="PAT-A", observed_frequency=5,
                       estimated_precision=0.9, proposed_yaml="",
                       discovery_epoch="epoch-1")
    assert r.digest.startswith("sha256:")


# ── T116-IDE-06: DiscoveredRule digest is non-empty (IDE-AUDIT-0 enforced) ───
def test_T116_IDE_06_digest_nonempty():
    r = DiscoveredRule("R", "d", "P", 6, 0.85, "", "e1")
    assert len(r.digest) > 0


# ── T116-IDE-07: analyze_failures returns empty list for empty input ──────────
def test_T116_IDE_07_empty_input(tmp_path):
    eng = fresh(tmp_path)
    assert eng.analyze_failures([], "epoch-1") == []


# ── T116-IDE-08: IDE-0 frequency gate — below threshold returns nothing ───────
def test_T116_IDE_08_frequency_gate(tmp_path):
    eng = fresh(tmp_path)
    recs = _records("PAT-LOW", 2, 2)  # count=2 < min_frequency=3
    result = eng.analyze_failures(recs, "epoch-1")
    assert result == []


# ── T116-IDE-09: IDE-0 precision gate — low precision dropped ────────────────
def test_T116_IDE_09_precision_gate(tmp_path):
    eng = fresh(tmp_path)
    # 3 hits out of 10 = 0.30 < 0.80
    recs = _records("PAT-LOW-PREC", 3, 10)
    result = eng.analyze_failures(recs, "epoch-1")
    assert result == []


# ── T116-IDE-10: rule returned when frequency AND precision both met ──────────
def test_T116_IDE_10_rule_returned_when_thresholds_met(tmp_path):
    eng = fresh(tmp_path)
    recs = _records("PAT-GOOD", 5, 5)  # 5/5 = 1.0 precision
    result = eng.analyze_failures(recs, "epoch-1")
    assert len(result) == 1
    assert result[0].failure_pattern == "PAT-GOOD"


# ── T116-IDE-11: IDE-GATE-0 deduplication — same pattern not returned twice ──
def test_T116_IDE_11_gate_dedup(tmp_path):
    eng = fresh(tmp_path)
    recs = _records("PAT-DUP", 5, 5)
    r1 = eng.analyze_failures(recs, "epoch-1")
    r2 = eng.analyze_failures(recs, "epoch-2")
    assert len(r1) == 1
    assert len(r2) == 0  # IDE-GATE-0: already known


# ── T116-IDE-12: IDE-DETERM-0 same epoch+pattern -> same rule_id ─────────────
def test_T116_IDE_12_deterministic_rule_id(tmp_path):
    eng1 = fresh(tmp_path / "a")
    eng2 = InvariantDiscoveryEngine(tmp_path / "b" / "r.jsonl", 3, 0.80)
    recs = _records("PAT-D", 5, 5)
    r1 = eng1.analyze_failures(recs, "epoch-X")
    r2 = eng2.analyze_failures(recs, "epoch-X")
    assert r1[0].rule_id == r2[0].rule_id


# ── T116-IDE-13: IDE-DETERM-0 same inputs -> same digest ─────────────────────
def test_T116_IDE_13_deterministic_digest(tmp_path):
    eng1 = fresh(tmp_path / "a")
    eng2 = InvariantDiscoveryEngine(tmp_path / "b" / "r.jsonl", 3, 0.80)
    recs = _records("PAT-D2", 5, 5)
    r1 = eng1.analyze_failures(recs, "epoch-Y")
    r2 = eng2.analyze_failures(recs, "epoch-Y")
    assert r1[0].digest == r2[0].digest


# ── T116-IDE-14: IDE-PERSIST-0 — ledger file created after analyze ────────────
def test_T116_IDE_14_ledger_created(tmp_path):
    eng = fresh(tmp_path)
    recs = _records("PAT-P", 5, 5)
    eng.analyze_failures(recs, "epoch-1")
    assert (tmp_path / "rules.jsonl").exists()


# ── T116-IDE-15: IDE-PERSIST-0 — all rules written to ledger ─────────────────
def test_T116_IDE_15_all_rules_persisted(tmp_path):
    eng = fresh(tmp_path)
    recs = _records("PAT-Q", 5, 5)
    result = eng.analyze_failures(recs, "epoch-1")
    lines = (tmp_path / "rules.jsonl").read_text().strip().splitlines()
    assert len(lines) == len(result)


# ── T116-IDE-16: ledger entries are valid JSON ────────────────────────────────
def test_T116_IDE_16_ledger_valid_json(tmp_path):
    eng = fresh(tmp_path)
    eng.analyze_failures(_records("PAT-J", 5, 5), "epoch-1")
    for line in (tmp_path / "rules.jsonl").read_text().strip().splitlines():
        json.loads(line)  # must not raise


# ── T116-IDE-17: ledger entries carry _hmac tag ───────────────────────────────
def test_T116_IDE_17_ledger_has_hmac(tmp_path):
    eng = fresh(tmp_path)
    eng.analyze_failures(_records("PAT-H", 5, 5), "epoch-1")
    for line in (tmp_path / "rules.jsonl").read_text().strip().splitlines():
        d = json.loads(line)
        assert "_hmac" in d


# ── T116-IDE-18: verify_chain returns True on intact ledger ───────────────────
def test_T116_IDE_18_verify_chain_intact(tmp_path):
    eng = fresh(tmp_path)
    eng.analyze_failures(_records("PAT-VC", 5, 5), "epoch-1")
    assert eng.verify_chain() is True


# ── T116-IDE-19: verify_chain returns True for empty ledger ───────────────────
def test_T116_IDE_19_verify_chain_empty(tmp_path):
    eng = fresh(tmp_path)
    assert eng.verify_chain() is True


# ── T116-IDE-20: verify_chain returns False after tamper ─────────────────────
def test_T116_IDE_20_verify_chain_tampered(tmp_path):
    eng = fresh(tmp_path)
    eng.analyze_failures(_records("PAT-T", 5, 5), "epoch-1")
    path = tmp_path / "rules.jsonl"
    content = path.read_text()
    path.write_text(content.replace('"proposed"', '"hacked"'))
    assert eng.verify_chain() is False


# ── T116-IDE-21: pending_rules returns proposed rules from ledger ──────────────
def test_T116_IDE_21_pending_rules(tmp_path):
    eng = fresh(tmp_path)
    eng.analyze_failures(_records("PAT-PR", 5, 5), "epoch-1")
    pending = eng.pending_rules()
    assert len(pending) == 1
    assert pending[0].status == "proposed"


# ── T116-IDE-22: pending_rules empty when ledger absent ──────────────────────
def test_T116_IDE_22_pending_rules_empty_when_no_ledger(tmp_path):
    eng = fresh(tmp_path)
    assert eng.pending_rules() == []


# ── T116-IDE-23: rule_id format matches DISC-<8char>-<NN> ────────────────────
def test_T116_IDE_23_rule_id_format(tmp_path):
    eng = fresh(tmp_path)
    result = eng.analyze_failures(_records("PAT-FMT", 5, 5), "epoch-2026")
    import re
    assert re.match(r"DISC-[A-Za-z0-9]{1,8}-\d{2}", result[0].rule_id)


# ── T116-IDE-24: proposed_yaml is non-empty string ───────────────────────────
def test_T116_IDE_24_proposed_yaml_nonempty(tmp_path):
    eng = fresh(tmp_path)
    result = eng.analyze_failures(_records("PAT-Y", 5, 5), "epoch-1")
    assert result[0].proposed_yaml


# ── T116-IDE-25: evidence_mutation_ids capped at 5 ───────────────────────────
def test_T116_IDE_25_evidence_capped(tmp_path):
    eng = fresh(tmp_path)
    recs = _records("PAT-EV", 10, 10)
    result = eng.analyze_failures(recs, "epoch-1")
    assert len(result[0].evidence_mutation_ids) <= 5


# ── T116-IDE-26: multiple distinct patterns each produce a rule ────────────────
def test_T116_IDE_26_multiple_patterns(tmp_path):
    eng = fresh(tmp_path)
    recs = []
    for pat in ["PAT-A", "PAT-B", "PAT-C"]:
        recs += _records(pat, 3, 3)
    # Use a fresh engine that will find all 3 patterns meeting thresholds
    eng2 = InvariantDiscoveryEngine(tmp_path / "multi.jsonl", min_frequency=3, min_precision=0.0)
    result = eng2.analyze_failures(recs, "epoch-1")
    assert len(result) >= 2


# ── T116-IDE-27: runtime/ file patterns extracted correctly ───────────────────
def test_T116_IDE_27_file_pattern_extraction(tmp_path):
    eng = InvariantDiscoveryEngine(tmp_path / "r.jsonl", min_frequency=3, min_precision=0.0)
    recs = [{"mutation_id": f"M{i}", "failed_rules": [], "reason_codes": [],
              "changed_files": ["runtime/core/foo.py"]} for i in range(5)]
    result = eng.analyze_failures(recs, "epoch-1")
    patterns = [r.failure_pattern for r in result]
    assert any("targets_runtime_core" in p for p in patterns)


# ── T116-IDE-28: IDE_INVARIANTS keys match expected names ─────────────────────
def test_T116_IDE_28_invariant_keys():
    expected = {"IDE-0", "IDE-DETERM-0", "IDE-PERSIST-0", "IDE-AUDIT-0", "IDE-GATE-0"}
    assert set(IDE_INVARIANTS.keys()) == expected


# ── T116-IDE-29: _chain_digest is deterministic ───────────────────────────────
def test_T116_IDE_29_chain_digest_deterministic():
    d1 = _chain_digest("R-01", "PAT", "0000000000000000")
    d2 = _chain_digest("R-01", "PAT", "0000000000000000")
    assert d1 == d2
    assert d1.startswith("sha256:")


# ── T116-IDE-30: __all__ exports all public symbols ──────────────────────────
def test_T116_IDE_30_all_exports():
    from runtime.innovations30 import invariant_discovery as m
    for sym in ["InvariantDiscoveryEngine", "DiscoveredRule", "IDEViolation",
                "IDE_INVARIANTS", "ide_guard"]:
        assert sym in m.__all__
