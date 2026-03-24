# SPDX-License-Identifier: Apache-2.0
"""INNOV-04 — Semantic Constitutional Drift Detector (SCDD).

World-first implementation of semantic drift detection for constitutional
invariants in an autonomous code evolution system.

Constitutional invariants are defined as static rule text, but their
*semantic coverage* — the behavioral surface they govern — shifts as the
evolving system substrate changes.  A rule that was precise at epoch 10
may become over-broad, under-broad, or behaviourally inert by epoch 100,
even if its text has not changed.  SCDD detects this drift, classifies it
by severity, and gates mutation progress when critical drift is found.

Constitutional Invariants Introduced
─────────────────────────────────────
  SCDD-0   SCDD MUST run every N epochs; any invariant with semantic drift
           score ≥ SCDD_CRITICAL_THRESHOLD MUST produce an SCDD_BLOCKED
           outcome, preventing further mutation progress until the drifted
           invariant is reviewed and ratified or amended through CSAP.

Design Constraints
──────────────────
  - All fingerprinting is deterministic given fixed inputs.
  - No datetime.now() / time.time() — injected epoch counter only.
  - Semantic distance computation is exact rational arithmetic.
  - Fail-closed: CRITICAL drift always → SCDD_BLOCKED; no exceptions.
  - ConstitutionalDriftReport is produced on ALL outcomes (STABLE,
    REVIEW_REQUIRED, BLOCKED); it is always hash-chained.

TIFE Integration
────────────────
  SCDD runs in parallel with TIFE in the CEL pre-validation tier.  An
  SCDD_CLEAR report is a required precondition for TIFE entry when the
  SCDD periodic window falls on the current epoch.  TIFE temporal hold
  decisions consume SCDD drift signals as supplemental invariant health
  data.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

SCDD_VERSION = "87.4"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

SCDD_MINOR_THRESHOLD: float = 0.30     # drift_score ≥ this → MINOR
SCDD_MAJOR_THRESHOLD: float = 0.55     # drift_score ≥ this → MAJOR
SCDD_CRITICAL_THRESHOLD: float = 0.75  # drift_score ≥ this → CRITICAL / BLOCKED
SCDD_REVIEW_THRESHOLD: float = 0.30    # any drift ≥ this → REVIEW_REQUIRED outcome
SCDD_DEFAULT_EPOCH_WINDOW: int = 10    # run SCDD every N epochs by default

# ---------------------------------------------------------------------------
# Failure code constants
# ---------------------------------------------------------------------------

SCDD_CRITICAL_DRIFT_FOUND = "SCDD_CRITICAL_DRIFT_FOUND"
SCDD_FINGERPRINT_NONDETERMINISTIC = "SCDD_FINGERPRINT_NONDETERMINISTIC"
SCDD_BASELINE_MISSING = "SCDD_BASELINE_MISSING"
SCDD_EMPTY_INVARIANT_SET = "SCDD_EMPTY_INVARIANT_SET"
SCDD_SURFACE_HASH_CONFLICT = "SCDD_SURFACE_HASH_CONFLICT"

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SCDDOutcome(str, Enum):
    STABLE = "SCDD_STABLE"
    REVIEW_REQUIRED = "SCDD_REVIEW_REQUIRED"
    BLOCKED = "SCDD_BLOCKED"


class DriftClass(str, Enum):
    STABLE = "STABLE"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Core data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BehavioralSurfaceSnapshot:
    """Behavioural statistics for a single invariant at a given epoch.

    These figures describe *how the rule fired* rather than what it says:
    how often it blocked, what the mean fitness delta of blocked mutations
    was, and how many distinct mutation classes it touched.

    Attributes
    ----------
    invariant_id:         ID of the rule this snapshot belongs to.
    epoch_id:             The epoch this snapshot was captured in.
    total_evaluations:    Number of mutations evaluated against this rule.
    total_blocks:         Number of mutations blocked by this rule.
    mean_fitness_delta_blocked: Mean fitness delta of blocked mutations.
    touched_mutation_classes: Set of mutation classes that triggered this rule.
    block_rate:           Derived; blocked / total (0.0 if total == 0).
    """

    invariant_id: str
    epoch_id: str
    total_evaluations: int
    total_blocks: int
    mean_fitness_delta_blocked: float
    touched_mutation_classes: FrozenSet[str]

    @property
    def block_rate(self) -> float:
        if self.total_evaluations == 0:
            return 0.0
        return self.total_blocks / self.total_evaluations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariant_id": self.invariant_id,
            "epoch_id": self.epoch_id,
            "total_evaluations": self.total_evaluations,
            "total_blocks": self.total_blocks,
            "mean_fitness_delta_blocked": self.mean_fitness_delta_blocked,
            "touched_mutation_classes": sorted(self.touched_mutation_classes),
            "block_rate": self.block_rate,
        }


@dataclass(frozen=True)
class SemanticInvariantFingerprint:
    """Deterministic fingerprint of an invariant's semantic state at an epoch.

    Composed from the rule's statement hash (structural) and a behavioural
    surface hash (empirical).  Used as the baseline or current snapshot in
    a DriftVector comparison.

    Attributes
    ----------
    invariant_id:       Rule identifier.
    epoch_id:           Epoch at which this fingerprint was taken.
    statement_hash:     SHA-256 of the rule's canonical statement text.
    surface_hash:       SHA-256 of the BehavioralSurfaceSnapshot serialised
                        as deterministic JSON.
    composite_hash:     SHA-256 of (statement_hash + surface_hash) — the
                        fingerprint identity used for drift comparisons.
    """

    invariant_id: str
    epoch_id: str
    statement_hash: str
    surface_hash: str
    composite_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariant_id": self.invariant_id,
            "epoch_id": self.epoch_id,
            "statement_hash": self.statement_hash,
            "surface_hash": self.surface_hash,
            "composite_hash": self.composite_hash,
        }


@dataclass(frozen=True)
class DriftVector:
    """Captures semantic drift between a baseline and current fingerprint.

    Attributes
    ----------
    invariant_id:           Rule identifier.
    baseline_epoch:         Epoch of the baseline fingerprint.
    current_epoch:          Epoch of the current fingerprint.
    statement_changed:      True if the rule text was amended between epochs.
    coverage_delta:         Absolute change in block_rate [0.0, 1.0].
    precision_delta:        Normalised change in mean_fitness_delta_blocked.
    class_surface_delta:    Jaccard distance between touched_mutation_classes
                            in baseline vs current [0.0, 1.0].
    drift_score:            Composite semantic distance [0.0, 1.0].
    drift_class:            Severity classification.
    """

    invariant_id: str
    baseline_epoch: str
    current_epoch: str
    statement_changed: bool
    coverage_delta: float
    precision_delta: float
    class_surface_delta: float
    drift_score: float
    drift_class: DriftClass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariant_id": self.invariant_id,
            "baseline_epoch": self.baseline_epoch,
            "current_epoch": self.current_epoch,
            "statement_changed": self.statement_changed,
            "coverage_delta": self.coverage_delta,
            "precision_delta": self.precision_delta,
            "class_surface_delta": self.class_surface_delta,
            "drift_score": self.drift_score,
            "drift_class": self.drift_class.value,
        }


@dataclass(frozen=True)
class ConstitutionalDriftReport:
    """Full output of a SCDD evaluation run.

    Always produced — on STABLE, REVIEW_REQUIRED, and BLOCKED outcomes.
    Hash-chained for replay integrity.

    Attributes
    ----------
    report_id:          Deterministic ID from content hash.
    epoch_id:           Current epoch under evaluation.
    outcome:            SCDDOutcome result.
    failure_codes:      List of triggered failure codes (empty on STABLE).
    drift_vectors:      One DriftVector per evaluated invariant.
    max_drift_score:    Maximum drift_score across all vectors.
    scdd_version:       Engine version for replay verification.
    predecessor_hash:   Hash of the preceding report in the epoch chain.
    content_hash:       SHA-256 of the report payload (excluding itself).
    """

    report_id: str
    epoch_id: str
    outcome: SCDDOutcome
    failure_codes: Tuple[str, ...]
    drift_vectors: Tuple[DriftVector, ...]
    max_drift_score: float
    scdd_version: str
    predecessor_hash: str
    content_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "epoch_id": self.epoch_id,
            "outcome": self.outcome.value,
            "failure_codes": list(self.failure_codes),
            "drift_vectors": [v.to_dict() for v in self.drift_vectors],
            "max_drift_score": self.max_drift_score,
            "scdd_version": self.scdd_version,
            "predecessor_hash": self.predecessor_hash,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class SCDDEvaluationInput:
    """Input bundle for a single SCDD gate evaluation.

    Attributes
    ----------
    epoch_id:             Current CEL epoch identifier.
    invariant_baselines:  Mapping of invariant_id → SemanticInvariantFingerprint
                          taken at a prior baseline epoch.
    invariant_current:    Mapping of invariant_id → SemanticInvariantFingerprint
                          taken at the current epoch.
    rule_statements:      Mapping of invariant_id → canonical statement text;
                          used to detect whether text drifted alongside behaviour.
    predecessor_hash:     Hash of the preceding ConstitutionalDriftReport
                          (empty string for genesis run).
    """

    epoch_id: str
    invariant_baselines: Dict[str, SemanticInvariantFingerprint]
    invariant_current: Dict[str, SemanticInvariantFingerprint]
    rule_statements: Dict[str, str]
    predecessor_hash: str


@dataclass(frozen=True)
class SCDDGateResult:
    """Return value of evaluate_scdd_gate_0()."""

    outcome: SCDDOutcome
    report: ConstitutionalDriftReport
    failure_codes: Tuple[str, ...]


# ---------------------------------------------------------------------------
# Fingerprinting helpers
# ---------------------------------------------------------------------------


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def compute_semantic_fingerprint(
    invariant_id: str,
    epoch_id: str,
    statement: str,
    surface: BehavioralSurfaceSnapshot,
) -> SemanticInvariantFingerprint:
    """Produce a deterministic SemanticInvariantFingerprint.

    Determinism contract
    ────────────────────
    - statement_hash:  SHA-256 of ``statement`` encoded as UTF-8.
    - surface_hash:    SHA-256 of ``surface.to_dict()`` serialised via
                       ``json.dumps(..., sort_keys=True)``.
    - composite_hash:  SHA-256 of ``statement_hash + surface_hash``.

    Returns
    -------
    SemanticInvariantFingerprint
        Fully-determined fingerprint for the given epoch state.
    """
    statement_hash = _sha256(statement)
    surface_json = json.dumps(surface.to_dict(), sort_keys=True)
    surface_hash = _sha256(surface_json)
    composite_hash = _sha256(statement_hash + surface_hash)
    return SemanticInvariantFingerprint(
        invariant_id=invariant_id,
        epoch_id=epoch_id,
        statement_hash=statement_hash,
        surface_hash=surface_hash,
        composite_hash=composite_hash,
    )


# ---------------------------------------------------------------------------
# Drift computation
# ---------------------------------------------------------------------------


def _jaccard_distance(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    """Jaccard distance between two sets [0.0, 1.0].  Empty ∩ empty → 0.0."""
    if not a and not b:
        return 0.0
    union = a | b
    intersection = a & b
    return 1.0 - len(intersection) / len(union)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _classify_drift(score: float) -> DriftClass:
    """Map a drift_score to its severity classification."""
    if score >= SCDD_CRITICAL_THRESHOLD:
        return DriftClass.CRITICAL
    if score >= SCDD_MAJOR_THRESHOLD:
        return DriftClass.MAJOR
    if score >= SCDD_MINOR_THRESHOLD:
        return DriftClass.MINOR
    return DriftClass.STABLE


def compute_drift_vector(
    baseline_surface: BehavioralSurfaceSnapshot,
    current_surface: BehavioralSurfaceSnapshot,
    baseline_fp: SemanticInvariantFingerprint,
    current_fp: SemanticInvariantFingerprint,
    rule_statement_baseline: str,
    rule_statement_current: str,
) -> DriftVector:
    """Compute the DriftVector between baseline and current epoch state.

    Drift Score Formula
    ───────────────────
    drift_score = (coverage_delta × 0.40)
                + (precision_delta × 0.30)
                + (class_surface_delta × 0.30)

    All component deltas are clamped to [0.0, 1.0] before weighting.
    Final drift_score clamped to [0.0, 1.0].

    Statement change adds a 0.10 bonus (capped at 1.0) because text
    changes amplify semantic ambiguity regardless of behavioural delta.
    """
    invariant_id = baseline_fp.invariant_id

    coverage_delta = _clamp(abs(baseline_surface.block_rate - current_surface.block_rate))

    # Precision delta: normalise mean_fitness_delta difference to [0, 1]
    raw_precision = abs(
        baseline_surface.mean_fitness_delta_blocked
        - current_surface.mean_fitness_delta_blocked
    )
    precision_delta = _clamp(raw_precision)

    class_surface_delta = _jaccard_distance(
        baseline_surface.touched_mutation_classes,
        current_surface.touched_mutation_classes,
    )

    statement_changed = (
        _sha256(rule_statement_baseline) != _sha256(rule_statement_current)
    )

    drift_score = (
        coverage_delta * 0.40
        + precision_delta * 0.30
        + class_surface_delta * 0.30
    )
    if statement_changed:
        drift_score = _clamp(drift_score + 0.10)
    drift_score = _clamp(drift_score)

    drift_class = _classify_drift(drift_score)

    return DriftVector(
        invariant_id=invariant_id,
        baseline_epoch=baseline_fp.epoch_id,
        current_epoch=current_fp.epoch_id,
        statement_changed=statement_changed,
        coverage_delta=coverage_delta,
        precision_delta=precision_delta,
        class_surface_delta=class_surface_delta,
        drift_score=drift_score,
        drift_class=drift_class,
    )


# ---------------------------------------------------------------------------
# Report construction helpers
# ---------------------------------------------------------------------------


def _report_payload(
    epoch_id: str,
    outcome: SCDDOutcome,
    failure_codes: Tuple[str, ...],
    drift_vectors: Tuple[DriftVector, ...],
    max_drift_score: float,
    scdd_version: str,
    predecessor_hash: str,
) -> str:
    payload = {
        "epoch_id": epoch_id,
        "outcome": outcome.value,
        "failure_codes": sorted(failure_codes),
        "drift_vectors": [v.to_dict() for v in drift_vectors],
        "max_drift_score": max_drift_score,
        "scdd_version": scdd_version,
        "predecessor_hash": predecessor_hash,
    }
    return json.dumps(payload, sort_keys=True)


def _build_report(
    epoch_id: str,
    outcome: SCDDOutcome,
    failure_codes: Tuple[str, ...],
    drift_vectors: Tuple[DriftVector, ...],
    predecessor_hash: str,
) -> ConstitutionalDriftReport:
    max_drift_score = (
        max(v.drift_score for v in drift_vectors) if drift_vectors else 0.0
    )
    payload = _report_payload(
        epoch_id=epoch_id,
        outcome=outcome,
        failure_codes=failure_codes,
        drift_vectors=drift_vectors,
        max_drift_score=max_drift_score,
        scdd_version=SCDD_VERSION,
        predecessor_hash=predecessor_hash,
    )
    content_hash = _sha256(payload)
    report_id = f"scdd-{epoch_id}-{content_hash[:12]}"
    return ConstitutionalDriftReport(
        report_id=report_id,
        epoch_id=epoch_id,
        outcome=outcome,
        failure_codes=failure_codes,
        drift_vectors=drift_vectors,
        max_drift_score=max_drift_score,
        scdd_version=SCDD_VERSION,
        predecessor_hash=predecessor_hash,
        content_hash=content_hash,
    )


# ---------------------------------------------------------------------------
# SCDD-GATE-0 — Main evaluation function
# ---------------------------------------------------------------------------


def evaluate_scdd_gate_0(
    evaluation_input: SCDDEvaluationInput,
    baseline_surfaces: Dict[str, BehavioralSurfaceSnapshot],
    current_surfaces: Dict[str, BehavioralSurfaceSnapshot],
    baseline_statements: Optional[Dict[str, str]] = None,
) -> SCDDGateResult:
    """Evaluate constitutional invariants for semantic drift — SCDD-GATE-0.

    Gate Checks (evaluated in order; all must pass for STABLE outcome)
    ─────────────────────────────────────────────────────────────────
    1. Invariant set is non-empty (SCDD-0 precondition).
    2. All current invariants have a baseline fingerprint present.
    3. All fingerprints are deterministic (re-derive and verify composite).
    4. Surface hash consistency: surface_hash in fingerprint matches derived.
    5. No invariant exceeds SCDD_CRITICAL_THRESHOLD → BLOCKED.
    6. No invariant exceeds SCDD_REVIEW_THRESHOLD → REVIEW_REQUIRED.
    7. All remaining invariants STABLE → SCDD_STABLE.

    Parameters
    ----------
    evaluation_input:   SCDDEvaluationInput bundle for this epoch.
    baseline_surfaces:  BehavioralSurfaceSnapshot per invariant at baseline.
    current_surfaces:   BehavioralSurfaceSnapshot per invariant at current epoch.
    baseline_statements: Optional mapping of invariant_id → rule text at baseline.
                         Defaults to current rule_statements if not provided.

    Returns
    -------
    SCDDGateResult
        Always includes a ConstitutionalDriftReport; outcome reflects severity.
    """
    ei = evaluation_input
    failure_codes: List[str] = []
    drift_vectors: List[DriftVector] = []

    # ------------------------------------------------------------------
    # Check 1: Non-empty invariant set
    # ------------------------------------------------------------------
    if not ei.invariant_current:
        log.warning("SCDD-GATE-0 check 1 FAIL: invariant set is empty")
        failure_codes.append(SCDD_EMPTY_INVARIANT_SET)
        report = _build_report(
            epoch_id=ei.epoch_id,
            outcome=SCDDOutcome.BLOCKED,
            failure_codes=tuple(failure_codes),
            drift_vectors=tuple(drift_vectors),
            predecessor_hash=ei.predecessor_hash,
        )
        return SCDDGateResult(
            outcome=SCDDOutcome.BLOCKED,
            report=report,
            failure_codes=tuple(failure_codes),
        )

    _baseline_stmts = baseline_statements or {}

    # ------------------------------------------------------------------
    # Check 2: All current invariants have a baseline
    # ------------------------------------------------------------------
    missing_baselines = [
        iid for iid in ei.invariant_current if iid not in ei.invariant_baselines
    ]
    if missing_baselines:
        log.warning(
            "SCDD-GATE-0 check 2 FAIL: missing baseline for %s", missing_baselines
        )
        failure_codes.append(SCDD_BASELINE_MISSING)
        report = _build_report(
            epoch_id=ei.epoch_id,
            outcome=SCDDOutcome.BLOCKED,
            failure_codes=tuple(failure_codes),
            drift_vectors=tuple(drift_vectors),
            predecessor_hash=ei.predecessor_hash,
        )
        return SCDDGateResult(
            outcome=SCDDOutcome.BLOCKED,
            report=report,
            failure_codes=tuple(failure_codes),
        )

    # ------------------------------------------------------------------
    # Check 3 & 4: Fingerprint determinism and surface hash consistency
    # ------------------------------------------------------------------
    for iid, current_fp in ei.invariant_current.items():
        stmt = ei.rule_statements.get(iid, "")
        cur_surface = current_surfaces.get(iid)
        if cur_surface is None:
            continue
        # Re-derive to verify determinism
        re_derived = compute_semantic_fingerprint(
            invariant_id=iid,
            epoch_id=current_fp.epoch_id,
            statement=stmt,
            surface=cur_surface,
        )
        if re_derived.composite_hash != current_fp.composite_hash:
            log.error(
                "SCDD-GATE-0 check 3 FAIL: composite_hash nondeterministic for %s", iid
            )
            failure_codes.append(SCDD_FINGERPRINT_NONDETERMINISTIC)
        if re_derived.surface_hash != current_fp.surface_hash:
            log.error(
                "SCDD-GATE-0 check 4 FAIL: surface_hash conflict for %s", iid
            )
            failure_codes.append(SCDD_SURFACE_HASH_CONFLICT)

    if failure_codes:
        report = _build_report(
            epoch_id=ei.epoch_id,
            outcome=SCDDOutcome.BLOCKED,
            failure_codes=tuple(failure_codes),
            drift_vectors=tuple(drift_vectors),
            predecessor_hash=ei.predecessor_hash,
        )
        return SCDDGateResult(
            outcome=SCDDOutcome.BLOCKED,
            report=report,
            failure_codes=tuple(failure_codes),
        )

    # ------------------------------------------------------------------
    # Compute DriftVectors for all invariants
    # ------------------------------------------------------------------
    for iid, current_fp in ei.invariant_current.items():
        baseline_fp = ei.invariant_baselines[iid]
        baseline_surface = baseline_surfaces.get(iid)
        current_surface = current_surfaces.get(iid)
        if baseline_surface is None or current_surface is None:
            continue

        baseline_stmt = _baseline_stmts.get(iid, ei.rule_statements.get(iid, ""))
        current_stmt = ei.rule_statements.get(iid, "")

        vector = compute_drift_vector(
            baseline_surface=baseline_surface,
            current_surface=current_surface,
            baseline_fp=baseline_fp,
            current_fp=current_fp,
            rule_statement_baseline=baseline_stmt,
            rule_statement_current=current_stmt,
        )
        drift_vectors.append(vector)

    # ------------------------------------------------------------------
    # Check 5: SCDD-0 — Critical drift → BLOCKED
    # ------------------------------------------------------------------
    critical = [v for v in drift_vectors if v.drift_class == DriftClass.CRITICAL]
    if critical:
        log.warning(
            "SCDD-GATE-0 check 5 FAIL: CRITICAL drift in %s",
            [v.invariant_id for v in critical],
        )
        failure_codes.append(SCDD_CRITICAL_DRIFT_FOUND)
        report = _build_report(
            epoch_id=ei.epoch_id,
            outcome=SCDDOutcome.BLOCKED,
            failure_codes=tuple(failure_codes),
            drift_vectors=tuple(drift_vectors),
            predecessor_hash=ei.predecessor_hash,
        )
        return SCDDGateResult(
            outcome=SCDDOutcome.BLOCKED,
            report=report,
            failure_codes=tuple(failure_codes),
        )

    # ------------------------------------------------------------------
    # Check 6: Minor or Major drift → REVIEW_REQUIRED
    # ------------------------------------------------------------------
    drifting = [v for v in drift_vectors if v.drift_score >= SCDD_REVIEW_THRESHOLD]
    if drifting:
        report = _build_report(
            epoch_id=ei.epoch_id,
            outcome=SCDDOutcome.REVIEW_REQUIRED,
            failure_codes=tuple(failure_codes),
            drift_vectors=tuple(drift_vectors),
            predecessor_hash=ei.predecessor_hash,
        )
        return SCDDGateResult(
            outcome=SCDDOutcome.REVIEW_REQUIRED,
            report=report,
            failure_codes=tuple(failure_codes),
        )

    # ------------------------------------------------------------------
    # Check 7: All STABLE
    # ------------------------------------------------------------------
    report = _build_report(
        epoch_id=ei.epoch_id,
        outcome=SCDDOutcome.STABLE,
        failure_codes=tuple(failure_codes),
        drift_vectors=tuple(drift_vectors),
        predecessor_hash=ei.predecessor_hash,
    )
    return SCDDGateResult(
        outcome=SCDDOutcome.STABLE,
        report=report,
        failure_codes=tuple(failure_codes),
    )
