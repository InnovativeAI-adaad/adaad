# SPDX-License-Identifier: Apache-2.0
"""Integration tests for EvolutionLoop.run_epoch public interfaces.

These tests intentionally exercise the shipped integration surfaces:
- CodebaseContext fixture -> EvolutionLoop.run_epoch(context)
- ProposalEngine.generate call point
- Public epoch outputs (EpochResult) and proposal-stage context effects
- Failure isolation for enrichment exceptions
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.evolution.evolution_loop import EpochResult, EvolutionLoop
from runtime.evolution.proposal_engine import ProposalEngine, ProposalRequest
from runtime.intelligence.proposal import Proposal

pytestmark = pytest.mark.regression_standard


@pytest.fixture
def minimal_context() -> CodebaseContext:
    return CodebaseContext(
        file_summaries={"runtime/evolution/evolution_loop.py": "epoch controller"},
        recent_failures=[],
        current_epoch_id="ep-integration-001",
        explore_ratio=0.42,
    )


def _noop_proposal() -> Proposal:
    return Proposal(
        proposal_id="ep-integration-001:auto",
        title="noop",
        summary="noop",
        estimated_impact=0.0,
        real_diff="",
    )


def test_run_epoch_accepts_minimal_context_and_returns_epoch_result(minimal_context):
    loop = EvolutionLoop(api_key="k", simulate_outcomes=True, market_integrator=None)

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={}):
        result = loop.run_epoch(minimal_context)

    assert isinstance(result, EpochResult)
    assert result.epoch_id == "ep-integration-001"
    assert result.total_candidates == 0


def test_run_epoch_calls_proposal_engine_generate_on_existing_call_point(minimal_context):
    engine = MagicMock(spec=ProposalEngine)
    engine.generate.return_value = _noop_proposal()
    loop = EvolutionLoop(
        api_key="k",
        simulate_outcomes=True,
        market_integrator=None,
        proposal_engine=engine,
    )

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value={}):
        result = loop.run_epoch(minimal_context)

    assert isinstance(result, EpochResult)
    engine.generate.assert_called_once()
    request = engine.generate.call_args.args[0]
    assert isinstance(request, ProposalRequest)
    assert request.cycle_id == minimal_context.current_epoch_id


def test_learning_enrichment_updates_context_visible_at_proposal_stage(minimal_context):
    loop = EvolutionLoop(api_key="k", simulate_outcomes=True, market_integrator=None)
    loop._learning_extractor = MagicMock(
        extract=MagicMock(
            return_value=SimpleNamespace(
                is_empty=lambda: False,
                as_prompt_block=lambda: "--- ADVISORY learning block ---",
            )
        )
    )

    captured = {}

    def _capture_context(ctx, api_key):
        captured["learning_context"] = ctx.learning_context
        return {}

    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        side_effect=_capture_context,
    ):
        result = loop.run_epoch(minimal_context)

    assert isinstance(result, EpochResult)
    assert captured["learning_context"] == "--- ADVISORY learning block ---"


def test_learning_enrichment_exceptions_do_not_abort_epoch(minimal_context):
    loop = EvolutionLoop(api_key="k", simulate_outcomes=True, market_integrator=None)
    loop._learning_extractor = MagicMock(extract=MagicMock(side_effect=RuntimeError("boom")))

    proposal_call_count = {"count": 0}

    def _capture_context(ctx, api_key):
        proposal_call_count["count"] += 1
        # enrichment failed; context should remain unset
        assert ctx.learning_context is None
        return {}

    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        side_effect=_capture_context,
    ):
        result = loop.run_epoch(minimal_context)

    assert isinstance(result, EpochResult)
    assert proposal_call_count["count"] == 1
