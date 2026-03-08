# SPDX-License-Identifier: Apache-2.0
"""
Test suite for runtime/autonomy/ai_mutation_proposer.py.

All 8 tests mock _call_claude — no real API calls are made in unit tests.
"""

from __future__ import annotations

import json
import threading
import time
import pytest
from unittest.mock import patch, MagicMock

from runtime.autonomy.ai_mutation_proposer import (
    CANONICAL_AGENT_ORDER,
    CodebaseContext,
    _parse_proposals,
    propose_mutations,
    propose_from_all_agents,
)
from runtime.autonomy.mutation_scaffold import MutationCandidate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


VALID_PROPOSALS_JSON = json.dumps([
    {
        "mutation_id": "architect-refactor-001",
        "description": "Introduce adapter pattern for external API clients.",
        "expected_gain": 0.45,
        "risk_score": 0.15,
        "complexity": 0.30,
        "coverage_delta": 0.10,
        "target_files": ["runtime/autonomy/mutation_scaffold.py"],
        "mutation_type": "structural",
    },
    {
        "mutation_id": "architect-iface-002",
        "description": "Extract scoring interface for testability.",
        "expected_gain": 0.40,
        "risk_score": 0.10,
        "complexity": 0.20,
        "coverage_delta": 0.15,
        "target_files": ["runtime/autonomy/mutation_scaffold.py"],
        "mutation_type": "structural",
    },
    {
        "mutation_id": "architect-deps-003",
        "description": "Remove circular dependency between agents and evolution.",
        "expected_gain": 0.50,
        "risk_score": 0.20,
        "complexity": 0.35,
        "coverage_delta": 0.05,
        "target_files": ["runtime/evolution/evolution_loop.py"],
        "mutation_type": "structural",
    },
])


