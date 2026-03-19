#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Benchmark a constrained mobile profile and fail closed on budget regressions."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=7, help="Measured iterations per benchmark.")
    parser.add_argument("--warmups", type=int, default=2, help="Warmup iterations (not counted).")
    parser.add_argument("--budgets", type=Path, default=Path("config/mobile_perf_budgets.json"))
    parser.add_argument("--output-json", type=Path, default=Path("artifacts/mobile_perf/mobile_benchmark.json"))
    parser.add_argument("--output-md", type=Path, default=Path("artifacts/mobile_perf/mobile_benchmark_summary.md"))
    return parser.parse_args()


def _run_python_snippet(snippet: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip())


def _sample_startup_latency_ms() -> float:
    snippet = (
        "import json,time;"
        "t=time.perf_counter();"
        "import app.main;"
        "d=(time.perf_counter()-t)*1000.0;"
        "print(json.dumps({'value': d}))"
    )
    return float(_run_python_snippet(snippet)["value"])


def _sample_peak_memory_mb() -> float:
    snippet = (
        "import json,tracemalloc,pathlib;"
        "tracemalloc.start();"
        "import app.main;"
        "registry=pathlib.Path('docs/assets/qr/registry.json').read_text(encoding='utf-8');"
        "ledger=pathlib.Path('data/checkpoint_chain.jsonl').read_text(encoding='utf-8');"
        "_={'registry_len':len(registry),'ledger_len':len(ledger)};"
        "_,peak=tracemalloc.get_traced_memory();"
        "print(json.dumps({'value': peak/(1024*1024)}))"
    )
    return float(_run_python_snippet(snippet)["value"])


def _sample_qr_workflow_ms() -> float:
    snippet = (
        "import json,time,pathlib;"
        "t=time.perf_counter();"
        "raw=pathlib.Path('docs/assets/qr/registry.json').read_text(encoding='utf-8');"
        "doc=json.loads(raw);"
        "items=doc.get('assets',[]);"
        "digest=''.join(sorted(str(i.get('id','')) for i in items));"
        "assert len(digest)>=0;"
        "d=(time.perf_counter()-t)*1000.0;"
        "print(json.dumps({'value': d}))"
    )
    return float(_run_python_snippet(snippet)["value"])


def _sample_ledger_workflow_ms() -> float:
    snippet = (
        "import json,time,hashlib,pathlib,tempfile,os;"
        "source=pathlib.Path('data/checkpoint_chain.jsonl').read_text(encoding='utf-8').splitlines();"
        "t=time.perf_counter();"
        "dig=hashlib.sha256();"
        "[dig.update(line.encode('utf-8')) for line in source[:256]];"
        "fd,tmp=tempfile.mkstemp(text=True);"
        "os.close(fd);"
        "p=pathlib.Path(tmp);"
        "p.write_text('\\n'.join(source[:8])+'\\n'+json.dumps({'event':'mobile-bench','digest':dig.hexdigest()})+'\\n', encoding='utf-8');"
        "_=len(p.read_text(encoding='utf-8').splitlines());"
        "p.unlink(missing_ok=True);"
        "d=(time.perf_counter()-t)*1000.0;"
        "print(json.dumps({'value': d}))"
    )
    return float(_run_python_snippet(snippet)["value"])


@dataclass(frozen=True)
class MetricResult:
    samples: list[float]

    @property
    def median(self) -> float:
        return float(round(statistics.median(self.samples), 3))

    @property
    def p95(self) -> float:
        ordered = sorted(self.samples)
        idx = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.95)))
        return float(round(ordered[idx], 3))


METRICS = {
    "startup_latency_ms": _sample_startup_latency_ms,
    "peak_memory_mb": _sample_peak_memory_mb,
    "qr_workflow_ms": _sample_qr_workflow_ms,
    "ledger_workflow_ms": _sample_ledger_workflow_ms,
}


def _measure(metric_fn: Any, warmups: int, iterations: int) -> MetricResult:
    for _ in range(warmups):
        metric_fn()
    samples = [float(metric_fn()) for _ in range(iterations)]
    return MetricResult(samples=samples)


def _load_budgets(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _evaluate_budget(metric_name: str, measured: MetricResult, budget: dict[str, Any]) -> dict[str, Any]:
    median = measured.median
    max_budget = float(budget["max"])
    baseline = float(budget["baseline"])
    tolerance = float(budget["regression_tolerance_pct"])
    allowed_regression = baseline * (1.0 + tolerance / 100.0)
    pass_absolute = median <= max_budget
    pass_delta = median <= allowed_regression
    return {
        "metric": metric_name,
        "median": median,
        "p95": measured.p95,
        "max_budget": max_budget,
        "baseline": baseline,
        "regression_tolerance_pct": tolerance,
        "allowed_regression": round(allowed_regression, 3),
        "pass_absolute": pass_absolute,
        "pass_delta": pass_delta,
        "pass": pass_absolute and pass_delta,
        "samples": [round(s, 3) for s in measured.samples],
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Mobile Performance Benchmark Summary",
        "",
        f"- Profile: `{payload['profile']}`",
        f"- Generated: `{payload['generated_at_utc']}`",
        f"- Overall status: **{'PASS' if payload['pass'] else 'FAIL'}**",
        "",
        "| Metric | Median | P95 | Max budget | Allowed regression | Status |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for result in payload["results"]:
        status = "✅" if result["pass"] else "❌"
        lines.append(
            f"| `{result['metric']}` | {result['median']:.3f} | {result['p95']:.3f} | "
            f"{result['max_budget']:.3f} | {result['allowed_regression']:.3f} | {status} |"
        )

    failures = [r for r in payload["results"] if not r["pass"]]
    if failures:
        lines.extend(["", "## Regressions", ""])
        for failed in failures:
            lines.append(
                f"- `{failed['metric']}` failed (median={failed['median']:.3f}, "
                f"max={failed['max_budget']:.3f}, allowed_delta={failed['allowed_regression']:.3f})"
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = _parse_args()
    if args.iterations <= 0:
        raise SystemExit("--iterations must be > 0")
    if args.warmups < 0:
        raise SystemExit("--warmups must be >= 0")

    budgets = _load_budgets(args.budgets)
    metric_budgets = budgets["metrics"]

    results: list[dict[str, Any]] = []
    for metric, metric_fn in METRICS.items():
        measured = _measure(metric_fn=metric_fn, warmups=args.warmups, iterations=args.iterations)
        results.append(_evaluate_budget(metric_name=metric, measured=measured, budget=metric_budgets[metric]))

    overall_pass = all(result["pass"] for result in results)
    payload = {
        "schema_version": "1.0.0",
        "profile": budgets.get("profile", "pydroid3_constrained"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "iterations": args.iterations,
        "warmups": args.warmups,
        "pass": overall_pass,
        "results": results,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(args.output_md, payload)

    print(json.dumps({"ok": overall_pass, "json": args.output_json.as_posix(), "markdown": args.output_md.as_posix()}))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
