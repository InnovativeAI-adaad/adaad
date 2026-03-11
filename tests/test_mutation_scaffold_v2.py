# SPDX-License-Identifier: Apache-2.0
"""
Test suite for mutation_scaffold.py v2.

All 7 v2-specific tests PLUS backward compatibility with existing v1 constructor
patterns. The 8 original tests in test_orchestrator_replay_mode.py must remain
green — this file validates the v2 additions only.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.autonomy.mutation_scaffold import (
    DEFAULT_ACCEPTANCE_THRESHOLD,
    ELITISM_BONUS,
    MutationCandidate,
    MutationScore,
    PopulationState,
    ScoringWeights,
    rank_mutation_candidates,
    score_candidate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _candidate(**overrides) -> MutationCandidate:
    defaults = dict(
        mutation_id="test-mc-001",
        expected_gain=0.5,
        risk_score=0.2,
        complexity=0.2,
        coverage_delta=0.3,
    )
    defaults.update(overrides)
    return MutationCandidate(**defaults)


# ---------------------------------------------------------------------------
# Test 1: v1 backward compatibility — 5-positional-arg constructor
# ---------------------------------------------------------------------------


def test_v1_backward_compat() -> None:
    """Old 5-arg positional constructor must not raise TypeError."""
    c = MutationCandidate("mc-v1", 0.6, 0.2, 0.3, 0.4)
    assert c.mutation_id == "mc-v1"
    assert c.parent_id is None
    assert c.agent_origin == "unknown"
    assert c.epoch_id == ""
    assert c.source_context_hash == ""
    # Must score without error
    result = score_candidate(c)
    assert isinstance(result, MutationScore)


# ---------------------------------------------------------------------------
# Test 2: ScoringWeights defaults match v1 constants
# ---------------------------------------------------------------------------


def test_scoring_weights_default() -> None:
    w = ScoringWeights()
    assert w.gain_weight == pytest.approx(0.35)
    assert w.coverage_weight == pytest.approx(0.25)
    assert w.horizon_weight == pytest.approx(0.20)
    assert w.risk_penalty == pytest.approx(0.20)
    assert w.complexity_penalty == pytest.approx(0.10)
    assert w.acceptance_threshold == pytest.approx(DEFAULT_ACCEPTANCE_THRESHOLD)


# ---------------------------------------------------------------------------
# Test 3: Adaptive threshold shifts downward with diversity_pressure
# ---------------------------------------------------------------------------


def test_adaptive_threshold() -> None:
    c = _candidate()

    state_exploit = PopulationState(diversity_pressure=0.0)
    state_balanced = PopulationState(diversity_pressure=0.5)
    state_explore = PopulationState(diversity_pressure=1.0)

    s_exploit = score_candidate(c, population_state=state_exploit)
    s_balanced = score_candidate(c, population_state=state_balanced)
    s_explore  = score_candidate(c, population_state=state_explore)

    thresh_exploit  = s_exploit.dimension_breakdown["adjusted_threshold"]
    thresh_balanced = s_balanced.dimension_breakdown["adjusted_threshold"]
    thresh_explore  = s_explore.dimension_breakdown["adjusted_threshold"]

    assert thresh_balanced < thresh_exploit
    assert thresh_explore  < thresh_balanced
    assert thresh_explore == pytest.approx(DEFAULT_ACCEPTANCE_THRESHOLD * 0.60)


# ---------------------------------------------------------------------------
# Test 4: Elitism bonus applied to elite-parent children
# ---------------------------------------------------------------------------


def test_elitism_bonus() -> None:
    parent_id = "elite-parent-001"
    state = PopulationState()
    state.record_elite(parent_id)

    # Child with elite parent
    child = _candidate(mutation_id="child-001", parent_id=parent_id)
    # Same candidate without elite parent
    plain = _candidate(mutation_id="plain-001", parent_id=None)

    child_score = score_candidate(child, population_state=state)
    plain_score = score_candidate(plain, population_state=state)

    assert child_score.elitism_applied is True
    assert plain_score.elitism_applied is False
    assert child_score.score == pytest.approx(plain_score.score + ELITISM_BONUS, abs=1e-4)


# ---------------------------------------------------------------------------
# Test 5: Lineage fields propagate through scoring
# ---------------------------------------------------------------------------


def test_lineage_fields() -> None:
    c = MutationCandidate(
        mutation_id="lineage-mc",
        expected_gain=0.5,
        risk_score=0.2,
        complexity=0.2,
        coverage_delta=0.3,
        parent_id="parent-abc",
        generation=2,
        agent_origin="architect",
        epoch_id="epoch-99",
        source_context_hash="deadbeef",
    )
    result = score_candidate(c)
    assert result.epoch_id == "epoch-99"
    assert result.parent_id == "parent-abc"
    assert result.agent_origin == "architect"


# ---------------------------------------------------------------------------
# Test 6: PopulationState.advance_generation() increments counter
# ---------------------------------------------------------------------------


def test_population_state_advance() -> None:
    state = PopulationState()
    assert state.generation == 0
    state.advance_generation()
    assert state.generation == 1
    state.advance_generation()
    assert state.generation == 2


# ---------------------------------------------------------------------------
# Test 7: PopulationState.record_elite() caps at max_elite=5
# ---------------------------------------------------------------------------


def test_elite_max_cap() -> None:
    state = PopulationState()
    for i in range(10):
        state.record_elite(f"elite-{i:03d}")
    assert len(state.elite_ids) <= 5


# ---------------------------------------------------------------------------
# Test 8: rank_mutation_candidates accepts v2 kwargs without breaking
# ---------------------------------------------------------------------------


def test_rank_with_v2_kwargs() -> None:
    candidates = [_candidate(mutation_id=f"mc-{i}", expected_gain=i * 0.1) for i in range(5)]
    weights = ScoringWeights()
    state   = PopulationState()
    results = rank_mutation_candidates(candidates, weights=weights, population_state=state)
    assert len(results) == 5
    # Descending score order
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_rank_tie_break_uses_secondary_signals_and_is_stable() -> None:
    from runtime.autonomy import mutation_scaffold as ms

    base = dict(expected_gain=0.8, risk_score=0.2, complexity=0.2, coverage_delta=0.1)
    a = MutationCandidate(mutation_id="a", generation=0, parent_id=None, source_context_hash="ctx-a", **base)
    b = MutationCandidate(mutation_id="b", generation=2, parent_id="p", source_context_hash="ctx-b", **base)
    c = MutationCandidate(mutation_id="c", generation=2, parent_id=None, source_context_hash="ctx-c", **base)

    ranked_once = rank_mutation_candidates([a, b, c])
    ranked_twice = rank_mutation_candidates([a, b, c])

    ids_once = [r.mutation_id for r in ranked_once]
    ids_twice = [r.mutation_id for r in ranked_twice]
    assert ids_once == ids_twice

    expected = [
        candidate.mutation_id
        for candidate in sorted(
            [a, b, c],
            key=lambda item: (
                -ms._tie_break_signals(item)[0],
                -ms._tie_break_signals(item)[1],
                ms._tie_break_signals(item)[2],
                item.mutation_id,
            ),
        )
    ]
    assert ids_once == expected


def test_semantic_scoring_cache_avoids_repeated_diff_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.autonomy import mutation_scaffold as ms

    calls = {"count": 0}

    class _FakeResult:
        fallback_used = False
        risk_score = 0.11
        complexity_score = 0.22

    class _FakeSDE:
        def diff(self, before_source: str, after_source: str):
            calls["count"] += 1
            return _FakeResult()

    monkeypatch.setattr("runtime.evolution.semantic_diff.SemanticDiffEngine", _FakeSDE)
    ms._semantic_feature_from_digest.cache_clear()

    candidate = MutationCandidate(
        mutation_id="sem-cache",
        expected_gain=0.5,
        risk_score=0.6,
        complexity=0.6,
        coverage_delta=0.5,
        python_content="def f():\n    return 1\n",
    )

    score_candidate(candidate)
    score_candidate(candidate)
    score_candidate(candidate)

    assert calls["count"] == 1
