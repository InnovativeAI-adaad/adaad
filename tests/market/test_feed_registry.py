# SPDX-License-Identifier: Apache-2.0
"""Tests for FeedRegistry and concrete market adapters — ADAAD-10 PR-10-01."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from runtime.market.feed_registry import FeedRegistry, MarketSignalReading, SIGNAL_DEMAND, SIGNAL_RESOURCE, SIGNAL_VOLATILITY
from runtime.market.adapters.live_adapters import VolatilityIndexAdapter, ResourcePriceAdapter, DemandSignalAdapter

SCHEMA_PATH = Path("schemas/market_signal_reading.v1.json")


class TestMarketSignalReading:
    def test_lineage_digest_format(self):
        r = MarketSignalReading(
            adapter_id="test", signal_type=SIGNAL_DEMAND, value=0.6,
            confidence=0.8, sampled_at=1000.0,
            lineage_digest=MarketSignalReading.compute_digest("test", 0.6, 1000.0),
            source_uri="test://")
        assert r.lineage_digest.startswith("sha256:")

    def test_fitness_contribution_is_confidence_weighted(self):
        r = MarketSignalReading(
            adapter_id="test", signal_type=SIGNAL_DEMAND, value=0.8,
            confidence=0.5, sampled_at=1000.0,
            lineage_digest=MarketSignalReading.compute_digest("test", 0.8, 1000.0),
            source_uri="test://")
        assert abs(r.to_fitness_contribution() - 0.4) < 1e-6

    def test_schema_file_exists_and_valid_json(self):
        assert SCHEMA_PATH.exists()
        schema = json.loads(SCHEMA_PATH.read_text())
        assert "required" in schema
        assert "signal_type" in schema["properties"]


class TestFeedRegistry:
    def test_register_and_composite_score(self):
        reg = FeedRegistry()
        reg.register(VolatilityIndexAdapter())
        reg.register(DemandSignalAdapter())
        score = reg.composite_score()
        assert 0.0 <= score <= 1.0

    def test_duplicate_adapter_id_raises(self):
        reg = FeedRegistry()
        reg.register(VolatilityIndexAdapter())
        with pytest.raises(ValueError, match="duplicate_adapter_id"):
            reg.register(VolatilityIndexAdapter())

    def test_fetch_all_returns_one_per_adapter(self):
        reg = FeedRegistry()
        reg.register(VolatilityIndexAdapter())
        reg.register(ResourcePriceAdapter())
        reg.register(DemandSignalAdapter())
        readings = reg.fetch_all()
        assert len(readings) == 3

    def test_adapter_failure_returns_zero_confidence(self):
        reg = FeedRegistry()
        bad = VolatilityIndexAdapter()
        bad._source_fn = lambda: (_ for _ in ()).throw(RuntimeError("upstream_down"))
        reg.register(bad)
        readings = reg.fetch_all()
        # adapter has no cache: fallback yields zero confidence
        assert readings[0].confidence == 0.0

    def test_composite_score_zero_with_no_adapters(self):
        reg = FeedRegistry()
        assert reg.composite_score() == 0.0

    def test_ordering_deterministic(self):
        for _ in range(5):
            reg = FeedRegistry()
            reg.register(DemandSignalAdapter())
            reg.register(VolatilityIndexAdapter())
            reg.register(ResourcePriceAdapter())
            ids = [r.adapter_id for r in reg.fetch_all()]
            assert ids == sorted(ids)


class TestVolatilityIndexAdapter:
    def test_high_volatility_yields_low_value(self):
        a = VolatilityIndexAdapter().with_source(lambda: {"volatility": 0.9, "confidence": 1.0})
        r = a.fetch()
        assert r.value < 0.2

    def test_low_volatility_yields_high_value(self):
        a = VolatilityIndexAdapter().with_source(lambda: {"volatility": 0.05, "confidence": 1.0})
        r = a.fetch()
        assert r.value > 0.9

    def test_signal_type_is_volatility(self):
        assert VolatilityIndexAdapter().fetch().signal_type == SIGNAL_VOLATILITY


class TestResourcePriceAdapter:
    def test_price_at_ceiling_yields_zero(self):
        a = ResourcePriceAdapter(budget_ceiling_usd=10.0).with_source(
            lambda: {"price_usd_per_hour": 10.0, "budget_ceiling_usd": 10.0})
        r = a.fetch()
        assert r.value == 0.0

    def test_price_zero_yields_one(self):
        a = ResourcePriceAdapter(budget_ceiling_usd=10.0).with_source(
            lambda: {"price_usd_per_hour": 0.0, "budget_ceiling_usd": 10.0})
        r = a.fetch()
        assert r.value == 1.0

    def test_signal_type_is_resource(self):
        assert ResourcePriceAdapter().fetch().signal_type == SIGNAL_RESOURCE


class TestDemandSignalAdapter:
    def test_high_dau_retention_yields_high_value(self):
        a = DemandSignalAdapter().with_source(
            lambda: {"dau": 0.9, "wau": 0.95, "retention_d7": 0.85, "confidence": 1.0})
        r = a.fetch()
        assert r.value > 0.75

    def test_low_dau_yields_low_value(self):
        a = DemandSignalAdapter().with_source(
            lambda: {"dau": 0.05, "wau": 0.10, "retention_d7": 0.05, "confidence": 1.0})
        r = a.fetch()
        assert r.value < 0.25

    def test_signal_type_is_demand(self):
        assert DemandSignalAdapter().fetch().signal_type == SIGNAL_DEMAND

    def test_lineage_digest_starts_sha256(self):
        r = DemandSignalAdapter().fetch()
        assert r.lineage_digest.startswith("sha256:")
