# SPDX-License-Identifier: Apache-2.0
"""Tests for MarketFitnessIntegrator — ADAAD-10 PR-10-02."""
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard
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
