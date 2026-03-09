# SPDX-License-Identifier: Apache-2.0
"""Router that ties strategy, proposal, and critique modules together.

Phase 17: strategy_id passed into CritiqueModule.review(); RoutedDecisionTelemetry
          emits routed_intelligence_decision.v1 on every route() call.
Phase 18: CritiqueSignalBuffer accumulates per-strategy critique outcomes across
          route() calls. breach_rate fed into StrategyModule.select() as payoff
          penalty — strategies that consistently breach floors rank lower.
          reset_epoch() clears buffer at epoch boundary (explicit, not automatic).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from runtime.intelligence.critique import CRITIQUE_DIMENSIONS, CritiqueModule, CritiqueResult
from runtime.intelligence.critique_signal import CritiqueSignalBuffer
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

    Phase 17: Routes strategy_id into CritiqueModule.review() so per-strategy
              dimension floor overrides are applied. Emits telemetry per route().
    Phase 18: Holds a CritiqueSignalBuffer that accumulates per-strategy critique
              outcomes across calls. Buffer feeds breach_rate penalties back into
              StrategyModule.select() -- closing the learn-from-critique loop.
              Call reset_epoch() at epoch boundary to clear buffer state.
    Signature unchanged -- backward compatible.
    """

    def __init__(
        self,
        *,
        strategy_module: StrategyModule | None = None,
        proposal_module: ProposalModule | None = None,
        critique_module: CritiqueModule | None = None,
        telemetry: RoutedDecisionTelemetry | None = None,
        signal_buffer: CritiqueSignalBuffer | None = None,
    ) -> None:
        self._strategy = strategy_module or StrategyModule()
        self._proposal = proposal_module or ProposalModule()
        self._critique = critique_module or CritiqueModule()
        self._telemetry = telemetry or RoutedDecisionTelemetry()
        self._signal_buffer = signal_buffer if signal_buffer is not None else CritiqueSignalBuffer()

    def route(self, context: StrategyInput) -> RoutedIntelligenceDecision:
        # Phase 18: pass accumulated signal so penalised strategies rank lower.
        strategy = self._strategy.select(context, signal_buffer=self._signal_buffer)

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

        # Phase 18: record outcome in buffer AFTER decision is built.
        self._signal_buffer.record(
            strategy_id=strategy.strategy_id,
            approved=critique.approved,
            risk_flags=list(critique.risk_flags),
        )

        # Phase 17: emit telemetry -- fail-isolated.
        self._telemetry.emit_routed_decision(decision)

        return decision

    def reset_epoch(self) -> None:
        """Clear CritiqueSignalBuffer at epoch boundary.

        Call this explicitly when starting a new epoch to ensure breach penalties
        from the previous epoch do not carry over.
        """
        self._signal_buffer.reset_epoch()

    @property
    def signal_buffer(self) -> CritiqueSignalBuffer:
        """Expose buffer for inspection and testing."""
        return self._signal_buffer

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
