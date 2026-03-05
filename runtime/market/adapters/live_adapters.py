# SPDX-License-Identifier: Apache-2.0
"""Concrete market feed adapters — ADAAD-10 Track A.

Three production adapters + one synthetic baseline for CI/offline:

  VolatilityIndexAdapter  — market stress / entropy pressure signal
  ResourcePriceAdapter    — compute cost signal (normalised against budget ceiling)
  DemandSignalAdapter     — DAU/WAU user demand signal

All adapters implement the MarketFeedAdapter protocol and are fail-closed:
source errors fall back to last cached reading, then to a zero-confidence
synthetic reading. They never raise to callers.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from runtime.market.feed_registry import (
    MarketSignalReading,
    SIGNAL_DEMAND,
    SIGNAL_RESOURCE,
    SIGNAL_VOLATILITY,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _digest(adapter_id: str, value: float, ts: float) -> str:
    return MarketSignalReading.compute_digest(adapter_id, value, ts)


def _reading(
    adapter_id: str,
    signal_type: str,
    value: float,
    confidence: float,
    source_uri: str,
    raw: Dict[str, Any],
) -> MarketSignalReading:
    ts = time.time()
    return MarketSignalReading(
        adapter_id=adapter_id,
        signal_type=signal_type,
        value=_clamp(value),
        confidence=_clamp(confidence),
        sampled_at=ts,
        lineage_digest=_digest(adapter_id, _clamp(value), ts),
        source_uri=source_uri,
        raw_payload=raw,
    )


# ---------------------------------------------------------------------------
# VolatilityIndexAdapter
# ---------------------------------------------------------------------------

@dataclass
class VolatilityIndexAdapter:
    """Market stress signal: high volatility → lower fitness incentive for risky mutations.

    Source function returns: {"volatility": float [0,1], "confidence": float [0,1]}
    Inverted: high external volatility → low value (system should be conservative).
    """

    adapter_id: str = "volatility_index"
    signal_type: str = SIGNAL_VOLATILITY
    source_uri: str = "internal:synthetic"
    _source_fn: Optional[Callable[[], Dict[str, Any]]] = field(default=None, repr=False)
    _cache: Optional[MarketSignalReading] = field(default=None, init=False, repr=False)

    def with_source(self, fn: Callable[[], Dict[str, Any]]) -> "VolatilityIndexAdapter":
        self._source_fn = fn
        return self

    def fetch(self) -> MarketSignalReading:
        try:
            raw = self._source_fn() if self._source_fn else {"volatility": 0.35, "confidence": 0.6}
            vol  = _clamp(float(raw.get("volatility", 0.35)))
            conf = _clamp(float(raw.get("confidence", 0.6)))
            # Invert: high volatility = low value (pressure to stay conservative)
            value = round(1.0 - vol, 6)
            r = _reading(self.adapter_id, self.signal_type, value, conf, self.source_uri, raw)
            self._cache = r
            return r
        except Exception as exc:
            log.warning("VolatilityIndexAdapter: source error — %s", exc)
            if self._cache:
                return self._cache
            return _reading(self.adapter_id, self.signal_type, 0.5, 0.0, "synthetic:fallback", {})


# ---------------------------------------------------------------------------
# ResourcePriceAdapter
# ---------------------------------------------------------------------------

@dataclass
class ResourcePriceAdapter:
    """Compute cost signal: high price → lower available fitness budget.

    Source returns: {"price_usd_per_hour": float, "budget_ceiling_usd": float}
    Normalised to [0,1] as 1 - (price / ceiling), clamped.
    """

    adapter_id: str = "resource_price"
    signal_type: str = SIGNAL_RESOURCE
    source_uri: str = "internal:synthetic"
    budget_ceiling_usd: float = 10.0   # operator-configured ceiling
    _source_fn: Optional[Callable[[], Dict[str, Any]]] = field(default=None, repr=False)
    _cache: Optional[MarketSignalReading] = field(default=None, init=False, repr=False)

    def with_source(self, fn: Callable[[], Dict[str, Any]]) -> "ResourcePriceAdapter":
        self._source_fn = fn
        return self

    def fetch(self) -> MarketSignalReading:
        try:
            raw = self._source_fn() if self._source_fn else {
                "price_usd_per_hour": 1.50, "budget_ceiling_usd": self.budget_ceiling_usd
            }
            price   = float(raw.get("price_usd_per_hour", 1.50))
            ceiling = float(raw.get("budget_ceiling_usd", self.budget_ceiling_usd))
            value   = _clamp(1.0 - (price / max(ceiling, 0.001)))
            conf    = _clamp(float(raw.get("confidence", 0.75)))
            r = _reading(self.adapter_id, self.signal_type, value, conf, self.source_uri, raw)
            self._cache = r
            return r
        except Exception as exc:
            log.warning("ResourcePriceAdapter: source error — %s", exc)
            if self._cache:
                return self._cache
            return _reading(self.adapter_id, self.signal_type, 0.5, 0.0, "synthetic:fallback", {})


# ---------------------------------------------------------------------------
# DemandSignalAdapter
# ---------------------------------------------------------------------------

@dataclass
class DemandSignalAdapter:
    """User demand signal: DAU/WAU ratio → selection pressure for growth.

    Source returns: {"dau": float [0,1], "wau": float [0,1], "retention_d7": float [0,1]}
    Composite: (dau * 0.45 + retention_d7 * 0.35 + (dau/wau clamp) * 0.20)
    """

    adapter_id: str = "demand_signal"
    signal_type: str = SIGNAL_DEMAND
    source_uri: str = "internal:synthetic"
    _source_fn: Optional[Callable[[], Dict[str, Any]]] = field(default=None, repr=False)
    _cache: Optional[MarketSignalReading] = field(default=None, init=False, repr=False)

    def with_source(self, fn: Callable[[], Dict[str, Any]]) -> "DemandSignalAdapter":
        self._source_fn = fn
        return self

    def fetch(self) -> MarketSignalReading:
        try:
            raw = self._source_fn() if self._source_fn else {
                "dau": 0.55, "wau": 0.70, "retention_d7": 0.42
            }
            dau   = _clamp(float(raw.get("dau", 0.55)))
            wau   = _clamp(float(raw.get("wau", 0.70)))
            r7    = _clamp(float(raw.get("retention_d7", 0.42)))
            ratio = _clamp(dau / max(wau, 0.001))
            value = round(dau * 0.45 + r7 * 0.35 + ratio * 0.20, 6)
            conf  = _clamp(float(raw.get("confidence", 0.80)))
            reading = _reading(self.adapter_id, self.signal_type, value, conf, self.source_uri, raw)
            self._cache = reading
            return reading
        except Exception as exc:
            log.warning("DemandSignalAdapter: source error — %s", exc)
            if self._cache:
                return self._cache
            return _reading(self.adapter_id, self.signal_type, 0.5, 0.0, "synthetic:fallback", {})


__all__ = ["VolatilityIndexAdapter", "ResourcePriceAdapter", "DemandSignalAdapter"]
