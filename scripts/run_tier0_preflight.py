#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run ADAAD Tier 0 gates with fail-closed handling for missing commands."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.tools.execution_contract import (
    ToolExecutionRequest,
    execute_tool_request,
    lint_check_request,
    test_check_request,
)
from adaad.orchestrator.remediation import format_blocked_state, gate_id_for_tier0_check


TEST_MODE_ENV_VARS = ("ADAAD_TEST_MODE", "PYTEST_CURRENT_TEST")
TEST_EXTRAS = ("cryptography", "pytest_benchmark")


def _test_mode_enabled() -> bool:
    return any(os.getenv(name, "").strip() for name in TEST_MODE_ENV_VARS)


def _missing_test_extras() -> list[str]:
    missing: list[str] = []
    for module_name in TEST_EXTRAS:
        try:
            __import__(module_name)
        except ModuleNotFoundError:
            missing.append(module_name)
    return missing


@dataclass(frozen=True)
class Check:
    name: str
    request: ToolExecutionRequest | None = None
    command: str = ""
    skip_if_missing: bool = False
    mandatory: bool = True

    def __post_init__(self) -> None:
        if self.request is not None:
            return
        if not self.command.strip():
            raise ValueError("check_requires_request_or_command")
        command_parts = tuple(shlex.split(self.command))
        object.__setattr__(
            self,
            "request",
            lint_check_request(tool_id=f"tier0-compat-{self.name.replace(' ', '-').lower()}", command=command_parts),
        )


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


def _run_check(check: Check, check_only: bool) -> CheckResult:
    if check_only:
        return CheckResult(check.name, "skipped", "diagnostic mode (--check-only): command execution skipped")

    result = execute_tool_request(check.request)
    if result.status == "passed":
        return CheckResult(check.name, "passed", "ok")
    if result.status == "missing_dependency":
        return CheckResult(check.name, "blocked", f"required command/script missing: {' '.join(check.request.command)}")
    if result.status == "timeout":
        return CheckResult(check.name, "blocked", f"timed out after {check.request.timeout_seconds}s")
    return CheckResult(check.name, "blocked", f"non-zero exit: {result.returncode}")


def _command_exists(command: str) -> bool:
    parts = shlex.split(command)
    if not parts:
        return False
    idx = 0
    while idx < len(parts) and "=" in parts[idx] and not parts[idx].startswith(("./", "/")):
        key, _, value = parts[idx].partition("=")
        if key and value:
            idx += 1
            continue
        break
    if idx >= len(parts):
        return False
    executable = parts[idx]
    if os.path.sep in executable:
        return Path(executable).exists()
    return shutil.which(executable) is not None


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
        for item in sorted(blocked, key=lambda r: r.name):
            gate_id = gate_id_for_tier0_check(item.name)
            print(
                format_blocked_state(
                    status="[ADAAD BLOCKED]",
                    gate_id=gate_id,
                    failure_detail=item.detail,
                    action_required="Fix the failing Tier 0 gate and rerun scripts/run_tier0_preflight.py.",
                )
            )
    elif skipped:
        print("Tier 0 diagnostic complete (not full green: checks were skipped).")
    else:
        print("Tier 0 green: all mandatory checks passed.")


def build_checks(include_tests: bool) -> list[Check]:
    checks = [
        Check(
            "schema validation",
            lint_check_request(tool_id="tier0-schema-validation", command=(sys.executable, "scripts/validate_governance_schemas.py")),
        ),
        Check(
            "architecture snapshot",
            lint_check_request(tool_id="tier0-architecture-snapshot", command=(sys.executable, "scripts/validate_architecture_snapshot.py")),
        ),
        Check(
            "determinism lint",
            lint_check_request(
                tool_id="tier0-determinism-lint",
                command=(sys.executable, "tools/lint_determinism.py", "runtime/", "security/", "adaad/orchestrator/", "app/main.py"),
            ),
        ),
        Check(
            "import boundary lint",
            lint_check_request(tool_id="tier0-import-boundary-lint", command=(sys.executable, "tools/lint_import_paths.py")),
        ),
        Check(
            "governance doc consistency",
            lint_check_request(
                tool_id="tier0-governance-doc-consistency",
                command=(sys.executable, "scripts/validate_governance_doc_consistency.py"),
            ),
        ),
    ]
    if include_tests:
        checks.append(
            Check(
                "fast confidence tests",
                test_check_request(
                    tool_id="tier0-fast-confidence-tests",
                    command=(
                        sys.executable,
                        "-m",
                        "pytest",
                        "tests/determinism/",
                        "tests/recovery/test_tier_manager.py",
                        "-k",
                        "not shared_epoch_parallel_validation_is_deterministic_in_strict_mode",
                        "-q",
                    ),
                    environment={"PYTHONPATH": "."},
                ),
            )
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="diagnostic mode; do not execute commands")
    parser.add_argument("--no-tests", action="store_true", help="omit the test gate (allowed only with --check-only)")
    args = parser.parse_args()

    if args.no_tests and not args.check_only:
        print(
            format_blocked_state(
                status="[ADAAD BLOCKED]",
                gate_id="TIER0_FAST_CONFIDENCE_TESTS",
                failure_detail="--no-tests is restricted to diagnostic mode; rerun with --check-only.",
                action_required="Rerun scripts/run_tier0_preflight.py without --no-tests, or pair --no-tests with --check-only.",
            )
        )
        return 2

    checks = build_checks(include_tests=not args.no_tests)

    if _test_mode_enabled() and not args.check_only:
        missing_test_extras = _missing_test_extras()
        if missing_test_extras:
            print(
                format_blocked_state(
                    status="[ADAAD BLOCKED]",
                    gate_id="TIER0_FAST_CONFIDENCE_TESTS",
                    failure_detail="missing test-mode extras: "
                    + ", ".join(missing_test_extras)
                    + ". Install requirements.dev.txt before running Tier 0 in test mode.",
                    action_required="Install requirements.dev.txt extras and rerun scripts/run_tier0_preflight.py.",
                )
            )
            return 2
    results = [_run_check(check, check_only=args.check_only) for check in checks]

    if args.no_tests and args.check_only:
        results.append(CheckResult("fast confidence tests", "skipped", "diagnostic-only skip requested via --no-tests"))

    _print_summary(results)
    return 1 if any(r.status == "blocked" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
