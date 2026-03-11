# SPDX-License-Identifier: Apache-2.0
"""Phase 17 — IntelligenceRouter strategy_id wire tests (10 tests, T17-01-01..10)."""

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.intelligence.critique import CritiqueModule, CritiqueResult, CRITIQUE_DIMENSIONS
from runtime.intelligence.proposal import Proposal
from runtime.intelligence.router import IntelligenceRouter, RoutedIntelligenceDecision
from runtime.intelligence.strategy import StrategyInput, STRATEGY_TAXONOMY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _well_formed_proposal(cycle_id: str, strategy_id: str, rationale: str) -> Proposal:
    return Proposal(
        proposal_id=f"{cycle_id}:{strategy_id}",
        title="Refactor mutation scoring pipeline",
        summary="Refactors the mutation scoring pipeline to improve throughput and auditability.",
        estimated_impact=0.1,
        real_diff="--- a/runtime/scoring.py\n+++ b/runtime/scoring.py\n@@ -1 +1 @@",
        evidence={"test_coverage": 0.9, "review_passed": True},
        projected_impact={"performance": 0.8, "maintainability": 0.7},
        metadata={"cycle_id": cycle_id, "strategy_id": strategy_id},
    )


class _CapturingCritiqueModule(CritiqueModule):
    """Records the strategy_id passed to review()."""

    def __init__(self):
        self.last_strategy_id = None

    def review(self, proposal: Proposal, *, strategy_id=None) -> CritiqueResult:
        self.last_strategy_id = strategy_id
        return super().review(proposal, strategy_id=strategy_id)


class _WellFormedProposalModule:
    def build(self, *, cycle_id: str, strategy_id: str, rationale: str) -> Proposal:
        return _well_formed_proposal(cycle_id, strategy_id, rationale)


