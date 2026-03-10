# SPDX-License-Identifier: Apache-2.0
"""ThreatScanLedger + ThreatScanReader — ADAAD Phase 30.

SHA-256 hash-chained append-only JSONL audit ledger for ThreatMonitor scan
results.  Closes the gap between ThreatMonitor's deterministic scan output
and the audit trail that operators need to triage escalation patterns over time.

Architectural pattern mirrors AdmissionAuditLedger (Phase 27) and
PressureAuditLedger:
- GENESIS_PREV_HASH sentinel: "sha256:" + "0" * 64
- Monotonically increasing sequence numbers
- Each record linked to predecessor via prev_hash → record_hash chain
- chain_verify_on_open=True raises ThreatScanChainError on construction
  if chain integrity is violated
- emit() catches ALL failures; logs WARNING; never propagates
- Reader is strictly read-only; no write path

Design invariants
─────────────────
- Append-only: no record is ever overwritten or deleted.
- Fail-closed chain verification: any hash mismatch → ThreatScanChainError.
- Emit failure isolation: I/O errors in emit() never surface to callers.
- Deterministic replay: same scan sequence → same chain hashes.
- Timestamp excluded from record_hash — chain is wall-clock independent.
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

THREAT_SCAN_LEDGER_GENESIS_PREV_HASH: str = "sha256:" + "0" * 64
THREAT_SCAN_LEDGER_VERSION: str = "30.0"

DEFAULT_THREAT_SCAN_LEDGER_PATH: str = "security/ledger/threat_scan_audit.jsonl"

VALID_RECOMMENDATIONS = frozenset({"continue", "escalate", "halt"})
VALID_RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class ThreatScanChainError(RuntimeError):
    """Raised when ThreatScanLedger chain verification fails."""

    def __init__(self, message: str, *, sequence: int, detail: str) -> None:
        super().__init__(message)
        self.sequence = sequence
        self.detail = detail


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256_prefixed(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _build_scan_record(
    *,
    sequence: int,
    prev_hash: str,
    scan: dict[str, Any],
    timestamp_iso: str,
) -> dict[str, Any]:
    """Build a JSONL record from a ThreatMonitor scan result dict.

    ``timestamp_iso`` is stored as metadata but excluded from ``record_hash``
    so the chain is deterministic regardless of wall-clock time.

    Expected ``scan`` keys (all optional — missing keys default to safe values):
        epoch_id, mutation_count, recommendation, risk_score, risk_level,
        triggered_count, finding_count, findings, scan_digest.
    """
    findings = list(scan.get("findings") or [])
    triggered = [f for f in findings if f.get("triggered")]

    chained: dict[str, Any] = {
        "ledger_version":   THREAT_SCAN_LEDGER_VERSION,
        "sequence":         sequence,
        "prev_hash":        prev_hash,
        "epoch_id":         str(scan.get("epoch_id") or ""),
        "mutation_count":   int(scan.get("mutation_count") or 0),
        "recommendation":   str(scan.get("recommendation") or "continue"),
        "risk_score":       round(float(scan.get("risk", {}).get("score") if isinstance(scan.get("risk"), dict) else scan.get("risk_score") or 0.0), 8),
        "risk_level":       str(scan.get("risk", {}).get("risk_level") if isinstance(scan.get("risk"), dict) else scan.get("risk_level") or "low"),
        "triggered_count":  len(triggered),
        "finding_count":    len(findings),
        "scan_digest":      str(scan.get("scan_digest") or ""),
    }
    record_hash = _sha256_prefixed(_canonical_bytes(chained))
    body = dict(chained)
    body["timestamp_iso"] = timestamp_iso
    body["record_hash"] = record_hash
    return body


def _verify_existing_chain(path: Path) -> None:
    """Verify hash chain. Raises ThreatScanChainError on any integrity violation."""
    prev_hash = THREAT_SCAN_LEDGER_GENESIS_PREV_HASH
    expected_seq = 0

    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ThreatScanChainError(
                    f"Unparseable record at expected sequence {expected_seq}",
                    sequence=expected_seq,
                    detail=str(exc),
                )

            seq = record.get("sequence", -1)
            if seq != expected_seq:
                raise ThreatScanChainError(
                    f"Sequence mismatch: expected {expected_seq}, got {seq}",
                    sequence=expected_seq,
                    detail=f"got sequence={seq}",
                )

            stored_prev = record.get("prev_hash", "")
            if stored_prev != prev_hash:
                raise ThreatScanChainError(
                    f"prev_hash mismatch at sequence {seq}",
                    sequence=seq,
                    detail=f"expected {prev_hash!r}, got {stored_prev!r}",
                )

            stored_hash = record.pop("record_hash", None)
            record.pop("timestamp_iso", None)
            computed = _sha256_prefixed(_canonical_bytes(record))
            if stored_hash != computed:
                raise ThreatScanChainError(
                    f"record_hash mismatch at sequence {seq}",
                    sequence=seq,
                    detail=f"stored={stored_hash!r}, computed={computed!r}",
                )

            prev_hash = stored_hash
            expected_seq += 1


# ---------------------------------------------------------------------------
# ThreatScanLedger
# ---------------------------------------------------------------------------

class ThreatScanLedger:
    """Append-only SHA-256 hash-chained JSONL ledger for ThreatMonitor scans.

    Parameters
    ----------
    path:
        File path for the JSONL ledger.  When ``None`` (default), the ledger
        is inactive: ``emit()`` is a no-op and no file is written.
    chain_verify_on_open:
        When ``True`` (default) and ``path`` is an existing non-empty file,
        the chain is verified on construction; raises ``ThreatScanChainError``
        if integrity is violated.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        chain_verify_on_open: bool = True,
    ) -> None:
        self._path: Path | None = Path(path) if path is not None else None
        self._sequence: int = 0
        self._prev_hash: str = THREAT_SCAN_LEDGER_GENESIS_PREV_HASH

        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists() and self._path.stat().st_size > 0:
                if chain_verify_on_open:
                    _verify_existing_chain(self._path)
                # resume sequence from existing records
                with self._path.open("r", encoding="utf-8") as fh:
                    lines = [l.strip() for l in fh if l.strip()]
                self._sequence = len(lines)
                if lines:
                    last = json.loads(lines[-1])
                    self._prev_hash = last.get("record_hash", self._prev_hash)

    def emit(self, scan: dict[str, Any]) -> None:
        """Append one ThreatMonitor scan result to the ledger.

        Parameters
        ----------
        scan:
            Dict returned by ``ThreatMonitor.scan()`` — keys: epoch_id,
            mutation_count, recommendation, risk, findings, scan_digest.

        Fail-safe: any I/O or serialisation error is logged and swallowed.
        """
        if self._path is None:
            return

        try:
            ts = datetime.now(tz=timezone.utc).isoformat()
            record = _build_scan_record(
                sequence=self._sequence,
                prev_hash=self._prev_hash,
                scan=scan,
                timestamp_iso=ts,
            )
            line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line)
            self._prev_hash = record["record_hash"]
            self._sequence += 1
        except Exception as exc:  # pragma: no cover
            log.warning("ThreatScanLedger.emit failed (silenced): %s", exc)

    def verify_chain(self) -> bool:
        """Return True if chain is intact; False if ledger is inactive."""
        if self._path is None or not self._path.exists():
            return False
        _verify_existing_chain(self._path)
        return True

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def path(self) -> Path | None:
        return self._path


