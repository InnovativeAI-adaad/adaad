# SPDX-License-Identifier: Apache-2.0
"""Fail-closed validator for GitHub workflow integrity invariants."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_NAME_PATTERN = re.compile(r"^name\s*:\s*(.+?)\s*$", re.MULTILINE)


def _extract_workflow_name(content: str) -> str | None:
    match = _NAME_PATTERN.search(content)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def validate_workflow_integrity(workflows_dir: Path) -> list[str]:
    errors: list[str] = []
    if not workflows_dir.exists():
        return [f"workflows directory not found: {workflows_dir}"]

    workflow_paths = sorted(
        [
            *workflows_dir.glob("*.yml"),
            *workflows_dir.glob("*.yaml"),
        ]
    )
    if not workflow_paths:
        return [f"no workflow files found in {workflows_dir}"]

    names_seen: dict[str, Path] = {}
    for path in workflow_paths:
        name = _extract_workflow_name(path.read_text(encoding="utf-8"))
        if not name:
            errors.append(f"{path.as_posix()}: missing top-level workflow name")
            continue
        if name in names_seen:
            first = names_seen[name]
            errors.append(
                f"duplicate workflow name '{name}' in {first.as_posix()} and {path.as_posix()}"
            )
        else:
            names_seen[name] = path

    codeql_candidates = sorted(path.name for path in workflow_paths if path.name.startswith("codeql"))
    if codeql_candidates != ["codeql.yml"]:
        errors.append(
            "CodeQL workflow surface must be canonical: expected only '.github/workflows/codeql.yml', "
            f"found {codeql_candidates!r}"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate workflow integrity invariants.")
    parser.add_argument(
        "--workflows-dir",
        type=Path,
        default=Path(".github/workflows"),
        help="Path containing GitHub workflow files.",
    )
    args = parser.parse_args()

    errors = validate_workflow_integrity(args.workflows_dir)
    if errors:
        print("[ADAAD BLOCKED] workflow integrity validation failed")
        for error in errors:
            print(f" - {error}")
        return 1

    print("workflow integrity validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

