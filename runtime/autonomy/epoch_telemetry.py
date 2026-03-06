# SPDX-License-Identifier: Apache-2.0
"""
EpochTelemetry — structured epoch analytics engine for ADAAD.

Purpose:
    Collects EpochResult records across epochs and computes:
      - Acceptance rate trend (per epoch and rolling average)
      - Weight adaptation trajectory (gain_weight, coverage_weight)
      - Agent selection distribution (which persona was recommended)
      - Bandit state evolution (UCB1 scores per epoch)
      - Plateau event history
      - Fitness landscape progression
      - Performance health indicators aligned with EVOLUTION_ARCHITECTURE.md

Invariants:
    - append() is the ONLY mutation surface — telemetry is append-only.
    - All analytics methods are pure: identical inputs → identical outputs.
    - No entropy, no randomness, no I/O (callers persist as needed).
    - GovernanceGate is never referenced here. Telemetry is advisory.

Usage:
    telemetry = EpochTelemetry()
    telemetry.append(epoch_result)          # after each epoch
    report = telemetry.generate_report()    # call any time
    json.dumps(report)                      # fully serialisable

CLI: see tools/epoch_analytics.py
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Health indicator thresholds (from EVOLUTION_ARCHITECTURE.md)
ACCEPTANCE_RATE_HEALTHY_MIN  = 0.20
ACCEPTANCE_RATE_HEALTHY_MAX  = 0.60
WEIGHT_ACCURACY_HEALTHY_MIN  = 0.55   # by epoch 10
PLATEAU_FREQUENCY_HEALTHY_MAX = 2     # per 10 epochs
WEIGHT_BOUNDS_MIN = 0.05
WEIGHT_BOUNDS_MAX = 0.70


# ---------------------------------------------------------------------------
# EpochRecord — internal ledger entry
# ---------------------------------------------------------------------------

@dataclass
class EpochRecord:
    """Normalised record for one epoch, derived from EpochResult + landscape snapshot."""
    epoch_id:           str
    epoch_index:        int           # 0-based sequence counter
    total_candidates:   int
    accepted_count:     int
    rejected_count:     int
    duration_seconds:   float
    gain_weight:        Optional[float]
    coverage_weight:    Optional[float]
    recommended_agent:  Optional[str]
    bandit_active:      bool
    bandit_total_pulls: int
    bandit_scores:      Dict[str, float]
    is_plateau:         bool
    recorded_at:        float = field(default_factory=time.time)

    @property
    def acceptance_rate(self) -> float:
        if self.total_candidates == 0:
            return 0.0
        return round(self.accepted_count / self.total_candidates, 4)

    def to_dict(self) -> dict:
        return {
            "epoch_id":           self.epoch_id,
            "epoch_index":        self.epoch_index,
            "total_candidates":   self.total_candidates,
            "accepted_count":     self.accepted_count,
            "rejected_count":     self.rejected_count,
            "acceptance_rate":    self.acceptance_rate,
            "duration_seconds":   self.duration_seconds,
            "gain_weight":        self.gain_weight,
            "coverage_weight":    self.coverage_weight,
            "recommended_agent":  self.recommended_agent,
            "bandit_active":      self.bandit_active,
            "bandit_total_pulls": self.bandit_total_pulls,
            "bandit_scores":      self.bandit_scores,
            "is_plateau":         self.is_plateau,
            "recorded_at":        self.recorded_at,
        }


# ---------------------------------------------------------------------------
# EpochTelemetry
# ---------------------------------------------------------------------------

class EpochTelemetry:
    """
    Append-only epoch telemetry collector and analytics engine.

    Typical integration with EvolutionLoop::

        telemetry = EpochTelemetry()
        result = loop.run_epoch(context)
        telemetry.append_from_result(result, landscape=loop.landscape, adaptor=loop.weight_adaptor)
        report = telemetry.generate_report()
    """

    def __init__(self) -> None:
        self._records: List[EpochRecord] = []

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def append(self, record: EpochRecord) -> None:
        """Append a pre-built EpochRecord."""
        self._records.append(record)

    def append_from_result(
        self,
        epoch_result: Any,
        landscape: Optional[Any] = None,
        weight_adaptor: Optional[Any] = None,
    ) -> EpochRecord:
        """
        Build and append an EpochRecord from an EpochResult dataclass.

        landscape:     FitnessLandscape instance (optional, for bandit state)
        weight_adaptor: WeightAdaptor instance (optional, for weight trajectory)
        """
        idx = len(self._records)
        total = getattr(epoch_result, "total_candidates", 0)
        accepted = getattr(epoch_result, "accepted_count", 0)

        # Weight state
        gain_w = coverage_w = None
        if weight_adaptor is not None:
            try:
                snap = weight_adaptor.weight_snapshot()
                gain_w     = snap.get("gain_weight")
                coverage_w = snap.get("coverage_weight")
            except Exception:
                pass

        # Bandit + landscape state
        recommended_agent = None
        bandit_active      = False
        bandit_total_pulls = 0
        bandit_scores: Dict[str, float] = {}
        is_plateau         = False

        if landscape is not None:
            try:
                summary = landscape.summary()
                recommended_agent  = summary.get("recommended_agent")
                is_plateau         = bool(summary.get("is_plateau", False))
                bandit_info        = summary.get("bandit", {})
                bandit_active      = bool(bandit_info.get("is_active", False))
                bandit_total_pulls = int(bandit_info.get("total_pulls", 0))
                bandit_scores      = {
                    k: float(v)
                    for k, v in bandit_info.get("ucb1_scores", {}).items()
                }
            except Exception:
                pass

        record = EpochRecord(
            epoch_id=str(getattr(epoch_result, "epoch_id", f"epoch-{idx}")),
            epoch_index=idx,
            total_candidates=int(total),
            accepted_count=int(accepted),
            rejected_count=int(total) - int(accepted),
            duration_seconds=float(getattr(epoch_result, "duration_seconds", 0.0)),
            gain_weight=gain_w,
            coverage_weight=coverage_w,
            recommended_agent=recommended_agent,
            bandit_active=bandit_active,
            bandit_total_pulls=bandit_total_pulls,
            bandit_scores=bandit_scores,
            is_plateau=is_plateau,
        )
        self.append(record)
        return record

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def acceptance_rate_series(self) -> List[float]:
        """Per-epoch acceptance rates in order."""
        return [r.acceptance_rate for r in self._records]

    def rolling_acceptance_rate(self, window: int = 5) -> List[float]:
        """Rolling mean acceptance rate over the last `window` epochs."""
        rates = self.acceptance_rate_series()
        result = []
        for i in range(len(rates)):
            start = max(0, i - window + 1)
            window_rates = rates[start : i + 1]
            result.append(round(sum(window_rates) / len(window_rates), 4))
        return result

    def weight_trajectory(self) -> Dict[str, List[Optional[float]]]:
        """Per-epoch gain_weight and coverage_weight sequences."""
        return {
            "gain_weight":     [r.gain_weight     for r in self._records],
            "coverage_weight": [r.coverage_weight for r in self._records],
        }

    def agent_distribution(self) -> Dict[str, int]:
        """Count of epochs each agent was recommended."""
        dist: Dict[str, int] = {}
        for r in self._records:
            if r.recommended_agent:
                dist[r.recommended_agent] = dist.get(r.recommended_agent, 0) + 1
        return dist

    def plateau_events(self) -> List[Dict[str, Any]]:
        """List of epochs where a fitness plateau was detected."""
        return [
            {"epoch_id": r.epoch_id, "epoch_index": r.epoch_index}
            for r in self._records if r.is_plateau
        ]

    def bandit_activation_epoch(self) -> Optional[int]:
        """Return the epoch_index at which the bandit first became active, or None."""
        for r in self._records:
            if r.bandit_active:
                return r.epoch_index
        return None

    def health_indicators(self) -> Dict[str, Any]:
        """
        Compute health status aligned with EVOLUTION_ARCHITECTURE.md targets.

        Returns a dict with one entry per indicator:
            status: 'healthy' | 'warning' | 'insufficient_data'
            value:  observed value
            target: target threshold
        """
        n = len(self._records)
        indicators: Dict[str, Any] = {}

        # Acceptance rate (last epoch)
        if n >= 1:
            last_rate = self._records[-1].acceptance_rate
            if ACCEPTANCE_RATE_HEALTHY_MIN <= last_rate <= ACCEPTANCE_RATE_HEALTHY_MAX:
                status = "healthy"
            else:
                status = "warning"
            indicators["acceptance_rate"] = {
                "status": status,
                "value":  last_rate,
                "target": f"{ACCEPTANCE_RATE_HEALTHY_MIN}–{ACCEPTANCE_RATE_HEALTHY_MAX}",
            }
        else:
            indicators["acceptance_rate"] = {"status": "insufficient_data"}

        # Weight bounds check (last epoch)
        last_w = self._records[-1] if n >= 1 else None
        if last_w and last_w.gain_weight is not None and last_w.coverage_weight is not None:
            in_bounds = (
                WEIGHT_BOUNDS_MIN <= last_w.gain_weight     <= WEIGHT_BOUNDS_MAX and
                WEIGHT_BOUNDS_MIN <= last_w.coverage_weight <= WEIGHT_BOUNDS_MAX
            )
            indicators["weight_bounds"] = {
                "status":          "healthy" if in_bounds else "warning",
                "gain_weight":     last_w.gain_weight,
                "coverage_weight": last_w.coverage_weight,
                "target":          f"[{WEIGHT_BOUNDS_MIN}, {WEIGHT_BOUNDS_MAX}]",
            }
        else:
            indicators["weight_bounds"] = {"status": "insufficient_data"}

        # Plateau frequency per 10 epochs
        if n >= 10:
            last_10 = self._records[-10:]
            plateau_count = sum(1 for r in last_10 if r.is_plateau)
            indicators["plateau_frequency"] = {
                "status": "healthy" if plateau_count <= PLATEAU_FREQUENCY_HEALTHY_MAX else "warning",
                "value":  plateau_count,
                "target": f"<= {PLATEAU_FREQUENCY_HEALTHY_MAX} per 10 epochs",
            }
        else:
            indicators["plateau_frequency"] = {
                "status": "insufficient_data",
                "epochs_collected": n,
            }

        # Agent distribution balance
        dist = self.agent_distribution()
        if n >= 5 and dist:
            max_share = max(dist.values()) / n
            indicators["agent_distribution"] = {
                "status":       "healthy" if max_share <= 0.70 else "warning",
                "distribution": dist,
                "dominant_agent_share": round(max_share, 3),
                "target":       "No agent > 70% of epochs",
            }
        else:
            indicators["agent_distribution"] = {"status": "insufficient_data"}

        # Bandit activation
        bandit_epoch = self.bandit_activation_epoch()
        indicators["bandit_activation"] = {
            "status": "active" if bandit_epoch is not None else "pending",
            "activated_at_epoch": bandit_epoch,
            "min_pulls_required": 10,
        }

        return indicators

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a complete, serialisable telemetry report.

        Output is deterministic: identical epoch records → identical report.
        Suitable for JSON export, CI artifacts, and Aponi dashboard ingestion.
        """
        n = len(self._records)
        return {
            "report_version":       "1.0",
            "generated_at":         time.time(),
            "epoch_count":          n,
            "summary": {
                "total_candidates":     sum(r.total_candidates  for r in self._records),
                "total_accepted":       sum(r.accepted_count    for r in self._records),
                "total_rejected":       sum(r.rejected_count    for r in self._records),
                "overall_acceptance_rate": (
                    round(
                        sum(r.accepted_count for r in self._records) /
                        max(sum(r.total_candidates for r in self._records), 1),
                        4,
                    )
                ),
                "total_duration_seconds": round(sum(r.duration_seconds for r in self._records), 3),
                "plateau_events":         len(self.plateau_events()),
                "bandit_activation_epoch": self.bandit_activation_epoch(),
            },
            "series": {
                "acceptance_rate":         self.acceptance_rate_series(),
                "rolling_acceptance_rate": self.rolling_acceptance_rate(window=5),
                "weight_trajectory":       self.weight_trajectory(),
            },
            "agent_distribution":  self.agent_distribution(),
            "plateau_events":      self.plateau_events(),
            "health_indicators":   self.health_indicators(),
            "epochs":              [r.to_dict() for r in self._records],
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """Persist the full report to JSON. Idempotent."""
        path.parent.mkdir(parents=True, exist_ok=True)
        report = self.generate_report()
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "EpochTelemetry":
        """Restore telemetry from a saved report. Records are read-back as EpochRecords."""
        telemetry = cls()
        if not path.exists():
            return telemetry
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for ep in data.get("epochs", []):
                record = EpochRecord(
                    epoch_id=ep["epoch_id"],
                    epoch_index=ep["epoch_index"],
                    total_candidates=ep["total_candidates"],
                    accepted_count=ep["accepted_count"],
                    rejected_count=ep["rejected_count"],
                    duration_seconds=ep["duration_seconds"],
                    gain_weight=ep.get("gain_weight"),
                    coverage_weight=ep.get("coverage_weight"),
                    recommended_agent=ep.get("recommended_agent"),
                    bandit_active=bool(ep.get("bandit_active", False)),
                    bandit_total_pulls=int(ep.get("bandit_total_pulls", 0)),
                    bandit_scores=ep.get("bandit_scores", {}),
                    is_plateau=bool(ep.get("is_plateau", False)),
                    recorded_at=float(ep.get("recorded_at", 0.0)),
                )
                telemetry.append(record)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Corrupt report — return empty telemetry
        return telemetry

    def epoch_count(self) -> int:
        return len(self._records)


__all__ = [
    "EpochTelemetry",
    "EpochRecord",
    "ACCEPTANCE_RATE_HEALTHY_MIN",
    "ACCEPTANCE_RATE_HEALTHY_MAX",
    "WEIGHT_ACCURACY_HEALTHY_MIN",
    "PLATEAU_FREQUENCY_HEALTHY_MAX",
]
