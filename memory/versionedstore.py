# SPDX-License-Identifier: Apache-2.0
"""Deterministic append-only versioned memory store with JSON and SQLite backends."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from runtime.governance.foundation import canonical_json


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class VersionedMemoryEntry:
    version_id: str
    parent_version_id: str | None
    created_at: str
    payload: dict[str, Any]
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "parent_version_id": self.parent_version_id,
            "created_at": self.created_at,
            "payload": dict(self.payload),
            "confidence": self.confidence,
        }


class VersionedMemoryStore:
    """Append-only memory persistence adapter.

    Invariants:
      - Entries are immutable once written (append-only; no UPDATE/DELETE on entry rows).
      - `rollback(version_id)` only moves the active head pointer; historical entries are preserved.
      - Commits are atomic:
        * JSON backend writes a temp file then atomically replaces the target file.
        * SQLite backend wraps writes in a single transaction and commits/rolls back as a unit.
    """

    def __init__(
        self,
        path: Path,
        *,
        sqlite_path: Path | None = None,
        backend: str = "json",
        clock: Callable[[], str] | None = None,
    ) -> None:
        if backend not in {"json", "sqlite"}:
            raise ValueError("invalid_state_backend")
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = sqlite_path or path.with_suffix(".sqlite")
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.backend = backend
        self._clock = clock or _utc_now_iso
        if self.backend == "sqlite":
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    version_id TEXT NOT NULL UNIQUE,
                    parent_version_id TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    confidence REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    head_version_id TEXT
                )
                """
            )
            conn.execute("INSERT OR IGNORE INTO memory_state(id, head_version_id) VALUES (1, NULL)")

    def _read_json_state(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": "1", "head_version_id": None, "entries": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"schema_version": "1", "head_version_id": None, "entries": []}
        if not isinstance(payload, dict):
            return {"schema_version": "1", "head_version_id": None, "entries": []}
        entries = payload.get("entries")
        if not isinstance(entries, list):
            entries = []
        return {
            "schema_version": str(payload.get("schema_version", "1")),
            "head_version_id": payload.get("head_version_id"),
            "entries": entries,
        }

    def _write_json_state_atomic(self, state: dict[str, Any]) -> None:
        serialized = json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(serialized)
            handle.flush()
            temp_path = Path(handle.name)
        temp_path.replace(self.path)

    def _entry_from_dict(self, raw: dict[str, Any]) -> VersionedMemoryEntry:
        return VersionedMemoryEntry(
            version_id=str(raw.get("version_id", "")),
            parent_version_id=(None if raw.get("parent_version_id") is None else str(raw.get("parent_version_id"))),
            created_at=str(raw.get("created_at", "")),
            payload=dict(raw.get("payload") or {}),
            confidence=float(raw.get("confidence", 0.0)),
        )

    def _next_version_id(self, count: int) -> str:
        return f"v{count + 1:08d}"

    def append(self, payload: dict[str, Any], *, confidence: float) -> VersionedMemoryEntry:
        """Append an immutable entry and advance active head."""
        confidence_value = float(confidence)
        if confidence_value < 0.0 or confidence_value > 1.0:
            raise ValueError("invalid_confidence")

        if self.backend == "sqlite":
            self._init_sqlite()
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                count = int(conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0])
                version_id = self._next_version_id(count)
                head = conn.execute("SELECT head_version_id FROM memory_state WHERE id = 1").fetchone()[0]
                entry = VersionedMemoryEntry(
                    version_id=version_id,
                    parent_version_id=(None if head is None else str(head)),
                    created_at=self._clock(),
                    payload=dict(payload),
                    confidence=confidence_value,
                )
                conn.execute(
                    """
                    INSERT INTO memory_entries(version_id, parent_version_id, created_at, payload_json, confidence)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        entry.version_id,
                        entry.parent_version_id,
                        entry.created_at,
                        canonical_json(entry.payload),
                        entry.confidence,
                    ),
                )
                conn.execute("UPDATE memory_state SET head_version_id = ? WHERE id = 1", (entry.version_id,))
                conn.commit()
                return entry

        state = self._read_json_state()
        entries = list(state.get("entries") or [])
        version_id = self._next_version_id(len(entries))
        entry = VersionedMemoryEntry(
            version_id=version_id,
            parent_version_id=(None if state.get("head_version_id") is None else str(state.get("head_version_id"))),
            created_at=self._clock(),
            payload=dict(payload),
            confidence=confidence_value,
        )
        entries.append(entry.as_dict())
        state["entries"] = entries
        state["head_version_id"] = entry.version_id
        self._write_json_state_atomic(state)
        return entry

    def rollback(self, version_id: str) -> VersionedMemoryEntry:
        target = self.get_version(version_id)
        if target is None:
            raise ValueError("unknown_version_id")

        if self.backend == "sqlite":
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE memory_state SET head_version_id = ? WHERE id = 1", (target.version_id,))
                conn.commit()
            return target

        state = self._read_json_state()
        state["head_version_id"] = target.version_id
        self._write_json_state_atomic(state)
        return target

    def current(self) -> VersionedMemoryEntry | None:
        if self.backend == "sqlite":
            self._init_sqlite()
            with sqlite3.connect(self.sqlite_path) as conn:
                row = conn.execute(
                    """
                    SELECT e.version_id, e.parent_version_id, e.created_at, e.payload_json, e.confidence
                    FROM memory_state s
                    LEFT JOIN memory_entries e ON e.version_id = s.head_version_id
                    WHERE s.id = 1
                    """
                ).fetchone()
            if row is None or row[0] is None:
                return None
            return VersionedMemoryEntry(
                version_id=str(row[0]),
                parent_version_id=(None if row[1] is None else str(row[1])),
                created_at=str(row[2]),
                payload=dict(json.loads(str(row[3]))),
                confidence=float(row[4]),
            )

        state = self._read_json_state()
        head = state.get("head_version_id")
        if head is None:
            return None
        for raw in state.get("entries") or []:
            if isinstance(raw, dict) and raw.get("version_id") == head:
                return self._entry_from_dict(raw)
        return None

    def get_version(self, version_id: str) -> VersionedMemoryEntry | None:
        if self.backend == "sqlite":
            self._init_sqlite()
            with sqlite3.connect(self.sqlite_path) as conn:
                row = conn.execute(
                    """
                    SELECT version_id, parent_version_id, created_at, payload_json, confidence
                    FROM memory_entries
                    WHERE version_id = ?
                    """,
                    (version_id,),
                ).fetchone()
            if row is None:
                return None
            return VersionedMemoryEntry(
                version_id=str(row[0]),
                parent_version_id=(None if row[1] is None else str(row[1])),
                created_at=str(row[2]),
                payload=dict(json.loads(str(row[3]))),
                confidence=float(row[4]),
            )

        for raw in self._read_json_state().get("entries") or []:
            if isinstance(raw, dict) and raw.get("version_id") == version_id:
                return self._entry_from_dict(raw)
        return None

    def iter_history(self, *, ascending: bool = True) -> Iterator[VersionedMemoryEntry]:
        if self.backend == "sqlite":
            self._init_sqlite()
            order = "ASC" if ascending else "DESC"
            with sqlite3.connect(self.sqlite_path) as conn:
                rows = conn.execute(
                    f"""
                    SELECT version_id, parent_version_id, created_at, payload_json, confidence
                    FROM memory_entries
                    ORDER BY seq {order}
                    """
                ).fetchall()
            for row in rows:
                yield VersionedMemoryEntry(
                    version_id=str(row[0]),
                    parent_version_id=(None if row[1] is None else str(row[1])),
                    created_at=str(row[2]),
                    payload=dict(json.loads(str(row[3]))),
                    confidence=float(row[4]),
                )
            return

        entries = [self._entry_from_dict(raw) for raw in self._read_json_state().get("entries") or [] if isinstance(raw, dict)]
        if not ascending:
            entries.reverse()
        yield from entries
