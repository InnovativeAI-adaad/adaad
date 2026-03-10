# SPDX-License-Identifier: Apache-2.0
"""CertifierScanLedger + CertifierScanReader — ADAAD Phase 33.

SHA-256 hash-chained append-only JSONL audit ledger for GateCertifier scan
results (``POST /governance/certify``).  Closes the observability gap between
the Phase 31 certifier endpoint and the governance health surface: rejection
rates are now measurable, auditable, and feed into the composite health score
``h`` as the 8th governance health signal (Phase 33).

Architectural pattern mirrors ThreatScanLedger (Phase 30) and
AdmissionAuditLedger (Phase 27):
- GENESIS_PREV_HASH sentinel: ``"sha256:" + "0" * 64``
- Monotonically increasing sequence numbers
- Each record linked to predecessor via prev_hash → record_hash chain
- ``chain_verify_on_open=True`` raises ``CertifierScanChainError`` on
  construction if chain integrity is violated
- ``emit()`` catches ALL failures; logs WARNING; never propagates
- Reader is strictly read-only; no write path

Design invariants
─────────────────
- Append-only: no record is ever overwritten or deleted.
- Fail-closed chain verification: any hash mismatch → ``CertifierScanChainError``.
- Emit failure isolation: I/O errors in ``emit()`` never surface to callers.
- Deterministic replay: same scan sequence → same chain hashes.
- Timestamp excluded from ``record_hash`` — chain is wall-clock independent.
- Ledger inactive by default: no ``path`` kwarg → no file written.
- GovernanceGate isolation: this module never imports GovernanceGate.
- Advisory only: ``CertifierScanLedger`` records outcomes; it never
  approves or blocks mutations.  GovernanceGate retains sole authority.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CERTIFIER_SCAN_LEDGER_GENESIS_PREV_HASH: str = "sha256:" + "0" * 64
CERTIFIER_SCAN_LEDGER_VERSION: str = "33.0"

DEFAULT_CERTIFIER_SCAN_LEDGER_PATH: str = "security/ledger/certifier_scan_audit.jsonl"

VALID_STATUSES = frozenset({"CERTIFIED", "REJECTED"})


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class CertifierScanChainError(RuntimeError):
    """Raised when CertifierScanLedger chain verification fails."""

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


def _build_certifier_record(
    *,
    sequence: int,
    prev_hash: str,
    scan: dict[str, Any],
    timestamp_iso: str,
) -> dict[str, Any]:
    """Build a JSONL record from a GateCertifier ``certify()`` result dict.

    ``timestamp_iso`` is stored as metadata but excluded from ``record_hash``
    so the chain is deterministic regardless of wall-clock time.

    Expected ``scan`` keys (all optional — missing keys safe-default):
        status, passed, file, escalation, mutation_blocked, fail_closed,
        metadata, checks.
    """
    status = str(scan.get("status") or "REJECTED")
    passed = bool(scan.get("passed", False))
    checks = dict(scan.get("checks") or {})

    chained: dict[str, Any] = {
        "ledger_version":  CERTIFIER_SCAN_LEDGER_VERSION,
        "sequence":        sequence,
        "prev_hash":       prev_hash,
        "status":          status if status in VALID_STATUSES else "REJECTED",
        "passed":          passed,
        "file_path":       str(scan.get("file") or ""),
        "escalation":      str(scan.get("escalation") or "advisory"),
        "mutation_blocked": bool(scan.get("mutation_blocked", False)),
        "fail_closed":     bool(scan.get("fail_closed", False)),
        "import_ok":       bool(checks.get("import_ok", True)),
        "token_ok":        bool(checks.get("token_ok", True)),
        "ast_ok":          bool(checks.get("ast_ok", True)),
        "auth_ok":         bool(checks.get("auth_ok", False)),
    }

    record_hash = _sha256_prefixed(_canonical_bytes(chained))
    return {
        **chained,
        "record_hash": record_hash,
        "timestamp":   timestamp_iso,
    }


def _verify_chain_records(records: list[dict[str, Any]]) -> tuple[bool, int, str]:
    """Verify the hash chain.  Returns (ok, fail_sequence, detail)."""
    prev_hash = CERTIFIER_SCAN_LEDGER_GENESIS_PREV_HASH
    for rec in records:
        seq = int(rec.get("sequence", -1))
        if rec.get("prev_hash") != prev_hash:
            return False, seq, f"prev_hash mismatch at seq {seq}"
        # Recompute record_hash
        chained_fields = {
            k: rec[k]
            for k in [
                "ledger_version", "sequence", "prev_hash", "status", "passed",
                "file_path", "escalation", "mutation_blocked", "fail_closed",
                "import_ok", "token_ok", "ast_ok", "auth_ok",
            ]
            if k in rec
        }
        expected = _sha256_prefixed(_canonical_bytes(chained_fields))
        if rec.get("record_hash") != expected:
            return False, seq, f"record_hash mismatch at seq {seq}"
        prev_hash = rec["record_hash"]
    return True, -1, ""


# ---------------------------------------------------------------------------
# CertifierScanLedger (writer)
# ---------------------------------------------------------------------------


class CertifierScanLedger:
    """Append-only SHA-256 hash-chained JSONL ledger for GateCertifier scans.

    Parameters
    ----------
    path:
        File path for the JSONL ledger.  ``None`` → inactive (no file written).
    chain_verify_on_open:
        When ``True`` (default), verify the existing chain on construction.
        Raises ``CertifierScanChainError`` on any integrity violation.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        chain_verify_on_open: bool = True,
    ) -> None:
        self._path: Path | None = Path(path) if path is not None else None
        self._sequence: int = 0
        self._prev_hash: str = CERTIFIER_SCAN_LEDGER_GENESIS_PREV_HASH

        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists():
                existing = self._load_records()
                if chain_verify_on_open and existing:
                    ok, fail_seq, detail = _verify_chain_records(existing)
                    if not ok:
                        raise CertifierScanChainError(
                            f"CertifierScanLedger: chain integrity violation",
                            sequence=fail_seq,
                            detail=detail,
                        )
                if existing:
                    last = existing[-1]
                    self._sequence = int(last["sequence"]) + 1
                    self._prev_hash = last["record_hash"]

    def emit(self, scan: dict[str, Any]) -> None:
        """Append a GateCertifier scan result to the ledger.

        Failure-isolated: any I/O or serialisation error is logged and
        swallowed.  Callers are never interrupted.
        """
        if self._path is None:
            return
        try:
            timestamp_iso = datetime.now(timezone.utc).isoformat()
            record = _build_certifier_record(
                sequence=self._sequence,
                prev_hash=self._prev_hash,
                scan=scan,
                timestamp_iso=timestamp_iso,
            )
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, separators=(",", ":")) + "\n")
            self._prev_hash = record["record_hash"]
            self._sequence += 1
        except Exception as exc:
            log.warning("CertifierScanLedger.emit() failed (swallowed): %s", exc)

    def verify_chain(self) -> bool:
        """Verify the current on-disk chain.  Returns ``True`` if intact."""
        if self._path is None or not self._path.exists():
            return True
        try:
            ok, _, _ = _verify_chain_records(self._load_records())
            return ok
        except Exception:
            return False

    def _load_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records


