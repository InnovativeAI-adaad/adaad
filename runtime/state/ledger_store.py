# SPDX-License-Identifier: Apache-2.0
"""
Module: ledger_store
Purpose: Provide deterministic append-only scoring ledger persistence for JSON/SQLite backends.
Author: ADAAD / InnovativeAI-adaad
Integration points:
  - Imports from: runtime.governance.foundation + deterministic filesystem
  - Consumed by: runtime.evolution.scoring_ledger and migration helpers
  - Governance impact: medium — ledger backend selected by governance policy state_backend
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from runtime.evolution.agm_event import AGMEventEnvelope, AGMEventValidationError, validate_event_envelope
from runtime.evolution.event_signing import EventVerifier, SignatureBundle
from runtime.governance.deterministic_filesystem import read_file_deterministic
from runtime.governance.foundation import canonical_json, sha256_prefixed_digest

_ZERO_HASH = "sha256:" + ("0" * 64)


class ScoringLedgerStore:
    def __init__(self, path: Path, *, sqlite_path: Path | None = None, backend: str = "json") -> None:
        if backend not in {"json", "sqlite"}:
            raise ValueError("invalid_state_backend")
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = sqlite_path or path.with_suffix(".sqlite")
        self.backend = backend
        if self.backend == "json" and not self.path.exists():
            self.path.touch()
        if self.backend == "sqlite":
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scoring_ledger (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    record_hash TEXT NOT NULL UNIQUE,
                    signature TEXT NOT NULL,
                    signing_key_id TEXT NOT NULL,
                    signature_algorithm TEXT NOT NULL
                )
                """
            )

    def _iter_json_records(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in read_file_deterministic(self.path).splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                rows.append(payload)
        return rows

    def iter_records(self) -> list[dict[str, Any]]:
        if self.backend == "sqlite":
            with sqlite3.connect(self.sqlite_path) as conn:
                rows = conn.execute(
                    "SELECT event_json, prev_hash, record_hash, signature, signing_key_id, signature_algorithm FROM scoring_ledger ORDER BY seq ASC"
                ).fetchall()
            return [
                {
                    "event": json.loads(event_json),
                    "prev_hash": prev_hash,
                    "record_hash": record_hash,
                    "signature": signature,
                    "signing_key_id": signing_key_id,
                    "signature_algorithm": signature_algorithm,
                }
                for event_json, prev_hash, record_hash, signature, signing_key_id, signature_algorithm in rows
            ]
        return self._iter_json_records()

    def last_hash(self) -> str:
        last = _ZERO_HASH
        for record in self.iter_records():
            candidate = record.get("record_hash")
            if isinstance(candidate, str):
                last = candidate
        return last

    @staticmethod
    def canonical_event_content(envelope: AGMEventEnvelope) -> str:
        payload = envelope.as_dict()
        payload.pop("signature", None)
        payload.pop("signing_key_id", None)
        payload.pop("signature_algorithm", None)
        return canonical_json(payload)

    def append_event(self, envelope: AGMEventEnvelope, *, verifier: EventVerifier) -> dict[str, Any]:
        try:
            validate_event_envelope(envelope)
        except AGMEventValidationError as exc:
            raise ValueError(f"invalid_event_envelope:{exc}") from exc

        signed = SignatureBundle(
            signature=envelope.signature,
            signing_key_id=envelope.signing_key_id,
            algorithm=envelope.signature_algorithm,
        )
        if not verifier.verify(message=self.canonical_event_content(envelope), signature=signed):
            raise ValueError("invalid_event_signature")

        prev_hash = self.last_hash()
        record = {
            "event": envelope.as_dict(),
            "prev_hash": prev_hash,
            "signature": envelope.signature,
            "signing_key_id": envelope.signing_key_id,
            "signature_algorithm": envelope.signature_algorithm,
        }
        record["record_hash"] = sha256_prefixed_digest(canonical_json(record))

        if self.backend == "sqlite":
            self._init_sqlite()
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.execute(
                    """
                    INSERT INTO scoring_ledger(
                        event_json,
                        prev_hash,
                        record_hash,
                        signature,
                        signing_key_id,
                        signature_algorithm
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_json(record["event"]),
                        record["prev_hash"],
                        record["record_hash"],
                        record["signature"],
                        record["signing_key_id"],
                        record["signature_algorithm"],
                    ),
                )
            return record

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        return record

    def verify_chain(self, verifier: EventVerifier | None = None) -> dict[str, Any]:
        if verifier is None:
            return {"ok": False, "count": 0, "error": "signature_verifier_missing", "index": 0}

        expected_prev = _ZERO_HASH
        records = self.iter_records()
        for index, record in enumerate(records):
            observed_prev = record.get("prev_hash")
            if observed_prev != expected_prev:
                return {"ok": False, "count": index, "error": "prev_hash_mismatch", "index": index}

            event_payload = record.get("event")
            if not isinstance(event_payload, dict):
                return {"ok": False, "count": index, "error": "invalid_event_payload", "index": index}

            try:
                envelope = AGMEventEnvelope(
                    schema_version=str(event_payload.get("schema_version", "")),
                    event_id=str(event_payload.get("event_id", "")),
                    event_type=str(event_payload.get("event_type", "")),
                    emitted_at=str(event_payload.get("emitted_at", "")),
                    payload=dict(event_payload.get("payload") or {}),
                    signature=str(event_payload.get("signature", "")),
                    signing_key_id=str(event_payload.get("signing_key_id", "")),
                    signature_algorithm=str(event_payload.get("signature_algorithm", "")),
                )
                validate_event_envelope(envelope)
            except (ValueError, AGMEventValidationError):
                return {"ok": False, "count": index, "error": "invalid_event_envelope", "index": index}

            signature = SignatureBundle(
                signature=envelope.signature,
                signing_key_id=envelope.signing_key_id,
                algorithm=envelope.signature_algorithm,
            )
            if not verifier.verify(message=self.canonical_event_content(envelope), signature=signature):
                return {"ok": False, "count": index, "error": "signature_invalid", "index": index}

            computed_record = {
                "event": envelope.as_dict(),
                "prev_hash": observed_prev,
                "signature": envelope.signature,
                "signing_key_id": envelope.signing_key_id,
                "signature_algorithm": envelope.signature_algorithm,
            }
            expected_hash = sha256_prefixed_digest(canonical_json(computed_record))
            if record.get("record_hash") != expected_hash:
                return {"ok": False, "count": index, "error": "record_hash_mismatch", "index": index}
            expected_prev = expected_hash
        return {"ok": True, "count": len(records), "tip_hash": expected_prev}

    def append(self, scoring_result: dict[str, Any]) -> dict[str, Any]:
        raise TypeError("append_removed_use_append_event")
