# SPDX-License-Identifier: Apache-2.0
"""Regression tests for unified post-merge orchestrator contracts."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


class TestOrchestratorMarker:
    def test_marker_env_var_name_is_stable(self) -> None:
        import sync_phase_status_on_merge as mod

        assert mod._ORCHESTRATOR_ENV_MARKER == "ADAAD_ORCHESTRATOR_RUN"

    def test_assert_passes_with_marker_set(self) -> None:
        import sync_phase_status_on_merge as mod

        with patch.dict(os.environ, {"CI": "true", "ADAAD_ORCHESTRATOR_RUN": "1"}, clear=False):
            mod._assert_orchestrator_context()

    def test_assert_fails_in_ci_without_marker(self) -> None:
        import sync_phase_status_on_merge as mod

        with patch.dict(os.environ, {"CI": "true", "ADAAD_ORCHESTRATOR_RUN": ""}, clear=False):
            with pytest.raises(SystemExit) as exc:
                mod._assert_orchestrator_context()
            assert exc.value.code == 1

    def test_assert_passes_outside_ci(self) -> None:
        import sync_phase_status_on_merge as mod

        with patch.dict(os.environ, {"CI": "", "ADAAD_ORCHESTRATOR_RUN": ""}, clear=False):
            mod._assert_orchestrator_context()


class TestPhaseSyncTriggerPattern:
    _PHASE_PATTERN = re.compile(r"PR-PHASE[0-9]+-[0-9]+")

    def _should_run(self, title: str, labels: str, force: str = "false") -> bool:
        return bool(self._PHASE_PATTERN.search(f"{title}{labels}")) or force == "true"

    @pytest.mark.parametrize(
        "title,labels,expected",
        [
            ("PR-PHASE65-01: sync docs", "", True),
            ("", "PR-PHASE77-02", True),
            ("chore: deps", "enhancement", False),
            ("PHASE65 mention", "", False),
        ],
    )
    def test_trigger_evaluation(self, title: str, labels: str, expected: bool) -> None:
        assert self._should_run(title, labels) is expected

    def test_force_overrides_no_match(self) -> None:
        assert self._should_run("chore: deps", "", force="true") is True


class TestWorkflowContracts:
    def test_loop_prevention_markers_present(self) -> None:
        workflow = ROOT / ".github/workflows/post_merge_orchestrator.yml"
        content = workflow.read_text(encoding="utf-8")
        assert "[doc-sync]" in content
        assert "github-actions[bot]" in content

    def test_retired_workflow_stub_is_inert(self) -> None:
        stub = ROOT / ".github/workflows/phase65_post_merge_sync.yml"
        content = stub.read_text(encoding="utf-8")
        assert "on: {}" in content
        assert "jobs:" not in content


class TestFilesChangedParser:
    def _parse(self, jsonl: str) -> int:
        for line in jsonl.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("event") == "sync_complete":
                return int(obj.get("files_changed", 0))
        return 0

    def test_parses_files_changed(self) -> None:
        assert self._parse('{"event":"sync_complete","files_changed":7}') == 7

    def test_returns_zero_if_missing_event(self) -> None:
        assert self._parse('{"event":"other"}') == 0


class TestProtectedFilePattern:
    _PATTERN = re.compile(
        r"^(docs/CONSTITUTION\.md"
        r"|docs/governance/ARCHITECT_SPEC"
        r"|governance/CANONICAL"
        r"|governance_runtime_profile\.lock\.json"
        r"|runtime/constitution\.py"
        r"|schemas/"
        r"|\.github/workflows/)"
    )

    @pytest.mark.parametrize(
        "path",
        [
            "docs/CONSTITUTION.md",
            "docs/governance/ARCHITECT_SPEC_v2.0.0.md",
            "governance/CANONICAL_ENGINE_DECLARATION.md",
            "runtime/constitution.py",
            "schemas/governance_policy.json",
            ".github/workflows/ci.yml",
        ],
    )
    def test_protected_paths_match(self, path: str) -> None:
        assert self._PATTERN.match(path)

    @pytest.mark.parametrize(
        "path",
        [
            "README.md",
            "ROADMAP.md",
            "docs/ENVIRONMENT_VARIABLES.md",
            "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md",
        ],
    )
    def test_syncable_paths_do_not_match(self, path: str) -> None:
        assert not self._PATTERN.match(path)
