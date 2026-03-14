#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate weekly governance metrics markdown summaries and threshold alerts."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from runtime.governance.governance_metrics_pipeline import (
    DEFAULT_GOVERNANCE_METRICS_LEDGER_PATH,
    GovernanceMetricAlertThresholds,
    GovernanceMetricsReport,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-path", default=DEFAULT_GOVERNANCE_METRICS_LEDGER_PATH)
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--end-at", default="", help="UTC ISO timestamp; default is now")
    parser.add_argument("--output", default="", help="Write markdown to this path")
    parser.add_argument("--fail-on-alerts", action="store_true")
    parser.add_argument("--tier1-failure-rate-warn", type=float, default=0.15)
    parser.add_argument("--tier1-failure-spike-delta", type=float, default=0.10)
    parser.add_argument("--replay-divergence-warn-count", type=int, default=1)
    parser.add_argument("--evidence-lag-warn-hours", type=float, default=24.0)
    parser.add_argument("--unblock-time-warn-hours", type=float, default=48.0)
    return parser


def _parse_end_at(raw: str) -> datetime:
    if not raw:
        return datetime.now(UTC)
    normalized = raw
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized).astimezone(UTC)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    thresholds = GovernanceMetricAlertThresholds(
        tier1_failure_rate_warn=args.tier1_failure_rate_warn,
        tier1_failure_spike_delta=args.tier1_failure_spike_delta,
        replay_divergence_warn_count=args.replay_divergence_warn_count,
        evidence_lag_warn_hours=args.evidence_lag_warn_hours,
        unblock_time_warn_hours=args.unblock_time_warn_hours,
    )

    report = GovernanceMetricsReport.from_ledger(args.ledger_path)
    end_at = _parse_end_at(args.end_at)
    markdown = report.render_weekly_markdown(
        end_at=end_at,
        lookback_days=args.lookback_days,
        thresholds=thresholds,
    )
    alerts = report.evaluate_alerts(
        thresholds=thresholds,
        end_at=end_at,
        lookback_days=args.lookback_days,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown + "\n", encoding="utf-8")
    print(markdown)

    if args.fail_on_alerts and alerts:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
