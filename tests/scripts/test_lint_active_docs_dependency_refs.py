import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from scripts import lint_active_docs_dependency_refs as validator


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_workflow_refs_accepts_existing_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path / ".github/workflows/ci.yml", "name: CI\n")
    doc = tmp_path / "docs/governance/ci-gating.md"
    _write(doc, "Uses `.github/workflows/ci.yml`.\n")

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    findings = validator._scan_workflow_refs(doc)

    assert findings == []


def test_scan_workflow_refs_flags_missing_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = tmp_path / "docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md"
    _write(doc, "Legacy `.github/workflows/missing_gate.yml` must pass.\n")

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    findings = validator._scan_workflow_refs(doc)

    assert len(findings) == 1
    assert findings[0]["kind"] == "missing_workflow_file_reference"
    assert findings[0]["target"] == ".github/workflows/missing_gate.yml"


def test_resolve_targets_scoped_uses_changed_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = tmp_path / "README.md"
    _write(doc, "See requirements.dev.txt\n")
    changed = tmp_path / "changed.txt"
    _write(changed, "README.md\n")
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    targets, mode = validator._resolve_targets(str(changed))

    assert mode == "scoped"
    assert doc in targets


def test_governance_roots_match_docs_integrity_validator() -> None:
    from scripts.validate_docs_integrity import GOVERNANCE_ALWAYS_ROOTS as integrity_roots

    assert validator.GOVERNANCE_ALWAYS_ROOTS == integrity_roots
