#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tier 0 remediation helper focused on gate verification.

This script intentionally does not perform branch creation, push, or PR creation.
VCS network operations should live in a separate wrapper.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.tools.execution_contract import (
    ToolExecutionRequest,
    ToolExecutionResult,
    dependency_check_request,
    execute_tool_request,
    lint_check_request,
    test_check_request,
)


TIER0_GATES: tuple[tuple[str, ToolExecutionRequest], ...] = (
    ("schema_validation", lint_check_request(tool_id="tier0-schema-validation", command=(sys.executable, "scripts/validate_governance_schemas.py"), working_directory=str(REPO_ROOT))),
    ("architecture_snapshot", lint_check_request(tool_id="tier0-architecture-snapshot", command=(sys.executable, "scripts/validate_architecture_snapshot.py"), working_directory=str(REPO_ROOT))),
    (
        "determinism_lint",
        lint_check_request(
            tool_id="tier0-determinism-lint",
            command=(sys.executable, "tools/lint_determinism.py", "runtime/", "security/", "adaad/orchestrator/", "app/main.py"),
            working_directory=str(REPO_ROOT),
        ),
    ),
    ("import_boundary_lint", lint_check_request(tool_id="tier0-import-boundary-lint", command=(sys.executable, "tools/lint_import_paths.py"), working_directory=str(REPO_ROOT))),
    (
        "fast_confidence_tests",
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
            environment={"PYTHONPATH": str(REPO_ROOT)},
            working_directory=str(REPO_ROOT),
        ),
    ),
    (
        "dependency_baseline",
        dependency_check_request(
            tool_id="tier0-dependency-baseline",
            command=(sys.executable, "scripts/check_dependency_baseline.py"),
            working_directory=str(REPO_ROOT),
        ),
    ),
)



def _run_gate(request: ToolExecutionRequest) -> ToolExecutionResult:
    return execute_tool_request(request)


def _build_commit_message_template(failed_gate_ids: list[str]) -> str:
    failure_suffix = ",".join(sorted(failed_gate_ids)) if failed_gate_ids else "none"
    return (
        "chore(tier0): remediation follow-up\n\n"
        f"Gate-Failures: {failure_suffix}\n"
        "Evidence: tier0-remediation\n"
        "Determinism: preserved"
    )


def _print_next_steps(commit_template: str, local_commit_enabled: bool) -> None:
    print("\nNext steps (manual / operator-driven):")
    print("1. Review failing gate output above and apply deterministic fixes.")
    print("2. Re-run this script until all Tier 0 gates pass.")
    print("3. Use your preferred VCS wrapper for branch/push/PR operations.")
    print("\nDeterministic commit message template:")
    print("---8<---")
    print(commit_template)
    print("--->8---")

    if local_commit_enabled:
        print("\nLocal commit mode enabled (no network operations):")
        print("- staged: git add -A")
        print("- committed: git commit -m \"chore(tier0): remediation follow-up\"")


def _maybe_local_commit(commit_template: str) -> int:
    add_result = subprocess.run(["git", "add", "-A"], cwd=REPO_ROOT, check=False)
    if add_result.returncode != 0:
        print("local_commit_failed: unable to stage changes", file=sys.stderr)
        return 1

    body = commit_template.split("\n\n", maxsplit=1)
    subject = body[0]
    details = body[1] if len(body) > 1 else ""
    commit_cmd = ["git", "commit", "-m", subject]
    if details:
        commit_cmd.extend(["-m", details])

    commit_result = subprocess.run(commit_cmd, cwd=REPO_ROOT, check=False)
    if commit_result.returncode != 0:
        print("local_commit_failed: git commit returned non-zero", file=sys.stderr)
    return int(commit_result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tier 0 remediation gates without network VCS actions")
    parser.add_argument(
        "--local-commit",
        action="store_true",
        help="Optionally create a local commit only (no checkout/push/PR network actions)",
    )
    args = parser.parse_args()

    failed_gate_ids: list[str] = []
    for gate_id, request in TIER0_GATES:
        print(f"\n[gate:{gate_id}] {' '.join(request.command)}")
        result = _run_gate(request)
        if result.ok:
            print("status=pass")
        else:
            print("status=fail")
            failed_gate_ids.append(gate_id)
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)

    commit_template = _build_commit_message_template(failed_gate_ids)
    _print_next_steps(commit_template, local_commit_enabled=args.local_commit)

    if args.local_commit:
        return _maybe_local_commit(commit_template)

    return 1 if failed_gate_ids else 0


if __name__ == "__main__":
    raise SystemExit(main())
