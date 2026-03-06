# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_validator(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/validate_release_evidence.py", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_matrix(repo: Path, body: str) -> None:
    matrix = repo / "docs" / "comms" / "claims_evidence_matrix.md"
    matrix.parent.mkdir(parents=True, exist_ok=True)
    normalized = body
    if "<!-- AUTHORITATIVE_EVIDENCE_MATRIX -->" not in normalized:
        normalized = "<!-- AUTHORITATIVE_EVIDENCE_MATRIX -->\n" + normalized
    matrix.write_text(normalized, encoding="utf-8")


def _seed_links(repo: Path) -> None:
    (repo / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (repo / ".github" / "workflows" / "determinism_lint.yml").write_text("name: lint\n", encoding="utf-8")
    (repo / ".github" / "workflows" / "codeql.yml").write_text("name: codeql\n", encoding="utf-8")
    (repo / "tests" / "determinism").mkdir(parents=True, exist_ok=True)
    (repo / "tests" / "determinism" / "README.md").write_text("ok\n", encoding="utf-8")
    (repo / "docs" / "governance").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "governance" / "APONI_V2_FORENSICS_AND_HEALTH_MODEL.md").write_text("ok\n", encoding="utf-8")
    (repo / "docs" / "governance" / "FORENSIC_BUNDLE_LIFECYCLE.md").write_text("ok\n", encoding="utf-8")
    (repo / "docs" / "governance" / "schema_versioning_and_migration.md").write_text("ok\n", encoding="utf-8")
    (repo / "docs" / "releases").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "releases" / "1.0.0.md").write_text("ok\n", encoding="utf-8")


