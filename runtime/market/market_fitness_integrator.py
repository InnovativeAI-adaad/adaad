# SPDX-License-Identifier: Apache-2.0
"""MarketFitnessIntegrator -- ADAAD-10 PR-10-02.

Bridges the FeedRegistry composite score into FitnessOrchestrator's
simulated_market_score component, replacing the static synthetic constant
with a live, confidence-weighted signal.

Invariants:
  - Never raises; on error injects cached/synthetic fallback.
  - Signal lineage digest propagated into fitness context for auditability.
  - Only place that writes simulated_market_score into the fitness context.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from runtime.governance.foundation import default_provider

log = logging.getLogger(__name__)

_EVENT_TYPE      = "market_fitness_signal_enriched.v1"
_INTEGRATE_EVENT = "market_fitness_integrated.v1"
_FALLBACK_SCORE  = 0.50


@dataclass(frozen=True)
class MarketEnrichmentRecord:
    composite_score: float
    signal_source:   str
    lineage_digest:  str
    enriched_at:     float
    adapter_count:   int


@dataclass(frozen=True)
class IntegrationResult:
    """Result returned by MarketFitnessIntegrator.integrate()."""
    epoch_id:                    str
    live_market_score:           float
    confidence:                  float
    is_synthetic:                bool
    adapter_id:                  str
    lineage_digest:              str
    signal_source:               str
    # Phase 13 / Track 11-B: consecutive synthetic epoch counter (PR-13-B-01).
    # Reflects the running count *including* this epoch.  Reset to 0 on any
    # non-synthetic reading.  Used by market_signal_integrity_invariant.
    consecutive_synthetic_epochs: int = 0


class MarketFitnessIntegrator:
    """Enriches a fitness scoring context with live market signal."""

    def __init__(self, *, registry: Any = None, feed_registry: Any = None,
                 fitness_orchestrator: Any = None, journal_fn: Any = None,
                 fallback_score: float = _FALLBACK_SCORE,
                 now_fn: Callable[[], float] | None = None) -> None:
        self._feed_registry        = feed_registry or registry
        self._fitness_orchestrator = fitness_orchestrator
        self._journal_fn           = journal_fn
        self._fallback             = fallback_score
        self._now_fn               = now_fn or _default_now_fn
        self._last_record: Optional[MarketEnrichmentRecord] = None
        # Phase 13 / Track 11-B: running synthetic epoch counter (PR-13-B-01)
        self._consecutive_synthetic: int = 0

    # ------------------------------------------------------------------
    # Primary API: integrate() -- used by PR-10-02 tests + EvolutionLoop
    # ------------------------------------------------------------------

    def integrate(self, *, epoch_id: str) -> IntegrationResult:
        """Bridge composite registry reading into FitnessOrchestrator.

        Reads composite_reading() from feed_registry, computes
        confidence-weighted score, injects it into the orchestrator,
        and emits journal event. Never raises.
        """
        try:
            result = self._do_integrate(epoch_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("MarketFitnessIntegrator.integrate: fallback -- %s", exc)
            result = IntegrationResult(
                epoch_id=epoch_id,
                live_market_score=self._fallback,
                confidence=0.0,
                is_synthetic=True,
                adapter_id="synthetic_fallback",
                lineage_digest="sha256:" + "0" * 64,
                signal_source="synthetic",
            )

        # Phase 13 / Track 11-B: update consecutive synthetic counter
        if result.is_synthetic:
            self._consecutive_synthetic += 1
        else:
            self._consecutive_synthetic = 0
        # Rebuild result with the updated counter (frozen dataclass — new instance)
        result = IntegrationResult(
            epoch_id=result.epoch_id,
            live_market_score=result.live_market_score,
            confidence=result.confidence,
            is_synthetic=result.is_synthetic,
            adapter_id=result.adapter_id,
            lineage_digest=result.lineage_digest,
            signal_source=result.signal_source,
            consecutive_synthetic_epochs=self._consecutive_synthetic,
        )

        if self._fitness_orchestrator is not None:
            try:
                self._fitness_orchestrator.inject_live_signal({
                    "epoch_id":          result.epoch_id,
                    "live_market_score": result.live_market_score,
                    "lineage_digest":    result.lineage_digest,
                    "confidence":        result.confidence,
                    "is_synthetic":      result.is_synthetic,
                })
            except Exception as exc:  # noqa: BLE001
                log.warning("MarketFitnessIntegrator: orchestrator inject -- %s", exc)

        self._emit_integrate_journal(result)
        return result

    def _do_integrate(self, epoch_id: str) -> IntegrationResult:
        registry = self._feed_registry
        if registry is None:
            return self._synthetic(epoch_id)

        reading = registry.composite_reading()
        if reading is None:
            return self._synthetic(epoch_id)

        raw_score  = float(reading.to_fitness_contribution())
        clamped    = max(0.0, min(1.0, raw_score))
        confidence = float(getattr(reading, "confidence", 1.0))
        is_stale   = bool(getattr(reading, "stale", False))
        adapter_id = str(getattr(reading, "adapter_id", "unknown"))
        lineage    = str(getattr(reading, "lineage_digest", "sha256:" + "0" * 64))
        source     = "cached" if is_stale else "live"

        return IntegrationResult(
            epoch_id=epoch_id,
            live_market_score=clamped,
            confidence=confidence,
            is_synthetic=False,
            adapter_id=adapter_id,
            lineage_digest=lineage,
            signal_source=source,
        )

    def _synthetic(self, epoch_id: str) -> IntegrationResult:
        return IntegrationResult(
            epoch_id=epoch_id,
            live_market_score=self._fallback,
            confidence=0.0,
            is_synthetic=True,
            adapter_id="synthetic_fallback",
            lineage_digest="sha256:" + "0" * 64,
            signal_source="synthetic",
        )

    # ------------------------------------------------------------------
    # Legacy API: enrich() -- context dict mutation pattern
    # ------------------------------------------------------------------

    def enrich(self, context: Dict[str, Any]) -> Dict[str, Any]:
        score, digest, source, n = self._fetch_signal()
        now = self._now_fn()
        enriched = dict(context)
        enriched["simulated_market_score"]       = score
        enriched["market_signal_lineage_digest"] = digest
        enriched["market_signal_source"]         = source
        enriched["market_signal_enriched_at"]    = now
        record = MarketEnrichmentRecord(score, source, digest, now, n)
        self._last_record = record
        self._emit_journal(record, str(context.get("epoch_id", "unknown")))
        return enriched

    @property
    def consecutive_synthetic_epochs(self) -> int:
        """Return the current consecutive-synthetic-epoch count (Phase 13 / Track 11-B)."""
        return self._consecutive_synthetic

    def reset_synthetic_counter(self) -> None:
        """Reset the consecutive synthetic counter (e.g. after operator acknowledgement)."""
        self._consecutive_synthetic = 0

    @property
    def last_enrichment(self) -> Optional[MarketEnrichmentRecord]:
        return self._last_record

    def _fetch_signal(self):
        try:
            registry  = self._feed_registry
            readings  = registry.fetch_all()
            n         = len(readings)
            live      = [r for r in readings if r.confidence > 0.0]
            if not live:
                return self._fallback, "sha256:" + "0" * 64, "synthetic", n
            total_conf = sum(r.confidence for r in live)
            score      = sum(r.value * r.confidence for r in live) / total_conf
            score      = round(max(0.0, min(1.0, score)), 6)
            best       = max(live, key=lambda r: r.confidence)
            source     = "cached" if best.stale else "live"
            return score, best.lineage_digest, source, n
        except Exception as exc:
            log.warning("MarketFitnessIntegrator: enrich fallback -- %s", exc)
            return self._fallback, "sha256:" + "0" * 64, "synthetic", 0

    def _emit_journal(self, record: MarketEnrichmentRecord, epoch_id: str) -> None:
        if self._journal_fn is None:
            return
        try:
            self._journal_fn(tx_type=_EVENT_TYPE, payload={
                "event_type": _EVENT_TYPE, "epoch_id": epoch_id,
                "composite_score": record.composite_score,
                "signal_source": record.signal_source,
                "lineage_digest": record.lineage_digest,
                "adapter_count": record.adapter_count,
            })
        except Exception as exc:
            log.warning("MarketFitnessIntegrator: journal -- %s", exc)

    def _emit_integrate_journal(self, result: IntegrationResult) -> None:
        if self._journal_fn is None:
            return
        try:
            self._journal_fn(_INTEGRATE_EVENT, {
                "epoch_id":                       result.epoch_id,
                "live_market_score":              result.live_market_score,
                "confidence":                     result.confidence,
                "is_synthetic":                   result.is_synthetic,
                "lineage_digest":                 result.lineage_digest,
                "signal_source":                  result.signal_source,
                "consecutive_synthetic_epochs":   result.consecutive_synthetic_epochs,
            })
        except Exception as exc:  # noqa: BLE001
            log.warning("MarketFitnessIntegrator: integrate journal -- %s", exc)


def _default_now_fn() -> float:
    """Resolve epoch timestamp from runtime provider when available."""
    try:
        return default_provider().now_utc().timestamp()
    except Exception:  # noqa: BLE001
        return time.time()


__all__ = ["MarketFitnessIntegrator", "MarketEnrichmentRecord", "IntegrationResult"]
