# SPDX-License-Identifier: Apache-2.0
"""Append-only, replay-verifiable mutation credit ledger.

The ledger stores deterministic JSONL records chained by sha256 hashes. It supports
idempotent appends via `idempotency_key` and deterministic balance replay.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


ZERO_HASH = "sha256:" + ("0" * 64)


@dataclass(frozen=True)
class MutationCreditEvent:
    agent_id: str
    mutation_id: str
    credits_delta: int
    budget_source: str
    idempotency_key: str
    details: Mapping[str, Any] | None = None


class MutationCreditLedgerError(RuntimeError):
    """Raised when ledger integrity or event schema validation fails."""


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _normalize(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, set):
        normalized = [_normalize(v) for v in value]
        return sorted(normalized, key=lambda item: _canonical_json(item))
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


class MutationCreditLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: MutationCreditEvent) -> Dict[str, Any]:
        event_payload = {
            "agent_id": str(event.agent_id),
            "mutation_id": str(event.mutation_id),
            "credits_delta": int(event.credits_delta),
            "budget_source": str(event.budget_source),
            "idempotency_key": str(event.idempotency_key),
            "details": _normalize(dict(event.details or {})),
        }
        if not event_payload["idempotency_key"]:
            raise MutationCreditLedgerError("idempotency_key_required")

        rows = _read_jsonl(self.path)
        for row in rows:
            existing = row.get("event", {})
            if existing.get("idempotency_key") == event_payload["idempotency_key"]:
                if _canonical_json(existing) != _canonical_json(event_payload):
                    raise MutationCreditLedgerError("idempotency_key_conflict")
                return row

        prev_hash = rows[-1]["record_hash"] if rows else ZERO_HASH
        record = {
            "event": event_payload,
            "prev_hash": prev_hash,
        }
        record_hash = _sha(record)
        record["record_hash"] = record_hash

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(record) + "\n")
        return record

    def verify_integrity(self) -> Dict[str, Any]:
        rows = _read_jsonl(self.path)
        prev_hash = ZERO_HASH
        for idx, row in enumerate(rows):
            if row.get("prev_hash") != prev_hash:
                return {"ok": False, "reason": "prev_hash_mismatch", "index": idx}
            hashed = _sha({"event": row.get("event", {}), "prev_hash": row.get("prev_hash")})
            if row.get("record_hash") != hashed:
                return {"ok": False, "reason": "record_hash_mismatch", "index": idx}
            prev_hash = row["record_hash"]
        return {"ok": True, "entries": len(rows), "last_hash": prev_hash}

    def replay_balances(self) -> Dict[str, int]:
        verification = self.verify_integrity()
        if not verification.get("ok"):
            raise MutationCreditLedgerError(f"integrity_failure:{verification.get('reason')}")
        balances: Dict[str, int] = {}
        for row in _read_jsonl(self.path):
            event = row["event"]
            agent_id = str(event["agent_id"])
            balances[agent_id] = int(balances.get(agent_id, 0)) + int(event["credits_delta"])
        return balances

    def events(self) -> Iterable[Dict[str, Any]]:
        return tuple(_read_jsonl(self.path))


__all__ = [
    "MutationCreditEvent",
    "MutationCreditLedger",
    "MutationCreditLedgerError",
    "ZERO_HASH",
]