def _make_context() -> CodebaseContext:
    return CodebaseContext(
        file_summaries={"runtime/autonomy/mutation_scaffold.py": "Scoring helpers."},
        recent_failures=["test_some_feature"],
        current_epoch_id="epoch-test-001",
        explore_ratio=0.5,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_propose_mutations_architect_returns_candidates() -> None:
    ctx = _make_context()
    with patch(
        "runtime.autonomy.ai_mutation_proposer._call_claude",
        return_value=VALID_PROPOSALS_JSON,
    ):
        result = propose_mutations("architect", ctx, api_key="test-key")
    assert len(result) >= 3
    assert all(isinstance(c, MutationCandidate) for c in result)


def test_agent_origin_set_correctly() -> None:
    ctx = _make_context()
    with patch(
        "runtime.autonomy.ai_mutation_proposer._call_claude",
        return_value=VALID_PROPOSALS_JSON,
    ):
        result = propose_mutations("architect", ctx, api_key="test-key")
    assert all(c.agent_origin == "architect" for c in result)


def test_markdown_fence_stripped() -> None:
    ctx = _make_context()
    fenced = f"```json\n{VALID_PROPOSALS_JSON}\n```"
    with patch(
        "runtime.autonomy.ai_mutation_proposer._call_claude",
        return_value=fenced,
    ):
        result = propose_mutations("dream", ctx, api_key="test-key")
    assert len(result) >= 1  # Parsed without JSONDecodeError


def test_invalid_agent_raises_value_error() -> None:
    ctx = _make_context()
    with pytest.raises(ValueError, match="Unknown agent"):
        propose_mutations("unknown_agent", ctx, api_key="test-key")


def test_parent_id_propagates() -> None:
    ctx = _make_context()
    with patch(
        "runtime.autonomy.ai_mutation_proposer._call_claude",
        return_value=VALID_PROPOSALS_JSON,
    ):
        result = propose_mutations("beast", ctx, api_key="test-key", parent_id="parent-xyz")
    assert all(c.parent_id == "parent-xyz" for c in result)


def test_context_hash_set_in_candidate() -> None:
    ctx = _make_context()
    with patch(
        "runtime.autonomy.ai_mutation_proposer._call_claude",
        return_value=VALID_PROPOSALS_JSON,
    ):
        result = propose_mutations("architect", ctx, api_key="test-key")
    assert all(len(c.source_context_hash) > 0 for c in result)


def test_propose_all_agents_returns_all_keys() -> None:
    ctx = _make_context()
    with patch(
        "runtime.autonomy.ai_mutation_proposer._call_claude",
        return_value=VALID_PROPOSALS_JSON,
    ), patch(
        "runtime.autonomy.ai_mutation_proposer._load_operator_outcome_history",
        return_value={},
    ):
        result = propose_from_all_agents(ctx, api_key="test-key")
    assert tuple(result.proposals_by_agent.keys()) == CANONICAL_AGENT_ORDER
    assert result.failures_by_agent == {}


def test_propose_all_agents_deterministic_order_when_completion_is_out_of_order() -> None:
    ctx = _make_context()
    delays = {
        "architect": 0.08,
        "dream": 0.01,
        "beast": 0.04,
    }

    def _slow_propose(agent: str, *_args, **_kwargs):
        time.sleep(delays[agent])
        return [MagicMock(spec=MutationCandidate)]

    with patch(
        "runtime.autonomy.ai_mutation_proposer.propose_mutations",
        side_effect=_slow_propose,
    ), patch(
        "runtime.autonomy.ai_mutation_proposer._load_operator_outcome_history",
        return_value={},
    ):
        result = propose_from_all_agents(ctx, api_key="test-key", timeout=1)

    assert tuple(result.proposals_by_agent.keys()) == CANONICAL_AGENT_ORDER
    assert all(len(result.proposals_by_agent[agent]) == 1 for agent in CANONICAL_AGENT_ORDER)


def test_propose_all_agents_failure_isolated_per_agent() -> None:
    ctx = _make_context()

    def _partial_failure(agent: str, *_args, **_kwargs):
        if agent == "dream":
            raise TimeoutError("dream timed out")
        return [MagicMock(spec=MutationCandidate)]

    with patch(
        "runtime.autonomy.ai_mutation_proposer.propose_mutations",
        side_effect=_partial_failure,
    ), patch(
        "runtime.autonomy.ai_mutation_proposer._load_operator_outcome_history",
        return_value={},
    ):
        result = propose_from_all_agents(ctx, api_key="test-key", timeout=2, retries=0)

    assert len(result.proposals_by_agent["architect"]) == 1
    assert len(result.proposals_by_agent["beast"]) == 1
    assert result.proposals_by_agent["dream"] == []
    assert result.failures_by_agent["dream"]["code"] == "agent_timeout"


def test_propose_all_agents_global_timeout_cancels_pending_work() -> None:
    ctx = _make_context()
    gate = threading.Event()

    def _hung_propose(agent: str, *_args, **_kwargs):
        if agent == "architect":
            return [MagicMock(spec=MutationCandidate)]
        gate.wait(timeout=0.5)
        return [MagicMock(spec=MutationCandidate)]

    with patch(
        "runtime.autonomy.ai_mutation_proposer.propose_mutations",
        side_effect=_hung_propose,
    ), patch(
        "runtime.autonomy.ai_mutation_proposer._load_operator_outcome_history",
        return_value={},
    ):
        result = propose_from_all_agents(
            ctx,
            api_key="test-key",
            timeout=1,
            global_timeout_budget=0.02,
        )

    assert len(result.proposals_by_agent["architect"]) == 1
    assert result.failures_by_agent["dream"]["code"] == "global_timeout"
    assert result.failures_by_agent["beast"]["code"] == "global_timeout"


def test_malformed_json_raises() -> None:
    ctx = _make_context()
    with patch(
        "runtime.autonomy.ai_mutation_proposer._call_claude",
        return_value="this is not json at all",
    ):
        with pytest.raises(json.JSONDecodeError):
            propose_mutations("architect", ctx, api_key="test-key")


def test_propose_all_agents_applies_operator_registry_metadata() -> None:
    ctx = _make_context()

    def _single(agent: str, *_args, **_kwargs):
        return [
            MutationCandidate(
                mutation_id=f"{agent}-m-1",
                expected_gain=0.5,
                risk_score=0.2,
                complexity=0.2,
                coverage_delta=0.1,
                agent_origin=agent,
            )
        ]

    with patch(
        "runtime.autonomy.ai_mutation_proposer.propose_mutations",
        side_effect=_single,
    ), patch(
        "runtime.autonomy.ai_mutation_proposer._load_operator_outcome_history",
        return_value={},
    ):
        result = propose_from_all_agents(ctx, api_key="test-key", retries=0)

    all_candidates = [
        candidate
        for proposals in result.proposals_by_agent.values()
        for candidate in proposals
    ]
    assert all(candidate.operator_key != "static" for candidate in all_candidates)
