# SPDX-License-Identifier: Apache-2.0

import ast
import json

import pytest
pytestmark = pytest.mark.regression_standard
from pathlib import Path

from tools import lint_import_paths


def _parse(source: str) -> ast.AST:
    return ast.parse(source)


def test_iter_issues_allowlists_governance_direct_imports() -> None:
    path = lint_import_paths.REPO_ROOT / "governance" / "__init__.py"
    tree = _parse("from governance.foundation import canonical\n")

    issues = list(lint_import_paths._iter_issues(path, tree))

    assert issues == []


def test_governance_impl_detection_flags_module_level_function() -> None:
    path = lint_import_paths.REPO_ROOT / "governance" / "utils.py"
    tree = _parse("def helper():\n    return 1\n")

    issues = list(lint_import_paths._iter_governance_impl_issues(path, tree))

    assert any(issue.message == lint_import_paths.GOVERNANCE_IMPL_VIOLATION_MESSAGE for issue in issues)


def test_governance_impl_detection_flags_module_level_class() -> None:
    path = lint_import_paths.REPO_ROOT / "governance" / "utils.py"
    tree = _parse("class Adapter:\n    pass\n")

    issues = list(lint_import_paths._iter_governance_impl_issues(path, tree))

    assert any(issue.message == lint_import_paths.GOVERNANCE_IMPL_VIOLATION_MESSAGE for issue in issues)


def test_governance_impl_detection_allows_all_assignment_only() -> None:
    path = lint_import_paths.REPO_ROOT / "governance" / "utils.py"
    tree = _parse('__all__ = ["X"]\n')

    issues = list(lint_import_paths._iter_governance_impl_issues(path, tree))

    assert issues == []


def test_governance_impl_detection_flags_nonstandard_assignment() -> None:
    path = lint_import_paths.REPO_ROOT / "governance" / "utils.py"
    tree = _parse('VERSION = "1.0"\n')

    issues = list(lint_import_paths._iter_governance_impl_issues(path, tree))

    assert any(issue.message == lint_import_paths.GOVERNANCE_IMPL_VIOLATION_MESSAGE for issue in issues)


def test_governance_impl_detection_ignores_runtime_governance_files() -> None:
    path = lint_import_paths.REPO_ROOT / "runtime" / "governance" / "foundation.py"
    tree = _parse("def helper():\n    return 1\n")

    issues = list(lint_import_paths._iter_governance_impl_issues(path, tree))

    assert issues == []


def test_main_skips_always_excluded_before_governance_impl_check(tmp_path: Path, monkeypatch) -> None:
    excluded = tmp_path / "tools" / "lint_import_paths.py"
    excluded.parent.mkdir(parents=True, exist_ok=True)
    excluded.write_text("def forbidden():\n    return 1\n", encoding="utf-8")

    monkeypatch.setattr(lint_import_paths, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lint_import_paths, "ALWAYS_EXCLUDED", frozenset({"tools/lint_import_paths.py"}))

    exit_code = lint_import_paths.main(["tools"])

    assert exit_code == 0


def test_governance_impl_detection_flags_nonstandard_annotated_assignment() -> None:
    path = lint_import_paths.REPO_ROOT / "governance" / "utils.py"
    tree = _parse('VERSION: str = "1.0"\n')

    issues = list(lint_import_paths._iter_governance_impl_issues(path, tree))

    assert any(issue.message == lint_import_paths.GOVERNANCE_IMPL_VIOLATION_MESSAGE for issue in issues)


def test_governance_impl_detection_allows_standard_annotated_assignment() -> None:
    path = lint_import_paths.REPO_ROOT / "governance" / "utils.py"
    tree = _parse('__version__: str = "1.0"\n')

    issues = list(lint_import_paths._iter_governance_impl_issues(path, tree))

    assert issues == []



def test_layer_boundary_flags_orchestrator_importing_app() -> None:
    path = lint_import_paths.REPO_ROOT / "adaad" / "orchestrator" / "dispatcher.py"
    tree = _parse("from app.main import Orchestrator\n")

    issues = list(lint_import_paths._iter_layer_boundary_issues(path, tree))

    assert any(issue.message == lint_import_paths.LAYER_BOUNDARY_VIOLATION_MESSAGE for issue in issues)




