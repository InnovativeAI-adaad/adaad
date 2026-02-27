# SPDX-License-Identifier: Apache-2.0
"""Canonical report/runtime version metadata helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPORT_VERSION_FILE = _REPO_ROOT / "governance" / "report_version.json"


def _git(args: list[str], default: str = "") -> str:
    completed = subprocess.run(["git", *args], cwd=_REPO_ROOT, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return default
    return completed.stdout.strip()


def load_report_version() -> str:
    payload = json.loads(_REPORT_VERSION_FILE.read_text(encoding="utf-8"))
    return str(payload["report_version"])


def current_git_metadata() -> Dict[str, str]:
    short_sha = _git(["rev-parse", "--short", "HEAD"], default="unknown") or "unknown"
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], default="detached") or "detached"
    tag = _git(["describe", "--tags", "--exact-match"], default="")
    return {
        "branch": branch,
        "tag": tag,
        "short_sha": short_sha,
    }


def build_snapshot_metadata() -> Dict[str, str]:
    metadata = current_git_metadata()
    metadata["report_version"] = load_report_version()
    metadata["tag"] = metadata["tag"] or "(none)"
    return metadata
