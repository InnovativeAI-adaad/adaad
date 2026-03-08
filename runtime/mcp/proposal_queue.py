# SPDX-License-Identifier: Apache-2.0
"""Append-only, hash-linked queue for MCP proposals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from runtime.api.agents import MutationRequest
from runtime.timeutils import now_iso


DEFAULT_QUEUE_PATH = Path("runtime/mcp/proposal_queue.jsonl")
_ZERO_HASH = "0" * 64


def _canonical_json(value: Dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_entry(prev_hash: str, payload: Dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical_json(payload)).encode("utf-8")).hexdigest()


def _tail_sidecar_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".tail.json")


def _write_tail_sidecar(path: Path, *, tail_hash: str) -> None:
    sidecar_path = _tail_sidecar_path(path)
    tmp_path = sidecar_path.with_suffix(sidecar_path.suffix + ".tmp")
    tmp_path.write_text(_canonical_json({"hash": str(tail_hash)}) + "\n", encoding="utf-8")
    tmp_path.replace(sidecar_path)


def _read_tail_sidecar(path: Path) -> str | None:
    sidecar_path = _tail_sidecar_path(path)
    if not sidecar_path.exists():
        return None
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    tail_hash = payload.get("hash")
    if not isinstance(tail_hash, str):
        return None
    return tail_hash


def _read_tail_hash_fast(path: Path) -> str | None:
    if not path.exists() or path.stat().st_size == 0:
        return _ZERO_HASH
    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        buffer = b""
        while position > 0:
            position -= 1
            handle.seek(position)
            byte = handle.read(1)
            if byte == b"\n":
                if buffer:
                    break
                continue
            buffer = byte + buffer
    if not buffer:
        return _ZERO_HASH
    try:
        payload = json.loads(buffer.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    tail_hash = payload.get("hash")
    if not isinstance(tail_hash, str):
        return None
    return tail_hash


def _tail_hash(path: Path) -> str:
    cached = _read_tail_sidecar(path)
    if cached is None:
        rebuilt = _read_tail_hash_fast(path)
        if rebuilt is None:
            rebuilt = _ZERO_HASH
        _write_tail_sidecar(path, tail_hash=rebuilt)
        return rebuilt
    observed = _read_tail_hash_fast(path)
    if observed is None or observed != cached:
        rebuilt = _read_tail_hash_fast(path)
        if rebuilt is None:
            rebuilt = _ZERO_HASH
        _write_tail_sidecar(path, tail_hash=rebuilt)
        return rebuilt
    return cached


def append_proposal(*, proposal_id: str, request: MutationRequest, path: Path = DEFAULT_QUEUE_PATH) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    prev_hash = _tail_hash(path)
    entry_wo_hash = {
        "ts": now_iso(),
        "event_type": "mcp_proposal_queued",
        "agent_id": "claude-proposal-agent",
        "proposal_id": proposal_id,
        "prev_hash": prev_hash,
        "payload": request.to_dict(),
    }
    digest = _hash_entry(prev_hash, entry_wo_hash)
    entry = dict(entry_wo_hash)
    entry["hash"] = digest
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    _write_tail_sidecar(path, tail_hash=digest)
    return entry


__all__ = ["append_proposal", "DEFAULT_QUEUE_PATH"]
