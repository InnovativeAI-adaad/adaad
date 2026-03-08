#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply safe import-boundary rewrites from lint_import_paths JSON output.

This fixer is intentionally fail-closed: when no rule-specific safe transform exists,
it marks an issue as manual-required instead of guessing a bridge module.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from tools.lint_import_paths import LAYER_IMPORT_BOUNDARIES

REPO_ROOT = Path(__file__).resolve().parents[1]

# Explicit, curated rewrites only. Unknown imports stay manual-required.
RUNTIME_IMPORT_APP_REWRITES: dict[str, str] = {
    "app.agents": "adaad.agents",
}

# Explicit per-scope remaps for generic layer boundary violations.
# Fail-closed default: no entry means manual-required.
LAYER_BOUNDARY_MANUAL_MAPPINGS: dict[str, dict[str, str]] = {}


@dataclass(frozen=True)
class FixIssue:
    path: str
    line: int
    column: int
    message: str
    rule: str


@dataclass(frozen=True)
class FixOutcome:
    issue: FixIssue
    status: str
    detail: str


Handler = Callable[[FixIssue, str], tuple[str, FixOutcome]]


def _replace_import_prefix(line: str, source_prefix: str, destination_prefix: str) -> str:
    pattern = re.compile(rf"(?<![\w.]){re.escape(source_prefix)}(?=\.|\b)")
    return pattern.sub(destination_prefix, line)


