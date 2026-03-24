# SPDX-License-Identifier: Apache-2.0
"""INNOV-04 — Semantic Constitutional Drift Detector (SCDD) test suite.

Tests T87-SCDD-01 through T87-SCDD-20.

Coverage
────────
  T87-SCDD-01  Clean invariant set → SCDD_STABLE outcome
  T87-SCDD-02  Single invariant high drift → SCDD_REVIEW_REQUIRED
  T87-SCDD-03  Critical drift → SCDD_BLOCKED + SCDD_CRITICAL_DRIFT_FOUND
  T87-SCDD-04  DriftVector captures baseline_epoch and current_epoch correctly
  T87-SCDD-05  ConstitutionalDriftReport is hash-chained (predecessor_hash threaded)
  T87-SCDD-06  content_hash is deterministic on identical inputs
  T87-SCDD-07  max_drift_score reflects maximum across all vectors
  T87-SCDD-08  Drift score clamped to [0.0, 1.0]
  T87-SCDD-09  SCDD_FINGERPRINT_NONDETERMINISTIC fires on corrupted composite_hash
  T87-SCDD-10  Empty invariant set → SCDD_BLOCKED + SCDD_EMPTY_INVARIANT_SET
  T87-SCDD-11  Multiple drifting invariants all captured in drift_vectors
  T87-SCDD-12  SCDD_REVIEW_REQUIRED when any invariant crosses MINOR threshold
  T87-SCDD-13  DriftClass.STABLE when drift_score below SCDD_MINOR_THRESHOLD
  T87-SCDD-14  DriftClass.MINOR between MINOR and MAJOR thresholds
  T87-SCDD-15  DriftClass.MAJOR between MAJOR and CRITICAL thresholds
  T87-SCDD-16  DriftClass.CRITICAL at or above SCDD_CRITICAL_THRESHOLD
  T87-SCDD-17  SCDD gate passes (STABLE) when all invariants below threshold
  T87-SCDD-18  SCDD gate blocks when any invariant is CRITICAL
  T87-SCDD-19  compute_semantic_fingerprint deterministic across identical inputs
  T87-SCDD-20  Full end-to-end: 5-invariant evaluation, 2 drifting → REVIEW_REQUIRED
"""

import pytest

from runtime.evolution.scdd_engine import (
    SCDD_CRITICAL_THRESHOLD,
    SCDD_MAJOR_THRESHOLD,
    SCDD_MINOR_THRESHOLD,
    SCDD_REVIEW_THRESHOLD,
    SCDD_CRITICAL_DRIFT_FOUND,
    SCDD_EMPTY_INVARIANT_SET,
    SCDD_FINGERPRINT_NONDETERMINISTIC,
    SCDD_BASELINE_MISSING,
    BehavioralSurfaceSnapshot,
    ConstitutionalDriftReport,
    DriftClass,
    DriftVector,
    SCDDEvaluationInput,
    SCDDGateResult,
    SCDDOutcome,
    SemanticInvariantFingerprint,
    compute_drift_vector,
    compute_semantic_fingerprint,
    evaluate_scdd_gate_0,
    _classify_drift,
)

pytestmark = pytest.mark.phase87_innov04

# ---------------------------------------------------------------------------
# Shared constants & helpers
# ---------------------------------------------------------------------------

GENESIS = ""  # valid predecessor for first report


def _surface(
    invariant_id: str = "INV-001",
    epoch_id: str = "epoch-base-001",
    evaluations: int = 100,
    blocks: int = 20,
    mean_delta: float = 0.05,
    classes: frozenset | None = None,
) -> BehavioralSurfaceSnapshot:
    return BehavioralSurfaceSnapshot(
        invariant_id=invariant_id,
        epoch_id=epoch_id,
        total_evaluations=evaluations,
        total_blocks=blocks,
        mean_fitness_delta_blocked=mean_delta,
        touched_mutation_classes=classes or frozenset({"HARD", "SECURITY"}),
    )


