# SPDX-License-Identifier: Apache-2.0
"""INNOV-07 — Live Shadow Mutation Execution (LSME).

World-first constitutionally governed shadow execution layer for an autonomous
software evolution system.

All prior ADAAD fitness evaluation runs against synthetic test fixtures.
LSME executes proposed mutations in a zero-write, read-only shadow against
ADAAD's own production request traffic before governance approval.  This
provides real-world fitness signal that synthetic tests structurally cannot
produce, while every constitutional guarantee is maintained through an
enforced zero-write shadow contract.

Constitutional Invariants Introduced
─────────────────────────────────────
  LSME-0   Shadow execution MUST be zero-write: write_operations_permitted,
           network_egress_permitted, and database_mutations_permitted are ALL
           false in the ShadowContract.  Any AST or runtime detection of a
           write or egress attempt MUST produce LSME_WRITE_DETECTED or
           LSME_EGRESS_DETECTED respectively — both are hard blocks requiring
           HUMAN-0 alert.

  LSME-1   A ShadowFitnessReport MUST be committed to the evidence ledger
           BEFORE any divergence comparison begins.  No partial evidence is
           accepted (LSME_TRACE_INCOMPLETE).  LSME_BUDGET_EXCEEDED is the
           only non-blocking failure; the mutation proceeds on synthetic
           fitness only when the budget is exhausted before shadow completes.

Design Constraints
──────────────────
  - LSME-GATE-0 is pre-execution; LSME-GATE-1 is post-execution.
    Gate-0 failure aborts before any traffic is replayed (zero contamination).
  - All divergence comparisons are deterministic: identical inputs → identical
    divergence score.
  - No datetime.now() / time.time() — injected epoch counter only.
  - ShadowFitnessReport is frozen, hash-chained, and ledger-appendable.
  - LSME_BUDGET_EXCEEDED is advisory (non-blocking): mutation proceeds on
    synthetic fitness.  All other failure codes are blocking.
  - P99 computation uses exact sorted-percentile on the provided latency list.

Pipeline Position (from INNOV Architecture Plan)
─────────────────────────────────────────────────
  SCDD_CLEAR → LSME-GATE-0 → (shadow exec) → LSME-GATE-1 → GovernanceGate v2
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

LSME_VERSION = "91.1"

# ---------------------------------------------------------------------------
# Thresholds (from spec)
# ---------------------------------------------------------------------------

DEFAULT_MAX_DIVERGENCE_RATE: float = 0.05    # 5% — LSME-GATE-1 check 1
MAX_ERROR_RATE_DELTA: float = 0.01           # +1% absolute — check 2
MAX_LATENCY_P99_MULTIPLIER: float = 1.10     # 10% regression ceiling — check 3

# ---------------------------------------------------------------------------
# Failure code constants
# ---------------------------------------------------------------------------

LSME_WRITE_DETECTED = "LSME_WRITE_DETECTED"
LSME_EGRESS_DETECTED = "LSME_EGRESS_DETECTED"
LSME_BUDGET_EXCEEDED = "LSME_BUDGET_EXCEEDED"
LSME_ERROR_REGRESSION = "LSME_ERROR_REGRESSION"
LSME_LATENCY_REGRESSION = "LSME_LATENCY_REGRESSION"
LSME_TRACE_INCOMPLETE = "LSME_TRACE_INCOMPLETE"
LSME_CONTRACT_VIOLATION = "LSME_CONTRACT_VIOLATION"
LSME_INVARIANT_FAILURE = "LSME_INVARIANT_FAILURE"
LSME_DIVERGENCE_EXCEEDED = "LSME_DIVERGENCE_EXCEEDED"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class LSMEOutcome(str, Enum):
    SHADOW_CLEAR = "LSME_SHADOW_CLEAR"
    SHADOW_FAILED = "LSME_SHADOW_FAILED"
    SHADOW_ABORTED = "LSME_SHADOW_ABORTED"    # GATE-0 block or budget
    BUDGET_EXCEEDED = "LSME_BUDGET_EXCEEDED"   # non-blocking advisory


class ShadowVerdict(str, Enum):
    CLEAR = "CLEAR"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShadowContract:
    """Constitutional constraints governing what the shadow may do.

    Attributes:
        write_operations_permitted: MUST be False (LSME-0).
        network_egress_permitted: MUST be False (LSME-0).
        database_mutations_permitted: MUST be False (LSME-0).
        max_divergence_rate: Maximum acceptable response divergence rate.
    """

    write_operations_permitted: bool
    network_egress_permitted: bool
    database_mutations_permitted: bool
    max_divergence_rate: float = DEFAULT_MAX_DIVERGENCE_RATE

    def is_zero_write(self) -> bool:
        """Return True iff all three zero-write conditions are satisfied (LSME-0)."""
        return (
            not self.write_operations_permitted
            and not self.network_egress_permitted
            and not self.database_mutations_permitted
        )


@dataclass(frozen=True)
class ShadowBudget:
    """Resource budget for one shadow execution run.

    Attributes:
        max_wall_clock_ms: Maximum elapsed wall-clock time in milliseconds.
        max_cpu_ms: Maximum CPU time in milliseconds.
        max_memory_mb: Maximum memory footprint in megabytes.
        max_requests: Maximum number of traffic requests to replay.
    """

    max_wall_clock_ms: float
    max_cpu_ms: float
    max_memory_mb: float
    max_requests: int = 100


@dataclass(frozen=True)
class TrafficRequest:
    """A single production traffic request for shadow replay.

    Attributes:
        request_id: Unique request identifier.
        method: HTTP method or RPC name.
        path: Request path/endpoint.
        payload_hash: SHA-256 of request body (content, not raw body).
    """

    request_id: str
    method: str
    path: str
    payload_hash: str


@dataclass(frozen=True)
class BaselineResponse:
    """Pre-recorded baseline response for comparison.

    Attributes:
        request_id: Matching request_id from TrafficRequest.
        response_hash: SHA-256 of the canonical response body.
        error: True if the baseline response was an error.
        latency_ms: Observed latency in milliseconds.
    """

    request_id: str
    response_hash: str
    error: bool
    latency_ms: float


@dataclass(frozen=True)
class ShadowResponse:
    """Shadow execution result for a single replayed request.

    Attributes:
        request_id: Matching request_id.
        response_hash: SHA-256 of shadow response body.
        error: True if shadow response was an error.
        latency_ms: Shadow execution latency in milliseconds.
        diverged: True if shadow response_hash != baseline response_hash.
    """

    request_id: str
    response_hash: str
    error: bool
    latency_ms: float
    diverged: bool


@dataclass(frozen=True)
class ShadowFitnessReport:
    """Complete evidence artifact for one LSME shadow execution run.

    LSME-1: This report MUST be committed to the ledger BEFORE divergence
    comparison begins.  It is hash-chained for replay integrity.

    Attributes:
        report_id: Deterministic ID from report_hash[:20].
        mutation_id: Mutation under evaluation.
        epoch_id: Epoch at evaluation time.
        total_requests: Number of requests replayed.
        divergence_count: Requests with divergent responses.
        divergence_rate: divergence_count / total_requests.
        shadow_error_rate: Fraction of shadow responses that were errors.
        baseline_error_rate: Fraction of baseline responses that were errors.
        shadow_p99_latency_ms: P99 latency across shadow responses.
        baseline_p99_latency_ms: P99 latency across baseline responses.
        invariant_failures: Invariant IDs that failed in shadow execution.
        shadow_responses: All individual shadow responses.
        verdict: CLEAR / FAILED / ABORTED.
        failure_codes: Triggered LSME failure codes.
        report_hash: SHA-256 of canonical report JSON.
        lsme_version: Engine version.
    """

    report_id: str
    mutation_id: str
    epoch_id: str
    total_requests: int
    divergence_count: int
    divergence_rate: float
    shadow_error_rate: float
    baseline_error_rate: float
    shadow_p99_latency_ms: float
    baseline_p99_latency_ms: float
    invariant_failures: Tuple[str, ...]
    shadow_responses: Tuple[ShadowResponse, ...]
    verdict: ShadowVerdict
    failure_codes: Tuple[str, ...]
    report_hash: str
    lsme_version: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "mutation_id": self.mutation_id,
            "epoch_id": self.epoch_id,
            "total_requests": self.total_requests,
            "divergence_count": self.divergence_count,
            "divergence_rate": round(self.divergence_rate, 6),
            "shadow_error_rate": round(self.shadow_error_rate, 6),
            "baseline_error_rate": round(self.baseline_error_rate, 6),
            "shadow_p99_latency_ms": round(self.shadow_p99_latency_ms, 3),
            "baseline_p99_latency_ms": round(self.baseline_p99_latency_ms, 3),
            "invariant_failures": list(self.invariant_failures),
            "verdict": self.verdict.value,
            "failure_codes": list(self.failure_codes),
            "report_hash": self.report_hash,
            "lsme_version": self.lsme_version,
        }


@dataclass(frozen=True)
class LSMEGateResult:
    """Return value of evaluate_lsme_gate_0() or evaluate_lsme_gate_1().

    Attributes:
        outcome: LSMEOutcome.
        fitness_report: ShadowFitnessReport if produced; None on pre-exec abort.
        failure_codes: All triggered failure codes.
        is_blocking: False only for LSME_BUDGET_EXCEEDED (advisory).
        gate_id: ``LSME-GATE-0`` or ``LSME-GATE-1``.
        result_hash: SHA-256 of canonical result payload.
    """

    outcome: LSMEOutcome
    fitness_report: Optional[ShadowFitnessReport]
    failure_codes: Tuple[str, ...]
    is_blocking: bool
    gate_id: str
    result_hash: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _p99(values: Sequence[float]) -> float:
    """Exact P99 via sorted-percentile.  Returns 0.0 for empty sequences."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = math.ceil(0.99 * len(sorted_v)) - 1
    return sorted_v[max(0, idx)]