def test_layer_boundary_flags_orchestrator_importing_runtime_platform_internal() -> None:
    path = lint_import_paths.REPO_ROOT / "adaad" / "orchestrator" / "dispatcher.py"
    tree = _parse("from runtime.platform.storage_manager import StorageManager\n")

    issues = list(lint_import_paths._iter_layer_boundary_issues(path, tree))

    assert any(issue.message == lint_import_paths.LAYER_BOUNDARY_VIOLATION_MESSAGE for issue in issues)
def test_layer_boundary_allows_orchestrator_runtime_import() -> None:
    path = lint_import_paths.REPO_ROOT / "adaad" / "orchestrator" / "dispatcher.py"
    tree = _parse("from runtime import metrics\n")

    issues = list(lint_import_paths._iter_layer_boundary_issues(path, tree))

    assert issues == []


def test_layer_boundary_flags_runtime_init_importing_orchestrator() -> None:
    path = lint_import_paths.REPO_ROOT / "runtime" / "__init__.py"
    tree = _parse("from adaad.orchestrator.dispatcher import dispatch\n")

    issues = list(lint_import_paths._iter_layer_boundary_issues(path, tree))

    assert any(issue.message == lint_import_paths.LAYER_BOUNDARY_VIOLATION_MESSAGE for issue in issues)


def test_layer_boundary_flags_orchestrator_relative_importing_app_module() -> None:
    path = lint_import_paths.REPO_ROOT / "adaad" / "orchestrator" / "dispatcher.py"
    tree = _parse("from ...app import main\n")

    issues = list(lint_import_paths._iter_layer_boundary_issues(path, tree))

    assert any(issue.message == lint_import_paths.LAYER_BOUNDARY_VIOLATION_MESSAGE for issue in issues)


def test_layer_boundary_flags_runtime_init_relative_importing_ui() -> None:
    path = lint_import_paths.REPO_ROOT / "runtime" / "__init__.py"
    tree = _parse("from ..ui import aponi_dashboard\n")

    issues = list(lint_import_paths._iter_layer_boundary_issues(path, tree))

    assert any(issue.message == lint_import_paths.LAYER_BOUNDARY_VIOLATION_MESSAGE for issue in issues)


def test_layer_boundary_flags_mutation_executor_importing_app_main() -> None:
    path = lint_import_paths.REPO_ROOT / "app" / "mutation_executor.py"
    tree = _parse("from app.main import Orchestrator\n")

    issues = list(lint_import_paths._iter_layer_boundary_issues(path, tree))

    assert any(issue.message == lint_import_paths.LAYER_BOUNDARY_VIOLATION_MESSAGE for issue in issues)


def test_resolve_relative_module_level_three_reaches_repo_root() -> None:
    path = lint_import_paths.REPO_ROOT / "adaad" / "orchestrator" / "dispatcher.py"
    tree = _parse("from ...app import main\n")
    node = next(node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))

    resolved = lint_import_paths._resolve_relative_module(path, node)

    assert resolved == "app"


