# SPDX-License-Identifier: Apache-2.0
"""Deterministic threat monitor for pre-mutation governance scans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Literal, Sequence


Recommendation = Literal["continue", "escalate", "halt"]
DetectorFn = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass(frozen=True)
class ThreatMonitor:
    """Run threat detectors deterministically over a bounded scan window."""

    detectors: Dict[str, DetectorFn]
    default_window_size: int = 10

    def scan(
        self,
        *,
        epoch_id: str,
        mutation_count: int,
        events: Sequence[Dict[str, Any]] | None = None,
        window_size: int | None = None,
    ) -> Dict[str, Any]:
        safe_epoch_id = str(epoch_id or "")
        safe_mutation_count = max(0, int(mutation_count))
        safe_window_size = max(0, int(self.default_window_size if window_size is None else window_size))
        safe_events = list(events or [])
        scan_window = safe_events[-safe_window_size:] if safe_window_size else []

        findings: list[Dict[str, Any]] = []
        max_severity = 0.0
        recommendation: Recommendation = "continue"

        for detector_name in sorted(self.detectors):
            detector = self.detectors[detector_name]
            result = dict(
                detector(
                    {
                        "epoch_id": safe_epoch_id,
                        "mutation_count": safe_mutation_count,
                        "events": list(scan_window),
                        "window_size": safe_window_size,
                    }
                )
                or {}
            )
            severity = float(result.get("severity", 0.0) or 0.0)
            triggered = bool(result.get("triggered"))
            recommendation_hint = str(result.get("recommendation") or "continue")
            if recommendation_hint not in {"continue", "escalate", "halt"}:
                recommendation_hint = "continue"

            findings.append(
                {
                    "detector": detector_name,
                    "triggered": triggered,
                    "severity": severity,
                    "reason": str(result.get("reason") or ""),
                    "recommendation": recommendation_hint,
                }
            )

            if severity > max_severity:
                max_severity = severity
            if recommendation_hint == "halt":
                recommendation = "halt"
            elif recommendation_hint == "escalate" and recommendation != "halt":
                recommendation = "escalate"

        return {
            "epoch_id": safe_epoch_id,
            "mutation_count": safe_mutation_count,
            "window_size": safe_window_size,
            "window_event_count": len(scan_window),
            "recommendation": recommendation,
            "max_severity": max_severity,
            "findings": findings,
        }


def _count_recent_failures(events: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for item in events:
        status = str(item.get("status") or "")
        if status in {"failed", "rejected", "error"}:
            count += 1
    return count


def default_detectors() -> Dict[str, DetectorFn]:
    def failure_spike_detector(context: Dict[str, Any]) -> Dict[str, Any]:
        events = list(context.get("events") or [])
        failures = _count_recent_failures(events)
        if failures >= 3:
            return {
                "triggered": True,
                "severity": 1.0,
                "reason": "failure_spike_detected",
                "recommendation": "halt",
            }
        if failures >= 2:
            return {
                "triggered": True,
                "severity": 0.7,
                "reason": "elevated_failure_rate",
                "recommendation": "escalate",
            }
        return {
            "triggered": False,
            "severity": 0.0,
            "reason": "ok",
            "recommendation": "continue",
        }

    def noop_detector(_context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "triggered": False,
            "severity": 0.0,
            "reason": "ok",
            "recommendation": "continue",
        }

    return {
        "failure_spike": failure_spike_detector,
        "baseline_stability": noop_detector,
    }


__all__ = ["ThreatMonitor", "Recommendation", "default_detectors"]