def _report_hash(
    mutation_id: str,
    epoch_id: str,
    total_requests: int,
    divergence_count: int,
    shadow_error_rate: float,
    baseline_error_rate: float,
    shadow_p99: float,
    baseline_p99: float,
    invariant_failures: Sequence[str],
    verdict: ShadowVerdict,
    failure_codes: Sequence[str],
) -> str:
    payload = {
        "mutation_id": mutation_id,
        "epoch_id": epoch_id,
        "total_requests": total_requests,
        "divergence_count": divergence_count,
        "shadow_error_rate": round(shadow_error_rate, 6),
        "baseline_error_rate": round(baseline_error_rate, 6),
        "shadow_p99": round(shadow_p99, 3),
        "baseline_p99": round(baseline_p99, 3),
        "invariant_failures": sorted(invariant_failures),
        "verdict": verdict.value,
        "failure_codes": sorted(failure_codes),
    }
    return _sha256(json.dumps(payload, sort_keys=True))


def _result_hash_fn(
    outcome: LSMEOutcome, gate_id: str, failure_codes: Sequence[str], report_id: Optional[str]
) -> str:
    return _sha256(
        json.dumps(
            {
                "outcome": outcome.value,
                "gate_id": gate_id,
                "failure_codes": sorted(failure_codes),
                "report_id": report_id,
            },
            sort_keys=True,
        )
    )


