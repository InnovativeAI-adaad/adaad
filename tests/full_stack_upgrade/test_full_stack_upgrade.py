# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import json
from pathlib import Path

from app.dream_mode import DreamMode
from core.random_control import DeterministicSeedManager
from evolution.evolution_analytics import summarize_cycles
from evolution.evolution_scheduler import EvolutionScheduler, VariantRecord
from evolution.fitness import FitnessMetrics, weighted_fitness
from evolution.revenue_alignment import score_revenue_alignment
from evolution.rollback import VariantHealth, prune_variants, rollback_if_needed
from governance.mutation_ledger import LedgerEntry, MutationLedger
from governance.promotion_gate import PromotionPolicy, evaluate_promotion
from sandbox.sandbox_executor import SandboxExecutor, SandboxLimits


def test_seed_reproducibility_and_namespace_independence() -> None:
    manager = DeterministicSeedManager(42)
    assert manager.derive("a").seed == manager.derive("a").seed
    assert manager.derive("a").seed != manager.derive("b").seed


def test_sandbox_pass_fail_timeout_and_invariant_blocking() -> None:
    executor = SandboxExecutor(SandboxLimits(timeout_ms=1, memory_kb_limit=100))

    passed = executor.execute(lambda: {"memory_kb": 10, "invariant_results": {"signature_preserved": True, "behavior_preserved": True}, "fitness_score": 0.9, "revenue_score": 0.9})
    assert passed.status == "pass"

    timeout = executor.execute(lambda: {"memory_kb": 10, "invariant_results": {"signature_preserved": True, "behavior_preserved": True}})
    # elapsed can be 0 on very fast systems; force timeout with hard-coded check
    forced_timeout = SandboxExecutor(SandboxLimits(timeout_ms=-1)).execute(lambda: {"memory_kb": 1, "invariant_results": {"signature_preserved": True, "behavior_preserved": True}})
    assert forced_timeout.status == "timeout"
    assert timeout.status in {"pass", "timeout"}

    failed = executor.execute(lambda: {"memory_kb": 10, "invariant_results": {"signature_preserved": False, "behavior_preserved": True}})
    assert failed.status == "fail"


def test_dream_mode_aggression_clamps() -> None:
    assert DreamMode._clamp_aggression(-1) == 0.0
    assert DreamMode._clamp_aggression(2) == 1.0


def test_fitness_and_revenue_deterministic() -> None:
    revenue = score_revenue_alignment(market_impact=1.0, scalability=0.9, compute_efficiency=1.0)
    assert revenue > 0.95
    low = score_revenue_alignment(market_impact=0.1, scalability=0.1, compute_efficiency=0.0)
    assert low < 0.1

    metrics = FitnessMetrics(1.0, 0.5, 0.5, 0.5, 1.0)
    assert weighted_fitness(metrics) == weighted_fitness(metrics)
    assert weighted_fitness(metrics) == 0.75


def test_ledger_append_only_and_hash(tmp_path: Path) -> None:
    ledger = MutationLedger(tmp_path / "ledger.jsonl")
    entry = LedgerEntry(variant_id="v1", seed=7, metrics={"fitness": 0.8}, promoted=True)
    digest = ledger.append(entry)
    rows = ledger.entries()
    assert len(rows) == 1
    assert rows[0]["hash"] == digest
    assert rows[0]["prev_hash"].startswith("sha256:")
    assert rows[0]["canonical_payload_hash"].startswith("sha256:")
    assert rows[0]["signature_bundle"]["signing_key_id"]
    assert rows[0]["entry"]["variant_id"] == "v1"


def test_promotion_gate_and_scheduler_and_rollback() -> None:
    result_payload = {
        "memory_kb": 1,
        "invariant_results": {"signature_preserved": True, "behavior_preserved": True},
        "fitness_score": 0.7,
        "revenue_score": 0.7,
    }
    result = SandboxExecutor().execute(lambda: result_payload, variant_id="v1")
    decision = evaluate_promotion(result, PromotionPolicy(), ledger_hash="abc")
    assert decision.approved is True and decision.ledger_hash == "abc"

    fail_result = SandboxExecutor().execute(lambda: {**result_payload, "invariant_results": {"signature_preserved": False, "behavior_preserved": True}}, variant_id="v2")
    assert evaluate_promotion(fail_result, PromotionPolicy()).approved is False

    scheduler = EvolutionScheduler(DeterministicSeedManager(99))
    pool = [VariantRecord("v1", 0.6, 0.6), VariantRecord("v2", 0.8, 0.5), VariantRecord("v3", 0.8, 0.7)]
    picked = scheduler.run_epoch(1, pool, k=2)
    assert [p.variant_id for p in picked] == ["v3", "v2"]
    assert scheduler.history[0]["epoch"] == 1

    current = VariantHealth("v3", invariant_ok=False, fitness_score=0.8, revenue_score=0.7)
    assert rollback_if_needed(["v1", "v2", "v3"], current) == "v2"
    pruned = prune_variants([
        VariantHealth("v1", True, 0.3, 0.8),
        VariantHealth("v2", True, 0.8, 0.8),
    ], min_fitness=0.5, min_revenue=0.5)
    assert [v.variant_id for v in pruned] == ["v2"]


def test_evolution_analytics() -> None:
    report = summarize_cycles([
        {"fitness": 0.5, "efficiency": 0.8, "revenue": 0.4, "status": "pass"},
        {"fitness": 1.0, "efficiency": 0.2, "revenue": 0.6, "status": "fail"},
    ])
    assert json.loads(json.dumps(report))["avg_fitness"] == 0.75
    assert report["success_rate"] == 0.5
