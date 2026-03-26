# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Ledger journaling utilities.

Performance contract for read APIs:

- ``read_entries`` is an append-order tail read (O(N) in file length to split lines,
  then O(limit) JSON decoding).
- ``read_entries_for_epoch`` narrows reads to an epoch and optional reviewer set.
  Without ``epoch_index`` it scans the decoded tail window once (O(limit)); with a
  precomputed ``epoch_index`` it reuses epoch-partitioned rows and applies only
  reviewer filtering (O(E_epoch)).

All filtered read APIs preserve ledger append order for deterministic replay.
"""

import json
import time
import hashlib
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager
from collections import deque
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol

from runtime import metrics
from runtime.governance.event_taxonomy import validate_event_type_for_agm_step
from runtime.tenancy import payload_in_tenant_scope, tenant_partition_path
from security.ledger import LEDGER_ROOT

ELEMENT_ID = "Water"

LEDGER_FILE = LEDGER_ROOT / "lineage.jsonl"
JOURNAL_PATH = LEDGER_ROOT / "cryovant_journal.jsonl"
GENESIS_PATH = LEDGER_ROOT / "cryovant_journal.genesis.jsonl"
TAIL_STATE_PATH = LEDGER_ROOT / "cryovant_journal.tail.json"
LOCK_PATH = LEDGER_ROOT / "cryovant_journal.lock"

_THREAD_APPEND_LOCK = threading.Lock()
_VERIFIED_TAIL_CACHE_LOCK = threading.Lock()
_VERIFIED_TAIL_CACHE: dict[str, tuple[str, int, int, str]] = {}


@dataclass(frozen=True)
class JournalPaths:
    """Resolved file-system paths for one journal instance."""

    journal_path: Path
    genesis_path: Path
    tail_state_path: Path
    lock_path: Path

# ---------------------------------------------------------------------------
# JOURNAL-CACHE-0  — in-memory tail cache (warm path, M78-01)
#
# Keyed by str(journal_path) so test isolation is automatic: each test that
# redirects JOURNAL_PATH to a unique tmp_path gets its own cache bucket.
#
# Invariants:
#   JOURNAL-CACHE-0       : cache entry advances atomically inside the append
#                           lock — no other thread observes a stale tail.
#   JOURNAL-CACHE-DETERM-0: given identical inputs, append produces identical
#                           chain hashes whether the cache is warm or cold.
#   JOURNAL-ISOLATE-0     : path-keyed bucketing guarantees zero cross-test
#                           state bleed when JOURNAL_PATH is redirected.
# ---------------------------------------------------------------------------
_VERIFIED_TAIL_CACHE: dict[str, tuple[str, int]] = {}


class JournalIntegrityError(RuntimeError):
    """Raised when the Cryovant journal integrity verification fails."""


class JournalRecoveryHook(Protocol):
    """Interface for invoking journal recovery workflows after integrity failures."""

    def on_journal_integrity_failure(self, *, journal_path: Path, error: JournalIntegrityError) -> None:
        """Handle a journal integrity failure (for example, snapshot restore)."""


def ensure_ledger() -> Path:
    """
    Guarantee the ledger directory and file exist.
    """
    LEDGER_ROOT.mkdir(parents=True, exist_ok=True)
    if not LEDGER_FILE.exists():
        LEDGER_FILE.touch()
    return LEDGER_FILE


def _derived_journal_paths(journal_path: Path) -> JournalPaths:
    return JournalPaths(
        journal_path=journal_path,
        genesis_path=journal_path.with_suffix(journal_path.suffix + ".genesis"),
        tail_state_path=journal_path.with_suffix(journal_path.suffix + ".tail"),
        lock_path=journal_path.with_suffix(journal_path.suffix + ".lock"),
    )


def _resolve_journal_paths(
    *,
    journal_path: Path | None = None,
    journal_paths: JournalPaths | None = None,
) -> JournalPaths:
    if journal_path is not None and journal_paths is not None:
        raise ValueError("journal_path_and_journal_paths_are_mutually_exclusive")
    if journal_paths is not None:
        return JournalPaths(
            journal_path=Path(journal_paths.journal_path),
            genesis_path=Path(journal_paths.genesis_path),
            tail_state_path=Path(journal_paths.tail_state_path),
            lock_path=Path(journal_paths.lock_path),
        )
    if journal_path is not None:
        return _derived_journal_paths(Path(journal_path))
    return JournalPaths(
        journal_path=JOURNAL_PATH,
        genesis_path=GENESIS_PATH,
        tail_state_path=TAIL_STATE_PATH,
        lock_path=LOCK_PATH,
    )


def _journal_cache_key(path: Path) -> str:
    return str(path.resolve(strict=False))


def _journal_content_digest(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_verified_tail_cache(path: Path) -> tuple[str, int, int, str] | None:
    with _VERIFIED_TAIL_CACHE_LOCK:
        return _VERIFIED_TAIL_CACHE.get(_journal_cache_key(path))


def _write_verified_tail_cache(path: Path, *, last_hash: str, offset: int) -> None:
    modified_ns = path.stat().st_mtime_ns if path.exists() else 0
    content_digest = _journal_content_digest(path)
    with _VERIFIED_TAIL_CACHE_LOCK:
        _VERIFIED_TAIL_CACHE[_journal_cache_key(path)] = (last_hash, offset, modified_ns, content_digest)


def _clear_verified_tail_cache(path: Path) -> None:
    with _VERIFIED_TAIL_CACHE_LOCK:
        _VERIFIED_TAIL_CACHE.pop(_journal_cache_key(path), None)


def ensure_journal(
    *,
    journal_path: Path | None = None,
    journal_paths: JournalPaths | None = None,
) -> Path:
    """
    Ensure the Cryovant journal exists, seeding from genesis if available.
    """
    paths = _resolve_journal_paths(journal_path=journal_path, journal_paths=journal_paths)
    paths.journal_path.parent.mkdir(parents=True, exist_ok=True)
    if not paths.journal_path.exists():
        if paths.genesis_path.exists():
            paths.journal_path.write_text(paths.genesis_path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            paths.journal_path.touch()
    return paths.journal_path


def write_entry(
    agent_id: str,
    action: str,
    payload: Dict[str, str] | None = None,
    *,
    tenant_context: Mapping[str, str] | None = None,
) -> None:
    ledger_path = tenant_partition_path(LEDGER_FILE, tenant_context)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if not ledger_path.exists():
        ledger_path.touch()
    tenant_payload = dict(payload or {})
    if tenant_context:
        tenant_payload.setdefault("tenant_id", str(tenant_context.get("tenant_id") or ""))
        tenant_payload.setdefault("workspace_id", str(tenant_context.get("workspace_id") or ""))
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agent_id": agent_id,
        "action": action,
        "payload": tenant_payload,
    }
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    metrics.log(event_type="ledger_write", payload=record, level="INFO", element_id=ELEMENT_ID)


def read_entries(limit: int = 50, *, tenant_context: Mapping[str, str] | None = None) -> List[Dict[str, str]]:
    ledger_path = tenant_partition_path(LEDGER_FILE, tenant_context)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if not ledger_path.exists():
        ledger_path.touch()
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    entries: List[Dict[str, str]] = []
    for line in lines[-limit:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if tenant_context and not payload_in_tenant_scope(row, tenant_context):
            continue
        entries.append(row)
    return entries


def read_entries_for_epoch(
    *,
    epoch_id: str,
    reviewer_ids: Iterable[str] | None = None,
    limit: int = 5_000,
    epoch_index: Mapping[str, List[Dict[str, Any]]] | None = None,
) -> List[Dict[str, Any]]:
    """Return ledger rows for one epoch with optional reviewer selection.

    Deterministic ordering is preserved from the underlying lineage ledger append
    sequence. When ``epoch_index`` is provided, this function avoids full-tail
    scans and filters only the pre-partitioned epoch rows.
    """
    normalized_epoch_id = str(epoch_id or "")
    reviewer_selector = {str(rid).strip() for rid in (reviewer_ids or []) if str(rid).strip()}

    if epoch_index is None:
        candidate_entries: Iterable[Dict[str, Any]] = read_entries(limit=limit)
    else:
        candidate_entries = list(epoch_index.get(normalized_epoch_id, []))

    selected: List[Dict[str, Any]] = []
    for entry in candidate_entries:
        if not isinstance(entry, dict):
            continue
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        if str(payload.get("epoch_id") or "") != normalized_epoch_id:
            continue
        if reviewer_selector:
            reviewer_id = str(payload.get("reviewer_id") or "").strip()
            if reviewer_id not in reviewer_selector:
                continue
        selected.append(entry)
    return selected


def read_latest_entry_by_action_and_mutation_id(
    *,
    action: str,
    mutation_id: str,
    limit: int = 5000,
) -> Dict[str, Any] | None:
    """Return the latest matching lineage entry within the most-recent ``limit`` rows."""
    ensure_ledger()
    recent_lines: deque[str] = deque(maxlen=max(limit, 1))
    with LEDGER_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            recent_lines.append(line)

    latest_match: Dict[str, Any] | None = None
    for line in recent_lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if str(entry.get("action") or "") != action:
            continue
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        if str(payload.get("mutation_id") or "") != mutation_id:
            continue
        latest_match = entry
    return latest_match


def _hash_line(prev_hash: str, payload: Dict[str, object]) -> str:
    material = (prev_hash + json.dumps(payload, ensure_ascii=False, sort_keys=True)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _last_hash() -> str:
    last_hash, _ = _validated_last_hash()
    return last_hash


def _raise_integrity_error(
    message: str,
    *,
    path: Path,
    recovery_hook: JournalRecoveryHook | None,
    cause: Exception | None = None,
) -> None:
    error = JournalIntegrityError(message)
    if recovery_hook is not None:
        recovery_hook.on_journal_integrity_failure(journal_path=path, error=error)
    if cause is not None:
        raise error from cause
    raise error


def _scan_chain(
    *,
    path: Path,
    recovery_hook: JournalRecoveryHook | None,
    start_offset: int,
    expected_prev_hash: str,
) -> tuple[str, int]:
    prev_hash = expected_prev_hash
    with path.open("r", encoding="utf-8") as handle:
        if start_offset:
            handle.seek(start_offset)
        for line_no, line in enumerate(handle, start=1):
            entry_text = line.strip()
            if not entry_text:
                continue
            try:
                entry = json.loads(entry_text)
            except json.JSONDecodeError as exc:
                _raise_integrity_error(
                    f"journal_invalid_json:line{line_no}:{exc}",
                    path=path,
                    recovery_hook=recovery_hook,
                    cause=exc,
                )
            if not isinstance(entry, dict):
                _raise_integrity_error(
                    f"journal_malformed_entry:line{line_no}",
                    path=path,
                    recovery_hook=recovery_hook,
                )
            entry_prev_hash = str(entry.get("prev_hash") or "")
            entry_hash = str(entry.get("hash") or "")
            if entry_prev_hash != prev_hash:
                _raise_integrity_error(
                    f"journal_prev_hash_mismatch:line{line_no}",
                    path=path,
                    recovery_hook=recovery_hook,
                )
            payload = {key: value for key, value in entry.items() if key != "hash"}
            computed_hash = _hash_line(prev_hash, payload)
            if entry_hash != computed_hash:
                _raise_integrity_error(
                    f"journal_hash_mismatch:line{line_no}",
                    path=path,
                    recovery_hook=recovery_hook,
                )
            prev_hash = entry_hash
        return prev_hash, handle.tell()


def _read_tail_state(path: Path) -> tuple[str, int] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    last_hash = str(data.get("last_hash") or "")
    offset = data.get("offset")
    if len(last_hash) != 64 or not isinstance(offset, int) or offset < 0:
        return None
    return last_hash, offset


def _write_tail_state(path: Path, *, last_hash: str, offset: int) -> None:
    payload = {"last_hash": last_hash, "offset": offset}
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def _write_verified_tail_state(paths: JournalPaths, *, last_hash: str, offset: int) -> None:
    _write_tail_state(paths.tail_state_path, last_hash=last_hash, offset=offset)
    _write_verified_tail_cache(paths.journal_path, last_hash=last_hash, offset=offset)


def _resume_verified_tail(
    *,
    paths: JournalPaths,
    recovery_hook: JournalRecoveryHook | None,
    state_hash: str,
    state_offset: int,
    verified_mtime_ns: int | None = None,
    verified_content_digest: str | None = None,
) -> tuple[str, int] | None:
    stat_result = paths.journal_path.stat()
    journal_size = stat_result.st_size
    if journal_size < state_offset:
        return None
    if journal_size == state_offset:
        if (
            verified_mtime_ns is not None
            and stat_result.st_mtime_ns == verified_mtime_ns
            and verified_content_digest is not None
            and _journal_content_digest(paths.journal_path) == verified_content_digest
        ):
            _write_verified_tail_cache(paths.journal_path, last_hash=state_hash, offset=state_offset)
            return state_hash, state_offset
        return None
    last_hash, offset = _scan_chain(
        path=paths.journal_path,
        recovery_hook=recovery_hook,
        start_offset=state_offset,
        expected_prev_hash=state_hash,
    )
    _write_verified_tail_state(paths, last_hash=last_hash, offset=offset)
    return last_hash, offset


def _validated_last_hash(
    recovery_hook: JournalRecoveryHook | None = None,
    *,
    journal_path: Path | None = None,
    journal_paths: JournalPaths | None = None,
) -> tuple[str, int]:
    paths = _resolve_journal_paths(journal_path=journal_path, journal_paths=journal_paths)
    ensure_journal(journal_paths=paths)
    default_hash = "0" * 64
    for tail_state in (
        _read_verified_tail_cache(paths.journal_path),
        _read_tail_state(paths.tail_state_path),
    ):
        if tail_state is None:
            continue
        state_hash = tail_state[0]
        state_offset = tail_state[1]
        verified_mtime_ns = tail_state[2] if len(tail_state) > 2 else None
        verified_content_digest = tail_state[3] if len(tail_state) > 3 else None
        try:
            resumed_tail = _resume_verified_tail(
                paths=paths,
                recovery_hook=recovery_hook,
                state_hash=state_hash,
                state_offset=state_offset,
                verified_mtime_ns=verified_mtime_ns,
                verified_content_digest=verified_content_digest,
            )
            if resumed_tail is not None:
                return resumed_tail
        except JournalIntegrityError:
            # Cached tail state is inconsistent with the current journal; fall back
            # to a full rescan from offset 0 below to rebuild a valid tail state.
            _clear_verified_tail_cache(paths.journal_path)
            metrics.log(
                event_type="ledger_journal_tail_recovery_error",
                payload={"journal_path": str(paths.journal_path)},
                level="WARNING",
            )

    last_hash, offset = _scan_chain(
        path=paths.journal_path,
        recovery_hook=recovery_hook,
        start_offset=0,
        expected_prev_hash=default_hash,
    )
    _write_verified_tail_state(paths, last_hash=last_hash, offset=offset)
    return last_hash, offset


@contextmanager
def _journal_append_lock(
    path: Path | None = None,
    *,
    journal_path: Path | None = None,
    journal_paths: JournalPaths | None = None,
):
    resolved_paths = _resolve_journal_paths(
        journal_path=journal_path if journal_path is not None else path,
        journal_paths=journal_paths,
    )
    lock_path = resolved_paths.lock_path
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _THREAD_APPEND_LOCK:
        with lock_path.open("a+", encoding="utf-8") as handle:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def verify_journal_integrity(
    recovery_hook: JournalRecoveryHook | None = None,
    *,
    journal_path: Path | None = None,
    journal_paths: JournalPaths | None = None,
) -> None:
    """Recompute the chain from genesis and validate every stored hash."""
    _validated_last_hash(
        recovery_hook=recovery_hook,
        journal_path=journal_path,
        journal_paths=journal_paths,
    )


def append_tx(
    tx_type: str,
    payload: Dict[str, object],
    tx_id: Optional[str] = None,
    *,
    journal_path: Path | None = None,
    journal_paths: JournalPaths | None = None,
    tenant_context: Mapping[str, str] | None = None,
) -> Dict[str, object]:
    normalized_type = validate_event_type_for_agm_step(
        event_type=tx_type,
        agm_step=payload.get("agm_step") if isinstance(payload, dict) else None,
    )
    if journal_paths is not None:
        paths = _resolve_journal_paths(journal_paths=journal_paths)
    else:
        resolved_journal_path = tenant_partition_path(journal_path or JOURNAL_PATH, tenant_context)
        paths = _resolve_journal_paths(journal_path=resolved_journal_path)
    ensure_journal(journal_paths=paths)
    with _journal_append_lock(journal_paths=paths):
        prev, offset = _validated_last_hash(journal_paths=paths)
        entry = {
            "tx": tx_id or f"TX-{normalized_type}-{time.strftime('%Y%m%d%H%M%S', time.gmtime())}",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": normalized_type,
            "payload": {
                **payload,
                **({"tenant_id": str(tenant_context.get("tenant_id") or ""), "workspace_id": str(tenant_context.get("workspace_id") or "")} if tenant_context else {}),
            },
            "prev_hash": prev,
        }
        # JOURNAL-CACHE-DETERM-0: canonical JSON hash — byte-identical on replay.
        entry["hash"] = _hash_line(prev, entry)
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with paths.journal_path.open("a", encoding="utf-8") as f:
            f.write(line)
        _write_verified_tail_state(
            paths,
            last_hash=entry["hash"],
            offset=offset + len(line.encode("utf-8")),
        )
        return entry


def invalidate_journal_cache(path: "Path | None" = None) -> None:
    """Evict the warm-cache entry for *path* (default: ``JOURNAL_PATH``).

    Primarily a test-isolation helper: call this after redirecting
    ``JOURNAL_PATH`` to a new tmp_path to guarantee the next ``append_tx``
    performs a clean cold-scan rather than reusing a stale entry from a
    previous test bucket that happened to share the same path string.

    Under normal production operation this function is never needed —
    cache entries are path-keyed so distinct journal files never collide.
    """
    key = str(path if path is not None else JOURNAL_PATH)
    _VERIFIED_TAIL_CACHE.pop(key, None)


def project_from_lineage(event: Dict[str, object]) -> Dict[str, object]:
    """Create a journal projection from a lineage-v2 event."""
    payload = dict(event.get("payload") or {})
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agent_id": str(payload.get("agent_id") or "system"),
        "action": str(event.get("type") or "lineage_event"),
        "payload": payload,
    }


def record_rotation_event(action: str, payload: Dict[str, object]) -> None:
    """
    Record a rotation event to both the lineage ledger and cryovant journal.
    """
    write_entry(agent_id="system", action=action, payload=payload)
    append_tx(tx_type=action, payload=payload)


def record_rotation_failure(action: str, payload: Dict[str, object]) -> None:
    """
    Record a rotation failure to both the lineage ledger and cryovant journal.
    """
    write_entry(agent_id="system", action=action, payload=payload)
    append_tx(tx_type=action, payload=payload)


__all__ = [
    "write_entry",
    "read_entries",
    "read_latest_entry_by_action_and_mutation_id",
    "append_tx",
    "invalidate_journal_cache",
    "ensure_ledger",
    "ensure_journal",
    "record_rotation_event",
    "record_rotation_failure",
    "project_from_lineage",
    "verify_journal_integrity",
    "JournalIntegrityError",
    "JournalPaths",
    "JournalRecoveryHook",
    "_VERIFIED_TAIL_CACHE",
]
