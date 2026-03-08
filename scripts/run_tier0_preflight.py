#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run ADAAD Tier 0 gates with fail-closed handling for missing commands."""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    name: str
    command: str
    mandatory: bool = True
    skip_if_missing: bool = False


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


def _command_exists(command: str) -> bool:
    first_token = shlex.split(command)[0]
    return shutil.which(first_token) is not None


def _run_check(check: Check, check_only: bool) -> CheckResult:
    if not _command_exists(check.command):
        if check.skip_if_missing and not check.mandatory:
            return CheckResult(check.name, "skipped", f"diagnostic-only missing dependency: {check.command}")
        return CheckResult(check.name, "blocked", f"required command/script missing: {check.command}")

    if check_only:
        return CheckResult(check.name, "skipped", "diagnostic mode (--check-only): command execution skipped")

    completed = subprocess.run(check.command, shell=True, check=False)
    if completed.returncode == 0:
        return CheckResult(check.name, "passed", "ok")
    return CheckResult(check.name, "blocked", f"non-zero exit: {completed.returncode}")


def _print_summary(results: list[CheckResult]) -> None:
    passed = [r for r in results if r.status == "passed"]
    skipped = [r for r in results if r.status == "skipped"]
    blocked = [r for r in results if r.status == "blocked"]

    print("\nTier 0 summary")
    print("passed checks:")
    for item in passed:
        print(f"  - {item.name}: {item.detail}")
    if not passed:
        print("  - (none)")

    print("skipped (diagnostic only):")
    for item in skipped:
        print(f"  - {item.name}: {item.detail}")
    if not skipped:
        print("  - (none)")

    print("blocked/incomplete gate:")
    for item in blocked:
        print(f"  - {item.name}: {item.detail}")
    if not blocked:
        print("  - (none)")

    if blocked:
        print("[ADAAD BLOCKED] one or more Tier 0 gates are incomplete/blocked.")
    elif skipped:
        print("Tier 0 diagnostic complete (not full green: checks were skipped).")
    else:
        print("Tier 0 green: all mandatory checks passed.")


def build_checks(include_tests: bool) -> list[Check]:
    checks = [
        Check("schema validation", "python scripts/validate_governance_schemas.py"),
        Check("architecture snapshot", "python scripts/validate_architecture_snapshot.py"),
        Check(
            "determinism lint",
            "python tools/lint_determinism.py runtime/ security/ adaad/orchestrator/ app/main.py",
        ),
        Check("import boundary lint", "python tools/lint_import_paths.py"),
    ]
    if include_tests:
        checks.append(
            Check(
                "fast confidence tests",
                'PYTHONPATH=. pytest tests/determinism/ tests/recovery/test_tier_manager.py -k "not shared_epoch_parallel_validation_is_deterministic_in_strict_mode" -q',
            )
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="diagnostic mode; do not execute commands")
    parser.add_argument("--no-tests", action="store_true", help="omit the test gate (allowed only with --check-only)")
    args = parser.parse_args()

    if args.no_tests and not args.check_only:
        print("[ADAAD BLOCKED] --no-tests is restricted to diagnostic mode; rerun with --check-only.")
        return 2

    checks = build_checks(include_tests=not args.no_tests)
    results = [_run_check(check, check_only=args.check_only) for check in checks]

    if args.no_tests and args.check_only:
        results.append(CheckResult("fast confidence tests", "skipped", "diagnostic-only skip requested via --no-tests"))

    _print_summary(results)
    return 1 if any(r.status == "blocked" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
