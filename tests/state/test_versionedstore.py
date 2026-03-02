from __future__ import annotations

import json
from pathlib import Path

from memory.versionedstore import VersionedMemoryStore
from runtime.memory_adapter import RuntimeMemoryAdapter


def _fixed_clock() -> str:
    return "2026-01-01T00:00:00Z"


def _build_store(tmp_path: Path, backend: str) -> VersionedMemoryStore:
    return VersionedMemoryStore(
        path=tmp_path / f"memory_{backend}.json",
        sqlite_path=tmp_path / f"memory_{backend}.sqlite",
        backend=backend,
        clock=_fixed_clock,
    )


def test_append_only_and_metadata_integrity_json(tmp_path: Path) -> None:
    store = _build_store(tmp_path, "json")
    first = store.append({"note": "alpha"}, confidence=0.4)
    second = store.append({"note": "beta"}, confidence=0.9)

    assert first.version_id == "v00000001"
    assert first.parent_version_id is None
    assert first.created_at == "2026-01-01T00:00:00Z"
    assert second.version_id == "v00000002"
    assert second.parent_version_id == first.version_id

    history = list(store.iter_history())
    assert [entry.version_id for entry in history] == ["v00000001", "v00000002"]
    assert store.current() is not None
    assert store.current().version_id == "v00000002"


def test_rollback_moves_head_without_destructive_rewrite_json(tmp_path: Path) -> None:
    store = _build_store(tmp_path, "json")
    v1 = store.append({"value": 1}, confidence=0.2)
    v2 = store.append({"value": 2}, confidence=0.3)
    store.rollback(v1.version_id)

    assert store.current() is not None
    assert store.current().version_id == v1.version_id

    history = list(store.iter_history())
    assert [entry.version_id for entry in history] == [v1.version_id, v2.version_id]


def test_sqlite_backend_supports_retrieval_and_rollback(tmp_path: Path) -> None:
    store = _build_store(tmp_path, "sqlite")
    v1 = store.append({"k": "a"}, confidence=0.6)
    v2 = store.append({"k": "b"}, confidence=0.7)
    assert store.get_version(v1.version_id).payload == {"k": "a"}

    store.rollback(v1.version_id)
    assert store.current() is not None
    assert store.current().version_id == v1.version_id
    assert [entry.version_id for entry in store.iter_history(ascending=False)] == [v2.version_id, v1.version_id]


def test_determinism_repeated_runs_json(tmp_path: Path) -> None:
    path_a = tmp_path / "run_a.json"
    path_b = tmp_path / "run_b.json"

    store_a = VersionedMemoryStore(path_a, backend="json", clock=_fixed_clock)
    store_b = VersionedMemoryStore(path_b, backend="json", clock=_fixed_clock)

    for store in (store_a, store_b):
        store.append({"value": 10}, confidence=0.1)
        store.append({"value": 11}, confidence=0.2)

    assert path_a.read_text(encoding="utf-8") == path_b.read_text(encoding="utf-8")


def test_runtime_adapter_contract_passthrough(tmp_path: Path) -> None:
    adapter = RuntimeMemoryAdapter(path=tmp_path / "adapter.json", backend="json")
    appended = adapter.append_memory({"state": "warm"}, confidence=0.8)

    current = adapter.get_current_memory()
    by_id = adapter.get_memory_version(appended["version_id"])

    assert current is not None
    assert current["version_id"] == appended["version_id"]
    assert by_id is not None
    assert by_id["confidence"] == 0.8


def test_json_backend_atomic_file_shape(tmp_path: Path) -> None:
    store = _build_store(tmp_path, "json")
    store.append({"safe": True}, confidence=0.5)

    payload = json.loads((tmp_path / "memory_json.json").read_text(encoding="utf-8"))
    assert payload["head_version_id"] == "v00000001"
    assert len(payload["entries"]) == 1
