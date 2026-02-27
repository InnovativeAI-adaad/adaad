# SPDX-License-Identifier: Apache-2.0

import pytest

from runtime.intelligence.critique import CRITIQUE_DIMENSIONS, CritiqueModule, CritiqueResult
from runtime.intelligence.proposal import Proposal
from runtime.intelligence.router import IntelligenceRouter
from runtime.intelligence.strategy import StrategyInput


class PositiveImpactProposalModule:
    def build(self, *, cycle_id: str, strategy_id: str, rationale: str) -> Proposal:
        return Proposal(
            proposal_id=f"{cycle_id}:{strategy_id}",
            title="positive",
            summary=rationale,
            estimated_impact=0.5,
            metadata={"cycle_id": cycle_id, "strategy_id": strategy_id},
        )


class NegativeImpactProposalModule:
    def build(self, *, cycle_id: str, strategy_id: str, rationale: str) -> Proposal:
        return Proposal(
            proposal_id=f"{cycle_id}:{strategy_id}",
            title="negative",
            summary=rationale,
            estimated_impact=-0.1,
            metadata={"cycle_id": cycle_id, "strategy_id": strategy_id},
        )


class IncompleteDimensionCritiqueModule(CritiqueModule):
    def review(self, proposal: Proposal) -> CritiqueResult:
        return CritiqueResult(
            approved=True,
            per_dimension_scores={"risk": 0.0},
            weighted_aggregate=0.0,
            risk_score=0.0,
            notes="incomplete",
            metadata={"proposal_id": proposal.proposal_id},
        )


def _strategy_input() -> StrategyInput:
    return StrategyInput(cycle_id="cycle-1", mutation_score=0.8, governance_debt_score=0.2)


def test_router_executes_and_carries_five_dimensions_for_approved_proposal() -> None:
    router = IntelligenceRouter(proposal_module=PositiveImpactProposalModule())

    decision = router.route(_strategy_input())

    assert decision.outcome == "execute"
    assert decision.critique.approved is True
    assert set(decision.critique.per_dimension_scores.keys()) == set(CRITIQUE_DIMENSIONS)
    assert decision.critique.per_dimension_scores["risk"] == decision.critique.risk_score


def test_router_holds_for_high_risk_proposal_with_dimension_contract() -> None:
    router = IntelligenceRouter(proposal_module=NegativeImpactProposalModule())

    decision = router.route(_strategy_input())

    assert decision.outcome == "hold"
    assert decision.critique.approved is False
    assert len(decision.critique.per_dimension_scores) == 5
    assert decision.critique.per_dimension_scores["risk"] == decision.critique.risk_score == 1.0


def test_router_rejects_incomplete_dimension_contract() -> None:
    router = IntelligenceRouter(
        proposal_module=PositiveImpactProposalModule(),
        critique_module=IncompleteDimensionCritiqueModule(),
    )

    with pytest.raises(ValueError, match="critique missing required dimensions"):
        router.route(_strategy_input())
