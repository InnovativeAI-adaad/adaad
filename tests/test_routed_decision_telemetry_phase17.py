# SPDX-License-Identifier: Apache-2.0
"""Phase 17 — RoutedDecisionTelemetry tests (12 tests, T17-02-01..12)."""

import pytest

from runtime.intelligence.proposal import Proposal
from runtime.intelligence.router import IntelligenceRouter
from runtime.intelligence.routed_decision_telemetry import (
    EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION,
    ROUTED_DECISION_TELEMETRY_VERSION,
    InMemoryTelemetrySink,
    RoutedDecisionTelemetry,
    build_routed_decision_payload,
    _payload_digest,
)
from runtime.intelligence.strategy import StrategyInput
from runtime.governance.event_taxonomy import (
    CANONICAL_EVENT_TYPES,
    EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION as TAXONOMY_CONSTANT,
)


def _proposal_module():
    class _Module:
        def build(self, *, cycle_id, strategy_id, rationale):
            return Proposal(
                proposal_id=f"{cycle_id}:{strategy_id}",
                title="Refactor mutation scoring pipeline for throughput",
                summary="Refactors the mutation scoring pipeline to improve throughput and auditability.",
                estimated_impact=0.1,
                real_diff="--- a/runtime/scoring.py\n+++ b/runtime/scoring.py\n@@ -1 +1 @@",
                evidence={"test_coverage": 0.9, "review_passed": True},
                projected_impact={"performance": 0.8},
                metadata={"cycle_id": cycle_id, "strategy_id": strategy_id},
            )
    return _Module()


# T17-02-01  EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION is in CANONICAL_EVENT_TYPES
def test_event_type_in_canonical_event_types() -> None:
    assert EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION in CANONICAL_EVENT_TYPES
    assert TAXONOMY_CONSTANT in CANONICAL_EVENT_TYPES


