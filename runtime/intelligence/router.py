# SPDX-License-Identifier: Apache-2.0
"""Router that ties strategy, proposal, and critique modules together.

Phase 17:
  - strategy_id passed from StrategyDecision into CritiqueModule.review()
    so Phase 16 per-strategy dimension floor overrides are applied.
  - RoutedDecisionTelemetry emits routed_intelligence_decision.v1 on every
    route() call — append-only, fail-isolated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Any

from runtime.intelligence.critique import CRITIQUE_DIMENSIONS, CritiqueModule, CritiqueResult
from runtime.intelligence.proposal import Proposal, ProposalModule
from runtime.intelligence.routed_decision_telemetry import RoutedDecisionTelemetry
from runtime.intelligence.strategy import StrategyDecision, StrategyInput, StrategyModule

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoutedIntelligenceDecision:
    strategy: StrategyDecision
    proposal: Proposal
    critique: CritiqueResult

    @property
    def outcome(self) -> str:
        return "execute" if self.critique.approved else "hold"


class IntelligenceRouter:
    """Stable orchestrator for AGM step composition.

    Phase 17:
      - Routes strategy_id from StrategyDecision into CritiqueModule.review()
        so per-strategy dimension floor overrides (Phase 16) are applied.
      - Emits routed_intelligence_decision.v1 telemetry on every route() call.
        Telemetry emission is fail-isolated — router outcome never degraded.
    Signature unchanged — backward compatible.
    """

    def __init__(
        self,
        *,
        strategy_module: StrategyModule | None = None,
        proposal_module: ProposalModule | None = None,
        critique_module: CritiqueModule | None = None,
        telemetry: RoutedDecisionTelemetry | None = None,
    ) -> None:
        self._strategy = strategy_module or StrategyModule()
        self._proposal = proposal_module or ProposalModule()
        self._critique = critique_module or CritiqueModule()
        self._telemetry = telemetry or RoutedDecisionTelemetry()

    def route(self, context: StrategyInput) -> RoutedIntelligenceDecision:
        strategy = self._strategy.select(context)
        proposal = self._proposal.build(
            cycle_id=context.cycle_id,
            strategy_id=strategy.strategy_id,
            rationale=strategy.rationale,
        )
        # Phase 17: pass strategy_id so per-strategy floor overrides are applied.
        critique = self._critique.review(proposal, strategy_id=strategy.strategy_id)
        self._validate_critique(critique)

        decision = RoutedIntelligenceDecision(
            strategy=strategy, proposal=proposal, critique=critique
        )

        # Phase 17: emit telemetry — fail-isolated.
        self._telemetry.emit_routed_decision(decision)

        return decision

    def _validate_critique(self, critique: CritiqueResult) -> None:
        missing_dimensions = [
            dimension
            for dimension in CRITIQUE_DIMENSIONS
            if dimension not in critique.per_dimension_scores
        ]
        if missing_dimensions:
            raise ValueError(
                f"critique missing required dimensions: {', '.join(missing_dimensions)}"
            )