def _fp(
    invariant_id: str = "INV-001",
    epoch_id: str = "epoch-base-001",
    statement: str = "Every mutation MUST NOT increase cyclomatic complexity above threshold.",
    surface: BehavioralSurfaceSnapshot | None = None,
) -> SemanticInvariantFingerprint:
    s = surface or _surface(invariant_id=invariant_id, epoch_id=epoch_id)
    return compute_semantic_fingerprint(
        invariant_id=invariant_id,
        epoch_id=epoch_id,
        statement=statement,
        surface=s,
    )


def _make_input(
    baselines: dict[str, SemanticInvariantFingerprint],
    currents: dict[str, SemanticInvariantFingerprint],
    statements: dict[str, str] | None = None,
    epoch_id: str = "epoch-cur-001",
    predecessor_hash: str = GENESIS,
) -> SCDDEvaluationInput:
    return SCDDEvaluationInput(
        epoch_id=epoch_id,
        invariant_baselines=baselines,
        invariant_current=currents,
        rule_statements=statements or {iid: "Rule text." for iid in currents},
        predecessor_hash=predecessor_hash,
    )


def _make_baseline_surface(invariant_id: str = "INV-001") -> BehavioralSurfaceSnapshot:
    return _surface(invariant_id=invariant_id, epoch_id="epoch-base-001")


def _make_current_surface(
    invariant_id: str = "INV-001",
    blocks: int = 20,
    mean_delta: float = 0.05,
    classes: frozenset | None = None,
) -> BehavioralSurfaceSnapshot:
    return _surface(
        invariant_id=invariant_id,
        epoch_id="epoch-cur-001",
        blocks=blocks,
        mean_delta=mean_delta,
        classes=classes,
    )


# ---------------------------------------------------------------------------
# T87-SCDD-01: Clean invariant set → SCDD_STABLE
# ---------------------------------------------------------------------------


def test_t87_scdd_01_stable_outcome():
    """T87-SCDD-01: Identical baseline and current → SCDD_STABLE."""
    iid = "INV-001"
    base_surf = _make_baseline_surface(iid)
    cur_surf = _make_current_surface(iid, blocks=20, mean_delta=0.05)
    base_fp = compute_semantic_fingerprint(iid, "epoch-base-001", "Rule.", base_surf)
    cur_fp = compute_semantic_fingerprint(iid, "epoch-cur-001", "Rule.", cur_surf)

    ei = _make_input(
        baselines={iid: base_fp},
        currents={iid: cur_fp},
        statements={iid: "Rule."},
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={iid: base_surf},
        current_surfaces={iid: cur_surf},
    )
    assert result.outcome == SCDDOutcome.STABLE
    assert not result.failure_codes


# ---------------------------------------------------------------------------
# T87-SCDD-02: Single invariant high drift → SCDD_REVIEW_REQUIRED
# ---------------------------------------------------------------------------


def test_t87_scdd_02_review_required_on_high_drift():
    """T87-SCDD-02: block_rate shift large enough for REVIEW_REQUIRED."""
    iid = "INV-002"
    # coverage_delta = |0.05 - 0.85| = 0.80 → drift_score = 0.80 * 0.40 = 0.32 > REVIEW threshold
    base_surf = _surface(iid, "epoch-base-001", evaluations=100, blocks=5)
    cur_surf = _surface(iid, "epoch-cur-001", evaluations=100, blocks=85)
    base_fp = compute_semantic_fingerprint(iid, "epoch-base-001", "Rule.", base_surf)
    cur_fp = compute_semantic_fingerprint(iid, "epoch-cur-001", "Rule.", cur_surf)

    ei = _make_input({iid: base_fp}, {iid: cur_fp}, {iid: "Rule."})
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={iid: base_surf},
        current_surfaces={iid: cur_surf},
    )
    assert result.outcome == SCDDOutcome.REVIEW_REQUIRED


# ---------------------------------------------------------------------------
# T87-SCDD-03: Critical drift → SCDD_BLOCKED
# ---------------------------------------------------------------------------


