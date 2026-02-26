# SPDX-License-Identifier: Apache-2.0
"""Strategy primitives for AGM-style runtime decisioning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class StrategyInput:
    """Typed context consumed by strategy selection."""

    cycle_id: str
    mutation_score: float
    governance_debt_score: float
    signals: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyDecision:
    """Normalized strategy output consumed by proposal generation."""

    strategy_id: str
    rationale: str
    confidence: float
    parameters: Mapping[str, Any] = field(default_factory=dict)


class StrategyModule:
    """Deterministic, side-effect-free baseline strategy module."""

    def select(self, context: StrategyInput) -> StrategyDecision:
        if context.mutation_score >= 0.7:
            return StrategyDecision(
                strategy_id="adaptive_self_mutate",
                rationale="mutation score exceeded baseline threshold",
                confidence=min(max(context.mutation_score, 0.0), 1.0),
                parameters={"threshold": 0.7},
            )
        return StrategyDecision(
            strategy_id="conservative_hold",
            rationale="mutation score below threshold",
            confidence=1.0 - min(max(context.mutation_score, 0.0), 1.0),
            parameters={"threshold": 0.7},
        )
