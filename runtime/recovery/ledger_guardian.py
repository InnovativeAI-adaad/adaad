# SPDX-License-Identifier: Apache-2.0
"""Ledger guardian: automatic recovery and snapshot management."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from runtime import metrics
from runtime.evolution.lineage_v2 import LineageIntegrityError, LineageLedgerV2, LineageRecoveryHook
from runtime.governance.foundation import RuntimeDeterminismProvider, default_provider, require_replay_safe_provider
from security.ledger import journal
from security.ledger.journal import JournalIntegrityError, JournalRecoveryHook, verify_journal_integrity


LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class SnapshotMetadata:
    snapshot_id: str
    timestamp: str
    file_count: int
    total_bytes: int
    files: dict[str, str]
    epoch_id: str = ""
    creation_sequence: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "files": self.files,
            "epoch_id": self.epoch_id,
            "creation_sequence": self.creation_sequence,
        }


class SnapshotManager:
    """Manages rotating snapshots with retention policy and metadata."""

    _completion_marker_name = "snapshot_complete"

    def __init__(
        self,
        snapshot_dir: Path,
        max_snapshots: int = 10,
        provider: RuntimeDeterminismProvider | None = None,
        *,
        replay_mode: str = "off",
        recovery_tier: str | None = None,
    ):
        self.snapshot_dir = snapshot_dir
        self.max_snapshots = max_snapshots
        self.provider = provider or default_provider()
        self.replay_mode = replay_mode
        self.recovery_tier = recovery_tier
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.snapshot_dir / "snapshots.json"
        self._metadata: dict[str, SnapshotMetadata] = {}
        self._next_creation_sequence = 1
        self._load_metadata()

    def _load_metadata(self) -> None:
        if not self.metadata_path.exists():
            return
        try:
            raw = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            for snapshot_id, item in raw.items():
                self._metadata[snapshot_id] = SnapshotMetadata(
                    snapshot_id=snapshot_id,
                    timestamp=str(item.get("timestamp") or ""),
                    file_count=int(item.get("file_count") or 0),
                    total_bytes=int(item.get("total_bytes") or 0),
                    files=dict(item.get("files") or {}),
                    epoch_id=str(item.get("epoch_id") or ""),
                    creation_sequence=int(item.get("creation_sequence") or 0),
                )
            self._repair_creation_sequences()
        except (ValueError, TypeError):
            self._metadata = {}
            self._next_creation_sequence = 1

    def _repair_creation_sequences(self) -> None:
        ordered = sorted(
            self._metadata.items(),
            key=lambda pair: (
                pair[1].creation_sequence > 0,
                pair[1].creation_sequence,
                pair[1].timestamp,
                pair[0],
            ),
        )

        sequence = 1
        fixed: dict[str, SnapshotMetadata] = {}
        for snapshot_id, meta in ordered:
            fixed[snapshot_id] = SnapshotMetadata(
                snapshot_id=meta.snapshot_id,
                timestamp=meta.timestamp,
                file_count=meta.file_count,
                total_bytes=meta.total_bytes,
                files=meta.files,
                epoch_id=meta.epoch_id,
                creation_sequence=sequence,
            )
            sequence += 1
        self._metadata = fixed
        self._next_creation_sequence = sequence

    def _save_metadata(self) -> None:
        payload = {sid: meta.to_dict() for sid, meta in self._metadata.items()}
        self.metadata_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def create_snapshot(self, *args: Path | str) -> Path:
        """Create snapshot with backward-compatible signatures.

        Supported signatures:
        - create_snapshot(source_path)
        - create_snapshot(lineage_path, journal_path, epoch_id)
        """
        if len(args) == 1 and isinstance(args[0], Path):
            metadata = self.create_snapshot_set([args[0]])
            return self.snapshot_dir / metadata.snapshot_id / args[0].name
        if len(args) == 3 and isinstance(args[0], Path) and isinstance(args[1], Path) and isinstance(args[2], str):
            metadata = self.create_snapshot_set([args[0], args[1]], epoch_id=args[2])
            return self.snapshot_dir / metadata.snapshot_id
        raise TypeError("create_snapshot expects (source_path) or (lineage_path, journal_path, epoch_id)")

    def create_snapshot_set(self, sources: list[Path], epoch_id: str = "") -> SnapshotMetadata:
        require_replay_safe_provider(self.provider, replay_mode=self.replay_mode, recovery_tier=self.recovery_tier)
        snapshot_id = self._reserve_snapshot_id()
        snapshot_path = self.snapshot_dir / snapshot_id
        staging_dir = snapshot_path.parent / f"{snapshot_path.name}.tmp"
        staging_dir.mkdir(parents=True, exist_ok=False)

        creation_sequence = self._next_creation_sequence

        try:
            file_hashes: dict[str, str] = {}
            total_bytes = 0
            for source in sources:
                source.parent.mkdir(parents=True, exist_ok=True)
                if not source.exists():
                    source.touch()
                target = staging_dir / source.name
                shutil.copy2(source, target)
                file_hashes[source.name] = self._hash_file(target)
                total_bytes += target.stat().st_size

            (staging_dir / "metadata.json").write_text(
                json.dumps({"creation_sequence": creation_sequence}, ensure_ascii=False),
                encoding="utf-8",
            )
            (staging_dir / self._completion_marker_name).write_text("1", encoding="utf-8")
            os.rename(staging_dir, snapshot_path)

            journal.append_tx(
                "SNAPSHOT_CREATED",
                {
                    "snapshot_id": str(snapshot_path.name),
                    "creation_sequence": creation_sequence,
                },
            )
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

        self._next_creation_sequence += 1
        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            timestamp=self.provider.iso_now(),
            file_count=len(sources),
            total_bytes=total_bytes,
            files=file_hashes,
            epoch_id=epoch_id,
            creation_sequence=creation_sequence,
        )
        self._metadata[snapshot_id] = metadata
        self._save_metadata()
        self._prune_old_snapshots()

        metrics.log(event_type="snapshot_created", payload=metadata.to_dict(), level="INFO")
        return metadata

    def list_snapshots(self) -> list[SnapshotMetadata]:
        return sorted(self._metadata.values(), key=lambda m: m.creation_sequence, reverse=True)

    def get_latest_snapshot(self) -> SnapshotMetadata | None:
        snapshots = self.list_snapshots()
        return snapshots[0] if snapshots else None

    def restore_snapshot(self, snapshot_id: str, lineage_path: Path, cryovant_path: Path) -> bool:
        metadata = self._metadata.get(snapshot_id)
        if metadata is None:
            metrics.log(event_type="snapshot_restore_failed", payload={"snapshot_id": snapshot_id, "reason": "not_found"}, level="ERROR")
            return False

        snapshot_dir = self.snapshot_dir / snapshot_id
        if not snapshot_dir.exists():
            metrics.log(event_type="snapshot_restore_failed", payload={"snapshot_id": snapshot_id, "reason": "missing_directory"}, level="ERROR")
            return False

        restored_any = False
        for file_name, target_path in ((lineage_path.name, lineage_path), (cryovant_path.name, cryovant_path)):
            source = snapshot_dir / file_name
            if source.exists():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target_path)
                restored_any = True

        metrics.log(
            event_type="snapshot_restored" if restored_any else "snapshot_restore_failed",
            payload={"snapshot_id": snapshot_id, "restored_any": restored_any},
            level="INFO" if restored_any else "ERROR",
        )
        return restored_any

    def _prune_old_snapshots(self) -> None:
        snapshots = sorted(self._metadata.values(), key=lambda m: m.creation_sequence, reverse=True)
        for old in snapshots[self.max_snapshots :]:
            shutil.rmtree(self.snapshot_dir / old.snapshot_id, ignore_errors=True)
            self._metadata.pop(old.snapshot_id, None)
        self._save_metadata()

    def _reserve_snapshot_id(self) -> str:
        for _ in range(32):
            snapshot_id = self._generate_snapshot_id()
            if snapshot_id in self._metadata:
                continue
            snapshot_path = self.snapshot_dir / snapshot_id
            temp_snapshot_path = self.snapshot_dir / f"{snapshot_id}.tmp"
            if snapshot_path.exists() or temp_snapshot_path.exists():
                continue
            return snapshot_id
        raise RuntimeError("unable_to_reserve_unique_snapshot_id")

    def _generate_snapshot_id(self) -> str:
        timestamp = self.provider.format_utc("%Y%m%dT%H%M%S.%fZ")
        suffix = self.provider.next_int(low=0, high=65535, label=f"snapshot:{timestamp}")
        return f"snapshot-{timestamp}-{suffix:04x}"

    def get_latest_valid_snapshot(self, source_name: str, validator: Callable[[Path], None]) -> Path | None:
        snapshot_dirs = [
            candidate
            for candidate in self.snapshot_dir.iterdir()
            if candidate.is_dir() and (candidate / self._completion_marker_name).exists()
        ]

        ranked_candidates: list[tuple[int, float, Path]] = []
        for candidate in snapshot_dirs:
            sequence: int | None = None
            metadata_path = candidate / "metadata.json"
            try:
                sequence_value = json.loads(metadata_path.read_text(encoding="utf-8")).get("creation_sequence")
                if isinstance(sequence_value, int):
                    sequence = sequence_value
            except Exception:
                sequence = None

            if sequence is None:
                LOG.warning("snapshot_ordering_fallback_to_mtime: %s", candidate)

            ranked_candidates.append((sequence if sequence is not None else -1, candidate.stat().st_mtime, candidate))

        ranked_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)

        for _, _, snapshot_dir in ranked_candidates:
            snapshot = snapshot_dir / source_name
            if not snapshot.exists():
                continue
            try:
                validator(snapshot)
                return snapshot
            except Exception:
                continue
        return None

    @staticmethod
    def _hash_file(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


class AutoRecoveryHook(LineageRecoveryHook, JournalRecoveryHook):
    """Attempts ledger/journal recovery from latest valid snapshot."""

    def __init__(
        self,
        snapshot_manager: SnapshotManager,
        provider: RuntimeDeterminismProvider | None = None,
        *,
        replay_mode: str = "off",
        recovery_tier: str | None = None,
    ):
        self.snapshot_manager = snapshot_manager
        self.provider = provider or snapshot_manager.provider
        self.replay_mode = replay_mode
        self.recovery_tier = recovery_tier
        self.recovery_log: list[dict[str, Any]] = []

    def on_lineage_integrity_failure(self, *, ledger_path: Path, error: LineageIntegrityError) -> None:
        snapshot = self.snapshot_manager.get_latest_valid_snapshot(
            ledger_path.name,
            lambda p: LineageLedgerV2(p).verify_integrity(),
        )
        if snapshot is None:
            raise RuntimeError(f"lineage_recovery_failed:{error}") from error

        self._restore_from_snapshot(target_path=ledger_path, snapshot_path=snapshot, error=str(error), recovery_type="lineage_recovery")

    def on_journal_integrity_failure(self, *, journal_path: Path, error: JournalIntegrityError) -> None:
        snapshot = self.snapshot_manager.get_latest_valid_snapshot(
            journal_path.name,
            lambda p: verify_journal_integrity(journal_path=p),
        )
        if snapshot is None:
            raise RuntimeError(f"journal_recovery_failed:{error}") from error

        self._restore_from_snapshot(target_path=journal_path, snapshot_path=snapshot, error=str(error), recovery_type="journal_recovery")

    def _restore_from_snapshot(self, *, target_path: Path, snapshot_path: Path, error: str, recovery_type: str) -> None:
        require_replay_safe_provider(self.provider, replay_mode=self.replay_mode, recovery_tier=self.recovery_tier)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        corrupted_backup = target_path.with_suffix(target_path.suffix + ".corrupted")
        if target_path.exists():
            shutil.move(target_path, corrupted_backup)
        shutil.copy2(snapshot_path, target_path)

        event = {
            "timestamp": self.provider.iso_now(),
            "type": recovery_type,
            "error": error,
            "restored_from": str(snapshot_path),
            "corrupted_backup": str(corrupted_backup),
        }
        self.recovery_log.append(event)
        metrics.log(event_type=recovery_type, payload=event, level="WARNING")

    def attempt_recovery(self, lineage_path: Path, cryovant_path: Path, error_type: str) -> dict[str, Any]:
        require_replay_safe_provider(self.provider, replay_mode=self.replay_mode, recovery_tier=self.recovery_tier)
        latest = self.snapshot_manager.get_latest_snapshot()
        if latest is None:
            result = {
                "success": False,
                "reason": "no_snapshots_available",
                "error_type": error_type,
                "timestamp": self.provider.iso_now(),
            }
            self.recovery_log.append(result)
            metrics.log(event_type="auto_recovery_failed", payload=result, level="ERROR")
            return result

        success = self.snapshot_manager.restore_snapshot(latest.snapshot_id, lineage_path, cryovant_path)
        result = {
            "success": success,
            "snapshot_id": latest.snapshot_id,
            "snapshot_epoch": latest.epoch_id,
            "error_type": error_type,
            "timestamp": self.provider.iso_now(),
        }
        self.recovery_log.append(result)
        metrics.log(event_type="auto_recovery_success" if success else "auto_recovery_failed", payload=result, level="WARNING" if success else "ERROR")
        return result

    def get_recovery_history(self) -> list[dict[str, Any]]:
        return list(self.recovery_log)


__all__ = ["SnapshotMetadata", "SnapshotManager", "AutoRecoveryHook"]
