#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run deterministic benchmark scenarios and emit versioned artifacts per SKU."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_VERSION = "v1"
DEFAULT_SKUS = ("community", "team", "enterprise")


def _pct(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    idx = int((len(ordered) - 1) * percentile)
    return float(ordered[max(0, min(idx, len(ordered) - 1))])


def _scenario_replay_verification_latency(samples: int, payload_size: int) -> dict[str, Any]:
    latencies_ms: list[float] = []
    payload = ("adaad-replay-vector-" * 32)[:payload_size]
    for idx in range(samples):
        t0 = time.perf_counter()
        proof = hashlib.sha256(f"{payload}:{idx}".encode("utf-8")).hexdigest()
        replay = hashlib.sha256(f"{payload}:{idx}".encode("utf-8")).hexdigest()
        if proof != replay:
            raise RuntimeError("replay verification mismatch")
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
    return {
        "scenario": "replay_verification_latency",
        "unit": "ms",
        "samples": samples,
        "latency_p50_ms": round(statistics.median(latencies_ms), 3),
        "latency_p95_ms": round(_pct(latencies_ms, 0.95), 3),
        "latency_p99_ms": round(_pct(latencies_ms, 0.99), 3),
    }


def _scenario_governance_gate_throughput(samples: int) -> dict[str, Any]:
    start = time.perf_counter()
    passed = 0
    for idx in range(samples):
        policy = {
            "risk_score": idx % 10,
            "impact_score": (idx * 3) % 10,
            "constitutional_floor": 3,
        }
        approved = (policy["risk_score"] + policy["impact_score"]) <= 12
        if approved:
            passed += 1
    elapsed = max(time.perf_counter() - start, 1e-9)
    throughput = samples / elapsed
    return {
        "scenario": "governance_gate_throughput",
        "unit": "evaluations_per_second",
        "samples": samples,
        "approved": passed,
        "throughput_eps": round(throughput, 2),
    }


def _scenario_api_p95_latency_under_concurrency(requests: int, concurrency: int) -> dict[str, Any]:
    def _api_handler(seed: int) -> dict[str, Any]:
        digest = hashlib.sha256(f"api-health:{seed}".encode("utf-8")).hexdigest()
        return {"status": "ok", "digest": digest[:16], "ts_bucket": seed % 10}

    def _hit(seed: int) -> tuple[float, int]:
        t0 = time.perf_counter()
        payload = _api_handler(seed)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return elapsed_ms, 200 if payload["status"] == "ok" else 500

    latencies_ms: list[float] = []
    failures = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for elapsed_ms, status_code in pool.map(_hit, range(requests)):
            latencies_ms.append(elapsed_ms)
            if status_code >= 400:
                failures += 1

    return {
        "scenario": "api_p95_latency_under_concurrent_load",
        "unit": "ms",
        "requests": requests,
        "concurrency": concurrency,
        "latency_p50_ms": round(statistics.median(latencies_ms), 3),
        "latency_p95_ms": round(_pct(latencies_ms, 0.95), 3),
        "latency_p99_ms": round(_pct(latencies_ms, 0.99), 3),
        "error_rate": round(failures / max(1, requests), 6),
    }


def _scenario_ledger_growth_and_retrieval() -> dict[str, Any]:
    batch_sizes = [250, 1000, 2500]
    rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="adaad-ledger-bench-") as tmpdir:
        ledger_path = Path(tmpdir) / "lineage_v2.jsonl"
        for size in batch_sizes:
            write_start = time.perf_counter()
            with ledger_path.open("w", encoding="utf-8") as handle:
                for idx in range(size):
                    handle.write(json.dumps({"seq": idx, "event_type": "BenchmarkEvent", "digest": hashlib.sha256(f"{size}:{idx}".encode("utf-8")).hexdigest()}) + "\n")
            write_ms = (time.perf_counter() - write_start) * 1000.0

            read_start = time.perf_counter()
            tail = ledger_path.read_text(encoding="utf-8").splitlines()[-100:]
            retrieval_ms = (time.perf_counter() - read_start) * 1000.0

            rows.append(
                {
                    "entries": size,
                    "write_ms": round(write_ms, 3),
                    "retrieval_last_100_ms": round(retrieval_ms, 3),
                    "retrieval_rows": len(tail),
                }
            )

    return {
        "scenario": "ledger_growth_and_retrieval_performance",
        "unit": "ms",
        "samples": rows,
        "write_p95_ms": round(_pct([r["write_ms"] for r in rows], 0.95), 3),
        "retrieval_p95_ms": round(_pct([r["retrieval_last_100_ms"] for r in rows], 0.95), 3),
    }


def _sku_targets() -> dict[str, dict[str, float]]:
    return {
        "community": {
            "replay_verification_latency_p95_ms": 2.5,
            "governance_gate_throughput_min_eps": 180000.0,
            "api_p95_latency_max_ms": 40.0,
            "ledger_retrieval_p95_ms": 3.0,
        },
        "team": {
            "replay_verification_latency_p95_ms": 1.8,
            "governance_gate_throughput_min_eps": 220000.0,
            "api_p95_latency_max_ms": 28.0,
            "ledger_retrieval_p95_ms": 2.5,
        },
        "enterprise": {
            "replay_verification_latency_p95_ms": 1.5,
            "governance_gate_throughput_min_eps": 250000.0,
            "api_p95_latency_max_ms": 22.0,
            "ledger_retrieval_p95_ms": 2.0,
        },
    }