# ---------------------------------------------------------------------------
# CertifierScanReader (read-only analytics)
# ---------------------------------------------------------------------------


class CertifierScanReader:
    """Read-only analytics over a ``CertifierScanLedger`` JSONL file.

    Parameters
    ----------
    path:
        Path to the JSONL ledger.  A non-existent path is treated as empty.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _records(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def history(
        self,
        *,
        limit: int | None = None,
        rejected_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return scan records, optionally filtered.

        Parameters
        ----------
        limit:
            Maximum number of records to return (most recent last).
        rejected_only:
            When ``True``, return only REJECTED scans.
        """
        recs = self._records()
        if rejected_only:
            recs = [r for r in recs if not r.get("passed", True)]
        if limit is not None:
            recs = recs[-limit:]
        return recs

    def rejection_rate(self) -> float:
        """Fraction of scans that were REJECTED.

        Returns ``0.0`` on empty history (no rejections → healthy).
        """
        recs = self._records()
        if not recs:
            return 0.0
        rejected = sum(1 for r in recs if not r.get("passed", True))
        return round(rejected / len(recs), 6)

    def certification_rate(self) -> float:
        """Fraction of scans that were CERTIFIED (1.0 - rejection_rate)."""
        return round(1.0 - self.rejection_rate(), 6)

    def escalation_breakdown(self) -> dict[str, int]:
        """Count scans by escalation level."""
        breakdown: dict[str, int] = {}
        for rec in self._records():
            lvl = str(rec.get("escalation") or "advisory")
            breakdown[lvl] = breakdown.get(lvl, 0) + 1
        return breakdown

    def mutation_blocked_count(self) -> int:
        """Number of scans that set mutation_blocked=True."""
        return sum(1 for r in self._records() if r.get("mutation_blocked", False))

    def fail_closed_count(self) -> int:
        """Number of scans that triggered fail_closed=True."""
        return sum(1 for r in self._records() if r.get("fail_closed", False))

    def verify_chain(self) -> bool:
        """Verify the on-disk hash chain.  Returns True if intact."""
        try:
            ok, _, _ = _verify_chain_records(self._records())
            return ok
        except Exception:
            return False


__all__ = [
    "CertifierScanChainError",
    "CertifierScanLedger",
    "CertifierScanReader",
    "CERTIFIER_SCAN_LEDGER_VERSION",
    "DEFAULT_CERTIFIER_SCAN_LEDGER_PATH",
]
