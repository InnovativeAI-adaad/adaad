# SPDX-License-Identifier: Apache-2.0
import shutil
from pathlib import Path

import pytest

from scripts import sync_phase_status_on_merge as sync

pytestmark = pytest.mark.regression_standard


def _seed_fixture_repo(tmp_path: Path) -> Path:
    fixture_dir = Path("tests/fixtures/phase65_sync")
    repo = tmp_path / "repo"
    (repo / "docs/governance").mkdir(parents=True)
    shutil.copy2(fixture_dir / "ROADMAP.md", repo / "ROADMAP.md")
    shutil.copy2(
        fixture_dir / "ADAAD_PR_PROCESSION_2026-03-v2.md",
        repo / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md",
    )
    return repo


def test_sync_phase65_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = _seed_fixture_repo(tmp_path)
    monkeypatch.setattr(sync, "_validate_release_evidence", lambda root: None)

    result = sync.sync_phase65_status(root=repo, require_evidence=True)

    assert result.files_changed == 2
    roadmap = (repo / "ROADMAP.md").read_text(encoding="utf-8")
    procession = (repo / "docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md").read_text(encoding="utf-8")
    assert "| next | pending |" not in roadmap
    assert "| shipped | complete |" in roadmap
    assert "Post-v9.0.0 program item" in roadmap
    assert "| 65 | v9.0.0 | Phase 64 | shipped |" in procession
    assert 'active_phase: "phase65_complete"' in procession
    assert 'milestone: "v9.0.0"' in procession


def test_sync_phase65_missing_anchor_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = _seed_fixture_repo(tmp_path)
    monkeypatch.setattr(sync, "_validate_release_evidence", lambda root: None)
    roadmap_path = repo / "ROADMAP.md"
    roadmap_path.write_text(roadmap_path.read_text(encoding="utf-8").replace("**Next:**", "**Upcoming:**"), encoding="utf-8")

    with pytest.raises(sync.SyncError, match="missing required anchor"):
        sync.sync_phase65_status(root=repo, require_evidence=True)


def test_sync_phase65_is_idempotent_on_second_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = _seed_fixture_repo(tmp_path)
    monkeypatch.setattr(sync, "_validate_release_evidence", lambda root: None)

    first = sync.sync_phase65_status(root=repo, require_evidence=True)
    second = sync.sync_phase65_status(root=repo, require_evidence=True)

    assert first.files_changed == 2
    assert second.files_changed == 0
