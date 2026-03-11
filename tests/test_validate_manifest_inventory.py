# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import shutil
import subprocess
import sys
from pathlib import Path


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/validate_manifest_inventory.py", "--format", "json"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def _seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "docs" / "governance").mkdir(parents=True)
    (repo / "docs" / "releases").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)

    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_manifest_inventory.py"
    shutil.copy2(src, repo / "scripts" / "validate_manifest_inventory.py")

    (repo / "VERSION").write_text("2.3.0\n", encoding="utf-8")
    (repo / "docs" / "governance" / "ARCHITECT_SPEC_v3.0.0.md").write_text("# spec\n", encoding="utf-8")
    (repo / "docs" / "releases" / "2.3.0.md").write_text("# release\n", encoding="utf-8")
    (repo / "tests" / "test_one.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    (repo / "docs" / "manifest.txt").write_text(
        "\n".join(
            [
                "# ADAAD v2.3.0 — Repository Manifest",
                "# Human readers: start at docs/README.md",
                "# Governance spec: docs/governance/ARCHITECT_SPEC_v3.0.0.md",
                "VERSION                          — Canonical version string (2.3.0)",
                "Latest tagged release notes      — docs/releases/2.3.0.md",
                "tests/                           — Full test suite (1 Python files)",
                "  ARCHITECT_SPEC_v3.0.0.md       — CANONICAL architectural specification (v3.0.0)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return repo


def test_manifest_inventory_validator_passes_for_aligned_manifest(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"ok": true' in result.stdout


def test_manifest_inventory_validator_fails_for_drifted_version(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    (repo / "VERSION").write_text("2.3.1\n", encoding="utf-8")

    result = _run(repo)

    assert result.returncode == 1
    assert "manifest header version mismatch" in result.stdout
    assert "manifest root VERSION line mismatch" in result.stdout
