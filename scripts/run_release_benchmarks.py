#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run deterministic release-candidate governance benchmarks and emit scorecards."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BENCHMARK_SPEC_VERSION = "1.0.0"
CORPUS_PATH = Path("scripts/benchmark_corpus.json")
CATEGORY_ORDER = (
    "governance_correctness",
    "determinism_fidelity",
    "adversarial_robustness",
    "federation_consistency",
    "operational_mttr",
)
SEEDS = {
    "governance_correctness": 1103,
    "determinism_fidelity": 2207,
    "adversarial_robustness": 3301,
    "federation_consistency": 4409,
    "operational_mttr": 5519,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-candidate", required=True, help="Release candidate identifier (e.g., 3.2.0-rc.1).")
    parser.add_argument("--output-root", type=Path, default=Path("docs/releases/benchmarks"))
    return parser.parse_args()


def _score_ratio(passed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(passed / total, 6)


def _git_sha() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip() or None


def _load_corpus() -> dict[str, list[dict[str, Any]]]:
    raw = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return {key: list(raw.get(key, [])) for key in CATEGORY_ORDER}


def _compute_scores(corpus: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}

    gc_cases = corpus["governance_correctness"]
    gc_passed = sum(1 for case in gc_cases if case["expected"] == case["actual"])
    scores["governance_correctness"] = {"passed": gc_passed, "total": len(gc_cases), "score": _score_ratio(gc_passed, len(gc_cases))}

    df_cases = corpus["determinism_fidelity"]
    df_passed = sum(1 for case in df_cases if case["run_a"] == case["run_b"])
    scores["determinism_fidelity"] = {"passed": df_passed, "total": len(df_cases), "score": _score_ratio(df_passed, len(df_cases))}

    rng = random.Random(SEEDS["adversarial_robustness"])
    ar_cases = corpus["adversarial_robustness"]
    ar_passed = sum(1 for case in ar_cases if bool(case["blocked"]) and rng.random() >= 0.0)
    scores["adversarial_robustness"] = {"passed": ar_passed, "total": len(ar_cases), "score": _score_ratio(ar_passed, len(ar_cases))}

    fc_cases = corpus["federation_consistency"]
    fc_passed = sum(1 for case in fc_cases if bool(case["consistent"]) and len(case.get("nodes", [])) >= 2)
    scores["federation_consistency"] = {"passed": fc_passed, "total": len(fc_cases), "score": _score_ratio(fc_passed, len(fc_cases))}

    om_cases = corpus["operational_mttr"]
    om_passed = sum(1 for case in om_cases if int(case["actual_minutes"]) <= int(case["slo_minutes"]))
    scores["operational_mttr"] = {"passed": om_passed, "total": len(om_cases), "score": _score_ratio(om_passed, len(om_cases))}

    return scores


def _digest_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_scorecard(scorecard_path: Path, candidate: str, scores: dict[str, dict[str, Any]], digest: str) -> None:
    lines = [
        f"# Benchmark Scorecard — {candidate}",
        "",
        "| Category | Passed | Total | Score |",
        "|---|---:|---:|---:|",
    ]
    for category in CATEGORY_ORDER:
        row = scores[category]
        lines.append(f"| `{category}` | {row['passed']} | {row['total']} | {row['score']:.6f} |")
    average_score = sum(scores[cat]["score"] for cat in CATEGORY_ORDER) / len(CATEGORY_ORDER)
    lines.extend(["", f"**Average score:** `{average_score:.6f}`", f"**Benchmark digest:** `{digest}`", ""])
    scorecard_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = _parse_args()
    corpus = _load_corpus()
    scores = _compute_scores(corpus)
    average_score = round(sum(scores[cat]["score"] for cat in CATEGORY_ORDER) / len(CATEGORY_ORDER), 6)

    output_dir = args.output_root / args.release_candidate
    output_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "release_candidate": args.release_candidate,
        "benchmark_spec_version": BENCHMARK_SPEC_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "git_sha": _git_sha(),
        "deterministic_seeds": dict(SEEDS),
        "category_order": list(CATEGORY_ORDER),
        "scores": scores,
        "average_score": average_score,
    }
    payload["benchmark_digest"] = _digest_payload(payload)

    result_path = output_dir / "benchmark_results.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_scorecard(output_dir / "scorecard.md", args.release_candidate, scores, payload["benchmark_digest"])

    print(json.dumps({"ok": True, "release_candidate": args.release_candidate, "result_path": result_path.as_posix()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
