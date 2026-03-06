# SPDX-License-Identifier: Apache-2.0
"""Smoke-test phase sequence consistency validator."""

from __future__ import annotations

import subprocess
import sys


def test_validate_phase_sequence_consistency_passes_for_repo_state() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase_sequence_consistency.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "validation passed" in result.stdout.lower()
