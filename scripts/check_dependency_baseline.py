#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify pinned dependency parity between runtime and archived backend requirements.

This script resolves requirement file paths relative to the repository root so it can
be executed from any current working directory.
"""

from __future__ import annotations

import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_REQUIREMENTS = REPO_ROOT / "requirements.server.txt"
ARCHIVE_REQUIREMENTS = REPO_ROOT / "archives/backend/requirements.txt"
PACKAGES_TO_MATCH = ("fastapi", "uvicorn", "anthropic")


def _parse_requirements(path: pathlib.Path) -> tuple[dict[str, str], dict[str, str]]:
    """Return exact pins and tracked package specifier violations for a requirements file."""
    pins: dict[str, str] = {}
    violations: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for package in PACKAGES_TO_MATCH:
            if line.startswith(f"{package}=="):
                pins[package] = line.split("==", 1)[1].strip()
                break
            if line.startswith(f"{package}") and not line.startswith(f"{package}=="):
                violations[package] = line
                break
    return pins, violations


def _validate_file_exists(path: pathlib.Path) -> str | None:
    if path.exists():
        return None
    return f"missing requirements file: {path}"


def main() -> int:
    issues: list[str] = []
    for path in (RUNTIME_REQUIREMENTS, ARCHIVE_REQUIREMENTS):
        missing = _validate_file_exists(path)
        if missing:
            issues.append(missing)

    if issues:
        print("Dependency baseline validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    runtime_pins, runtime_violations = _parse_requirements(RUNTIME_REQUIREMENTS)
    archive_pins, archive_violations = _parse_requirements(ARCHIVE_REQUIREMENTS)

    for package, line in runtime_violations.items():
        issues.append(f"runtime file must pin {package} with '==': found {line!r}")
    for package, line in archive_violations.items():
        issues.append(f"archive file must pin {package} with '==': found {line!r}")

    for package in PACKAGES_TO_MATCH:
        runtime_version = runtime_pins.get(package)
        archive_version = archive_pins.get(package)
        if runtime_version is None:
            issues.append(
                f"runtime file missing required pin for {package}: {RUNTIME_REQUIREMENTS}"
            )
            continue
        if archive_version is None:
            issues.append(
                f"archive file missing required pin for {package}: {ARCHIVE_REQUIREMENTS}"
            )
            continue
        if runtime_version != archive_version:
            issues.append(
                f"{package} mismatch: runtime={runtime_version!r}, archive={archive_version!r}"
            )

    if issues:
        print("Dependency baseline mismatch detected:")
        for issue in issues:
            print(f"- {issue}")
        print(
            "Expected archives/backend/requirements.txt to mirror the pinned "
            "runtime baseline for fastapi/uvicorn/anthropic."
        )
        return 1

    print(
        "Dependency baseline check passed: archives/backend/requirements.txt "
        "matches requirements.server.txt for fastapi/uvicorn/anthropic."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
