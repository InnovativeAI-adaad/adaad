# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import json
import subprocess
import sys
from pathlib import Path


def _run_tool(tmp_path: Path, source: str, *, mode: str = "auto") -> tuple[dict, str]:
    target = tmp_path / "sample.py"
    target.write_text(source, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "fix_import_boundaries.py", str(target), "--mode", mode, "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout), target.read_text(encoding="utf-8")


def test_auto_mode_moves_import_to_single_consumer(tmp_path: Path) -> None:
    payload = """
import os


def build():
    return os.path.join("a", "b")
""".lstrip()

    report, updated = _run_tool(tmp_path, payload, mode="auto")

    assert report["applied_fix_count"] == 1
    assert report["suggested_fix_count"] == 0
    assert report["verification"]["verified_applied_fix_count"] == 1
    assert "#" not in updated
    assert "def build():\n    import os\n" in updated
    assert not updated.startswith("import os\n")


def test_auto_mode_keeps_source_when_fix_is_manual(tmp_path: Path) -> None:
    payload = """
import os

ROOT = os.getcwd()


def build():
    return os.path.join(ROOT, "x")
""".lstrip()

    report, updated = _run_tool(tmp_path, payload, mode="auto")

    assert report["applied_fix_count"] == 0
    assert report["suggested_fix_count"] == 1
    assert report["verification"]["verified_applied_fix_count"] == 0
    assert updated == payload
    assert report["suggested"][0]["classification"] == "manual"
