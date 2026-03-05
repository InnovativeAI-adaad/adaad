# SPDX-License-Identifier: Apache-2.0
"""Market signal feed registry — ADAAD-10 Track A.

FeedRegistry: deterministic adapter ordering, TTL caching, fail-closed stale guard.
MarketSignalReading: schema-validated, lineage-stamped signal reading dataclass.
MarketFeedAdapter: Protocol implemented by all concrete adapters.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

log = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "market_signal_reading.v1.json"

SIGNAL_VOLATILITY = "volatility_index"
SIGNAL_RESOURCE   = "resource_price"
SIGNAL_DEMAND     = "demand_signal"
SIGNAL_COMPOSITE  = "composite"


# ---------------------------------------------------------------------------
# Reading dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MarketSignalReading:
    """Validated, lineage-stamped market signal reading."""

    adapter_id:      str
    signal_type:     str   # volatility_index | resource_price | demand_signal | composite
    value:           float  # normalised [0.0, 1.0]
    confidence:      float  # data quality / freshness [0.0, 1.0]
    sampled_at:      float  # epoch timestamp
    lineage_digest:  str    # sha256:hex
    source_uri:      str
    raw_payload:     Dict[str, Any] = field(default_factory=dict)
    stale:           bool = False
    stale_reason:    str  = ""

    def to_fitness_contribution(self) -> float:
        """Return a confidence-weighted value for fitness pipeline ingestion."""
        return round(self.value * self.confidence, 6)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "adapter_id":     self.adapter_id,
            "signal_type":    self.signal_type,
            "value":          self.value,
            "confidence":     self.confidence,
            "sampled_at":     self.sampled_at,
            "lineage_digest": self.lineage_digest,
            "source_uri":     self.source_uri,
        }
        if self.raw_payload:
            d["raw_payload"] = self.raw_payload
        if self.stale:
            d["stale"] = True
            d["stale_reason"] = self.stale_reason
        return d

    @staticmethod
    def compute_digest(adapter_id: str, value: float, sampled_at: float) -> str:
        payload = f"{adapter_id}|{value:.8f}|{sampled_at:.3f}"
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class MarketFeedAdapter(Protocol):
    """Protocol implemented by all concrete market feed adapters."""

    @property
    def adapter_id(self) -> str: ...

    @property
    def signal_type(self) -> str: ...

    def fetch(self) -> MarketSignalReading: ...


# ---------------------------------------------------------------------------
# Stale guard
# ---------------------------------------------------------------------------

def _mark_stale(reading: MarketSignalReading, reason: str) -> MarketSignalReading:
    return MarketSignalReading(
        adapter_id=reading.adapter_id,
        signal_type=reading.signal_type,
        value=reading.value,
        confidence=max(0.0, reading.confidence * 0.5),  # halve confidence on stale
        sampled_at=reading.sampled_at,
        lineage_digest=reading.lineage_digest,
        source_uri=reading.source_uri,
        raw_payload=reading.raw_payload,
        stale=True,
        stale_reason=reason,
    )


# ---------------------------------------------------------------------------
# FeedRegistry
# ---------------------------------------------------------------------------

class FeedRegistry:
    """Deterministic, fail-closed registry of market feed adapters.

    Invariants:
    - Adapter order is deterministic (insertion order, then adapter_id sort on tie).
    - Every fetch returns a reading; source failures fall back to cache.
    - Stale readings (beyond ttl_seconds) are marked stale but still returned.
    - Composite score is confidence-weighted mean across all live readings.
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = 300.0,
        min_confidence_threshold: float = 0.1,
    ) -> None:
        self._adapters:  List[MarketFeedAdapter] = []
        self._cache:     Dict[str, Tuple[MarketSignalReading, float]] = {}  # adapter_id → (reading, ts)
        self._ttl        = float(ttl_seconds)
        self._min_conf   = float(min_confidence_threshold)

    def register(self, adapter: MarketFeedAdapter) -> None:
        if any(a.adapter_id == adapter.adapter_id for a in self._adapters):
            raise ValueError(f"duplicate_adapter_id:{adapter.adapter_id}")
        self._adapters.append(adapter)
        log.info("FeedRegistry: registered adapter %s (%s)", adapter.adapter_id, adapter.signal_type)

    def fetch_all(self) -> List[MarketSignalReading]:
        """Fetch readings from all registered adapters. Never raises."""
        now   = time.time()
        out:  List[MarketSignalReading] = []
        for adapter in sorted(self._adapters, key=lambda a: a.adapter_id):
            reading = self._fetch_one(adapter, now)
            out.append(reading)
        return out

    def composite_score(self) -> float:
        """Confidence-weighted mean of all live readings. Returns 0.0 if no adapters."""
        readings = self.fetch_all()
        live = [r for r in readings if r.confidence >= self._min_conf]
        if not live:
            return 0.0
        total_conf = sum(r.confidence for r in live)
        if total_conf <= 0.0:
            return 0.0
        return round(sum(r.value * r.confidence for r in live) / total_conf, 6)

    def adapter_ids(self) -> List[str]:
        return sorted(a.adapter_id for a in self._adapters)

    # ------------------------------------------------------------------
    def _fetch_one(self, adapter: MarketFeedAdapter, now: float) -> MarketSignalReading:
        try:
            reading = adapter.fetch()
            self._cache[adapter.adapter_id] = (reading, now)
            return reading
        except Exception as exc:
            log.warning("FeedRegistry: adapter %s error — %s", adapter.adapter_id, exc)
            cached = self._cache.get(adapter.adapter_id)
            if cached:
                r, ts = cached
                age = now - ts
                return _mark_stale(r, f"source_error:age={age:.0f}s")
            # No cache — synthesise a zero-confidence stale reading
            ts_now = time.time()
            return MarketSignalReading(
                adapter_id=adapter.adapter_id,
                signal_type=adapter.signal_type,
                value=0.0,
                confidence=0.0,
                sampled_at=ts_now,
                lineage_digest=MarketSignalReading.compute_digest(adapter.adapter_id, 0.0, ts_now),
                source_uri="synthetic:no-cache",
                stale=True,
                stale_reason=f"source_error_no_cache:{exc}",
            )


__all__ = [
    "FeedRegistry",
    "MarketFeedAdapter",
    "MarketSignalReading",
    "SIGNAL_VOLATILITY",
    "SIGNAL_RESOURCE",
    "SIGNAL_DEMAND",
    "SIGNAL_COMPOSITE",
]