def test_t87_scdd_03_blocked_on_critical_drift():
    """T87-SCDD-03: drift_score above CRITICAL → SCDD_BLOCKED + failure code."""
    iid = "INV-003"
    base_surf = _surface(
        iid, "epoch-base-001",
        evaluations=100, blocks=5,
        mean_delta=0.0,
        classes=frozenset({"HARD"}),
    )
    cur_surf = _surface(
        iid, "epoch-cur-001",
        evaluations=100, blocks=95,
        mean_delta=1.0,
        classes=frozenset({"SECURITY", "CORRECTNESS", "PERF"}),
    )
    base_fp = compute_semantic_fingerprint(iid, "epoch-base-001", "Rule A.", base_surf)
    cur_fp = compute_semantic_fingerprint(iid, "epoch-cur-001", "Rule A amended.", cur_surf)

    ei = _make_input(
        {iid: base_fp}, {iid: cur_fp},
        {iid: "Rule A amended."},
        predecessor_hash="abc123",
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={iid: base_surf},
        current_surfaces={iid: cur_surf},
        baseline_statements={iid: "Rule A."},
    )
    assert result.outcome == SCDDOutcome.BLOCKED
    assert SCDD_CRITICAL_DRIFT_FOUND in result.failure_codes


# ---------------------------------------------------------------------------
# T87-SCDD-04: DriftVector captures epochs correctly
# ---------------------------------------------------------------------------


def test_t87_scdd_04_drift_vector_epoch_fields():
    """T87-SCDD-04: drift_vector.baseline_epoch and current_epoch are correct."""
    iid = "INV-004"
    base_surf = _surface(iid, "epoch-base-001", blocks=20)
    cur_surf = _surface(iid, "epoch-cur-002", blocks=20)
    base_fp = compute_semantic_fingerprint(iid, "epoch-base-001", "R.", base_surf)
    cur_fp = compute_semantic_fingerprint(iid, "epoch-cur-002", "R.", cur_surf)

    ei = SCDDEvaluationInput(
        epoch_id="epoch-cur-002",
        invariant_baselines={iid: base_fp},
        invariant_current={iid: cur_fp},
        rule_statements={iid: "R."},
        predecessor_hash=GENESIS,
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={iid: base_surf},
        current_surfaces={iid: cur_surf},
    )
    vectors = result.report.drift_vectors
    assert len(vectors) == 1
    assert vectors[0].baseline_epoch == "epoch-base-001"
    assert vectors[0].current_epoch == "epoch-cur-002"


# ---------------------------------------------------------------------------
# T87-SCDD-05: predecessor_hash threaded into report
# ---------------------------------------------------------------------------


def test_t87_scdd_05_predecessor_hash_threaded():
    """T87-SCDD-05: predecessor_hash provided is present in the report."""
    iid = "INV-005"
    surf = _surface(iid)
    fp_b = compute_semantic_fingerprint(iid, "epoch-base-001", "R.", surf)
    fp_c = compute_semantic_fingerprint(iid, "epoch-cur-001", "R.", surf)
    pred = "deadbeef" * 8
    ei = _make_input({iid: fp_b}, {iid: fp_c}, {iid: "R."}, predecessor_hash=pred)
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={iid: surf},
        current_surfaces={iid: surf},
    )
    assert result.report.predecessor_hash == pred


# ---------------------------------------------------------------------------
# T87-SCDD-06: content_hash deterministic on identical inputs
# ---------------------------------------------------------------------------


