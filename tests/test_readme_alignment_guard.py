# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess


def test_validate_readme_alignment_guard_script_passes() -> None:
    completed = subprocess.run(["python", "scripts/validate_readme_alignment.py"], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "readme_alignment_ok" in completed.stdout
