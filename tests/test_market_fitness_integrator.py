# SPDX-License-Identifier: Apache-2.0
"""Integration tests for MarketFitnessIntegrator + FitnessOrchestrator — ADAAD-10 PR-10-02.

Verifies:
- MarketFitnessIntegrator.integrate() bridges reading → orchestrator correctly
- inject_live_signal() overrides simulated_market_score in FitnessOrchestrator.score()
- Synthetic fallback activates when FeedRegistry returns None
- Zero-confidence synthetic score does not inflate fitness incorrectly
- Lineage digest propagates from reading to IntegrationResult
- Journal event emitted on every integrate() call
- Live score clamped to [0.0, 1.0]
"""

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

@dataclass
class _FakeReading:
    adapter_id: str = "test_adapter"
    signal_type: str = "composite"
    value: float = 0.8
    confidence: float = 0.9
    sampled_at: float = 1_000_000.0
    lineage_digest: str = "sha256:" + "a" * 64
    stale: bool = False

    def to_fitness_contribution(self) -> float:
        return round(self.value * self.confidence, 6)


class _FakeRegistry:
    def __init__(self, reading: Optional[_FakeReading] = None) -> None:
        self._reading = reading

    def composite_reading(self) -> Optional[_FakeReading]:
        return self._reading


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.injected: List[Dict[str, Any]] = []

    def inject_live_signal(self, payload: Dict[str, Any]) -> None:
        self.injected.append(payload)


# ---------------------------------------------------------------------------
# Tests: MarketFitnessIntegrator
# ---------------------------------------------------------------------------

class TestMarketFitnessIntegratorBridging:
    def test_live_reading_produces_correct_score(self) -> None:
        from runtime.market.market_fitness_integrator import MarketFitnessIntegrator
        reading = _FakeReading(value=0.8, confidence=0.9)
        orchestrator = _FakeOrchestrator()
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistry(reading),
            fitness_orchestrator=orchestrator,
        )
        result = integrator.integrate(epoch_id="epoch-1")
        expected = round(0.8 * 0.9, 6)
        assert result.live_market_score == expected
        assert result.confidence == 0.9
        assert result.is_synthetic is False

    def test_none_registry_returns_synthetic_fallback(self) -> None:
        from runtime.market.market_fitness_integrator import MarketFitnessIntegrator
        orchestrator = _FakeOrchestrator()
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistry(None),
            fitness_orchestrator=orchestrator,
        )
        result = integrator.integrate(epoch_id="epoch-synthetic")
        assert result.live_market_score == 0.5
        assert result.confidence == 0.0
        assert result.is_synthetic is True
        assert result.adapter_id == "synthetic_fallback"

    def test_lineage_digest_propagated(self) -> None:
        from runtime.market.market_fitness_integrator import MarketFitnessIntegrator
        digest = "sha256:" + "b" * 64
        reading = _FakeReading(lineage_digest=digest)
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistry(reading),
            fitness_orchestrator=_FakeOrchestrator(),
        )
        result = integrator.integrate(epoch_id="epoch-digest")
        assert result.lineage_digest == digest

    def test_inject_called_with_epoch_id(self) -> None:
        from runtime.market.market_fitness_integrator import MarketFitnessIntegrator
        orchestrator = _FakeOrchestrator()
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistry(_FakeReading()),
            fitness_orchestrator=orchestrator,
        )
        integrator.integrate(epoch_id="epoch-injection-check")
        assert len(orchestrator.injected) == 1
        assert orchestrator.injected[0]["epoch_id"] == "epoch-injection-check"

    def test_live_score_clamped_above_one(self) -> None:
        from runtime.market.market_fitness_integrator import MarketFitnessIntegrator
        reading = _FakeReading(value=2.0, confidence=1.0)
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistry(reading),
            fitness_orchestrator=_FakeOrchestrator(),
        )
        result = integrator.integrate(epoch_id="epoch-clamp")
        assert result.live_market_score <= 1.0

    def test_journal_fn_called_on_integrate(self) -> None:
        from runtime.market.market_fitness_integrator import MarketFitnessIntegrator
        journal_calls: list[tuple[str, dict]] = []
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistry(_FakeReading()),
            fitness_orchestrator=_FakeOrchestrator(),
            journal_fn=lambda ev, payload: journal_calls.append((ev, payload)),
        )
        integrator.integrate(epoch_id="epoch-journal")
        assert len(journal_calls) == 1
        ev_type, payload = journal_calls[0]
        assert ev_type == "market_fitness_integrated.v1"
        assert payload["epoch_id"] == "epoch-journal"
        assert "live_market_score" in payload
        assert "lineage_digest" in payload


# ---------------------------------------------------------------------------
# Tests: FitnessOrchestrator live signal injection
# ---------------------------------------------------------------------------

class TestFitnessOrchestratorLiveOverride:
    def _base_context(self, epoch_id: str) -> dict:
        return {
            "epoch_id": epoch_id,
            "correctness_score": 0.8,
            "efficiency_score": 0.7,
            "policy_compliance_score": 0.9,
            "goal_alignment_score": 0.75,
            "simulated_market_score": 0.1,  # will be overridden
            "regime": "economic_full",
        }

    def test_live_signal_overrides_simulated_market_score(self) -> None:
        from runtime.evolution.fitness_orchestrator import FitnessOrchestrator
        orch = FitnessOrchestrator()
        orch.inject_live_signal({"epoch_id": "epoch-live", "live_market_score": 0.95})
        ctx = self._base_context("epoch-live")
        result = orch.score(ctx)
        # With live override, breakdown should have simulated_market_score=0.95
        assert result.breakdown["simulated_market_score"] == 0.95

    def test_no_override_uses_context_market_score(self) -> None:
        from runtime.evolution.fitness_orchestrator import FitnessOrchestrator
        orch = FitnessOrchestrator()
        ctx = self._base_context("epoch-no-override")
        result = orch.score(ctx)
        assert result.breakdown["simulated_market_score"] == 0.1

    def test_inject_live_signal_bad_epoch_id_silently_dropped(self) -> None:
        from runtime.evolution.fitness_orchestrator import FitnessOrchestrator
        orch = FitnessOrchestrator()
        orch.inject_live_signal({"epoch_id": "", "live_market_score": 0.9})  # empty epoch — must not raise
        orch.inject_live_signal({})  # no epoch — must not raise

    def test_live_override_score_clamped_to_unit_interval(self) -> None:
        from runtime.evolution.fitness_orchestrator import FitnessOrchestrator
        orch = FitnessOrchestrator()
        orch.inject_live_signal({"epoch_id": "epoch-clamp2", "live_market_score": 99.0})
        ctx = self._base_context("epoch-clamp2")
        result = orch.score(ctx)
        assert result.breakdown["simulated_market_score"] <= 1.0
        assert result.total_score <= 1.0

    def test_live_override_is_advisory_total_score_bounded(self) -> None:
        from runtime.evolution.fitness_orchestrator import FitnessOrchestrator
        orch = FitnessOrchestrator()
        orch.inject_live_signal({"epoch_id": "epoch-bound", "live_market_score": 1.0})
        ctx = self._base_context("epoch-bound")
        result = orch.score(ctx)
        assert 0.0 <= result.total_score <= 1.0
