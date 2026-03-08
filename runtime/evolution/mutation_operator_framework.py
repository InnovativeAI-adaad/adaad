# SPDX-License-Identifier: Apache-2.0
"""Deterministic mutation-operator registry and adaptive selection helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping, Protocol

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.autonomy.mutation_scaffold import MutationCandidate


@dataclass(frozen=True)
class OperatorMetadata:
    """Deterministic operator identity and ordering metadata."""

    operator_key: str
    category: str
    deterministic_rank: int
    version: str = "1.0.0"
    profile_bias: float = 0.0


@dataclass(frozen=True)
class OperatorOutcome:
    """Historical outcome summary for one operator."""

    successes: int = 0
    failures: int = 0

    @property
    def total(self) -> int:
        return self.successes + self.failures

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.5
        return self.successes / float(self.total)


@dataclass(frozen=True)
class OperatorSelectionProfile:
    """Profile data sourced from AI proposal context for adaptive selection."""

    explore_ratio: float = 0.5
    recent_failures_count: int = 0
    preferred_operator_hint: str = ""


class MutationOperator(Protocol):
    """Contract implemented by all mutation operators."""

    metadata: OperatorMetadata

    def transform(self, candidate: "MutationCandidate") -> "MutationCandidate":
        """Return a deterministically transformed candidate."""


class ASTTransformOperator:
    metadata = OperatorMetadata(
        operator_key="ast_transform",
        category="ast",
        deterministic_rank=10,
        profile_bias=0.06,
    )

    def transform(self, candidate: "MutationCandidate") -> "MutationCandidate":
        from runtime.autonomy.mutation_scaffold import MutationCandidate

        return MutationCandidate(
            **candidate.__dict__,
            strategic_horizon=max(0.10, min(2.0, candidate.strategic_horizon + 0.15)),
            coverage_delta=max(0.0, min(1.0, candidate.coverage_delta + 0.05)),
        )


class RefactorOperator:
    metadata = OperatorMetadata(
        operator_key="refactor",
        category="refactor",
        deterministic_rank=20,
        profile_bias=0.02,
    )

    def transform(self, candidate: "MutationCandidate") -> "MutationCandidate":
        from runtime.autonomy.mutation_scaffold import MutationCandidate

        return MutationCandidate(
            **candidate.__dict__,
            risk_score=max(0.0, min(1.0, candidate.risk_score - 0.05)),
            complexity=max(0.0, min(1.0, candidate.complexity - 0.04)),
        )


class PerformanceRewriteOperator:
    metadata = OperatorMetadata(
        operator_key="performance_rewrite",
        category="performance",
        deterministic_rank=30,
        profile_bias=-0.01,
    )

    def transform(self, candidate: "MutationCandidate") -> "MutationCandidate":
        from runtime.autonomy.mutation_scaffold import MutationCandidate

        return MutationCandidate(
            **candidate.__dict__,
            expected_gain=max(0.0, min(1.0, candidate.expected_gain + 0.08)),
            complexity=max(0.0, min(1.0, candidate.complexity + 0.02)),
        )


class MutationOperatorRegistry:
    """Deterministic operator registration, selection, and safe application."""

    def __init__(self, operators: Iterable[MutationOperator] | None = None) -> None:
        defaults = operators or [ASTTransformOperator(), RefactorOperator(), PerformanceRewriteOperator()]
        self._operators = sorted(list(defaults), key=lambda op: (op.metadata.deterministic_rank, op.metadata.operator_key))

    def ordered_metadata(self) -> list[OperatorMetadata]:
        return [op.metadata for op in self._operators]

    def select_operator(
        self,
        candidate: "MutationCandidate",
        *,
        outcome_history: Mapping[str, OperatorOutcome] | None = None,
        profile: OperatorSelectionProfile | None = None,
    ) -> MutationOperator:
        history = outcome_history or {}
        p = profile or OperatorSelectionProfile()

        best = self._operators[0]
        best_score = float("-inf")
        for op in self._operators:
            meta = op.metadata
            hist = history.get(meta.operator_key, OperatorOutcome())
            score = (
                hist.success_rate
                + meta.profile_bias
                + (p.explore_ratio * 0.10)
                - (p.recent_failures_count * 0.01)
                - (meta.deterministic_rank * 0.0001)
            )
            if p.preferred_operator_hint and p.preferred_operator_hint == meta.operator_key:
                score += 0.08
            if candidate.agent_origin == "beast" and meta.category == "performance":
                score += 0.05
            if candidate.agent_origin == "architect" and meta.category == "refactor":
                score += 0.05
            if candidate.agent_origin == "dream" and meta.category == "ast":
                score += 0.05
            if score > best_score:
                best_score = score
                best = op

        return best

    def apply_operator(
        self,
        candidate: "MutationCandidate",
        *,
        outcome_history: Mapping[str, OperatorOutcome] | None = None,
        profile: OperatorSelectionProfile | None = None,
    ) -> "MutationCandidate":
        from runtime.autonomy.mutation_scaffold import MutationCandidate

        selected = self.select_operator(candidate, outcome_history=outcome_history, profile=profile)
        metadata = selected.metadata
        try:
            transformed = selected.transform(candidate)
        except Exception:
            transformed = candidate
            metadata = OperatorMetadata(
                operator_key="fallback_static",
                category="fallback",
                deterministic_rank=999,
                version="1.0.0",
                profile_bias=0.0,
            )

        return replace(
            transformed,
            operator_key=metadata.operator_key,
            operator_category=metadata.category,
            operator_version=metadata.version,
            operator_rank=metadata.deterministic_rank,
        )


__all__ = [
    "ASTTransformOperator",
    "MutationOperatorRegistry",
    "OperatorMetadata",
    "OperatorOutcome",
    "OperatorSelectionProfile",
    "PerformanceRewriteOperator",
    "RefactorOperator",
]
