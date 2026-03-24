# SPDX-License-Identifier: Apache-2.0
"""Phase 91 — INNOV-07 · Live Shadow Mutation Execution (LSME).

Test ID format: T91-LSME-NN

20 tests covering:
  - T91-LSME-01..04  ShadowContract zero-write invariant (LSME-0)
  - T91-LSME-05..08  LSME-GATE-0 pass paths: clean contract, budget advisory
  - T91-LSME-09..11  LSME-GATE-0 block paths: write/egress AST detection
  - T91-LSME-12..15  LSME-GATE-1 pass path: SHADOW_CLEAR + ShadowFitnessReport
  - T91-LSME-16..18  LSME-GATE-1 block paths: divergence, error delta, latency P99
  - T91-LSME-19..20  LSME-1 invariant: trace_committed=False → ABORTED;
                     report_hash determinism
"""

from __future__ import annotations

import hashlib
from typing import List

import pytest

from runtime.evolution.lsme_engine import (
    DEFAULT_MAX_DIVERGENCE_RATE,
    LSME_BUDGET_EXCEEDED,
    LSME_CONTRACT_VIOLATION,
    LSME_DIVERGENCE_EXCEEDED,
    LSME_EGRESS_DETECTED,
    LSME_ERROR_REGRESSION,
    LSME_INVARIANT_FAILURE,
    LSME_LATENCY_REGRESSION,
    LSME_TRACE_INCOMPLETE,
    LSME_VERSION,
    LSME_WRITE_DETECTED,
    LSMEGateResult,
    LSMEOutcome,
    BaselineResponse,
    ShadowBudget,
    ShadowContract,
    ShadowFitnessReport,
    ShadowResponse,
    ShadowVerdict,
    evaluate_lsme_gate_0,
    evaluate_lsme_gate_1,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

MUT_ID = "MUT-SHADOW-001"
EPOCH_ID = "epoch-099"

GOOD_CONTRACT = ShadowContract(
    write_operations_permitted=False,
    network_egress_permitted=False,
    database_mutations_permitted=False,
    max_divergence_rate=DEFAULT_MAX_DIVERGENCE_RATE,
)

BUDGET = ShadowBudget(max_wall_clock_ms=5000.0, max_cpu_ms=3000.0, max_memory_mb=256.0, max_requests=50)


def _response_hash(req_id: str, mutated: bool = False) -> str:
    suffix = "MUTATED" if mutated else "BASELINE"
    return hashlib.sha256(f"{req_id}:{suffix}".encode()).hexdigest()


def _make_baseline(n: int = 10, error_rate: float = 0.0, latency: float = 20.0) -> List[BaselineResponse]:
    responses = []
    for i in range(n):
        is_error = i < int(n * error_rate)
        responses.append(BaselineResponse(
            request_id=f"REQ-{i:03d}",
            response_hash=_response_hash(f"REQ-{i:03d}"),
            error=is_error,
            latency_ms=latency,
        ))
    return responses


def _make_shadow(
    baseline: List[BaselineResponse],
    diverge_count: int = 0,
    error_count: int = 0,
    latency: float = 20.0,
) -> List[ShadowResponse]:
    responses = []
    for i, b in enumerate(baseline):
        is_error = i < error_count
        diverged = i < diverge_count
        responses.append(ShadowResponse(
            request_id=b.request_id,
            response_hash=_response_hash(b.request_id, mutated=diverged),
            error=is_error,
            latency_ms=latency,
            diverged=diverged,
        ))
    return responses


# ---------------------------------------------------------------------------
# T91-LSME-01 — ShadowContract.is_zero_write() True for correct contract
# ---------------------------------------------------------------------------


def test_t91_lsme_01_zero_write_contract_valid():
    """T91-LSME-01: GOOD_CONTRACT.is_zero_write() returns True."""
    assert GOOD_CONTRACT.is_zero_write() is True


# ---------------------------------------------------------------------------
# T91-LSME-02 — ShadowContract.is_zero_write() False when write allowed
# ---------------------------------------------------------------------------


def test_t91_lsme_02_zero_write_fails_when_write_permitted():
    """T91-LSME-02: is_zero_write() returns False if write_operations_permitted=True."""
    bad = ShadowContract(
        write_operations_permitted=True,
        network_egress_permitted=False,
        database_mutations_permitted=False,
    )
    assert bad.is_zero_write() is False


# ---------------------------------------------------------------------------
# T91-LSME-03 — ShadowContract.is_zero_write() False when egress allowed
# ---------------------------------------------------------------------------


def test_t91_lsme_03_zero_write_fails_when_egress_permitted():
    """T91-LSME-03: is_zero_write() False if network_egress_permitted=True."""
    bad = ShadowContract(
        write_operations_permitted=False,
        network_egress_permitted=True,
        database_mutations_permitted=False,
    )
    assert bad.is_zero_write() is False


# ---------------------------------------------------------------------------
# T91-LSME-04 — ShadowContract.is_zero_write() False when DB write allowed
# ---------------------------------------------------------------------------


def test_t91_lsme_04_zero_write_fails_when_db_write_permitted():
    """T91-LSME-04: is_zero_write() False if database_mutations_permitted=True."""
    bad = ShadowContract(
        write_operations_permitted=False,
        network_egress_permitted=False,
        database_mutations_permitted=True,
    )
    assert bad.is_zero_write() is False


# ---------------------------------------------------------------------------
# T91-LSME-05 — GATE-0 CLEAR on clean contract
# ---------------------------------------------------------------------------


def test_t91_lsme_05_gate0_clear_clean_contract():
    """T91-LSME-05: clean zero-write contract → LSME_SHADOW_CLEAR."""
    result = evaluate_lsme_gate_0(MUT_ID, GOOD_CONTRACT, BUDGET)
    assert result.outcome == LSMEOutcome.SHADOW_CLEAR
    assert not result.failure_codes
    assert result.is_blocking is False
    assert result.gate_id == "LSME-GATE-0"


# ---------------------------------------------------------------------------
# T91-LSME-06 — GATE-0 returns LSMEGateResult type
# ---------------------------------------------------------------------------


def test_t91_lsme_06_gate0_returns_correct_type():
    """T91-LSME-06: evaluate_lsme_gate_0 always returns LSMEGateResult."""
    result = evaluate_lsme_gate_0(MUT_ID, GOOD_CONTRACT, BUDGET)
    assert isinstance(result, LSMEGateResult)
    assert isinstance(result.failure_codes, tuple)
    assert len(result.result_hash) == 64


# ---------------------------------------------------------------------------
# T91-LSME-07 — GATE-0 budget advisory is non-blocking
# ---------------------------------------------------------------------------


def test_t91_lsme_07_gate0_budget_exceeded_non_blocking():
    """T91-LSME-07: estimated_budget_ms > max → BUDGET_EXCEEDED; is_blocking=False."""
    result = evaluate_lsme_gate_0(
        MUT_ID, GOOD_CONTRACT, BUDGET, estimated_budget_ms=99999.0
    )
    assert result.outcome == LSMEOutcome.BUDGET_EXCEEDED
    assert LSME_BUDGET_EXCEEDED in result.failure_codes
    assert result.is_blocking is False


# ---------------------------------------------------------------------------
# T91-LSME-08 — GATE-0 within budget is CLEAR
# ---------------------------------------------------------------------------


def test_t91_lsme_08_gate0_within_budget_clear():
    """T91-LSME-08: estimated_budget_ms within limit → CLEAR."""
    result = evaluate_lsme_gate_0(
        MUT_ID, GOOD_CONTRACT, BUDGET, estimated_budget_ms=100.0
    )
    assert result.outcome == LSMEOutcome.SHADOW_CLEAR


# ---------------------------------------------------------------------------
# T91-LSME-09 — GATE-0 ABORTED: write_operations_permitted=True in contract
# ---------------------------------------------------------------------------


def test_t91_lsme_09_gate0_aborted_bad_contract_write():
    """T91-LSME-09: write_operations_permitted=True → LSME_CONTRACT_VIOLATION, blocking."""
    bad_contract = ShadowContract(
        write_operations_permitted=True,
        network_egress_permitted=False,
        database_mutations_permitted=False,
    )
    result = evaluate_lsme_gate_0(MUT_ID, bad_contract, BUDGET)
    assert result.outcome == LSMEOutcome.SHADOW_ABORTED
    assert LSME_CONTRACT_VIOLATION in result.failure_codes
    assert result.is_blocking is True


# ---------------------------------------------------------------------------
# T91-LSME-10 — GATE-0 ABORTED: write_ops_in_ast=True (AST scan)
# ---------------------------------------------------------------------------


def test_t91_lsme_10_gate0_aborted_ast_write_detected():
    """T91-LSME-10: write_ops_in_ast=True → LSME_WRITE_DETECTED, blocking."""
    result = evaluate_lsme_gate_0(MUT_ID, GOOD_CONTRACT, BUDGET, write_ops_in_ast=True)
    assert result.outcome == LSMEOutcome.SHADOW_ABORTED
    assert LSME_WRITE_DETECTED in result.failure_codes
    assert result.is_blocking is True


# ---------------------------------------------------------------------------
# T91-LSME-11 — GATE-0 ABORTED: egress_in_ast=True
# ---------------------------------------------------------------------------


def test_t91_lsme_11_gate0_aborted_egress_detected():
    """T91-LSME-11: egress_in_ast=True → LSME_EGRESS_DETECTED, blocking."""
    result = evaluate_lsme_gate_0(MUT_ID, GOOD_CONTRACT, BUDGET, egress_in_ast=True)
    assert result.outcome == LSMEOutcome.SHADOW_ABORTED
    assert LSME_EGRESS_DETECTED in result.failure_codes
    assert result.is_blocking is True


# ---------------------------------------------------------------------------
# T91-LSME-12 — GATE-1 SHADOW_CLEAR on perfect shadow
# ---------------------------------------------------------------------------


def test_t91_lsme_12_gate1_clear_perfect_shadow():
    """T91-LSME-12: zero divergence, no errors, same latency → SHADOW_CLEAR."""
    baseline = _make_baseline(10)
    shadow = _make_shadow(baseline, diverge_count=0, error_count=0, latency=20.0)
    result = evaluate_lsme_gate_1(MUT_ID, EPOCH_ID, shadow, baseline, GOOD_CONTRACT)
    assert result.outcome == LSMEOutcome.SHADOW_CLEAR
    assert not result.failure_codes
    assert result.is_blocking is False
    assert result.fitness_report is not None


# ---------------------------------------------------------------------------
# T91-LSME-13 — ShadowFitnessReport has correct structure
# ---------------------------------------------------------------------------


def test_t91_lsme_13_fitness_report_structure():
    """T91-LSME-13: ShadowFitnessReport fields are complete and typed."""
    baseline = _make_baseline(10)
    shadow = _make_shadow(baseline)
    result = evaluate_lsme_gate_1(MUT_ID, EPOCH_ID, shadow, baseline, GOOD_CONTRACT)
    r = result.fitness_report
    assert isinstance(r, ShadowFitnessReport)
    assert r.mutation_id == MUT_ID
    assert r.epoch_id == EPOCH_ID
    assert r.total_requests == 10
    assert r.verdict == ShadowVerdict.CLEAR
    assert r.lsme_version == LSME_VERSION
    assert len(r.report_hash) == 64


# ---------------------------------------------------------------------------
# T91-LSME-14 — report_hash is deterministic
# ---------------------------------------------------------------------------


def test_t91_lsme_14_report_hash_deterministic():
    """T91-LSME-14: identical inputs → identical report_hash."""
    baseline = _make_baseline(10)
    shadow = _make_shadow(baseline)
    r1 = evaluate_lsme_gate_1(MUT_ID, EPOCH_ID, shadow, baseline, GOOD_CONTRACT)
    r2 = evaluate_lsme_gate_1(MUT_ID, EPOCH_ID, shadow, baseline, GOOD_CONTRACT)
    assert r1.fitness_report.report_hash == r2.fitness_report.report_hash


# ---------------------------------------------------------------------------
# T91-LSME-15 — GATE-1 CLEAR with divergence below threshold
# ---------------------------------------------------------------------------


def test_t91_lsme_15_gate1_clear_below_divergence_threshold():
    """T91-LSME-15: divergence_rate below max_divergence_rate → SHADOW_CLEAR."""
    baseline = _make_baseline(100)
    # 4 of 100 diverge = 4% < 5% threshold
    shadow = _make_shadow(baseline, diverge_count=4)
    result = evaluate_lsme_gate_1(MUT_ID, EPOCH_ID, shadow, baseline, GOOD_CONTRACT)
    assert result.outcome == LSMEOutcome.SHADOW_CLEAR
    assert result.fitness_report.divergence_rate == pytest.approx(0.04, abs=1e-6)


# ---------------------------------------------------------------------------
# T91-LSME-16 — GATE-1 FAILED: divergence rate exceeded
# ---------------------------------------------------------------------------


def test_t91_lsme_16_gate1_failed_divergence_exceeded():
    """T91-LSME-16: divergence_rate > max_divergence_rate → LSME_DIVERGENCE_EXCEEDED."""
    baseline = _make_baseline(20)
    # 4 of 20 diverge = 20% >> 5%
    shadow = _make_shadow(baseline, diverge_count=4)
    result = evaluate_lsme_gate_1(MUT_ID, EPOCH_ID, shadow, baseline, GOOD_CONTRACT)
    assert result.outcome == LSMEOutcome.SHADOW_FAILED
    assert LSME_DIVERGENCE_EXCEEDED in result.failure_codes
    assert result.is_blocking is True


# ---------------------------------------------------------------------------
# T91-LSME-17 — GATE-1 FAILED: error regression
# ---------------------------------------------------------------------------


def test_t91_lsme_17_gate1_failed_error_regression():
    """T91-LSME-17: shadow error rate > baseline + 1% → LSME_ERROR_REGRESSION."""
    baseline = _make_baseline(100, error_rate=0.0)  # 0 errors
    # 5 shadow errors on 100 requests = 5% >> 0% + 1%
    shadow = _make_shadow(baseline, error_count=5, latency=20.0)
    result = evaluate_lsme_gate_1(MUT_ID, EPOCH_ID, shadow, baseline, GOOD_CONTRACT)
    assert result.outcome == LSMEOutcome.SHADOW_FAILED
    assert LSME_ERROR_REGRESSION in result.failure_codes


# ---------------------------------------------------------------------------
# T91-LSME-18 — GATE-1 FAILED: P99 latency regression
# ---------------------------------------------------------------------------


def test_t91_lsme_18_gate1_failed_latency_regression():
    """T91-LSME-18: shadow P99 > baseline P99 × 1.10 → LSME_LATENCY_REGRESSION."""
    baseline = _make_baseline(100, latency=100.0)
    # Shadow runs at 130ms P99 (30% regression)
    shadow = _make_shadow(baseline, latency=130.0)
    result = evaluate_lsme_gate_1(MUT_ID, EPOCH_ID, shadow, baseline, GOOD_CONTRACT)
    assert result.outcome == LSMEOutcome.SHADOW_FAILED
    assert LSME_LATENCY_REGRESSION in result.failure_codes


# ---------------------------------------------------------------------------
# T91-LSME-19 — LSME-1: trace_committed=False → SHADOW_ABORTED
# ---------------------------------------------------------------------------


def test_t91_lsme_19_gate1_aborted_trace_not_committed():
    """T91-LSME-19: LSME-1 — trace_committed=False always → SHADOW_ABORTED."""
    baseline = _make_baseline(10)
    shadow = _make_shadow(baseline)
    result = evaluate_lsme_gate_1(
        MUT_ID, EPOCH_ID, shadow, baseline, GOOD_CONTRACT, trace_committed=False
    )
    assert result.outcome == LSMEOutcome.SHADOW_ABORTED
    assert LSME_TRACE_INCOMPLETE in result.failure_codes
    assert result.is_blocking is True
    # Report is still produced for evidence archival
    assert result.fitness_report is not None
    assert result.fitness_report.verdict == ShadowVerdict.ABORTED


# ---------------------------------------------------------------------------
# T91-LSME-20 — GATE-1 FAILED: invariant failures detected in shadow
# ---------------------------------------------------------------------------


def test_t91_lsme_20_gate1_failed_invariant_failures():
    """T91-LSME-20: invariant failures in shadow execution → LSME_INVARIANT_FAILURE."""
    baseline = _make_baseline(10)
    shadow = _make_shadow(baseline)
    result = evaluate_lsme_gate_1(
        MUT_ID, EPOCH_ID, shadow, baseline, GOOD_CONTRACT,
        invariant_failures=["CONC-0", "CSAP-1"],
    )
    assert result.outcome == LSMEOutcome.SHADOW_FAILED
    assert LSME_INVARIANT_FAILURE in result.failure_codes
    assert result.fitness_report.invariant_failures == ("CONC-0", "CSAP-1")
