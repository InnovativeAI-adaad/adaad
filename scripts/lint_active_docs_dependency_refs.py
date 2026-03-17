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
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    findings: list[dict[str, object]] = []

    for doc_path in _iter_active_docs():
        findings.extend(_scan_file(doc_path))

    for doc_path in _iter_governance_docs():
        findings.extend(_scan_workflow_refs(doc_path))

    findings = sorted(findings, key=lambda item: (item["file"], item["line"], item["target"]))

    if args.format == "json":
        print(json.dumps({"validator": "active_docs_dependency_refs", "ok": not findings, "findings": findings}, sort_keys=True))
    else:
        if findings:
            for finding in findings:
                print(f"{finding['kind']}:{finding['file']}:{finding['line']}:{finding['target']}")
        else:
            print("active_docs_dependency_refs_ok")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
