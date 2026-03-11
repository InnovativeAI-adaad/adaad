import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.fitness_orchestrator import FitnessOrchestrator


class _LedgerStub:
    def __init__(self) -> None:
        self.events = []

    def append_event(self, event_type: str, payload):
        self.events.append({"type": event_type, "payload": payload})
        return self.events[-1]


def _context(**extra):
    base = {
        "epoch_id": "epoch-1",
        "mutation_tier": "low",
        "correctness_score": 1.0,
        "efficiency_score": 0.8,
        "policy_compliance_score": 0.9,
        "goal_alignment_score": 0.7,
        "simulated_market_score": 0.6,
    }
    base.update(extra)
    return base


def test_same_input_same_output_is_deterministic() -> None:
    orchestrator = FitnessOrchestrator()
    first = orchestrator.score(_context())
    second = orchestrator.score(_context())
    assert first.total_score == second.total_score
    assert dict(first.breakdown) == dict(second.breakdown)
    assert first.regime == second.regime
    assert first.config_hash == second.config_hash


def test_weights_and_regime_are_frozen_within_epoch() -> None:
    ledger = _LedgerStub()
    orchestrator = FitnessOrchestrator()
    first = orchestrator.score(_context(ledger=ledger, mutation_tier="low"))
    second = orchestrator.score(_context(ledger=ledger, mutation_tier="critical", efficiency_score=0.1))

    assert first.regime == "economic_full"
    assert second.regime == "economic_full"
    assert first.config_hash == second.config_hash
    assert len(ledger.events) == 2
    assert ledger.events[0]["type"] == "fitness_regime_snapshot"
    assert ledger.events[1]["type"] == "EpochMetadataEvent"


def test_config_hash_stability_for_same_regime_snapshot() -> None:
    orchestrator_a = FitnessOrchestrator()
    orchestrator_b = FitnessOrchestrator()
    result_a = orchestrator_a.score(_context(epoch_id="epoch-a", mutation_tier="medium"))
    result_b = orchestrator_b.score(_context(epoch_id="epoch-b", mutation_tier="medium"))
    assert result_a.config_hash == result_b.config_hash


def test_tier_to_regime_mapping_invariants() -> None:
    orchestrator = FitnessOrchestrator()
    assert orchestrator.score(_context(epoch_id="epoch-low", mutation_tier="low")).regime == "economic_full"
    assert orchestrator.score(_context(epoch_id="epoch-med", mutation_tier="medium")).regime == "hybrid"
    assert orchestrator.score(_context(epoch_id="epoch-high", mutation_tier="high")).regime == "survival_only"
    assert orchestrator.score(_context(epoch_id="epoch-crit", mutation_tier="critical")).regime == "survival_only"


def test_deterministic_seed_propagates_into_snapshot_hashes() -> None:
    orchestrator = FitnessOrchestrator()
    seeded_a = orchestrator.score(_context(epoch_id="seeded-a", deterministic_seed="seed-1"))
    seeded_b = orchestrator.score(_context(epoch_id="seeded-b", deterministic_seed="seed-1"))
    seeded_c = orchestrator.score(_context(epoch_id="seeded-c", deterministic_seed="seed-2"))

    assert seeded_a.config_hash == seeded_b.config_hash
    assert seeded_a.weight_snapshot_hash == seeded_b.weight_snapshot_hash
    assert seeded_a.config_hash != seeded_c.config_hash
