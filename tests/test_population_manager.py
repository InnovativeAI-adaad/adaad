# SPDX-License-Identifier: Apache-2.0
"""Test suite for runtime/evolution/population_manager.py"""

from __future__ import annotations

import random

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.autonomy.mutation_scaffold import MutationCandidate, ScoringWeights
from runtime.evolution.population_manager import (
    BLX_ALPHA,
    MAX_POPULATION,
    PopulationManager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _candidate(mid: str, gain: float = 0.5, risk: float = 0.2,
               complexity: float = 0.3, coverage: float = 0.3,
               parent_id=None) -> MutationCandidate:
    return MutationCandidate(
        mutation_id=mid,
        expected_gain=gain,
        risk_score=risk,
        complexity=complexity,
        coverage_delta=coverage,
        parent_id=parent_id,
    )


@pytest.fixture
def manager() -> PopulationManager:
    m = PopulationManager()
    m.set_weights(ScoringWeights())
    return m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_crossover_child_in_blx_range(manager) -> None:
    parent_a = _candidate("pa", gain=0.4, risk=0.2, complexity=0.3, coverage=0.2)
    parent_b = _candidate("pb", gain=0.6, risk=0.4, complexity=0.5, coverage=0.4)
    manager.seed([parent_a, parent_b])

    child = manager._crossover(parent_a, parent_b)
    assert child is not None

    # BLX-0.5 range for expected_gain: [0.4-(0.1), 0.6+(0.1)] = [0.3, 0.7]
    extent_gain = (0.6 - 0.4) * BLX_ALPHA
    assert (0.4 - extent_gain) <= child.expected_gain <= (0.6 + extent_gain)


def test_crossover_lineage_parent_id(manager) -> None:
    parent_a = _candidate("parent-a-001")
    parent_b = _candidate("parent-b-002")
    manager.seed([parent_a, parent_b])
    child = manager._crossover(parent_a, parent_b)
    assert child is not None
    assert child.parent_id == "parent-a-001"


def test_diversity_deduplicates_identical(manager) -> None:
    c1 = _candidate("dup-001", gain=0.500, risk=0.200, complexity=0.300, coverage=0.300)
    c2 = _candidate("dup-002", gain=0.500, risk=0.200, complexity=0.300, coverage=0.300)
    result = PopulationManager._enforce_diversity([c1, c2])
    assert len(result) == 1


def test_max_population_enforced(manager) -> None:
    candidates = [_candidate(f"mc-{i:03d}", gain=i * 0.04) for i in range(20)]
    manager.seed(candidates)
    assert len(manager.population) <= MAX_POPULATION


def test_elite_ids_populated_after_evolve(manager) -> None:
    candidates = [
        _candidate(f"mc-{i:03d}", gain=0.7, risk=0.1, complexity=0.2, coverage=0.3)
        for i in range(6)
    ]
    manager.seed(candidates)
    manager.evolve_generation()
    assert len(manager.state.elite_ids) > 0


def test_generation_advances_on_evolve(manager) -> None:
    candidates = [_candidate(f"mc-{i}", gain=0.6) for i in range(4)]
    manager.seed(candidates)
    manager.evolve_generation()
    manager.evolve_generation()
    assert manager.state.generation == 2


def test_same_seed_produces_identical_crossover_children() -> None:
    parent_a = _candidate("parent-a-001", gain=0.4, risk=0.2, complexity=0.3, coverage=0.2)
    parent_b = _candidate("parent-b-002", gain=0.6, risk=0.4, complexity=0.5, coverage=0.4)

    manager_one = PopulationManager()
    manager_two = PopulationManager()
    manager_one.set_seed(1337)
    manager_two.set_seed(1337)

    child_one = manager_one._crossover(parent_a, parent_b)
    child_two = manager_two._crossover(parent_a, parent_b)

    assert child_one is not None
    assert child_two is not None
    assert child_one.mutation_id == child_two.mutation_id
    assert child_one.expected_gain == child_two.expected_gain
    assert child_one.risk_score == child_two.risk_score
    assert child_one.complexity == child_two.complexity
    assert child_one.coverage_delta == child_two.coverage_delta


def test_seeded_rng_and_set_seed_match_repeated_runs(manager) -> None:
    candidates = [
        _candidate("base-a", gain=0.95, risk=0.05, complexity=0.1, coverage=0.6),
        _candidate("base-b", gain=0.75, risk=0.15, complexity=0.2, coverage=0.5),
        _candidate("base-c", gain=0.55, risk=0.25, complexity=0.3, coverage=0.4),
        _candidate("base-d", gain=0.35, risk=0.35, complexity=0.4, coverage=0.3),
    ]

    manager_one = PopulationManager(random.Random(2026))
    manager_one.set_weights(ScoringWeights())
    manager_one.seed(candidates)

    manager_two = PopulationManager()
    manager_two.set_weights(ScoringWeights())
    manager_two.set_seed(2026)
    manager_two.seed(candidates)

    scores_one = manager_one.evolve_generation()
    scores_two = manager_two.evolve_generation()

    assert [s.mutation_id for s in scores_one] == [s.mutation_id for s in scores_two]
    assert [c.mutation_id for c in manager_one.population] == [c.mutation_id for c in manager_two.population]
    assert [
        (c.expected_gain, c.risk_score, c.complexity, c.coverage_delta)
        for c in manager_one.population
    ] == [
        (c.expected_gain, c.risk_score, c.complexity, c.coverage_delta)
        for c in manager_two.population
    ]
