# SPDX-License-Identifier: Apache-2.0
"""Reviewer Reputation Ledger — ADAAD Phase 7, PR-7-01.

Append-only, SHA-256 hash-chained ledger of all reviewer decisions.
Every entry records the outcome of a governance review action so that
the Reputation Scoring Engine (M7-02) can derive deterministic,
epoch-scoped reputation scores from a stable event history.

Architectural invariants:
- **Write-once per decision**: entries are immutable once appended.
- **Hash-chained**: each entry carries ``prev_entry_hash`` and
  ``entry_hash`` so chain integrity can be verified offline.
- **reviewer_id privacy**: ``reviewer_id`` stored in the ledger is an
  HMAC-derived opaque token over the signing-key fingerprint — no
  plaintext PII.
- **Deterministic / replay-safe**: all state is derived from the event
  stream; no wall-clock or random calls inside core logic.
- **In-memory default**: the ``ReviewerReputationLedger`` class operates
  entirely in memory by default, making it compatible with replay harnesses
  without touching the filesystem.  Callers that need persistence should
  supply a ``ledger_path`` and call ``flush()`` / ``load()``.

Decision taxonomy
-----------------
``DECISION_APPROVE``   Reviewer approved the mutation proposal.
``DECISION_REJECT``    Reviewer rejected the mutation proposal.
``DECISION_TIMEOUT``   Reviewer did not respond within the SLA window.
``DECISION_OVERRIDE``  A higher-authority principal overrode the reviewer.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from runtime.governance.foundation.canonical import canonical_json_bytes
from runtime.governance.foundation.hashing import sha256_prefixed_digest

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

LEDGER_FORMAT_VERSION = "1.0"
LEDGER_EVENT_TYPE = "reviewer_reputation_ledger_entry"

DECISION_APPROVE = "approve"
DECISION_REJECT = "reject"
DECISION_TIMEOUT = "timeout"
DECISION_OVERRIDE = "override"

VALID_DECISIONS: frozenset[str] = frozenset(
    {DECISION_APPROVE, DECISION_REJECT, DECISION_TIMEOUT, DECISION_OVERRIDE}
)

GENESIS_PREV_HASH = "sha256:" + ("0" * 64)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LedgerIntegrityError(RuntimeError):
    """Raised when chain integrity verification fails."""


class InvalidDecisionError(ValueError):
    """Raised when an unknown decision value is supplied."""


class DuplicateReviewError(ValueError):
    """Raised when an attempt is made to append a second entry for the same
    (reviewer_id, mutation_id, epoch_id) triple."""


# ---------------------------------------------------------------------------
# Reviewer ID derivation
# ---------------------------------------------------------------------------


def derive_reviewer_id(
    signing_key_fingerprint: str,
    *,
    hmac_secret: bytes,
) -> str:
    """Derive an opaque, HMAC-based reviewer token from a signing-key fingerprint.

    The resulting token is stable for a given ``(fingerprint, secret)`` pair
    and contains no plaintext PII.

    Parameters
    ----------
    signing_key_fingerprint:
        The raw fingerprint string (e.g. ``"SHA256:Ia6ftPTad2E2/..."``) from
        the reviewer's signing key.
    hmac_secret:
        Bytes used as the HMAC key.  In production this is derived from the
        deployment's governance signing key material.

    Returns
    -------
    str
        Hex-encoded HMAC-SHA256 digest prefixed with ``"rid:"``.
    """
    digest = hmac.new(
        hmac_secret,
        signing_key_fingerprint.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"rid:{digest}"


# ---------------------------------------------------------------------------
# Ledger entry dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReputationLedgerEntry:
    """A single immutable reviewer decision record.

    Fields
    ------
    sequence_number
        Monotonically increasing position in the ledger (0-based).
    reviewer_id
        Opaque HMAC-derived token identifying the reviewer.
    epoch_id
        Governance epoch in which the decision was made.
    mutation_id
        The mutation proposal that was reviewed.
    decision
        One of ``approve``, ``reject``, ``timeout``, ``override``.
    rationale_length
        Number of characters in the review rationale (used as a
        calibration consistency signal by the scoring engine).
    outcome_validated
        ``True`` if post-merge fitness confirmed the decision was correct,
        ``False`` if post-merge fitness contradicted it, ``None`` if the
        fitness signal has not yet been observed.
    scoring_algorithm_version
        Version of the scoring algorithm active when this entry was created.
    prev_entry_hash
        ``sha256:``-prefixed digest of the previous entry's canonical payload,
        or the genesis sentinel for the first entry.
    entry_hash
        ``sha256:``-prefixed digest of this entry's canonical payload
        (computed over all fields except ``entry_hash`` itself).
    """

    sequence_number: int
    reviewer_id: str
    epoch_id: str
    mutation_id: str
    decision: str
    rationale_length: int
    outcome_validated: Optional[bool]
    scoring_algorithm_version: str
    prev_entry_hash: str
    entry_hash: str = field(compare=False)

    # ------------------------------------------------------------------
    # Canonical payload (excludes ``entry_hash`` to avoid circularity)
    # ------------------------------------------------------------------

    def _canonical_payload(self) -> Dict[str, Any]:
        return {
            "sequence_number": self.sequence_number,
            "reviewer_id": self.reviewer_id,
            "epoch_id": self.epoch_id,
            "mutation_id": self.mutation_id,
            "decision": self.decision,
            "rationale_length": self.rationale_length,
            "outcome_validated": self.outcome_validated,
            "scoring_algorithm_version": self.scoring_algorithm_version,
            "prev_entry_hash": self.prev_entry_hash,
            "ledger_format_version": LEDGER_FORMAT_VERSION,
            "event_type": LEDGER_EVENT_TYPE,
        }

    def verify_hash(self) -> bool:
        """Return ``True`` iff ``entry_hash`` matches the canonical payload digest."""
        expected = sha256_prefixed_digest(self._canonical_payload())
        return self.entry_hash == expected

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation."""
        d = self._canonical_payload()
        d["entry_hash"] = self.entry_hash
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReputationLedgerEntry":
        """Reconstruct an entry from a previously serialised dict."""
        return cls(
            sequence_number=data["sequence_number"],
            reviewer_id=data["reviewer_id"],
            epoch_id=data["epoch_id"],
            mutation_id=data["mutation_id"],
            decision=data["decision"],
            rationale_length=data["rationale_length"],
            outcome_validated=data.get("outcome_validated"),
            scoring_algorithm_version=data["scoring_algorithm_version"],
            prev_entry_hash=data["prev_entry_hash"],
            entry_hash=data["entry_hash"],
        )


