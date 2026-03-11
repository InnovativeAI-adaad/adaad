# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.evolution.lineage_v2 import LineageIntegrityError, LineageLedgerV2
from runtime.recovery.ledger_guardian import AutoRecoveryHook, SnapshotManager
from security.ledger.journal import JournalIntegrityError, append_tx, verify_journal_integrity


@pytest.fixture(autouse=True)
def _isolate_journal_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from security.ledger import journal

    monkeypatch.setattr(journal, "JOURNAL_PATH", tmp_path / "cryovant_journal.jsonl")
    monkeypatch.setattr(journal, "GENESIS_PATH", tmp_path / "cryovant_journal.genesis.jsonl")


def test_lineage_auto_recovery_from_snapshot(tmp_path: Path) -> None:
    ledger_path = tmp_path / "lineage_v2.jsonl"
    ledger = LineageLedgerV2(ledger_path)
    ledger.append_event("EpochStartEvent", {"epoch_id": "ep-1"})

    snapshots = SnapshotManager(tmp_path / "snaps")
    snapshots.create_snapshot(ledger_path)

    entry = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])
    entry["prev_hash"] = "x" * 64
    ledger_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    hook = AutoRecoveryHook(snapshots)
    with pytest.raises(LineageIntegrityError):
        ledger.verify_integrity(recovery_hook=hook)

    # run verify again post-recovery
    ledger.verify_integrity()
    assert hook.recovery_log


def test_journal_auto_recovery_from_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from security.ledger import journal

    temp_journal = tmp_path / "cryovant_journal.jsonl"
    temp_genesis = tmp_path / "cryovant_journal.genesis.jsonl"
    monkeypatch.setattr(journal, "JOURNAL_PATH", temp_journal)
    monkeypatch.setattr(journal, "GENESIS_PATH", temp_genesis)

    append_tx("test", {"i": 1}, tx_id="TX-1")

    snapshots = SnapshotManager(tmp_path / "snaps")
    snapshots.create_snapshot(temp_journal)

    entry = json.loads(temp_journal.read_text(encoding="utf-8").splitlines()[0])
    entry["hash"] = "bad"
    temp_journal.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    hook = AutoRecoveryHook(snapshots)
    with pytest.raises(JournalIntegrityError):
        verify_journal_integrity(recovery_hook=hook)

    verify_journal_integrity()
    assert hook.recovery_log


def test_snapshot_manager_list_restore_and_latest(tmp_path: Path) -> None:
    lineage = tmp_path / "lineage_v2.jsonl"
    journal = tmp_path / "journal_state.jsonl"
    lineage.write_text('{"type":"EpochStartEvent"}\n', encoding="utf-8")
    journal.write_text('{"tx":"ok"}\n', encoding="utf-8")

    snapshots = SnapshotManager(tmp_path / "snaps")
    snapshots.create_snapshot(lineage, journal, "epoch-1")

    all_snaps = snapshots.list_snapshots()
    assert all_snaps
    latest = snapshots.get_latest_snapshot()
    assert latest is not None
    assert latest.epoch_id == "epoch-1"

    lineage.write_text("corrupt\n", encoding="utf-8")
    journal.write_text("corrupt\n", encoding="utf-8")
    restored = snapshots.restore_snapshot(latest.snapshot_id, lineage, journal)
    assert restored
    assert "EpochStartEvent" in lineage.read_text(encoding="utf-8")


def test_snapshot_manager_create_snapshot_set_uses_unique_ids_under_rapid_calls(tmp_path: Path) -> None:
    source = tmp_path / "lineage_v2.jsonl"
    source.write_text('{"type":"EpochStartEvent"}\n', encoding="utf-8")

    snapshots = SnapshotManager(tmp_path / "snaps")
    ids: list[str] = []
    for _ in range(100):
        metadata = snapshots.create_snapshot_set([source])
        ids.append(metadata.snapshot_id)

    assert len(ids) == len(set(ids))


def test_snapshot_manager_prunes_deterministically_with_rapid_calls(tmp_path: Path) -> None:
    source = tmp_path / "lineage_v2.jsonl"
    source.write_text('{"type":"EpochStartEvent"}\n', encoding="utf-8")

    snapshots = SnapshotManager(tmp_path / "snaps", max_snapshots=5)
    created = [snapshots.create_snapshot_set([source]) for _ in range(12)]

    remaining = snapshots.list_snapshots()
    assert len(remaining) == 5

    expected_ids = [item.snapshot_id for item in created[-5:]][::-1]
    assert [item.snapshot_id for item in remaining] == expected_ids
    assert [item.creation_sequence for item in remaining] == [12, 11, 10, 9, 8]


