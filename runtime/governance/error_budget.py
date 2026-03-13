# SPDX-License-Identifier: Apache-2.0
"""Error budget tracker for fail-closed governance decisions.

Phase 3 addition: tracks the count of fail-closed decisions over a rolling
time window (ADAAD_ERROR_BUDGET_WINDOW, default 3600 seconds). When the
count of fail-closed events exceeds ADAAD_ERROR_BUDGET_THRESHOLD (default 50)
within the window, emits an ``error_budget_exceeded`` alert via the metrics
layer so operators can investigate governance pressure before it becomes a
systemic problem.

Usage:
    from runtime.governance.error_budget import get_error_budget_tracker
    tracker = get_error_budget_tracker()
    tracker.record_fail_closed("replay_divergence", context={"epoch_id": "42"})
    if tracker.is_budget_exceeded():
        metrics.log(event_type="error_budget_exceeded", ...)
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_DEFAULT_WINDOW_SECONDS = 3600   # 1-hour rolling window
_DEFAULT_THRESHOLD = 50          # fail-closed events before alert


def _window_seconds() -> float:
    try:
        return max(1.0, float(os.environ.get("ADAAD_ERROR_BUDGET_WINDOW", _DEFAULT_WINDOW_SECONDS)))
    except (ValueError, TypeError):
        return float(_DEFAULT_WINDOW_SECONDS)


def _threshold() -> int:
    try:
        return max(1, int(os.environ.get("ADAAD_ERROR_BUDGET_THRESHOLD", _DEFAULT_THRESHOLD)))
    except (ValueError, TypeError):
        return _DEFAULT_THRESHOLD


# ---------------------------------------------------------------------------
# Event record
# ---------------------------------------------------------------------------
@dataclass
class _FailClosedEvent:
    timestamp: float
    reason: str
    context: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------
class ErrorBudgetTracker:
    """Thread-safe rolling-window fail-closed event counter.

    Records each fail-closed governance decision and exposes ``is_budget_exceeded()``
    for callers to check whether the error budget threshold has been breached.
    The window and threshold are read from environment variables at call time,
    so they can be adjusted without restart in test environments.
    """

    def __init__(self) -> None:
        self._events: list[_FailClosedEvent] = []
        self._lock = threading.Lock()

    def record_fail_closed(self, reason: str, *, context: dict[str, Any] | None = None) -> None:
        """Record a single fail-closed governance decision."""
        event = _FailClosedEvent(
            timestamp=time.monotonic(),
            reason=reason,
            context=context or {},
        )
        with self._lock:
            self._events.append(event)
            self._evict_stale()

    def _evict_stale(self) -> None:
        """Remove events outside the rolling window. Must be called under lock."""
        cutoff = time.monotonic() - _window_seconds()
        self._events = [e for e in self._events if e.timestamp > cutoff]

    def count_in_window(self) -> int:
        """Return the number of fail-closed events in the current rolling window."""
        with self._lock:
            self._evict_stale()
            return len(self._events)

    def is_budget_exceeded(self) -> bool:
        """Return True if the fail-closed count exceeds the configured threshold."""
        return self.count_in_window() >= _threshold()

    def snapshot(self) -> dict[str, Any]:
        """Return a diagnostic snapshot of current budget state."""
        with self._lock:
            self._evict_stale()
            count = len(self._events)
            threshold = _threshold()
            window = _window_seconds()
            reasons: dict[str, int] = {}
            for e in self._events:
                reasons[e.reason] = reasons.get(e.reason, 0) + 1
            return {
                "count_in_window": count,
                "threshold": threshold,
                "window_seconds": window,
                "budget_exceeded": count >= threshold,
                "reason_breakdown": reasons,
            }

    def reset(self) -> None:
        """Reset the tracker — used in tests and after operator acknowledgment."""
        with self._lock:
            self._events.clear()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_tracker: ErrorBudgetTracker | None = None
_tracker_lock = threading.Lock()


def get_error_budget_tracker() -> ErrorBudgetTracker:
    """Return the module-level singleton error budget tracker."""
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = ErrorBudgetTracker()
    return _tracker


__all__ = ["ErrorBudgetTracker", "get_error_budget_tracker"]