# ---------------------------------------------------------------------------
# Hash computation helper
# ---------------------------------------------------------------------------


def _compute_entry_hash(
    sequence_number: int,
    reviewer_id: str,
    epoch_id: str,
    mutation_id: str,
    decision: str,
    rationale_length: int,
    outcome_validated: Optional[bool],
    scoring_algorithm_version: str,
    prev_entry_hash: str,
) -> str:
    payload: Dict[str, Any] = {
        "sequence_number": sequence_number,
        "reviewer_id": reviewer_id,
        "epoch_id": epoch_id,
        "mutation_id": mutation_id,
        "decision": decision,
        "rationale_length": rationale_length,
        "outcome_validated": outcome_validated,
        "scoring_algorithm_version": scoring_algorithm_version,
        "prev_entry_hash": prev_entry_hash,
        "ledger_format_version": LEDGER_FORMAT_VERSION,
        "event_type": LEDGER_EVENT_TYPE,
    }
    return sha256_prefixed_digest(payload)


# ---------------------------------------------------------------------------
# Ledger class
# ---------------------------------------------------------------------------


class ReviewerReputationLedger:
    """In-memory append-only reviewer reputation ledger.

    Thread-safe for concurrent ``append()`` calls.  Persistence is opt-in
    via ``flush()`` / ``load()``.

    Parameters
    ----------
    ledger_path
        Optional filesystem path for JSONL persistence.
    scoring_algorithm_version
        Default version tag stamped on new entries (may be overridden
        per-call).
    """

    def __init__(
        self,
        *,
        ledger_path: Optional[Path] = None,
        scoring_algorithm_version: str = "1.0",
    ) -> None:
        self._entries: List[ReputationLedgerEntry] = []
        self._decision_keys: set[tuple[str, str, str]] = set()
        self._lock = threading.Lock()
        self._ledger_path = ledger_path
        self._scoring_algorithm_version = scoring_algorithm_version

    # ------------------------------------------------------------------
    # Append
    # ------------------------------------------------------------------

    def append(
        self,
        *,
        reviewer_id: str,
        epoch_id: str,
        mutation_id: str,
        decision: str,
        rationale_length: int,
        outcome_validated: Optional[bool] = None,
        scoring_algorithm_version: Optional[str] = None,
    ) -> ReputationLedgerEntry:
        """Append a new decision record and return the created entry.

        Parameters
        ----------
        reviewer_id
            Opaque reviewer token (use :func:`derive_reviewer_id`).
        epoch_id
            Governance epoch identifier.
        mutation_id
            The mutation proposal identifier.
        decision
            Must be one of the ``DECISION_*`` constants.
        rationale_length
            Character count of the review rationale.
        outcome_validated
            Post-merge fitness signal (``None`` until observed).
        scoring_algorithm_version
            Overrides the instance default if supplied.

        Raises
        ------
        InvalidDecisionError
            If ``decision`` is not in :data:`VALID_DECISIONS`.
        DuplicateReviewError
            If an entry for ``(reviewer_id, mutation_id, epoch_id)`` already
            exists in this ledger instance.
        """
        if decision not in VALID_DECISIONS:
            raise InvalidDecisionError(
                f"Invalid decision '{decision}'. Must be one of: {sorted(VALID_DECISIONS)}"
            )

        sav = scoring_algorithm_version or self._scoring_algorithm_version
        key = (reviewer_id, mutation_id, epoch_id)

        with self._lock:
            if key in self._decision_keys:
                raise DuplicateReviewError(
                    f"Duplicate review entry for reviewer_id={reviewer_id!r}, "
                    f"mutation_id={mutation_id!r}, epoch_id={epoch_id!r}"
                )

            prev_hash = (
                self._entries[-1].entry_hash if self._entries else GENESIS_PREV_HASH
            )
            seq = len(self._entries)

            entry_hash = _compute_entry_hash(
                sequence_number=seq,
                reviewer_id=reviewer_id,
                epoch_id=epoch_id,
                mutation_id=mutation_id,
                decision=decision,
                rationale_length=rationale_length,
                outcome_validated=outcome_validated,
                scoring_algorithm_version=sav,
                prev_entry_hash=prev_hash,
            )

            entry = ReputationLedgerEntry(
                sequence_number=seq,
                reviewer_id=reviewer_id,
                epoch_id=epoch_id,
                mutation_id=mutation_id,
                decision=decision,
                rationale_length=rationale_length,
                outcome_validated=outcome_validated,
                scoring_algorithm_version=sav,
                prev_entry_hash=prev_hash,
                entry_hash=entry_hash,
            )

            self._entries.append(entry)
            self._decision_keys.add(key)

        return entry

    # ------------------------------------------------------------------
    # Update outcome_validated (write-once signal)
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        *,
        reviewer_id: str,
        mutation_id: str,
        epoch_id: str,
        outcome_validated: bool,
        scoring_algorithm_version: Optional[str] = None,
    ) -> ReputationLedgerEntry:
        """Append a corrective outcome entry for a prior decision.

        Because ledger entries are immutable, outcome signals are recorded as
        *new* entries with ``decision`` set to the original decision value and
        ``outcome_validated`` set to the observed signal.  The caller must
        have already appended the initial decision entry.

        If no prior entry exists for the key, this method appends a synthetic
        entry with ``decision=DECISION_APPROVE`` as a best-effort fallback,
        which will be visible in the audit trail.
        """
        with self._lock:
            # Find the most recent entry for this key
            matching = [
                e
                for e in self._entries
                if e.reviewer_id == reviewer_id
                and e.mutation_id == mutation_id
                and e.epoch_id == epoch_id
            ]

        original_decision = matching[-1].decision if matching else DECISION_APPROVE

        return self.append(
            reviewer_id=reviewer_id,
            epoch_id=epoch_id,
            mutation_id=f"{mutation_id}:outcome",
            decision=original_decision,
            rationale_length=0,
            outcome_validated=outcome_validated,
            scoring_algorithm_version=scoring_algorithm_version,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def entries(self) -> List[ReputationLedgerEntry]:
        """Return an immutable snapshot of all entries."""
        with self._lock:
            return list(self._entries)

    def entries_for_reviewer(self, reviewer_id: str) -> List[ReputationLedgerEntry]:
        """Return all entries for a specific reviewer."""
        with self._lock:
            return [e for e in self._entries if e.reviewer_id == reviewer_id]

    def entries_for_epoch(self, epoch_id: str) -> List[ReputationLedgerEntry]:
        """Return all entries for a specific epoch."""
        with self._lock:
            return [e for e in self._entries if e.epoch_id == epoch_id]

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    # ------------------------------------------------------------------
    # Integrity verification
    # ------------------------------------------------------------------

    def verify_chain_integrity(self) -> bool:
        """Verify the complete hash chain from genesis.

        Returns ``True`` if all entries are consistent; raises
        :exc:`LedgerIntegrityError` on the first violation.
        """
        with self._lock:
            snapshot = list(self._entries)

        prev_hash = GENESIS_PREV_HASH
        for entry in snapshot:
            if entry.prev_entry_hash != prev_hash:
                raise LedgerIntegrityError(
                    f"Chain break at sequence {entry.sequence_number}: "
                    f"expected prev_hash={prev_hash!r}, got {entry.prev_entry_hash!r}"
                )
            if not entry.verify_hash():
                raise LedgerIntegrityError(
                    f"Entry hash mismatch at sequence {entry.sequence_number}"
                )
            prev_hash = entry.entry_hash

        return True

    # ------------------------------------------------------------------
    # Ledger digest (for cross-ledger comparison / attestation)
    # ------------------------------------------------------------------

    def ledger_digest(self) -> str:
        """Return a ``sha256:``-prefixed digest over the full chain.

        The digest is deterministic for a given sequence of appended entries
        and can be used as an attestation anchor.
        """
        with self._lock:
            if not self._entries:
                return sha256_prefixed_digest(
                    {"entries": [], "ledger_format_version": LEDGER_FORMAT_VERSION}
                )
            tail_hash = self._entries[-1].entry_hash

        return sha256_prefixed_digest(
            {
                "tail_entry_hash": tail_hash,
                "entry_count": len(self._entries),
                "ledger_format_version": LEDGER_FORMAT_VERSION,
            }
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def flush(self, path: Optional[Path] = None) -> Path:
        """Persist the ledger to a JSONL file.

        Parameters
        ----------
        path
            Override the instance ``ledger_path``.  Raises ``ValueError``
            if neither is set.

        Returns
        -------
        Path
            The path written to.
        """
        target = path or self._ledger_path
        if target is None:
            raise ValueError("No ledger_path configured; supply path= to flush()")
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        with self._lock:
            for entry in self._entries:
                lines.append(json.dumps(entry.to_dict(), sort_keys=True, separators=(",", ":")))
        target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return target

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        verify_integrity: bool = True,
        scoring_algorithm_version: str = "1.0",
    ) -> "ReviewerReputationLedger":
        """Load a previously flushed ledger from disk.

        Parameters
        ----------
        path
            Path to the JSONL file.
        verify_integrity
            If ``True`` (default) the hash chain is verified after loading.
        scoring_algorithm_version
            Default version for new entries appended after load.

        Raises
        ------
        LedgerIntegrityError
            If ``verify_integrity=True`` and the chain is broken.
        """
        ledger = cls(
            ledger_path=path,
            scoring_algorithm_version=scoring_algorithm_version,
        )
        path = Path(path)
        if not path.exists():
            return ledger

        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            entry = ReputationLedgerEntry.from_dict(data)
            key = (entry.reviewer_id, entry.mutation_id, entry.epoch_id)
            ledger._entries.append(entry)
            ledger._decision_keys.add(key)

        if verify_integrity:
            ledger.verify_chain_integrity()

        return ledger


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def new_ledger(
    *,
    ledger_path: Optional[Path] = None,
    scoring_algorithm_version: str = "1.0",
) -> ReviewerReputationLedger:
    """Create a fresh in-memory :class:`ReviewerReputationLedger`."""
    return ReviewerReputationLedger(
        ledger_path=ledger_path,
        scoring_algorithm_version=scoring_algorithm_version,
    )


__all__ = [
    "DECISION_APPROVE",
    "DECISION_REJECT",
    "DECISION_TIMEOUT",
    "DECISION_OVERRIDE",
    "VALID_DECISIONS",
    "GENESIS_PREV_HASH",
    "LEDGER_EVENT_TYPE",
    "LEDGER_FORMAT_VERSION",
    "DuplicateReviewError",
    "InvalidDecisionError",
    "LedgerIntegrityError",
    "ReputationLedgerEntry",
    "ReviewerReputationLedger",
    "derive_reviewer_id",
    "new_ledger",
]
