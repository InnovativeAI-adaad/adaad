# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from runtime.integrations.offline_ledger_sync import AckIntegrityError, OfflineLedgerSyncQueue


def _queue(tmp_path: Path) -> OfflineLedgerSyncQueue:
    return OfflineLedgerSyncQueue(tmp_path / "offline_ops.jsonl", device_id="device-A")


def test_offline_create_update_flows_and_reconnect_ordering(tmp_path: Path) -> None:
    q = _queue(tmp_path)
    c = q.enqueue_create(ledger_key="entry-1", payload={"title": "first"}, now_ts="2026-03-19T00:00:00Z")
    u = q.enqueue_update(
        ledger_key="entry-1", payload={"title": "first-v2"}, base_version=1, now_ts="2026-03-19T00:00:01Z"
    )

    replay = q.pending_replay(now_ts="9999-12-31T23:59:59Z")
    assert [row["op_id"] for row in replay] == [c["op_id"], u["op_id"]]
    assert [row["operation_type"] for row in replay] == ["create", "update"]


def test_duplicate_delivery_ack_is_idempotent(tmp_path: Path) -> None:
    q = _queue(tmp_path)
    op = q.enqueue_create(ledger_key="entry-2", payload={"status": "new"}, now_ts="2026-03-19T00:00:00Z")

    ack = {
        "op_id": op["op_id"],
        "status": "applied",
        "op_digest": op["op_digest"],
        "remote_version": 2,
    }
    first = q.apply_remote_ack(ack, now_ts="2026-03-19T00:00:02Z")
    second = q.apply_remote_ack({**ack, "status": "duplicate"}, now_ts="2026-03-19T00:00:03Z")

    assert first["state"] == "acked"
    assert second["state"] == "acked"


def test_conflict_ack_sets_user_visible_conflict_state(tmp_path: Path) -> None:
    q = _queue(tmp_path)
    op = q.enqueue_update(
        ledger_key="entry-3", payload={"status": "offline-edit"}, base_version=4, now_ts="2026-03-19T00:00:01Z"
    )

    q.apply_remote_ack(
        {
            "op_id": op["op_id"],
            "status": "conflict",
            "op_digest": op["op_digest"],
            "reason": "version_conflict",
            "remote_snapshot": {"status": "server-edit", "version": 5},
        },
        now_ts="2026-03-19T00:00:10Z",
    )

    conflicts = q.user_visible_conflicts()
    assert len(conflicts) == 1
    assert conflicts[0]["state"] == "conflict"
    assert conflicts[0]["reason"] == "version_conflict"
    assert conflicts[0]["ledger_key"] == "entry-3"


def test_ack_integrity_rejects_digest_mismatch(tmp_path: Path) -> None:
    q = _queue(tmp_path)
    op = q.enqueue_create(ledger_key="entry-4", payload={"x": 1}, now_ts="2026-03-19T00:00:00Z")

    with pytest.raises(AckIntegrityError, match="digest mismatch"):
        q.apply_remote_ack(
            {
                "op_id": op["op_id"],
                "status": "applied",
                "op_digest": "bad-digest",
            },
            now_ts="2026-03-19T00:00:08Z",
        )
