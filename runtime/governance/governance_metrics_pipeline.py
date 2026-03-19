# SPDX-License-Identifier: Apache-2.0
"""Periodic governance metrics pipeline for gate and blocked-event analytics."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_GOVERNANCE_METRICS_LEDGER_PATH = "security/ledger/governance_metrics_events.jsonl"
GOVERNANCE_METRICS_SCHEMA_VERSION = "1.0"
ALLOWED_EVENT_TYPES = frozenset({"gate_outcome", "blocked_emission"})
ALLOWED_GATE_STATUSES = frozenset({"pass", "fail"})
ALLOWED_TIERS = frozenset({"0", "1", "2", "3", "M"})


@dataclass(frozen=True)
class GovernanceMetricAlertThresholds:
    """Threshold defaults for governance KPI regression alerts."""

    tier1_failure_rate_warn: float = 0.15
    tier1_failure_spike_delta: float = 0.10
    replay_divergence_warn_count: int = 1
    evidence_lag_warn_hours: float = 24.0
    unblock_time_warn_hours: float = 48.0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso_utc(raw: str) -> datetime:
    normalized = raw.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def _serialize_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _require_fields(event: dict[str, Any], required: Iterable[str]) -> None:
    missing = [field for field in required if field not in event]
    if missing:
        raise ValueError(f"missing required event fields: {', '.join(sorted(missing))}")


def validate_metrics_event(event: dict[str, Any]) -> None:
    """Validate minimal metrics event schema."""

    _require_fields(
        event,
        (
            "schema_version",
            "event_type",
            "event_timestamp",
            "pr_id",
            "payload",
        ),
    )
    if event["schema_version"] != GOVERNANCE_METRICS_SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    if event["event_type"] not in ALLOWED_EVENT_TYPES:
        raise ValueError("unsupported event_type")
    _parse_iso_utc(str(event["event_timestamp"]))
    if not str(event["pr_id"]).strip():
        raise ValueError("pr_id must be non-empty")

    payload = event["payload"]
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    if event["event_type"] == "gate_outcome":
        _require_fields(payload, ("tier", "gate_name", "status"))
        if payload["tier"] not in ALLOWED_TIERS:
            raise ValueError("gate_outcome payload tier must be one of 0,1,2,3,M")
        if payload["status"] not in ALLOWED_GATE_STATUSES:
            raise ValueError("gate_outcome payload status must be pass or fail")
    elif event["event_type"] == "blocked_emission":
        _require_fields(payload, ("tier", "blocked_reason"))
        if payload["tier"] not in ALLOWED_TIERS:
            raise ValueError("blocked_emission payload tier must be one of 0,1,2,3,M")


class GovernanceMetricsLedger:
    """Append-only JSONL ledger for governance metrics events."""

    def __init__(self, path: str | Path = DEFAULT_GOVERNANCE_METRICS_LEDGER_PATH) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append_event(self, event: dict[str, Any]) -> None:
        validate_metrics_event(event)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(_serialize_json(event) + "\n")

    def emit_gate_outcome(
        self,
        *,
        pr_id: str,
        tier: str,
        gate_name: str,
        status: str,
        blocked_reason: str = "",
        replay_divergence: bool = False,
        evidence_lag_hours: float | None = None,
        event_timestamp: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tier": tier,
            "gate_name": gate_name,
            "status": status,
            "blocked_reason": blocked_reason,
            "replay_divergence": bool(replay_divergence),
        }
        if evidence_lag_hours is not None:
            payload["evidence_lag_hours"] = float(evidence_lag_hours)
        event = {
            "schema_version": GOVERNANCE_METRICS_SCHEMA_VERSION,
            "event_type": "gate_outcome",
            "event_timestamp": event_timestamp or _utc_now_iso(),
            "pr_id": pr_id,
            "payload": payload,
        }
        self.append_event(event)
        return event

    def emit_blocked_emission(
        self,
        *,
        pr_id: str,
        tier: str,
        blocked_reason: str,
        blocked_at: str,
        unblocked_at: str | None = None,
        event_timestamp: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tier": tier,
            "blocked_reason": blocked_reason,
            "blocked_at": blocked_at,
            "unblocked_at": unblocked_at,
        }
        event = {
            "schema_version": GOVERNANCE_METRICS_SCHEMA_VERSION,
            "event_type": "blocked_emission",
            "event_timestamp": event_timestamp or _utc_now_iso(),
            "pr_id": pr_id,
            "payload": payload,
        }
        self.append_event(event)
        return event


class GovernanceMetricsReport:
    """Weekly metrics and alert generation over governance metric events."""

    def __init__(self, events: Iterable[dict[str, Any]]) -> None:
        self._events = list(events)

    @classmethod
    def from_ledger(cls, path: str | Path = DEFAULT_GOVERNANCE_METRICS_LEDGER_PATH) -> "GovernanceMetricsReport":
        ledger_path = Path(path)
        if not ledger_path.exists():
            return cls([])
        events: list[dict[str, Any]] = []
        for raw_line in ledger_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            item = json.loads(line)
            validate_metrics_event(item)
            events.append(item)
        return cls(events)

    def _windowed(self, end_at: datetime, lookback_days: int) -> list[dict[str, Any]]:
        start = end_at - timedelta(days=lookback_days)
        return [
            event
            for event in self._events
            if start <= _parse_iso_utc(str(event["event_timestamp"])) <= end_at
        ]

    @staticmethod
    def _failure_rates_by_tier(gate_events: list[dict[str, Any]]) -> dict[str, float]:
        totals: dict[str, int] = defaultdict(int)
        failures: dict[str, int] = defaultdict(int)
        for event in gate_events:
            payload = event["payload"]
            tier = str(payload["tier"])
            totals[tier] += 1
            if payload["status"] == "fail":
                failures[tier] += 1
        return {
            tier: round((failures[tier] / totals[tier]), 4)
            for tier in sorted(totals)
            if totals[tier] > 0
        }

    @staticmethod
    def _mean_time_to_unblock_hours(blocked_events: list[dict[str, Any]]) -> float | None:
        durations: list[float] = []
        for event in blocked_events:
            payload = event["payload"]
            if not payload.get("unblocked_at"):
                continue
            blocked_at = _parse_iso_utc(str(payload["blocked_at"]))
            unblocked_at = _parse_iso_utc(str(payload["unblocked_at"]))
            durations.append((unblocked_at - blocked_at).total_seconds() / 3600.0)
        if not durations:
            return None
        return round(sum(durations) / len(durations), 3)

    @staticmethod
    def _most_common_blocked_reasons(blocked_events: list[dict[str, Any]], limit: int = 5) -> list[tuple[str, int]]:
        counts = Counter(str(event["payload"].get("blocked_reason") or "<none>") for event in blocked_events)
        return counts.most_common(limit)

    @staticmethod
    def _replay_divergence_frequency(gate_events: list[dict[str, Any]]) -> float:
        if not gate_events:
            return 0.0
        divergences = sum(1 for event in gate_events if bool(event["payload"].get("replay_divergence", False)))
        return round(divergences / len(gate_events), 4)

    @staticmethod
    def _evidence_completeness_lag_hours(gate_events: list[dict[str, Any]]) -> float | None:
        lags: list[float] = []
        for event in gate_events:
            payload = event["payload"]
            if "evidence_lag_hours" in payload:
                lags.append(float(payload["evidence_lag_hours"]))
        if not lags:
            return None
        return round(sum(lags) / len(lags), 3)

    def weekly_summary(self, *, end_at: datetime | None = None, lookback_days: int = 7) -> dict[str, Any]:
        report_end = end_at or datetime.now(timezone.utc)
        window = self._windowed(report_end, lookback_days)
        gate_events = [event for event in window if event["event_type"] == "gate_outcome"]
        blocked_events = [event for event in window if event["event_type"] == "blocked_emission"]

        return {
            "window_start": (report_end - timedelta(days=lookback_days)).isoformat().replace("+00:00", "Z"),
            "window_end": report_end.isoformat().replace("+00:00", "Z"),
            "event_count": len(window),
            "gate_failure_rates_by_tier": self._failure_rates_by_tier(gate_events),
            "mean_time_to_unblock_hours": self._mean_time_to_unblock_hours(blocked_events),
            "most_common_blocked_reasons": self._most_common_blocked_reasons(blocked_events),
            "replay_divergence_frequency": self._replay_divergence_frequency(gate_events),
            "evidence_completeness_lag_hours": self._evidence_completeness_lag_hours(gate_events),
            "tier1_failure_rate": self._failure_rates_by_tier(gate_events).get("1", 0.0),
            "replay_divergence_count": sum(
                1 for event in gate_events if bool(event["payload"].get("replay_divergence", False))
            ),
        }

    def evaluate_alerts(
        self,
        *,
        thresholds: GovernanceMetricAlertThresholds | None = None,
        end_at: datetime | None = None,
        lookback_days: int = 7,
    ) -> list[str]:
        threshold = thresholds or GovernanceMetricAlertThresholds()
        report_end = end_at or datetime.now(timezone.utc)
        current = self.weekly_summary(end_at=report_end, lookback_days=lookback_days)
        previous = self.weekly_summary(end_at=report_end - timedelta(days=lookback_days), lookback_days=lookback_days)

        alerts: list[str] = []
        tier1_rate = float(current.get("tier1_failure_rate") or 0.0)
        previous_tier1_rate = float(previous.get("tier1_failure_rate") or 0.0)
        if tier1_rate >= threshold.tier1_failure_rate_warn:
            alerts.append(
                f"Tier 1 gate failure rate is {tier1_rate:.2%}, above warning threshold {threshold.tier1_failure_rate_warn:.2%}."
            )
        if (tier1_rate - previous_tier1_rate) >= threshold.tier1_failure_spike_delta:
            alerts.append(
                "Tier 1 gate failure rate spike detected "
                f"({previous_tier1_rate:.2%} -> {tier1_rate:.2%}; delta {(tier1_rate - previous_tier1_rate):.2%})."
            )
        if int(current.get("replay_divergence_count") or 0) >= threshold.replay_divergence_warn_count:
            alerts.append(
                "Replay divergence count exceeded threshold "
                f"({current['replay_divergence_count']} >= {threshold.replay_divergence_warn_count})."
            )
        lag = current.get("evidence_completeness_lag_hours")
        if lag is not None and float(lag) >= threshold.evidence_lag_warn_hours:
            alerts.append(
                f"Evidence completeness lag is {float(lag):.2f}h, above {threshold.evidence_lag_warn_hours:.2f}h."
            )
        unblock = current.get("mean_time_to_unblock_hours")
        if unblock is not None and float(unblock) >= threshold.unblock_time_warn_hours:
            alerts.append(
                f"Mean time to unblock is {float(unblock):.2f}h, above {threshold.unblock_time_warn_hours:.2f}h."
            )
        return alerts

    def render_weekly_markdown(
        self,
        *,
        end_at: datetime | None = None,
        lookback_days: int = 7,
        thresholds: GovernanceMetricAlertThresholds | None = None,
    ) -> str:
        summary = self.weekly_summary(end_at=end_at, lookback_days=lookback_days)
        alerts = self.evaluate_alerts(thresholds=thresholds, end_at=end_at, lookback_days=lookback_days)
        lines = [
            "# Weekly Governance Metrics Report",
            "",
            f"- Window: `{summary['window_start']}` → `{summary['window_end']}`",
            f"- Total events: **{summary['event_count']}**",
            "",
            "## KPI Summary",
            "",
            "| KPI | Value |",
            "| --- | --- |",
            f"| Gate failure rates by tier | `{summary['gate_failure_rates_by_tier']}` |",
            f"| Mean time to unblock (hours) | `{summary['mean_time_to_unblock_hours']}` |",
            f"| Most common blocked reasons | `{summary['most_common_blocked_reasons']}` |",
            f"| Replay divergence frequency | `{summary['replay_divergence_frequency']}` |",
            f"| Evidence completeness lag (hours) | `{summary['evidence_completeness_lag_hours']}` |",
            "",
            "## Regression Alerts",
            "",
        ]
        if alerts:
            lines.extend(f"- ⚠️ {alert}" for alert in alerts)
        else:
            lines.append("- ✅ No threshold regressions detected.")
        lines.append("")
        return "\n".join(lines)


__all__ = [
    "ALLOWED_EVENT_TYPES",
    "ALLOWED_GATE_STATUSES",
    "ALLOWED_TIERS",
    "DEFAULT_GOVERNANCE_METRICS_LEDGER_PATH",
    "GOVERNANCE_METRICS_SCHEMA_VERSION",
    "GovernanceMetricAlertThresholds",
    "GovernanceMetricsLedger",
    "GovernanceMetricsReport",
    "validate_metrics_event",
]
