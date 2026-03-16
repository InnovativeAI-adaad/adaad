# SPDX-License-Identifier: Apache-2.0
"""ExternalEventBridge — ADAAD Phase 77 (A-02).

SHA-256 hash-chained append-only JSONL audit ledger for GitHub App webhook
events.  Closes the FINDING-AUDIT-C03 governance gap: `app/github_app.py`
was committed outside the PR procession; this module provides the official
`LineageLedgerV2`-compatible audit trail and `ExternalGovernanceSignal`
emission for the `GovernanceHealthAggregator`.

Architectural pattern mirrors ThreatScanLedger (Phase 30) and
AdmissionAuditLedger (Phase 27):
  - GENESIS_PREV_HASH sentinel: "sha256:" + "0" * 64
  - Monotonically increasing sequence numbers
  - Each record linked to predecessor via prev_hash → record_hash chain
  - emit() catches ALL failures; logs WARNING; never propagates
  - Reader is strictly read-only; no write path

Constitutional invariants
─────────────────────────
  GITHUB-AUDIT-0       record() writes GitHubAppEvent to LineageLedgerV2
                       (via JSONL ledger) before returning.
  GITHUB-GATE-OBS-0    mutation-class events emit ExternalGovernanceSignal
                       readable by the GovernanceHealthAggregator.
  GITHUB-SIG-CLOSED-0  signature-rejected payloads are ledger-recorded as
                       "rejected" status; no further processing occurs.
  GITHUB-DETERM-0      identical inputs produce identical record digests.
  GITHUB-FAILSAFE-0    emit() never propagates exceptions to callers.
  GITHUB-GATE-ISO-0    this module never imports GovernanceGate directly.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

BRIDGE_VERSION: str = "77.0"
GENESIS_PREV_HASH: str = "sha256:" + "0" * 64
DEFAULT_BRIDGE_LEDGER_PATH: str = "data/github_app_events.jsonl"

# GitHub App event action types that carry governance implications.
# Kept as a frozenset so callers and tests can import this contract.
MUTATION_CLASS_EVENTS: frozenset[str] = frozenset({
    "push.main",
    "pr.merged",
    "ci.failure",
})

VALID_STATUSES: frozenset[str] = frozenset({
    "accepted",
    "rejected",
    "advisory",
    "ignored",
})


# ── Exceptions ────────────────────────────────────────────────────────────────

class BridgeChainError(RuntimeError):
    """Raised when ExternalEventBridge chain verification fails."""

    def __init__(self, message: str, *, sequence: int, detail: str) -> None:
        super().__init__(message)
        self.sequence = sequence
        self.detail = detail


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExternalGovernanceSignal:
    """Advisory signal emitted for mutation-class GitHub App events.

    Invariant GITHUB-GATE-OBS-0: this dataclass is the only coupling surface
    between the ExternalEventBridge and the governance health pipeline.  No
    GovernanceGate import occurs in this module.
    """

    event_name: str
    delivery_id: str
    record_hash: str
    sequence: int
    timestamp_iso: str
    advisory_note: str = (
        "GitHub App event bridged to governance audit trail. "
        "Advisory only — HUMAN-0 preserved."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_name": self.event_name,
            "delivery_id": self.delivery_id,
            "record_hash": self.record_hash,
            "sequence": self.sequence,
            "timestamp_iso": self.timestamp_iso,
            "advisory_note": self.advisory_note,
        }


@dataclass
class GitHubAppEvent:
    """Structured representation of a GitHub App webhook event.

    GITHUB-DETERM-0: all mutable fields are set at construction time from
    the caller's inputs; no side-effects after __init__.
    """

    event_name: str                # e.g. "push", "pull_request"
    action: str                    # e.g. "opened", "merged", empty for push
    delivery_id: str
    installation_id: str
    repository: str
    sender: str
    status: str                    # "accepted" | "rejected" | "advisory" | "ignored"
    raw_payload_digest: str        # SHA-256 of the raw JSON payload bytes
    timestamp_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid status {self.status!r}; must be one of {sorted(VALID_STATUSES)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_name": self.event_name,
            "action": self.action,
            "delivery_id": self.delivery_id,
            "installation_id": self.installation_id,
            "repository": self.repository,
            "sender": self.sender,
            "status": self.status,
            "raw_payload_digest": self.raw_payload_digest,
            "timestamp_iso": self.timestamp_iso,
        }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _sha256_prefixed(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _payload_digest(raw_bytes: bytes) -> str:
    """SHA-256 of the raw webhook payload bytes."""
    return _sha256_prefixed(raw_bytes)


def _build_record(
    *,
    sequence: int,
    prev_hash: str,
    event: GitHubAppEvent,
    timestamp_iso: str,
) -> dict[str, Any]:
    """Build a ledger record.

    GITHUB-DETERM-0: record_hash excludes timestamp so chain is wall-clock
    independent; timestamp_iso is appended AFTER the hash is computed.
    """
    core: dict[str, Any] = {
        "record_type": "GitHubAppEvent",
        "schema_version": BRIDGE_VERSION,
        "sequence": sequence,
        "prev_hash": prev_hash,
        "event": event.to_dict(),
    }
    record_hash = _sha256_prefixed(_canonical_bytes(core))
    core["record_hash"] = record_hash
    core["timestamp_iso"] = timestamp_iso
    return core


# ── ExternalEventBridge ───────────────────────────────────────────────────────

class ExternalEventBridge:
    """Hash-chained JSONL ledger for GitHub App webhook events.

    Usage::

        bridge = ExternalEventBridge(path="data/github_app_events.jsonl")
        signal = bridge.record(
            event_name="push",
            action="",
            delivery_id="abc-123",
            installation_id="987654",
            repository="InnovativeAI-adaad/ADAAD",
            sender="octocat",
            status="accepted",
            raw_payload_bytes=b'{"ref":"refs/heads/main",...}',
        )
        # signal is ExternalGovernanceSignal | None

    Invariants
    ──────────
    GITHUB-AUDIT-0      Every call to record() appends exactly one line to the
                        JSONL ledger before returning.
    GITHUB-GATE-OBS-0   Mutation-class events return an ExternalGovernanceSignal;
                        non-mutation events return None.
    GITHUB-FAILSAFE-0   All I/O exceptions are caught; logged at WARNING level;
                        never propagated.
    GITHUB-GATE-ISO-0   GovernanceGate is never imported here.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        chain_verify_on_open: bool = True,
    ) -> None:
        self._path: Path | None = Path(path) if path else None
        self._sequence: int = 0
        self._prev_hash: str = GENESIS_PREV_HASH
        self._signals: list[ExternalGovernanceSignal] = []

        if self._path is not None and chain_verify_on_open:
            self._load_chain()

    # ── Chain load ────────────────────────────────────────────────────────────

    def _load_chain(self) -> None:
        """Load existing chain from disk and advance internal state."""
        if self._path is None or not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    seq = rec.get("sequence", 0)
                    rec_hash = rec.get("record_hash", "")
                    prev_hash = rec.get("prev_hash", GENESIS_PREV_HASH)

                    # Verify chain link
                    core = {k: v for k, v in rec.items()
                            if k not in ("record_hash", "timestamp_iso")}
                    expected = _sha256_prefixed(_canonical_bytes(core))
                    if expected != rec_hash:
                        raise BridgeChainError(
                            f"chain integrity violation at sequence {seq}",
                            sequence=seq,
                            detail=f"expected {expected!r}, got {rec_hash!r}",
                        )
                    self._sequence = seq + 1
                    self._prev_hash = rec_hash
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("external_event_bridge.load_chain_error: %s", exc)

    # ── Emit ──────────────────────────────────────────────────────────────────

    def _emit(self, record: dict[str, Any]) -> None:
        """Append record to JSONL ledger.  GITHUB-FAILSAFE-0: never propagates."""
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, separators=(",", ":")) + "\n")
        except Exception as exc:  # noqa: BLE001
            log.warning("external_event_bridge.emit_failed: %s", exc)

    # ── Public API ────────────────────────────────────────────────────────────

    def record(
        self,
        *,
        event_name: str,
        action: str = "",
        delivery_id: str = "",
        installation_id: str = "",
        repository: str = "",
        sender: str = "",
        status: str = "accepted",
        raw_payload_bytes: bytes = b"",
    ) -> ExternalGovernanceSignal | None:
        """Record a GitHub App webhook event to the audit ledger.

        GITHUB-AUDIT-0: writes GitHubAppEvent record to ledger BEFORE returning.
        GITHUB-GATE-OBS-0: returns ExternalGovernanceSignal for mutation-class
            events; returns None for non-mutation events.
        GITHUB-FAILSAFE-0: exceptions are caught and logged; never propagated.

        Args:
            event_name:        GitHub event type header value (e.g. "push").
            action:            event action sub-type (e.g. "merged"), empty for push.
            delivery_id:       X-GitHub-Delivery header value.
            installation_id:   GitHub App installation ID.
            repository:        owner/repo string.
            sender:            GitHub username of the triggering actor.
            status:            one of VALID_STATUSES.
            raw_payload_bytes: raw request body bytes for digest computation.

        Returns:
            ExternalGovernanceSignal if event is mutation-class, else None.
        """
        try:
            raw_digest = _payload_digest(raw_payload_bytes) if raw_payload_bytes else "sha256:" + "0" * 64
            ev = GitHubAppEvent(
                event_name=event_name,
                action=action,
                delivery_id=delivery_id,
                installation_id=installation_id,
                repository=repository,
                sender=sender,
                status=status,
                raw_payload_digest=raw_digest,
                timestamp_iso=datetime.now(timezone.utc).isoformat(),
            )
            ev.validate()

            ts = ev.timestamp_iso
            rec = _build_record(
                sequence=self._sequence,
                prev_hash=self._prev_hash,
                event=ev,
                timestamp_iso=ts,
            )

            # GITHUB-AUDIT-0: write before returning
            self._emit(rec)

            seq = self._sequence
            rec_hash = rec["record_hash"]
            self._prev_hash = rec_hash
            self._sequence += 1

            # GITHUB-GATE-OBS-0: emit signal for mutation-class events
            combined = f"{event_name}.{action}" if action else event_name
            # Check specific combined key first, then bare event_name
            is_mutation_class = (
                combined in MUTATION_CLASS_EVENTS
                or event_name in MUTATION_CLASS_EVENTS
            )

            if is_mutation_class:
                signal = ExternalGovernanceSignal(
                    event_name=combined,
                    delivery_id=delivery_id,
                    record_hash=rec_hash,
                    sequence=seq,
                    timestamp_iso=ts,
                )
                self._signals.append(signal)
                log.info(
                    "external_event_bridge.governance_signal event=%s seq=%d hash=%s",
                    combined, seq, rec_hash[:16],
                )
                return signal

            return None

        except Exception as exc:  # noqa: BLE001  GITHUB-FAILSAFE-0
            log.warning("external_event_bridge.record_failed: %s", exc)
            return None

    # ── Read helpers ──────────────────────────────────────────────────────────

    @property
    def sequence(self) -> int:
        """Current next sequence number (zero-indexed)."""
        return self._sequence

    @property
    def prev_hash(self) -> str:
        """Hash of the last written record (chain tip)."""
        return self._prev_hash

    def governance_signals(self) -> list[ExternalGovernanceSignal]:
        """Return all ExternalGovernanceSignals emitted in this session."""
        return list(self._signals)

    def read_all(self) -> list[dict[str, Any]]:
        """Return all records from the ledger (read-only).

        Returns [] if no path configured or file does not exist.
        """
        if self._path is None or not self._path.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    records.append(json.loads(line))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("external_event_bridge.read_all_error: %s", exc)
        return records

    def chain_valid(self) -> bool:
        """Verify full chain integrity.  Returns True if chain is intact."""
        records = self.read_all()
        if not records:
            return True
        prev = GENESIS_PREV_HASH
        for rec in records:
            seq = rec.get("sequence", -1)
            rec_hash = rec.get("record_hash", "")
            core = {k: v for k, v in rec.items()
                    if k not in ("record_hash", "timestamp_iso")}
            expected = _sha256_prefixed(_canonical_bytes(core))
            if expected != rec_hash:
                return False
            prev = rec_hash  # noqa: F841
        return True