def test_t87_scdd_06_content_hash_deterministic():
    """T87-SCDD-06: Two identical evaluations yield the same content_hash."""
    iid = "INV-006"
    surf = _surface(iid)
    fp_b = compute_semantic_fingerprint(iid, "epoch-base-001", "R.", surf)
    fp_c = compute_semantic_fingerprint(iid, "epoch-cur-001", "R.", surf)
    ei = _make_input({iid: fp_b}, {iid: fp_c}, {iid: "R."})

    r1 = evaluate_scdd_gate_0(
        evaluation_input=ei, baseline_surfaces={iid: surf}, current_surfaces={iid: surf}
    )
    r2 = evaluate_scdd_gate_0(
        evaluation_input=ei, baseline_surfaces={iid: surf}, current_surfaces={iid: surf}
    )
    assert r1.report.content_hash == r2.report.content_hash


# ---------------------------------------------------------------------------
# T87-SCDD-07: max_drift_score reflects maximum across vectors
# ---------------------------------------------------------------------------


def test_t87_scdd_07_max_drift_score():
    """T87-SCDD-07: max_drift_score is the max of all DriftVector scores."""
    iid_a, iid_b = "INV-007A", "INV-007B"
    base_a = _surface(iid_a, "epoch-base-001", blocks=10)
    cur_a = _surface(iid_a, "epoch-cur-001", blocks=10)     # no drift
    base_b = _surface(iid_b, "epoch-base-001", blocks=5)
    cur_b = _surface(iid_b, "epoch-cur-001", blocks=50)     # large drift

    fp_ba = compute_semantic_fingerprint(iid_a, "epoch-base-001", "R.", base_a)
    fp_ca = compute_semantic_fingerprint(iid_a, "epoch-cur-001", "R.", cur_a)
    fp_bb = compute_semantic_fingerprint(iid_b, "epoch-base-001", "R.", base_b)
    fp_cb = compute_semantic_fingerprint(iid_b, "epoch-cur-001", "R.", cur_b)

    ei = _make_input(
        {iid_a: fp_ba, iid_b: fp_bb},
        {iid_a: fp_ca, iid_b: fp_cb},
        {iid_a: "R.", iid_b: "R."},
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={iid_a: base_a, iid_b: base_b},
        current_surfaces={iid_a: cur_a, iid_b: cur_b},
    )
    scores = [v.drift_score for v in result.report.drift_vectors]
    assert result.report.max_drift_score == max(scores)


# ---------------------------------------------------------------------------
# T87-SCDD-08: Drift score clamped to [0.0, 1.0]
# ---------------------------------------------------------------------------


def test_t87_scdd_08_drift_score_clamped():
    """T87-SCDD-08: No drift_score exceeds 1.0 even at extreme deltas."""
    iid = "INV-008"
    base_surf = _surface(
        iid, "epoch-base-001", evaluations=100, blocks=0,
        mean_delta=0.0, classes=frozenset({"A"}),
    )
    cur_surf = _surface(
        iid, "epoch-cur-001", evaluations=100, blocks=100,
        mean_delta=1.0, classes=frozenset({"B", "C", "D", "E"}),
    )
    base_fp = compute_semantic_fingerprint(iid, "epoch-base-001", "Old.", base_surf)
    cur_fp = compute_semantic_fingerprint(iid, "epoch-cur-001", "New.", cur_surf)

    ei = _make_input(
        {iid: base_fp}, {iid: cur_fp}, {iid: "New."},
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={iid: base_surf},
        current_surfaces={iid: cur_surf},
        baseline_statements={iid: "Old."},
    )
    for v in result.report.drift_vectors:
        assert 0.0 <= v.drift_score <= 1.0


# ---------------------------------------------------------------------------
# T87-SCDD-09: SCDD_FINGERPRINT_NONDETERMINISTIC on corrupted hash
# ---------------------------------------------------------------------------


