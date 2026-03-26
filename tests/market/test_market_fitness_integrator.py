# SPDX-License-Identifier: Apache-2.0
"""Tests for MarketFitnessIntegrator — ADAAD-10 PR-10-02."""
from __future__ import annotations
from runtime.market.feed_registry import FeedRegistry
from runtime.market.adapters.live_adapters import DemandSignalAdapter, VolatilityIndexAdapter
from runtime.market.market_fitness_integrator import MarketFitnessIntegrator
from runtime.evolution.fitness_orchestrator import FitnessOrchestrator


def _reg(dau=0.7, vol=0.2):
    reg = FeedRegistry()
    reg.register(DemandSignalAdapter().with_source(
        lambda: {"dau": dau, "wau": 0.80, "retention_d7": 0.60, "confidence": 0.9}))
    reg.register(VolatilityIndexAdapter().with_source(
        lambda: {"volatility": vol, "confidence": 0.8}))
    return reg


class TestMarketFitnessIntegrator:
    def test_enrich_uses_injected_now_fn_for_deterministic_timestamp(self):
        integrator = MarketFitnessIntegrator(registry=_reg(), now_fn=lambda: 1234.5)
        enriched = integrator.enrich({"epoch_id": "epoch-clock"})
        assert enriched["market_signal_enriched_at"] == 1234.5
        assert integrator.last_enrichment is not None
        assert integrator.last_enrichment.enriched_at == 1234.5

    def test_enrich_injects_market_score(self):
        integrator = MarketFitnessIntegrator(registry=_reg())
        ctx = {"epoch_id": "epoch-1", "correctness_score": 0.8}
        enriched = integrator.enrich(ctx)
        assert "simulated_market_score" in enriched
        assert 0.0 <= enriched["simulated_market_score"] <= 1.0

    def test_enrich_does_not_mutate_input(self):
        integrator = MarketFitnessIntegrator(registry=_reg())
        ctx = {"epoch_id": "epoch-1", "correctness_score": 0.8}
        original = dict(ctx)
        integrator.enrich(ctx)
        assert ctx == original

    def test_lineage_digest_propagated(self):
        integrator = MarketFitnessIntegrator(registry=_reg())
        enriched = integrator.enrich({"epoch_id": "epoch-2"})
        assert enriched["market_signal_lineage_digest"].startswith("sha256:")

    def test_source_is_live_for_healthy_adapters(self):
        integrator = MarketFitnessIntegrator(registry=_reg())
        enriched = integrator.enrich({"epoch_id": "epoch-3"})
        assert enriched["market_signal_source"] in ("live", "cached")

    def test_fallback_on_empty_registry(self):
        integrator = MarketFitnessIntegrator(registry=FeedRegistry(), fallback_score=0.42)
        enriched = integrator.enrich({"epoch_id": "epoch-4"})
        assert enriched["simulated_market_score"] == 0.42
        assert enriched["market_signal_source"] == "synthetic"

    def test_last_enrichment_record_captured(self):
        integrator = MarketFitnessIntegrator(registry=_reg())
        integrator.enrich({"epoch_id": "epoch-5"})
        assert integrator.last_enrichment is not None
        assert integrator.last_enrichment.adapter_count == 2

    def test_enrich_default_api_behavior_without_now_fn(self):
        integrator = MarketFitnessIntegrator(registry=_reg())
        enriched = integrator.enrich({"epoch_id": "epoch-default-clock"})
        assert isinstance(enriched["market_signal_enriched_at"], float)

    def test_enrichment_never_raises_on_broken_registry(self):
        class _BrokenRegistry:
            def fetch_all(self): raise RuntimeError("db exploded")
        integrator = MarketFitnessIntegrator(registry=_BrokenRegistry())
        enriched = integrator.enrich({"epoch_id": "epoch-6"})
        assert enriched["simulated_market_score"] == 0.50  # default fallback

    def test_journal_fn_called_on_enrich(self):
        calls = []
        integrator = MarketFitnessIntegrator(registry=_reg(), journal_fn=lambda **kw: calls.append(kw))
        integrator.enrich({"epoch_id": "epoch-7"})
        assert len(calls) == 1
        assert calls[0]["tx_type"] == "market_fitness_signal_enriched.v1"

    def test_high_demand_yields_higher_score_than_low(self):
        hi_int = MarketFitnessIntegrator(registry=_reg(dau=0.95))
        lo_int = MarketFitnessIntegrator(registry=_reg(dau=0.10))
        hi = hi_int.enrich({"epoch_id": "epoch-hi"})["simulated_market_score"]
        lo = lo_int.enrich({"epoch_id": "epoch-lo"})["simulated_market_score"]
        assert hi > lo


