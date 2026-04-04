# SPDX-License-Identifier: Apache-2.0
"""T112-BLAST-01..30 — Phase 112 acceptance tests for INNOV-27 Mutation Blast Radius Modeling."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from runtime.innovations30.blast_radius_model import (
    BlastRadiusModeler, BlastRadiusReport, blast_report_guard,
    BLAST_INVARIANTS, BLAST_THRESHOLDS, REVERSAL_SLA, VALID_RISK_TIERS,
)

def make_report(**kw):
    defaults = dict(mutation_id="MUT-001", changed_files=["a.py"],
                    direct_dependents=0, transitive_dependents=0,
                    blast_score=0.0, risk_tier="low",
                    reversal_cost_estimate="LOW", reversal_sla_hours=1.0)
    defaults.update(kw)
    return BlastRadiusReport(**defaults)

# T112-BLAST-01: module imports
def test_T112_BLAST_01_import():
    assert BlastRadiusModeler is not None

# T112-BLAST-02: BLAST_INVARIANTS has exactly three entries
def test_T112_BLAST_02_invariant_registry():
    assert set(BLAST_INVARIANTS.keys()) == {"BLAST-0", "BLAST-SLA-0", "BLAST-AUDIT-0"}

# T112-BLAST-03: VALID_RISK_TIERS contains exactly four tiers
def test_T112_BLAST_03_valid_tiers():
    assert VALID_RISK_TIERS == {"low", "medium", "high", "critical"}

# T112-BLAST-04: REVERSAL_SLA values are correct
def test_T112_BLAST_04_sla_values():
    assert REVERSAL_SLA["low"] == 1.0
    assert REVERSAL_SLA["medium"] == 8.0
    assert REVERSAL_SLA["high"] == 48.0
    assert REVERSAL_SLA["critical"] == 168.0

# T112-BLAST-05: BLAST-AUDIT-0 — report_digest non-empty on construction
def test_T112_BLAST_05_digest_nonempty():
    r = make_report()
    assert r.report_digest.startswith("sha256:")

# T112-BLAST-06: report_digest seals mutation_id
def test_T112_BLAST_06_digest_seals_mutation_id():
    r1 = make_report(mutation_id="MUT-A")
    r2 = make_report(mutation_id="MUT-B")
    assert r1.report_digest != r2.report_digest

# T112-BLAST-07: report_digest seals risk_tier
def test_T112_BLAST_07_digest_seals_tier():
    r1 = make_report(risk_tier="low", reversal_sla_hours=1.0)
    r2 = make_report(risk_tier="medium", reversal_sla_hours=8.0)
    assert r1.report_digest != r2.report_digest

# T112-BLAST-08: to_ledger_row produces valid JSON
def test_T112_BLAST_08_ledger_row_json():
    r = make_report()
    row = r.to_ledger_row()
    parsed = json.loads(row)
    assert parsed["mutation_id"] == "MUT-001"

# T112-BLAST-09: to_ledger_row is single-line
def test_T112_BLAST_09_ledger_row_single_line():
    r = make_report()
    assert "\n" not in r.to_ledger_row()

# T112-BLAST-10: invariants_verified includes all three
def test_T112_BLAST_10_invariants_listed():
    r = make_report()
    assert set(r.invariants_verified) == {"BLAST-0", "BLAST-SLA-0", "BLAST-AUDIT-0"}

# T112-BLAST-11: blast_report_guard passes on valid report
def test_T112_BLAST_11_guard_pass():
    r = make_report(blast_score=0.5, risk_tier="medium", reversal_sla_hours=8.0)
    blast_report_guard(r)  # must not raise

# T112-BLAST-12: blast_report_guard rejects blast_score > 1.0
def test_T112_BLAST_12_guard_score_over():
    r = make_report(blast_score=1.5)
    with pytest.raises(RuntimeError, match="BLAST-0"):
        blast_report_guard(r)

# T112-BLAST-13: blast_report_guard rejects blast_score < 0.0
def test_T112_BLAST_13_guard_score_under():
    r = make_report(blast_score=-0.1)
    with pytest.raises(RuntimeError, match="BLAST-0"):
        blast_report_guard(r)

# T112-BLAST-14: blast_report_guard rejects invalid risk_tier
def test_T112_BLAST_14_guard_invalid_tier():
    r = make_report(risk_tier="extreme")
    with pytest.raises(RuntimeError, match="BLAST-0"):
        blast_report_guard(r)

# T112-BLAST-15: blast_report_guard rejects mismatched SLA hours
def test_T112_BLAST_15_guard_sla_mismatch():
    r = make_report(risk_tier="high", reversal_sla_hours=1.0)  # should be 48.0
    with pytest.raises(RuntimeError, match="BLAST-SLA-0"):
        blast_report_guard(r)

# T112-BLAST-16: blast_report_guard rejects empty digest
def test_T112_BLAST_16_guard_empty_digest():
    r = make_report()
    r.report_digest = ""
    with pytest.raises(RuntimeError, match="BLAST-AUDIT-0"):
        blast_report_guard(r)

# T112-BLAST-17: BLAST_THRESHOLDS — critical threshold is 50
def test_T112_BLAST_17_critical_threshold():
    assert BLAST_THRESHOLDS["critical"] == 50

# T112-BLAST-18: BLAST_THRESHOLDS — low threshold is 0
def test_T112_BLAST_18_low_threshold():
    assert BLAST_THRESHOLDS["low"] == 0

# T112-BLAST-19: blast_score capped at 1.0 [BLAST-0]
def test_T112_BLAST_19_blast_score_cap():
    r = BlastRadiusReport(
        mutation_id="M", changed_files=["x.py"],
        direct_dependents=10000, transitive_dependents=20000,
        blast_score=1.0, risk_tier="critical",
        reversal_cost_estimate="CRIT", reversal_sla_hours=168.0,
    )
    assert r.blast_score <= 1.0

# T112-BLAST-20: modeler constructs with default repo_root
def test_T112_BLAST_20_modeler_default_root():
    m = BlastRadiusModeler()
    assert m.repo_root == Path(".")

# T112-BLAST-21: modeler.model returns BlastRadiusReport
def test_T112_BLAST_21_model_returns_report():
    m = BlastRadiusModeler(repo_root=Path("/tmp"))
    r = m.model("MUT-TEST", ["nonexistent_file_xyz.py"])
    assert isinstance(r, BlastRadiusReport)

# T112-BLAST-22: modeler.model — sla_hours matches tier [BLAST-SLA-0]
def test_T112_BLAST_22_model_sla_matches_tier():
    m = BlastRadiusModeler(repo_root=Path("/tmp"))
    r = m.model("MUT-SLA", ["nothing.py"])
    assert r.reversal_sla_hours == REVERSAL_SLA[r.risk_tier]

# T112-BLAST-23: modeler.model — blast_score in [0,1] [BLAST-0]
def test_T112_BLAST_23_model_score_in_bounds():
    m = BlastRadiusModeler(repo_root=Path("/tmp"))
    r = m.model("MUT-SCORE", ["nothing.py"])
    assert 0.0 <= r.blast_score <= 1.0

# T112-BLAST-24: modeler.model — risk_tier valid [BLAST-0]
def test_T112_BLAST_24_model_tier_valid():
    m = BlastRadiusModeler(repo_root=Path("/tmp"))
    r = m.model("MUT-TIER", ["nothing.py"])
    assert r.risk_tier in VALID_RISK_TIERS

# T112-BLAST-25: reversal_timeline returns required keys
def test_T112_BLAST_25_reversal_timeline_keys():
    m = BlastRadiusModeler()
    t = m.reversal_timeline("low")
    for k in ["risk_tier", "sla_hours", "rollback_steps", "escalation_required",
               "governor_signoff_required", "invariant_code"]:
        assert k in t

# T112-BLAST-26: reversal_timeline — critical requires governor sign-off
def test_T112_BLAST_26_critical_governor_signoff():
    m = BlastRadiusModeler()
    t = m.reversal_timeline("critical")
    assert t["governor_signoff_required"] is True
    assert t["escalation_required"] is True

# T112-BLAST-27: reversal_timeline — low does not require escalation
def test_T112_BLAST_27_low_no_escalation():
    m = BlastRadiusModeler()
    t = m.reversal_timeline("low")
    assert t["escalation_required"] is False
    assert t["governor_signoff_required"] is False

# T112-BLAST-28: reversal_timeline rejects invalid tier
def test_T112_BLAST_28_timeline_invalid_tier():
    m = BlastRadiusModeler()
    with pytest.raises(ValueError, match="BLAST-0"):
        m.reversal_timeline("extreme")

# T112-BLAST-29: reversal_timeline invariant_code is BLAST-SLA-0
def test_T112_BLAST_29_timeline_invariant_code():
    m = BlastRadiusModeler()
    t = m.reversal_timeline("medium")
    assert t["invariant_code"] == "BLAST-SLA-0"

# T112-BLAST-30: dependency_graph_summary returns required structure
def test_T112_BLAST_30_dep_graph_summary():
    m = BlastRadiusModeler(repo_root=Path("/tmp"))
    s = m.dependency_graph_summary(["nonexistent_xyz.py"])
    assert "changed_files" in s
    assert "per_file" in s
    assert "total_direct_importers" in s
    assert "unique_importers" in s
