#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate claims-to-evidence matrix entries for release readiness."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

MATRIX_PATH = Path("docs/comms/claims_evidence_matrix.md")
CANONICAL_MATRIX_MARKER = "<!-- AUTHORITATIVE_EVIDENCE_MATRIX -->"
GOVERNANCE_DOCS_ROOT = Path("docs/governance")
DOCS_ROOT = Path("docs")
STALE_EVIDENCE_MATRIX_PATHS = (
    "docs/RELEASE_EVIDENCE_MATRIX.md",
    "../RELEASE_EVIDENCE_MATRIX.md",
    "RELEASE_EVIDENCE_MATRIX.md",
)
REQUIRED_CLAIM_IDS = {
    "ci-status-requirements",
    "replay-proof-outputs",
    "forensic-bundle-examples",
    "codeql-status",
    "versioned-docs-spec-links",
}
DISALLOWED_TOKENS = {"tbd", "todo", "coming soon"}
CLAIM_ID_CELL_PATTERN = re.compile(r"^`(?P<claim_id>[^`]+)`$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
EXPECTED_TABLE_COLUMNS = 5


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Fail unless all required claims are marked Complete.",
    )
    parser.add_argument(
        "--allow-external-links",
        action="store_true",
        help="Permit http/https evidence links during --require-complete validation.",
    )
    parser.add_argument(
        "--require-adversarial-summary",
        action="store_true",
        help="Require and validate deterministic adversarial scenario summary completeness.",
    )
    parser.add_argument(
        "--adversarial-summary-path",
        default="reports/security/adversarial_scenarios_summary.json",
        help="Path to operator-facing adversarial scenario summary artifact.",
    )
    return parser.parse_args()


def _is_http_link(link: str) -> bool:
    return link.startswith("http://") or link.startswith("https://")


def _normalize_local_target(link: str, base_dir: Path) -> Path:
    clean_link = link.split("#", 1)[0]
    return (base_dir / clean_link).resolve()


def _parse_version_triplet(raw: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", raw.strip())
    if not match:
        return None
    return tuple(int(match.group(i)) for i in (1, 2, 3))


def _parse_markdown_table_row(raw_line: str) -> list[str] | None:
    stripped = raw_line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped[1:-1]:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            current.append(char)
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)

    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())
    return cells


def _collect_authoritative_matrix_marker_errors() -> list[str]:
    if not DOCS_ROOT.exists():
        return []

    marker_locations: list[str] = []
    for markdown_file in sorted(DOCS_ROOT.rglob("*.md")):
        text = markdown_file.read_text(encoding="utf-8")
        if CANONICAL_MATRIX_MARKER in text:
            marker_locations.append(markdown_file.as_posix())

    expected = MATRIX_PATH.as_posix()
    if marker_locations != [expected]:
        discovered = ", ".join(marker_locations) if marker_locations else "<none>"
        return [
            "authoritative evidence matrix marker must appear exactly once at "
            f"{expected}; found: {discovered}"
        ]
    return []


def _collect_duplicate_authoritative_matrix_errors() -> list[str]:
    if not DOCS_ROOT.exists():
        return []

    duplicate_paths: list[str] = []
    canonical_heading = "# Claims-to-Evidence Matrix"

    for markdown_file in sorted(DOCS_ROOT.rglob("*.md")):
        if markdown_file == MATRIX_PATH:
            continue
        text = markdown_file.read_text(encoding="utf-8")
        if canonical_heading in text and "| Claim ID |" in text and "| Status |" in text:
            duplicate_paths.append(markdown_file.as_posix())
        if "Release Evidence Matrix" in text and "| Claim ID |" in text and "| Status |" in text:
            duplicate_paths.append(markdown_file.as_posix())

    if duplicate_paths:
        deduped = ", ".join(sorted(set(duplicate_paths)))
        return [
            "duplicate authoritative evidence matrix content detected outside canonical path: "
            f"{deduped}"
        ]
    return []


def _iter_release_note_versions(release_dir: Path) -> Iterable[tuple[int, int, int]]:
    if not release_dir.exists():
        return []
    versions: list[tuple[int, int, int]] = []
    for note_file in release_dir.glob("*.md"):
        parsed = _parse_version_triplet(note_file.stem)
        if parsed is not None:
            versions.append(parsed)
    return versions


def _collect_adversarial_summary_errors(path: Path) -> list[str]:
    if not path.exists():
        return [f"adversarial summary artifact is missing: {path.as_posix()}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"adversarial summary artifact is not valid JSON: {path.as_posix()} ({exc})"]

    errors: list[str] = []
    if payload.get("complete") is not True:
        errors.append("adversarial summary reports incomplete run (complete must be true)")

    rows = payload.get("results")
    if not isinstance(rows, list) or not rows:
        errors.append("adversarial summary results must be a non-empty list")
        return errors

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"adversarial summary row {idx} must be an object")
            continue
        for field in ("scenario_id", "expected_verdict", "actual_verdict", "evidence_pointers", "passed"):
            if field not in row:
                errors.append(f"adversarial summary row {idx} missing required field: {field}")
        pointers = row.get("evidence_pointers")
        if not isinstance(pointers, list) or not pointers:
            errors.append(f"adversarial summary row {idx} must include non-empty evidence_pointers")
    return errors


