# SPDX-License-Identifier: Apache-2.0
"""Router that ties strategy, proposal, and critique modules together."""

from __future__ import annotations

from dataclasses import dataclass

from runtime.intelligence.critique import CRITIQUE_DIMENSIONS, CritiqueModule, CritiqueResult
from runtime.intelligence.proposal import Proposal, ProposalModule
from runtime.intelligence.strategy import StrategyDecision, StrategyInput, StrategyModule


@dataclass(frozen=True)
class RoutedIntelligenceDecision:
    strategy: StrategyDecision
    proposal: Proposal
    critique: CritiqueResult

    @property
    def outcome(self) -> str:
        return "execute" if self.critique.approved else "hold"


class IntelligenceRouter:
    """Stable orchestrator for AGM step composition."""

    def __init__(
        self,
        *,
        strategy_module: StrategyModule | None = None,
        proposal_module: ProposalModule | None = None,
        critique_module: CritiqueModule | None = None,
    ) -> None:
        self._strategy = strategy_module or StrategyModule()
        self._proposal = proposal_module or ProposalModule()
        self._critique = critique_module or CritiqueModule()

    def route(self, context: StrategyInput) -> RoutedIntelligenceDecision:
        strategy = self._strategy.select(context)
        proposal = self._proposal.build(
            cycle_id=context.cycle_id,
            strategy_id=strategy.strategy_id,
            rationale=strategy.rationale,
        )
        critique = self._critique.review(proposal)
        self._validate_critique(critique)
        return RoutedIntelligenceDecision(strategy=strategy, proposal=proposal, critique=critique)

    def _validate_critique(self, critique: CritiqueResult) -> None:
        missing_dimensions = [dimension for dimension in CRITIQUE_DIMENSIONS if dimension not in critique.per_dimension_scores]
        if missing_dimensions:
            raise ValueError(f"critique missing required dimensions: {', '.join(missing_dimensions)}")