def test_require_complete_validates_non_required_rows(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_evidence.py"
    (repo / "scripts" / "validate_release_evidence.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _seed_links(repo)

    _write_matrix(
        repo,
        """
| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |
| --- | --- | --- | --- |
| `ci-status-requirements` | x | [ci](../../.github/workflows/ci.yml) | Complete |
| `replay-proof-outputs` | x | [det](../../tests/determinism) | Complete |
| `forensic-bundle-examples` | x | [for](../governance/FORENSIC_BUNDLE_LIFECYCLE.md) | Complete |
| `codeql-status` | x | [codeql](../../.github/workflows/codeql.yml) | Complete |
| `versioned-docs-spec-links` | x | [spec](../governance/schema_versioning_and_migration.md) | Complete |
| `extra-claim` | x | [missing](../releases/does-not-exist.md) | Complete |
""".strip()
        + "\n",
    )

    result = _run_validator(repo, "--require-complete")

    assert result.returncode == 1
    assert "extra-claim: missing linked artifact" in result.stdout


def test_default_mode_only_enforces_required_claims(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_evidence.py"
    (repo / "scripts" / "validate_release_evidence.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _seed_links(repo)

    _write_matrix(
        repo,
        """
| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |
| --- | --- | --- | --- |
| `ci-status-requirements` | x | [ci](../../.github/workflows/ci.yml) | Complete |
| `replay-proof-outputs` | x | [det](../../tests/determinism) | Complete |
| `forensic-bundle-examples` | x | [for](../governance/FORENSIC_BUNDLE_LIFECYCLE.md) | Complete |
| `codeql-status` | x | [codeql](../../.github/workflows/codeql.yml) | Complete |
| `versioned-docs-spec-links` | x | [spec](../governance/schema_versioning_and_migration.md) | Complete |
| `extra-claim` | x | [missing](../releases/does-not-exist.md) | Complete |
""".strip()
        + "\n",
    )

    result = _run_validator(repo)

    assert result.returncode == 0


def test_require_complete_rejects_external_links_by_default(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_evidence.py"
    (repo / "scripts" / "validate_release_evidence.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _seed_links(repo)

    _write_matrix(
        repo,
        """
| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |
| --- | --- | --- | --- |
| `ci-status-requirements` | x | [ci](../../.github/workflows/ci.yml) | Complete |
| `replay-proof-outputs` | x | [det](../../tests/determinism) | Complete |
| `forensic-bundle-examples` | x | [for](../governance/FORENSIC_BUNDLE_LIFECYCLE.md) | Complete |
| `codeql-status` | x | [codeql](../../.github/workflows/codeql.yml) | Complete |
| `versioned-docs-spec-links` | x | [spec](../governance/schema_versioning_and_migration.md), [external](https://example.com/spec) | Complete |
""".strip()
        + "\n",
    )

    result = _run_validator(repo, "--require-complete")

    assert result.returncode == 1
    assert "external links are not allowed with --require-complete" in result.stdout


def test_require_complete_allows_external_links_with_opt_in(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_evidence.py"
    (repo / "scripts" / "validate_release_evidence.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _seed_links(repo)

    _write_matrix(
        repo,
        """
| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |
| --- | --- | --- | --- |
| `ci-status-requirements` | x | [ci](../../.github/workflows/ci.yml) | Complete |
| `replay-proof-outputs` | x | [det](../../tests/determinism) | Complete |
| `forensic-bundle-examples` | x | [for](../governance/FORENSIC_BUNDLE_LIFECYCLE.md) | Complete |
| `codeql-status` | x | [codeql](../../.github/workflows/codeql.yml) | Complete |
| `versioned-docs-spec-links` | x | [spec](../governance/schema_versioning_and_migration.md), [external](https://example.com/spec) | Complete |
""".strip()
        + "\n",
    )

    result = _run_validator(repo, "--require-complete", "--allow-external-links")

    assert result.returncode == 0



def test_governance_docs_reject_stale_evidence_matrix_links(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_evidence.py"
    (repo / "scripts" / "validate_release_evidence.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _seed_links(repo)

    stale_doc = repo / "docs" / "governance" / "ADAAD_7_GA_CLOSURE_TRACKER.md"
    stale_doc.write_text("Release evidence matrix: ../RELEASE_EVIDENCE_MATRIX.md\n", encoding="utf-8")

    _write_matrix(
        repo,
        """
| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |
| --- | --- | --- | --- |
| `ci-status-requirements` | x | [ci](../../.github/workflows/ci.yml) | Complete |
| `replay-proof-outputs` | x | [det](../../tests/determinism) | Complete |
| `forensic-bundle-examples` | x | [for](../governance/FORENSIC_BUNDLE_LIFECYCLE.md) | Complete |
| `codeql-status` | x | [codeql](../../.github/workflows/codeql.yml) | Complete |
| `versioned-docs-spec-links` | x | [spec](../governance/schema_versioning_and_migration.md) | Complete |
""".strip()
        + "\n",
    )

    result = _run_validator(repo)

    assert result.returncode == 1
    assert "stale evidence matrix path reference" in result.stdout


def _seed_version(repo: Path, value: str) -> None:
    (repo / "VERSION").write_text(f"{value}\n", encoding="utf-8")


def test_validator_fails_when_version_exceeds_latest_release_note(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_evidence.py"
    (repo / "scripts" / "validate_release_evidence.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _seed_links(repo)
    _seed_version(repo, "9.9.9")

    _write_matrix(
        repo,
        """
| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |
| --- | --- | --- | --- |
| `ci-status-requirements` | x | [ci](../../.github/workflows/ci.yml) | Complete |
| `replay-proof-outputs` | x | [det](../../tests/determinism) | Complete |
| `forensic-bundle-examples` | x | [for](../governance/FORENSIC_BUNDLE_LIFECYCLE.md) | Complete |
| `codeql-status` | x | [codeql](../../.github/workflows/codeql.yml) | Complete |
| `versioned-docs-spec-links` | x | [spec](../governance/schema_versioning_and_migration.md) | Complete |
""".strip()
        + "\n",
    )

    result = _run_validator(repo)

    assert result.returncode == 1
    assert "VERSION exceeds latest release note file" in result.stdout


def test_validator_accepts_version_equal_to_latest_release_note(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_evidence.py"
    (repo / "scripts" / "validate_release_evidence.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _seed_links(repo)
    _seed_version(repo, "1.0.0")

    _write_matrix(
        repo,
        """
| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |
| --- | --- | --- | --- |
| `ci-status-requirements` | x | [ci](../../.github/workflows/ci.yml) | Complete |
| `replay-proof-outputs` | x | [det](../../tests/determinism) | Complete |
| `forensic-bundle-examples` | x | [for](../governance/FORENSIC_BUNDLE_LIFECYCLE.md) | Complete |
| `codeql-status` | x | [codeql](../../.github/workflows/codeql.yml) | Complete |
| `versioned-docs-spec-links` | x | [spec](../governance/schema_versioning_and_migration.md) | Complete |
""".strip()
        + "\n",
    )

    result = _run_validator(repo)

    assert result.returncode == 0


def test_validator_rejects_duplicate_authoritative_matrix(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_evidence.py"
    (repo / "scripts" / "validate_release_evidence.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _seed_links(repo)

    duplicate = repo / "docs" / "RELEASE_EVIDENCE_MATRIX.md"
    duplicate.parent.mkdir(parents=True, exist_ok=True)
    duplicate.write_text(
        "# Claims-to-Evidence Matrix\n\n| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |\n",
        encoding="utf-8",
    )

    _write_matrix(
        repo,
        """
| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |
| --- | --- | --- | --- |
| `ci-status-requirements` | x | [ci](../../.github/workflows/ci.yml) | Complete |
| `replay-proof-outputs` | x | [det](../../tests/determinism) | Complete |
| `forensic-bundle-examples` | x | [for](../governance/FORENSIC_BUNDLE_LIFECYCLE.md) | Complete |
| `codeql-status` | x | [codeql](../../.github/workflows/codeql.yml) | Complete |
| `versioned-docs-spec-links` | x | [spec](../governance/schema_versioning_and_migration.md) | Complete |
""".strip()
        + "\n",
    )

    result = _run_validator(repo)

    assert result.returncode == 1
    assert "duplicate authoritative evidence matrix content detected" in result.stdout


def test_validator_rejects_missing_authoritative_marker(tmp_path: Path) -> None:
    repo = tmp_path
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_evidence.py"
    (repo / "scripts" / "validate_release_evidence.py").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _seed_links(repo)

    matrix = repo / "docs" / "comms" / "claims_evidence_matrix.md"
    matrix.parent.mkdir(parents=True, exist_ok=True)
    matrix.write_text(
        """
| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |
| --- | --- | --- | --- |
| `ci-status-requirements` | x | [ci](../../.github/workflows/ci.yml) | Complete |
| `replay-proof-outputs` | x | [det](../../tests/determinism) | Complete |
| `forensic-bundle-examples` | x | [for](../governance/FORENSIC_BUNDLE_LIFECYCLE.md) | Complete |
| `codeql-status` | x | [codeql](../../.github/workflows/codeql.yml) | Complete |
| `versioned-docs-spec-links` | x | [spec](../governance/schema_versioning_and_migration.md) | Complete |
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = _run_validator(repo)

    assert result.returncode == 1
    assert "authoritative evidence matrix marker must appear exactly once" in result.stdout
