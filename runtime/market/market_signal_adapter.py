# SPDX-License-Identifier: Apache-2.0
"""
MarketSignalAdapter: governed external market signal ingestion.

This is the highest-ROI module in the ADAAD codebase (I-06 from Master PR Codex).
When real DAU and retention_d7 signals flow through this adapter into the fitness
pipeline, the following capabilities activate simultaneously:
  - Budget mode switching on real external selection pressure
  - ROI attribution against live signals instead of synthetic constants
  - Darwinian agent selection driven by market outcomes
  - Earned autonomy progression tied to real retention metrics

Architecture:
  - Fail-closed by design: source failures fall back to last cached signal,
    never to 0.0. A cached signal is far more accurate than a zero.
  - Signal schema validated before emission. Malformed payloads are quarantined.
  - Every emitted signal carries a lineage_digest for audit traceability.
  - Synthetic baseline mode is active when no source_fn is provided, ensuring
    CI, Pydroid3, and offline environments always have a valid signal.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


# -- Signal types -------------------------------------------------------------


@dataclass(frozen=True)
class MarketSignal:
    """Validated, lineage-stamped market signal for fitness pipeline ingestion."""

    dau:                    float   # Daily Active Users, normalized [0.0, 1.0]
    retention_d7:           float   # 7-day retention rate [0.0, 1.0]
    simulated_market_score: float   # Composite fitness signal [0.0, 1.0]
    source:                 str     # "live" | "cached" | "synthetic"
    ingested_at:            float   # epoch timestamp
    lineage_digest:         str     # sha256 of signal payload
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_fitness_payload(self) -> Dict[str, Any]:
        """Emit in the shape consumed by FitnessOrchestrator / FitnessPipeline."""
        return {
            "dau":                    self.dau,
            "retention_d7":          self.retention_d7,
            "simulated_market_score": self.simulated_market_score,
            "signal_source":         self.source,
            "signal_lineage_digest": self.lineage_digest,
            "ingested_at":           self.ingested_at,
        }


class MarketSignalValidator:
    """Validates raw signal dicts before the adapter emits them."""

    _REQUIRED_FIELDS = {"dau", "retention_d7"}
    _FLOAT_RANGE     = (0.0, 1.0)

    def validate(self, raw: Dict[str, Any]) -> Tuple[bool, str]:
        missing = self._REQUIRED_FIELDS - raw.keys()
        if missing:
            return False, f"missing_fields:{sorted(missing)}"
        for f in self._REQUIRED_FIELDS:
            val = raw.get(f)
            try:
                fv = float(val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return False, f"{f}_not_numeric:{val!r}"
            lo, hi = self._FLOAT_RANGE
            if not (lo <= fv <= hi):
                return False, f"{f}_out_of_range:{fv}"
        return True, "ok"


# -- Adapter ------------------------------------------------------------------


class MarketSignalAdapter:
    """
    Fetches governed market signals from a configurable source function.

    Usage (live):
        adapter = MarketSignalAdapter(source_fn=lambda: my_analytics_api.fetch())
        signal  = adapter.fetch()
        payload = signal.to_fitness_payload()  # pass to FitnessPipeline

    Usage (CI / Pydroid3):
        adapter = MarketSignalAdapter()   # synthetic baseline, never raises
        signal  = adapter.fetch()

    The adapter always returns a MarketSignal. It never raises.
    """

    _SYNTHETIC_BASELINE: Dict[str, Any] = {
        "dau":          0.50,
        "retention_d7": 0.40,
    }

    def __init__(
        self,
        source_fn: Optional[Callable[[], Dict[str, Any]]] = None,
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        self._source_fn      = source_fn
        self._cache_ttl      = cache_ttl_seconds
        self._validator      = MarketSignalValidator()
        self._cached_signal: Optional[MarketSignal] = None
        self._cache_ts:      float = 0.0
        self._quarantine:    List[Dict[str, Any]] = []

    def fetch(self) -> MarketSignal:
        """Return a validated, lineage-stamped MarketSignal. Never raises."""
        now = time.time()
        if self._cached_signal and (now - self._cache_ts) < self._cache_ttl:
            log.debug("MarketSignalAdapter: cache hit (age=%.1fs)", now - self._cache_ts)
            return self._cached_signal

        try:
            raw = self._call_source()
            ok, reason = self._validator.validate(raw)
            if not ok:
                log.warning("MarketSignalAdapter: quarantining invalid signal — %s", reason)
                self._quarantine.append({"raw": raw, "reason": reason, "ts": now})
                return self._fallback(reason=f"validation_failed:{reason}")

            source = "live" if self._source_fn else "synthetic"
            signal = self._build_signal(raw, source=source)
            self._cached_signal = signal
            self._cache_ts      = now
            log.info(
                "MarketSignalAdapter: ingested dau=%.3f retention_d7=%.3f source=%s digest=%.16s",
                signal.dau, signal.retention_d7, source, signal.lineage_digest,
            )
            return signal

        except Exception as exc:
            log.warning("MarketSignalAdapter: source error, circuit-breaker — %s", exc)
            return self._fallback(reason=f"source_error:{exc}")

    @property
    def quarantine_log(self) -> List[Dict[str, Any]]:
        """Read-only view of quarantined invalid signals for operator review."""
        return list(self._quarantine)

    # -- Internal -------------------------------------------------------------

    def _call_source(self) -> Dict[str, Any]:
        if self._source_fn is not None:
            return dict(self._source_fn())
        return dict(self._SYNTHETIC_BASELINE)

    def _build_signal(self, raw: Dict[str, Any], source: str) -> MarketSignal:
        dau          = float(raw["dau"])
        retention_d7 = float(raw["retention_d7"])
        market_score = round((dau * 0.55) + (retention_d7 * 0.45), 4)
        ts           = time.time()
        digest       = self._lineage_digest(source, dau, retention_d7, ts)
        return MarketSignal(
            dau=dau,
            retention_d7=retention_d7,
            simulated_market_score=market_score,
            source=source,
            ingested_at=ts,
            lineage_digest=digest,
            raw=dict(raw),
        )

    def _fallback(self, reason: str) -> MarketSignal:
        if self._cached_signal is not None:
            log.info("MarketSignalAdapter: circuit-breaker returning cached signal")
            return self._cached_signal
        log.warning(
            "MarketSignalAdapter: no cache available, emitting synthetic baseline (reason=%s)",
            reason,
        )
        return self._build_signal(dict(self._SYNTHETIC_BASELINE), source="synthetic")

    @staticmethod
    def _lineage_digest(source: str, dau: float, retention_d7: float, ts: float) -> str:
        payload = f"{source}|{dau:.6f}|{retention_d7:.6f}|{ts:.3f}"
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


__all__ = ["MarketSignalAdapter", "MarketSignal", "MarketSignalValidator"]