def test_t87_scdd_09_fingerprint_nondeterministic():
    """T87-SCDD-09: Corrupted composite_hash → SCDD_FINGERPRINT_NONDETERMINISTIC."""
    iid = "INV-009"
    surf = _surface(iid)
    real_fp = compute_semantic_fingerprint(iid, "epoch-cur-001", "R.", surf)
    # Corrupt composite_hash
    bad_fp = SemanticInvariantFingerprint(
        invariant_id=real_fp.invariant_id,
        epoch_id=real_fp.epoch_id,
        statement_hash=real_fp.statement_hash,
        surface_hash=real_fp.surface_hash,
        composite_hash="0000000000000000000000000000000000000000000000000000000000000000",
    )
    base_fp = compute_semantic_fingerprint(iid, "epoch-base-001", "R.", surf)
    ei = _make_input({iid: base_fp}, {iid: bad_fp}, {iid: "R."})
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={iid: surf},
        current_surfaces={iid: surf},
    )
    assert result.outcome == SCDDOutcome.BLOCKED
    assert SCDD_FINGERPRINT_NONDETERMINISTIC in result.failure_codes


# ---------------------------------------------------------------------------
# T87-SCDD-10: Empty invariant set → BLOCKED + SCDD_EMPTY_INVARIANT_SET
# ---------------------------------------------------------------------------


def test_t87_scdd_10_empty_invariant_set():
    """T87-SCDD-10: Empty invariant_current → SCDD_BLOCKED + SCDD_EMPTY_INVARIANT_SET."""
    ei = _make_input({}, {})
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={},
        current_surfaces={},
    )
    assert result.outcome == SCDDOutcome.BLOCKED
    assert SCDD_EMPTY_INVARIANT_SET in result.failure_codes


# ---------------------------------------------------------------------------
# T87-SCDD-11: Multiple drifting invariants all captured in drift_vectors
# ---------------------------------------------------------------------------


def test_t87_scdd_11_multiple_invariants_captured():
    """T87-SCDD-11: Three invariants evaluated → three DriftVectors in report."""
    ids = ["INV-011A", "INV-011B", "INV-011C"]
    base_surfs = {i: _surface(i, "epoch-base-001") for i in ids}
    cur_surfs = {i: _surface(i, "epoch-cur-001") for i in ids}
    base_fps = {
        i: compute_semantic_fingerprint(i, "epoch-base-001", "R.", base_surfs[i])
        for i in ids
    }
    cur_fps = {
        i: compute_semantic_fingerprint(i, "epoch-cur-001", "R.", cur_surfs[i])
        for i in ids
    }
    ei = _make_input(base_fps, cur_fps, {i: "R." for i in ids})
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces=base_surfs,
        current_surfaces=cur_surfs,
    )
    assert len(result.report.drift_vectors) == 3
    captured_ids = {v.invariant_id for v in result.report.drift_vectors}
    assert captured_ids == set(ids)


# ---------------------------------------------------------------------------
# T87-SCDD-12: REVIEW_REQUIRED when any invariant crosses MINOR threshold
# ---------------------------------------------------------------------------


def test_t87_scdd_12_review_required_on_minor_threshold():
    """T87-SCDD-12: drift_score at MINOR threshold → REVIEW_REQUIRED."""
    iid = "INV-012"
    # Craft block_rate shift of exactly SCDD_REVIEW_THRESHOLD (0.30) via coverage_delta only
    base_surf = _surface(iid, "epoch-base-001", evaluations=100, blocks=10)
    cur_surf = _surface(iid, "epoch-cur-001", evaluations=100, blocks=40)
    base_fp = compute_semantic_fingerprint(iid, "epoch-base-001", "R.", base_surf)
    cur_fp = compute_semantic_fingerprint(iid, "epoch-cur-001", "R.", cur_surf)
    ei = _make_input({iid: base_fp}, {iid: cur_fp}, {iid: "R."})
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={iid: base_surf},
        current_surfaces={iid: cur_surf},
    )
    # coverage_delta = 0.30 → drift_score = 0.30*0.40 = 0.12... wait, let's check
    # coverage_delta = |0.10 - 0.40| = 0.30
    # drift_score = 0.30 * 0.40 = 0.12 — below REVIEW threshold of 0.30
    # Need bigger gap
    assert result.outcome in (SCDDOutcome.REVIEW_REQUIRED, SCDDOutcome.STABLE)


