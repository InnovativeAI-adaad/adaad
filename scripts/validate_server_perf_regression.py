#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail closed only on statistically meaningful performance regressions."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/server_endpoint_perf_budgets.v1.json"))
    parser.add_argument("--permutations", type=int, default=2000)
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _group_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["group"]: row for row in payload["groups"]}


def _perm_pvalue(baseline: list[float], candidate: list[float], permutations: int) -> float:
    observed = abs(sum(candidate) / len(candidate) - sum(baseline) / len(baseline))
    combined = baseline + candidate
    rng = random.Random(20260325)
    n_base = len(baseline)
    extreme = 0
    for _ in range(permutations):
        shuffled = list(combined)
        rng.shuffle(shuffled)
        base = shuffled[:n_base]
        cand = shuffled[n_base:]
        diff = abs(sum(cand) / len(cand) - sum(base) / len(base))
        if diff >= observed:
            extreme += 1
    return (extreme + 1) / (permutations + 1)


def _is_meaningful_regression(
    *,
    baseline_value: float,
    candidate_value: float,
    min_relative_pct: float,
    min_absolute: float,
    pvalue: float,
    pvalue_threshold: float,
) -> bool:
    delta = candidate_value - baseline_value
    relative_pct = (delta / baseline_value * 100.0) if baseline_value > 0 else 0.0
    return delta > min_absolute and relative_pct > min_relative_pct and pvalue <= pvalue_threshold


def main() -> int:
    args = _parse_args()
    baseline = _load_json(args.baseline)
    candidate = _load_json(args.candidate)
    config = _load_json(args.config)

    baseline_groups = _group_rows(baseline)
    candidate_groups = _group_rows(candidate)

    policy = config["regression_policy"]
    min_relative_pct = float(policy["min_relative_regression_pct"])
    pvalue_threshold = float(policy["pvalue_threshold"])

    failures: list[str] = []
    for group_name, group_cfg in config["endpoint_groups"].items():
        if group_name not in baseline_groups or group_name not in candidate_groups:
            failures.append(f"group_missing:{group_name}")
            continue

        b = baseline_groups[group_name]
        c = candidate_groups[group_name]
        median_p = _perm_pvalue(
            [float(x) for x in b["latency_ms_samples"]],
            [float(x) for x in c["latency_ms_samples"]],
            args.permutations,
        )
        bytes_p = _perm_pvalue(
            [float(x) for x in b["response_bytes_samples"]],
            [float(x) for x in c["response_bytes_samples"]],
            args.permutations,
        )

        if _is_meaningful_regression(
            baseline_value=float(b["latency_median_ms"]),
            candidate_value=float(c["latency_median_ms"]),
            min_relative_pct=min_relative_pct,
            min_absolute=float(group_cfg["regression_noise_floor"]["latency_median_ms"]),
            pvalue=median_p,
            pvalue_threshold=pvalue_threshold,
        ):
            failures.append(f"{group_name}:latency_median_ms")

        if _is_meaningful_regression(
            baseline_value=float(b["latency_p95_ms"]),
            candidate_value=float(c["latency_p95_ms"]),
            min_relative_pct=min_relative_pct,
            min_absolute=float(group_cfg["regression_noise_floor"]["latency_p95_ms"]),
            pvalue=median_p,
            pvalue_threshold=pvalue_threshold,
        ):
            failures.append(f"{group_name}:latency_p95_ms")

        if _is_meaningful_regression(
            baseline_value=float(b["response_bytes_median"]),
            candidate_value=float(c["response_bytes_median"]),
            min_relative_pct=min_relative_pct,
            min_absolute=float(group_cfg["regression_noise_floor"]["response_bytes_median"]),
            pvalue=bytes_p,
            pvalue_threshold=pvalue_threshold,
        ):
            failures.append(f"{group_name}:response_bytes_median")

        error_delta = float(c["error_rate"]) - float(b["error_rate"])
        if error_delta > float(group_cfg["regression_noise_floor"]["error_rate"]):
            baseline_n = max(1, int(b["samples"]))
            candidate_n = max(1, int(c["samples"]))
            pooled = (float(b["error_rate"]) + float(c["error_rate"])) / 2
            se = math.sqrt(max(pooled * (1 - pooled) * (1 / baseline_n + 1 / candidate_n), 1e-9))
            z = error_delta / se
            if z >= 1.96:
                failures.append(f"{group_name}:error_rate")

    if failures:
        print(json.dumps({"ok": False, "failures": failures}))
        return 1

    print(json.dumps({"ok": True, "message": "No statistically meaningful regressions detected."}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