def test_latest_valid_snapshot_ignores_incomplete_directories(tmp_path: Path) -> None:
    source = tmp_path / "lineage_v2.jsonl"
    source.write_text('{"type":"EpochStartEvent"}\n', encoding="utf-8")

    snapshots = SnapshotManager(tmp_path / "snaps")
    complete = snapshots.create_snapshot_set([source])

    partial_dir = snapshots.snapshot_dir / "snapshot-partial"
    partial_dir.mkdir(parents=True)
    (partial_dir / source.name).write_text("valid-but-incomplete\n", encoding="utf-8")

    metadata = json.loads(snapshots.metadata_path.read_text(encoding="utf-8"))
    metadata["snapshot-partial"] = {
        "snapshot_id": "snapshot-partial",
        "timestamp": "2100-01-01T00:00:00Z",
        "file_count": 1,
        "total_bytes": 1,
        "files": {source.name: "dummy"},
        "epoch_id": "",
        "creation_sequence": 999,
    }
    snapshots.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    refreshed = SnapshotManager(snapshots.snapshot_dir)
    def _validate_exists(path: Path) -> None:
        path.read_text(encoding="utf-8")

    latest = refreshed.get_latest_valid_snapshot(source.name, _validate_exists)
    assert latest is not None
    assert latest.parent.name == complete.snapshot_id


def test_latest_valid_snapshot_orders_by_creation_sequence_not_mtime(tmp_path: Path) -> None:
    source = tmp_path / "lineage_v2.jsonl"
    source.write_text('{"type":"EpochStartEvent"}\n', encoding="utf-8")

    snapshots = SnapshotManager(tmp_path / "snaps")
    first = snapshots.create_snapshot_set([source])

    source.write_text('{"type":"EpochStartEvent","n":2}\n', encoding="utf-8")
    second = snapshots.create_snapshot_set([source])

    first_file = snapshots.snapshot_dir / first.snapshot_id / source.name
    second_file = snapshots.snapshot_dir / second.snapshot_id / source.name
    # Make the older snapshot look newer by mtime to ensure ordering ignores mtime.
    first_file.touch()
    (snapshots.snapshot_dir / first.snapshot_id).touch()

    def _validate_exists(path: Path) -> None:
        path.read_text(encoding="utf-8")

    latest = snapshots.get_latest_valid_snapshot(source.name, _validate_exists)
    assert latest is not None
    assert latest.parent.name == second.snapshot_id
    assert latest.read_text(encoding="utf-8") == second_file.read_text(encoding="utf-8")


def test_snapshot_write_is_atomic(tmp_path: Path) -> None:
    """Staging .tmp dir must exist before rename; snapshot dir must not exist before rename."""
    source = tmp_path / "lineage_v2.jsonl"
    source.write_text('{"type":"EpochStartEvent"}\n', encoding="utf-8")

    manager = SnapshotManager(tmp_path / "snaps")
    rename_calls: list[tuple[Path, Path]] = []
    original_rename = os.rename

    def tracking_rename(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        rename_calls.append((src_path, dst_path))
        assert src_path.exists(), "staging dir must exist before rename"
        assert not dst_path.exists(), "final dir must not exist before rename"
        assert (src_path / "snapshot_complete").exists(), "sentinel must be in staging before rename"
        original_rename(src, dst)

    with patch("os.rename", side_effect=tracking_rename):
        manager.create_snapshot_set([source])

    assert len(rename_calls) == 1
    final = rename_calls[0][1]
    assert final.exists()
    assert (final / "snapshot_complete").exists()


def test_partial_snapshot_excluded(tmp_path: Path) -> None:
    """Snapshot directories without sentinel must be excluded from candidate set."""
    source = tmp_path / "lineage_v2.jsonl"
    source.write_text('{"type":"EpochStartEvent"}\n', encoding="utf-8")

    manager = SnapshotManager(tmp_path / "snaps")

    partial = manager.snapshot_dir / "snap-000"
    partial.mkdir(parents=True)
    (partial / "metadata.json").write_text(json.dumps({"creation_sequence": 999}), encoding="utf-8")

    result = manager.get_latest_valid_snapshot(source.name, lambda path: path.read_text(encoding="utf-8"))
    assert result is None or result.parent != partial


def test_ordering_uses_creation_sequence_not_mtime(tmp_path: Path) -> None:
    """Snapshot with higher creation_sequence wins even if its mtime is older."""
    manager = SnapshotManager(tmp_path / "snaps")

    snap1 = manager.snapshot_dir / "snap-001"
    snap1.mkdir(parents=True)
    (snap1 / "lineage_v2.jsonl").write_text("one\n", encoding="utf-8")
    (snap1 / "metadata.json").write_text(json.dumps({"creation_sequence": 1}), encoding="utf-8")
    (snap1 / "snapshot_complete").write_text("1", encoding="utf-8")

    time.sleep(0.01)

    snap2 = manager.snapshot_dir / "snap-002"
    snap2.mkdir(parents=True)
    (snap2 / "lineage_v2.jsonl").write_text("two\n", encoding="utf-8")
    (snap2 / "metadata.json").write_text(json.dumps({"creation_sequence": 2}), encoding="utf-8")
    (snap2 / "snapshot_complete").write_text("1", encoding="utf-8")

    old_time = time.time() - 3600
    os.utime(snap2, (old_time, old_time))

    result = manager.get_latest_valid_snapshot("lineage_v2.jsonl", lambda path: path.read_text(encoding="utf-8"))
    assert result is not None
    assert result.parent == snap2