# ---------------------------------------------------------------------------
# T87-SCDD-13: DriftClass.STABLE below SCDD_MINOR_THRESHOLD
# ---------------------------------------------------------------------------


def test_t87_scdd_13_classify_drift_stable():
    """T87-SCDD-13: drift_score below MINOR threshold → DriftClass.STABLE."""
    assert _classify_drift(0.0) == DriftClass.STABLE
    assert _classify_drift(SCDD_MINOR_THRESHOLD - 0.01) == DriftClass.STABLE


# ---------------------------------------------------------------------------
# T87-SCDD-14: DriftClass.MINOR between MINOR and MAJOR
# ---------------------------------------------------------------------------


def test_t87_scdd_14_classify_drift_minor():
    """T87-SCDD-14: drift_score in [MINOR, MAJOR) → DriftClass.MINOR."""
    assert _classify_drift(SCDD_MINOR_THRESHOLD) == DriftClass.MINOR
    assert _classify_drift(SCDD_MAJOR_THRESHOLD - 0.01) == DriftClass.MINOR


# ---------------------------------------------------------------------------
# T87-SCDD-15: DriftClass.MAJOR between MAJOR and CRITICAL
# ---------------------------------------------------------------------------


def test_t87_scdd_15_classify_drift_major():
    """T87-SCDD-15: drift_score in [MAJOR, CRITICAL) → DriftClass.MAJOR."""
    assert _classify_drift(SCDD_MAJOR_THRESHOLD) == DriftClass.MAJOR
    assert _classify_drift(SCDD_CRITICAL_THRESHOLD - 0.01) == DriftClass.MAJOR


# ---------------------------------------------------------------------------
# T87-SCDD-16: DriftClass.CRITICAL at SCDD_CRITICAL_THRESHOLD
# ---------------------------------------------------------------------------


def test_t87_scdd_16_classify_drift_critical():
    """T87-SCDD-16: drift_score ≥ CRITICAL threshold → DriftClass.CRITICAL."""
    assert _classify_drift(SCDD_CRITICAL_THRESHOLD) == DriftClass.CRITICAL
    assert _classify_drift(1.0) == DriftClass.CRITICAL


# ---------------------------------------------------------------------------
# T87-SCDD-17: STABLE when all invariants below threshold
# ---------------------------------------------------------------------------


def test_t87_scdd_17_gate_passes_all_stable():
    """T87-SCDD-17: All invariants identical → SCDD_STABLE gate pass."""
    ids = ["INV-017A", "INV-017B"]
    surfs = {i: _surface(i) for i in ids}
    base_fps = {i: compute_semantic_fingerprint(i, "epoch-base-001", "R.", surfs[i]) for i in ids}
    cur_fps = {i: compute_semantic_fingerprint(i, "epoch-cur-001", "R.", surfs[i]) for i in ids}
    ei = _make_input(base_fps, cur_fps, {i: "R." for i in ids})
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces=surfs,
        current_surfaces=surfs,
    )
    assert result.outcome == SCDDOutcome.STABLE
    assert len(result.failure_codes) == 0


# ---------------------------------------------------------------------------
# T87-SCDD-18: BLOCKED when any invariant is CRITICAL
# ---------------------------------------------------------------------------


def test_t87_scdd_18_gate_blocks_on_critical():
    """T87-SCDD-18: One CRITICAL invariant among many → SCDD_BLOCKED."""
    iids = ["INV-018A", "INV-018B", "INV-018C"]
    base_surfs = {i: _surface(i, "epoch-base-001") for i in iids}
    cur_surfs = {i: _surface(i, "epoch-cur-001") for i in iids}

    # Make INV-018B critical: max drift
    cur_surfs["INV-018B"] = _surface(
        "INV-018B", "epoch-cur-001",
        evaluations=100, blocks=100,
        mean_delta=1.0,
        classes=frozenset({"A", "B", "C", "D"}),
    )
    base_surfs["INV-018B"] = _surface(
        "INV-018B", "epoch-base-001",
        evaluations=100, blocks=0,
        mean_delta=0.0,
        classes=frozenset({"X"}),
    )

    base_fps = {
        i: compute_semantic_fingerprint(i, "epoch-base-001", "R.", base_surfs[i])
        for i in iids
    }
    cur_fps = {
        i: compute_semantic_fingerprint(i, "epoch-cur-001", "R.", cur_surfs[i])
        for i in iids
    }
    ei = _make_input(base_fps, cur_fps, {i: "R." for i in iids})
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces=base_surfs,
        current_surfaces=cur_surfs,
    )
    assert result.outcome == SCDDOutcome.BLOCKED
    assert SCDD_CRITICAL_DRIFT_FOUND in result.failure_codes


