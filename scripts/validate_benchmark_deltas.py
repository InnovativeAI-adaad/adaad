#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail closed when benchmark category deltas regress unless signed waiver is provided."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CATEGORY_ORDER = (
    "governance_correctness",
    "determinism_fidelity",
    "adversarial_robustness",
    "federation_consistency",
    "operational_mttr",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--waiver", type=Path)
    return parser.parse_args()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _compute_signature(signed_by: str, signed_at_utc: str, rationale: str, categories: list[str]) -> str:
    material = f"{signed_by}|{signed_at_utc}|{rationale}|{','.join(sorted(categories))}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _validate_waiver(waiver: dict, regressions: list[str], baseline_version: str, candidate_version: str) -> list[str]:
    errors: list[str] = []
    for required in ("waiver_id", "baseline", "candidate", "regressed_categories", "rationale", "signed_by", "signed_at_utc", "signature"):
        if required not in waiver:
            errors.append(f"missing waiver field: {required}")

    if errors:
        return errors

    waiver_categories = sorted(str(c) for c in waiver["regressed_categories"])
    if waiver_categories != sorted(regressions):
        errors.append(
            f"waiver regressed_categories mismatch: waiver={waiver_categories} expected={sorted(regressions)}"
        )

    if str(waiver["baseline"]) != baseline_version:
        errors.append(f"waiver baseline mismatch: {waiver['baseline']} != {baseline_version}")

    if str(waiver["candidate"]) != candidate_version:
        errors.append(f"waiver candidate mismatch: {waiver['candidate']} != {candidate_version}")

    expected_signature = _compute_signature(
        signed_by=str(waiver["signed_by"]),
        signed_at_utc=str(waiver["signed_at_utc"]),
        rationale=str(waiver["rationale"]),
        categories=waiver_categories,
    )
    if str(waiver["signature"]) != expected_signature:
        errors.append("waiver signature invalid")

    return errors


def main() -> int:
    args = _parse_args()
    baseline = _load(args.baseline)
    candidate = _load(args.candidate)

    regressions: list[str] = []
    for category in CATEGORY_ORDER:
        baseline_score = float(baseline["scores"][category]["score"])
        candidate_score = float(candidate["scores"][category]["score"])
        if candidate_score < baseline_score:
            regressions.append(category)

    if not regressions:
        print("benchmark delta check passed: non-regressive")
        return 0

    print(f"benchmark regressions detected: {', '.join(regressions)}")
    if args.waiver is None:
        print("no waiver provided; failing closed")
        return 1

    waiver = _load(args.waiver)
    errors = _validate_waiver(
        waiver=waiver,
        regressions=regressions,
        baseline_version=str(baseline.get("release_candidate", "unknown")),
        candidate_version=str(candidate.get("release_candidate", "unknown")),
    )

    if errors:
        print("waiver validation failed:")
        for err in errors:
            print(f" - {err}")
        return 1

    print(f"benchmark regressions waived by signed rationale: {waiver['waiver_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
