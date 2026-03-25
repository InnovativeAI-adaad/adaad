#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish endpoint-group performance trends (latency, payload bytes, error rate)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--history-jsonl", type=Path, default=Path("artifacts/perf/server_endpoint_perf_trends.jsonl"))
    parser.add_argument("--summary-md", type=Path, default=Path("artifacts/perf/server_endpoint_perf_trends.md"))
    parser.add_argument("--max-points", type=int, default=20)
    return parser.parse_args()


def _load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _render_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    latest = rows[-1]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        for group in row["groups"]:
            grouped.setdefault(group["group"], []).append(group)

    lines = [
        "# Server Endpoint Performance Trends",
        "",
        f"- Updated at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Runs tracked: `{len(rows)}`",
        f"- Latest status: **{'PASS' if latest.get('pass') else 'FAIL'}**",
        "",
    ]

    for group_name, samples in sorted(grouped.items()):
        latest_group = samples[-1]
        lines.extend(
            [
                f"## `{group_name}`",
                "",
                "| Metric | Latest | Prior run | Delta |",
                "|---|---:|---:|---:|",
            ]
        )
        prior_group = samples[-2] if len(samples) > 1 else samples[-1]

        for metric in ("latency_median_ms", "latency_p95_ms", "response_bytes_median", "error_rate"):
            latest_value = float(latest_group[metric])
            prior_value = float(prior_group[metric])
            delta = latest_value - prior_value
            lines.append(f"| `{metric}` | {latest_value:.6f} | {prior_value:.6f} | {delta:+.6f} |")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = _parse_args()
    run = json.loads(args.input.read_text(encoding="utf-8"))
    history = _load_history(args.history_jsonl)
    history.append(run)
    history = history[-args.max_points :]

    args.history_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.history_jsonl.write_text("\n".join(json.dumps(row, sort_keys=True) for row in history) + "\n", encoding="utf-8")
    _render_summary(args.summary_md, history)

    print(json.dumps({"ok": True, "history_jsonl": str(args.history_jsonl), "summary_md": str(args.summary_md)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
