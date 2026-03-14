#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail if Python build/lib artifacts are committed as source files."""

from __future__ import annotations

import subprocess
import sys

FORBIDDEN_PATHS = (
    "build/lib/**/*.py",
    "build/lib/*.py",
)


def _tracked_build_lib_python_files() -> list[str]:
    cmd = ["git", "ls-files", "--", *FORBIDDEN_PATHS]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git ls-files failure"
        raise RuntimeError(f"git ls-files failed: {detail}")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def main() -> int:
    tracked_files = _tracked_build_lib_python_files()
    if tracked_files:
        print("[ADAAD BLOCKED] build/lib Python artifacts must not be versioned.")
        print("Remove these tracked files and keep runtime/ as the source-of-truth:")
        for path in tracked_files:
            print(f" - {path}")
        return 1

    print("ok: no git-tracked build/lib Python artifacts found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
