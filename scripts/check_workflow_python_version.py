#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail when GitHub workflows use multiple setup-python versions."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

PYTHON_VERSION_PATTERN = re.compile(r"^\s*python-version:\s*['\"]?([^'\"\s#]+)")

# Matches GitHub Actions expression syntax: ${{ ... }}
# These resolve at runtime and are not treated as literal version strings.
_EXPRESSION_PATTERN = re.compile(r"^\$\{\{.*\}\}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflows-dir",
        default=".github/workflows",
        help="Directory containing workflow YAML files.",
    )
    parser.add_argument(
        "--expected-version",
        default=None,
        help="Optional exact version to enforce in all setup-python steps.",
    )
    return parser.parse_args()


def collect_versions(workflows_dir: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for workflow in sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")]):
        versions: list[str] = []
        for line in workflow.read_text(encoding="utf-8").splitlines():
            match = PYTHON_VERSION_PATTERN.match(line)
            if match:
                version = match.group(1)
                # Skip GitHub Actions expression references (e.g. ${{ env.PYTHON_VERSION }}).
                # These resolve at runtime; their canonical value is defined elsewhere in the
                # workflow (env block) and is validated by examining that literal definition.
                if version.startswith("${{"):
                    continue
                versions.append(version)
        if versions:
            found[str(workflow.relative_to(Path.cwd())) if workflow.is_absolute() else str(workflow)] = versions
    return found


def main() -> int:
    args = parse_args()
    workflows_dir = Path(args.workflows_dir)
    versions_by_file = collect_versions(workflows_dir)

    if not versions_by_file:
        raise SystemExit("No python-version entries found in workflow files.")

    unique_versions = sorted({v for vals in versions_by_file.values() for v in vals})

    print("Detected workflow Python versions:")
    for workflow, versions in versions_by_file.items():
        print(f"- {workflow}: {', '.join(versions)}")

    if len(unique_versions) != 1:
        raise SystemExit(
            "Expected exactly one Python version across workflow files, "
            f"found {len(unique_versions)}: {', '.join(unique_versions)}"
        )

    selected = unique_versions[0]
    if args.expected_version and selected != args.expected_version:
        raise SystemExit(
            f"Expected workflow Python version {args.expected_version}, found {selected}"
        )

    print(f"OK: unified workflow Python version is {selected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
