# SPDX-License-Identifier: Apache-2.0
"""MarketFitnessIntegrator — ADAAD-10 PR-10-02.

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
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_EVENT_TYPE    = "market_fitness_signal_enriched.v1"
_FALLBACK_SCORE = 0.50


@dataclass(frozen=True)
class MarketEnrichmentRecord:
    composite_score: float
    signal_source:   str
    lineage_digest:  str
    enriched_at:     float
    adapter_count:   int


class MarketFitnessIntegrator:
    """Enriches a fitness scoring context with live market signal."""

    def __init__(self, *, registry: Any, journal_fn: Any = None,
                 fallback_score: float = _FALLBACK_SCORE) -> None:
        self._registry   = registry
        self._journal_fn = journal_fn
        self._fallback   = fallback_score
        self._last_record: Optional[MarketEnrichmentRecord] = None

    def enrich(self, context: Dict[str, Any]) -> Dict[str, Any]:
        score, digest, source, n = self._fetch_signal()
        enriched = dict(context)
        enriched["simulated_market_score"]       = score
        enriched["market_signal_lineage_digest"] = digest
        enriched["market_signal_source"]         = source
        enriched["market_signal_enriched_at"]    = time.time()
        record = MarketEnrichmentRecord(score, source, digest, time.time(), n)
        self._last_record = record
        self._emit_journal(record, str(context.get("epoch_id", "unknown")))
        return enriched

    @property
    def last_enrichment(self) -> Optional[MarketEnrichmentRecord]:
        return self._last_record

    def _fetch_signal(self):
        try:
            readings  = self._registry.fetch_all()
            n         = len(readings)
            live      = [r for r in readings if r.confidence > 0.0]
            if not live:
                return self._fallback, "sha256:" + "0" * 64, "synthetic", n
            total_conf = sum(r.confidence for r in live)
            score  = sum(r.value * r.confidence for r in live) / total_conf
            score  = round(max(0.0, min(1.0, score)), 6)
            best   = max(live, key=lambda r: r.confidence)
            source = "cached" if best.stale else "live"
            return score, best.lineage_digest, source, n
        except Exception as exc:
            log.warning("MarketFitnessIntegrator: fallback — %s", exc)
            return self._fallback, "sha256:" + "0" * 64, "synthetic", 0

    def _emit_journal(self, record: MarketEnrichmentRecord, epoch_id: str) -> None:
        if self._journal_fn is None:
            try:
                from security.ledger.journal import log as _jlog
                self._journal_fn = _jlog
            except Exception:
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
            log.warning("MarketFitnessIntegrator: journal — %s", exc)

__all__ = ["MarketFitnessIntegrator", "MarketEnrichmentRecord"]
