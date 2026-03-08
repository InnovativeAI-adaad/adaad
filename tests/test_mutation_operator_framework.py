# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from runtime.autonomy.mutation_scaffold import MutationCandidate, rank_candidates_via_registry
from runtime.evolution.mutation_operator_framework import (
    ASTTransformOperator,
    MutationOperatorRegistry,
    OperatorMetadata,
    OperatorOutcome,
    OperatorSelectionProfile,
)


class _FailingOperator(ASTTransformOperator):
    metadata = OperatorMetadata(
        operator_key="ast_transform",
        category="ast",
        deterministic_rank=10,
        version="1.0.0",
        profile_bias=0.06,
    )

    def transform(self, candidate: MutationCandidate) -> MutationCandidate:
        raise RuntimeError("boom")


def _candidate(mutation_id: str, agent: str = "dream") -> MutationCandidate:
    return MutationCandidate(
        mutation_id=mutation_id,
        expected_gain=0.6,
        risk_score=0.2,
        complexity=0.2,
        coverage_delta=0.2,
        agent_origin=agent,
    )


def test_operator_registry_metadata_is_diverse_and_deterministic() -> None:
    registry = MutationOperatorRegistry()
    metadata = registry.ordered_metadata()

    assert [m.operator_key for m in metadata] == ["ast_transform", "refactor", "performance_rewrite"]
    assert sorted({m.category for m in metadata}) == ["ast", "performance", "refactor"]


def test_rank_candidates_via_registry_keeps_deterministic_order() -> None:
    candidates = [_candidate("m-b"), _candidate("m-a")]
    scores = rank_candidates_via_registry(candidates)

    assert [item.mutation_id for item in scores] == ["m-a", "m-b"]


def test_adaptive_selection_prefers_operator_with_better_outcomes() -> None:
    registry = MutationOperatorRegistry()
    selected = registry.select_operator(
        _candidate("m-1", agent="beast"),
        outcome_history={
            "performance_rewrite": OperatorOutcome(successes=6, failures=1),
            "ast_transform": OperatorOutcome(successes=1, failures=5),
        },
        profile=OperatorSelectionProfile(explore_ratio=0.2, recent_failures_count=0),
    )

    assert selected.metadata.operator_key == "performance_rewrite"


def test_registry_falls_back_when_operator_raises() -> None:
    registry = MutationOperatorRegistry(operators=[_FailingOperator()])
    candidate = _candidate("m-fail")

    transformed = registry.apply_operator(candidate)

    assert transformed.mutation_id == "m-fail"
    assert transformed.operator_key == "fallback_static"
