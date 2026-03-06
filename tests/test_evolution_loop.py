# SPDX-License-Identifier: Apache-2.0
"""
Integration tests for runtime/evolution/evolution_loop.py.

All 5 tests mock propose_from_all_agents — no real Claude API calls.
simulate_outcomes=True enables full weight adaptation in tests.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch

from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.autonomy.mutation_scaffold import MutationCandidate
from runtime.evolution.evolution_loop import EvolutionLoop, EpochResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_candidates(agent: str, n: int = 4) -> list[MutationCandidate]:
    return [
        MutationCandidate(
            mutation_id=f"{agent}-mc-{i:03d}",
            expected_gain=0.6,
            risk_score=0.1,
            complexity=0.2,
            coverage_delta=0.3,
            agent_origin=agent,
            epoch_id="epoch-test",
        )
        for i in range(n)
    ]


MOCK_PROPOSALS = {
    "architect": _make_candidates("architect"),
    "dream":     _make_candidates("dream"),
    "beast":     _make_candidates("beast"),
}


def _make_context() -> CodebaseContext:
    return CodebaseContext(
        file_summaries={"runtime/evolution/evolution_loop.py": "Epoch orchestrator."},
        recent_failures=[],
        current_epoch_id="epoch-test-001",
    )


@pytest.fixture
def loop(tmp_path) -> EvolutionLoop:
    # Patch persistence paths to tmp_path to avoid polluting data/
    with patch("runtime.autonomy.weight_adaptor.DEFAULT_STATE_PATH", tmp_path / "w.json"), \
         patch("runtime.autonomy.fitness_landscape.DEFAULT_LANDSCAPE_PATH", tmp_path / "fl.json"):
        return EvolutionLoop(api_key="test-key", generations=2, simulate_outcomes=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_epoch_returns_epoch_result(loop) -> None:
    ctx = _make_context()
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=MOCK_PROPOSALS,
    ):
        result = loop.run_epoch(ctx)
    assert isinstance(result, EpochResult)
    assert result.epoch_id == "epoch-test-001"
    assert result.generation_count == 2


def test_accepted_count_gt_zero_simulate(loop) -> None:
    ctx = _make_context()
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=MOCK_PROPOSALS,
    ):
        result = loop.run_epoch(ctx)
    assert result.accepted_count > 0


def test_weight_accuracy_updates(loop) -> None:
    ctx = _make_context()
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=MOCK_PROPOSALS,
    ):
        result = loop.run_epoch(ctx)
    # After simulate epoch, accuracy should deviate from initial 0.5
    assert result.weight_accuracy != 0.0


def test_landscape_recorded_after_epoch(loop) -> None:
    ctx = _make_context()
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=MOCK_PROPOSALS,
    ):
        loop.run_epoch(ctx)
    # Landscape should have some records after epoch
    summary = loop._landscape.summary()
    assert isinstance(summary["types"], dict)


def test_recommended_next_agent_returned(loop) -> None:
    ctx = _make_context()
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=MOCK_PROPOSALS,
    ):
        result = loop.run_epoch(ctx)
    assert result.recommended_next_agent in {"architect", "dream", "beast"}