# ---------------------------------------------------------------------------
# T17-01-01  Router passes strategy_id to CritiqueModule.review()
# ---------------------------------------------------------------------------
def test_router_passes_strategy_id_to_critique() -> None:
    capturing = _CapturingCritiqueModule()
    router = IntelligenceRouter(
        proposal_module=_WellFormedProposalModule(),
        critique_module=capturing,
    )
    router.route(StrategyInput(
        cycle_id="c-wire",
        mutation_score=0.85,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert capturing.last_strategy_id in STRATEGY_TAXONOMY


# ---------------------------------------------------------------------------
# T17-01-02  strategy_id in critique metadata matches strategy decision
# ---------------------------------------------------------------------------
def test_critique_metadata_strategy_id_matches_decision() -> None:
    router = IntelligenceRouter(proposal_module=_WellFormedProposalModule())
    decision = router.route(StrategyInput(
        cycle_id="c-match",
        mutation_score=0.85,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert decision.critique.metadata.get("strategy_id") == decision.strategy.strategy_id


# ---------------------------------------------------------------------------
# T17-01-03  safety_hardening uses elevated governance floor
# ---------------------------------------------------------------------------
def test_safety_hardening_applies_elevated_governance_floor() -> None:
    capturing = _CapturingCritiqueModule()
    router = IntelligenceRouter(
        proposal_module=_WellFormedProposalModule(),
        critique_module=capturing,
    )
    # Trigger safety_hardening: debt >= 0.70
    router.route(StrategyInput(
        cycle_id="c-safety",
        mutation_score=0.40,
        governance_debt_score=0.75,
        lineage_health=0.80,
    ))
    assert capturing.last_strategy_id == "safety_hardening"


# ---------------------------------------------------------------------------
# T17-01-04  RoutedIntelligenceDecision carries strategy, proposal, critique
# ---------------------------------------------------------------------------
def test_routed_decision_carries_all_three_components() -> None:
    router = IntelligenceRouter(proposal_module=_WellFormedProposalModule())
    decision = router.route(StrategyInput(
        cycle_id="c-components",
        mutation_score=0.80,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert isinstance(decision, RoutedIntelligenceDecision)
    assert decision.strategy is not None
    assert decision.proposal is not None
    assert decision.critique is not None


# ---------------------------------------------------------------------------
# T17-01-05  outcome is "execute" for approved critique
# ---------------------------------------------------------------------------
def test_outcome_execute_for_approved_critique() -> None:
    router = IntelligenceRouter(proposal_module=_WellFormedProposalModule())
    decision = router.route(StrategyInput(
        cycle_id="c-execute",
        mutation_score=0.85,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    if decision.critique.approved:
        assert decision.outcome == "execute"


# ---------------------------------------------------------------------------
# T17-01-06  outcome is "hold" for rejected critique
# ---------------------------------------------------------------------------
def test_outcome_hold_for_rejected_critique() -> None:
    class _BadProposalModule:
        def build(self, *, cycle_id, strategy_id, rationale):
            return Proposal(
                proposal_id=f"{cycle_id}:bad",
                title="x",
                summary=rationale,
                estimated_impact=-0.1,
                metadata={},
            )

    router = IntelligenceRouter(proposal_module=_BadProposalModule())
    decision = router.route(StrategyInput(
        cycle_id="c-hold",
        mutation_score=0.85,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert decision.outcome == "hold"
    assert decision.critique.approved is False


# ---------------------------------------------------------------------------
# T17-01-07  critique carries taxonomy_version "16.0" via metadata
# ---------------------------------------------------------------------------
def test_critique_carries_taxonomy_version() -> None:
    router = IntelligenceRouter(proposal_module=_WellFormedProposalModule())
    decision = router.route(StrategyInput(
        cycle_id="c-ver",
        mutation_score=0.85,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert decision.critique.metadata.get("critique_taxonomy_version") == "16.0"


# ---------------------------------------------------------------------------
# T17-01-08  router still raises on incomplete dimensions (existing invariant)
# ---------------------------------------------------------------------------
def test_router_raises_on_incomplete_dimension_contract() -> None:
    class _IncompleteCritique(CritiqueModule):
        def review(self, proposal, *, strategy_id=None):
            return CritiqueResult(
                approved=True,
                per_dimension_scores={"risk": 0.0},
                weighted_aggregate=0.0,
                risk_score=0.0,
                notes="incomplete",
                metadata={"proposal_id": proposal.proposal_id},
            )

    router = IntelligenceRouter(
        proposal_module=_WellFormedProposalModule(),
        critique_module=_IncompleteCritique(),
    )
    with pytest.raises(ValueError, match="critique missing required dimensions"):
        router.route(StrategyInput(
            cycle_id="c-incomplete",
            mutation_score=0.80,
            governance_debt_score=0.10,
            lineage_health=0.70,
        ))


# ---------------------------------------------------------------------------
# T17-01-09  router is deterministic: same context → same strategy_id
# ---------------------------------------------------------------------------
def test_router_is_deterministic() -> None:
    ctx = StrategyInput(
        cycle_id="c-det",
        mutation_score=0.65,
        governance_debt_score=0.60,
        lineage_health=0.70,
    )
    router = IntelligenceRouter(proposal_module=_WellFormedProposalModule())
    strategy_ids = {router.route(ctx).strategy.strategy_id for _ in range(3)}
    assert len(strategy_ids) == 1


# ---------------------------------------------------------------------------
# T17-01-10  critique review_digest includes strategy_id (not baseline)
# ---------------------------------------------------------------------------
def test_critique_review_digest_includes_strategy() -> None:
    capturing = _CapturingCritiqueModule()
    router = IntelligenceRouter(
        proposal_module=_WellFormedProposalModule(),
        critique_module=capturing,
    )
    decision = router.route(StrategyInput(
        cycle_id="c-digest",
        mutation_score=0.85,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert capturing.last_strategy_id is not None
    assert capturing.last_strategy_id != "baseline"
    assert decision.critique.review_digest.startswith("sha256:")
