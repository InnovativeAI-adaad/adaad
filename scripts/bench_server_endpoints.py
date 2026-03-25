#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run lightweight deterministic benchmarks for critical read-only endpoints and websocket connect path."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import server


DEFAULT_CONFIG_PATH = Path("config/server_endpoint_perf_budgets.v1.json")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--iterations", type=int, default=15)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--output-json", type=Path, default=Path("artifacts/perf/server_endpoint_perf_current.json"))
    parser.add_argument("--output-md", type=Path, default=Path("artifacts/perf/server_endpoint_perf_summary.md"))
    return parser.parse_args()


def _pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    idx = int((len(ordered) - 1) * p)
    return float(ordered[max(0, min(len(ordered) - 1, idx))])


def _benchmark_http_endpoint(client: TestClient, endpoint: str, iterations: int, warmups: int) -> dict[str, Any]:
    latencies_ms: list[float] = []
    response_bytes: list[int] = []
    failures = 0

    for i in range(warmups + iterations):
        t0 = time.perf_counter()
        response = client.get(endpoint)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if i >= warmups:
            latencies_ms.append(round(elapsed_ms, 3))
            response_bytes.append(len(response.content))
            if response.status_code >= 400:
                failures += 1

    return {
        "endpoint": endpoint,
        "type": "http_get",
        "samples": iterations,
        "latency_ms_samples": latencies_ms,
        "response_bytes_samples": response_bytes,
        "latency_median_ms": round(float(statistics.median(latencies_ms)), 3),
        "latency_p95_ms": round(_pct(latencies_ms, 0.95), 3),
        "response_bytes_median": int(statistics.median(response_bytes)),
        "error_rate": round(failures / iterations, 6),
    }


def _benchmark_websocket_connect(client: TestClient, endpoint: str, iterations: int, warmups: int) -> dict[str, Any]:
    latencies_ms: list[float] = []
    response_bytes: list[int] = []
    failures = 0

    for i in range(warmups + iterations):
        t0 = time.perf_counter()
        try:
            with client.websocket_connect(endpoint) as websocket:
                handshake_frame = websocket.receive_json()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            payload_size = len(json.dumps(handshake_frame, sort_keys=True).encode("utf-8"))
            if i >= warmups:
                latencies_ms.append(round(elapsed_ms, 3))
                response_bytes.append(payload_size)
        except Exception:
            if i >= warmups:
                failures += 1
                latencies_ms.append(round((time.perf_counter() - t0) * 1000.0, 3))
                response_bytes.append(0)

    return {
        "endpoint": endpoint,
        "type": "websocket_connect",
        "samples": iterations,
        "latency_ms_samples": latencies_ms,
        "response_bytes_samples": response_bytes,
        "latency_median_ms": round(float(statistics.median(latencies_ms)), 3),
        "latency_p95_ms": round(_pct(latencies_ms, 0.95), 3),
        "response_bytes_median": int(statistics.median(response_bytes)),
        "error_rate": round(failures / iterations, 6),
    }


def _aggregate_group(group_name: str, endpoint_rows: list[dict[str, Any]]) -> dict[str, Any]:
    latency_samples: list[float] = []
    response_bytes_samples: list[int] = []
    total_failures = 0
    total_samples = 0
    for row in endpoint_rows:
        latency_samples.extend(float(v) for v in row["latency_ms_samples"])
        response_bytes_samples.extend(int(v) for v in row["response_bytes_samples"])
        total_samples += int(row["samples"])
        total_failures += int(round(row["error_rate"] * row["samples"]))

    return {
        "group": group_name,
        "samples": total_samples,
        "latency_ms_samples": latency_samples,
        "response_bytes_samples": response_bytes_samples,
        "latency_median_ms": round(float(statistics.median(latency_samples)), 3),
        "latency_p95_ms": round(_pct(latency_samples, 0.95), 3),
        "response_bytes_median": int(statistics.median(response_bytes_samples)),
        "error_rate": round(total_failures / total_samples if total_samples else 1.0, 6),
        "endpoints": [row["endpoint"] for row in endpoint_rows],
    }


def _evaluate_group_budget(group_row: dict[str, Any], budget: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "latency_median_ms": float(group_row["latency_median_ms"]) <= float(budget["latency_median_ms"]),
        "latency_p95_ms": float(group_row["latency_p95_ms"]) <= float(budget["latency_p95_ms"]),
        "response_bytes_median": float(group_row["response_bytes_median"]) <= float(budget["max_payload_bytes"]),
        "error_rate": float(group_row["error_rate"]) <= float(budget["error_rate"]),
    }
    return {
        "group": group_row["group"],
        "pass": all(checks.values()),
        "checks": checks,
    }


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Server Endpoint Performance Summary",
        "",
        f"- Generated at: `{payload['generated_at_utc']}`",
        f"- Iterations: `{payload['iterations']}`",
        f"- Warmups: `{payload['warmups']}`",
        f"- Status: **{'PASS' if payload['pass'] else 'FAIL'}**",
        "",
        "| Group | Median latency (ms) | P95 latency (ms) | Median bytes | Error rate | Status |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for group in payload["groups"]:
        status = "✅" if payload["budgets"][group["group"]]["pass"] else "❌"
        lines.append(
            f"| `{group['group']}` | {group['latency_median_ms']:.3f} | {group['latency_p95_ms']:.3f} | "
            f"{group['response_bytes_median']} | {group['error_rate']:.6f} | {status} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = _parse_args()
    if args.iterations <= 0:
        raise SystemExit("--iterations must be > 0")
    if args.warmups < 0:
        raise SystemExit("--warmups must be >= 0")

    config = json.loads(args.config.read_text(encoding="utf-8"))
    groups = config["endpoint_groups"]

    endpoint_rows: dict[str, list[dict[str, Any]]] = {}
    with TestClient(server.app) as client:
        for group_name, group_cfg in groups.items():
            rows: list[dict[str, Any]] = []
            for endpoint in group_cfg.get("http_get", []):
                rows.append(_benchmark_http_endpoint(client, endpoint, args.iterations, args.warmups))
            for endpoint in group_cfg.get("websocket_connect", []):
                rows.append(_benchmark_websocket_connect(client, endpoint, args.iterations, args.warmups))
            endpoint_rows[group_name] = rows

    group_rollups = [_aggregate_group(name, rows) for name, rows in endpoint_rows.items()]
    budget_results = {
        group["group"]: _evaluate_group_budget(group, groups[group["group"]]["budgets"])
        for group in group_rollups
    }
    overall_pass = all(row["pass"] for row in budget_results.values())

    payload = {
        "schema_version": "1.0.0",
        "config_version": str(config.get("config_version", "v1")),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "iterations": args.iterations,
        "warmups": args.warmups,
        "pass": overall_pass,
        "groups": group_rollups,
        "budgets": budget_results,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_summary(args.output_md, payload)
    print(json.dumps({"ok": overall_pass, "output_json": str(args.output_json), "output_md": str(args.output_md)}))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
