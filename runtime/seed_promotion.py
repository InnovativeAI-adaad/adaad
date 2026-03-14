# SPDX-License-Identifier: Apache-2.0
"""Phase 72 — Seed Promotion Queue.

Graduated Capability Seeds (expansion_score >= GRADUATION_THRESHOLD from
Phase 71) enter this advisory promotion queue as Tier-2 mutation candidates.
The queue is read-only for external consumers; entries are never automatically
acted upon without human review.

Constitutional invariants
=========================
SEED-PROMO-0        Only seeds with expansion_score >= GRADUATION_THRESHOLD
                    may be added to the promotion queue.  Any attempt to enqueue
                    a sub-threshold seed raises PromotionThresholdError.
SEED-PROMO-IDEM-0   Re-enqueuing an already-queued seed_id is idempotent; the
                    existing entry is returned unchanged.
SEED-PROMO-HUMAN-0  The promotion queue is advisory only.  No mutation proposal
                    is created, applied, or forwarded without explicit human
                    approval.  This queue NEVER bypasses GovernanceGate or
                    HUMAN-0 gates.
SEED-PROMO-ORDER-0  Queue entries are stored in enqueue order (FIFO); list()
                    returns them oldest-first for deterministic display.

Promotion entry schema
======================
{
  "seed_id":         str,
  "lane":            str,
  "intent":          str,
  "author":          str,
  "expansion_score": float,
  "epoch_id":        str,
  "lineage_digest":  str,
  "enqueued_at":     ISO-8601,
  "status":          "pending_human_review",
}
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from runtime.innovations import CapabilitySeed
from runtime.seed_evolution import GRADUATION_THRESHOLD

logger = logging.getLogger(__name__)


class PromotionThresholdError(ValueError):
    """Raised when a seed with expansion_score < threshold is submitted (SEED-PROMO-0)."""


class SeedPromotionQueue:
    """In-process FIFO queue of graduated seeds awaiting human promotion review.

    Usage::

        queue = SeedPromotionQueue()
        queue.enqueue(seed, evolution_result, epoch_id="ep-156")
        entries = queue.list()
    """

    def __init__(self, threshold: float = GRADUATION_THRESHOLD) -> None:
        self._threshold = threshold
        self._entries: List[Dict] = []          # ordered FIFO
        self._by_id: Dict[str, Dict] = {}       # fast dedup

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def enqueue(
        self,
        seed: CapabilitySeed,
        evolution_result: Dict,
        epoch_id: str = "",
    ) -> Dict:
        """Add a graduated seed to the promotion queue.

        SEED-PROMO-0:   expansion_score must be >= threshold.
        SEED-PROMO-IDEM-0: re-enqueue of existing seed_id is a no-op.

        Returns the (existing or new) promotion entry dict.
        """
        score = float(evolution_result.get("expansion_score", 0.0))
        if score < self._threshold:
            raise PromotionThresholdError(
                f"seed {seed.seed_id!r} expansion_score={score:.4f} "
                f"< threshold={self._threshold:.4f} (SEED-PROMO-0)"
            )

        # SEED-PROMO-IDEM-0
        if seed.seed_id in self._by_id:
            logger.debug("seed_promotion: idempotent enqueue seed=%s", seed.seed_id)
            return self._by_id[seed.seed_id]

        entry: Dict = {
            "seed_id": seed.seed_id,
            "lane": seed.lane,
            "intent": seed.intent,
            "author": seed.author,
            "expansion_score": score,
            "epoch_id": epoch_id,
            "lineage_digest": evolution_result.get("lineage_digest", seed.lineage_digest()),
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending_human_review",  # SEED-PROMO-HUMAN-0
        }
        self._entries.append(entry)
        self._by_id[seed.seed_id] = entry
        logger.info(
            "seed_promotion: enqueued seed=%s score=%.4f epoch=%s",
            seed.seed_id, score, epoch_id,
        )
        return entry

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list(self) -> List[Dict]:
        """Return all promotion entries in enqueue order (SEED-PROMO-ORDER-0)."""
        return list(self._entries)

    def get(self, seed_id: str) -> Optional[Dict]:
        """Return the promotion entry for *seed_id*, or None if absent."""
        return self._by_id.get(seed_id)

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def threshold(self) -> float:
        return self._threshold


# ---------------------------------------------------------------------------
# Process-wide singleton
# ---------------------------------------------------------------------------

_QUEUE: Optional[SeedPromotionQueue] = None


def get_promotion_queue() -> SeedPromotionQueue:
    """Return the process-wide SeedPromotionQueue singleton."""
    global _QUEUE
    if _QUEUE is None:
        _QUEUE = SeedPromotionQueue()
    return _QUEUE


__all__ = [
    "PromotionThresholdError",
    "SeedPromotionQueue",
    "get_promotion_queue",
]
