# SPDX-License-Identifier: Apache-2.0
"""Append-only, hash-linked queue for MCP proposals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from app.agents.mutation_request import MutationRequest
from runtime.timeutils import now_iso


DEFAULT_QUEUE_PATH = Path("runtime/mcp/proposal_queue.jsonl")


def _canonical_json(value: Dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_entry(prev_hash: str, payload: Dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical_json(payload)).encode("utf-8")).hexdigest()


def _tail_hash(path: Path) -> str:
    if not path.exists():
        return "0" * 64
    prev = "0" * 64
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        prev = str(entry.get("hash") or prev)
    return prev


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
    return entry


__all__ = ["append_proposal", "DEFAULT_QUEUE_PATH"]
