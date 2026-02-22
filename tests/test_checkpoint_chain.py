# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from runtime.evolution.checkpoint_registry import CheckpointRegistry
from runtime.evolution.epoch import EpochManager
from runtime.evolution.governor import EvolutionGovernor
from runtime.evolution.lineage_v2 import LineageLedgerV2


class _ReplaySafeProvider:
    replay_safe = True
    deterministic = True

    def __init__(self) -> None:
        self._counter = 0

    def iso_now(self) -> str:
        return "2026-01-01T00:00:00Z"

    def format_utc(self, fmt: str) -> str:
        return "20260101T000000Z"

    def next_id(self, label: str = "id", length: int = 6) -> str:
        self._counter += 1
        return f"{self._counter:06d}"[-length:]

    def next_token(self, *, label: str, length: int = 6) -> str:
        return self.next_id(label=label, length=length)

    def now_utc(self):
        from datetime import datetime, timezone

        return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _manager(tmp_path: Path) -> EpochManager:
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    governor = EvolutionGovernor(ledger=ledger, provider=_ReplaySafeProvider())
    return EpochManager(
        governor,
        ledger,
        provider=governor.provider,
        replay_mode="strict",
        state_path=tmp_path / "state" / "current_epoch.json",
    )


def test_valid_prior_checkpoint_transition(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    epoch = manager.load_or_create()
    checkpoint = CheckpointRegistry(manager.ledger).create_checkpoint(epoch.epoch_id)

    rotated = manager.rotate_epoch("mutation_threshold")

    assert rotated.epoch_id != epoch.epoch_id
    continuity_events = [e for e in manager.ledger.read_all() if e.get("type") == "epoch_checkpoint_continuity_verified"]
    assert continuity_events
    assert continuity_events[-1]["payload"]["terminal_checkpoint_hash"] == checkpoint["checkpoint_hash"]


def test_missing_prior_checkpoint(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    manager.load_or_create()

    with pytest.raises(RuntimeError, match=r"^epoch_checkpoint_continuity_failed:prior_checkpoint_missing$"):
        manager.rotate_epoch("mutation_threshold")


def test_hash_mismatch_at_boundary(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    epoch = manager.load_or_create()
    checkpoint = CheckpointRegistry(manager.ledger).create_checkpoint(epoch.epoch_id)

    manager.ledger.append_event(
        "EpochCheckpointEvent",
        {
            **checkpoint,
            "checkpoint_id": "chk_tampered",
            "checkpoint_hash": "sha256:" + ("f" * 64),
            "prev_checkpoint_hash": checkpoint["checkpoint_hash"],
        },
    )

    with pytest.raises(RuntimeError, match=r"^epoch_checkpoint_continuity_failed:checkpoint_hash_mismatch:1$"):
        manager.rotate_epoch("mutation_threshold")


def test_fail_closed_behavior(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    epoch = manager.load_or_create()

    with pytest.raises(RuntimeError):
        manager.rotate_epoch("mutation_threshold")

    assert manager.get_active().epoch_id == epoch.epoch_id
    failed_events = [e for e in manager.ledger.read_all() if e.get("type") == "epoch_checkpoint_continuity_failed"]
    assert failed_events
