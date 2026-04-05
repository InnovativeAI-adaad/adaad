# SPDX-License-Identifier: Apache-2.0
"""Deterministic change classifier for adaptive governance gates."""

from __future__ import annotations

import subprocess
from enum import Enum
from pathlib import Path
from typing import Set


class ChangeType(Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    UNKNOWN = "unknown"


def _get_changed_files() -> Set[str]:
    """Return the set of files changed in the current working tree vs HEAD."""
    try:
        # Get list of changed files (staged and unstaged)
        cmd = ["git", "diff", "HEAD", "--name-only"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}
    except subprocess.CalledProcessError:
        return set()


def _is_functional_file(path_str: str) -> bool:
    """Categorize file types into functional vs non-functional."""
    path = Path(path_str)
    
    # Core logic and configuration are always functional
    if path.suffix == ".py":
        # Check if it's a test file (tests are functional changes to verification logic)
        return True
    
    if path.name in ("pyproject.toml", "requirements.server.txt", "requirements.dev.txt", "requirements.phone.txt"):
        return True
    
    if "security/" in path_str or "runtime/governance/" in path_str:
        return True

    return False


def classify_current_changes() -> ChangeType:
    """Analyze current repository changes and return a global ChangeType."""
    changed_files = _get_changed_files()
    if not changed_files:
        return ChangeType.NON_FUNCTIONAL

    for f in changed_files:
        if _is_functional_file(f):
            return ChangeType.FUNCTIONAL

    return ChangeType.NON_FUNCTIONAL


__all__ = ["ChangeType", "classify_current_changes"]