# ---------------------------------------------------------------------------
# ThreatScanReader
# ---------------------------------------------------------------------------

class ThreatScanReader:
    """Read-only analytics surface over a ThreatScanLedger JSONL file."""

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
        recommendation_filter: str | None = None,
        triggered_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return records in chronological order with optional filtering.

        Parameters
        ----------
        limit:
            Maximum number of records to return (most recent).
        recommendation_filter:
            If set, only records with ``recommendation == recommendation_filter``.
        triggered_only:
            If ``True``, only records where ``triggered_count >= 1``.
        """
        records = self._all_records()
        if recommendation_filter is not None:
            records = [r for r in records if r.get("recommendation") == recommendation_filter]
        if triggered_only:
            records = [r for r in records if (r.get("triggered_count") or 0) >= 1]
        if limit is not None:
            records = records[-limit:]
        return records

    def recommendation_breakdown(self) -> dict[str, int]:
        """Return count of records per recommendation value."""
        breakdown: dict[str, int] = {}
        for rec in self._all_records():
            key = rec.get("recommendation", "unknown")
            breakdown[key] = breakdown.get(key, 0) + 1
        return breakdown

    def triggered_rate(self) -> float:
        """Return fraction of scans where at least one detector triggered.

        Returns 0.0 when history is empty.
        """
        records = self._all_records()
        if not records:
            return 0.0
        triggered = sum(1 for r in records if (r.get("triggered_count") or 0) >= 1)
        return triggered / len(records)

    def escalation_rate(self) -> float:
        """Return fraction of scans with recommendation != 'continue'.

        Returns 0.0 when history is empty.
        """
        records = self._all_records()
        if not records:
            return 0.0
        escalated = sum(1 for r in records if r.get("recommendation") != "continue")
        return escalated / len(records)

    def avg_risk_score(self) -> float:
        """Return mean risk_score across all records; 0.0 when empty."""
        records = self._all_records()
        if not records:
            return 0.0
        return sum(float(r.get("risk_score") or 0.0) for r in records) / len(records)

    def risk_level_breakdown(self) -> dict[str, int]:
        """Return count of records per risk_level value."""
        breakdown: dict[str, int] = {}
        for rec in self._all_records():
            key = rec.get("risk_level", "unknown")
            breakdown[key] = breakdown.get(key, 0) + 1
        return breakdown

    def verify_chain(self) -> bool:
        """Return True if chain is intact; raise on violation."""
        if not self._path.exists():
            return False
        _verify_existing_chain(self._path)
        return True


__all__ = [
    "ThreatScanLedger",
    "ThreatScanReader",
    "ThreatScanChainError",
    "THREAT_SCAN_LEDGER_VERSION",
    "DEFAULT_THREAT_SCAN_LEDGER_PATH",
]