# T17-02-02  IntelligenceRouter emits exactly one event per route() call
def test_router_emits_one_event_per_route_call() -> None:
    sink = InMemoryTelemetrySink()
    telemetry = RoutedDecisionTelemetry(sink=sink.emit)
    router = IntelligenceRouter(
        proposal_module=_proposal_module(),
        telemetry=telemetry,
    )
    router.route(StrategyInput(
        cycle_id="c-emit",
        mutation_score=0.80,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert len(sink) == 1


# T17-02-03  Emitted payload contains expected fields
def test_emitted_payload_has_required_fields() -> None:
    sink = InMemoryTelemetrySink()
    router = IntelligenceRouter(
        proposal_module=_proposal_module(),
        telemetry=RoutedDecisionTelemetry(sink=sink.emit),
    )
    router.route(StrategyInput(
        cycle_id="c-fields",
        mutation_score=0.80,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    entry = sink.entries()[0]
    for field in ["event_type", "cycle_id", "strategy_id", "outcome",
                  "composite_score", "dimension_verdicts", "review_digest",
                  "confidence", "risk_flags", "payload_digest"]:
        assert field in entry, f"Missing field: {field}"


# T17-02-04  event_type is correct constant
def test_emitted_event_type_is_correct() -> None:
    sink = InMemoryTelemetrySink()
    router = IntelligenceRouter(
        proposal_module=_proposal_module(),
        telemetry=RoutedDecisionTelemetry(sink=sink.emit),
    )
    router.route(StrategyInput(
        cycle_id="c-type",
        mutation_score=0.80,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert sink.entries()[0]["event_type"] == EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION


# T17-02-05  outcome in emitted event matches RoutedIntelligenceDecision.outcome
def test_emitted_outcome_matches_decision_outcome() -> None:
    sink = InMemoryTelemetrySink()
    router = IntelligenceRouter(
        proposal_module=_proposal_module(),
        telemetry=RoutedDecisionTelemetry(sink=sink.emit),
    )
    decision = router.route(StrategyInput(
        cycle_id="c-outcome",
        mutation_score=0.80,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert sink.entries()[0]["outcome"] == decision.outcome


# T17-02-06  strategy_id in emitted event matches StrategyDecision.strategy_id
def test_emitted_strategy_id_matches_decision() -> None:
    sink = InMemoryTelemetrySink()
    router = IntelligenceRouter(
        proposal_module=_proposal_module(),
        telemetry=RoutedDecisionTelemetry(sink=sink.emit),
    )
    decision = router.route(StrategyInput(
        cycle_id="c-sid",
        mutation_score=0.80,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert sink.entries()[0]["strategy_id"] == decision.strategy.strategy_id


# T17-02-07  payload_digest is deterministic
def test_payload_digest_is_deterministic() -> None:
    d1 = _payload_digest(
        cycle_id="c-det", strategy_id="adaptive_self_mutate",
        outcome="execute", composite=0.72, review_digest="sha256:abc"
    )
    d2 = _payload_digest(
        cycle_id="c-det", strategy_id="adaptive_self_mutate",
        outcome="execute", composite=0.72, review_digest="sha256:abc"
    )
    assert d1 == d2
    assert d1.startswith("sha256:")


# T17-02-08  Different strategy_ids produce different payload_digests
def test_different_strategy_ids_produce_different_digests() -> None:
    d1 = _payload_digest(
        cycle_id="c", strategy_id="adaptive_self_mutate",
        outcome="execute", composite=0.72, review_digest="sha256:abc"
    )
    d2 = _payload_digest(
        cycle_id="c", strategy_id="safety_hardening",
        outcome="execute", composite=0.72, review_digest="sha256:abc"
    )
    assert d1 != d2


# T17-02-09  Telemetry emission failure never propagates to router
def test_telemetry_failure_does_not_propagate() -> None:
    def _exploding_sink(_payload):
        raise RuntimeError("sink exploded")

    router = IntelligenceRouter(
        proposal_module=_proposal_module(),
        telemetry=RoutedDecisionTelemetry(sink=_exploding_sink),
    )
    # Should NOT raise — telemetry failure is isolated
    decision = router.route(StrategyInput(
        cycle_id="c-safe",
        mutation_score=0.80,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert decision is not None


# T17-02-10  Multiple route() calls each produce an entry
def test_multiple_route_calls_each_emit_event() -> None:
    sink = InMemoryTelemetrySink()
    router = IntelligenceRouter(
        proposal_module=_proposal_module(),
        telemetry=RoutedDecisionTelemetry(sink=sink.emit),
    )
    for i in range(3):
        router.route(StrategyInput(
            cycle_id=f"c-multi-{i}",
            mutation_score=0.80,
            governance_debt_score=0.10,
            lineage_health=0.70,
        ))
    assert len(sink) == 3


# T17-02-11  telemetry_version field is "17.0"
def test_telemetry_version_in_payload() -> None:
    sink = InMemoryTelemetrySink()
    router = IntelligenceRouter(
        proposal_module=_proposal_module(),
        telemetry=RoutedDecisionTelemetry(sink=sink.emit),
    )
    router.route(StrategyInput(
        cycle_id="c-ver",
        mutation_score=0.80,
        governance_debt_score=0.10,
        lineage_health=0.70,
    ))
    assert sink.entries()[0]["telemetry_version"] == ROUTED_DECISION_TELEMETRY_VERSION
    assert ROUTED_DECISION_TELEMETRY_VERSION == "17.0"


# T17-02-12  InMemoryTelemetrySink.entries() returns immutable snapshot
def test_in_memory_sink_entries_are_immutable_snapshot() -> None:
    sink = InMemoryTelemetrySink()
    sink.emit({"a": 1})
    entries = sink.entries()
    sink.emit({"b": 2})
    assert len(entries) == 1  # snapshot not affected by later emit
    assert len(sink.entries()) == 2
