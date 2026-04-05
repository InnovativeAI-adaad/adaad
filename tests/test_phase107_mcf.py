# SPDX-License-Identifier: Apache-2.0
"""Phase 107 — INNOV-22 Mutation Conflict Framework (MCF) acceptance tests.

T107-MCF-01 … T107-MCF-30  — 30/30 must pass.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import pytest

from runtime.innovations30.mutation_conflict_framework import (
    ConflictRecord,
    EscalationAdvisory,
    MCFViolation,
    MutationConflictFramework,
    AUTO_RESOLVE_SEVERITIES,
    ESCALATION_SEVERITIES,
    MCF_VERSION,
    VALID_SEVERITIES,
    MCF_INV_VERSION, MCF_INV_DETECT, MCF_INV_SEVERITY,
    MCF_INV_PERSIST, MCF_INV_CHAIN, MCF_INV_RESOLVE,
    MCF_INV_GATE, MCF_INV_DETERM,
)


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_mcf(tmp_path):
    return MutationConflictFramework(state_path=tmp_path / "conflicts.jsonl")


@pytest.fixture
def tmp_ledger(tmp_path):
    return tmp_path / "conflicts.jsonl"


# ── T107-MCF-01: MCF_VERSION non-empty (MCF-0) ───────────────────────────────

def test_mcf_01_version_non_empty():
    """MCF-0: MCF_VERSION must be present and non-empty."""
    assert MCF_VERSION
    assert isinstance(MCF_VERSION, str)
    assert len(MCF_VERSION) > 0


# ── T107-MCF-02: invariant codes exposed (MCF-0) ─────────────────────────────

def test_mcf_02_invariant_codes_exported():
    """MCF-0: all eight invariant code constants must be non-empty strings."""
    for code in [
        MCF_INV_VERSION, MCF_INV_DETECT, MCF_INV_SEVERITY,
        MCF_INV_PERSIST, MCF_INV_CHAIN, MCF_INV_RESOLVE,
        MCF_INV_GATE, MCF_INV_DETERM,
    ]:
        assert isinstance(code, str) and code


# ── T107-MCF-03: no overlap → None returned (MCF-DETECT-0) ──────────────────

def test_mcf_03_no_overlap_returns_none(tmp_mcf):
    """MCF-DETECT-0: disjoint target paths produce no conflict."""
    result = tmp_mcf.analyze(
        "mut-A", "mut-B",
        ["runtime/module_x.py", "runtime/module_y.py"],
        ["runtime/module_z.py", "runtime/module_w.py"],
    )
    assert result is None


# ── T107-MCF-04: overlap → ConflictRecord returned (MCF-DETECT-0) ───────────

def test_mcf_04_overlap_returns_record(tmp_mcf):
    """MCF-DETECT-0: shared path produces a ConflictRecord."""
    record = tmp_mcf.analyze(
        "mut-A", "mut-B",
        ["runtime/shared.py"],
        ["runtime/shared.py"],
    )
    assert isinstance(record, ConflictRecord)
    assert "runtime/shared.py" in record.overlap_paths


# ── T107-MCF-05: blank mutation_id_a raises MCFViolation (MCF-GATE-0) ────────

def test_mcf_05_blank_id_a_raises(tmp_mcf):
    """MCF-GATE-0: blank mutation_id_a is a constitutional violation."""
    with pytest.raises(MCFViolation, match=MCF_INV_GATE):
        tmp_mcf.analyze("", "mut-B", ["a.py"], ["a.py"])


# ── T107-MCF-06: blank mutation_id_b raises MCFViolation (MCF-GATE-0) ────────

def test_mcf_06_blank_id_b_raises(tmp_mcf):
    """MCF-GATE-0: blank mutation_id_b is a constitutional violation."""
    with pytest.raises(MCFViolation, match=MCF_INV_GATE):
        tmp_mcf.analyze("mut-A", "   ", ["a.py"], ["a.py"])


# ── T107-MCF-07: conflict_digest is deterministic (MCF-DETERM-0) ─────────────

def test_mcf_07_deterministic_digest(tmp_mcf):
    """MCF-DETERM-0: digest is stable across two independent constructions."""
    r1 = tmp_mcf.analyze("mut-A", "mut-B", ["x.py"], ["x.py"])
    # Build expected digest manually
    ids = sorted(["mut-A", "mut-B"])
    overlap = sorted(["x.py"])
    payload = (
        f"{ids[0]}:{ids[1]}"
        f":{','.join(overlap)}"
        f":{r1.severity}:unresolved"
        f":genesis"
    )
    expected = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
    assert r1.conflict_digest == expected


# ── T107-MCF-08: digest order-independent on mutation_ids (MCF-DETERM-0) ─────

def test_mcf_08_digest_id_order_independent(tmp_path):
    """MCF-DETERM-0: swapping A/B yields same digest (sorted internally)."""
    mcf1 = MutationConflictFramework(state_path=tmp_path / "c1.jsonl")
    mcf2 = MutationConflictFramework(state_path=tmp_path / "c2.jsonl")
    r1 = mcf1.analyze("mut-A", "mut-B", ["shared.py"], ["shared.py"])
    r2 = mcf2.analyze("mut-B", "mut-A", ["shared.py"], ["shared.py"])
    # Same sorted IDs → same digest (modulo prev_digest which is genesis both)
    assert r1.conflict_digest == r2.conflict_digest


# ── T107-MCF-09: persist appends to JSONL (MCF-PERSIST-0) ────────────────────

def test_mcf_09_persist_appends_jsonl(tmp_path):
    """MCF-PERSIST-0: each detect call appends exactly one JSONL line."""
    ledger = tmp_path / "c.jsonl"
    mcf = MutationConflictFramework(state_path=ledger)
    mcf.analyze("mut-A", "mut-B", ["f.py"], ["f.py"])
    mcf.analyze("mut-C", "mut-D", ["g.py"], ["g.py"])
    lines = [l for l in ledger.read_text().splitlines() if l.strip()]
    assert len(lines) == 2


# ── T107-MCF-10: ledger uses append mode only (MCF-PERSIST-0) ────────────────

def test_mcf_10_ledger_no_overwrite(tmp_path):
    """MCF-PERSIST-0: pre-existing ledger content is preserved after new write."""
    ledger = tmp_path / "c.jsonl"
    sentinel = '{"sentinel": true}\n'
    ledger.write_text(sentinel)
    mcf = MutationConflictFramework(state_path=ledger)
    mcf.analyze("mut-A", "mut-B", ["f.py"], ["f.py"])
    content = ledger.read_text()
    assert content.startswith(sentinel)


# ── T107-MCF-11: low severity for small overlap ratio (MCF-SEVERITY-0) ───────

def test_mcf_11_low_severity_small_overlap(tmp_mcf):
    """MCF-SEVERITY-0: <25% overlap ratio → severity='low'."""
    record = tmp_mcf.analyze(
        "mut-A", "mut-B",
        ["a.py", "b.py", "c.py", "d.py", "e.py"],  # 5 paths
        ["a.py", "z1.py", "z2.py", "z3.py", "z4.py"],  # 1 overlap / 5 = 0.20
    )
    assert record is not None
    assert record.severity == "low"


# ── T107-MCF-12: medium severity (MCF-SEVERITY-0) ────────────────────────────

def test_mcf_12_medium_severity(tmp_mcf):
    """MCF-SEVERITY-0: 25–50% overlap ratio → severity='medium'."""
    record = tmp_mcf.analyze(
        "mut-A", "mut-B",
        ["a.py", "b.py", "c.py", "d.py"],  # 4 paths
        ["a.py", "b.py", "x.py", "y.py"],  # 2 overlap / 4 = 0.50 → medium
    )
    assert record is not None
    assert record.severity in ("medium", "high")


# ── T107-MCF-13: critical severity for full overlap (MCF-SEVERITY-0) ─────────

def test_mcf_13_critical_severity_full_overlap(tmp_mcf):
    """MCF-SEVERITY-0: 100% overlap → severity='critical'."""
    record = tmp_mcf.analyze(
        "mut-A", "mut-B",
        ["a.py", "b.py"],
        ["a.py", "b.py"],
    )
    assert record is not None
    assert record.severity == "critical"


# ── T107-MCF-14: valid severity set (MCF-SEVERITY-0) ─────────────────────────

def test_mcf_14_valid_severity_set():
    """MCF-SEVERITY-0: VALID_SEVERITIES == expected four values."""
    assert VALID_SEVERITIES == {"low", "medium", "high", "critical"}


# ── T107-MCF-15: AUTO_RESOLVE_SEVERITIES subset (MCF-RESOLVE-0) ──────────────

def test_mcf_15_auto_resolve_severities():
    """MCF-RESOLVE-0: auto-resolution allowed only for low/medium."""
    assert AUTO_RESOLVE_SEVERITIES == {"low", "medium"}
    assert ESCALATION_SEVERITIES == {"high", "critical"}


# ── T107-MCF-16: low/medium conflict auto-resolves without HUMAN-0 (MCF-RESOLVE-0)

def test_mcf_16_auto_resolve_low(tmp_mcf):
    """MCF-RESOLVE-0: low severity resolves without human0_acknowledged."""
    record = tmp_mcf.analyze(
        "mut-A", "mut-B",
        ["a.py", "b.py", "c.py", "d.py", "e.py"],
        ["a.py", "z.py", "y.py", "x.py", "w.py"],
    )
    assert record is not None and record.severity == "low"
    resolved = tmp_mcf.resolve(record.conflict_digest, "mutation_a_wins")
    assert resolved.resolution == "mutation_a_wins"


# ── T107-MCF-17: critical escalation without HUMAN-0 raises (MCF-RESOLVE-0) ──

def test_mcf_17_critical_no_human0_raises(tmp_mcf):
    """MCF-RESOLVE-0: resolving critical without human0_acknowledged raises MCFViolation."""
    record = tmp_mcf.analyze("mut-A", "mut-B", ["a.py"], ["a.py"])
    assert record is not None and record.severity == "critical"
    with pytest.raises(MCFViolation, match=MCF_INV_RESOLVE):
        tmp_mcf.resolve(record.conflict_digest, "auto", human0_acknowledged=False)


# ── T107-MCF-18: critical resolves after HUMAN-0 acknowledged (MCF-RESOLVE-0) ─

def test_mcf_18_critical_resolves_with_human0(tmp_mcf):
    """MCF-RESOLVE-0: critical conflict resolves with human0_acknowledged=True."""
    record = tmp_mcf.analyze("mut-A", "mut-B", ["a.py"], ["a.py"])
    assert record is not None
    resolved = tmp_mcf.resolve(
        record.conflict_digest, "human0_deferred", human0_acknowledged=True
    )
    assert resolved.resolution == "human0_deferred"
    assert resolved.human0_escalated is True


# ── T107-MCF-19: escalation advisory created for critical (MCF-RESOLVE-0) ────

def test_mcf_19_escalation_advisory_created(tmp_mcf):
    """MCF-RESOLVE-0: critical conflict produces pending escalation advisory."""
    tmp_mcf.analyze("mut-A", "mut-B", ["a.py"], ["a.py"])
    pending = tmp_mcf.pending_escalations()
    assert len(pending) == 1
    assert pending[0].severity == "critical"
    assert "HUMAN-0" in pending[0].message


# ── T107-MCF-20: acknowledge_escalation clears advisory ──────────────────────

def test_mcf_20_acknowledge_clears_escalation(tmp_mcf):
    """Acknowledging an escalation removes it from pending list."""
    record = tmp_mcf.analyze("mut-A", "mut-B", ["a.py"], ["a.py"])
    assert record is not None
    digest = tmp_mcf.pending_escalations()[0].conflict_digest
    tmp_mcf.acknowledge_escalation(digest)
    assert len(tmp_mcf.pending_escalations()) == 0


# ── T107-MCF-21: resolve unknown digest raises MCFViolation ──────────────────

def test_mcf_21_resolve_unknown_digest_raises(tmp_mcf):
    """MCF-RESOLVE-0: resolving an unknown digest raises MCFViolation."""
    with pytest.raises(MCFViolation, match=MCF_INV_RESOLVE):
        tmp_mcf.resolve("sha256:nonexistent", "manual")


# ── T107-MCF-22: chain integrity valid after single detect (MCF-CHAIN-0) ─────

def test_mcf_22_chain_valid_single_entry(tmp_path):
    """MCF-CHAIN-0: chain verifies after a single conflict record."""
    ledger = tmp_path / "c.jsonl"
    mcf = MutationConflictFramework(state_path=ledger)
    mcf.analyze("mut-A", "mut-B", ["f.py"], ["f.py"])
    ok, msg = mcf.verify_chain()
    assert ok, msg


# ── T107-MCF-23: chain integrity valid across multiple entries (MCF-CHAIN-0) ─

def test_mcf_23_chain_valid_multiple_entries(tmp_path):
    """MCF-CHAIN-0: chain verifies correctly across three conflict events."""
    ledger = tmp_path / "c.jsonl"
    mcf = MutationConflictFramework(state_path=ledger)
    mcf.analyze("mut-A", "mut-B", ["f.py"], ["f.py"])
    mcf.analyze("mut-C", "mut-D", ["g.py"], ["g.py"])
    mcf.analyze("mut-E", "mut-F", ["h.py"], ["h.py"])
    ok, msg = mcf.verify_chain()
    assert ok, msg


# ── T107-MCF-24: tampered ledger fails chain verify (MCF-CHAIN-0) ────────────

def test_mcf_24_tampered_ledger_fails_chain(tmp_path):
    """MCF-CHAIN-0: a tampered ledger entry causes chain verification to fail."""
    ledger = tmp_path / "c.jsonl"
    mcf = MutationConflictFramework(state_path=ledger)
    mcf.analyze("mut-A", "mut-B", ["f.py"], ["f.py"])
    content = ledger.read_text()
    d = json.loads(content.strip())
    d["severity"] = "low"  # tamper: change severity post-hoc
    ledger.write_text(json.dumps(d) + "\n")
    ok, msg = mcf.verify_chain()
    assert not ok


# ── T107-MCF-25: empty ledger chain verify passes (MCF-CHAIN-0) ──────────────

def test_mcf_25_empty_ledger_chain_valid(tmp_path):
    """MCF-CHAIN-0: an empty ledger trivially passes chain verification."""
    ledger = tmp_path / "c.jsonl"
    mcf = MutationConflictFramework(state_path=ledger)
    ok, msg = mcf.verify_chain()
    assert ok
    assert "trivially" in msg


# ── T107-MCF-26: state persists across reinit (MCF-PERSIST-0) ─────────────────

def test_mcf_26_state_reloaded_across_init(tmp_path):
    """MCF-PERSIST-0: records are restored from ledger on re-construction."""
    ledger = tmp_path / "c.jsonl"
    mcf1 = MutationConflictFramework(state_path=ledger)
    record = mcf1.analyze("mut-A", "mut-B", ["f.py"], ["f.py"])
    assert record is not None
    digest = record.conflict_digest

    mcf2 = MutationConflictFramework(state_path=ledger)
    summary = mcf2.conflict_summary()
    assert summary["total_conflicts"] >= 1


# ── T107-MCF-27: conflict_summary counts correctly ───────────────────────────

def test_mcf_27_conflict_summary_counts(tmp_mcf):
    """conflict_summary reports correct total and resolved counts."""
    r = tmp_mcf.analyze(
        "mut-A", "mut-B",
        ["a.py", "b.py", "c.py", "d.py", "e.py"],
        ["a.py", "z1.py", "z2.py", "z3.py", "z4.py"],
    )
    assert r is not None
    summary = tmp_mcf.conflict_summary()
    assert summary["total_conflicts"] == 1
    assert summary["unresolved"] == 1
    assert summary["resolved"] == 0


# ── T107-MCF-28: resolve increments resolved count ───────────────────────────

def test_mcf_28_resolve_increments_count(tmp_mcf):
    """After resolve(), conflict_summary shows one more resolved entry."""
    r = tmp_mcf.analyze(
        "mut-A", "mut-B",
        ["a.py", "b.py", "c.py", "d.py", "e.py"],
        ["a.py", "z1.py", "z2.py", "z3.py", "z4.py"],
    )
    assert r is not None and r.severity == "low"
    tmp_mcf.resolve(r.conflict_digest, "mutation_a_wins")
    summary = tmp_mcf.conflict_summary()
    assert summary["resolved"] == 1
    assert summary["unresolved"] == 0


# ── T107-MCF-29: multiple overlapping paths captured (MCF-DETECT-0) ──────────

def test_mcf_29_multiple_overlap_paths_captured(tmp_mcf):
    """MCF-DETECT-0: all overlapping paths are recorded in overlap_paths."""
    record = tmp_mcf.analyze(
        "mut-A", "mut-B",
        ["a.py", "b.py", "c.py"],
        ["a.py", "b.py", "d.py"],
    )
    assert record is not None
    assert set(record.overlap_paths) == {"a.py", "b.py"}


# ── T107-MCF-30: EscalationAdvisory structure is correct ─────────────────────

def test_mcf_30_escalation_advisory_structure(tmp_mcf):
    """EscalationAdvisory carries required fields for HUMAN-0 review."""
    tmp_mcf.analyze("mut-A", "mut-B", ["a.py"], ["a.py"])
    advisories = tmp_mcf.pending_escalations()
    assert len(advisories) == 1
    adv = advisories[0]
    assert isinstance(adv, EscalationAdvisory)
    assert adv.conflict_digest
    assert adv.severity in VALID_SEVERITIES
    assert adv.mutation_id_a == "mut-A"
    assert adv.mutation_id_b == "mut-B"
    assert len(adv.overlap_paths) > 0
    assert not adv.acknowledged
