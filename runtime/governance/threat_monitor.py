# SPDX-License-Identifier: Apache-2.0
"""Deterministic threat monitor for pre-mutation governance scans."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
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

        predicted_risk = _predict_risk(findings)

        return {
            "epoch_id": safe_epoch_id,
            "mutation_count": safe_mutation_count,
            "window_size": safe_window_size,
            "window_event_count": len(scan_window),
            "recommendation": recommendation,
            "max_severity": max_severity,
            "findings": findings,
            "predicted_risk": predicted_risk,
        }


def _count_recent_failures(events: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for item in events:
        # Support both flat dicts and ledger event envelopes (payload-wrapped).
        payload = item.get("payload") or {}
        status = str(item.get("status") or payload.get("status") or "")
        if status in {"failed", "rejected", "error"}:
            count += 1
    return count


def _float_metric(event: Dict[str, Any], key: str) -> float:
    value = event.get(key)
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _window_mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def _window_std(values: Sequence[float], mean: float) -> float:
    if len(values) <= 1:
        return 0.0
    variance = sum((value - mean) ** 2 for value in values) / float(len(values))
    return sqrt(max(0.0, variance))


def _predict_risk(findings: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = []
    total = 0.0
    for finding in findings:
        severity = max(0.0, min(1.0, float(finding.get("severity", 0.0) or 0.0)))
        if not bool(finding.get("triggered")):
            severity *= 0.25
        normalized.append((str(finding.get("detector") or ""), severity, str(finding.get("reason") or "")))
        total += severity

    risk_score = min(1.0, total / max(1.0, float(len(normalized))))
    risk_level = "low"
    if risk_score >= 0.75:
        risk_level = "critical"
    elif risk_score >= 0.5:
        risk_level = "high"
    elif risk_score >= 0.25:
        risk_level = "medium"

    attributions = [
        {"feature": name, "contribution": round(score, 6), "reason": reason}
        for name, score, reason in sorted(normalized, key=lambda row: (-row[1], row[0]))
    ]
    return {
        "score": round(risk_score, 6),
        "risk_level": risk_level,
        "attributions": attributions,
    }


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

    def failure_density_shift_detector(context: Dict[str, Any]) -> Dict[str, Any]:
        events = list(context.get("events") or [])
        if len(events) < 4:
            return {"triggered": False, "severity": 0.0, "reason": "insufficient_window", "recommendation": "continue"}
        midpoint = len(events) // 2
        left = events[:midpoint]
        right = events[midpoint:]
        if not left or not right:
            return {"triggered": False, "severity": 0.0, "reason": "insufficient_window", "recommendation": "continue"}

        left_density = _count_recent_failures(left) / float(len(left))
        right_density = _count_recent_failures(right) / float(len(right))
        drift = right_density - left_density
        if drift >= 0.5:
            return {"triggered": True, "severity": min(1.0, drift), "reason": "failure_density_trend_shift", "recommendation": "halt"}
        if drift >= 0.25:
            return {
                "triggered": True,
                "severity": min(1.0, 0.5 + drift / 2.0),
                "reason": "failure_density_elevated",
                "recommendation": "escalate",
            }
        return {"triggered": False, "severity": 0.0, "reason": "stable_failure_density", "recommendation": "continue"}

    def divergence_frequency_detector(context: Dict[str, Any]) -> Dict[str, Any]:
        events = list(context.get("events") or [])
        flags = [1.0 if bool(item.get("divergence")) else 0.0 for item in events]
        if len(flags) < 3:
            return {"triggered": False, "severity": 0.0, "reason": "insufficient_window", "recommendation": "continue"}
        mean = _window_mean(flags)
        std = _window_std(flags, mean)
        latest = flags[-1]
        z_score = 0.0 if std == 0.0 else (latest - mean) / std
        divergence_rate = sum(flags) / float(len(flags))
        if z_score >= 1.5 and divergence_rate >= 0.5:
            return {
                "triggered": True,
                "severity": min(1.0, 0.5 + divergence_rate / 2.0),
                "reason": "divergence_frequency_shift",
                "recommendation": "escalate",
            }
        return {"triggered": False, "severity": 0.0, "reason": "stable_divergence_frequency", "recommendation": "continue"}

    def resource_spike_detector(context: Dict[str, Any]) -> Dict[str, Any]:
        events = list(context.get("events") or [])
        resources = [_float_metric(item, "resource_pressure") for item in events]
        if len(resources) < 3:
            return {"triggered": False, "severity": 0.0, "reason": "insufficient_window", "recommendation": "continue"}
        baseline = resources[:-1]
        mean = _window_mean(baseline)
        std = _window_std(baseline, mean)
        latest = resources[-1]
        if std == 0.0:
            spike_ratio = 0.0 if mean <= 0.0 else latest / mean
            if spike_ratio >= 2.0:
                return {
                    "triggered": True,
                    "severity": min(1.0, spike_ratio / 3.0),
                    "reason": "resource_pressure_spike",
                    "recommendation": "escalate",
                }
            return {"triggered": False, "severity": 0.0, "reason": "stable_resource_pressure", "recommendation": "continue"}

        z_score = (latest - mean) / std
        if z_score >= 2.0:
            return {
                "triggered": True,
                "severity": min(1.0, z_score / 3.0),
                "reason": "resource_pressure_spike",
                "recommendation": "escalate",
            }
        return {"triggered": False, "severity": 0.0, "reason": "stable_resource_pressure", "recommendation": "continue"}

    return {
        "failure_spike": failure_spike_detector,
        "failure_density_shift": failure_density_shift_detector,
        "divergence_frequency": divergence_frequency_detector,
        "resource_spike": resource_spike_detector,
        "baseline_stability": noop_detector,
    }


__all__ = ["ThreatMonitor", "Recommendation", "default_detectors"]
