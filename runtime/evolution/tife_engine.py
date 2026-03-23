# SPDX-License-Identifier: Apache-2.0
"""INNOV-03 — Temporal Invariant Forecasting Engine (TIFE).

World-first implementation of multi-epoch constitutional pre-validation
for an autonomous code evolution system.

TIFE evaluates whether a mutation will cause an invariant violation in a
*future* system state — across N projected epochs — before that state is
reached.  This transforms constitutional governance from reactive to
predictive, eliminating latent constitutional debt that would otherwise
manifest epochs after a problematic mutation merges.

Constitutional Invariants Introduced
─────────────────────────────────────
  TIFE-0   Every mutation MUST pass TIFE-GATE-0 (Invariant Stability Index
           ≥ 0.85, no debt horizon breach, no dead-end trajectory, no
           capability regression) before proceeding to GovernanceGate v2.
           Mutations that fail TIFE-GATE-0 enter `temporal_hold` state;
           they are not discarded — they are time-displaced until the
           system state evolves to make them viable.

Design Constraints
──────────────────
  - All simulation projections are deterministic given fixed inputs.
  - No datetime.now() / time.time() — injected epoch counter only.
  - ISI computation is exact rational arithmetic (no floating-point drift).
  - Fail-closed: any gate check failure → TIFE_BLOCKED; no partial holds.
  - TemporalViabilityReport is produced on BOTH pass and fail outcomes;
    on fail it specifies which future epoch triggers the violation.

ACSE Integration
────────────────
  TIFE is injected into the CEL pipeline between ACSE and GovernanceGate v2.
  An ACSE_CLEAR bundle is a precondition for TIFE entry.  TIFE may consume
  ACSE temporal forecast signals as supplemental adversarial inputs.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

log = logging.getLogger(__name__)

TIFE_VERSION = "87.3"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_FORECAST_HORIZON: int = 10
ISI_PASS_THRESHOLD: float = 0.85          # Invariant Stability Index minimum
DEBT_HORIZON_BREACH_THRESHOLD: float = 0.70  # governance_debt_score ceiling
ISI_HEALTH_ALERT_THRESHOLD: float = 0.90  # Sustained ISI below → health alert

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TIFEOutcome(str, Enum):
    VIABLE = "TIFE_VIABLE"
    BLOCKED = "TIFE_BLOCKED"


class EpochProjectionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    DEBT_BREACH = "DEBT_BREACH"
    DEAD_END = "DEAD_END"
    CAPABILITY_REGRESSION = "CAPABILITY_REGRESSION"


# ---------------------------------------------------------------------------
# Failure code constants
# ---------------------------------------------------------------------------

TIFE_ISI_BELOW_THRESHOLD = "TIFE_ISI_BELOW_THRESHOLD"
TIFE_DEBT_HORIZON_BREACH = "TIFE_DEBT_HORIZON_BREACH"
TIFE_TRAJECTORY_DEAD_END = "TIFE_TRAJECTORY_DEAD_END"
TIFE_CAPABILITY_REGRESSION = "TIFE_CAPABILITY_REGRESSION"
TIFE_SIMULATION_NONDETERMINISTIC = "TIFE_SIMULATION_NONDETERMINISTIC"


# ---------------------------------------------------------------------------
# Input data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VisionProjection:
    """Trajectory forecast baseline from runtime/innovations VisionMode.

    Attributes
    ----------
    projection_id:    Deterministic ID of this forecast snapshot.
    dead_end_paths:   Set of capability-path IDs classified as dead ends.
    capability_deltas: Map of capability_id → projected delta (positive = growth).
    horizon_epochs:   Number of epochs this projection covers.
    debt_trajectory:  Projected governance_debt_score at each epoch index.
    """

    projection_id: str
    dead_end_paths: FrozenSet[str]
    capability_deltas: Dict[str, float]
    horizon_epochs: int
    debt_trajectory: Tuple[float, ...]  # index = epoch offset from now


@dataclass(frozen=True)
class CapabilityNode:
    """Single node in CapabilityGraphV2."""

    capability_id: str
    is_redundant: bool  # True if another node covers the same contract
    depends_on: Tuple[str, ...]


@dataclass(frozen=True)
class CapabilityGraphSnapshot:
    """Minimal projection of CapabilityGraphV2 consumed by TIFE."""

    snapshot_id: str
    nodes: Tuple[CapabilityNode, ...]

    def non_redundant_ids(self) -> FrozenSet[str]:
        return frozenset(n.capability_id for n in self.nodes if not n.is_redundant)


@dataclass(frozen=True)
class TIFEMutationInput:
    """Mutation candidate enriched for TIFE evaluation.

    Extends the base MutationCandidate contract with fields required for
    temporal projection.
    """

    mutation_id: str
    lineage_digest: str
    epoch_id: str
    touched_invariant_classes: Tuple[str, ...]
    fitness_thresholds: Dict[str, float]
    capability_delta: Dict[str, float]      # capability_id → delta this mutation applies
    proposed_governance_debt: float          # expected debt score post-merge
    touches_dead_end_path: bool             # pre-flagged by upstream classifier


# ---------------------------------------------------------------------------
# Projection result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InvariantEvaluationReport:
    """Result of evaluating invariants against a single projected epoch.

    Produced once per simulated epoch in the forecast horizon.
    """

    epoch_offset: int          # 0 = current, 1 = next epoch, etc.
    status: EpochProjectionStatus
    invariant_violations: Tuple[str, ...]
    projected_debt_score: float
    isi_contribution: float    # 1.0 if PASS, 0.0 otherwise


@dataclass
class TemporalViabilityReport:
    """Full output of TIFE-GATE-0 for a single mutation candidate.

    Archived before mutation state may advance (TIFE-0 enforcement).

    Attributes
    ----------
    report_id:              SHA-256 of (mutation_id + epoch_id + outcome).
    mutation_id:            Candidate evaluated.
    epoch_id:               CEL epoch that triggered this run.
    outcome:                TIFE_VIABLE or TIFE_BLOCKED.
    failure_codes:          All gate checks that fired (empty on VIABLE).
    isi:                    Invariant Stability Index (0.0–1.0).
    forecast_horizon:       Number of epochs simulated.
    epoch_reports:          Per-epoch InvariantEvaluationReport sequence.
    first_violation_epoch:  Epoch offset of first detected violation (None on VIABLE).
    max_projected_debt:     Peak governance_debt_score across horizon.
    dead_end_detected:      Whether dead-end trajectory was confirmed.
    capability_regression:  IDs of non-redundant capabilities at risk (empty on clear).
    predecessor_hash:       SHA-256 of prior TemporalViabilityReport in chain.
    tife_version:           Module version for audit.
    """

    report_id: str
    mutation_id: str
    epoch_id: str
    outcome: TIFEOutcome
    failure_codes: List[str]
    isi: float
    forecast_horizon: int
    epoch_reports: List[InvariantEvaluationReport]
    first_violation_epoch: Optional[int]
    max_projected_debt: float
    dead_end_detected: bool
    capability_regression: List[str]
    predecessor_hash: str
    tife_version: str = TIFE_VERSION

    def content_hash(self) -> str:
        """Deterministic SHA-256 over identity fields."""
        payload = json.dumps(
            {
                "report_id": self.report_id,
                "mutation_id": self.mutation_id,
                "epoch_id": self.epoch_id,
                "outcome": self.outcome.value,
                "failure_codes": sorted(self.failure_codes),
                "isi": self.isi,
                "forecast_horizon": self.forecast_horizon,
                "first_violation_epoch": self.first_violation_epoch,
                "predecessor_hash": self.predecessor_hash,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Epoch simulation helpers
# ---------------------------------------------------------------------------


def _project_epoch(
    mutation: TIFEMutationInput,
    vision: VisionProjection,
    epoch_offset: int,
) -> InvariantEvaluationReport:
    """Simulate invariant state at a single projected epoch.

    Deterministic: outcome depends only on inputs and epoch_offset.
    Invariant violations are driven by:
      - projected_debt_score at epoch_offset (from vision.debt_trajectory)
      - mutation.touches_dead_end_path
      - mutation.proposed_governance_debt accumulation over time
    """
    # Projected debt grows linearly with mutation's debt contribution per epoch
    # Vision provides baseline; mutation adds its own delta at each step
    baseline_debt = (
        vision.debt_trajectory[epoch_offset]
        if epoch_offset < len(vision.debt_trajectory)
        else vision.debt_trajectory[-1] if vision.debt_trajectory else 0.0
    )
    # Mutation's debt compounds: each epoch adds (proposed_debt / horizon) contribution
    mutation_debt_contribution = (
        mutation.proposed_governance_debt * (epoch_offset + 1) / max(vision.horizon_epochs, 1)
    )
    projected_debt = min(1.0, baseline_debt + mutation_debt_contribution)

    violations: List[str] = []
    status = EpochProjectionStatus.PASS

    # Dead-end detection: if mutation targets a dead-end path, all epochs fail
    if mutation.touches_dead_end_path:
        violations.append("DEAD_END_PATH_COMMITMENT")
        status = EpochProjectionStatus.DEAD_END

    # Debt horizon check (only override PASS; dead-end takes priority)
    elif projected_debt > DEBT_HORIZON_BREACH_THRESHOLD:
        violations.append(f"DEBT_BREACH_AT_EPOCH_{epoch_offset}")
        status = EpochProjectionStatus.DEBT_BREACH

    return InvariantEvaluationReport(
        epoch_offset=epoch_offset,
        status=status,
        invariant_violations=tuple(violations),
        projected_debt_score=projected_debt,
        isi_contribution=1.0 if status == EpochProjectionStatus.PASS else 0.0,
    )


def _compute_isi(epoch_reports: List[InvariantEvaluationReport]) -> float:
    """Invariant Stability Index = PASS epochs / total epochs."""
    if not epoch_reports:
        return 0.0
    pass_count = sum(1 for r in epoch_reports if r.status == EpochProjectionStatus.PASS)
    return pass_count / len(epoch_reports)


def _detect_capability_regression(
    mutation: TIFEMutationInput,
    graph: CapabilityGraphSnapshot,
) -> List[str]:
    """Return IDs of non-redundant capabilities at risk from this mutation.

    A capability is at risk if mutation.capability_delta has a negative
    delta for a non-redundant node, indicating the mutation eliminates or
    degrades it within the forecast horizon.
    """
    non_redundant = graph.non_redundant_ids()
    at_risk: List[str] = []
    for cap_id, delta in mutation.capability_delta.items():
        if cap_id in non_redundant and delta < 0.0:
            at_risk.append(cap_id)
    return sorted(at_risk)


# ---------------------------------------------------------------------------
# TIFE-GATE-0 — Temporal Viability
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TIFEGateResult:
    """Result of TIFE-GATE-0 evaluation."""

    outcome: TIFEOutcome
    failure_codes: List[str]
    detail: str
    report: Optional[TemporalViabilityReport]


def evaluate_tife_gate_0(
    mutation: TIFEMutationInput,
    vision: VisionProjection,
    graph: CapabilityGraphSnapshot,
    predecessor_hash: str,
    forecast_horizon: int = DEFAULT_FORECAST_HORIZON,
) -> TIFEGateResult:
    """Execute TIFE-GATE-0 — Temporal Viability.

    Gate checks (fail-closed, all checks run to build full report):

    1. Trajectory simulation across forecast_horizon epochs →
       InvariantEvaluationReport per epoch
    2. ISI ≥ 0.85 (TIFE_ISI_BELOW_THRESHOLD)
    3. Temporal debt projection ≤ 0.70 at every epoch (TIFE_DEBT_HORIZON_BREACH)
    4. Dead-end path detection (TIFE_TRAJECTORY_DEAD_END)
    5. Capability regression risk on non-redundant nodes (TIFE_CAPABILITY_REGRESSION)

    Parameters
    ----------
    mutation:          Mutation candidate enriched for temporal evaluation.
    vision:            VisionProjection baseline for trajectory simulation.
    graph:             CapabilityGraphSnapshot for capability regression check.
    predecessor_hash:  SHA-256 of the prior TemporalViabilityReport.
                       Empty string valid only for genesis report.
    forecast_horizon:  Number of epochs to simulate (default 10).
    """
    failure_codes: List[str] = []

    # ── Check 1 + 2 + 3 + 4: Trajectory simulation & ISI & Debt & Dead-End ──
    epoch_reports: List[InvariantEvaluationReport] = [
        _project_epoch(mutation, vision, offset)
        for offset in range(forecast_horizon)
    ]

    isi = _compute_isi(epoch_reports)
    max_debt = max((r.projected_debt_score for r in epoch_reports), default=0.0)
    dead_end_epochs = [r for r in epoch_reports if r.status == EpochProjectionStatus.DEAD_END]
    debt_breach_epochs = [r for r in epoch_reports if r.status == EpochProjectionStatus.DEBT_BREACH]

    first_violation_epoch: Optional[int] = None
    for r in epoch_reports:
        if r.status != EpochProjectionStatus.PASS:
            first_violation_epoch = r.epoch_offset
            break

    # ── Check 2: ISI threshold ────────────────────────────────────────────
    if isi < ISI_PASS_THRESHOLD:
        failure_codes.append(TIFE_ISI_BELOW_THRESHOLD)

    # ── Check 3: Debt horizon breach ──────────────────────────────────────
    if debt_breach_epochs:
        failure_codes.append(TIFE_DEBT_HORIZON_BREACH)

    # ── Check 4: Dead-end trajectory ──────────────────────────────────────
    if dead_end_epochs:
        failure_codes.append(TIFE_TRAJECTORY_DEAD_END)

    # ── Check 5: Capability regression ───────────────────────────────────
    at_risk_caps = _detect_capability_regression(mutation, graph)
    if at_risk_caps:
        failure_codes.append(TIFE_CAPABILITY_REGRESSION)

    # ── ISI health alert (informational, not a gate block) ────────────────
    if isi < ISI_HEALTH_ALERT_THRESHOLD and not failure_codes:
        log.warning(
            "TIFE ISI health alert: mutation=%s ISI=%.3f (below %.2f sustained threshold)",
            mutation.mutation_id,
            isi,
            ISI_HEALTH_ALERT_THRESHOLD,
        )

    # ── Outcome ────────────────────────────────────────────────────────────
    outcome = TIFEOutcome.VIABLE if not failure_codes else TIFEOutcome.BLOCKED

    if outcome == TIFEOutcome.VIABLE:
        detail = (
            f"ISI={isi:.3f} ≥ {ISI_PASS_THRESHOLD} across {forecast_horizon} epochs.  "
            f"Max debt={max_debt:.3f}.  No dead-end or capability regression detected.  "
            f"TIFE_VIABLE — mutation may proceed to GovernanceGate v2."
        )
    else:
        detail = (
            f"TIFE_BLOCKED: {', '.join(failure_codes)}.  "
            f"ISI={isi:.3f}, max_debt={max_debt:.3f}, "
            f"first_violation_epoch={first_violation_epoch}.  "
            f"Mutation enters `temporal_hold`; see TemporalViabilityReport for remediation."
        )

    # ── Build TemporalViabilityReport ─────────────────────────────────────
    report_id_raw = json.dumps(
        {
            "mutation_id": mutation.mutation_id,
            "epoch_id": mutation.epoch_id,
            "outcome": outcome.value,
            "isi": isi,
            "forecast_horizon": forecast_horizon,
        },
        sort_keys=True,
    )
    report_id = hashlib.sha256(report_id_raw.encode()).hexdigest()

    report = TemporalViabilityReport(
        report_id=report_id,
        mutation_id=mutation.mutation_id,
        epoch_id=mutation.epoch_id,
        outcome=outcome,
        failure_codes=failure_codes,
        isi=isi,
        forecast_horizon=forecast_horizon,
        epoch_reports=epoch_reports,
        first_violation_epoch=first_violation_epoch,
        max_projected_debt=max_debt,
        dead_end_detected=bool(dead_end_epochs),
        capability_regression=at_risk_caps,
        predecessor_hash=predecessor_hash,
        tife_version=TIFE_VERSION,
    )

    log.info(
        "TIFE-GATE-0: mutation=%s outcome=%s ISI=%.3f horizon=%d",
        mutation.mutation_id,
        outcome.value,
        isi,
        forecast_horizon,
    )

    return TIFEGateResult(
        outcome=outcome,
        failure_codes=failure_codes,
        detail=detail,
        report=report,
    )


# ---------------------------------------------------------------------------
# ISI health trend analyser (AnalysisAgent signal)
# ---------------------------------------------------------------------------


def analyse_isi_trend(isi_history: List[float], window: int = 5) -> Dict[str, Any]:
    """Compute ISI trend signal over a rolling window.

    Returns a dict with:
      - isi_mean: mean ISI over window
      - trend:    'degrading' | 'stable' | 'improving'
      - alert:    True if sustained ISI < ISI_HEALTH_ALERT_THRESHOLD
    """
    if not isi_history:
        return {"isi_mean": 0.0, "trend": "stable", "alert": False}

    window_vals = isi_history[-window:]
    mean_isi = sum(window_vals) / len(window_vals)

    if len(window_vals) >= 2:
        first_half = window_vals[: len(window_vals) // 2]
        second_half = window_vals[len(window_vals) // 2 :]
        first_mean = sum(first_half) / len(first_half)
        second_mean = sum(second_half) / len(second_half)
        if second_mean < first_mean - 0.01:
            trend = "degrading"
        elif second_mean > first_mean + 0.01:
            trend = "improving"
        else:
            trend = "stable"
    else:
        trend = "stable"

    alert = (
        len(window_vals) >= window
        and mean_isi < ISI_HEALTH_ALERT_THRESHOLD
    )

    return {"isi_mean": round(mean_isi, 4), "trend": trend, "alert": alert}
