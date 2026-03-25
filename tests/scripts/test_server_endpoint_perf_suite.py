# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_server_endpoint_benchmark_and_trend_publish(tmp_path: Path) -> None:
    output_json = tmp_path / "current.json"
    output_md = tmp_path / "summary.md"
    trends_jsonl = tmp_path / "trends.jsonl"
    trends_md = tmp_path / "trends.md"
    config_path = tmp_path / "budgets.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "config_version": "v1",
                "regression_policy": {"min_relative_regression_pct": 8.0, "pvalue_threshold": 0.05},
                "endpoint_groups": {
                    "critical_read_gets": {
                        "http_get": ["/api/health"],
                        "websocket_connect": [],
                        "budgets": {"latency_median_ms": 10000.0, "latency_p95_ms": 10000.0, "max_payload_bytes": 1000000, "error_rate": 1.0},
                        "regression_noise_floor": {"latency_median_ms": 2.0, "latency_p95_ms": 4.0, "response_bytes_median": 128.0, "error_rate": 0.02},
                    },
                    "websocket_connect_path": {
                        "http_get": [],
                        "websocket_connect": ["/ws/events"],
                        "budgets": {"latency_median_ms": 10000.0, "latency_p95_ms": 10000.0, "max_payload_bytes": 1000000, "error_rate": 1.0},
                        "regression_noise_floor": {"latency_median_ms": 3.0, "latency_p95_ms": 6.0, "response_bytes_median": 64.0, "error_rate": 0.02},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/bench_server_endpoints.py",
            "--iterations",
            "2",
            "--warmups",
            "0",
            "--config",
            str(config_path),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        check=True,
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0.0"
    assert {group["group"] for group in payload["groups"]} == {"critical_read_gets", "websocket_connect_path"}

    subprocess.run(
        [
            sys.executable,
            "scripts/publish_server_perf_trends.py",
            "--input",
            str(output_json),
            "--history-jsonl",
            str(trends_jsonl),
            "--summary-md",
            str(trends_md),
        ],
        check=True,
    )
    assert "Server Endpoint Performance Trends" in trends_md.read_text(encoding="utf-8")


def test_server_perf_regression_gate_only_blocks_meaningful_regression(tmp_path: Path) -> None:
    baseline = {
        "groups": [
            {
                "group": "critical_read_gets",
                "samples": 10,
                "latency_ms_samples": [10.0] * 10,
                "response_bytes_samples": [1000] * 10,
                "latency_median_ms": 10.0,
                "latency_p95_ms": 10.0,
                "response_bytes_median": 1000,
                "error_rate": 0.0,
            },
            {
                "group": "websocket_connect_path",
                "samples": 10,
                "latency_ms_samples": [20.0] * 10,
                "response_bytes_samples": [200] * 10,
                "latency_median_ms": 20.0,
                "latency_p95_ms": 20.0,
                "response_bytes_median": 200,
                "error_rate": 0.0,
            },
        ]
    }
    noisy = {
        "groups": [
            {
                "group": "critical_read_gets",
                "samples": 10,
                "latency_ms_samples": [10.5] * 10,
                "response_bytes_samples": [1004] * 10,
                "latency_median_ms": 10.5,
                "latency_p95_ms": 10.5,
                "response_bytes_median": 1004,
                "error_rate": 0.0,
            },
            {
                "group": "websocket_connect_path",
                "samples": 10,
                "latency_ms_samples": [20.6] * 10,
                "response_bytes_samples": [201] * 10,
                "latency_median_ms": 20.6,
                "latency_p95_ms": 20.6,
                "response_bytes_median": 201,
                "error_rate": 0.0,
            },
        ]
    }
    regressed = {
        "groups": [
            {
                "group": "critical_read_gets",
                "samples": 10,
                "latency_ms_samples": [22.0] * 10,
                "response_bytes_samples": [2000] * 10,
                "latency_median_ms": 22.0,
                "latency_p95_ms": 22.0,
                "response_bytes_median": 2000,
                "error_rate": 0.2,
            },
            {
                "group": "websocket_connect_path",
                "samples": 10,
                "latency_ms_samples": [36.0] * 10,
                "response_bytes_samples": [500] * 10,
                "latency_median_ms": 36.0,
                "latency_p95_ms": 36.0,
                "response_bytes_median": 500,
                "error_rate": 0.0,
            },
        ]
    }

    baseline_path = tmp_path / "baseline.json"
    noisy_path = tmp_path / "noisy.json"
    regressed_path = tmp_path / "regressed.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    noisy_path.write_text(json.dumps(noisy), encoding="utf-8")
    regressed_path.write_text(json.dumps(regressed), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/validate_server_perf_regression.py",
            "--baseline",
            str(baseline_path),
            "--candidate",
            str(noisy_path),
            "--config",
            "config/server_endpoint_perf_budgets.v1.json",
            "--permutations",
            "200",
        ],
        check=True,
    )

    failed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_server_perf_regression.py",
            "--baseline",
            str(baseline_path),
            "--candidate",
            str(regressed_path),
            "--config",
            "config/server_endpoint_perf_budgets.v1.json",
            "--permutations",
            "200",
        ],
        check=False,
    )
    assert failed.returncode == 1