def _is_import_statement(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("import ") or stripped.startswith("from ")


def _resolve_layer_scope(path: str) -> str | None:
    for scope, _forbidden in LAYER_IMPORT_BOUNDARIES:
        if path == scope or path.startswith(scope):
            return scope
    return None


def _handle_runtime_imports_app_violation(issue: FixIssue, line: str) -> tuple[str, FixOutcome]:
    if not _is_import_statement(line):
        return line, FixOutcome(issue, "manual-required", "line is not an import statement")

    transformed = line
    for source_prefix, destination_prefix in RUNTIME_IMPORT_APP_REWRITES.items():
        transformed = _replace_import_prefix(transformed, source_prefix, destination_prefix)

    if transformed != line:
        return transformed, FixOutcome(issue, "fixed", "applied explicit runtime->non-app rewrite")

    return line, FixOutcome(
        issue,
        "manual-required",
        "no safe runtime import rewrite known for app/* reference; requires manual migration",
    )


def _handle_app_runtime_internal_violation(issue: FixIssue, line: str) -> tuple[str, FixOutcome]:
    if not _is_import_statement(line):
        return line, FixOutcome(issue, "manual-required", "line is not an import statement")

    transformed = re.sub(r"(?<![\w.])runtime(?!\.api)(?=\.|\b)", "runtime.api", line)
    if transformed != line:
        return transformed, FixOutcome(issue, "fixed", "rewrote runtime.* import to runtime.api.* facade")
    return line, FixOutcome(issue, "manual-required", "runtime.* symbol not found on target line")


def _handle_legacy_agent_namespace_violation(issue: FixIssue, line: str) -> tuple[str, FixOutcome]:
    if not _is_import_statement(line):
        return line, FixOutcome(issue, "manual-required", "line is not an import statement")

    transformed = _replace_import_prefix(line, "app.agents", "adaad.agents")
    if transformed != line:
        return transformed, FixOutcome(issue, "fixed", "rewrote app.agents.* to adaad.agents.*")
    return line, FixOutcome(issue, "manual-required", "app.agents prefix not present on target line")


def _handle_layer_boundary_violation(issue: FixIssue, line: str) -> tuple[str, FixOutcome]:
    if not _is_import_statement(line):
        return line, FixOutcome(issue, "manual-required", "line is not an import statement")

    scope = _resolve_layer_scope(issue.path)
    if scope is None:
        return line, FixOutcome(issue, "manual-required", "path did not match any LAYER_IMPORT_BOUNDARIES scope")

    mapping = LAYER_BOUNDARY_MANUAL_MAPPINGS.get(scope)
    if not mapping:
        return line, FixOutcome(
            issue,
            "manual-required",
            f"no explicit manual mapping configured for scope {scope!r} in LAYER_BOUNDARY_MANUAL_MAPPINGS",
        )

    transformed = line
    for source_prefix, destination_prefix in mapping.items():
        transformed = _replace_import_prefix(transformed, source_prefix, destination_prefix)

    if transformed != line:
        return transformed, FixOutcome(issue, "fixed", f"applied explicit layer mapping for scope {scope!r}")

    return line, FixOutcome(issue, "manual-required", f"no mapping entry matched import line for scope {scope!r}")


RULE_HANDLERS: dict[str, Handler] = {
    "runtime_imports_app_violation": _handle_runtime_imports_app_violation,
    "app_runtime_internal_violation": _handle_app_runtime_internal_violation,
    "legacy_agent_namespace_violation": _handle_legacy_agent_namespace_violation,
    "layer_boundary_violation": _handle_layer_boundary_violation,
}


def _load_lint_report(lint_json_path: Path | None) -> dict[str, object]:
    if lint_json_path is not None:
        return json.loads(lint_json_path.read_text(encoding="utf-8"))

    proc = subprocess.run(
        [sys.executable, "tools/lint_import_paths.py", "--format=json"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if not proc.stdout.strip():
        raise RuntimeError(f"lint_import_paths.py did not produce JSON output. stderr={proc.stderr.strip()!r}")
    return json.loads(proc.stdout)


def _parse_issues(payload: dict[str, object]) -> list[FixIssue]:
    raw_issues = payload.get("issues", [])
    if not isinstance(raw_issues, list):
        raise ValueError("lint JSON payload has non-list 'issues'")
    issues: list[FixIssue] = []
    for item in raw_issues:
        if not isinstance(item, dict):
            continue
        rule = str(item.get("rule", ""))
        if rule not in RULE_HANDLERS:
            continue
        issues.append(
            FixIssue(
                path=str(item.get("path", "")),
                line=int(item.get("line", 1)),
                column=int(item.get("column", 0)),
                message=str(item.get("message", "")),
                rule=rule,
            )
        )
    return issues


def apply_fixes(issues: Sequence[FixIssue]) -> list[FixOutcome]:
    outcomes: list[FixOutcome] = []
    by_path: dict[str, list[FixIssue]] = {}
    for issue in issues:
        by_path.setdefault(issue.path, []).append(issue)

    for rel_path, path_issues in sorted(by_path.items()):
        file_path = REPO_ROOT / rel_path
        if not file_path.exists():
            outcomes.extend(FixOutcome(issue, "manual-required", "target file missing") for issue in path_issues)
            continue

        lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        for issue in sorted(path_issues, key=lambda value: value.line, reverse=True):
            if issue.line < 1 or issue.line > len(lines):
                outcomes.append(FixOutcome(issue, "manual-required", "line out of range for file"))
                continue
            idx = issue.line - 1
            handler = RULE_HANDLERS[issue.rule]
            new_line, outcome = handler(issue, lines[idx])
            lines[idx] = new_line
            outcomes.append(outcome)

        file_path.write_text("".join(lines), encoding="utf-8")

    return outcomes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lint-json", type=Path, default=None, help="Path to lint_import_paths --format=json output")
    args = parser.parse_args(argv)

    payload = _load_lint_report(args.lint_json)
    issues = _parse_issues(payload)
    if not issues:
        print("no auto-fixable import-boundary issues found")
        return 0

    outcomes = apply_fixes(issues)
    fixed = [outcome for outcome in outcomes if outcome.status == "fixed"]
    manual = [outcome for outcome in outcomes if outcome.status == "manual-required"]

    for outcome in outcomes:
        print(f"{outcome.issue.path}:{outcome.issue.line}:{outcome.issue.column} [{outcome.issue.rule}] {outcome.status}: {outcome.detail}")

    print(f"summary: fixed={len(fixed)} manual_required={len(manual)}")
    return 1 if manual else 0


if __name__ == "__main__":
    raise SystemExit(main())
