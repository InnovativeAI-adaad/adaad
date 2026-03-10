# SPDX-License-Identifier: Apache-2.0
"""PressureAuditLedger + PressureAuditReader — Phase 25

SHA-256 hash-chained append-only JSONL audit ledger for PressureAdjustment records.

Architectural pattern mirrors FileTelemetrySink (Phase 21):
- GENESIS_PREV_HASH sentinel: "sha256:" + "0" * 64
- Monotonically increasing sequence numbers
- Each record linked to predecessor via prev_hash → record_hash chain
- chain_verify_on_open=True raises PressureAuditChainError on construction if broken
- emit() catches ALL failures; logs WARNING; never propagates
- Reader is strictly read-only; no write path

Design invariants:
- Append-only: no record is ever overwritten or deleted
- Fail-closed chain verification: any hash mismatch → PressureAuditChainError
- Emit failure isolation: I/O errors in emit() never surface to callers
- Deterministic replay: same records → same chain hashes → same verify result
- Ledger inactive by default: no env var / kwarg → no file written
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

PRESSURE_LEDGER_GENESIS_PREV_HASH: str = "sha256:" + "0" * 64
PRESSURE_LEDGER_VERSION: str = "25.0"

# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class PressureAuditChainError(RuntimeError):
    """Raised when PressureAuditLedger chain verification fails."""

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
    adjustment: Any,  # PressureAdjustment
    timestamp_iso: str,
) -> dict[str, Any]:
    """Build a JSONL record from a PressureAdjustment; compute record_hash.

    timestamp_iso is stored as metadata but excluded from record_hash so that
    the hash chain is deterministic: same adjustment sequence → same hashes,
    regardless of wall-clock time.
    """
    # Chained fields (deterministic — timestamp excluded)
    chained: dict[str, Any] = {
        "ledger_version": PRESSURE_LEDGER_VERSION,
        "sequence": sequence,
        "prev_hash": prev_hash,
        "health_score": round(adjustment.health_score, 8),
        "health_band": adjustment.health_band,
        "pressure_tier": adjustment.pressure_tier,
        "adjusted_tiers": list(adjustment.adjusted_tiers),
        "adjustment_digest": adjustment.adjustment_digest,
        "adaptor_version": adjustment.adaptor_version,
    }
    record_hash = _sha256_prefixed(_canonical_bytes(chained))
    body = dict(chained)
    body["timestamp_iso"] = timestamp_iso
    body["record_hash"] = record_hash
    return body


def _verify_existing_chain(path: Path) -> None:
    """Verify hash chain of an existing ledger file.

    Raises PressureAuditChainError on any integrity violation.
    Returns silently when chain is intact.
    """
    prev_hash = PRESSURE_LEDGER_GENESIS_PREV_HASH
    expected_seq = 0

    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise PressureAuditChainError(
                    f"Unparseable record at expected sequence {expected_seq}",
                    sequence=expected_seq,
                    detail=str(exc),
                )

            seq = record.get("sequence", -1)
            if seq != expected_seq:
                raise PressureAuditChainError(
                    f"Sequence mismatch: expected {expected_seq}, got {seq}",
                    sequence=expected_seq,
                    detail=f"got sequence={seq}",
                )

            stored_prev = record.get("prev_hash", "")
            if stored_prev != prev_hash:
                raise PressureAuditChainError(
                    f"prev_hash mismatch at sequence {seq}",
                    sequence=seq,
                    detail=f"expected {prev_hash!r}, got {stored_prev!r}",
                )

            stored_hash = record.pop("record_hash", None)
            # timestamp_iso is metadata — exclude from hash recomputation
            record.pop("timestamp_iso", None)
            computed = _sha256_prefixed(_canonical_bytes(record))
            if stored_hash != computed:
                raise PressureAuditChainError(
                    f"record_hash mismatch at sequence {seq}",
                    sequence=seq,
                    detail=f"stored={stored_hash!r}, computed={computed!r}",
                )

            prev_hash = stored_hash
            expected_seq += 1


# ---------------------------------------------------------------------------
# PressureAuditLedger
# ---------------------------------------------------------------------------


class PressureAuditLedger:
    """Append-only SHA-256 hash-chained JSONL audit ledger for PressureAdjustment.

    Parameters
    ----------
    path:
        Path to the JSONL ledger file. Created on first emit if it does not exist.
    chain_verify_on_open:
        If True (default) and the file already exists, verify the chain at
        construction. Raises PressureAuditChainError on any violation.
    """

    def __init__(
        self,
        path: Path | str,
        *,
        chain_verify_on_open: bool = True,
    ) -> None:
        self._path = Path(path)
        self._sequence: int = 0
        self._prev_hash: str = PRESSURE_LEDGER_GENESIS_PREV_HASH

        if self._path.exists():
            if chain_verify_on_open:
                _verify_existing_chain(self._path)
            # Count existing records to set sequence
            count = sum(
                1 for line in self._path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
            self._sequence = count
            # Re-read last prev_hash for continuation
            if count > 0:
                last_line = ""
                for line in self._path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        last_line = line.strip()
                try:
                    self._prev_hash = json.loads(last_line).get(
                        "record_hash", PRESSURE_LEDGER_GENESIS_PREV_HASH
                    )
                except Exception:
                    self._prev_hash = PRESSURE_LEDGER_GENESIS_PREV_HASH

    def emit(self, adjustment: Any) -> None:  # PressureAdjustment
        """Append one PressureAdjustment record to the ledger.

        Never raises: all I/O and serialisation failures are caught and
        logged as WARNING (Phase 21 isolation contract).
        """
        try:
            ts = datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")
            record = _build_record(
                sequence=self._sequence,
                prev_hash=self._prev_hash,
                adjustment=adjustment,
                timestamp_iso=ts,
            )
            line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line)
            self._prev_hash = record["record_hash"]
            self._sequence += 1
        except Exception as exc:  # pragma: no cover
            log.warning("PressureAuditLedger.emit() failed (record dropped): %s", exc)

    def verify_chain(self) -> bool:
        """Verify full chain integrity. Raises PressureAuditChainError on violation."""
        if not self._path.exists():
            return True
        _verify_existing_chain(self._path)
        return True

    @property
    def sequence(self) -> int:
        """Current sequence counter (number of records written this session)."""
        return self._sequence

    @property
    def path(self) -> Path:
        return self._path


# ---------------------------------------------------------------------------
# PressureAuditReader
# ---------------------------------------------------------------------------


class PressureAuditReader:
    """Read-only query interface for a PressureAuditLedger file.

    Parameters
    ----------
    path:
        Path to the JSONL ledger file. Must exist; raises FileNotFoundError otherwise.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(f"PressureAuditReader: ledger not found: {self._path}")

    def _all_records(self) -> list[dict[str, Any]]:
        records = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return records

    def history(
        self,
        *,
        pressure_tier: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return ledger records newest-first.

        Parameters
        ----------
        pressure_tier:
            Filter by pressure tier ("none", "elevated", "critical").
        limit:
            Maximum records to return (1–500).
        offset:
            Skip this many records (after filter, before limit).
        """
        if limit > 500:
            raise ValueError(f"limit={limit} exceeds maximum of 500")

        records = list(reversed(self._all_records()))

        if pressure_tier is not None:
            records = [r for r in records if r.get("pressure_tier") == pressure_tier]

        return records[offset: offset + limit]

    def tier_frequency(self) -> dict[str, int]:
        """Return {pressure_tier: count} across all ledger records."""
        counts: dict[str, int] = {}
        for record in self._all_records():
            tier = record.get("pressure_tier")
            if tier is not None:
                counts[tier] = counts.get(tier, 0) + 1
        return counts

    def tier_frequency_series(self, *, window: int = 10) -> dict[str, list[float]]:
        """Rolling window pressure-tier frequency series.

        Divides all records (arrival order) into non-overlapping windows of
        `window` size. For each window, computes {tier: count/window}.
        Returns {tier: [freq_window0, freq_window1, ...]}.
        Tiers absent from a given window have 0.0 for that slot.
        """
        records = self._all_records()
        all_tiers: set[str] = {r.get("pressure_tier", "") for r in records} - {""}

        if not records:
            return {}

        windows: list[list[dict]] = []
        for i in range(0, len(records), window):
            chunk = records[i: i + window]
            if chunk:
                windows.append(chunk)

        series: dict[str, list[float]] = {t: [] for t in all_tiers}

        for chunk in windows:
            chunk_size = len(chunk)
            counts: dict[str, int] = {}
            for r in chunk:
                t = r.get("pressure_tier", "")
                if t:
                    counts[t] = counts.get(t, 0) + 1
            for tier in all_tiers:
                series[tier].append(counts.get(tier, 0) / chunk_size)

        return series

    def verify_chain(self) -> bool:
        """Verify ledger chain integrity. Raises PressureAuditChainError on violation."""
        _verify_existing_chain(self._path)
        return True


__all__ = [
    "PRESSURE_LEDGER_GENESIS_PREV_HASH",
    "PRESSURE_LEDGER_VERSION",
    "PressureAuditChainError",
    "PressureAuditLedger",
    "PressureAuditReader",
]