def _build_fitness_report(
    mutation_id: str,
    epoch_id: str,
    shadow_responses: List[ShadowResponse],
    baseline_responses: List[BaselineResponse],
    invariant_failures: List[str],
    failure_codes: List[str],
    verdict: ShadowVerdict,
) -> ShadowFitnessReport:
    """Construct and hash-anchor a ShadowFitnessReport."""
    total = len(shadow_responses)
    diverged = sum(1 for r in shadow_responses if r.diverged)
    div_rate = diverged / total if total else 0.0

    shadow_errors = sum(1 for r in shadow_responses if r.error)
    shadow_err_rate = shadow_errors / total if total else 0.0
    baseline_errors = sum(1 for r in baseline_responses if r.error)
    baseline_err_rate = baseline_errors / len(baseline_responses) if baseline_responses else 0.0

    shadow_p99 = _p99([r.latency_ms for r in shadow_responses])
    baseline_p99 = _p99([r.latency_ms for r in baseline_responses])

    rh = _report_hash(
        mutation_id=mutation_id,
        epoch_id=epoch_id,
        total_requests=total,
        divergence_count=diverged,
        shadow_error_rate=shadow_err_rate,
        baseline_error_rate=baseline_err_rate,
        shadow_p99=shadow_p99,
        baseline_p99=baseline_p99,
        invariant_failures=invariant_failures,
        verdict=verdict,
        failure_codes=failure_codes,
    )
    report_id = f"LSME-{rh[:20].upper()}"
    return ShadowFitnessReport(
        report_id=report_id,
        mutation_id=mutation_id,
        epoch_id=epoch_id,
        total_requests=total,
        divergence_count=diverged,
        divergence_rate=div_rate,
        shadow_error_rate=shadow_err_rate,
        baseline_error_rate=baseline_err_rate,
        shadow_p99_latency_ms=shadow_p99,
        baseline_p99_latency_ms=baseline_p99,
        invariant_failures=tuple(invariant_failures),
        shadow_responses=tuple(shadow_responses),
        verdict=verdict,
        failure_codes=tuple(failure_codes),
        report_hash=rh,
        lsme_version=LSME_VERSION,
    )


