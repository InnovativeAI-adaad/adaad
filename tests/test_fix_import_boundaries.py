# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess

import fix_import_boundaries


def _cp(returncode: int, stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_collect_issues_prefers_json(monkeypatch) -> None:
    payload = {
        "passed": False,
        "issue_count": 1,
        "issues": [
            {
                "path": "app/main.py",
                "line": 12,
                "column": 4,
                "message": "forbidden cross-layer import; see docs/ARCHITECTURE_CONTRACT.md",
                "rule": "layer_boundary_violation",
            }
        ],
    }

    monkeypatch.setattr(fix_import_boundaries, "_run_lint_json", lambda: _cp(1, json.dumps(payload)))

    issues, mode = fix_import_boundaries._collect_issues()

    assert mode == "json"
    assert len(issues) == 1
    assert issues[0].rule == "layer_boundary_violation"


def test_collect_issues_falls_back_to_text_when_json_unavailable(monkeypatch) -> None:
    text_output = "app/main.py:4:0: import app.agents.* is deprecated; use adaad.agents.* canonical namespace\n"

    monkeypatch.setattr(fix_import_boundaries, "_run_lint_json", lambda: _cp(2, "internal error"))
    monkeypatch.setattr(fix_import_boundaries, "_run_lint_text", lambda: _cp(1, text_output))

    issues, mode = fix_import_boundaries._collect_issues()

    assert mode == "text"
    assert len(issues) == 1
    assert issues[0].rule == "legacy_agent_namespace_violation"


def test_resolve_remediation_is_rule_driven() -> None:
    issue = fix_import_boundaries.ImportIssue(
        path="runtime/foo.py",
        line=8,
        column=0,
        message="runtime/* must not import app/* (except runtime/api facade modules)",
        rule="runtime_imports_app_violation",
    )

    handlers = fix_import_boundaries._build_rule_handlers()
    resolution = fix_import_boundaries._resolve_remediation(issue, handlers)

    assert "runtime.api facade abstraction" in resolution
