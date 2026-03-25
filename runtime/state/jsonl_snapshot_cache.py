# SPDX-License-Identifier: Apache-2.0
"""Short-TTL cache for frequently requested JSONL aggregate snapshots."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from runtime.governance.mutation_ledger import GENESIS_PREV_HASH


@dataclass(frozen=True)
class MutationLedgerSnapshot:
    total_entries: int
    promoted_count: int
    last_hash: str


@dataclass
class _SnapshotCacheEntry:
    expires_at: float
    source_mtime_ns: int
    source_size: int
    snapshot: MutationLedgerSnapshot


_CACHE: dict[Path, _SnapshotCacheEntry] = {}
_CACHE_LOCK = Lock()


def read_mutation_ledger_snapshot(path: Path, *, ttl_seconds: float = 2.0) -> MutationLedgerSnapshot:
    """Return memoized aggregates for mutation ledger reads.

    The cache is invalidated by TTL expiry or source file metadata changes.
    """
    path = path.resolve()
    now = time.monotonic()
    stat = path.stat() if path.exists() else None
    mtime_ns = stat.st_mtime_ns if stat else 0
    size = stat.st_size if stat else 0

    with _CACHE_LOCK:
        cached = _CACHE.get(path)
        if cached and cached.expires_at >= now and cached.source_mtime_ns == mtime_ns and cached.source_size == size:
            return cached.snapshot

    snapshot = _build_snapshot(path)
    with _CACHE_LOCK:
        _CACHE[path] = _SnapshotCacheEntry(
            expires_at=now + max(0.0, ttl_seconds),
            source_mtime_ns=mtime_ns,
            source_size=size,
            snapshot=snapshot,
        )
    return snapshot


def _build_snapshot(path: Path) -> MutationLedgerSnapshot:
    total_entries = 0
    promoted_count = 0
    last_hash = GENESIS_PREV_HASH

    if not path.exists():
        return MutationLedgerSnapshot(total_entries=0, promoted_count=0, last_hash=last_hash)

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            total_entries += 1
            if record.get("entry", {}).get("promoted") is True:
                promoted_count += 1
            candidate_hash = record.get("hash")
            if isinstance(candidate_hash, str) and candidate_hash:
                last_hash = candidate_hash

    return MutationLedgerSnapshot(
        total_entries=total_entries,
        promoted_count=promoted_count,
        last_hash=last_hash,
    )
