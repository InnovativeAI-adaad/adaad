# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import subprocess
import sys
from pathlib import Path


def _run_validator(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/validate_release_hardening_claims.py"],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_validator_fails_when_release_notes_overclaim_hardening(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "runtime" / "sandbox").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "releases").mkdir(parents=True, exist_ok=True)

    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_hardening_claims.py"
    (repo / "scripts" / "validate_release_hardening_claims.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    (repo / "runtime" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "runtime" / "sandbox" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "runtime" / "sandbox" / "isolation.py").write_text(
        "def runtime_hardening_capabilities(*, container_rollout_enabled: bool):\n"
        "    return {\n"
        "        'kernel_seccomp_filter_enforcement': {'implemented': False},\n"
        "        'namespace_cgroup_hard_isolation': {'implemented': False},\n"
        "    }\n",
        encoding="utf-8",
    )

    (repo / "docs" / "releases" / "1.0.0.md").write_text(
        "Kernel seccomp filter enforced in-kernel for all sandbox modes.\n",
        encoding="utf-8",
    )

    result = _run_validator(repo)
    assert result.returncode == 1
    assert "claims 'kernel_seccomp_filter_enforcement' hardening" in result.stdout


def test_validator_passes_when_no_overclaim(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "runtime" / "sandbox").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "releases").mkdir(parents=True, exist_ok=True)

    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_hardening_claims.py"
    (repo / "scripts" / "validate_release_hardening_claims.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    (repo / "runtime" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "runtime" / "sandbox" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "runtime" / "sandbox" / "isolation.py").write_text(
        "def runtime_hardening_capabilities(*, container_rollout_enabled: bool):\n"
        "    return {\n"
        "        'kernel_seccomp_filter_enforcement': {'implemented': False},\n"
        "        'namespace_cgroup_hard_isolation': {'implemented': False},\n"
        "    }\n",
        encoding="utf-8",
    )

    (repo / "docs" / "releases" / "1.0.0.md").write_text(
        "Sandbox hardening depth remains out-of-scope for this release.\n",
        encoding="utf-8",
    )

    result = _run_validator(repo)
    assert result.returncode == 0
