# SPDX-License-Identifier: Apache-2.0
"""AdmissionAuditLedger + AdmissionAuditReader — ADAAD Phase 27.

SHA-256 hash-chained append-only JSONL audit ledger for AdmissionDecision
records produced by MutationAdmissionController (Phase 25).

Architectural pattern mirrors PressureAuditLedger (Phase 25 / remote):
- GENESIS_PREV_HASH sentinel: "sha256:" + "0" * 64
- Monotonically increasing sequence numbers
- Each record linked to predecessor via prev_hash → record_hash chain
- chain_verify_on_open=True raises AdmissionAuditChainError on construction
  if chain integrity is violated
- emit() catches ALL failures; logs WARNING; never propagates
- Reader is strictly read-only; no write path

Design invariants
─────────────────
- Append-only: no record is ever overwritten or deleted.
- Fail-closed chain verification: any hash mismatch → AdmissionAuditChainError.
- Emit failure isolation: I/O errors in emit() never surface to callers.
- Deterministic replay: same AdmissionDecision sequence → same chain hashes.
- Timestamp excluded from record_hash (metadata only) — chain is wall-clock
  independent.
- Ledger inactive by default: no path kwarg → no file written.
- GovernanceGate isolation: this module never imports GovernanceGate.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ADMISSION_LEDGER_GENESIS_PREV_HASH: str = "sha256:" + "0" * 64
ADMISSION_LEDGER_VERSION: str = "29.0"  # extended: enforcement verdict fields added Phase 29

# Default path (relative to repo root) — only used when activated
DEFAULT_ADMISSION_LEDGER_PATH: str = "security/ledger/admission_audit.jsonl"


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class AdmissionAuditChainError(RuntimeError):
    """Raised when AdmissionAuditLedger chain verification fails."""

    def __init__(self, message: str, *, sequence: int, detail: str) -> None:
        super().__init__(message)
        self.sequence = sequence
        self.detail = detail


# ---------------------------------------------------------------------------
# Chain helpers
# ---------------------------------------------------------------------------


def _canonical_bytes(obj: dict[str, Any]) -> bytes:
    """Deterministic UTF-8 JSON serialisation (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_prefixed(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _build_record(
    *,
    sequence: int,
    prev_hash: str,
    decision: Any,  # AdmissionDecision
    timestamp_iso: str,
    verdict: Any = None,  # Optional[EnforcerVerdict] — Phase 29
) -> dict[str, Any]:
    """Build a JSONL record from an AdmissionDecision; compute record_hash.

    ``timestamp_iso`` is stored as metadata but excluded from ``record_hash``
    so the hash chain is deterministic: same decision sequence → same hashes,
    regardless of wall-clock time.

    Phase 29: when ``verdict`` (an EnforcerVerdict) is provided, enforcement
    fields are included in the chained payload and covered by record_hash.
    """
    chained: dict[str, Any] = {
        "ledger_version":      ADMISSION_LEDGER_VERSION,
        "sequence":            sequence,
        "prev_hash":           prev_hash,
        "health_score":        round(float(decision.health_score), 8),
        "mutation_risk_score": round(float(decision.mutation_risk_score), 8),
        "admission_band":      decision.admission_band,
        "risk_threshold":      round(float(decision.risk_threshold), 8),
        "admitted":            bool(decision.admitted),
        "admits_all":          bool(decision.admits_all),
        "epoch_paused":        bool(decision.epoch_paused),
        "decision_digest":     decision.decision_digest,
        "controller_version":  decision.controller_version,
        # Phase 29 enforcement fields — present when verdict is provided
        "enforcement_present":   verdict is not None,
        "escalation_mode":       verdict.escalation_mode if verdict is not None else None,
        "blocked":               bool(verdict.blocked) if verdict is not None else None,
        "block_reason":          verdict.block_reason if verdict is not None else None,
        "verdict_digest":        verdict.verdict_digest if verdict is not None else None,
        "enforcer_version":      verdict.enforcer_version if verdict is not None else None,
    }
    record_hash = _sha256_prefixed(_canonical_bytes(chained))
    body = dict(chained)
    body["timestamp_iso"] = timestamp_iso
    body["record_hash"] = record_hash
    return body


def _verify_existing_chain(path: Path) -> None:
    """Verify hash chain of an existing ledger file.

    Raises ``AdmissionAuditChainError`` on any integrity violation.
    Returns silently when chain is intact.
    """
    prev_hash = ADMISSION_LEDGER_GENESIS_PREV_HASH
    expected_seq = 0

    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise AdmissionAuditChainError(
                    f"Unparseable record at expected sequence {expected_seq}",
                    sequence=expected_seq,
                    detail=str(exc),
                )

            seq = record.get("sequence", -1)
            if seq != expected_seq:
                raise AdmissionAuditChainError(
                    f"Sequence mismatch: expected {expected_seq}, got {seq}",
                    sequence=expected_seq,
                    detail=f"got sequence={seq}",
                )

            stored_prev = record.get("prev_hash", "")
            if stored_prev != prev_hash:
                raise AdmissionAuditChainError(
                    f"prev_hash mismatch at sequence {seq}",
                    sequence=seq,
                    detail=f"expected {prev_hash!r}, got {stored_prev!r}",
                )

            stored_hash = record.pop("record_hash", None)
            record.pop("timestamp_iso", None)   # metadata — excluded from hash
            computed = _sha256_prefixed(_canonical_bytes(record))
            if stored_hash != computed:
                raise AdmissionAuditChainError(
                    f"record_hash mismatch at sequence {seq}",
                    sequence=seq,
                    detail=f"stored={stored_hash!r}, computed={computed!r}",
                )

            prev_hash = stored_hash
            expected_seq += 1


# ---------------------------------------------------------------------------
# AdmissionAuditLedger
# ---------------------------------------------------------------------------


class AdmissionAuditLedger:
    """Append-only SHA-256 hash-chained JSONL ledger for AdmissionDecision.

    Parameters
    ----------
    path:
        Path to the JSONL ledger file.  When ``None`` the ledger is inactive:
        ``emit()`` is a no-op and no file is created.
    chain_verify_on_open:
        When ``True`` (default) and the file already exists, its chain is
        verified before any new records are appended.  Construction raises
        ``AdmissionAuditChainError`` on integrity violation.

    Usage
    -----
    ::

        ledger = AdmissionAuditLedger(path="security/ledger/admission_audit.jsonl")
        ledger.emit(decision)   # fail-safe; never raises

    GovernanceGate isolation
    ────────────────────────
    This module never imports ``GovernanceGate``.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        chain_verify_on_open: bool = True,
    ) -> None:
        self._path: Path | None = Path(path) if path is not None else None
        self._sequence: int = 0
        self._prev_hash: str = ADMISSION_LEDGER_GENESIS_PREV_HASH

        if self._path is None:
            return  # inactive ledger

        if self._path.exists():
            if chain_verify_on_open:
                _verify_existing_chain(self._path)
            # Resume sequence from existing records
            with self._path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        rec = json.loads(raw_line)
                        self._prev_hash = rec.get("record_hash", self._prev_hash)
                        self._sequence = rec.get("sequence", self._sequence - 1) + 1
                    except json.JSONDecodeError:
                        pass  # chain verify already caught bad lines above
        else:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def emit(self, decision: Any, *, verdict: Any = None) -> None:  # AdmissionDecision[, EnforcerVerdict]
        """Append one ``AdmissionDecision`` (and optionally an ``EnforcerVerdict``) to the ledger.

        Phase 29: when ``verdict`` is supplied, enforcement fields
        (escalation_mode, blocked, block_reason, verdict_digest, enforcer_version)
        are included in the chained JSONL record and covered by record_hash.

        Fail-safe: any I/O or serialisation error is logged and swallowed.
        The caller is never interrupted by ledger failures.
        """
        if self._path is None:
            return  # inactive

        try:
            ts = datetime.now(tz=timezone.utc).isoformat()
            record = _build_record(
                sequence=self._sequence,
                prev_hash=self._prev_hash,
                decision=decision,
                timestamp_iso=ts,
                verdict=verdict,
            )
            line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line)
            self._prev_hash = record["record_hash"]
            self._sequence += 1
        except Exception as exc:  # pragma: no cover
            log.warning("AdmissionAuditLedger.emit failed (silenced): %s", exc)

    def verify_chain(self) -> bool:
        """Return ``True`` if chain is intact; ``False`` if ledger is inactive."""
        if self._path is None or not self._path.exists():
            return False
        _verify_existing_chain(self._path)   # raises on violation
        return True

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def path(self) -> Path | None:
        return self._path


# ---------------------------------------------------------------------------
# AdmissionAuditReader
# ---------------------------------------------------------------------------


class AdmissionAuditReader:
    """Read-only analytics surface over an AdmissionAuditLedger JSONL file.

    No write path.  All methods are idempotent.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def _all_records(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        records = []
        with self._path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if raw_line:
                    try:
                        records.append(json.loads(raw_line))
                    except json.JSONDecodeError:
                        pass
        return records

    def history(
        self,
        *,
        limit: int | None = None,
        band_filter: str | None = None,
        admitted_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return records in chronological order with optional filtering.

        Parameters
        ----------
        limit:
            Maximum number of records to return (most recent).
        band_filter:
            If set, only records with ``admission_band == band_filter`` are
            returned.  Case-sensitive.
        admitted_only:
            If ``True``, only records where ``admitted == True`` are returned.
        """
        records = self._all_records()
        if band_filter is not None:
            records = [r for r in records if r.get("admission_band") == band_filter]
        if admitted_only:
            records = [r for r in records if r.get("admitted") is True]
        if limit is not None:
            records = records[-limit:]
        return records

    def band_frequency(self) -> dict[str, int]:
        """Return count of records per admission_band."""
        freq: dict[str, int] = {}
        for rec in self._all_records():
            band = rec.get("admission_band", "unknown")
            freq[band] = freq.get(band, 0) + 1
        return freq

    def admission_rate(self) -> float:
        """Return overall admitted / total ratio; 1.0 when history is empty."""
        records = self._all_records()
        if not records:
            return 1.0
        admitted = sum(1 for r in records if r.get("admitted") is True)
        return admitted / len(records)

    def verify_chain(self) -> bool:
        """Return ``True`` if chain is intact; raise on violation."""
        if not self._path.exists():
            return False
        _verify_existing_chain(self._path)
        return True

    # ------------------------------------------------------------------
    # Phase 29 — Enforcement analytics
    # ------------------------------------------------------------------

    def blocked_count(self) -> int:
        """Return count of records where ``blocked == True``."""
        return sum(1 for r in self._all_records() if r.get("blocked") is True)

    def enforcement_rate(self) -> float:
        """Return fraction of records that carried enforcement verdict data.

        Returns 0.0 when history is empty.
        """
        records = self._all_records()
        if not records:
            return 0.0
        with_enforcement = sum(1 for r in records if r.get("enforcement_present") is True)
        return with_enforcement / len(records)

    def escalation_mode_breakdown(self) -> dict[str, int]:
        """Return count of records per escalation_mode value.

        Records without enforcement data (``enforcement_present=False``) are
        counted under the key ``"none"``.
        """
        breakdown: dict[str, int] = {}
        for rec in self._all_records():
            mode = rec.get("escalation_mode") if rec.get("enforcement_present") else "none"
            key = mode if mode is not None else "none"
            breakdown[key] = breakdown.get(key, 0) + 1
        return breakdown

    def history_with_enforcement(
        self,
        *,
        limit: int | None = None,
        blocked_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return records that contain enforcement verdict fields.

        Parameters
        ----------
        limit:
            Maximum number of records to return (most recent).
        blocked_only:
            If ``True``, only records where ``blocked == True`` are returned.
        """
        records = [r for r in self._all_records() if r.get("enforcement_present") is True]
        if blocked_only:
            records = [r for r in records if r.get("blocked") is True]
        if limit is not None:
            records = records[-limit:]
        return records