def main() -> int:
    args = _parse_args()

    if not MATRIX_PATH.exists():
        print(f"ERROR: missing matrix file: {MATRIX_PATH}")
        return 1

    errors: list[str] = []
    errors.extend(_collect_authoritative_matrix_marker_errors())
    errors.extend(_collect_duplicate_authoritative_matrix_errors())

    matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
    rows: dict[str, dict[str, str | list[str]]] = {}

    for line_number, line in enumerate(matrix_text.splitlines(), start=1):
        cells = _parse_markdown_table_row(line)
        if cells is None:
            continue
        if len(cells) != EXPECTED_TABLE_COLUMNS:
            errors.append(
                "matrix parse error at "
                f"line {line_number}: expected {EXPECTED_TABLE_COLUMNS} columns, "
                f"found {len(cells)} in row: {line.strip()}"
            )
            continue
        claim_match = CLAIM_ID_CELL_PATTERN.fullmatch(cells[0])
        if not claim_match:
            continue
        claim_id = claim_match.group("claim_id").strip()
        evidence_cell = cells[2]
        status_cell = cells[4]
        links = MARKDOWN_LINK_PATTERN.findall(evidence_cell)
        rows[claim_id] = {"status": status_cell, "links": links, "evidence": evidence_cell}

    version_path = Path("VERSION")
    release_dir = Path("docs/releases")

    if version_path.exists():
        version_raw = version_path.read_text(encoding="utf-8").strip()
        version_triplet = _parse_version_triplet(version_raw)
        if version_triplet is None:
            errors.append(f"invalid VERSION format: {version_raw!r}; expected MAJOR.MINOR.PATCH")
        else:
            release_versions = list(_iter_release_note_versions(release_dir))
            if not release_versions:
                errors.append(f"no semantic release note files found in {release_dir.as_posix()}")
            else:
                latest_release_version = max(release_versions)
                if version_triplet > latest_release_version:
                    latest_str = ".".join(str(x) for x in latest_release_version)
                    errors.append(
                        "VERSION exceeds latest release note file: "
                        f"VERSION={version_raw} > docs/releases/{latest_str}.md"
                    )

    if args.require_adversarial_summary:
        errors.extend(_collect_adversarial_summary_errors(Path(args.adversarial_summary_path)))

    missing_claims = REQUIRED_CLAIM_IDS - rows.keys()
    if missing_claims:
        errors.append(f"missing required claims: {', '.join(sorted(missing_claims))}")

    if GOVERNANCE_DOCS_ROOT.exists():
        for governance_doc in sorted(GOVERNANCE_DOCS_ROOT.rglob("*.md")):
            text = governance_doc.read_text(encoding="utf-8")
            stale_matches = [path for path in STALE_EVIDENCE_MATRIX_PATHS if path in text]
            if stale_matches:
                stale_csv = ", ".join(sorted(stale_matches))
                errors.append(
                    f"{governance_doc.as_posix()}: stale evidence matrix path reference(s): {stale_csv}; "
                    f"use {MATRIX_PATH.as_posix()}"
                )

    repo_root = Path.cwd().resolve()
    matrix_dir = MATRIX_PATH.parent.resolve()

    claim_ids_to_validate = sorted(rows.keys()) if args.require_complete else sorted(REQUIRED_CLAIM_IDS & rows.keys())

    for claim_id in claim_ids_to_validate:
        row = rows[claim_id]
        status = str(row["status"]).strip()
        evidence_cell = str(row["evidence"]).lower()
        links = [str(link).strip() for link in row["links"]]

        if not links:
            errors.append(f"{claim_id}: missing evidence links")

        for token in DISALLOWED_TOKENS:
            if token in evidence_cell:
                errors.append(f"{claim_id}: evidence contains placeholder token '{token}'")

        if args.require_complete and status != "Complete":
            errors.append(f"{claim_id}: status must be 'Complete' (found '{status}')")

        for link in links:
            if _is_http_link(link):
                if args.require_complete and not args.allow_external_links:
                    errors.append(f"{claim_id}: external links are not allowed with --require-complete: {link}")
                continue
            target = _normalize_local_target(link, matrix_dir)
            try:
                target.relative_to(repo_root)
            except ValueError:
                errors.append(f"{claim_id}: link escapes repository root: {link}")
                continue
            if not target.exists():
                errors.append(f"{claim_id}: missing linked artifact: {link}")

    if errors:
        print("Release evidence validation failed:")
        for err in errors:
            print(f" - {err}")
        return 1

    print("Release evidence validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
