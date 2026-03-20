# SPDX-License-Identifier: Apache-2.0
"""Phase 81 — Constitutional Self-Discovery Loop Tests.

Tests ID convention: T81-CSDL-NN

Invariants under test:
  CSDL-0                  No candidate enters constitution.yaml without HUMAN-0.
  CSDL-0-AGENT            Agent generates; governor patches.
  CSDL-CLUSTER-0          Clustering is deterministic.
  CSDL-CANDIDATE-0        Candidate IDs are stable and deterministic.
  CSDL-CANDIDATE-ADVISORY-0  All candidates are disabled until ratified.
  CSDL-CANDIDATE-DEDUP-0  Same cluster → same candidate_id.
  CSDL-MIN-FREQ-0         Only clusters meeting threshold are proposed.
  CSDL-IMMUTABLE-0        Mining is read-only.
  CSDL-AUDIT-0            Every decision produces a RatificationRecord.
  CSDL-REPLAY-0           Records are replayable from their digest.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
from typing import Any, Dict, List

import pytest

from runtime.evolution.failure_pattern_miner import (
    FailurePatternMiner,
    FailureCluster,
    RejectionRecord,
    MIN_CLUSTER_FREQUENCY,
    _cluster_id,
    _jaccard,
)
from runtime.evolution.invariant_candidate_proposer import (
    InvariantCandidateProposer,
    InvariantCandidate,
    _candidate_id,
    _severity_for_frequency,
)
from runtime.evolution.invariant_ratification_gate import (
    InvariantRatificationGate,
    RatificationRecord,
    RatificationPackage,
    VALID_VERDICTS,
)
from runtime.evolution.constitutional_self_discovery import (
    ConstitutionalSelfDiscoveryLoop,
    DiscoveryRunResult,
)

pytestmark = pytest.mark.phase81


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _rejection(
    mutation_id: str = "m-001",
    failed_rules: List[str] = None,
    reason_codes: List[str] = None,
    sequence: int = 1,
) -> Dict[str, Any]:
    return {
        "approved": False,
        "decision": "deny",
        "mutation_id": mutation_id,
        "failed_rules": failed_rules or ["AST-SAFE-0"],
        "reason_codes": reason_codes or ["syntax_error"],
        "gate_mode": "serial",
        "trust_mode": "standard",
        "sequence": sequence,
    }


def _approval(mutation_id: str = "m-ok", sequence: int = 100) -> Dict[str, Any]:
    return {
        "approved": True,
        "decision": "pass",
        "mutation_id": mutation_id,
        "failed_rules": [],
        "reason_codes": [],
        "gate_mode": "serial",
        "trust_mode": "standard",
        "sequence": sequence,
    }


def _make_records(rule: str = "AST-SAFE-0", count: int = 5) -> List[Dict[str, Any]]:
    return [_rejection(f"m-{i:03d}", [rule], sequence=i) for i in range(count)]


def _make_cluster(
    failed_rules=("AST-SAFE-0",), frequency=5
) -> FailureCluster:
    key = "|".join(sorted(failed_rules))
    cid = _cluster_id(key)
    from runtime.evolution.failure_pattern_miner import _cluster_digest
    return FailureCluster(
        cluster_id=cid,
        rule_set_key=key,
        failed_rules=tuple(sorted(failed_rules)),
        reason_codes=("syntax_error",),
        frequency=frequency,
        example_mutation_ids=("m-001",),
        gate_mode_counts={"serial": frequency},
        trust_mode_counts={"standard": frequency},
        cluster_digest=_cluster_digest(cid, frequency),
    )


def _make_candidate(failed_rules=("AST-SAFE-0",), frequency=5) -> InvariantCandidate:
    cluster = _make_cluster(failed_rules, frequency)
    proposer = InvariantCandidateProposer()
    return proposer.propose([cluster])[0]


# ---------------------------------------------------------------------------
# T81-CSDL-01: RejectionRecord.from_raw filters out approvals
# ---------------------------------------------------------------------------


def test_T81_CSDL_01_rejection_record_filters_approvals():
    """T81-CSDL-01: CSDL-IMMUTABLE-0 — from_raw returns None for approved records."""
    assert RejectionRecord.from_raw(_approval()) is None


# ---------------------------------------------------------------------------
# T81-CSDL-02: RejectionRecord.from_raw parses rejections correctly
# ---------------------------------------------------------------------------


def test_T81_CSDL_02_rejection_record_parse():
    """T81-CSDL-02: RejectionRecord parses failed_rules and reason_codes correctly."""
    raw = _rejection("m-1", ["AST-SAFE-0", "IMPORT-0"], ["syntax_error", "banned_import"])
    rec = RejectionRecord.from_raw(raw)
    assert rec is not None
    assert rec.mutation_id == "m-1"
    assert rec.failed_rules == ("AST-SAFE-0", "IMPORT-0")  # sorted
    assert "syntax_error" in rec.reason_codes


# ---------------------------------------------------------------------------
# T81-CSDL-03: RejectionRecord.failed_rules are always sorted (CSDL-CLUSTER-0)
# ---------------------------------------------------------------------------


def test_T81_CSDL_03_failed_rules_sorted_determinism():
    """T81-CSDL-03: CSDL-CLUSTER-0 — failed_rules sorted regardless of input order."""
    r1 = RejectionRecord.from_raw(_rejection(failed_rules=["B-RULE", "A-RULE"]))
    r2 = RejectionRecord.from_raw(_rejection(failed_rules=["A-RULE", "B-RULE"]))
    assert r1.failed_rules == r2.failed_rules == ("A-RULE", "B-RULE")


# ---------------------------------------------------------------------------
# T81-CSDL-04: FailurePatternMiner.mine returns empty on no rejections
# ---------------------------------------------------------------------------


def test_T81_CSDL_04_mine_empty_on_no_rejections():
    """T81-CSDL-04: mine() returns [] when only approvals are present."""
    records = [_approval() for _ in range(10)]
    miner = FailurePatternMiner()
    assert miner.mine(records) == []


# ---------------------------------------------------------------------------
# T81-CSDL-05: CSDL-MIN-FREQ-0 — clusters below threshold suppressed
# ---------------------------------------------------------------------------


def test_T81_CSDL_05_min_frequency_enforced():
    """T81-CSDL-05: CSDL-MIN-FREQ-0 — clusters below min_frequency not emitted."""
    records = _make_records(count=2)  # below default MIN_CLUSTER_FREQUENCY=3
    miner = FailurePatternMiner(min_frequency=3)
    assert miner.mine(records) == []


# ---------------------------------------------------------------------------
# T81-CSDL-06: CSDL-MIN-FREQ-0 — clusters at threshold are emitted
# ---------------------------------------------------------------------------


def test_T81_CSDL_06_min_frequency_at_threshold_emitted():
    """T81-CSDL-06: CSDL-MIN-FREQ-0 — clusters at exactly min_frequency are included."""
    records = _make_records(count=3)
    miner = FailurePatternMiner(min_frequency=3)
    clusters = miner.mine(records)
    assert len(clusters) == 1
    assert clusters[0].frequency == 3


# ---------------------------------------------------------------------------
# T81-CSDL-07: CSDL-CLUSTER-0 — identical inputs → identical clusters
# ---------------------------------------------------------------------------


def test_T81_CSDL_07_cluster_determinism():
    """T81-CSDL-07: CSDL-CLUSTER-0 — mine() is deterministic for identical inputs."""
    records = _make_records(count=5)
    miner = FailurePatternMiner(min_frequency=3)
    r1 = miner.mine(records)
    r2 = miner.mine(records)
    assert [c.cluster_id for c in r1] == [c.cluster_id for c in r2]
    assert [c.cluster_digest for c in r1] == [c.cluster_digest for c in r2]


# ---------------------------------------------------------------------------
# T81-CSDL-08: Cluster groups by rule_set_key
# ---------------------------------------------------------------------------


def test_T81_CSDL_08_clusters_group_by_rule_set():
    """T81-CSDL-08: Different rule sets produce different clusters."""
    records = (
        _make_records("AST-SAFE-0", count=4)
        + _make_records("IMPORT-0", count=4)
    )
    miner = FailurePatternMiner(min_frequency=3)
    clusters = miner.mine(records)
    rule_sets = {c.rule_set_key for c in clusters}
    assert len(rule_sets) == 2


# ---------------------------------------------------------------------------
# T81-CSDL-09: FailureCluster round-trip serialisation
# ---------------------------------------------------------------------------


def test_T81_CSDL_09_cluster_roundtrip():
    """T81-CSDL-09: FailureCluster to_dict / from_dict round-trip."""
    cluster = _make_cluster(frequency=7)
    d = cluster.to_dict()
    cluster2 = FailureCluster.from_dict(d)
    assert cluster == cluster2


# ---------------------------------------------------------------------------
# T81-CSDL-10: CSDL-CANDIDATE-0 — candidate_id is deterministic from cluster_id
# ---------------------------------------------------------------------------


def test_T81_CSDL_10_candidate_id_determinism():
    """T81-CSDL-10: CSDL-CANDIDATE-0 — same cluster → same candidate_id."""
    cluster = _make_cluster(frequency=5)
    c1 = _candidate_id(cluster.cluster_id)
    c2 = _candidate_id(cluster.cluster_id)
    assert c1 == c2
    assert c1.startswith("CSDL-CAND-")


# ---------------------------------------------------------------------------
# T81-CSDL-11: CSDL-CANDIDATE-DEDUP-0 — same cluster produces same candidate
# ---------------------------------------------------------------------------


def test_T81_CSDL_11_candidate_dedup():
    """T81-CSDL-11: CSDL-CANDIDATE-DEDUP-0 — proposing same cluster twice = same id."""
    cluster = _make_cluster(frequency=5)
    proposer = InvariantCandidateProposer()
    c1 = proposer.propose([cluster])[0]
    c2 = proposer.propose([cluster])[0]
    assert c1.candidate_id == c2.candidate_id
    assert c1.invariant_id == c2.invariant_id


# ---------------------------------------------------------------------------
# T81-CSDL-12: CSDL-CANDIDATE-ADVISORY-0 — all candidates are disabled
# ---------------------------------------------------------------------------


def test_T81_CSDL_12_candidate_always_disabled():
    """T81-CSDL-12: CSDL-CANDIDATE-ADVISORY-0 — constitution_entry.enabled is False."""
    candidate = _make_candidate(frequency=100)  # even high-freq: still disabled
    assert candidate.constitution_entry["enabled"] is False


# ---------------------------------------------------------------------------
# T81-CSDL-13: severity escalates with frequency
# ---------------------------------------------------------------------------


def test_T81_CSDL_13_severity_escalation():
    """T81-CSDL-13: higher frequency clusters get escalated severity."""
    assert _severity_for_frequency(60) == "blocking"
    assert _severity_for_frequency(25) == "warning"
    assert _severity_for_frequency(1) == "advisory"


# ---------------------------------------------------------------------------
# T81-CSDL-14: InvariantCandidate round-trip serialisation
# ---------------------------------------------------------------------------


def test_T81_CSDL_14_candidate_roundtrip():
    """T81-CSDL-14: InvariantCandidate to_dict / from_dict round-trip."""
    candidate = _make_candidate(frequency=6)
    d = candidate.to_dict()
    c2 = InvariantCandidate.from_dict(d)
    assert candidate == c2


# ---------------------------------------------------------------------------
# T81-CSDL-15: CSDL-0 — RatificationGate present() always produces defer
# ---------------------------------------------------------------------------


def test_T81_CSDL_15_gate_present_always_defers():
    """T81-CSDL-15: CSDL-0 — present() never approves without explicit ratify()."""
    candidate = _make_candidate(frequency=100)  # even high-freq
    gate = InvariantRatificationGate()
    pkg = gate.present(candidate)
    assert pkg.record.verdict == "defer"
    assert pkg.yaml_patch is None


# ---------------------------------------------------------------------------
# T81-CSDL-16: CSDL-0 — approved verdict produces yaml_patch
# ---------------------------------------------------------------------------


def test_T81_CSDL_16_approved_verdict_produces_patch():
    """T81-CSDL-16: CSDL-0 — ratify approve produces yaml_patch."""
    candidate = _make_candidate(frequency=5)
    gate = InvariantRatificationGate(governor="Test Governor")
    pkg = gate.ratify(candidate, verdict="approve", rationale="Test approval")
    assert pkg.record.verdict == "approve"
    assert pkg.yaml_patch is not None
    assert pkg.yaml_patch["enabled"] is True  # approval activates the rule
    assert pkg.yaml_patch["name"] == candidate.name


# ---------------------------------------------------------------------------
# T81-CSDL-17: CSDL-0 — rejected verdict produces no yaml_patch
# ---------------------------------------------------------------------------


def test_T81_CSDL_17_rejected_verdict_no_patch():
    """T81-CSDL-17: CSDL-0 — reject verdict produces no yaml_patch."""
    candidate = _make_candidate()
    gate = InvariantRatificationGate()
    pkg = gate.ratify(candidate, verdict="reject", rationale="Not needed")
    assert pkg.record.verdict == "reject"
    assert pkg.yaml_patch is None


# ---------------------------------------------------------------------------
# T81-CSDL-18: CSDL-AUDIT-0 — every decision produces a RatificationRecord
# ---------------------------------------------------------------------------


def test_T81_CSDL_18_every_decision_produces_record():
    """T81-CSDL-18: CSDL-AUDIT-0 — all verdicts produce a RatificationRecord."""
    candidate = _make_candidate()
    gate = InvariantRatificationGate()
    for verdict in VALID_VERDICTS:
        pkg = gate.ratify(candidate, verdict=verdict)
        assert isinstance(pkg.record, RatificationRecord)
        assert pkg.record.verdict == verdict
        assert pkg.record.candidate_id == candidate.candidate_id


# ---------------------------------------------------------------------------
# T81-CSDL-19: CSDL-AUDIT-0 — invalid verdict raises ValueError
# ---------------------------------------------------------------------------


def test_T81_CSDL_19_invalid_verdict_raises():
    """T81-CSDL-19: CSDL-0 — invalid verdict raises ValueError."""
    candidate = _make_candidate()
    gate = InvariantRatificationGate()
    with pytest.raises(ValueError, match="CSDL-0"):
        gate.ratify(candidate, verdict="auto_approve")


# ---------------------------------------------------------------------------
# T81-CSDL-20: CSDL-REPLAY-0 — record has evidence_digest
# ---------------------------------------------------------------------------


def test_T81_CSDL_20_record_has_evidence_digest():
    """T81-CSDL-20: CSDL-REPLAY-0 — every RatificationRecord has evidence_digest."""
    candidate = _make_candidate()
    gate = InvariantRatificationGate()
    pkg = gate.ratify(candidate, verdict="defer")
    assert pkg.record.evidence_digest.startswith("sha256:")
    assert len(pkg.record.evidence_digest) > 10


# ---------------------------------------------------------------------------
# T81-CSDL-21: RatificationRecord round-trip serialisation
# ---------------------------------------------------------------------------


def test_T81_CSDL_21_ratification_record_roundtrip():
    """T81-CSDL-21: RatificationRecord to_dict / from_dict round-trip."""
    candidate = _make_candidate()
    gate = InvariantRatificationGate(governor="Test Gov")
    pkg = gate.ratify(candidate, verdict="approve", rationale="Good")
    d = pkg.record.to_dict()
    rec2 = RatificationRecord.from_dict(d)
    assert pkg.record == rec2


# ---------------------------------------------------------------------------
# T81-CSDL-22: Full CSDL run returns DiscoveryRunResult
# ---------------------------------------------------------------------------


def test_T81_CSDL_22_full_run_returns_result():
    """T81-CSDL-22: ConstitutionalSelfDiscoveryLoop.run() returns DiscoveryRunResult."""
    records = _make_records(count=5)
    csdl = ConstitutionalSelfDiscoveryLoop(min_cluster_frequency=3)
    result = csdl.run_with_injected_records(records)
    assert isinstance(result, DiscoveryRunResult)
    assert result.clusters_found >= 1
    assert result.candidates_proposed >= 1
    assert result.phase == 81


# ---------------------------------------------------------------------------
# T81-CSDL-23: Full run: all packages deferred (CSDL-0)
# ---------------------------------------------------------------------------


def test_T81_CSDL_23_full_run_all_deferred():
    """T81-CSDL-23: CSDL-0 — all packages in a run are deferred, none auto-approved."""
    records = _make_records(count=10)
    csdl = ConstitutionalSelfDiscoveryLoop(min_cluster_frequency=3)
    result = csdl.run_with_injected_records(records)
    assert result.approved_count == 0
    assert result.deferred_count == result.candidates_proposed


# ---------------------------------------------------------------------------
# T81-CSDL-24: Full run: run_digest changes when records change
# ---------------------------------------------------------------------------


def test_T81_CSDL_24_run_digest_changes_with_records():
    """T81-CSDL-24: run_digest is sensitive to input changes."""
    r1 = _make_records("AST-SAFE-0", count=5)
    r2 = _make_records("IMPORT-0", count=5)
    csdl = ConstitutionalSelfDiscoveryLoop(min_cluster_frequency=3)
    result1 = csdl.run_with_injected_records(r1)
    result2 = csdl.run_with_injected_records(r2)
    assert result1.run_digest != result2.run_digest


# ---------------------------------------------------------------------------
# T81-CSDL-25: Full run: preview_text is non-empty
# ---------------------------------------------------------------------------


def test_T81_CSDL_25_preview_text_non_empty():
    """T81-CSDL-25: preview_text is non-empty and contains candidate info."""
    records = _make_records(count=5)
    csdl = ConstitutionalSelfDiscoveryLoop(min_cluster_frequency=3)
    result = csdl.run_with_injected_records(records)
    assert len(result.preview_text) > 50
    assert "CSDL" in result.preview_text


# ---------------------------------------------------------------------------
# T81-CSDL-26: CSDL-IMMUTABLE-0 — mine() on non-existent ledger returns []
# ---------------------------------------------------------------------------


def test_T81_CSDL_26_mine_missing_ledger_returns_empty():
    """T81-CSDL-26: CSDL-IMMUTABLE-0 — missing ledger path returns empty, no error."""
    miner = FailurePatternMiner(
        ledger_path=pathlib.Path("/tmp/nonexistent_adaad_ledger_xyz.jsonl"),
        min_frequency=1,
    )
    assert miner.mine() == []


# ---------------------------------------------------------------------------
# T81-CSDL-27: CSDL-IMMUTABLE-0 — mine() with real file, read-only
# ---------------------------------------------------------------------------


def test_T81_CSDL_27_mine_reads_from_file():
    """T81-CSDL-27: CSDL-IMMUTABLE-0 — mine() reads ledger without modifying it."""
    with tempfile.TemporaryDirectory() as td:
        path = pathlib.Path(td) / "ledger.jsonl"
        records = _make_records(count=5)
        path.write_text("\n".join(json.dumps(r) for r in records))
        size_before = path.stat().st_size
        miner = FailurePatternMiner(ledger_path=path, min_frequency=3)
        clusters = miner.mine()
        size_after = path.stat().st_size
        assert size_before == size_after  # not modified
        assert len(clusters) >= 1


# ---------------------------------------------------------------------------
# T81-CSDL-28: Jaccard similarity helper is correct
# ---------------------------------------------------------------------------


def test_T81_CSDL_28_jaccard_helper():
    """T81-CSDL-28: _jaccard produces correct similarity scores."""
    a = frozenset(["A", "B", "C"])
    b = frozenset(["B", "C", "D"])
    assert abs(_jaccard(a, b) - 0.5) < 0.01
    assert _jaccard(frozenset(), frozenset()) == 1.0
    assert _jaccard(a, a) == 1.0
    assert _jaccard(a, frozenset(["X", "Y"])) == 0.0


# ---------------------------------------------------------------------------
# T81-CSDL-29: artifact dir write for approve verdict
# ---------------------------------------------------------------------------


def test_T81_CSDL_29_artifact_dir_written_on_approve():
    """T81-CSDL-29: CSDL-AUDIT-0 — approval artifact written to artifact_dir."""
    with tempfile.TemporaryDirectory() as td:
        art_dir = pathlib.Path(td) / "artifacts"
        candidate = _make_candidate(frequency=5)
        gate = InvariantRatificationGate(governor="Test Gov", artifact_dir=art_dir)
        gate.ratify(candidate, verdict="approve", rationale="OK")
        artifacts = list(art_dir.glob("ratification_*.json"))
        assert len(artifacts) == 1
        content = json.loads(artifacts[0].read_text())
        assert content["record"]["verdict"] == "approve"


# ---------------------------------------------------------------------------
# T81-CSDL-30: end-to-end: mine → propose → ratify → patch
# ---------------------------------------------------------------------------


def test_T81_CSDL_30_end_to_end_mine_propose_ratify_patch():
    """T81-CSDL-30: Full pipeline: records → cluster → candidate → approved patch."""
    records = _make_records("AST-SAFE-0", count=6)
    miner = FailurePatternMiner(min_frequency=3)
    proposer = InvariantCandidateProposer()
    gate = InvariantRatificationGate(governor="Dustin L. Reid")

    clusters = miner.mine(records)
    assert len(clusters) >= 1

    candidates = proposer.propose(clusters)
    assert len(candidates) >= 1

    candidate = candidates[0]
    # CSDL-CANDIDATE-ADVISORY-0: disabled until ratified
    assert candidate.constitution_entry["enabled"] is False

    pkg = gate.ratify(candidate, verdict="approve", rationale="End-to-end test")
    # CSDL-0: patch is produced and activation flips enabled=True
    assert pkg.yaml_patch is not None
    assert pkg.yaml_patch["enabled"] is True
    assert pkg.yaml_patch["name"] == candidate.name
    # CSDL-0-AGENT: instructions exist but are not auto-applied
    assert "constitution.yaml" in pkg.yaml_patch_instructions
    assert pkg.record.governor == "Dustin L. Reid"
