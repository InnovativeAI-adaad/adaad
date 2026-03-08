#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Machine-readable remediation driver for import boundary violations."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent

_RULE_BY_MESSAGE: dict[str, str] = {
    "forbidden cross-layer import; see docs/ARCHITECTURE_CONTRACT.md": "layer_boundary_violation",
    "runtime/* must not import app/* (except runtime/api facade modules)": "runtime_imports_app_violation",
    "app/* must import runtime only via runtime.api facade": "app_runtime_internal_violation",
    "import app.agents.* is deprecated; use adaad.agents.* canonical namespace": "legacy_agent_namespace_violation",
}


@dataclass(frozen=True)
class ImportIssue:
    path: str
    line: int
    column: int
    message: str
    rule: str


def _run_lint_json() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/lint_import_paths.py", "--format=json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_lint_text() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/lint_import_paths.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _parse_json_issues(raw: str) -> list[ImportIssue]:
    payload = json.loads(raw)
    parsed: list[ImportIssue] = []
    for issue in payload.get("issues", []):
        parsed.append(
            ImportIssue(
                path=str(issue["path"]),
                line=int(issue["line"]),
                column=int(issue["column"]),
                message=str(issue["message"]),
                rule=str(issue["rule"]),
            )
        )
    return parsed


def _fallback_parse_text_issues(raw: str) -> list[ImportIssue]:
    line_re = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?P<column>\d+): (?P<message>.+)$")
    parsed: list[ImportIssue] = []
    for line in raw.splitlines():
        match = line_re.match(line.strip())
        if not match:
            continue
        message = match.group("message")
        parsed.append(
            ImportIssue(
                path=match.group("path"),
                line=int(match.group("line")),
                column=int(match.group("column")),
                message=message,
                rule=_RULE_BY_MESSAGE.get(message, "unknown"),
            )
        )
    return parsed


def _handle_layer_boundary_violation(issue: ImportIssue) -> str:
    return f"{issue.path}:{issue.line} -> remove disallowed cross-layer import"


def _handle_runtime_imports_app_violation(issue: ImportIssue) -> str:
    return f"{issue.path}:{issue.line} -> replace app.* import with runtime.api facade abstraction"


def _handle_app_runtime_internal_violation(issue: ImportIssue) -> str:
    return f"{issue.path}:{issue.line} -> route runtime import through runtime.api.*"


def _handle_legacy_agent_namespace_violation(issue: ImportIssue) -> str:
    return f"{issue.path}:{issue.line} -> migrate app.agents.* to adaad.agents.*"


def _build_rule_handlers() -> dict[str, Callable[[ImportIssue], str]]:
    return {
        "layer_boundary_violation": _handle_layer_boundary_violation,
        "runtime_imports_app_violation": _handle_runtime_imports_app_violation,
        "app_runtime_internal_violation": _handle_app_runtime_internal_violation,
        "legacy_agent_namespace_violation": _handle_legacy_agent_namespace_violation,
    }


def _resolve_remediation(issue: ImportIssue, handlers: dict[str, Callable[[ImportIssue], str]]) -> str:
    handler = handlers.get(issue.rule)
    if handler is not None:
        return handler(issue)
    return f"{issue.path}:{issue.line} -> unhandled rule '{issue.rule}' ({issue.message})"


def _collect_issues() -> tuple[list[ImportIssue], str]:
    result = _run_lint_json()
    if result.returncode in (0, 1):
        try:
            return _parse_json_issues(result.stdout), "json"
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

    fallback = _run_lint_text()
    return _fallback_parse_text_issues(fallback.stdout), "text"


def _emit_remediation(issues: Iterable[ImportIssue]) -> None:
    handlers = _build_rule_handlers()
    for issue in issues:
        print(_resolve_remediation(issue, handlers))


def main(argv: Sequence[str] | None = None) -> int:
    _ = argv
    issues, parser_mode = _collect_issues()
    if not issues:
        print(f"No import boundary issues found (parser={parser_mode}).")
        return 0
    print(f"Found {len(issues)} import boundary issues (parser={parser_mode}).")
    _emit_remediation(issues)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
