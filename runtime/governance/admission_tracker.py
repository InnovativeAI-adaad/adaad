# SPDX-License-Identifier: Apache-2.0
"""AdmissionRateTracker — ADAAD Phase 26.

Records per-epoch ``AdmissionDecision`` outcomes and produces a rolling
admission-rate health signal for ``GovernanceHealthAggregator``.

Design invariants
─────────────────
- Read-only scoring surface: ``AdmissionRateTracker`` never calls
  ``GovernanceGate`` and never approves or blocks mutations.
- Deterministic: identical sequence of recorded decisions → identical
  ``admission_rate_score``.
- Epoch-scoped: each ``record_decision()`` call is tagged with an
  ``epoch_id``; the rolling window operates over complete epochs.
- Fail-safe: empty history returns ``1.0`` (full contribution — no
  penalisation when history is unavailable).
- Window capped at ``max_epochs`` (default 10) most-recent distinct epochs.

Signal derivation
─────────────────
::

    admitted_count   = decisions where admitted == True (in window)
    total_count      = all decisions recorded (in window)
    admission_rate   = admitted_count / total_count          ∈ [0.0, 1.0]
    admission_rate_score = admission_rate                    ∈ [0.0, 1.0]

``admission_rate_score`` feeds ``GovernanceHealthAggregator`` with weight
``ADMISSION_RATE_WEIGHT = 0.10``.  A lower score means a higher proportion
of mutations are being deferred — indicating sustained health pressure.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple


TRACKER_VERSION: str = "26.0"
DEFAULT_MAX_EPOCHS: int = 10

# Weight exported for use by GovernanceHealthAggregator
ADMISSION_RATE_WEIGHT: float = 0.10


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdmissionRateReport:
    """Rolling admission-rate summary.

    Attributes
    ----------
    admission_rate_score:
        Fraction of admitted decisions in the rolling window ∈ [0.0, 1.0].
        Defaults to ``1.0`` when history is empty.
    admitted_count:
        Number of admitted decisions in the window.
    total_count:
        Total decisions in the window.
    epochs_in_window:
        Number of distinct epoch_ids contributing to this window.
    max_epochs:
        Configured rolling-window size.
    report_digest:
        SHA-256(admission_rate_score | admitted_count | total_count |
                epochs_in_window | tracker_version).
    tracker_version:
        Semver string identifying the tracker implementation.
    """

    admission_rate_score: float
    admitted_count:       int
    total_count:          int
    epochs_in_window:     int
    max_epochs:           int
    report_digest:        str
    tracker_version:      str


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class AdmissionRateTracker:
    """Record admission decisions and derive a rolling admission-rate signal.

    Usage
    -----
    ::

        tracker = AdmissionRateTracker()
        tracker.record_decision(epoch_id="epoch-42", admitted=True)
        tracker.record_decision(epoch_id="epoch-42", admitted=False)
        report = tracker.generate_report()
        signal = report.admission_rate_score   # feeds GovernanceHealthAggregator

    GovernanceGate isolation
    ────────────────────────
    ``AdmissionRateTracker`` **never** imports or calls ``GovernanceGate``.
    It is a read-only analytics surface.
    """

    def __init__(self, *, max_epochs: int = DEFAULT_MAX_EPOCHS) -> None:
        if max_epochs < 1:
            raise ValueError(f"AdmissionRateTracker: max_epochs must be >= 1; got {max_epochs}")
        self._max_epochs: int = max_epochs
        # Each entry: (epoch_id, admitted)
        self._log: Deque[Tuple[str, bool]] = deque()

    # ------------------------------------------------------------------
    # Mutation (record only — never gates mutations)
    # ------------------------------------------------------------------

    def record_decision(self, *, epoch_id: str, admitted: bool) -> None:
        """Append one admission outcome to the rolling log.

        Parameters
        ----------
        epoch_id:
            Epoch identifier for this decision.
        admitted:
            ``True`` if the mutation was admitted; ``False`` if deferred.
        """
        self._log.append((str(epoch_id), bool(admitted)))
        self._trim()

    # ------------------------------------------------------------------
    # Read-only analytics
    # ------------------------------------------------------------------

    def generate_report(self) -> AdmissionRateReport:
        """Produce a deterministic AdmissionRateReport from the rolling window.

        Empty history returns ``admission_rate_score = 1.0`` (fail-safe).
        """
        window = self._window_entries()

        total = len(window)
        if total == 0:
            rate  = 1.0
            admit = 0
            epochs = 0
        else:
            admit  = sum(1 for _, ok in window if ok)
            rate   = admit / total
            epochs = len({eid for eid, _ in window})

        rate = round(max(0.0, min(1.0, rate)), 10)
        digest = self._compute_digest(rate, admit, total, epochs)

        return AdmissionRateReport(
            admission_rate_score=rate,
            admitted_count=admit,
            total_count=total,
            epochs_in_window=epochs,
            max_epochs=self._max_epochs,
            report_digest=digest,
            tracker_version=TRACKER_VERSION,
        )

    def admission_rate_score(self) -> float:
        """Convenience accessor — returns ``generate_report().admission_rate_score``."""
        return self.generate_report().admission_rate_score

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _window_entries(self) -> List[Tuple[str, bool]]:
        """Return entries from the ``max_epochs`` most-recent distinct epochs."""
        # Walk backwards collecting epochs until we have max_epochs distinct ids
        seen: list[str] = []
        for epoch_id, _ in reversed(self._log):
            if epoch_id not in seen:
                seen.append(epoch_id)
            if len(seen) >= self._max_epochs:
                break
        if not seen:
            return []
        epoch_set = set(seen)
        return [(eid, ok) for eid, ok in self._log if eid in epoch_set]

    def _trim(self) -> None:
        """Evict entries outside the rolling window on every insert."""
        # Keep at most max_epochs distinct epoch_ids in the log
        seen: list[str] = []
        for epoch_id, _ in reversed(self._log):
            if epoch_id not in seen:
                seen.append(epoch_id)
        # epochs to evict = those ranked > max_epochs
        if len(seen) <= self._max_epochs:
            return
        evict_epochs = set(seen[self._max_epochs:])
        self._log = deque(
            (eid, ok) for eid, ok in self._log if eid not in evict_epochs
        )

    @staticmethod
    def _compute_digest(
        rate: float,
        admitted: int,
        total: int,
        epochs: int,
    ) -> str:
        payload = json.dumps(
            {
                "admission_rate_score": round(rate, 10),
                "admitted_count":       admitted,
                "total_count":          total,
                "epochs_in_window":     epochs,
                "tracker_version":      TRACKER_VERSION,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
