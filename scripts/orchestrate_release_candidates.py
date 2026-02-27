#!/usr/bin/env python3
"""Run release packaging and evidence validation for top policy-compliant candidates."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True, help="Path to candidate score/policy input JSON file.")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/release_decisions"), help="Directory to write release decision bundle.")
    return parser.parse_args()


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("candidates", [])
    if not isinstance(raw, list):
        raise ValueError("candidate payload must be a list or {'candidates': [...]} object")
    return [item for item in raw if isinstance(item, dict)]


def _score(candidate: dict[str, Any]) -> float:
    for key in ("autonomy_composite_score", "score", "forecast_roi"):
        value = candidate.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _policy_ok(candidate: dict[str, Any]) -> bool:
    verdict = candidate.get("policy_verdict")
    if isinstance(verdict, str):
        return verdict.lower() in {"pass", "allow", "compliant"}
    return bool(candidate.get("policy_compliant", False))


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, capture_output=True, text=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }


def main() -> int:
    args = _parse_args()
    candidates = _load_candidates(args.candidates)
    compliant = [candidate for candidate in candidates if _policy_ok(candidate)]
    compliant.sort(key=_score, reverse=True)

    snapshot = [
        {
            "candidate_id": item.get("candidate_id") or item.get("mutation_id") or "unknown",
            "score": _score(item),
            "policy_compliant": _policy_ok(item),
            "policy_verdict": item.get("policy_verdict", "unknown"),
        }
        for item in candidates
    ]

    bundle_id = f"release-decision-{int(time.time())}"
    bundle_dir = args.output_dir / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    build_result: dict[str, Any] | None = None
    evidence_result: dict[str, Any] | None = None

    selected = compliant[0] if compliant else None
    if selected is not None:
        build_result = _run(["bash", "scripts/build_release.sh"])
        if build_result["ok"]:
            evidence_result = _run(["python", "scripts/validate_release_evidence.py", "--require-complete"])

    bundle = {
        "bundle_id": bundle_id,
        "selected_candidate": selected,
        "score_snapshot": snapshot,
        "policy_verdicts": [
            {
                "candidate_id": row["candidate_id"],
                "policy_compliant": row["policy_compliant"],
                "policy_verdict": row["policy_verdict"],
            }
            for row in snapshot
        ],
        "release_packaging": build_result,
        "evidence_validation": evidence_result,
        "status": "executed" if selected is not None else "skipped_no_policy_compliant_candidate",
    }
    bundle_path = bundle_dir / "release_decision_bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({"ok": True, "bundle_path": str(bundle_path), "status": bundle["status"]}))
    if selected is None:
        return 0
    if not build_result or not build_result["ok"]:
        return 1
    if not evidence_result or not evidence_result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
