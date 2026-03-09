# SPDX-License-Identifier: Apache-2.0
"""Phase 20 — runtime.intelligence public API contract tests (10 tests, T20-01-01..10).

These tests exist to catch silent removal of exported symbols across future refactors.
They import exclusively via `from runtime.intelligence import X` — the public surface.
"""

import pytest

# ---------------------------------------------------------------------------
# T20-01-01  STRATEGY_TAXONOMY importable from runtime.intelligence
# ---------------------------------------------------------------------------
def test_strategy_taxonomy_importable() -> None:
    from runtime.intelligence import STRATEGY_TAXONOMY
    assert isinstance(STRATEGY_TAXONOMY, frozenset)
    assert len(STRATEGY_TAXONOMY) == 6


# ---------------------------------------------------------------------------
# T20-01-02  STRATEGY_TAXONOMY contains all expected strategy IDs
# ---------------------------------------------------------------------------
def test_strategy_taxonomy_contains_all_six_strategies() -> None:
    from runtime.intelligence import STRATEGY_TAXONOMY
    expected = {
        "safety_hardening",
        "structural_refactor",
        "test_coverage_expansion",
        "performance_optimization",
        "adaptive_self_mutate",
        "conservative_hold",
    }
    assert STRATEGY_TAXONOMY == expected


# ---------------------------------------------------------------------------
# T20-01-03  CritiqueSignalBuffer importable from runtime.intelligence
# ---------------------------------------------------------------------------
def test_critique_signal_buffer_importable() -> None:
    from runtime.intelligence import CritiqueSignalBuffer
    buf = CritiqueSignalBuffer()
    assert buf.breach_rate("any_strategy") == 0.0


# ---------------------------------------------------------------------------
# T20-01-04  RoutedDecisionTelemetry importable from runtime.intelligence
# ---------------------------------------------------------------------------
def test_routed_decision_telemetry_importable() -> None:
    from runtime.intelligence import RoutedDecisionTelemetry
    tel = RoutedDecisionTelemetry()
    assert tel.default_sink is not None


# ---------------------------------------------------------------------------
# T20-01-05  InMemoryTelemetrySink importable from runtime.intelligence
# ---------------------------------------------------------------------------
def test_in_memory_telemetry_sink_importable() -> None:
    from runtime.intelligence import InMemoryTelemetrySink
    sink = InMemoryTelemetrySink()
    sink.emit({"event_type": "test"})
    assert len(sink) == 1


# ---------------------------------------------------------------------------
# T20-01-06  EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION importable and correct
# ---------------------------------------------------------------------------
def test_event_type_constant_importable() -> None:
    from runtime.intelligence import EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION
    assert EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION == "routed_intelligence_decision.v1"


# ---------------------------------------------------------------------------
# T20-01-07  All Phase 16/17/18 symbols present in __all__
# ---------------------------------------------------------------------------
def test_phase_16_17_18_symbols_in_all() -> None:
    import runtime.intelligence as ri
    required = {
        "STRATEGY_TAXONOMY",
        "CritiqueSignalBuffer",
        "RoutedDecisionTelemetry",
        "InMemoryTelemetrySink",
        "EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION",
    }
    missing = required - set(ri.__all__)
    assert not missing, f"Missing from __all__: {missing}"


# ---------------------------------------------------------------------------
# T20-01-08  Core pre-Phase-16 symbols still present in __all__
# ---------------------------------------------------------------------------
def test_legacy_symbols_still_in_all() -> None:
    import runtime.intelligence as ri
    legacy = {
        "IntelligenceRouter",
        "StrategyDecision",
        "StrategyInput",
        "StrategyModule",
        "CritiqueModule",
        "CritiqueResult",
        "Proposal",
        "ProposalModule",
    }
    missing = legacy - set(ri.__all__)
    assert not missing, f"Legacy symbols removed from __all__: {missing}"


# ---------------------------------------------------------------------------
# T20-01-09  CritiqueSignalBuffer from public import is same class as direct import
# ---------------------------------------------------------------------------
def test_critique_signal_buffer_identity() -> None:
    from runtime.intelligence import CritiqueSignalBuffer as PubCSB
    from runtime.intelligence.critique_signal import CritiqueSignalBuffer as DirectCSB
    assert PubCSB is DirectCSB


# ---------------------------------------------------------------------------
# T20-01-10  RoutedDecisionTelemetry from public import is same class as direct import
# ---------------------------------------------------------------------------
def test_routed_decision_telemetry_identity() -> None:
    from runtime.intelligence import RoutedDecisionTelemetry as PubRDT
    from runtime.intelligence.routed_decision_telemetry import RoutedDecisionTelemetry as DirectRDT
    assert PubRDT is DirectRDT