class TestFitnessOrchestratorLiveWiring:
    """Integration: MarketFitnessIntegrator + FitnessOrchestrator end-to-end."""

    def test_orchestrator_scores_live_enriched_context(self):
        integrator   = MarketFitnessIntegrator(registry=_reg())
        orchestrator = FitnessOrchestrator()
        ctx = {
            "epoch_id": "epoch-live-01",
            "correctness_score": 0.82,
            "efficiency_score": 0.75,
            "policy_compliance_score": 0.88,
            "goal_alignment_score": 0.70,
        }
        enriched = integrator.enrich(ctx)
        result = orchestrator.score(enriched)
        assert 0.0 <= result.total_score <= 1.0
        assert result.breakdown["simulated_market_score"] > 0.0

    def test_score_increases_with_higher_market_signal(self):
        orch = FitnessOrchestrator()
        base_ctx = {
            "correctness_score": 0.80,
            "efficiency_score": 0.75,
            "policy_compliance_score": 0.85,
            "goal_alignment_score": 0.70,
        }
        hi_int = MarketFitnessIntegrator(registry=_reg(dau=0.95))
        lo_int = MarketFitnessIntegrator(registry=_reg(dau=0.10))

        hi_ctx = hi_int.enrich({**base_ctx, "epoch_id": "epoch-hi-mkt"})
        lo_ctx = lo_int.enrich({**base_ctx, "epoch_id": "epoch-lo-mkt"})

        hi_result = orch.score(hi_ctx)
        lo_result = orch.score(lo_ctx)
        assert hi_result.total_score > lo_result.total_score

    def test_lineage_digest_in_enriched_context_matches_adapter(self):
        reg = FeedRegistry()
        reg.register(DemandSignalAdapter().with_source(
            lambda: {"dau": 0.7, "wau": 0.8, "retention_d7": 0.6, "confidence": 1.0}))
        integrator = MarketFitnessIntegrator(registry=reg)
        enriched = integrator.enrich({"epoch_id": "epoch-digest-check"})
        assert enriched["market_signal_lineage_digest"].startswith("sha256:")


# ---------------------------------------------------------------------------
# Compatibility coverage from legacy root-level market integrator tests
# ---------------------------------------------------------------------------

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import pytest


pytestmark = pytest.mark.regression_standard

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


class _FakeRegistryCompat:
    def __init__(self, reading: Optional[_FakeReading] = None) -> None:
        self._reading = reading

    def composite_reading(self) -> Optional[_FakeReading]:
        return self._reading


class _FakeOrchestratorCompat:
    def __init__(self) -> None:
        self.injected: List[Dict[str, Any]] = []

    def inject_live_signal(self, payload: Dict[str, Any]) -> None:
        self.injected.append(payload)


