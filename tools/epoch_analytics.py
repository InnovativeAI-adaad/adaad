# SPDX-License-Identifier: Apache-2.0
"""
CLI tool: epoch analytics report generator.

Usage:
    python tools/epoch_analytics.py --input data/epoch_telemetry.json
    python tools/epoch_analytics.py --input data/epoch_telemetry.json --output reports/epoch_report.json
    python tools/epoch_analytics.py --input data/epoch_telemetry.json --summary
    python tools/epoch_analytics.py --input data/epoch_telemetry.json --health

Exit codes:
    0  — Report generated (or printed) successfully.
    1  — Input file not found.
    2  — Health indicators contain at least one 'warning'.
    3  — Parse / I/O error.

This tool is safe to run in CI: it never writes to governed surfaces.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate ADAAD epoch analytics report from telemetry data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--input", type=Path, required=True,
        help="Path to epoch telemetry JSON (data/epoch_telemetry.json).",
    )
    p.add_argument(
        "--output", type=Path, default=None,
        help="Write report JSON to this path instead of stdout.",
    )
    p.add_argument(
        "--summary", action="store_true",
        help="Print human-readable summary table to stdout.",
    )
    p.add_argument(
        "--health", action="store_true",
        help="Print health indicators and exit 2 if any warnings.",
    )
    p.add_argument(
        "--fail-on-warning", action="store_true",
        help="Exit 2 if any health indicator is 'warning' (CI use).",
    )
    return p


def _print_summary(report: dict) -> None:
    s = report.get("summary", {})
    n = report.get("epoch_count", 0)
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║          ADAAD Epoch Telemetry — Analytics Report        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Epochs collected:        {n}")
    print(f"  Total candidates:        {s.get('total_candidates', 0)}")
    print(f"  Total accepted:          {s.get('total_accepted', 0)}")
    print(f"  Overall acceptance rate: {s.get('overall_acceptance_rate', 0.0):.1%}")
    print(f"  Total duration:          {s.get('total_duration_seconds', 0.0):.1f}s")
    print(f"  Plateau events:          {s.get('plateau_events', 0)}")
    bandit_ep = s.get("bandit_activation_epoch")
    print(f"  Bandit activated:        epoch {bandit_ep}" if bandit_ep is not None else "  Bandit activated:        not yet (< 10 pulls)")

    dist = report.get("agent_distribution", {})
    if dist:
        print("\n  Agent distribution:")
        total_dist = sum(dist.values())
        for agent, count in sorted(dist.items(), key=lambda x: -x[1]):
            pct = count / total_dist * 100 if total_dist else 0
            bar = "█" * int(pct / 5)
            print(f"    {agent:12s}  {count:4d} epochs  {pct:5.1f}%  {bar}")

    series = report.get("series", {})
    rates = series.get("acceptance_rate", [])
    if rates:
        recent = rates[-min(5, len(rates)):]
        print(f"\n  Acceptance rate (last {len(recent)} epochs): {[f'{r:.0%}' for r in recent]}")

    print()


def _print_health(report: dict) -> bool:
    """Print health indicators table. Returns True if any warning found."""
    indicators = report.get("health_indicators", {})
    has_warning = False
    print("\n  Health Indicators:")
    print(f"  {'Indicator':<30} {'Status':<20} {'Value / Notes'}")
    print(f"  {'─'*30} {'─'*20} {'─'*30}")
    for name, info in indicators.items():
        status = info.get("status", "unknown")
        if status == "warning":
            has_warning = True
            icon = "⚠️ "
        elif status in ("healthy", "active"):
            icon = "✅ "
        else:
            icon = "ℹ️  "
        # Build a short value string
        if "value" in info:
            val = f"{info['value']}  (target: {info.get('target', '?')})"
        elif "gain_weight" in info:
            val = f"gain={info['gain_weight']}, coverage={info['coverage_weight']}  target={info.get('target','?')}"
        elif "distribution" in info:
            val = f"dominant={info.get('dominant_agent_share','?')} share"
        elif "activated_at_epoch" in info:
            ep = info["activated_at_epoch"]
            val = f"epoch {ep}" if ep is not None else f"pending ({info.get('min_pulls_required',10)} pulls)"
        elif "epochs_collected" in info:
            val = f"{info['epochs_collected']} epochs so far"
        else:
            val = ""
        print(f"  {icon} {name:<28} {status:<20} {val}")
    print()
    return has_warning


def main() -> int:
    parser = _build_parser()
    args   = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        from runtime.autonomy.epoch_telemetry import EpochTelemetry
        telemetry = EpochTelemetry.load(args.input)
        report    = telemetry.generate_report()
    except Exception as exc:
        print(f"ERROR: Failed to generate report: {exc}", file=sys.stderr)
        return 3

    if args.summary or args.health:
        if args.summary:
            _print_summary(report)
        if args.health:
            has_warning = _print_health(report)
            if (args.fail_on_warning or args.health) and has_warning:
                print("HEALTH CHECK: one or more indicators are 'warning'.", file=sys.stderr)
                return 2

    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"Report written to {args.output}")
        except OSError as exc:
            print(f"ERROR: Could not write output: {exc}", file=sys.stderr)
            return 3
    elif not args.summary and not args.health:
        print(json.dumps(report, indent=2))

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