def test_main_json_output_contains_rule_ids(tmp_path: Path, monkeypatch, capsys) -> None:
    src = tmp_path / "app" / "x.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("from governance import foundation\n", encoding="utf-8")

    monkeypatch.setattr(lint_import_paths, "REPO_ROOT", tmp_path)

    exit_code = lint_import_paths.main(["app", "--format=json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False
    assert payload["issue_count"] == 1
    assert payload["issues"][0]["rule"] == "governance_direct_import"


def test_main_json_output_empty_when_clean(tmp_path: Path, monkeypatch, capsys) -> None:
    src = tmp_path / "app" / "x.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("from runtime.api.app_layer import metrics\n", encoding="utf-8")

    monkeypatch.setattr(lint_import_paths, "REPO_ROOT", tmp_path)

    exit_code = lint_import_paths.main(["app", "--format=json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["issue_count"] == 0
    assert payload["issues"] == []


def test_validate_boundary_table_rejects_invalid_scope(monkeypatch) -> None:
    monkeypatch.setattr(lint_import_paths, "LAYER_IMPORT_BOUNDARIES", (("adaad/orchestrator", ("app",)),))
    with pytest.raises(ValueError, match="must end with"):
        lint_import_paths._validate_boundary_table()


def test_validate_boundary_table_rejects_empty_forbidden_set(monkeypatch) -> None:
    monkeypatch.setattr(lint_import_paths, "LAYER_IMPORT_BOUNDARIES", (("adaad/orchestrator/", ()),))
    with pytest.raises(ValueError, match="empty forbidden-prefix tuple"):
        lint_import_paths._validate_boundary_table()


def test_archive_import_is_forbidden() -> None:
    path = lint_import_paths.REPO_ROOT / "app" / "x.py"
    tree = _parse("import archives.snapshot\n")

    issues = list(lint_import_paths._iter_issues(path, tree))

    assert any(issue.message == lint_import_paths.ARCHIVE_IMPORT_VIOLATION_MESSAGE for issue in issues)


def test_runtime_non_facade_importing_app_is_forbidden() -> None:
    path = lint_import_paths.REPO_ROOT / "runtime" / "evolution" / "x.py"
    tree = _parse("from app.main import Orchestrator\n")

    issues = list(lint_import_paths._iter_runtime_app_boundary_issues(path, tree))

    assert any(issue.message == lint_import_paths.RUNTIME_APP_IMPORT_VIOLATION_MESSAGE for issue in issues)


def test_runtime_api_importing_app_is_allowed() -> None:
    path = lint_import_paths.REPO_ROOT / "runtime" / "api" / "x.py"
    tree = _parse("from app.main import Orchestrator\n")

    issues = list(lint_import_paths._iter_runtime_app_boundary_issues(path, tree))

    assert issues == []


def test_app_importing_runtime_internal_is_forbidden() -> None:
    path = lint_import_paths.REPO_ROOT / "app" / "x.py"
    tree = _parse("from runtime.evolution import EvolutionRuntime\n")

    issues = list(lint_import_paths._iter_app_runtime_facade_issues(path, tree))

    assert any(issue.message == lint_import_paths.APP_RUNTIME_INTERNAL_VIOLATION_MESSAGE for issue in issues)


def test_app_importing_runtime_api_is_allowed() -> None:
    path = lint_import_paths.REPO_ROOT / "app" / "x.py"
    tree = _parse("from runtime.api.runtime_services import EvolutionRuntime\n")

    issues = list(lint_import_paths._iter_app_runtime_facade_issues(path, tree))

    assert issues == []


def test_legacy_agent_namespace_import_is_forbidden_outside_shims() -> None:
    path = lint_import_paths.REPO_ROOT / "app" / "main.py"
    tree = _parse("from app.agents.mutation_request import MutationRequest\n")

    issues = list(lint_import_paths._iter_agent_namespace_drift_issues(path, tree))

    assert any(issue.message == lint_import_paths.LEGACY_AGENT_NAMESPACE_VIOLATION_MESSAGE for issue in issues)


def test_legacy_agent_namespace_import_is_allowed_inside_shims() -> None:
    path = lint_import_paths.REPO_ROOT / "app" / "agents" / "shim.py"
    tree = _parse("from app.agents.mutation_request import MutationRequest\n")

    issues = list(lint_import_paths._iter_agent_namespace_drift_issues(path, tree))

    assert issues == []


def test_duplicate_namespace_pattern_is_reported() -> None:
    path = lint_import_paths.REPO_ROOT / "runtime" / "x.py"
    tree = _parse(
        "from app.agents.discovery import resolve_agent_id\n"
        "from adaad.agents.discovery import iter_agent_dirs\n"
    )

    issues = list(lint_import_paths._iter_agent_namespace_drift_issues(path, tree))

    assert any(issue.message == lint_import_paths.DUPLICATE_AGENT_NAMESPACE_VIOLATION_MESSAGE for issue in issues)


def test_deprecated_import_path_flags_app_root_import() -> None:
    path = lint_import_paths.REPO_ROOT / "runtime" / "x.py"
    tree = _parse("from app.root import ROOT_DIR\n")

    issues = list(lint_import_paths._iter_deprecated_import_issues(path, tree))

    assert any(issue.message == lint_import_paths.DEPRECATED_IMPORT_VIOLATION_MESSAGE for issue in issues)


def test_deprecated_import_path_allows_app_root_compatibility_module() -> None:
    path = lint_import_paths.REPO_ROOT / "app" / "root.py"
    tree = _parse("from adaad.core.root import ROOT_DIR\n")

    issues = list(lint_import_paths._iter_deprecated_import_issues(path, tree))

    assert issues == []