class TestMarketFitnessIntegratorBridgingCompat:
    def test_integrate_live_reading_produces_expected_score(self) -> None:
        reading = _FakeReading(value=0.8, confidence=0.9)
        orchestrator = _FakeOrchestratorCompat()
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistryCompat(reading),
            fitness_orchestrator=orchestrator,
        )
        result = integrator.integrate(epoch_id="epoch-1")
        assert result.live_market_score == round(0.8 * 0.9, 6)
        assert result.confidence == 0.9
        assert result.is_synthetic is False

    def test_integrate_none_registry_returns_synthetic_fallback(self) -> None:
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistryCompat(None),
            fitness_orchestrator=_FakeOrchestratorCompat(),
        )
        result = integrator.integrate(epoch_id="epoch-synthetic")
        assert result.live_market_score == 0.5
        assert result.confidence == 0.0
        assert result.is_synthetic is True
        assert result.adapter_id == "synthetic_fallback"

    def test_integrate_inject_called_with_epoch_id(self) -> None:
        orchestrator = _FakeOrchestratorCompat()
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistryCompat(_FakeReading()),
            fitness_orchestrator=orchestrator,
        )
        integrator.integrate(epoch_id="epoch-injection-check")
        assert len(orchestrator.injected) == 1
        assert orchestrator.injected[0]["epoch_id"] == "epoch-injection-check"

    def test_integrate_clamps_scores_above_one(self) -> None:
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistryCompat(_FakeReading(value=2.0, confidence=1.0)),
            fitness_orchestrator=_FakeOrchestratorCompat(),
        )
        result = integrator.integrate(epoch_id="epoch-clamp")
        assert result.live_market_score <= 1.0

    def test_integrate_emits_market_fitness_integrated_event(self) -> None:
        journal_calls: list[tuple[str, dict]] = []
        integrator = MarketFitnessIntegrator(
            feed_registry=_FakeRegistryCompat(_FakeReading()),
            fitness_orchestrator=_FakeOrchestratorCompat(),
            journal_fn=lambda ev, payload: journal_calls.append((ev, payload)),
        )
        integrator.integrate(epoch_id="epoch-journal")
        assert len(journal_calls) == 1
        ev_type, payload = journal_calls[0]
        assert ev_type == "market_fitness_integrated.v1"
        assert payload["epoch_id"] == "epoch-journal"
        assert "live_market_score" in payload
        assert "lineage_digest" in payload


class TestFitnessOrchestratorLiveOverrideCompat:
    def _base_context(self, epoch_id: str) -> dict:
        return {
            "epoch_id": epoch_id,
            "correctness_score": 0.8,
            "efficiency_score": 0.7,
            "policy_compliance_score": 0.9,
            "goal_alignment_score": 0.75,
            "simulated_market_score": 0.1,
            "regime": "economic_full",
        }

    def test_live_signal_override_updates_market_breakdown(self) -> None:
        orch = FitnessOrchestrator()
        orch.inject_live_signal({"epoch_id": "epoch-live", "live_market_score": 0.95})
        result = orch.score(self._base_context("epoch-live"))
        assert result.breakdown["simulated_market_score"] == 0.95

    def test_no_override_keeps_context_market_score(self) -> None:
        orch = FitnessOrchestrator()
        result = orch.score(self._base_context("epoch-no-override"))
        assert result.breakdown["simulated_market_score"] == 0.1

    def test_inject_live_signal_bad_epoch_id_silently_dropped(self) -> None:
        orch = FitnessOrchestrator()
        orch.inject_live_signal({"epoch_id": "", "live_market_score": 0.9})
        orch.inject_live_signal({})

    def test_live_override_score_clamped_to_unit_interval(self) -> None:
        orch = FitnessOrchestrator()
        orch.inject_live_signal({"epoch_id": "epoch-clamp2", "live_market_score": 99.0})
        result = orch.score(self._base_context("epoch-clamp2"))
        assert result.breakdown["simulated_market_score"] <= 1.0
        assert result.total_score <= 1.0

    def test_live_override_is_advisory_total_score_bounded(self) -> None:
        orch = FitnessOrchestrator()
        orch.inject_live_signal({"epoch_id": "epoch-bound", "live_market_score": 1.0})
        result = orch.score(self._base_context("epoch-bound"))
        assert 0.0 <= result.total_score <= 1.0
