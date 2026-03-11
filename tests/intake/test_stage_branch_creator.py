# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.branch_manager import BranchManager
from runtime.governance.foundation.determinism import SeededDeterminismProvider
from runtime.intake.stage_branch_creator import StageBranchCreator


def _repo_with_sources(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for root in ["app", "runtime", "security", "experiments/branches"]:
        (repo / root).mkdir(parents=True, exist_ok=True)
    (repo / "app" / "sample.txt").write_text("hello", encoding="utf-8")
    return repo


def test_create_stage_branch_has_deterministic_name_and_manifest_provenance(tmp_path: Path) -> None:
    repo = _repo_with_sources(tmp_path)
    provider = SeededDeterminismProvider(
        seed="pr12",
        fixed_now=datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )
    manager = BranchManager(
        repo_root=repo,
        branches_dir=repo / "experiments" / "branches",
        sources=("app",),
        provider=provider,
    )
    creator = StageBranchCreator(branch_manager=manager, provider=provider)

    branch_path = creator.create_stage_branch(
        intake_id="intake-7",
        scan_id="scan-42",
        sources=["app", "runtime"],
    )

    assert branch_path.name == "stage-intake-7-def32df4987d"
    payload = json.loads((branch_path / ".manifest.json").read_text(encoding="utf-8"))
    assert payload["created_at"] == "2030-01-02T03:04:05Z"
    assert payload["intake_id"] == "intake-7"
    assert payload["scan_id"] == "scan-42"
    assert payload["sources"] == ["app", "runtime"]


def test_create_stage_branch_fail_closed_when_blocked(tmp_path: Path) -> None:
    repo = _repo_with_sources(tmp_path)
    provider = SeededDeterminismProvider(seed="blocked")
    manager = BranchManager(repo_root=repo, branches_dir=repo / "experiments" / "branches", provider=provider)
    creator = StageBranchCreator(branch_manager=manager, provider=provider)

    with pytest.raises(PermissionError, match="mutation_blocked_fail_closed"):
        creator.create_stage_branch(intake_id="intake-1", scan_id="scan-1", blocked=True, fail_closed=True)
