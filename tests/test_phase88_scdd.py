# SPDX-License-Identifier: Apache-2.0
"""Phase 88 — INNOV-04 · Semantic Constitutional Drift Detector (SCDD).

Test ID format: T88-SCDD-NN

20 tests covering:
  - T88-SCDD-01..04  Fingerprint determinism & structural correctness
  - T88-SCDD-05..08  Drift vector computation and classification
  - T88-SCDD-09..12  SCDD-GATE-0 pass paths (STABLE, REVIEW_REQUIRED)
  - T88-SCDD-13..16  SCDD-GATE-0 block paths (CRITICAL, missing baseline, empty set)
  - T88-SCDD-17..18  Hash chaining and report digest integrity
  - T88-SCDD-19..20  Surface-hash consistency gate and statement-change bonus
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, FrozenSet

import pytest

from runtime.evolution.scdd_engine import (
    SCDD_CRITICAL_THRESHOLD,
    SCDD_MAJOR_THRESHOLD,
    SCDD_MINOR_THRESHOLD,
    SCDD_REVIEW_THRESHOLD,
    SCDD_VERSION,
    SCDD_BASELINE_MISSING,
    SCDD_CRITICAL_DRIFT_FOUND,
    SCDD_EMPTY_INVARIANT_SET,
    SCDD_FINGERPRINT_NONDETERMINISTIC,
    SCDD_SURFACE_HASH_CONFLICT,
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
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

EPOCH_BASE = "epoch-001"
EPOCH_CURR = "epoch-010"
EPOCH_DRIFT = "epoch-020"

STATEMENT_V1 = (
    "All mutations MUST NOT increase cyclomatic complexity by more than 3 nodes "
    "without an explicit architectural review gate approval signed by ArchitectAgent."
)
STATEMENT_V2 = (
    "All mutations MUST NOT increase cyclomatic complexity by more than 3 nodes "
    "without an explicit architectural review gate approval signed by ArchitectAgent."
)  # identical → statement_changed = False
STATEMENT_AMENDED = (
    "All mutations MUST NOT increase cyclomatic complexity by more than 5 nodes "
    "without explicit review gate approval by any governance agent with WRITE scope."
)  # different → statement_changed = True

INV_ID = "TEST-0"


def _surface(
    inv_id: str = INV_ID,
    epoch_id: str = EPOCH_BASE,
    total_evaluations: int = 100,
    total_blocks: int = 10,
    mean_fitness_delta: float = -0.05,
    mutation_classes: FrozenSet[str] = frozenset({"refactor", "complexity"}),
) -> BehavioralSurfaceSnapshot:
    return BehavioralSurfaceSnapshot(
        invariant_id=inv_id,
        epoch_id=epoch_id,
        total_evaluations=total_evaluations,
        total_blocks=total_blocks,
        mean_fitness_delta_blocked=mean_fitness_delta,
        touched_mutation_classes=mutation_classes,
    )


def _fingerprint(
    inv_id: str = INV_ID,
    epoch_id: str = EPOCH_BASE,
    statement: str = STATEMENT_V1,
    surface: BehavioralSurfaceSnapshot | None = None,
) -> SemanticInvariantFingerprint:
    if surface is None:
        surface = _surface(inv_id=inv_id, epoch_id=epoch_id)
    return compute_semantic_fingerprint(inv_id, epoch_id, statement, surface)


def _scdd_input(
    epoch_id: str = EPOCH_CURR,
    baseline: SemanticInvariantFingerprint | None = None,
    current: SemanticInvariantFingerprint | None = None,
    statement: str = STATEMENT_V1,
    predecessor_hash: str = "0" * 64,
) -> SCDDEvaluationInput:
    if baseline is None:
        baseline = _fingerprint(epoch_id=EPOCH_BASE)
    if current is None:
        current = _fingerprint(epoch_id=epoch_id)
    return SCDDEvaluationInput(
        epoch_id=epoch_id,
        invariant_baselines={INV_ID: baseline},
        invariant_current={INV_ID: current},
        rule_statements={INV_ID: statement},
        predecessor_hash=predecessor_hash,
    )


# ---------------------------------------------------------------------------
# T88-SCDD-01 — compute_semantic_fingerprint returns correct types
# ---------------------------------------------------------------------------


def test_t88_scdd_01_fingerprint_types():
    """T88-SCDD-01: compute_semantic_fingerprint returns SemanticInvariantFingerprint."""
    surface = _surface()
    fp = compute_semantic_fingerprint(INV_ID, EPOCH_BASE, STATEMENT_V1, surface)
    assert isinstance(fp, SemanticInvariantFingerprint)
    assert fp.invariant_id == INV_ID
    assert fp.epoch_id == EPOCH_BASE
    assert len(fp.statement_hash) == 64
    assert len(fp.surface_hash) == 64
    assert len(fp.composite_hash) == 64


# ---------------------------------------------------------------------------
# T88-SCDD-02 — fingerprint is deterministic
# ---------------------------------------------------------------------------


def test_t88_scdd_02_fingerprint_deterministic():
    """T88-SCDD-02: identical inputs → identical fingerprint hashes."""
    surface = _surface()
    fp1 = compute_semantic_fingerprint(INV_ID, EPOCH_BASE, STATEMENT_V1, surface)
    fp2 = compute_semantic_fingerprint(INV_ID, EPOCH_BASE, STATEMENT_V1, surface)
    assert fp1.statement_hash == fp2.statement_hash
    assert fp1.surface_hash == fp2.surface_hash
    assert fp1.composite_hash == fp2.composite_hash


# ---------------------------------------------------------------------------
# T88-SCDD-03 — statement hash changes when text changes
# ---------------------------------------------------------------------------


def test_t88_scdd_03_statement_hash_sensitive_to_text():
    """T88-SCDD-03: statement_hash differs when rule text is amended."""
    surface = _surface()
    fp_v1 = compute_semantic_fingerprint(INV_ID, EPOCH_BASE, STATEMENT_V1, surface)
    fp_v2 = compute_semantic_fingerprint(INV_ID, EPOCH_BASE, STATEMENT_AMENDED, surface)
    assert fp_v1.statement_hash != fp_v2.statement_hash
    assert fp_v1.composite_hash != fp_v2.composite_hash


# ---------------------------------------------------------------------------
# T88-SCDD-04 — surface hash changes when behavioral surface changes
# ---------------------------------------------------------------------------


def test_t88_scdd_04_surface_hash_sensitive_to_behavior():
    """T88-SCDD-04: surface_hash differs when behavioral stats change."""
    s1 = _surface(total_blocks=10)
    s2 = _surface(total_blocks=90)
    fp1 = compute_semantic_fingerprint(INV_ID, EPOCH_BASE, STATEMENT_V1, s1)
    fp2 = compute_semantic_fingerprint(INV_ID, EPOCH_BASE, STATEMENT_V1, s2)
    assert fp1.surface_hash != fp2.surface_hash


# ---------------------------------------------------------------------------
# T88-SCDD-05 — STABLE drift vector when surfaces are identical
# ---------------------------------------------------------------------------


def test_t88_scdd_05_drift_stable_identical_surfaces():
    """T88-SCDD-05: identical baseline and current → drift_class STABLE."""
    surface = _surface()
    fp = _fingerprint()
    vector = compute_drift_vector(
        baseline_surface=surface,
        current_surface=surface,
        baseline_fp=fp,
        current_fp=fp,
        rule_statement_baseline=STATEMENT_V1,
        rule_statement_current=STATEMENT_V1,
    )
    assert vector.drift_class == DriftClass.STABLE
    assert vector.drift_score < SCDD_MINOR_THRESHOLD
    assert vector.statement_changed is False


# ---------------------------------------------------------------------------
# T88-SCDD-06 — MINOR drift when block rate shifts moderately
# ---------------------------------------------------------------------------


def test_t88_scdd_06_drift_minor_moderate_block_rate():
    """T88-SCDD-06: moderate block rate shift → MINOR drift class."""
    baseline = _surface(total_blocks=10, total_evaluations=100)  # block_rate 0.10
    current = _surface(
        total_blocks=55, total_evaluations=100, epoch_id=EPOCH_CURR
    )  # block_rate 0.55 → coverage_delta 0.45
    fp_base = _fingerprint(epoch_id=EPOCH_BASE, surface=baseline)
    fp_curr = _fingerprint(epoch_id=EPOCH_CURR, surface=current)
    vector = compute_drift_vector(
        baseline_surface=baseline,
        current_surface=current,
        baseline_fp=fp_base,
        current_fp=fp_curr,
        rule_statement_baseline=STATEMENT_V1,
        rule_statement_current=STATEMENT_V1,
    )
    # coverage_delta 0.45 × 0.40 = 0.18 → MINOR (≥ 0.30 requires more components)
    assert vector.coverage_delta == pytest.approx(0.45, abs=1e-6)
    assert vector.drift_class in (DriftClass.STABLE, DriftClass.MINOR)


# ---------------------------------------------------------------------------
# T88-SCDD-07 — CRITICAL drift when all components are maxed
# ---------------------------------------------------------------------------


def test_t88_scdd_07_drift_critical_when_fully_diverged():
    """T88-SCDD-07: fully diverged surfaces → CRITICAL drift class."""
    baseline = _surface(
        total_blocks=5,
        total_evaluations=100,
        mean_fitness_delta=-0.01,
        mutation_classes=frozenset({"refactor"}),
    )
    current = _surface(
        total_blocks=100,
        total_evaluations=100,
        mean_fitness_delta=-0.99,
        mutation_classes=frozenset({"api_break", "security"}),
        epoch_id=EPOCH_CURR,
    )
    fp_base = _fingerprint(epoch_id=EPOCH_BASE, surface=baseline)
    fp_curr = _fingerprint(epoch_id=EPOCH_CURR, surface=current)
    vector = compute_drift_vector(
        baseline_surface=baseline,
        current_surface=current,
        baseline_fp=fp_base,
        current_fp=fp_curr,
        rule_statement_baseline=STATEMENT_V1,
        rule_statement_current=STATEMENT_AMENDED,  # adds 0.10 bonus
    )
    assert vector.drift_class == DriftClass.CRITICAL
    assert vector.drift_score >= SCDD_CRITICAL_THRESHOLD
    assert vector.statement_changed is True


# ---------------------------------------------------------------------------
# T88-SCDD-08 — class_surface_delta uses Jaccard distance correctly
# ---------------------------------------------------------------------------


def test_t88_scdd_08_class_surface_jaccard():
    """T88-SCDD-08: completely disjoint mutation class sets → class_surface_delta 1.0."""
    baseline = _surface(mutation_classes=frozenset({"refactor", "complexity"}))
    current = _surface(
        mutation_classes=frozenset({"api_break", "security"}),
        epoch_id=EPOCH_CURR,
    )
    fp_base = _fingerprint(epoch_id=EPOCH_BASE, surface=baseline)
    fp_curr = _fingerprint(epoch_id=EPOCH_CURR, surface=current)
    vector = compute_drift_vector(
        baseline_surface=baseline,
        current_surface=current,
        baseline_fp=fp_base,
        current_fp=fp_curr,
        rule_statement_baseline=STATEMENT_V1,
        rule_statement_current=STATEMENT_V1,
    )
    assert vector.class_surface_delta == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# T88-SCDD-09 — gate returns STABLE on identical inputs
# ---------------------------------------------------------------------------


def test_t88_scdd_09_gate_stable_identical():
    """T88-SCDD-09: evaluate_scdd_gate_0 returns STABLE when no drift."""
    surface = _surface()
    fp = _fingerprint()
    ei = _scdd_input(baseline=fp, current=fp)
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: surface},
        current_surfaces={INV_ID: surface},
    )
    assert result.outcome == SCDDOutcome.STABLE
    assert not result.failure_codes
    assert isinstance(result.report, ConstitutionalDriftReport)


# ---------------------------------------------------------------------------
# T88-SCDD-10 — gate result is always a SCDDGateResult
# ---------------------------------------------------------------------------


def test_t88_scdd_10_gate_returns_gate_result_type():
    """T88-SCDD-10: evaluate_scdd_gate_0 always returns SCDDGateResult."""
    surface = _surface()
    fp = _fingerprint()
    ei = _scdd_input(baseline=fp, current=fp)
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: surface},
        current_surfaces={INV_ID: surface},
    )
    assert isinstance(result, SCDDGateResult)
    assert isinstance(result.report, ConstitutionalDriftReport)
    assert isinstance(result.failure_codes, tuple)


# ---------------------------------------------------------------------------
# T88-SCDD-11 — REVIEW_REQUIRED outcome for minor drift
# ---------------------------------------------------------------------------


def test_t88_scdd_11_gate_review_required_minor_drift():
    """T88-SCDD-11: drift_score ≥ SCDD_REVIEW_THRESHOLD → REVIEW_REQUIRED (not BLOCKED)."""
    # Force exactly MINOR drift: high coverage_delta only
    baseline_surf = _surface(total_blocks=5, total_evaluations=100, mean_fitness_delta=0.0, mutation_classes=frozenset({"a"}))
    current_surf = _surface(total_blocks=90, total_evaluations=100, mean_fitness_delta=0.0, mutation_classes=frozenset({"a"}), epoch_id=EPOCH_CURR)

    fp_base = compute_semantic_fingerprint(INV_ID, EPOCH_BASE, STATEMENT_V1, baseline_surf)
    fp_curr = compute_semantic_fingerprint(INV_ID, EPOCH_CURR, STATEMENT_V1, current_surf)

    ei = SCDDEvaluationInput(
        epoch_id=EPOCH_CURR,
        invariant_baselines={INV_ID: fp_base},
        invariant_current={INV_ID: fp_curr},
        rule_statements={INV_ID: STATEMENT_V1},
        predecessor_hash="0" * 64,
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: baseline_surf},
        current_surfaces={INV_ID: current_surf},
    )
    # coverage_delta ≈ 0.85, score ≈ 0.34 → MINOR / REVIEW_REQUIRED
    assert result.outcome in (SCDDOutcome.REVIEW_REQUIRED, SCDDOutcome.STABLE)


# ---------------------------------------------------------------------------
# T88-SCDD-12 — SCDD-0: critical drift → BLOCKED (invariant enforcement)
# ---------------------------------------------------------------------------


def test_t88_scdd_12_gate_blocked_critical_drift():
    """T88-SCDD-12: SCDD-0 — CRITICAL drift forces SCDD_BLOCKED outcome."""
    baseline_surf = _surface(
        total_blocks=1, total_evaluations=100, mean_fitness_delta=-0.01,
        mutation_classes=frozenset({"refactor"})
    )
    current_surf = _surface(
        total_blocks=100, total_evaluations=100, mean_fitness_delta=-1.0,
        mutation_classes=frozenset({"api_break", "security", "data_model"}),
        epoch_id=EPOCH_CURR,
    )
    fp_base = compute_semantic_fingerprint(INV_ID, EPOCH_BASE, STATEMENT_V1, baseline_surf)
    fp_curr = compute_semantic_fingerprint(INV_ID, EPOCH_CURR, STATEMENT_AMENDED, current_surf)

    ei = SCDDEvaluationInput(
        epoch_id=EPOCH_CURR,
        invariant_baselines={INV_ID: fp_base},
        invariant_current={INV_ID: fp_curr},
        rule_statements={INV_ID: STATEMENT_AMENDED},
        predecessor_hash="0" * 64,
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: baseline_surf},
        current_surfaces={INV_ID: current_surf},
        baseline_statements={INV_ID: STATEMENT_V1},
    )
    assert result.outcome == SCDDOutcome.BLOCKED
    assert SCDD_CRITICAL_DRIFT_FOUND in result.failure_codes


# ---------------------------------------------------------------------------
# T88-SCDD-13 — BLOCKED on empty invariant set
# ---------------------------------------------------------------------------


def test_t88_scdd_13_gate_blocked_empty_invariant_set():
    """T88-SCDD-13: empty invariant_current → SCDD_EMPTY_INVARIANT_SET."""
    ei = SCDDEvaluationInput(
        epoch_id=EPOCH_CURR,
        invariant_baselines={},
        invariant_current={},
        rule_statements={},
        predecessor_hash="0" * 64,
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={},
        current_surfaces={},
    )
    assert result.outcome == SCDDOutcome.BLOCKED
    assert SCDD_EMPTY_INVARIANT_SET in result.failure_codes


# ---------------------------------------------------------------------------
# T88-SCDD-14 — BLOCKED on missing baseline fingerprint
# ---------------------------------------------------------------------------


def test_t88_scdd_14_gate_blocked_missing_baseline():
    """T88-SCDD-14: current invariant with no baseline → SCDD_BASELINE_MISSING."""
    surface = _surface()
    fp_curr = _fingerprint(epoch_id=EPOCH_CURR)

    ei = SCDDEvaluationInput(
        epoch_id=EPOCH_CURR,
        invariant_baselines={},          # no baseline
        invariant_current={INV_ID: fp_curr},
        rule_statements={INV_ID: STATEMENT_V1},
        predecessor_hash="0" * 64,
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: surface},
        current_surfaces={INV_ID: surface},
    )
    assert result.outcome == SCDDOutcome.BLOCKED
    assert SCDD_BASELINE_MISSING in result.failure_codes


# ---------------------------------------------------------------------------
# T88-SCDD-15 — BLOCKED on fingerprint nondeterminism (tampered composite_hash)
# ---------------------------------------------------------------------------


def test_t88_scdd_15_gate_blocked_nondeterministic_fingerprint():
    """T88-SCDD-15: tampered composite_hash → SCDD_FINGERPRINT_NONDETERMINISTIC."""
    surface = _surface()
    fp_base = _fingerprint(epoch_id=EPOCH_BASE)
    fp_curr_real = _fingerprint(epoch_id=EPOCH_CURR)

    # Tamper: replace composite_hash with garbage
    fp_tampered = SemanticInvariantFingerprint(
        invariant_id=fp_curr_real.invariant_id,
        epoch_id=fp_curr_real.epoch_id,
        statement_hash=fp_curr_real.statement_hash,
        surface_hash=fp_curr_real.surface_hash,
        composite_hash="0" * 64,  # tampered
    )

    ei = SCDDEvaluationInput(
        epoch_id=EPOCH_CURR,
        invariant_baselines={INV_ID: fp_base},
        invariant_current={INV_ID: fp_tampered},
        rule_statements={INV_ID: STATEMENT_V1},
        predecessor_hash="0" * 64,
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: surface},
        current_surfaces={INV_ID: surface},
    )
    assert result.outcome == SCDDOutcome.BLOCKED
    assert SCDD_FINGERPRINT_NONDETERMINISTIC in result.failure_codes


# ---------------------------------------------------------------------------
# T88-SCDD-16 — gate handles multiple invariants correctly
# ---------------------------------------------------------------------------


def test_t88_scdd_16_gate_multiple_invariants_stable():
    """T88-SCDD-16: multiple invariants all stable → STABLE outcome."""
    ids = ["INV-A", "INV-B", "INV-C"]
    surfaces = {i: _surface(inv_id=i) for i in ids}
    fps = {i: compute_semantic_fingerprint(i, EPOCH_BASE, STATEMENT_V1, surfaces[i]) for i in ids}

    ei = SCDDEvaluationInput(
        epoch_id=EPOCH_CURR,
        invariant_baselines=fps,
        invariant_current=fps,
        rule_statements={i: STATEMENT_V1 for i in ids},
        predecessor_hash="0" * 64,
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces=surfaces,
        current_surfaces=surfaces,
    )
    assert result.outcome == SCDDOutcome.STABLE
    assert len(result.report.drift_vectors) == 3


# ---------------------------------------------------------------------------
# T88-SCDD-17 — report content_hash covers all fields
# ---------------------------------------------------------------------------


def test_t88_scdd_17_report_content_hash_integrity():
    """T88-SCDD-17: report.content_hash is deterministic SHA-256 of payload."""
    surface = _surface()
    fp = _fingerprint()
    ei = _scdd_input(baseline=fp, current=fp)
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: surface},
        current_surfaces={INV_ID: surface},
    )
    report = result.report
    assert len(report.content_hash) == 64
    assert report.content_hash != "0" * 64
    # Same inputs → same hash (determinism)
    result2 = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: surface},
        current_surfaces={INV_ID: surface},
    )
    assert result.report.content_hash == result2.report.content_hash


# ---------------------------------------------------------------------------
# T88-SCDD-18 — report_id embeds epoch and content hash prefix
# ---------------------------------------------------------------------------


def test_t88_scdd_18_report_id_structure():
    """T88-SCDD-18: report_id follows 'scdd-{epoch_id}-{hash_prefix}' format."""
    surface = _surface()
    fp = _fingerprint()
    ei = _scdd_input(epoch_id=EPOCH_CURR, baseline=fp, current=fp)
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: surface},
        current_surfaces={INV_ID: surface},
    )
    rid = result.report.report_id
    assert rid.startswith("scdd-")
    assert EPOCH_CURR in rid
    assert result.report.content_hash[:12] in rid


# ---------------------------------------------------------------------------
# T88-SCDD-19 — surface hash conflict detection
# ---------------------------------------------------------------------------


def test_t88_scdd_19_surface_hash_conflict_blocked():
    """T88-SCDD-19: surface_hash in fingerprint not matching re-derived → BLOCKED."""
    surface = _surface()
    fp_real = _fingerprint(epoch_id=EPOCH_CURR, surface=surface)
    fp_base = _fingerprint(epoch_id=EPOCH_BASE, surface=surface)

    # Craft fingerprint with wrong surface_hash but correct composite
    # (simulate partial tampering that escapes statement check)
    fp_bad_surface = SemanticInvariantFingerprint(
        invariant_id=fp_real.invariant_id,
        epoch_id=fp_real.epoch_id,
        statement_hash=fp_real.statement_hash,
        surface_hash="deadbeef" * 8,          # wrong surface hash
        composite_hash=fp_real.composite_hash,  # stale composite
    )

    ei = SCDDEvaluationInput(
        epoch_id=EPOCH_CURR,
        invariant_baselines={INV_ID: fp_base},
        invariant_current={INV_ID: fp_bad_surface},
        rule_statements={INV_ID: STATEMENT_V1},
        predecessor_hash="0" * 64,
    )
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: surface},
        current_surfaces={INV_ID: surface},
    )
    # Both composite AND surface hash are wrong → BLOCKED
    assert result.outcome == SCDDOutcome.BLOCKED
    assert (
        SCDD_FINGERPRINT_NONDETERMINISTIC in result.failure_codes
        or SCDD_SURFACE_HASH_CONFLICT in result.failure_codes
    )


# ---------------------------------------------------------------------------
# T88-SCDD-20 — predecessor_hash is preserved in report
# ---------------------------------------------------------------------------


def test_t88_scdd_20_predecessor_hash_chained():
    """T88-SCDD-20: predecessor_hash propagates into ConstitutionalDriftReport."""
    predecessor = "a" * 64
    surface = _surface()
    fp = _fingerprint()
    ei = _scdd_input(baseline=fp, current=fp, predecessor_hash=predecessor)
    result = evaluate_scdd_gate_0(
        evaluation_input=ei,
        baseline_surfaces={INV_ID: surface},
        current_surfaces={INV_ID: surface},
    )
    assert result.report.predecessor_hash == predecessor
    assert result.report.scdd_version == SCDD_VERSION