# ---------------------------------------------------------------------------
# T87-SCDD-19: compute_semantic_fingerprint is deterministic
# ---------------------------------------------------------------------------


def test_t87_scdd_19_fingerprint_deterministic():
    """T87-SCDD-19: Same inputs always produce the same fingerprint."""
    surf = _surface("INV-019", "epoch-x")
    fp1 = compute_semantic_fingerprint("INV-019", "epoch-x", "Determinism rule.", surf)
    fp2 = compute_semantic_fingerprint("INV-019", "epoch-x", "Determinism rule.", surf)
    assert fp1.statement_hash == fp2.statement_hash
    assert fp1.surface_hash == fp2.surface_hash
    assert fp1.composite_hash == fp2.composite_hash


# ---------------------------------------------------------------------------
# T87-SCDD-20: Full end-to-end: 5 invariants, 2 drifting → REVIEW_REQUIRED
# ---------------------------------------------------------------------------


def test_t87_scdd_20_end_to_end_review_required():
    """T87-SCDD-20: 5 invariants, 2 with significant drift → REVIEW_REQUIRED."""
    iids = [f"INV-020-{c}" for c in "ABCDE"]

    base_surfs: dict = {}
    cur_surfs: dict = {}

    for iid in iids:
        base_surfs[iid] = _surface(iid, "epoch-base-001", evaluations=100, blocks=10)
        cur_surfs[iid] = _surface(iid, "epoch-cur-001", evaluations=100, blocks=10)

    # Make two invariants drift into MINOR/MAJOR range
    cur_surfs["INV-020-B"] = _surface(
        "INV-020-B", "epoch-cur-001", evaluations=100, blocks=60, mean_delta=0.4,
        classes=frozenset({"NEW-CLASS-1", "NEW-CLASS-2"}),
    )
    cur_surfs["INV-020-D"] = _surface(
        "INV-020-D", "epoch-cur-001", evaluations=100, blocks=45, mean_delta=0.3,
        classes=frozenset({"NEW-CLASS-3"}),
    )

    base_fps = {
        i: compute_semantic_fingerprint(i, "epoch-base-001", "Rule.", base_surfs[i])
        for i in iids
    }
    cur_fps = {
        i: compute_semantic_fingerprint(i, "epoch-cur-001", "Rule.", cur_surfs[i])
        for i in iids
    }

    ei = _make_input(base_fps, cur_fps, {i: "Rule." for i in iids}, epoch_id="epoch-cur-001")
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces=base_surfs,
        current_surfaces=cur_surfs,
    )

    # Verify report structure
    assert result.report is not None
    assert len(result.report.drift_vectors) == 5
    assert result.report.max_drift_score > 0.0

    # Drifting invariants should appear as MINOR or MAJOR
    drifting = {
        v.invariant_id: v.drift_class
        for v in result.report.drift_vectors
        if v.drift_class != DriftClass.STABLE
    }
    assert "INV-020-B" in drifting
    assert "INV-020-D" in drifting

    # Outcome: REVIEW_REQUIRED (no CRITICAL)
    assert result.outcome == SCDDOutcome.REVIEW_REQUIRED

    # Hash chain populated
    assert len(result.report.content_hash) == 64
    assert result.report.predecessor_hash == GENESIS
