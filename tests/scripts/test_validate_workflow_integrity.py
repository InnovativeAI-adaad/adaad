import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from scripts.validate_workflow_integrity import validate_workflow_integrity


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_validate_workflow_integrity_passes_for_canonical_codeql(tmp_path: Path) -> None:
    workflows = tmp_path / ".github/workflows"
    _write(workflows / "ci.yml", "name: CI\n")
    _write(workflows / "codeql.yml", "name: CodeQL\n")

    assert validate_workflow_integrity(workflows) == []


def test_validate_workflow_integrity_blocks_duplicate_names(tmp_path: Path) -> None:
    workflows = tmp_path / ".github/workflows"
    _write(workflows / "a.yml", "name: Duplicate Name\n")
    _write(workflows / "b.yml", "name: Duplicate Name\n")
    _write(workflows / "codeql.yml", "name: CodeQL\n")

    errors = validate_workflow_integrity(workflows)

    assert any("duplicate workflow name" in message for message in errors)


def test_validate_workflow_integrity_blocks_noncanonical_codeql_surface(tmp_path: Path) -> None:
    workflows = tmp_path / ".github/workflows"
    _write(workflows / "ci.yml", "name: CI\n")
    _write(workflows / "codeql.yml", "name: CodeQL\n")
    _write(workflows / "codeql1.yml", "name: CodeQL Alt\n")

    errors = validate_workflow_integrity(workflows)

    assert any("CodeQL workflow surface must be canonical" in message for message in errors)
