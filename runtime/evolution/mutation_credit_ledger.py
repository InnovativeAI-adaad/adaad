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

    def _tail_sidecar_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".tail.json")

    def _idempotency_index_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".idempotency.jsonl")

    def _write_tail_sidecar(self, *, record_hash: str, entries: int) -> None:
        payload = {"record_hash": str(record_hash), "entries": int(entries)}
        sidecar_path = self._tail_sidecar_path()
        tmp_path = sidecar_path.with_suffix(sidecar_path.suffix + ".tmp")
        tmp_path.write_text(_canonical_json(payload) + "\n", encoding="utf-8")
        tmp_path.replace(sidecar_path)

    def _read_tail_sidecar(self) -> Dict[str, Any] | None:
        sidecar_path = self._tail_sidecar_path()
        if not sidecar_path.exists():
            return None
        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(payload, dict):
            return None
        record_hash = payload.get("record_hash")
        entries = payload.get("entries")
        if not isinstance(record_hash, str) or not isinstance(entries, int) or entries < 0:
            return None
        return {"record_hash": record_hash, "entries": entries}

    def _read_last_record_hash_fast(self) -> str | None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return ZERO_HASH
        with self.path.open("rb") as handle:
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
            return ZERO_HASH
        try:
            payload = json.loads(buffer.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        record_hash = payload.get("record_hash")
        if not isinstance(record_hash, str):
            return None
        return record_hash

    def _append_idempotency_index(self, *, idempotency_key: str, record_hash: str) -> None:
        row = {"idempotency_key": str(idempotency_key), "record_hash": str(record_hash)}
        with self._idempotency_index_path().open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(row) + "\n")

    def _read_idempotency_index(self) -> Dict[str, str] | None:
        path = self._idempotency_index_path()
        if not path.exists():
            return None
        mapping: Dict[str, str] = {}
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                row = json.loads(stripped)
                if not isinstance(row, dict):
                    return None
                key = row.get("idempotency_key")
                value = row.get("record_hash")
                if not isinstance(key, str) or not isinstance(value, str):
                    return None
                mapping[key] = value
        except (json.JSONDecodeError, OSError):
            return None
        return mapping

    def _rebuild_indexes(self) -> tuple[Dict[str, str], Dict[str, Any]]:
        rows = _read_jsonl(self.path)
        idempotency: Dict[str, str] = {}
        last_hash = ZERO_HASH
        for row in rows:
            event = row.get("event", {})
            if isinstance(event, dict):
                key = event.get("idempotency_key")
                record_hash = row.get("record_hash")
                if isinstance(key, str) and isinstance(record_hash, str):
                    idempotency[key] = record_hash
            candidate = row.get("record_hash")
            if isinstance(candidate, str):
                last_hash = candidate
        idempotency_path = self._idempotency_index_path()
        tmp_index = idempotency_path.with_suffix(idempotency_path.suffix + ".tmp")
        with tmp_index.open("w", encoding="utf-8") as handle:
            for key in sorted(idempotency):
                handle.write(_canonical_json({"idempotency_key": key, "record_hash": idempotency[key]}) + "\n")
        tmp_index.replace(idempotency_path)
        sidecar = {"record_hash": last_hash, "entries": len(rows)}
        self._write_tail_sidecar(record_hash=last_hash, entries=len(rows))
        return idempotency, sidecar

    def _load_indexes(self) -> tuple[Dict[str, str], Dict[str, Any]]:
        tail = self._read_tail_sidecar()
        idempotency = self._read_idempotency_index()
        if tail is None or idempotency is None:
            return self._rebuild_indexes()
        fast_hash = self._read_last_record_hash_fast()
        if fast_hash is None or fast_hash != tail.get("record_hash"):
            return self._rebuild_indexes()
        return idempotency, tail

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

        idempotency_index, tail = self._load_indexes()
        existing_hash = idempotency_index.get(event_payload["idempotency_key"])
        if existing_hash is not None:
            for row in _read_jsonl(self.path):
                if row.get("record_hash") != existing_hash:
                    continue
                existing = row.get("event", {})
                if _canonical_json(existing) != _canonical_json(event_payload):
                    raise MutationCreditLedgerError("idempotency_key_conflict")
                return row
            self._rebuild_indexes()
            return self.append(event)

        prev_hash = str(tail["record_hash"])
        record = {
            "event": event_payload,
            "prev_hash": prev_hash,
        }
        record_hash = _sha(record)
        record["record_hash"] = record_hash

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(record) + "\n")
        self._append_idempotency_index(idempotency_key=event_payload["idempotency_key"], record_hash=record_hash)
        self._write_tail_sidecar(record_hash=record_hash, entries=int(tail.get("entries", 0)) + 1)
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

        indexed, tail = self._load_indexes()
        expected: Dict[str, str] = {}
        for row in rows:
            event = row.get("event", {})
            if not isinstance(event, dict):
                continue
            key = event.get("idempotency_key")
            record_hash = row.get("record_hash")
            if isinstance(key, str) and isinstance(record_hash, str):
                expected[key] = record_hash
        if indexed != expected or tail.get("record_hash") != prev_hash or int(tail.get("entries", -1)) != len(rows):
            return {"ok": False, "reason": "index_mismatch", "index": len(rows)}
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
