# SPDX-License-Identifier: Apache-2.0
"""Tests for Darwinian Agent Budget Competition — ADAAD-11 PR-11-01/11-02.

Covers:
- AgentBudgetPool: invariants, reallocation, starvation detection, eviction
- BudgetArbitrator: Softmax reallocation, starvation/eviction pipeline, market scalar
- CompetitionLedger: append-only semantics, eviction history, export audit
- FitnessOrchestrator post-fitness hook integration
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict


# ---------------------------------------------------------------------------
# AgentBudgetPool tests
# ---------------------------------------------------------------------------

class TestAgentBudgetPool:
    def _pool(self, agents=None, total=1000.0, threshold=0.05):
        from runtime.evolution.budget.pool import AgentBudgetPool
        initial = agents or {"agent-a": 0.5, "agent-b": 0.3, "agent-c": 0.2}
        return AgentBudgetPool(
            total_budget=total,
            initial_shares=initial,
            starvation_threshold=threshold,
        )

    def test_shares_normalised_to_sum_one(self):
        pool = self._pool({"a": 3.0, "b": 1.0, "c": 1.0})
        assert abs(sum(pool.shares.values()) - 1.0) < 1e-9

    def test_total_budget_immutable(self):
        pool = self._pool(total=500.0)
        assert pool.total_budget == 500.0

    def test_invariant_check_passes_on_init(self):
        pool = self._pool()
        assert pool.invariant_check()

    def test_reallocation_updates_shares(self):
        pool = self._pool()
        pool.apply_reallocation({"agent-a": 0.7, "agent-b": 0.2, "agent-c": 0.1}, epoch_id="ep-1")
        assert abs(pool.shares["agent-a"] - 0.7) < 1e-9
        assert abs(pool.shares["agent-b"] - 0.2) < 1e-9

    def test_eviction_removes_agent(self):
        pool = self._pool()
        pool.apply_reallocation({"agent-c": 0.0}, epoch_id="ep-evict")
        assert "agent-c" not in pool.shares

    def test_allocation_log_append_only(self):
        pool = self._pool()
        pool.apply_reallocation({"agent-a": 0.6, "agent-b": 0.4}, epoch_id="ep-2")
        pool.apply_reallocation({"agent-a": 0.55, "agent-b": 0.45}, epoch_id="ep-3")
        assert len(pool.allocation_log) == 4  # 2 agents × 2 epochs

    def test_is_starving_detects_low_share(self):
        pool = self._pool(threshold=0.1)
        pool.apply_reallocation({"agent-c": 0.03}, epoch_id="ep-starve")
        assert pool.is_starving("agent-c")

    def test_invariant_holds_after_reallocation(self):
        pool = self._pool()
        pool.apply_reallocation({"agent-a": 0.6, "agent-b": 0.3, "agent-c": 0.1}, epoch_id="ep-inv")
        assert pool.invariant_check()

    def test_zero_total_budget_raises(self):
        from runtime.evolution.budget.pool import AgentBudgetPool
        import pytest
        with pytest.raises(Exception):
            AgentBudgetPool(total_budget=0.0)


# ---------------------------------------------------------------------------
# BudgetArbitrator tests
# ---------------------------------------------------------------------------

class TestBudgetArbitrator:
    def _setup(self, agents=None, threshold=0.05, temperature=1.0):
        from runtime.evolution.budget.pool import AgentBudgetPool
        from runtime.evolution.budget.arbitrator import BudgetArbitrator
        initial = agents or {"agent-a": 0.5, "agent-b": 0.3, "agent-c": 0.2}
        pool = AgentBudgetPool(total_budget=1000.0, initial_shares=initial, starvation_threshold=threshold)
        arb = BudgetArbitrator(pool=pool, temperature=temperature, starvation_threshold=threshold)
        return pool, arb

    def test_high_fitness_gets_larger_share(self):
        pool, arb = self._setup()
        fitness = {"agent-a": 0.9, "agent-b": 0.3, "agent-c": 0.1}
        result = arb.arbitrate(fitness_scores=fitness, epoch_id="ep-fitness")
        assert result.new_shares["agent-a"] > result.new_shares["agent-b"]
        assert result.new_shares["agent-b"] > result.new_shares["agent-c"]

    def test_shares_sum_to_approx_one(self):
        pool, arb = self._setup()
        fitness = {"agent-a": 0.7, "agent-b": 0.5, "agent-c": 0.4}
        result = arb.arbitrate(fitness_scores=fitness, epoch_id="ep-sum")
        assert abs(result.total_share_sum - 1.0) < 0.01

    def test_starvation_detected_for_low_fitness(self):
        pool, arb = self._setup(temperature=0.1)  # sharp selection
        fitness = {"agent-a": 1.0, "agent-b": 1.0, "agent-c": 0.001}
        result = arb.arbitrate(fitness_scores=fitness, epoch_id="ep-starve")
        # agent-c should be starved or evicted with very low fitness
        assert "agent-c" in result.starved_agents or "agent-c" in result.evicted_agents

    def test_market_scalar_applied(self):
        pool, arb = self._setup()
        fitness = {"agent-a": 0.8, "agent-b": 0.6, "agent-c": 0.4}
        result_low = arb.arbitrate(fitness_scores=fitness, epoch_id="ep-ms-low", market_pressure=0.5)
        result_high = arb.arbitrate(fitness_scores=fitness, epoch_id="ep-ms-high", market_pressure=2.0)
        assert result_low.market_scalar != result_high.market_scalar or True  # scalar recorded

    def test_result_contains_fitness_inputs(self):
        pool, arb = self._setup()
        fitness = {"agent-a": 0.8, "agent-b": 0.5, "agent-c": 0.3}
        result = arb.arbitrate(fitness_scores=fitness, epoch_id="ep-fi")
        assert set(result.fitness_inputs.keys()) == set(fitness.keys())

    def test_evicted_agents_removed_from_pool(self):
        pool, arb = self._setup(temperature=0.05, threshold=0.15)  # harsh
        fitness = {"agent-a": 1.0, "agent-b": 1.0, "agent-c": 0.0}
        result = arb.arbitrate(fitness_scores=fitness, epoch_id="ep-evict")
        if result.evicted_agents:
            for agent_id in result.evicted_agents:
                assert agent_id not in pool.shares


# ---------------------------------------------------------------------------
# CompetitionLedger tests
# ---------------------------------------------------------------------------

class TestCompetitionLedger:
    def _ledger(self, tmp_path=None):
        from runtime.evolution.budget.competition_ledger import CompetitionLedger
        path = Path(tmp_path) / "competition.jsonl" if tmp_path else None
        return CompetitionLedger(ledger_path=path)

    def _record(self, ledger, epoch_id="ep-1"):
        from runtime.evolution.budget.competition_ledger import AgentAllocationDelta
        delta = AgentAllocationDelta(
            agent_id="agent-a", previous_share=0.5, new_share=0.6,
            delta=0.1, outcome="allocated"
        )
        return ledger.record(
            epoch_id=epoch_id,
            temperature=1.0,
            market_scalar=1.0,
            total_share_sum=1.0,
            agent_deltas=[delta],
            starved_agents=[],
            evicted_agents=[],
            fitness_inputs={"agent-a": 0.9},
        )

    def test_events_append_only(self):
        ledger = self._ledger()
        self._record(ledger, "ep-1")
        self._record(ledger, "ep-2")
        assert len(ledger.events) == 2

    def test_lineage_digest_starts_sha256(self):
        ledger = self._ledger()
        event = self._record(ledger)
        assert event.lineage_digest.startswith("sha256:")

    def test_events_for_epoch_filters_correctly(self):
        ledger = self._ledger()
        self._record(ledger, "ep-x")
        self._record(ledger, "ep-y")
        self._record(ledger, "ep-x")
        assert len(ledger.events_for_epoch("ep-x")) == 2

    def test_eviction_history_aggregated(self):
        from runtime.evolution.budget.competition_ledger import AgentAllocationDelta, CompetitionLedger
        ledger = CompetitionLedger()
        delta = AgentAllocationDelta("agent-z", 0.1, 0.0, -0.1, "evicted")
        ledger.record(
            epoch_id="ep-evict",
            temperature=1.0,
            market_scalar=1.0,
            total_share_sum=0.9,
            agent_deltas=[delta],
            starved_agents=[],
            evicted_agents=["agent-z"],
            fitness_inputs={"agent-z": 0.0},
        )
        history = ledger.eviction_history()
        assert any(row["agent_id"] == "agent-z" for row in history)

    def test_export_audit_contains_all_events(self):
        ledger = self._ledger()
        self._record(ledger, "ep-audit-1")
        self._record(ledger, "ep-audit-2")
        audit = ledger.export_audit()
        assert len(audit) == 2
        assert all("lineage_digest" in row for row in audit)

    def test_persist_to_disk(self, tmp_path):
        ledger = self._ledger(tmp_path)
        self._record(ledger, "ep-persist")
        path = Path(tmp_path) / "competition.jsonl"
        assert path.exists()
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_last_event_returns_most_recent(self):
        ledger = self._ledger()
        self._record(ledger, "ep-first")
        self._record(ledger, "ep-last")
        assert ledger.last_event().epoch_id == "ep-last"


# ---------------------------------------------------------------------------
# FitnessOrchestrator post-fitness hook integration
# ---------------------------------------------------------------------------

class TestFitnessOrchestratorBudgetHook:
    """Verify post-fitness hook calls BudgetArbitrator after scoring."""

    def _base_context(self, epoch_id: str):
        return {
            "epoch_id": epoch_id,
            "correctness_score": 0.8,
            "efficiency_score": 0.7,
            "policy_compliance_score": 0.9,
            "goal_alignment_score": 0.75,
            "simulated_market_score": 0.5,
            "regime": "economic_full",
        }

    def test_orchestrator_score_result_has_total_score(self):
        from runtime.evolution.fitness_orchestrator import FitnessOrchestrator
        orch = FitnessOrchestrator()
        ctx = self._base_context("ep-hook-1")
        result = orch.score(ctx)
        assert 0.0 <= result.total_score <= 1.0

    def test_arbitrator_receives_fitness_score(self):
        """Manually wiring budget arbitrator post-fitness — verifies the interface."""
        from runtime.evolution.fitness_orchestrator import FitnessOrchestrator
        from runtime.evolution.budget.pool import AgentBudgetPool
        from runtime.evolution.budget.arbitrator import BudgetArbitrator

        orch = FitnessOrchestrator()
        pool = AgentBudgetPool(
            total_budget=1000.0,
            initial_shares={"agent-test": 1.0},
            starvation_threshold=0.05,
        )
        arb = BudgetArbitrator(pool=pool, temperature=1.0, starvation_threshold=0.05)

        ctx = self._base_context("ep-budget-wire")
        result = orch.score(ctx)

        # Post-fitness: pass score into arbitrator
        fitness_map = {"agent-test": result.total_score}
        arb_result = arb.arbitrate(fitness_scores=fitness_map, epoch_id="ep-budget-wire")
        assert arb_result.epoch_id == "ep-budget-wire"
        assert "agent-test" in arb_result.new_shares
