# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc

from runtime.governance.governance_metrics_pipeline import (
    GovernanceMetricsLedger,
    GovernanceMetricsReport,
    validate_metrics_event,
)


def _ts(raw: str) -> str:
    return datetime.fromisoformat(raw).astimezone(UTC).isoformat().replace("+00:00", "Z")


def test_validate_metrics_event_requires_gate_fields() -> None:
    event = {
        "schema_version": "1.0",
        "event_type": "gate_outcome",
        "event_timestamp": _ts("2026-03-14T00:00:00+00:00"),
        "pr_id": "PR-PHASE65-01",
        "payload": {"tier": "1", "gate_name": "full_test_suite", "status": "fail"},
    }
    validate_metrics_event(event)


def test_metrics_report_computes_requested_kpis(tmp_path) -> None:
    ledger_path = tmp_path / "metrics.jsonl"
    ledger = GovernanceMetricsLedger(path=ledger_path)

    ledger.emit_gate_outcome(
        pr_id="PR-1",
        tier="1",
        gate_name="full_test_suite",
        status="fail",
        replay_divergence=False,
        evidence_lag_hours=36,
        event_timestamp=_ts("2026-03-10T01:00:00+00:00"),
    )
    ledger.emit_gate_outcome(
        pr_id="PR-1",
        tier="1",
        gate_name="full_test_suite",
        status="pass",
        replay_divergence=False,
        evidence_lag_hours=12,
        event_timestamp=_ts("2026-03-10T02:00:00+00:00"),
    )
    ledger.emit_gate_outcome(
        pr_id="PR-2",
        tier="2",
        gate_name="strict_replay",
        status="fail",
        replay_divergence=True,
        event_timestamp=_ts("2026-03-11T03:00:00+00:00"),
    )
    ledger.emit_blocked_emission(
        pr_id="PR-1",
        tier="1",
        blocked_reason="full_test_suite_failed",
        blocked_at=_ts("2026-03-10T01:00:00+00:00"),
        unblocked_at=_ts("2026-03-10T13:00:00+00:00"),
        event_timestamp=_ts("2026-03-10T13:05:00+00:00"),
    )

    report = GovernanceMetricsReport.from_ledger(ledger_path)
    summary = report.weekly_summary(end_at=datetime(2026, 3, 14, tzinfo=UTC), lookback_days=7)

    assert summary["gate_failure_rates_by_tier"]["1"] == 0.5
    assert summary["replay_divergence_frequency"] == 0.3333
    assert summary["mean_time_to_unblock_hours"] == 12.0
    assert summary["most_common_blocked_reasons"][0][0] == "full_test_suite_failed"
    assert summary["evidence_completeness_lag_hours"] == 24.0


def test_render_weekly_markdown_and_alerts(tmp_path) -> None:
    ledger_path = tmp_path / "metrics.jsonl"
    ledger = GovernanceMetricsLedger(path=ledger_path)
    ledger.emit_gate_outcome(
        pr_id="PR-1",
        tier="1",
        gate_name="full_test_suite",
        status="fail",
        event_timestamp=_ts("2026-03-13T01:00:00+00:00"),
    )

    report = GovernanceMetricsReport.from_ledger(ledger_path)
    markdown = report.render_weekly_markdown(end_at=datetime(2026, 3, 14, tzinfo=UTC), lookback_days=7)
    alerts = report.evaluate_alerts(end_at=datetime(2026, 3, 14, tzinfo=UTC), lookback_days=7)

    assert "Weekly Governance Metrics Report" in markdown
    assert "Regression Alerts" in markdown
    assert alerts