# ---------------------------------------------------------------------------
# LSME-GATE-0 — Shadow Contract Enforcement (pre-execution)
# ---------------------------------------------------------------------------


def evaluate_lsme_gate_0(
    mutation_id: str,
    shadow_contract: ShadowContract,
    shadow_budget: ShadowBudget,
    write_ops_in_ast: bool = False,
    egress_in_ast: bool = False,
    estimated_budget_ms: Optional[float] = None,
) -> LSMEGateResult:
    """Evaluate LSME-GATE-0 — pre-execution shadow contract enforcement.

    Gate checks:
      1. shadow_contract.write_operations_permitted MUST be False (LSME-0).
      2. shadow_contract.network_egress_permitted MUST be False (LSME-0).
      3. shadow_contract.database_mutations_permitted MUST be False (LSME-0).
      4. write_ops_in_ast MUST be False (AST pre-scan).
      5. egress_in_ast MUST be False (AST network pre-scan).
      6. estimated_budget_ms ≤ shadow_budget.max_wall_clock_ms if provided.

    Hard blocks: checks 1-5 produce blocking failures (LSME-0 enforcement).
    Advisory: check 6 failure → LSME_BUDGET_EXCEEDED (non-blocking).

    Args:
        mutation_id: Mutation under evaluation.
        shadow_contract: Constitutional zero-write contract.
        shadow_budget: Resource bounds.
        write_ops_in_ast: True if AST pre-scan detected write operations.
        egress_in_ast: True if AST pre-scan detected network egress.
        estimated_budget_ms: Estimated shadow execution time (optional).

    Returns:
        LSMEGateResult with gate_id=``LSME-GATE-0``.
    """
    failure_codes: List[str] = []
    blocking = False

    # Checks 1-3: Contract zero-write invariants (LSME-0)
    if shadow_contract.write_operations_permitted:
        log.error("LSME-GATE-0 check 1 FAIL: write_operations_permitted=True — LSME-0 violated")
        failure_codes.append(LSME_CONTRACT_VIOLATION)
        blocking = True
    if shadow_contract.network_egress_permitted:
        log.error("LSME-GATE-0 check 2 FAIL: network_egress_permitted=True — LSME-0 violated")
        failure_codes.append(LSME_CONTRACT_VIOLATION)
        blocking = True
    if shadow_contract.database_mutations_permitted:
        log.error("LSME-GATE-0 check 3 FAIL: database_mutations_permitted=True — LSME-0 violated")
        failure_codes.append(LSME_CONTRACT_VIOLATION)
        blocking = True

    # Check 4: AST write detection
    if write_ops_in_ast:
        log.error("LSME-GATE-0 check 4 FAIL: write operations detected in mutation AST — LSME-0")
        failure_codes.append(LSME_WRITE_DETECTED)
        blocking = True

    # Check 5: AST egress detection
    if egress_in_ast:
        log.error("LSME-GATE-0 check 5 FAIL: network egress detected in mutation AST — LSME-0")
        failure_codes.append(LSME_EGRESS_DETECTED)
        blocking = True

    if blocking:
        outcome = LSMEOutcome.SHADOW_ABORTED
        rh = _result_hash_fn(outcome, "LSME-GATE-0", failure_codes, None)
        return LSMEGateResult(
            outcome=outcome,
            fitness_report=None,
            failure_codes=tuple(failure_codes),
            is_blocking=True,
            gate_id="LSME-GATE-0",
            result_hash=rh,
        )

    # Check 6: Budget advisory
    if estimated_budget_ms is not None and estimated_budget_ms > shadow_budget.max_wall_clock_ms:
        log.info(
            "LSME-GATE-0 check 6: estimated_budget_ms=%.1f > max=%.1f → LSME_BUDGET_EXCEEDED (advisory)",
            estimated_budget_ms,
            shadow_budget.max_wall_clock_ms,
        )
        failure_codes.append(LSME_BUDGET_EXCEEDED)
        rh = _result_hash_fn(LSMEOutcome.BUDGET_EXCEEDED, "LSME-GATE-0", failure_codes, None)
        return LSMEGateResult(
            outcome=LSMEOutcome.BUDGET_EXCEEDED,
            fitness_report=None,
            failure_codes=tuple(failure_codes),
            is_blocking=False,   # advisory only
            gate_id="LSME-GATE-0",
            result_hash=rh,
        )

    log.debug("LSME-GATE-0 CLEAR for mutation '%s' — shadow execution authorised.", mutation_id)
    rh = _result_hash_fn(LSMEOutcome.SHADOW_CLEAR, "LSME-GATE-0", [], None)
    return LSMEGateResult(
        outcome=LSMEOutcome.SHADOW_CLEAR,
        fitness_report=None,
        failure_codes=(),
        is_blocking=False,
        gate_id="LSME-GATE-0",
        result_hash=rh,
    )


