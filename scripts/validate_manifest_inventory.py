#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "manifest.txt"
VERSION_PATH = ROOT / "VERSION"
RELEASES_DIR = ROOT / "docs" / "releases"
CANONICAL_SPEC_PATH = "docs/governance/ARCHITECT_SPEC_v3.1.0.md"

HEADER_VERSION_RE = re.compile(r"^# ADAAD v(?P<version>\d+\.\d+\.\d+) — Repository Manifest$")
HEADER_SPEC_RE = re.compile(r"^# Governance spec: (?P<path>\S+)$")
ROOT_VERSION_RE = re.compile(r"^VERSION\s+— Canonical version string \((?P<version>\d+\.\d+\.\d+)\)$")
LATEST_RELEASE_RE = re.compile(r"^Latest tagged release notes\s+— (?P<path>docs/releases/\d+\.\d+\.\d+\.md)$")
TEST_COUNT_RE = re.compile(r"^tests/\s+— Full test suite \((?P<count>\d+) Python files\)$")
CANONICAL_SPEC_LINE_RE = re.compile(r"^\s+ARCHITECT_SPEC_v3\.1\.0\.md\s+— CANONICAL architectural specification \(v3\.1\.0\)$")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _parse_semver(raw: str) -> tuple[int, int, int] | None:
    match = SEMVER_RE.fullmatch(raw.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _latest_release() -> str | None:
    versions: list[tuple[int, int, int]] = []
    for candidate in RELEASES_DIR.glob("*.md"):
        parsed = _parse_semver(candidate.stem)
        if parsed is not None:
            versions.append(parsed)
    if not versions:
        return None
    return ".".join(str(part) for part in max(versions))


def _expected_pytest_file_count() -> int:
    return sum(1 for _ in (ROOT / "tests").rglob("*.py"))


def _find_first_match(pattern: re.Pattern[str], lines: list[str]) -> str | None:
    for line in lines:
        match = pattern.fullmatch(line.rstrip("\n"))
        if match:
            return match.groupdict().get("version") or match.groupdict().get("path") or match.groupdict().get("count")
    return None


def _contains_exact_line(pattern: re.Pattern[str], lines: list[str]) -> bool:
    for line in lines:
        if pattern.fullmatch(line.rstrip("\n")):
            return True
    return False


def validate_manifest() -> list[str]:
    errors: list[str] = []

    if not MANIFEST_PATH.exists():
        return ["missing docs/manifest.txt"]
    if not VERSION_PATH.exists():
        return ["missing VERSION"]

    manifest_lines = MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
    version = VERSION_PATH.read_text(encoding="utf-8").strip()

    if _parse_semver(version) is None:
        errors.append(f"invalid VERSION format: {version!r}")
        return errors

    header_version = _find_first_match(HEADER_VERSION_RE, manifest_lines)
    if header_version != version:
        errors.append(f"manifest header version mismatch: expected {version}, found {header_version}")

    root_version = _find_first_match(ROOT_VERSION_RE, manifest_lines)
    if root_version != version:
        errors.append(f"manifest root VERSION line mismatch: expected {version}, found {root_version}")

    header_spec = _find_first_match(HEADER_SPEC_RE, manifest_lines)
    if header_spec != CANONICAL_SPEC_PATH:
        errors.append(
            f"manifest governance spec mismatch: expected {CANONICAL_SPEC_PATH}, found {header_spec}"
        )

    if not _contains_exact_line(CANONICAL_SPEC_LINE_RE, manifest_lines):
        errors.append("manifest canonical spec inventory entry missing or drifted: ARCHITECT_SPEC_v3.1.0.md")

    latest_release = _latest_release()
    if latest_release is None:
        errors.append("unable to determine latest release from docs/releases/*.md")
    else:
        latest_release_line = _find_first_match(LATEST_RELEASE_RE, manifest_lines)
        expected_release_path = f"docs/releases/{latest_release}.md"
        if latest_release_line != expected_release_path:
            errors.append(
                "manifest latest release notes line mismatch: "
                f"expected {expected_release_path}, found {latest_release_line}"
            )

    declared_test_count = _find_first_match(TEST_COUNT_RE, manifest_lines)
    expected_test_count = str(_expected_pytest_file_count())
    if declared_test_count != expected_test_count:
        errors.append(
            f"manifest test file count mismatch: expected {expected_test_count}, found {declared_test_count}"
        )

    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate docs/manifest.txt against repository truth.")
    parser.add_argument("--format", choices=("text", "json"), default="json")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    errors = validate_manifest()

    if args.format == "json":
        print(json.dumps({"validator": "manifest_inventory", "ok": not errors, "errors": errors}, sort_keys=True))
    else:
        if errors:
            for error in errors:
                print(error)
        else:
            print("manifest_inventory_ok")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