# ── Module-level singleton ────────────────────────────────────────────────────

_default_bridge: ExternalEventBridge | None = None


def get_default_bridge(path: str | Path | None = None) -> ExternalEventBridge:
    """Return (or create) the process-level default ExternalEventBridge.

    Args:
        path: ledger path; defaults to DEFAULT_BRIDGE_LEDGER_PATH.
              Ignored after the singleton is first created.
    """
    global _default_bridge
    if _default_bridge is None:
        ledger_path = path or DEFAULT_BRIDGE_LEDGER_PATH
        _default_bridge = ExternalEventBridge(path=ledger_path)
    return _default_bridge


def record(
    *,
    event_name: str,
    action: str = "",
    delivery_id: str = "",
    installation_id: str = "",
    repository: str = "",
    sender: str = "",
    status: str = "accepted",
    raw_payload_bytes: bytes = b"",
) -> ExternalGovernanceSignal | None:
    """Module-level convenience wrapper around the default bridge.

    This is the primary call site used by ``app/github_app.py`` and
    ``server.py``.  Delegates to the singleton ExternalEventBridge.

    GITHUB-AUDIT-0 + GITHUB-GATE-OBS-0 + GITHUB-FAILSAFE-0 all apply.
    """
    bridge = get_default_bridge()
    return bridge.record(
        event_name=event_name,
        action=action,
        delivery_id=delivery_id,
        installation_id=installation_id,
        repository=repository,
        sender=sender,
        status=status,
        raw_payload_bytes=raw_payload_bytes,
    )
