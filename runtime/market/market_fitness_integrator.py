# SPDX-License-Identifier: Apache-2.0
"""Market Fitness Integrator — ADAAD-10 PR-10-01.

Bridges live ``MarketSignalReading`` objects from the FeedRegistry into
``FitnessOrchestrator.inject_live_signal()`` so the economic regime weight
and live_market_score are driven by real signals instead of the static
``simulated_market_score`` constant.

Architecture
------------
::

    FeedRegistry.composite_reading()
         │  confidence-weighted blend of all registered adapters
         ▼
    MarketFitnessIntegrator.build_live_payload()
         │  normalised fitness contribution, lineage anchoring
         ▼
    FitnessOrchestrator.inject_live_signal(payload)
         │  updates epoch regime-weight override (advisory; GovernanceGate authoritative)
         ▼
    Audit journal: market_fitness_integrated.v1

Invariants
----------
- Integrator is read-only with respect to epoch snapshots; it never mutates
  a frozen snapshot.
- A stale or failed registry reading falls back to synthetic baseline value;
  ``live_market_score`` is never set to 0.0 from a transient source failure.
- Every integration event is journalled with lineage_digest for traceability.
- The GovernanceGate retains final mutation-approval authority regardless of
  what signal value the integrator supplies.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_EVENT_TYPE = "market_fitness_integrated.v1"

# Fallback score used when registry returns no usable reading
_SYNTHETIC_BASELINE = 0.5
_SYNTHETIC_CONFIDENCE = 0.0  # Zero confidence flags it as synthetic


@dataclass(frozen=True)
class IntegrationResult:
    """Result of a single market→fitness integration cycle."""

    live_market_score: float       # normalised [0.0, 1.0] for fitness_orchestrator
    confidence: float              # data freshness/quality [0.0, 1.0]
    lineage_digest: str            # sha256 from the underlying reading
    adapter_id: str                # which adapter dominated the composite
    signal_type: str               # volatility_index | resource_price | demand_signal | composite
    sampled_at: float              # UNIX timestamp of the underlying reading
    injected_at: float             # UNIX timestamp when this integration ran
    is_synthetic: bool             # True iff feed returned no live reading


class MarketFitnessIntegrator:
    """Bridges FeedRegistry live readings into FitnessOrchestrator.

    Parameters
    ----------
    feed_registry:
        A ``FeedRegistry`` instance (or compatible duck-type) exposing
        ``composite_reading() -> Optional[MarketSignalReading]``.
    fitness_orchestrator:
        A ``FitnessOrchestrator`` instance exposing
        ``inject_live_signal(payload: Dict) -> None``.
    journal_fn:
        Optional callable ``(event_type: str, payload: dict) -> None`` for
        audit journalling.  When ``None``, journalling is silently skipped.
    """

    def __init__(
        self,
        *,
        feed_registry: Any,
        fitness_orchestrator: Any,
        journal_fn: Any = None,
    ) -> None:
        self._registry = feed_registry
        self._orchestrator = fitness_orchestrator
        self._journal_fn = journal_fn

    def integrate(self, *, epoch_id: str) -> IntegrationResult:
        """Run one integration cycle for the given epoch.

        Returns an ``IntegrationResult`` describing what was injected.
        Never raises — failures degrade gracefully to synthetic baseline.
        """
        reading = self._safe_composite_reading()
        result = self._build_result(reading)
        self._inject(epoch_id=epoch_id, result=result)
        self._journal(epoch_id=epoch_id, result=result)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_composite_reading(self) -> Optional[Any]:
        try:
            return self._registry.composite_reading()
        except Exception as exc:  # pragma: no cover
            log.warning("MarketFitnessIntegrator: composite_reading() failed — %s", exc)
            return None

    def _build_result(self, reading: Optional[Any]) -> IntegrationResult:
        now = time.time()
        if reading is None:
            return IntegrationResult(
                live_market_score=_SYNTHETIC_BASELINE,
                confidence=_SYNTHETIC_CONFIDENCE,
                lineage_digest="sha256:" + "0" * 64,
                adapter_id="synthetic_fallback",
                signal_type="composite",
                sampled_at=now,
                injected_at=now,
                is_synthetic=True,
            )

        score = float(getattr(reading, "to_fitness_contribution", lambda: reading.value)())
        score = max(0.0, min(1.0, score))

        return IntegrationResult(
            live_market_score=score,
            confidence=float(getattr(reading, "confidence", 1.0)),
            lineage_digest=str(getattr(reading, "lineage_digest", "sha256:" + "0" * 64)),
            adapter_id=str(getattr(reading, "adapter_id", "unknown")),
            signal_type=str(getattr(reading, "signal_type", "composite")),
            sampled_at=float(getattr(reading, "sampled_at", now)),
            injected_at=now,
            is_synthetic=bool(getattr(reading, "stale", False)),
        )

    def _inject(self, *, epoch_id: str, result: IntegrationResult) -> None:
        try:
            self._orchestrator.inject_live_signal({
                "epoch_id": epoch_id,
                "live_market_score": result.live_market_score,
                "confidence": result.confidence,
                "lineage_digest": result.lineage_digest,
                "adapter_id": result.adapter_id,
                "signal_type": result.signal_type,
                "sampled_at": result.sampled_at,
                "injected_at": result.injected_at,
                "is_synthetic": result.is_synthetic,
            })
        except Exception as exc:  # pragma: no cover
            log.error("MarketFitnessIntegrator: inject_live_signal() failed — %s", exc)

    def _journal(self, *, epoch_id: str, result: IntegrationResult) -> None:
        if self._journal_fn is None:
            return
        try:
            self._journal_fn(_EVENT_TYPE, {
                "epoch_id": epoch_id,
                "live_market_score": result.live_market_score,
                "confidence": result.confidence,
                "lineage_digest": result.lineage_digest,
                "adapter_id": result.adapter_id,
                "signal_type": result.signal_type,
                "is_synthetic": result.is_synthetic,
                "injected_at": result.injected_at,
            })
        except Exception as exc:  # pragma: no cover
            log.warning("MarketFitnessIntegrator: journal failed — %s", exc)


__all__ = ["MarketFitnessIntegrator", "IntegrationResult"]
