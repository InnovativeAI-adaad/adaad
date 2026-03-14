# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.timeutils import now_iso

_NONDETERMINISTIC_FIELD_RE = re.compile(
    r"(?:^|_)(?:ts|timestamp|generated_at|created_at|updated_at|nonce|run_id|session_id|uuid)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReplayDivergenceArtifactBundle:
    artifact_dir: str
    machine_report_path: str
    human_report_path: str


def _sanitize_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return cleaned or "unknown"


def _normalize_for_diff(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in sorted(value.items()):
            if _NONDETERMINISTIC_FIELD_RE.search(key):
                normalized[key] = "<normalized>"
            else:
                normalized[key] = _normalize_for_diff(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_for_diff(item) for item in value]
    return value


def _first_diff_path(left: Any, right: Any, prefix: str = "") -> str | None:
    if type(left) is not type(right):
        return prefix or "$"
    if isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                return path
            diff = _first_diff_path(left[key], right[key], path)
            if diff:
                return diff
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{prefix}.length" if prefix else "length"
        for idx, (l_item, r_item) in enumerate(zip(left, right)):
            path = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            diff = _first_diff_path(l_item, r_item, path)
            if diff:
                return diff
        return None
    return None if left == right else (prefix or "$")


def _collect_ledger_excerpt(ledger: Any, epoch_id: str, *, max_entries: int = 8) -> list[dict[str, Any]]:
    if not ledger or not hasattr(ledger, "read_epoch"):
        return []
    try:
        events = ledger.read_epoch(epoch_id)
    except Exception:
        return []
    excerpt = [dict(event) for event in events[-max_entries:]]
    return _normalize_for_diff(excerpt)


def _determinism_lint_summary() -> dict[str, Any]:
    command = [
        "python",
        "tools/lint_determinism.py",
        "runtime/",
        "security/",
        "adaad/orchestrator/",
        "app/main.py",
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except Exception as exc:
        return {"command": " ".join(command), "returncode": -1, "status": "error", "summary": str(exc)}
    output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
    tail_lines = [line for line in output.splitlines() if line.strip()][-20:]
    return {
        "command": " ".join(command),
        "returncode": int(completed.returncode),
        "status": "ok" if completed.returncode == 0 else "violations",
        "summary": "\n".join(tail_lines),
    }


def build_replay_divergence_artifacts(
    *,
    preflight: dict[str, Any],
    replay_command: str,
    replay_env_flags: dict[str, str],
    ledger: Any,
    artifacts_root: Path,
) -> ReplayDivergenceArtifactBundle:
    ts = _sanitize_component(now_iso())
    artifact_dir = artifacts_root / f"replay_divergence_{ts}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    results = list(preflight.get("results") or [])
    first_divergence = next((result for result in results if not bool(result.get("passed", False))), {})
    epoch_id = str(first_divergence.get("epoch_id") or preflight.get("verify_target") or "unknown")

    expected_digest = str(first_divergence.get("expected_digest") or first_divergence.get("expected") or "sha256:0")
    actual_digest = str(first_divergence.get("actual_digest") or first_divergence.get("digest") or "sha256:0")

    expected_frame = _normalize_for_diff({"epoch_id": epoch_id, "digest": expected_digest, "passed": True})
    actual_frame = _normalize_for_diff({"epoch_id": epoch_id, "digest": actual_digest, "passed": bool(first_divergence.get("passed"))})

    normalized_divergence = _normalize_for_diff(first_divergence)
    diff_path = _first_diff_path(expected_frame, actual_frame)
    ledger_excerpt = _collect_ledger_excerpt(ledger, epoch_id)
    lint_summary = _determinism_lint_summary()

    machine_report = {
        "schema_version": "replay_divergence_artifact.v1",
        "generated_at": now_iso(),
        "replay": {
            "command": replay_command,
            "environment_flags": dict(sorted(replay_env_flags.items())),
            "verify_target": preflight.get("verify_target"),
            "decision": preflight.get("decision"),
        },
        "digests": {
            "base": expected_digest,
            "current": actual_digest,
        },
        "normalized_timeline": {
            "first_divergence_epoch": epoch_id,
            "first_divergence_path": diff_path,
            "expected_frame": expected_frame,
            "actual_frame": actual_frame,
            "result_excerpt": normalized_divergence,
        },
        "ledger_excerpt": ledger_excerpt,
        "determinism_lint": lint_summary,
    }

    machine_path = artifact_dir / "replay_divergence_report.json"
    machine_path.write_text(json.dumps(machine_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    human_lines = [
        "# Replay Divergence Artifact Report",
        "",
        f"- Generated at: `{machine_report['generated_at']}`",
        f"- Replay command: `{replay_command}`",
        f"- Verify target: `{preflight.get('verify_target')}`",
        f"- Decision: `{preflight.get('decision')}`",
        "",
        "## Digest Comparison",
        f"- Base digest: `{expected_digest}`",
        f"- Current digest: `{actual_digest}`",
        "",
        "## Normalized First Divergence",
        f"- Epoch: `{epoch_id}`",
        f"- First differing path: `{diff_path}`",
        "",
        "## Environment Flags",
    ]
    for key, value in sorted(replay_env_flags.items()):
        human_lines.append(f"- `{key}={value}`")
    human_lines.extend(
        [
            "",
            "## Determinism Lint Summary",
            f"- Command: `{lint_summary['command']}`",
            f"- Return code: `{lint_summary['returncode']}`",
            f"- Status: `{lint_summary['status']}`",
            "",
            "```text",
            str(lint_summary.get("summary") or "(no output)"),
            "```",
            "",
            "## Artifact Files",
            f"- JSON: `{machine_path.as_posix()}`",
            f"- Markdown: `{(artifact_dir / 'replay_divergence_report.md').as_posix()}`",
        ]
    )
    human_path = artifact_dir / "replay_divergence_report.md"
    human_path.write_text("\n".join(human_lines) + "\n", encoding="utf-8")

    return ReplayDivergenceArtifactBundle(
        artifact_dir=artifact_dir.as_posix(),
        machine_report_path=machine_path.as_posix(),
        human_report_path=human_path.as_posix(),
    )


__all__ = [
    "ReplayDivergenceArtifactBundle",
    "build_replay_divergence_artifacts",
]
