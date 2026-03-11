# SPDX-License-Identifier: Apache-2.0
"""Tests: Epoch Replay Simulator — ADAAD-8 / PR-11

Tests cover:
- Isolation invariant: simulation=False policy raises SimulationIsolationError
- Per-epoch simulation: all constraint types filter correctly
- Determinism: identical inputs → identical results
- Scoring version binding: version propagated from epoch record
- Epoch range simulation: aggregate metrics are correct
- Run digest and policy digest are deterministic
- Empty epoch / empty policy edge cases
- No ledger writes during simulation (isolation assertion)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
pytestmark = pytest.mark.governance_gate
from unittest.mock import MagicMock, patch

from runtime.governance.simulation.constraint_interpreter import (
    SimulationPolicy,
    SimulationPolicyError,
    interpret_policy_block,
)
from runtime.governance.simulation.epoch_simulator import (
    EpochReplaySimulator,
    EpochSimulationResult,
    SimulationRunResult,
    SimulationIsolationError,
    _assert_simulation_flag,
    _evaluate_mutation_under_policy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_policy() -> SimulationPolicy:
    return interpret_policy_block("")


def _make_mutation(
    mutation_id: str = "mut-001",
    risk_score: float = 0.2,
    complexity_delta: float = 0.05,
    lineage_depth: int = 3,
    test_coverage: float = 0.90,
    tier: str = "standard",
    entropy: float = 0.1,
) -> dict:
    return {
        "mutation_id": mutation_id,
        "risk_score": risk_score,
        "complexity_delta": complexity_delta,
        "lineage_depth": lineage_depth,
        "test_coverage": test_coverage,
        "tier": tier,
        "entropy": entropy,
    }


def _make_epoch(
    epoch_id: str = "epoch-001",
    mutations: list | None = None,
    actual_mutations_advanced: int | None = None,
    entropy: float = 0.1,
    scoring_algorithm_version: str = "1.0",
) -> dict:
    muts = mutations if mutations is not None else [_make_mutation()]
    return {
        "epoch_id": epoch_id,
        "mutations": muts,
        "actual_mutations_advanced": actual_mutations_advanced if actual_mutations_advanced is not None else len(muts),
        "entropy": entropy,
        "scoring_algorithm_version": scoring_algorithm_version,
    }


# ---------------------------------------------------------------------------
# Isolation invariant
# ---------------------------------------------------------------------------

class TestSimulationIsolation:
    def test_assert_simulation_flag_raises_on_false(self):
        """_assert_simulation_flag raises SimulationIsolationError for any object with simulation=False."""
        fake = type("FakePolicy", (), {"simulation": False})()
        with pytest.raises(SimulationIsolationError):
            _assert_simulation_flag(fake)

    def test_simulator_construction_raises_on_false_policy(self):
        with pytest.raises((SimulationIsolationError, SimulationPolicyError)):
            # SimulationPolicy(simulation=False) raises SimulationPolicyError at construction
            EpochReplaySimulator(SimulationPolicy(simulation=False))  # type: ignore

    def test_simulator_accepts_true_policy(self):
        policy = _empty_policy()
        sim = EpochReplaySimulator(policy)
        assert sim.policy.simulation is True

    def test_no_ledger_writes_during_simulation(self):
        """Simulation must not call any journal/ledger write functions."""
        policy = interpret_policy_block("max_risk_score(threshold=0.9)")
        sim = EpochReplaySimulator(policy)
        epoch = _make_epoch()

        import security.ledger.journal as journal_module
        original_append = journal_module.append_tx

        calls = []
        def tracking_append(*args, **kwargs):
            calls.append(args)
            return original_append(*args, **kwargs)

        with patch.object(journal_module, "append_tx", side_effect=tracking_append):
            sim.simulate_epoch("epoch-001", epoch_data=epoch)

        assert calls == [], f"Unexpected ledger writes during simulation: {calls}"


# ---------------------------------------------------------------------------
# Mutation-level constraint evaluation
# ---------------------------------------------------------------------------

class TestMutationConstraintEvaluation:
    def test_empty_policy_passes_all(self):
        policy = _empty_policy()
        mutation = _make_mutation(risk_score=0.9, complexity_delta=0.5)
        passes, reason = _evaluate_mutation_under_policy(mutation, policy)
        assert passes is True

    def test_max_risk_score_blocks_high_risk(self):
        policy = interpret_policy_block("max_risk_score(threshold=0.5)")
        mutation = _make_mutation(risk_score=0.7)
        passes, reason = _evaluate_mutation_under_policy(mutation, policy)
        assert passes is False
        assert "risk_score" in reason

    def test_max_risk_score_passes_low_risk(self):
        policy = interpret_policy_block("max_risk_score(threshold=0.5)")
        mutation = _make_mutation(risk_score=0.3)
        passes, _ = _evaluate_mutation_under_policy(mutation, policy)
        assert passes is True

    def test_max_complexity_delta_blocks(self):
        policy = interpret_policy_block("max_complexity_delta(delta=0.10)")
        mutation = _make_mutation(complexity_delta=0.25)
        passes, reason = _evaluate_mutation_under_policy(mutation, policy)
        assert passes is False
        assert "complexity_delta" in reason

    def test_min_test_coverage_blocks_low_coverage(self):
        policy = interpret_policy_block("min_test_coverage(threshold=0.85)")
        mutation = _make_mutation(test_coverage=0.70)
        passes, reason = _evaluate_mutation_under_policy(mutation, policy)
        assert passes is False
        assert "test_coverage" in reason

    def test_freeze_tier_blocks_frozen_tier(self):
        policy = interpret_policy_block("freeze_tier(tier=PRODUCTION)")
        mutation = _make_mutation(tier="PRODUCTION")
        passes, reason = _evaluate_mutation_under_policy(mutation, policy)
        assert passes is False
        assert "PRODUCTION" in reason

    def test_freeze_tier_passes_non_frozen_tier(self):
        policy = interpret_policy_block("freeze_tier(tier=PRODUCTION)")
        mutation = _make_mutation(tier="SANDBOX")
        passes, _ = _evaluate_mutation_under_policy(mutation, policy)
        assert passes is True

    def test_require_lineage_depth_blocks_shallow(self):
        policy = interpret_policy_block("require_lineage_depth(min=5)")
        mutation = _make_mutation(lineage_depth=2)
        passes, reason = _evaluate_mutation_under_policy(mutation, policy)
        assert passes is False
        assert "lineage_depth" in reason

    def test_require_lineage_depth_passes_deep(self):
        policy = interpret_policy_block("require_lineage_depth(min=3)")
        mutation = _make_mutation(lineage_depth=5)
        passes, _ = _evaluate_mutation_under_policy(mutation, policy)
        assert passes is True


# ---------------------------------------------------------------------------
# Epoch-level simulation
# ---------------------------------------------------------------------------

class TestEpochSimulation:
    def test_empty_epoch_produces_zero_results(self):
        policy = _empty_policy()
        sim = EpochReplaySimulator(policy)
        epoch = _make_epoch(mutations=[], actual_mutations_advanced=0)
        result = sim.simulate_epoch("epoch-empty", epoch_data=epoch)
        assert result.simulated_mutations_advanced == 0
        assert result.blocked_by_simulation == []
        assert result.velocity_delta_pct == 0.0

    def test_all_mutations_pass_under_empty_policy(self):
        policy = _empty_policy()
        sim = EpochReplaySimulator(policy)
        muts = [_make_mutation(f"mut-{i}") for i in range(5)]
        epoch = _make_epoch(mutations=muts, actual_mutations_advanced=5)
        result = sim.simulate_epoch("epoch-001", epoch_data=epoch)
        assert result.simulated_mutations_advanced == 5
        assert result.blocked_by_simulation == []

    def test_high_risk_mutations_blocked(self):
        policy = interpret_policy_block("max_risk_score(threshold=0.3)")
        sim = EpochReplaySimulator(policy)
        muts = [
            _make_mutation("mut-pass", risk_score=0.2),
            _make_mutation("mut-block", risk_score=0.8),
        ]
        epoch = _make_epoch(mutations=muts, actual_mutations_advanced=2)
        result = sim.simulate_epoch("epoch-001", epoch_data=epoch)
        assert result.simulated_mutations_advanced == 1
        assert "mut-block" in result.blocked_by_simulation
        assert "mut-pass" not in result.blocked_by_simulation

    def test_max_mutations_per_epoch_ceiling(self):
        policy = interpret_policy_block("max_mutations_per_epoch(count=2)")
        sim = EpochReplaySimulator(policy)
        muts = [_make_mutation(f"mut-{i}") for i in range(5)]
        epoch = _make_epoch(mutations=muts, actual_mutations_advanced=5)
        result = sim.simulate_epoch("epoch-001", epoch_data=epoch)
        assert result.simulated_mutations_advanced == 2

    def test_velocity_delta_negative_when_more_blocked(self):
        policy = interpret_policy_block("max_risk_score(threshold=0.1)")
        sim = EpochReplaySimulator(policy)
        muts = [_make_mutation(f"mut-{i}", risk_score=0.5) for i in range(4)]
        epoch = _make_epoch(mutations=muts, actual_mutations_advanced=4)
        result = sim.simulate_epoch("epoch-001", epoch_data=epoch)
        assert result.velocity_delta_pct < 0.0

    def test_governance_health_score_bounded(self):
        policy = interpret_policy_block("max_risk_score(threshold=0.9)")
        sim = EpochReplaySimulator(policy)
        epoch = _make_epoch()
        result = sim.simulate_epoch("epoch-001", epoch_data=epoch)
        assert 0.0 <= result.governance_health_score <= 1.0

    def test_scoring_version_bound_from_epoch_record(self):
        policy = _empty_policy()
        sim = EpochReplaySimulator(policy)
        epoch = _make_epoch(scoring_algorithm_version="2.0")
        result = sim.simulate_epoch("epoch-001", epoch_data=epoch)
        assert result.scoring_algorithm_version == "2.0"

    def test_unknown_epoch_id_returns_zero_state(self):
        policy = _empty_policy()
        sim = EpochReplaySimulator(policy, replay_engine=None)
        result = sim.simulate_epoch("epoch-nonexistent")
        assert result.epoch_id == "epoch-nonexistent"
        assert result.simulated_mutations_advanced == 0


# ---------------------------------------------------------------------------
# Epoch range simulation
# ---------------------------------------------------------------------------

class TestEpochRangeSimulation:
    def test_empty_epoch_range_returns_zero_aggregate(self):
        policy = _empty_policy()
        sim = EpochReplaySimulator(policy)
        result = sim.simulate_epoch_range([], epoch_data_map={})
        assert result.epoch_count == 0
        assert result.total_mutations_actual == 0
        assert result.simulation is True

    def test_aggregate_totals_across_epochs(self):
        policy = _empty_policy()
        sim = EpochReplaySimulator(policy)
        epoch_data = {
            "epoch-001": _make_epoch("epoch-001", mutations=[_make_mutation("m1"), _make_mutation("m2")], actual_mutations_advanced=2),
            "epoch-002": _make_epoch("epoch-002", mutations=[_make_mutation("m3")], actual_mutations_advanced=1),
        }
        result = sim.simulate_epoch_range(["epoch-001", "epoch-002"], epoch_data_map=epoch_data)
        assert result.epoch_count == 2
        assert result.total_mutations_actual == 3
        assert result.total_mutations_simulated == 3
        assert result.total_mutations_blocked == 0

    def test_velocity_impact_is_mean_across_epochs(self):
        policy = interpret_policy_block("max_mutations_per_epoch(count=1)")
        sim = EpochReplaySimulator(policy)
        epoch_data = {
            "e1": _make_epoch("e1", mutations=[_make_mutation("m1"), _make_mutation("m2")], actual_mutations_advanced=2),
            "e2": _make_epoch("e2", mutations=[_make_mutation("m3"), _make_mutation("m4")], actual_mutations_advanced=2),
        }
        result = sim.simulate_epoch_range(["e1", "e2"], epoch_data_map=epoch_data)
        assert result.velocity_impact_pct < 0.0  # simulation advanced fewer

    def test_simulation_true_in_run_result(self):
        policy = _empty_policy()
        sim = EpochReplaySimulator(policy)
        result = sim.simulate_epoch_range(["e1"], epoch_data_map={"e1": _make_epoch("e1")})
        assert result.simulation is True


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestSimulationDeterminism:
    def test_epoch_result_is_deterministic(self):
        policy = interpret_policy_block("max_risk_score(threshold=0.5)\nmax_mutations_per_epoch(count=3)")
        sim = EpochReplaySimulator(policy)
        muts = [_make_mutation(f"mut-{i}", risk_score=0.3 + i * 0.1) for i in range(4)]
        epoch = _make_epoch(mutations=muts, actual_mutations_advanced=4)

        r1 = sim.simulate_epoch("epoch-det", epoch_data=epoch)
        r2 = sim.simulate_epoch("epoch-det", epoch_data=epoch)
        assert r1 == r2

    def test_run_digest_is_deterministic(self):
        policy = interpret_policy_block("max_risk_score(threshold=0.6)")
        sim = EpochReplaySimulator(policy)
        epoch_data = {"e1": _make_epoch("e1"), "e2": _make_epoch("e2")}

        r1 = sim.simulate_epoch_range(["e1", "e2"], epoch_data_map=epoch_data)
        r2 = sim.simulate_epoch_range(["e1", "e2"], epoch_data_map=epoch_data)
        assert r1.run_digest == r2.run_digest

    def test_policy_digest_is_deterministic(self):
        block = "max_risk_score(threshold=0.5)\nrequire_approvals(tier=PRODUCTION, count=2)"
        p1 = interpret_policy_block(block)
        p2 = interpret_policy_block(block)
        from runtime.governance.simulation.epoch_simulator import _compute_policy_digest
        assert _compute_policy_digest(p1) == _compute_policy_digest(p2)

    def test_different_policies_produce_different_digests(self):
        from runtime.governance.simulation.epoch_simulator import _compute_policy_digest
        p1 = interpret_policy_block("max_risk_score(threshold=0.4)")
        p2 = interpret_policy_block("max_risk_score(threshold=0.6)")
        assert _compute_policy_digest(p1) != _compute_policy_digest(p2)
