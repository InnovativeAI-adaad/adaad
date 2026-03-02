# SPDX-License-Identifier: Apache-2.0
"""Runtime adapter that routes memory operations through the versioned memory store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from memory.versionedstore import VersionedMemoryStore


class RuntimeMemoryAdapter:
    """Compatibility adapter for runtime memory call contracts.

    Rationale for mutation logic:
      - All writes are delegated to VersionedMemoryStore.append/rollback so memory state
        remains append-only and rollback only moves the active head pointer.
      - Adapter keeps a narrow translation layer to preserve existing runtime-facing calls.
    """

    def __init__(
        self,
        path: Path,
        *,
        sqlite_path: Path | None = None,
        backend: str = "json",
    ) -> None:
        self._store = VersionedMemoryStore(path=path, sqlite_path=sqlite_path, backend=backend)

    def append_memory(self, payload: dict[str, Any], *, confidence: float) -> dict[str, Any]:
        return self._store.append(payload, confidence=confidence).as_dict()

    def rollback_memory(self, version_id: str) -> dict[str, Any]:
        return self._store.rollback(version_id).as_dict()

    def get_current_memory(self) -> dict[str, Any] | None:
        current = self._store.current()
        return None if current is None else current.as_dict()

    def get_memory_version(self, version_id: str) -> dict[str, Any] | None:
        entry = self._store.get_version(version_id)
        return None if entry is None else entry.as_dict()

    def scan_memory_history(self, *, ascending: bool = True) -> list[dict[str, Any]]:
        return [entry.as_dict() for entry in self._store.iter_history(ascending=ascending)]

    # Compatibility aliases for prior runtime integrations.
    def append(self, payload: dict[str, Any], *, confidence: float) -> dict[str, Any]:
        return self.append_memory(payload, confidence=confidence)

    def rollback(self, version_id: str) -> dict[str, Any]:
        return self.rollback_memory(version_id)

    def current(self) -> dict[str, Any] | None:
        return self.get_current_memory()

    def get(self, version_id: str) -> dict[str, Any] | None:
        return self.get_memory_version(version_id)

    def history(self, *, ascending: bool = True) -> list[dict[str, Any]]:
        return self.scan_memory_history(ascending=ascending)
