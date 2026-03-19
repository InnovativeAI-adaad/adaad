#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_DOC_PATHS = [
    "README.md",
    "QUICKSTART.md",
    "docs/*.md",
    "docs/governance/*.md",
]
GOVERNANCE_DOC_PATHS = [
    "docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md",
    "docs/governance/*.md",
]
REQ_FILE_PATTERN = re.compile(r"requirements[^\s'\"`]*\.txt")
WORKFLOW_REF_PATTERN = re.compile(r"\.github/workflows/[A-Za-z0-9._/-]+\.ya?ml")

try:
    from validate_docs_integrity import GOVERNANCE_ALWAYS_ROOTS, SCOPED_DOC_EXTENSIONS, _fatal
except ImportError:  # pragma: no cover
    GOVERNANCE_ALWAYS_ROOTS = frozenset(
        {
            "docs/governance",
            "docs/comms",
            "docs/release",
            "docs/releases",
        }
    )
    SCOPED_DOC_EXTENSIONS = frozenset({".md", ".html", ".svg", ".txt", ".rst"})

    def _fatal(code: str, message: str) -> None:
        print(json.dumps({"event": code, "message": message}, sort_keys=True))
        raise SystemExit(1)


def _iter_active_docs() -> list[Path]:
    files: set[Path] = set()
    for pattern in ACTIVE_DOC_PATHS:
        files.update((ROOT / ".").glob(pattern))
    return sorted(path for path in files if path.is_file())


def _scan_file(path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for match in REQ_FILE_PATTERN.finditer(line):
            requirement_ref = match.group(0)
            if any(ch in requirement_ref for ch in "*?[]"):
                continue
            target = ROOT / requirement_ref
            if not target.exists():
                findings.append(
                    {
                        "kind": "missing_dependency_file_reference",
                        "file": str(path.relative_to(ROOT)),
                        "line": line_number,
                        "target": requirement_ref,
                    }
                )
    return findings


def _iter_governance_docs() -> list[Path]:
    files: set[Path] = set()
    for pattern in GOVERNANCE_DOC_PATHS:
        files.update((ROOT / ".").glob(pattern))
    return sorted(path for path in files if path.is_file())


def _scan_workflow_refs(path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for match in WORKFLOW_REF_PATTERN.finditer(line):
            workflow_ref = match.group(0)
            target = ROOT / workflow_ref
            if not target.exists():
                findings.append(
                    {
                        "kind": "missing_workflow_file_reference",
                        "file": str(path.relative_to(ROOT)),
                        "line": line_number,
                        "target": workflow_ref,
                    }
                )
    return findings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail if active documentation references nonexistent dependency requirement files."
    )
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument("--changed-files", default=None, help="Optional newline-delimited changed-files list for scoped validation.")
    return parser


def _resolve_targets(changed_files: str | None) -> tuple[list[Path], str]:
    if changed_files is None:
        return sorted(set(_iter_active_docs()) | set(_iter_governance_docs())), "full"

    cf_path = Path(changed_files)
    if not cf_path.exists():
        _fatal("LINT_DEPS_ERROR_CHANGED_FILES_MISSING", f"--changed-files path does not exist: {cf_path}")

    try:
        lines = cf_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fatal("LINT_DEPS_ERROR_CHANGED_FILES_READ", str(exc))

    targets: set[Path] = set()
    governance_roots_to_expand: set[str] = set()

    for raw_line in lines:
        rel = raw_line.strip()
        if not rel:
            continue
        normalized = rel.replace("\\", "/")
        candidate = (ROOT / normalized).resolve()
        if candidate.suffix.lower() not in SCOPED_DOC_EXTENSIONS:
            continue

        if candidate.exists() and candidate.suffix.lower() == ".md":
            targets.add(candidate)

        for root in GOVERNANCE_ALWAYS_ROOTS:
            if normalized == root or normalized.startswith(f"{root}/"):
                governance_roots_to_expand.add(root)
                break

    if governance_roots_to_expand:
        for path in _iter_governance_docs():
            rel = path.relative_to(ROOT).as_posix()
            if any(rel == root or rel.startswith(f"{root}/") for root in governance_roots_to_expand):
                targets.add(path)

    if not targets:
        return [], "empty-scoped"

    mode = "scoped+gov-always" if governance_roots_to_expand else "scoped"
    return sorted(targets), mode


def main() -> int:
    args = _build_parser().parse_args()
    findings: list[dict[str, object]] = []
    targets, mode = _resolve_targets(args.changed_files)
    governance_docs = set(_iter_governance_docs())

    if mode == "empty-scoped":
        if args.format == "json":
            print(json.dumps({"event": "lint_start", "mode": mode, "target_count": 0}, sort_keys=True))
            print(json.dumps({"event": "lint_complete", "mode": mode, "files_checked": 0, "errors": 0}, sort_keys=True))
        else:
            print("active_docs_dependency_refs_ok")
        return 0

    for doc_path in targets:
        findings.extend(_scan_file(doc_path))
        if doc_path in governance_docs:
            findings.extend(_scan_workflow_refs(doc_path))

    findings = sorted(findings, key=lambda item: (item["file"], item["line"], item["target"]))

    if args.format == "json":
        print(json.dumps({"event": "lint_start", "mode": mode, "target_count": len(targets)}, sort_keys=True))
        print(json.dumps({"validator": "active_docs_dependency_refs", "ok": not findings, "findings": findings}, sort_keys=True))
        print(json.dumps({"event": "lint_complete", "mode": mode, "files_checked": len(targets), "errors": len(findings)}, sort_keys=True))
    else:
        if findings:
            for finding in findings:
                print(f"{finding['kind']}:{finding['file']}:{finding['line']}:{finding['target']}")
        else:
            print("active_docs_dependency_refs_ok")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
