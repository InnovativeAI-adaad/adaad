# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


QUEUE_SCHEMA_VERSION = "offline_ledger_sync_queue.v1"


class OfflineLedgerSyncError(RuntimeError):
    """Base error for offline ledger queue failures."""


class AckIntegrityError(OfflineLedgerSyncError):
    """Raised when remote acknowledgement cannot be validated safely."""


@dataclass(frozen=True)
class QueueLimits:
    max_pending_operations: int = 1_000
    ack_retention_entries: int = 2_000
    min_retry_backoff_seconds: int = 2
    max_retry_backoff_seconds: int = 300


class OfflineLedgerSyncQueue:
    """Append-only offline operation queue with idempotent replay semantics."""

    def __init__(
        self,
        log_path: Path | str,
        *,
        device_id: str,
        limits: QueueLimits | None = None,
    ) -> None:
        self.log_path = Path(log_path)
        self.device_id = device_id.strip()
        if not self.device_id:
            raise ValueError("device_id is required")
        self.limits = limits or QueueLimits()
        self._events = self._load_events()
        self._ops, self._acked_ids, self._conflicts, self._next_seq = self._rebuild_state(self._events)

    @staticmethod
    def _canonical_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def _op_digest(cls, payload: dict[str, Any]) -> str:
        return hashlib.sha256(cls._canonical_json(payload).encode("utf-8")).hexdigest()

    def _load_events(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def _append_event(self, event: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
        self._events.append(event)

    def _rebuild_state(
        self, events: list[dict[str, Any]]
    ) -> tuple[dict[str, dict[str, Any]], set[str], dict[str, dict[str, Any]], int]:
        ops: dict[str, dict[str, Any]] = {}
        acked_ids: set[str] = set()
        conflicts: dict[str, dict[str, Any]] = {}
        next_seq = 0
        for event in events:
            kind = event.get("event")
            if kind == "enqueue":
                op = dict(event["operation"])
                ops[op["op_id"]] = op
                next_seq = max(next_seq, int(op.get("op_seq", 0)))
            elif kind == "attempt":
                op = ops.get(event["op_id"])
                if op:
                    op["attempt_count"] = int(op.get("attempt_count", 0)) + 1
                    op["last_attempt_ts"] = event["ts"]
                    op["next_retry_ts"] = event["next_retry_ts"]
            elif kind == "ack_applied":
                op = ops.get(event["op_id"])
                if op:
                    op["state"] = "acked"
                    op["ack_ts"] = event["ts"]
                    op["remote_version"] = event.get("remote_version")
                acked_ids.add(event["op_id"])
            elif kind == "ack_conflict":
                op = ops.get(event["op_id"])
                if op:
                    op["state"] = "conflict"
                    op["conflict"] = dict(event["conflict"])
                    conflicts[event["op_id"]] = op["conflict"]
            elif kind == "resolve_conflict":
                op = ops.get(event["op_id"])
                if op:
                    op["state"] = "pending"
                    op["next_retry_ts"] = event["ts"]
                    op.pop("conflict", None)
                    conflicts.pop(event["op_id"], None)
        return ops, acked_ids, conflicts, next_seq + 1

    def _assert_capacity(self) -> None:
        pending = [op for op in self._ops.values() if op.get("state") == "pending"]
        if len(pending) >= self.limits.max_pending_operations:
            raise OfflineLedgerSyncError("offline queue is full")

    def enqueue_operation(
        self,
        *,
        operation_type: str,
        ledger_key: str,
        payload: dict[str, Any],
        now_ts: str,
        base_version: int | None = None,
    ) -> dict[str, Any]:
        self._assert_capacity()
        seq = self._next_seq
        op_seed = {
            "device_id": self.device_id,
            "ledger_key": ledger_key,
            "operation_type": operation_type,
            "op_seq": seq,
            "payload": payload,
            "base_version": base_version,
        }
        op_id = self._op_digest(op_seed)[:24]
        operation = {
            "schema_version": QUEUE_SCHEMA_VERSION,
            "op_id": op_id,
            "op_seq": seq,
            "operation_type": operation_type,
            "ledger_key": ledger_key,
            "payload": payload,
            "base_version": base_version,
            "enqueued_ts": now_ts,
            "next_retry_ts": now_ts,
            "attempt_count": 0,
            "state": "pending",
            "op_digest": self._op_digest(
                {
                    "operation_type": operation_type,
                    "ledger_key": ledger_key,
                    "payload": payload,
                    "base_version": base_version,
                }
            ),
        }
        event = {"event": "enqueue", "ts": now_ts, "operation": operation}
        self._append_event(event)
        self._ops[op_id] = operation
        self._next_seq += 1
        return dict(operation)

    def enqueue_create(self, *, ledger_key: str, payload: dict[str, Any], now_ts: str) -> dict[str, Any]:
        return self.enqueue_operation(
            operation_type="create", ledger_key=ledger_key, payload=payload, now_ts=now_ts, base_version=None
        )

    def enqueue_update(
        self, *, ledger_key: str, payload: dict[str, Any], base_version: int, now_ts: str
    ) -> dict[str, Any]:
        return self.enqueue_operation(
            operation_type="update",
            ledger_key=ledger_key,
            payload=payload,
            now_ts=now_ts,
            base_version=base_version,
        )

    def pending_replay(self, *, now_ts: str) -> list[dict[str, Any]]:
        return [
            dict(op)
            for op in sorted(self._ops.values(), key=lambda row: (row["op_seq"], row["op_id"]))
            if op.get("state") == "pending" and str(op.get("next_retry_ts", now_ts)) <= now_ts
        ]

    def mark_delivery_attempt(self, *, op_id: str, now_ts: str) -> dict[str, Any]:
        op = self._ops.get(op_id)
        if not op:
            raise OfflineLedgerSyncError(f"unknown op_id: {op_id}")
        if op.get("state") != "pending":
            return dict(op)
        attempts = int(op.get("attempt_count", 0)) + 1
        backoff = min(
            self.limits.max_retry_backoff_seconds,
            self.limits.min_retry_backoff_seconds * (2 ** (attempts - 1)),
        )
        next_retry_ts = f"{now_ts}+{backoff}s"
        op["attempt_count"] = attempts
        op["last_attempt_ts"] = now_ts
        op["next_retry_ts"] = next_retry_ts
        self._append_event(
            {
                "event": "attempt",
                "ts": now_ts,
                "op_id": op_id,
                "attempt_count": attempts,
                "next_retry_ts": next_retry_ts,
            }
        )
        return dict(op)

    def apply_remote_ack(self, ack: dict[str, Any], *, now_ts: str) -> dict[str, Any]:
        op_id = str(ack.get("op_id", "")).strip()
        if not op_id:
            raise AckIntegrityError("ack missing op_id")
        op = self._ops.get(op_id)
        if op is None:
            raise AckIntegrityError(f"ack references unknown op_id: {op_id}")
        remote_digest = ack.get("op_digest")
        if remote_digest and remote_digest != op.get("op_digest"):
            raise AckIntegrityError("ack digest mismatch")

        status = ack.get("status")
        if status not in {"applied", "duplicate", "conflict"}:
            raise AckIntegrityError("ack status is invalid")

        if status in {"applied", "duplicate"}:
            if op_id in self._acked_ids:
                return dict(op)
            op["state"] = "acked"
            op["ack_ts"] = now_ts
            op["remote_version"] = ack.get("remote_version")
            self._acked_ids.add(op_id)
            self._append_event(
                {
                    "event": "ack_applied",
                    "ts": now_ts,
                    "op_id": op_id,
                    "remote_version": ack.get("remote_version"),
                    "remote_status": status,
                }
            )
            self._trim_acked_index()
            return dict(op)

        conflict = {
            "state": "conflict",
            "reason": ack.get("reason", "remote_conflict"),
            "remote_snapshot": ack.get("remote_snapshot"),
            "detected_ts": now_ts,
            "resolution_required": True,
        }
        op["state"] = "conflict"
        op["conflict"] = conflict
        self._conflicts[op_id] = conflict
        self._append_event({"event": "ack_conflict", "ts": now_ts, "op_id": op_id, "conflict": conflict})
        return dict(op)

    def resolve_conflict_keep_remote(self, *, op_id: str, now_ts: str) -> dict[str, Any]:
        op = self._ops.get(op_id)
        if not op or op.get("state") != "conflict":
            raise OfflineLedgerSyncError("operation is not in conflict state")
        op["state"] = "acked"
        op["ack_ts"] = now_ts
        op.pop("conflict", None)
        self._conflicts.pop(op_id, None)
        self._acked_ids.add(op_id)
        self._append_event({"event": "ack_applied", "ts": now_ts, "op_id": op_id, "remote_status": "keep_remote"})
        self._trim_acked_index()
        return dict(op)

    def resolve_conflict_retry_local(self, *, op_id: str, now_ts: str) -> dict[str, Any]:
        op = self._ops.get(op_id)
        if not op or op.get("state") != "conflict":
            raise OfflineLedgerSyncError("operation is not in conflict state")
        op["state"] = "pending"
        op["next_retry_ts"] = now_ts
        op.pop("conflict", None)
        self._conflicts.pop(op_id, None)
        self._append_event({"event": "resolve_conflict", "ts": now_ts, "op_id": op_id, "resolution": "retry_local"})
        return dict(op)

    def user_visible_conflicts(self) -> list[dict[str, Any]]:
        conflicts = []
        for op_id, conflict in self._conflicts.items():
            op = self._ops[op_id]
            conflicts.append({"op_id": op_id, "ledger_key": op["ledger_key"], **conflict})
        return sorted(conflicts, key=lambda row: row["op_id"])

    def _trim_acked_index(self) -> None:
        if len(self._acked_ids) <= self.limits.ack_retention_entries:
            return
        acked_in_order = [
            e["op_id"]
            for e in self._events
            if e.get("event") == "ack_applied" and isinstance(e.get("op_id"), str)
        ]
        if len(acked_in_order) <= self.limits.ack_retention_entries:
            return
        keep = set(acked_in_order[-self.limits.ack_retention_entries :])
        self._acked_ids.intersection_update(keep)


__all__ = [
    "AckIntegrityError",
    "OfflineLedgerSyncError",
    "OfflineLedgerSyncQueue",
    "QueueLimits",
    "QUEUE_SCHEMA_VERSION",
]
