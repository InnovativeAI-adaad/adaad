# SPDX-License-Identifier: Apache-2.0
"""MarketDrivenContainerProfiler — ADAAD-14 Track A×C convergence.

Uses live market signals (FeedRegistry / FederatedSignalBroker) to dynamically
select the container resource profile applied to each sandbox execution.

Architecture
------------
::

    MarketDrivenContainerProfiler
         ├── select_profile()     — choose profile tier from market composite signal
         ├── profile_for_slot()   — return profile dict for ContainerOrchestrator
         └── profile_summary()    — introspect last selection + rationale

    ContainerProfileTier (enum)
         ├── CONSTRAINED  — high market pressure → minimal resources
         ├── STANDARD     — normal operating range (default)
         └── BURST        — low market pressure, spare capacity available

Profile selection rules (market composite score, lower = more expensive/stressed):
    score < 0.35  → CONSTRAINED  (cpu=25%, mem=128 MB, pids=32)
    score < 0.65  → STANDARD     (cpu=50%, mem=256 MB, pids=64)   [default]
    score >= 0.65 → BURST        (cpu=80%, mem=512 MB, pids=128)

Invariants
----------
- Profile selection is advisory; ContainerOrchestrator retains final authority
  over container pool allocation and lifecycle.
- A zero-confidence market reading always falls back to STANDARD profile.
- All profile selections are journalled for audit trail.
- Authority invariant: profiler never approves mutations or calls GovernanceGate.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

log = logging.getLogger(__name__)

# Profile tier thresholds (market composite)
_CONSTRAINED_THRESHOLD = 0.35
_BURST_THRESHOLD = 0.65
_MIN_CONFIDENCE_FOR_OVERRIDE = 0.3  # below this → stay on STANDARD regardless


class ContainerProfileTier(str, Enum):
    CONSTRAINED = "constrained"
    STANDARD    = "standard"
    BURST       = "burst"


# ---------------------------------------------------------------------------
# Static resource profile definitions
# ---------------------------------------------------------------------------

PROFILE_DEFINITIONS: Dict[ContainerProfileTier, Dict[str, Any]] = {
    ContainerProfileTier.CONSTRAINED: {
        "profile_id": "market_constrained",
        "tier": ContainerProfileTier.CONSTRAINED,
        "description": "High market pressure — reduced resource allocation",
        "cpu_quota_percent": 25,
        "memory_limit_mb": 128,
        "memory_swap_limit_mb": 128,
        "pids_limit": 32,
        "disk_write_bps": 5_242_880,    # 5 MB/s
        "disk_read_bps": 26_214_400,    # 25 MB/s
        "network_ingress_bps": 0,
        "network_egress_bps": 0,
    },
    ContainerProfileTier.STANDARD: {
        "profile_id": "market_standard",
        "tier": ContainerProfileTier.STANDARD,
        "description": "Normal market conditions — default resource allocation",
        "cpu_quota_percent": 50,
        "memory_limit_mb": 256,
        "memory_swap_limit_mb": 256,
        "pids_limit": 64,
        "disk_write_bps": 10_485_760,   # 10 MB/s
        "disk_read_bps": 52_428_800,    # 50 MB/s
        "network_ingress_bps": 0,
        "network_egress_bps": 0,
    },
    ContainerProfileTier.BURST: {
        "profile_id": "market_burst",
        "tier": ContainerProfileTier.BURST,
        "description": "Low market pressure — expanded resource allocation",
        "cpu_quota_percent": 80,
        "memory_limit_mb": 512,
        "memory_swap_limit_mb": 512,
        "pids_limit": 128,
        "disk_write_bps": 20_971_520,   # 20 MB/s
        "disk_read_bps": 104_857_600,   # 100 MB/s
        "network_ingress_bps": 0,
        "network_egress_bps": 0,
    },
}


# ---------------------------------------------------------------------------
# Selection result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProfileSelection:
    tier: ContainerProfileTier
    market_score: float
    market_confidence: float
    rationale: str
    selected_at: float
    lineage_digest: str
    overridden: bool = False  # True when confidence was too low for override

    def profile_dict(self) -> Dict[str, Any]:
        return dict(PROFILE_DEFINITIONS[self.tier])

    def to_journal_event(self) -> Dict[str, Any]:
        return {
            "event_type": "container_profile_selected.v1",
            "tier": self.tier.value,
            "market_score": self.market_score,
            "market_confidence": self.market_confidence,
            "rationale": self.rationale,
            "selected_at": self.selected_at,
            "lineage_digest": self.lineage_digest,
            "overridden": self.overridden,
        }


# ---------------------------------------------------------------------------
# MarketDrivenContainerProfiler
# ---------------------------------------------------------------------------

class MarketDrivenContainerProfiler:
    """Select container resource profile tier based on market composite signal.

    Parameters
    ----------
    score_provider:
        Callable returning (score: float, confidence: float). Typically wraps
        FeedRegistry.composite_reading() or FederatedSignalBroker.cluster_composite().
    constrained_threshold:
        Market score below which CONSTRAINED tier is selected.
    burst_threshold:
        Market score at or above which BURST tier is selected.
    min_confidence:
        Minimum confidence required to override STANDARD. Below this, STANDARD
        is always returned regardless of score.
    journal_fn:
        Optional callable accepting a journal event dict for audit trail.
    """

    def __init__(
        self,
        *,
        score_provider: Callable[[], tuple[float, float]],
        constrained_threshold: float = _CONSTRAINED_THRESHOLD,
        burst_threshold: float = _BURST_THRESHOLD,
        min_confidence: float = _MIN_CONFIDENCE_FOR_OVERRIDE,
        journal_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self._score_provider = score_provider
        self._constrained_threshold = constrained_threshold
        self._burst_threshold = burst_threshold
        self._min_confidence = min_confidence
        self._journal_fn = journal_fn
        self._last_selection: Optional[ProfileSelection] = None

    def select_profile(self, *, epoch_id: str = "") -> ProfileSelection:
        """Fetch current market signal and select the appropriate container profile tier.

        Always returns a valid ProfileSelection; falls back to STANDARD on any error.
        """
        try:
            score, confidence = self._score_provider()
        except Exception as exc:
            log.warning("MarketDrivenContainerProfiler: score_provider error — %s; using STANDARD", exc)
            score, confidence = 0.5, 0.0

        now = time.time()
        overridden = False

        if confidence < self._min_confidence:
            tier = ContainerProfileTier.STANDARD
            rationale = (
                f"confidence={confidence:.3f} below min={self._min_confidence:.3f} — STANDARD forced"
            )
            overridden = True
        elif score < self._constrained_threshold:
            tier = ContainerProfileTier.CONSTRAINED
            rationale = (
                f"score={score:.3f} < constrained_threshold={self._constrained_threshold:.3f}"
            )
        elif score >= self._burst_threshold:
            tier = ContainerProfileTier.BURST
            rationale = (
                f"score={score:.3f} >= burst_threshold={self._burst_threshold:.3f}"
            )
        else:
            tier = ContainerProfileTier.STANDARD
            rationale = (
                f"score={score:.3f} in normal range "
                f"[{self._constrained_threshold:.3f}, {self._burst_threshold:.3f})"
            )

        raw = json.dumps({
            "tier": tier.value, "score": score, "confidence": confidence,
            "epoch_id": epoch_id, "ts": now,
        }, sort_keys=True)
        digest = "sha256:" + hashlib.sha256(raw.encode()).hexdigest()

        selection = ProfileSelection(
            tier=tier,
            market_score=score,
            market_confidence=confidence,
            rationale=rationale,
            selected_at=now,
            lineage_digest=digest,
            overridden=overridden,
        )
        self._last_selection = selection

        log.debug(
            "MarketDrivenContainerProfiler: selected=%s score=%.4f confidence=%.4f epoch=%s",
            tier.value, score, confidence, epoch_id,
        )

        if self._journal_fn is not None:
            try:
                self._journal_fn(selection.to_journal_event())
            except Exception as exc:
                log.warning("MarketDrivenContainerProfiler: journal error — %s", exc)

        return selection

    def profile_for_slot(self, *, epoch_id: str = "") -> Dict[str, Any]:
        """Convenience method: select profile and return the resource dict directly."""
        return self.select_profile(epoch_id=epoch_id).profile_dict()

    @property
    def last_selection(self) -> Optional[ProfileSelection]:
        return self._last_selection

    def profile_summary(self) -> Dict[str, Any]:
        if self._last_selection is None:
            return {"status": "no_selection_yet"}
        s = self._last_selection
        return {
            "tier": s.tier.value,
            "market_score": s.market_score,
            "market_confidence": s.market_confidence,
            "rationale": s.rationale,
            "overridden": s.overridden,
            "selected_at": s.selected_at,
            "lineage_digest": s.lineage_digest,
        }


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def make_profiler_from_feed_registry(feed_registry: Any, **kwargs) -> MarketDrivenContainerProfiler:
    """Construct a profiler backed by a FeedRegistry composite reading."""
    def _provider() -> tuple[float, float]:
        reading = feed_registry.composite_reading()
        return reading.value, reading.confidence

    return MarketDrivenContainerProfiler(score_provider=_provider, **kwargs)


def make_profiler_from_federated_broker(broker: Any, **kwargs) -> MarketDrivenContainerProfiler:
    """Construct a profiler backed by a FederatedSignalBroker cluster composite."""
    def _provider() -> tuple[float, float]:
        score = broker.cluster_composite()
        # FederatedSignalBroker.cluster_composite returns a float (no confidence)
        # Use alive peer count as proxy for confidence
        peers = broker.alive_peer_count()
        confidence = min(1.0, 0.5 + peers * 0.1)
        return score, confidence

    return MarketDrivenContainerProfiler(score_provider=_provider, **kwargs)
