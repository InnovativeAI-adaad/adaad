#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run release packaging and evidence validation for top policy-compliant candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.tools.execution_contract import build_check_request, execute_tool_request, lint_check_request


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True, help="Path to candidate score/policy input JSON file.")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/release_decisions"), help="Directory to write release decision bundle.")
    return parser.parse_args()


def _extract_candidates(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        raw = raw.get("candidates", [])
    if not isinstance(raw, list):
        raise ValueError("candidate payload must be a list or {'candidates': [...]} object")
    return [item for item in raw if isinstance(item, dict)]


def _canonical_json(value: Any) -> str:
    """Return a deterministic JSON encoding for digest derivation."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _resolve_release_metadata(raw_payload: Any) -> tuple[str, str]:
    """Resolve release version/lane from candidate payload metadata.

    This preserves a stable derivation contract for release decision bundle IDs.
    """
    if not isinstance(raw_payload, dict):
        return "unknown-version", "unknown-lane"

    version = str(raw_payload.get("release_version") or raw_payload.get("version") or "").strip()
    lane = str(raw_payload.get("lane") or raw_payload.get("control_lane") or "").strip()
    return version or "unknown-version", lane or "unknown-lane"


def _derive_bundle_id(*, release_inputs: Any, release_version: str, lane: str) -> str:
    """Build a deterministic, human-readable release decision bundle ID.

    ID derivation contract (deterministic by construction):
    1) Normalize the release inputs + release metadata to canonical JSON.
    2) Compute SHA-256 over that canonical string.
    3) Emit a readable stable label + short digest segment:
       ``release-decision-<12hex>``.

    This intentionally replaces epoch-second suffixes so re-running with the
    same inputs yields the same bundle ID.
    """
    canonical_material = {
        "lane": str(lane or "unknown-lane"),
        "release_inputs": release_inputs,
        "release_version": str(release_version or "unknown-version"),
    }
    digest = hashlib.sha256(_canonical_json(canonical_material).encode("utf-8")).hexdigest()
    return f"release-decision-{digest[:12]}"


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


def _run(request):
    result = execute_tool_request(request)
    return {
        "tool_id": request.tool_id,
        "check_kind": request.check_kind,
        "command": list(request.command),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "status": result.status,
        "duration_ms": result.duration_ms,
        "failure_reason": result.failure_reason,
        "artifact_pointers": dict(sorted(request.artifact_pointers.items())),
        "ok": result.ok,
    }


def main() -> int:
    args = _parse_args()
    raw_payload = json.loads(args.candidates.read_text(encoding="utf-8"))
    candidates = _extract_candidates(raw_payload)
    release_version, lane = _resolve_release_metadata(raw_payload)
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

    bundle_id = _derive_bundle_id(release_inputs=raw_payload, release_version=release_version, lane=lane)
    bundle_dir = args.output_dir / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    build_result: dict[str, Any] | None = None
    evidence_result: dict[str, Any] | None = None

    selected = compliant[0] if compliant else None
    if selected is not None:
        build_result = _run(
            build_check_request(
                tool_id="release-build",
                command=("bash", "scripts/build_release.sh"),
                artifact_pointers={"release_dir": "releases/", "policy_artifact": "artifacts/policy/"},
            )
        )
        if build_result["ok"]:
            evidence_result = _run(
                lint_check_request(
                    tool_id="release-evidence-validation",
                    command=("python", "scripts/validate_release_evidence.py", "--require-complete"),
                )
            )

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
