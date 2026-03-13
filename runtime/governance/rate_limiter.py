# SPDX-License-Identifier: Apache-2.0
"""Token-bucket rate limiter for governance mutation proposal endpoints.

H-06: Enforce ADAAD_PROPOSAL_RATE_LIMIT (default 10 req/min per source IP)
on POST /api/mutations/proposals. Emits ``governance_proposal_rate_limited``
ledger event on breach. Fail-closed design: if the limiter itself errors,
the request is rejected rather than allowed through.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_DEFAULT_RATE_LIMIT = 10        # requests per window
_DEFAULT_WINDOW_SECONDS = 60    # 1 minute rolling window


def _configured_limit() -> int:
    try:
        val = int(os.environ.get("ADAAD_PROPOSAL_RATE_LIMIT", _DEFAULT_RATE_LIMIT))
        return max(1, val)
    except (ValueError, TypeError):
        return _DEFAULT_RATE_LIMIT


def _configured_window() -> float:
    try:
        val = float(os.environ.get("ADAAD_PROPOSAL_RATE_WINDOW_SECONDS", _DEFAULT_WINDOW_SECONDS))
        return max(1.0, val)
    except (ValueError, TypeError):
        return float(_DEFAULT_WINDOW_SECONDS)


# ---------------------------------------------------------------------------
# Token bucket state per source key
# ---------------------------------------------------------------------------
@dataclass
class _Bucket:
    """Sliding-window token bucket for a single source key."""
    timestamps: list[float] = field(default_factory=list)


class ProposalRateLimiter:
    """Thread-safe sliding-window rate limiter keyed by source IP.

    Uses a sliding window (not fixed window) so a burst at a minute boundary
    cannot double the effective rate.
    """

    def __init__(self) -> None:
        self._buckets: Dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def check(self, source_key: str) -> tuple[bool, dict]:
        """Check and consume one token for *source_key*.

        Returns ``(allowed, info)`` where *info* carries diagnostic context.
        When ``allowed=False``, the caller must reject the request and emit
        the ``governance_proposal_rate_limited`` ledger event.
        """
        limit = _configured_limit()
        window = _configured_window()
        now = time.monotonic()
        cutoff = now - window

        with self._lock:
            bucket = self._buckets.setdefault(source_key, _Bucket())
            # Evict timestamps outside the sliding window
            bucket.timestamps = [t for t in bucket.timestamps if t > cutoff]
            current_count = len(bucket.timestamps)
            if current_count >= limit:
                return False, {
                    "source_key": source_key,
                    "count_in_window": current_count,
                    "limit": limit,
                    "window_seconds": window,
                    "retry_after_seconds": round(window - (now - bucket.timestamps[0]), 1),
                }
            bucket.timestamps.append(now)
            return True, {
                "source_key": source_key,
                "count_in_window": current_count + 1,
                "limit": limit,
                "window_seconds": window,
            }

    def reset(self, source_key: str | None = None) -> None:
        """Reset bucket(s) — used in tests and operational tooling."""
        with self._lock:
            if source_key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(source_key, None)


# Module-level singleton — shared across all requests in a single process.
_limiter: ProposalRateLimiter | None = None
_limiter_lock = threading.Lock()


def get_limiter() -> ProposalRateLimiter:
    """Return the module-level singleton rate limiter."""
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                _limiter = ProposalRateLimiter()
    return _limiter


__all__ = ["ProposalRateLimiter", "get_limiter"]
