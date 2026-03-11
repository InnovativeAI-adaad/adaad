# SPDX-License-Identifier: Apache-2.0
"""Phase 18 — IntelligenceRouter CritiqueSignalBuffer wire tests (10 tests, T18-02-01..10)."""

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.intelligence.critique_signal import CritiqueSignalBuffer
from runtime.intelligence.proposal import Proposal
from runtime.intelligence.router import IntelligenceRouter
from runtime.intelligence.strategy import StrategyInput, STRATEGY_TAXONOMY


def _good_proposal_module():
    class _M:
        def build(self, *, cycle_id, strategy_id, rationale):
            return Proposal(
                proposal_id=f"{cycle_id}:{strategy_id}",
                title="Refactor mutation scoring pipeline for throughput and auditability",
                summary="Refactors the mutation scoring pipeline to improve throughput and auditability.",
                estimated_impact=0.1,
                real_diff="--- a/runtime/scoring.py\n+++ b/runtime/scoring.py\n@@ -1 +1 @@",
                evidence={"test_coverage": 0.9, "review_passed": True},
                projected_impact={"performance": 0.8, "maintainability": 0.7},
                metadata={"cycle_id": cycle_id, "strategy_id": strategy_id},
            )
    return _M()


def _ctx(cycle_id="c-18", **kw) -> StrategyInput:
    defaults = dict(
        mutation_score=0.75,
        governance_debt_score=0.15,
        lineage_health=0.70,
        resource_budget=0.80,
    )
    defaults.update(kw)
    return StrategyInput(cycle_id=cycle_id, **defaults)


# T18-02-01  Router exposes signal_buffer property
def test_router_exposes_signal_buffer() -> None:
    router = IntelligenceRouter(proposal_module=_good_proposal_module())
    assert isinstance(router.signal_buffer, CritiqueSignalBuffer)


# T18-02-02  After one route(), buffer has one record for the chosen strategy
def test_buffer_has_one_record_after_route() -> None:
    router = IntelligenceRouter(proposal_module=_good_proposal_module())
    decision = router.route(_ctx())
    sid = decision.strategy.strategy_id
    assert router.signal_buffer.total_count(sid) == 1


# T18-02-03  Buffer accumulates across multiple route() calls
def test_buffer_accumulates_across_routes() -> None:
    router = IntelligenceRouter(proposal_module=_good_proposal_module())
    ctx = _ctx()
    d1 = router.route(ctx)
    d2 = router.route(ctx)
    total = sum(
        router.signal_buffer.total_count(sid) for sid in STRATEGY_TAXONOMY
    )
    assert total == 2


# T18-02-04  reset_epoch() clears buffer
def test_reset_epoch_clears_buffer() -> None:
    router = IntelligenceRouter(proposal_module=_good_proposal_module())
    router.route(_ctx())
    router.reset_epoch()
    for sid in STRATEGY_TAXONOMY:
        assert router.signal_buffer.total_count(sid) == 0


# T18-02-05  Injected signal_buffer is used (not a new one)
def test_injected_signal_buffer_is_used() -> None:
    buf = CritiqueSignalBuffer()
    router = IntelligenceRouter(
        proposal_module=_good_proposal_module(),
        signal_buffer=buf,
    )
    router.route(_ctx())
    assert buf is router.signal_buffer
    total = sum(buf.total_count(sid) for sid in STRATEGY_TAXONOMY)
    assert total == 1


# T18-02-06  route() still returns RoutedIntelligenceDecision with valid outcome
def test_route_returns_valid_decision() -> None:
    router = IntelligenceRouter(proposal_module=_good_proposal_module())
    decision = router.route(_ctx())
    assert decision.outcome in ("execute", "hold")
    assert decision.strategy.strategy_id in STRATEGY_TAXONOMY


# T18-02-07  breach_penalties key present in strategy parameters after route()
def test_breach_penalties_in_strategy_parameters() -> None:
    router = IntelligenceRouter(proposal_module=_good_proposal_module())
    decision = router.route(_ctx())
    assert "breach_penalties" in decision.strategy.parameters


# T18-02-08  After reset_epoch, next route() starts fresh (zero penalties)
def test_fresh_route_after_reset_has_zero_penalties() -> None:
    router = IntelligenceRouter(proposal_module=_good_proposal_module())
    for _ in range(3):
        router.route(_ctx())
    router.reset_epoch()
    decision = router.route(_ctx())
    penalties = decision.strategy.parameters.get("breach_penalties", {})
    assert all(v == 0.0 for v in penalties.values())


# T18-02-09  Existing router tests still pass — dimension contract enforced
def test_dimension_contract_still_enforced() -> None:
    from runtime.intelligence.critique import CritiqueModule, CritiqueResult

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
        proposal_module=_good_proposal_module(),
        critique_module=_IncompleteCritique(),
    )
    with pytest.raises(ValueError, match="critique missing required dimensions"):
        router.route(_ctx())


# T18-02-10  signal_buffer.snapshot() after multiple routes is deterministic
def test_buffer_snapshot_is_deterministic() -> None:
    ctx = _ctx()
    router = IntelligenceRouter(proposal_module=_good_proposal_module())
    for _ in range(4):
        router.route(ctx)
    snap1 = router.signal_buffer.snapshot()
    snap2 = router.signal_buffer.snapshot()
    assert snap1 == snap2
    assert list(snap1.keys()) == sorted(snap1.keys())
