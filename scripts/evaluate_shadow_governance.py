#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay-only deterministic evaluator for shadow-governance policy artifacts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALLOWED_DECISIONS = {"allow", "block"}


@dataclass(frozen=True)
class Thresholds:
    false_allow_rate_max: float
    false_block_rate_max: float
    divergence_count_max: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Path to candidate governance policy artifact (envelope or payload JSON).",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to required historical replay ledger dataset JSON.",
    )
    parser.add_argument(
        "--max-false-allow-rate",
        type=float,
        default=0.05,
        help="Fail if false allow rate exceeds this threshold.",
    )
    parser.add_argument(
        "--max-false-block-rate",
        type=float,
        default=0.20,
        help="Fail if false block rate exceeds this threshold.",
    )
    parser.add_argument(
        "--max-divergence-count",
        type=int,
        default=3,
        help="Fail if divergence count exceeds this threshold.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/shadow_governance_report.json"),
        help="JSON report output path.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_policy_payload(raw_policy: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_policy.get("payload"), dict):
        return raw_policy["payload"]
    return raw_policy


def _safe_decision(value: str, *, field_name: str, entry_id: str) -> str:
    if value not in ALLOWED_DECISIONS:
        raise ValueError(f"{entry_id}: invalid {field_name}='{value}', expected one of {sorted(ALLOWED_DECISIONS)}")
    return value


def _candidate_decision(features: dict[str, float], policy_payload: dict[str, Any]) -> str:
    risk = policy_payload.get("risk") or {}
    weights = risk.get("instability_weights") or {}
    alerts = risk.get("alerts_thresholds") or {}

    score = (
        float(weights.get("semantic_drift", 0.0)) * float(features.get("semantic_drift", 0.0))
        + float(weights.get("replay_failure", 0.0)) * float(features.get("replay_failure", 0.0))
        + float(weights.get("escalation", 0.0)) * float(features.get("escalation", 0.0))
        + float(weights.get("determinism_drift", 0.0)) * float(features.get("determinism_drift", 0.0))
    )
    instability_warning = float(alerts.get("instability_warning", 0.5))
    replay_failure_warning = float(alerts.get("replay_failure_warning", 0.05))

    if score >= instability_warning or float(features.get("replay_failure_rate", 0.0)) >= replay_failure_warning:
        return "block"
    return "allow"


def _evaluate(
    *,
    dataset: list[dict[str, Any]],
    policy_payload: dict[str, Any],
    thresholds: Thresholds,
) -> dict[str, Any]:
    total = len(dataset)
    false_allow = 0
    false_block = 0
    divergence = 0

    for row in dataset:
        entry_id = str(row.get("entry_id", "unknown"))
        expected = _safe_decision(str(row.get("expected_decision")), field_name="expected_decision", entry_id=entry_id)
        historical = _safe_decision(str(row.get("historical_decision")), field_name="historical_decision", entry_id=entry_id)

        features = row.get("features")
        if not isinstance(features, dict):
            raise ValueError(f"{entry_id}: features must be an object")

        candidate = _candidate_decision(features, policy_payload)

        if candidate != historical:
            divergence += 1
        if candidate == "allow" and expected == "block":
            false_allow += 1
        if candidate == "block" and expected == "allow":
            false_block += 1

    false_allow_rate = false_allow / total if total else 0.0
    false_block_rate = false_block / total if total else 0.0

    passed = (
        false_allow_rate <= thresholds.false_allow_rate_max
        and false_block_rate <= thresholds.false_block_rate_max
        and divergence <= thresholds.divergence_count_max
    )

    return {
        "status": "pass" if passed else "fail",
        "metrics": {
            "records_evaluated": total,
            "false_allow_count": false_allow,
            "false_allow_rate": false_allow_rate,
            "false_block_count": false_block,
            "false_block_rate": false_block_rate,
            "divergence_count": divergence,
        },
        "thresholds": {
            "false_allow_rate_max": thresholds.false_allow_rate_max,
            "false_block_rate_max": thresholds.false_block_rate_max,
            "divergence_count_max": thresholds.divergence_count_max,
        },
    }


def main() -> int:
    args = _parse_args()
    raw_policy = _load_json(args.candidate)
    if not isinstance(raw_policy, dict):
        raise ValueError("candidate policy JSON must be an object")

    dataset = _load_json(args.dataset)
    if not isinstance(dataset, list):
        raise ValueError("dataset JSON must be a list of replay records")

    report = _evaluate(
        dataset=dataset,
        policy_payload=_resolve_policy_payload(raw_policy),
        thresholds=Thresholds(
            false_allow_rate_max=args.max_false_allow_rate,
            false_block_rate_max=args.max_false_block_rate,
            divergence_count_max=args.max_divergence_count,
        ),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
