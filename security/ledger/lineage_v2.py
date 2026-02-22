# SPDX-License-Identifier: Apache-2.0
"""Deterministic lineage chain helpers for governance validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from runtime import ROOT_DIR

LINEAGE_V2_PATH = ROOT_DIR / "security" / "ledger" / "lineage_v2.jsonl"


class LineageResolutionError(RuntimeError):
    """Raised when lineage chain resolution fails."""


def _canonical_json(value: Dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_entry(prev_hash: str, payload: Dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical_json(payload)).encode("utf-8")).hexdigest()


def _agent_id(entry: Dict[str, Any]) -> str:
    payload = dict(entry.get("payload") or {})
    certificate = dict(payload.get("certificate") or {})
    return str(payload.get("agent_id") or certificate.get("agent_id") or "")


def _mutation_id(entry: Dict[str, Any]) -> str:
    payload = dict(entry.get("payload") or {})
    certificate = dict(payload.get("certificate") or {})
    return str(payload.get("mutation_id") or payload.get("bundle_id") or certificate.get("mutation_id") or certificate.get("bundle_id") or "")


def _parent_mutation_id(entry: Dict[str, Any]) -> str:
    payload = dict(entry.get("payload") or {})
    certificate = dict(payload.get("certificate") or {})
    lineage = dict(payload.get("lineage") or {})
    return str(
        payload.get("parent_mutation_id")
        or payload.get("parent_bundle_id")
        or certificate.get("parent_mutation_id")
        or certificate.get("parent_bundle_id")
        or lineage.get("parent_mutation_id")
        or ""
    )


def resolve_chain(agent_id: str, *, ledger_path: Path | None = None) -> List[str] | None:
    """Resolve lineage hash chain ending at latest mutation for agent_id if available."""
    path = ledger_path or LINEAGE_V2_PATH
    if not path.exists():
        return None

    entries: List[Dict[str, Any]] = []
    prev_hash = "0" * 64
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        entry = json.loads(text)
        if not isinstance(entry, dict):
            raise LineageResolutionError("lineage_entry_malformed")
        payload = {k: v for k, v in entry.items() if k != "hash"}
        computed = _hash_entry(prev_hash, payload)
        if str(entry.get("prev_hash") or "") != prev_hash or str(entry.get("hash") or "") != computed:
            raise LineageResolutionError("lineage_hash_mismatch")
        prev_hash = computed
        entries.append(entry)

    if not entries:
        return None

    by_mutation: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        mutation_id = _mutation_id(entry)
        if mutation_id:
            by_mutation[mutation_id] = entry

    normalized_agent_id = str(agent_id or "").strip()
    if normalized_agent_id:
        tail = next((entry for entry in reversed(entries) if _mutation_id(entry) and _agent_id(entry) == normalized_agent_id), None)
    else:
        tail = next((entry for entry in reversed(entries) if _mutation_id(entry)), None)
    if tail is None:
        return None

    chain: List[str] = []
    cursor = tail
    while cursor is not None:
        chain.append(str(cursor.get("hash") or ""))
        parent_id = _parent_mutation_id(cursor)
        cursor = by_mutation.get(parent_id) if parent_id else None

    chain.reverse()
    if chain and chain[0] != entries[0].get("hash"):
        chain.insert(0, str(entries[0].get("hash") or ""))
    return chain


__all__ = ["LineageResolutionError", "LINEAGE_V2_PATH", "resolve_chain"]