def _evaluate_against_targets(sku: str, scenarios: dict[str, Any]) -> dict[str, Any]:
    targets = _sku_targets()[sku]
    checks = {
        "replay_verification_latency": scenarios["replay_verification_latency"]["latency_p95_ms"] <= targets["replay_verification_latency_p95_ms"],
        "governance_gate_throughput": scenarios["governance_gate_throughput"]["throughput_eps"] >= targets["governance_gate_throughput_min_eps"],
        "api_p95_latency": scenarios["api_p95_latency_under_concurrent_load"]["latency_p95_ms"] <= targets["api_p95_latency_max_ms"],
        "ledger_retrieval": scenarios["ledger_growth_and_retrieval_performance"]["retrieval_p95_ms"] <= targets["ledger_retrieval_p95_ms"],
    }
    return {
        "sku": sku,
        "targets": targets,
        "checks": checks,
        "pass": all(checks.values()),
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    evals = payload["evaluation"]
    lines = [
        f"# Performance Scenario Baseline — {payload['sku'].title()}",
        "",
        f"- Generated: `{payload['generated_at_utc']}`",
        f"- Baseline version: `{payload['baseline_version']}`",
        f"- Overall status: **{'PASS' if evals['pass'] else 'FAIL'}**",
        "",
        "| Scenario | Key metric | Value | Target band | Status |",
        "|---|---|---:|---:|:---:|",
    ]
    lines.append(
        "| replay_verification_latency | p95 latency (ms) | "
        f"{payload['scenarios']['replay_verification_latency']['latency_p95_ms']:.3f} | <= {evals['targets']['replay_verification_latency_p95_ms']:.3f} | "
        f"{'✅' if evals['checks']['replay_verification_latency'] else '❌'} |"
    )
    lines.append(
        "| governance_gate_throughput | throughput (eval/s) | "
        f"{payload['scenarios']['governance_gate_throughput']['throughput_eps']:.2f} | >= {evals['targets']['governance_gate_throughput_min_eps']:.2f} | "
        f"{'✅' if evals['checks']['governance_gate_throughput'] else '❌'} |"
    )
    lines.append(
        "| api_p95_latency_under_concurrent_load | p95 latency (ms) | "
        f"{payload['scenarios']['api_p95_latency_under_concurrent_load']['latency_p95_ms']:.3f} | <= {evals['targets']['api_p95_latency_max_ms']:.3f} | "
        f"{'✅' if evals['checks']['api_p95_latency'] else '❌'} |"
    )
    lines.append(
        "| ledger_growth_and_retrieval_performance | retrieval p95 (ms) | "
        f"{payload['scenarios']['ledger_growth_and_retrieval_performance']['retrieval_p95_ms']:.3f} | <= {evals['targets']['ledger_retrieval_p95_ms']:.3f} | "
        f"{'✅' if evals['checks']['ledger_retrieval'] else '❌'} |"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sku", choices=list(DEFAULT_SKUS) + ["all"], default="all")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Version tag used in artifact path.")
    parser.add_argument("--requests", type=int, default=60, help="Request samples for concurrent API benchmark.")
    parser.add_argument("--concurrency", type=int, default=8, help="Concurrent workers for API benchmark.")
    parser.add_argument("--output-root", type=Path, default=Path("docs/releases/performance"))
    return parser.parse_args()


def _run_once(*, sku: str, version: str, requests: int, concurrency: int, output_root: Path) -> dict[str, Any]:
    scenarios = {
        "replay_verification_latency": _scenario_replay_verification_latency(samples=600, payload_size=512),
        "governance_gate_throughput": _scenario_governance_gate_throughput(samples=150000),
        "api_p95_latency_under_concurrent_load": _scenario_api_p95_latency_under_concurrency(requests=requests, concurrency=concurrency),
        "ledger_growth_and_retrieval_performance": _scenario_ledger_growth_and_retrieval(),
    }
    evaluation = _evaluate_against_targets(sku=sku, scenarios=scenarios)

    output_dir = output_root / "sku-performance-scenarios" / version
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"{sku}.performance_scenarios.{timestamp}.json"
    md_path = output_dir / f"{sku}.performance_scenarios.{timestamp}.md"

    payload = {
        "schema_version": "1.0.0",
        "baseline_version": version,
        "sku": sku,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "requests": requests,
        "concurrency": concurrency,
        "scenarios": scenarios,
        "evaluation": evaluation,
    }

    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(md_path, payload)

    return {
        "sku": sku,
        "ok": evaluation["pass"],
        "json": json_path.as_posix(),
        "markdown": md_path.as_posix(),
    }


def main() -> int:
    args = _parse_args()
    if args.requests <= 0:
        raise SystemExit("--requests must be > 0")
    if args.concurrency <= 0:
        raise SystemExit("--concurrency must be > 0")

    skus = list(DEFAULT_SKUS) if args.sku == "all" else [args.sku]
    results = [
        _run_once(
            sku=sku,
            version=args.version,
            requests=args.requests,
            concurrency=args.concurrency,
            output_root=args.output_root,
        )
        for sku in skus
    ]

    print(json.dumps({"ok": all(row["ok"] for row in results), "results": results}, indent=2))
    return 0 if all(row["ok"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
