# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from tools import fix_import_boundaries


def _issue(rule: str, path: str = "app/main.py", line: int = 1) -> fix_import_boundaries.FixIssue:
    return fix_import_boundaries.FixIssue(path=path, line=line, column=0, message="m", rule=rule)


def test_app_runtime_internal_violation_rewrites_runtime_to_runtime_api() -> None:
    issue = _issue("app_runtime_internal_violation")
    new_line, outcome = fix_import_boundaries._handle_app_runtime_internal_violation(issue, "from runtime.core import Engine\n")
    assert new_line == "from runtime.api.core import Engine\n"
    assert outcome.status == "fixed"


def test_legacy_agent_namespace_violation_rewrites_namespace() -> None:
    issue = _issue("legacy_agent_namespace_violation")
    new_line, outcome = fix_import_boundaries._handle_legacy_agent_namespace_violation(issue, "import app.agents.scheduler as scheduler\n")
    assert new_line == "import adaad.agents.scheduler as scheduler\n"
    assert outcome.status == "fixed"


def test_runtime_imports_app_violation_uses_explicit_mapping_only() -> None:
    issue = _issue("runtime_imports_app_violation", path="runtime/engine.py")
    new_line, outcome = fix_import_boundaries._handle_runtime_imports_app_violation(issue, "from app.agents.router import Router\n")
    assert new_line == "from adaad.agents.router import Router\n"
    assert outcome.status == "fixed"



def test_runtime_imports_app_violation_requires_manual_when_unknown() -> None:
    issue = _issue("runtime_imports_app_violation", path="runtime/engine.py")
    new_line, outcome = fix_import_boundaries._handle_runtime_imports_app_violation(issue, "from app.main import create_app\n")
    assert new_line == "from app.main import create_app\n"
    assert outcome.status == "manual-required"


def test_layer_boundary_violation_requires_explicit_scope_mapping() -> None:
    issue = _issue("layer_boundary_violation", path="adaad/orchestrator/run.py")
    new_line, outcome = fix_import_boundaries._handle_layer_boundary_violation(issue, "from app.main import bootstrap\n")
    assert new_line == "from app.main import bootstrap\n"
    assert outcome.status == "manual-required"
    assert "LAYER_BOUNDARY_MANUAL_MAPPINGS" in outcome.detail
