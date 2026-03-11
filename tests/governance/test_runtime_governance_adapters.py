# SPDX-License-Identifier: Apache-2.0
"""Regression tests for runtime-governance canonicalization and adapter shims."""

from __future__ import annotations
import pytest
pytestmark = pytest.mark.governance_gate

from pathlib import Path

from governance import mutation_ledger as adapter_ledger
from governance import promotion_gate as adapter_promotion
from runtime.api import app_layer
from runtime.governance import mutation_ledger as runtime_ledger
from runtime.governance import promotion_gate as runtime_promotion
from sandbox.sandbox_executor import SandboxResult


def test_governance_ledger_adapter_re_exports_runtime_symbols() -> None:
    assert adapter_ledger.LedgerEntry is runtime_ledger.LedgerEntry
    assert adapter_ledger.MutationLedger is runtime_ledger.MutationLedger


def test_governance_promotion_adapter_re_exports_runtime_symbols() -> None:
    assert adapter_promotion.PromotionPolicy is runtime_promotion.PromotionPolicy
    assert adapter_promotion.PromotionDecision is runtime_promotion.PromotionDecision
    assert adapter_promotion.evaluate_promotion is runtime_promotion.evaluate_promotion


def test_app_layer_exports_required_governance_primitives() -> None:
    assert app_layer.GovernanceGate.__name__ == "GovernanceGate"
    assert app_layer.DeterministicAxisEvaluator.__name__ == "DeterministicAxisEvaluator"
    assert app_layer.RuntimeDirector.__name__ == "RuntimeDirector"
    assert app_layer.GovernanceDeniedError.__name__ == "GovernanceDeniedError"


def test_runtime_mutation_ledger_round_trip(tmp_path: Path) -> None:
    ledger = runtime_ledger.MutationLedger(tmp_path / "mutation_ledger.jsonl")
    entry = runtime_ledger.LedgerEntry(
        variant_id="variant-1",
        seed=7,
        metrics={"fitness": 0.9},
        promoted=True,
    )

    digest = ledger.append(entry)

    rows = ledger.entries()
    assert len(rows) == 1
    assert rows[0]["entry"]["variant_id"] == "variant-1"
    assert rows[0]["hash"] == digest


def test_runtime_promotion_gate_decision_paths() -> None:
    policy = runtime_promotion.PromotionPolicy(min_fitness=0.6, min_revenue=0.5)

    failed = runtime_promotion.evaluate_promotion(
        SandboxResult(variant_id="v1", execution_time_ms=1, memory_kb=1, status="fail", invariant_results={}, fitness_score=1.0, revenue_score=1.0),
        policy,
    )
    assert failed.reason == "sandbox_failed"

    approved = runtime_promotion.evaluate_promotion(
        SandboxResult(variant_id="v2", execution_time_ms=1, memory_kb=1, status="pass", invariant_results={}, fitness_score=0.9, revenue_score=0.8),
        policy,
        ledger_hash="abc",
    )
    assert approved.approved is True
    assert approved.ledger_hash == "abc"