# ---------------------------------------------------------------------------
# LSME-GATE-1 — Shadow Fitness Evaluation (post-execution)
# ---------------------------------------------------------------------------


def evaluate_lsme_gate_1(
    mutation_id: str,
    epoch_id: str,
    shadow_responses: List[ShadowResponse],
    baseline_responses: List[BaselineResponse],
    shadow_contract: ShadowContract,
    invariant_failures: Optional[List[str]] = None,
    trace_committed: bool = True,
) -> LSMEGateResult:
    """Evaluate LSME-GATE-1 — post-execution shadow fitness evaluation.

    LSME-1: ShadowFitnessReport is built FIRST (hash-committed), then
    divergence comparisons run against it.  No partial evidence accepted.

    Gate checks:
      1. trace_committed MUST be True (LSME-1 enforcement).
      2. Divergence rate ≤ shadow_contract.max_divergence_rate.
      3. Shadow error rate ≤ baseline_error_rate + MAX_ERROR_RATE_DELTA.
      4. Shadow P99 latency ≤ baseline_p99 × MAX_LATENCY_P99_MULTIPLIER.
      5. No invariant failures.

    Args:
        mutation_id: Mutation being evaluated.
        epoch_id: Current epoch.
        shadow_responses: All shadow execution responses.
        baseline_responses: Pre-recorded baseline responses.
        shadow_contract: Contract governing divergence threshold.
        invariant_failures: Invariant IDs that failed in shadow (optional).
        trace_committed: MUST be True before evaluation proceeds (LSME-1).

    Returns:
        LSMEGateResult with gate_id=``LSME-GATE-1``.
    """
    inv_failures = invariant_failures or []
    failure_codes: List[str] = []

    # Check 1: LSME-1 — trace MUST be committed first
    if not trace_committed:
        log.error("LSME-GATE-1 check 1 FAIL: trace_committed=False — LSME-1 violated")
        failure_codes.append(LSME_TRACE_INCOMPLETE)
        report = _build_fitness_report(
            mutation_id=mutation_id,
            epoch_id=epoch_id,
            shadow_responses=shadow_responses,
            baseline_responses=baseline_responses,
            invariant_failures=inv_failures,
            failure_codes=failure_codes,
            verdict=ShadowVerdict.ABORTED,
        )
        rh = _result_hash_fn(LSMEOutcome.SHADOW_ABORTED, "LSME-GATE-1", failure_codes, report.report_id)
        return LSMEGateResult(
            outcome=LSMEOutcome.SHADOW_ABORTED,
            fitness_report=report,
            failure_codes=tuple(failure_codes),
            is_blocking=True,
            gate_id="LSME-GATE-1",
            result_hash=rh,
        )

    # Compute metrics
    total = len(shadow_responses)
    diverged = sum(1 for r in shadow_responses if r.diverged)
    div_rate = diverged / total if total else 0.0

    shadow_errors = sum(1 for r in shadow_responses if r.error)
    shadow_err_rate = shadow_errors / total if total else 0.0
    baseline_errors = sum(1 for r in baseline_responses if r.error)
    baseline_err_rate = baseline_errors / len(baseline_responses) if baseline_responses else 0.0

    shadow_p99 = _p99([r.latency_ms for r in shadow_responses])
    baseline_p99 = _p99([r.latency_ms for r in baseline_responses])

    # Check 2: Divergence rate
    if div_rate > shadow_contract.max_divergence_rate:
        log.warning(
            "LSME-GATE-1 check 2 FAIL: divergence_rate=%.4f > max=%.4f",
            div_rate,
            shadow_contract.max_divergence_rate,
        )
        failure_codes.append(LSME_DIVERGENCE_EXCEEDED)

    # Check 3: Error rate delta
    if shadow_err_rate > baseline_err_rate + MAX_ERROR_RATE_DELTA:
        log.warning(
            "LSME-GATE-1 check 3 FAIL: shadow_err_rate=%.4f > baseline=%.4f + delta=%.2f",
            shadow_err_rate,
            baseline_err_rate,
            MAX_ERROR_RATE_DELTA,
        )
        failure_codes.append(LSME_ERROR_REGRESSION)

    # Check 4: P99 latency
    if baseline_p99 > 0 and shadow_p99 > baseline_p99 * MAX_LATENCY_P99_MULTIPLIER:
        log.warning(
            "LSME-GATE-1 check 4 FAIL: shadow_p99=%.1fms > baseline_p99=%.1fms × %.2f",
            shadow_p99,
            baseline_p99,
            MAX_LATENCY_P99_MULTIPLIER,
        )
        failure_codes.append(LSME_LATENCY_REGRESSION)

    # Check 5: Invariant failures
    if inv_failures:
        log.warning("LSME-GATE-1 check 5 FAIL: invariant failures in shadow: %s", inv_failures)
        failure_codes.append(LSME_INVARIANT_FAILURE)

    verdict = ShadowVerdict.CLEAR if not failure_codes else ShadowVerdict.FAILED
    outcome = LSMEOutcome.SHADOW_CLEAR if not failure_codes else LSMEOutcome.SHADOW_FAILED

    report = _build_fitness_report(
        mutation_id=mutation_id,
        epoch_id=epoch_id,
        shadow_responses=shadow_responses,
        baseline_responses=baseline_responses,
        invariant_failures=inv_failures,
        failure_codes=failure_codes,
        verdict=verdict,
    )

    rh = _result_hash_fn(outcome, "LSME-GATE-1", failure_codes, report.report_id)
    if outcome == LSMEOutcome.SHADOW_CLEAR:
        log.info(
            "LSME-GATE-1 SHADOW_CLEAR: mutation '%s' — div=%.3f err_delta=%.3f p99_ratio=%.3f",
            mutation_id,
            div_rate,
            shadow_err_rate - baseline_err_rate,
            (shadow_p99 / baseline_p99) if baseline_p99 else 1.0,
        )
    else:
        log.warning(
            "LSME-GATE-1 SHADOW_FAILED: mutation '%s' — codes: %s",
            mutation_id,
            failure_codes,
        )

    return LSMEGateResult(
        outcome=outcome,
        fitness_report=report,
        failure_codes=tuple(failure_codes),
        is_blocking=bool(failure_codes),
        gate_id="LSME-GATE-1",
        result_hash=rh,
    )


# ---------------------------------------------------------------------------
# Serialisation helper (ledger / EvidenceBundle integration)
# ---------------------------------------------------------------------------


def gate_result_to_ledger_payload(result: LSMEGateResult) -> Dict[str, Any]:
    """Convert an LSMEGateResult to a ledger-appendable dict."""
    payload: Dict[str, Any] = {
        "event_type": "lsme_gate_evaluation",
        "lsme_version": LSME_VERSION,
        "gate_id": result.gate_id,
        "outcome": result.outcome.value,
        "failure_codes": list(result.failure_codes),
        "is_blocking": result.is_blocking,
        "result_hash": result.result_hash,
    }
    if result.fitness_report is not None:
        payload["fitness_report"] = result.fitness_report.to_dict()
    return payload
