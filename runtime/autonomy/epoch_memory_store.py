# SPDX-License-Identifier: Apache-2.0
"""
EpochMemoryStore — Governed cross-epoch learning ledger for ADAAD Phase 52.

Purpose:
    Persist a rolling window of epoch outcome summaries so the mutation engine
    accumulates *structured memory* across sessions. Unlike BanditSelector
    (which stores only win/loss counts per arm), EpochMemoryStore records
    the qualitative signature of each epoch: which strategy succeeded, what
    fitness delta was observed, which mutation type was selected, and the
    resulting lineage digest. This gives the LearningSignalExtractor enough
    history to derive actionable guidance for future proposal generation.

Architecture contract:
    - Append-only; entries are write-once. No retroactive modification.
    - SHA-256 hash-chained: each entry records the hash of the previous entry,
      producing a tamper-evident lineage chain identical to the evidence ledger
      pattern used throughout ADAAD.
    - Rolling window of MEMORY_WINDOW_SIZE entries (default 100). Oldest entries
      are evicted when the window is full; the chain is NOT broken — the last
      evicted entry hash is carried forward as the anchor.
    - All arithmetic is bounded and deterministic; no RNG.
    - File writes are atomic (write-to-temp + rename).

Constitutional invariants:
    - MEMORY-0: EpochMemoryStore is ADVISORY only. GovernanceGate is never
      invoked here. Learning signals derived from this store are inputs to
      proposal generation — they do not approve or promote mutations.
    - MEMORY-1: Entry integrity is verified on load. A corrupt or tampered
      chain raises EpochMemoryIntegrityError (fail-closed). Learning signal
      degrades to empty on integrity failure — epoch execution continues.
    - MEMORY-2: All fields are deterministic given identical inputs. No
      wall-clock time in digest computation (epoch_id carries temporal context).

Storage format (JSONL, UTF-8):
    One JSON object per line. Each entry:
    {
        "seq":                <int>   — monotonic sequence number
        "epoch_id":           <str>   — epoch identifier string
        "winning_agent":      <str>   — "architect" | "dream" | "beast" | null
        "winning_mutation_type": <str> | null
        "winning_strategy_id": <str> | null
        "fitness_delta":      <float> — post-epoch fitness change (may be 0.0)
        "proposal_count":     <int>   — total proposals evaluated this epoch
        "accepted_count":     <int>   — proposals that passed GovernanceGate
        "context_hash":       <str>   — short deterministic CodebaseContext context hash
        "constitution_version": <str>
        "entry_digest":       <str>   — SHA-256 of canonical entry fields
        "prev_digest":        <str>   — SHA-256 of previous entry (or GENESIS_DIGEST)
    }

Extension point (Phase 53+):
    EpochMemoryStore.export_window() provides the raw entry list for
    external analytics or federation propagation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MEMORY_WINDOW_SIZE: int = 100
GENESIS_DIGEST: str = "0" * 64
STORE_DEFAULT_PATH: Path = Path("runtime/state/epoch_memory.jsonl")
_ENTRY_VERSION: str = "52.0"
_INTEGRITY_REASON_CODE: str = "epoch_memory_integrity_broken"
_LOAD_PARSE_REASON_CODE: str = "epoch_memory_load_parse_error"
_LOAD_IO_REASON_CODE: str = "epoch_memory_load_io_error"

_LOG = logging.getLogger(__name__)

_CANON_ENTRY_FIELDS: tuple[str, ...] = (
    "seq",
    "epoch_id",
    "winning_agent",
    "winning_mutation_type",
    "winning_strategy_id",
    "fitness_delta",
    "proposal_count",
    "accepted_count",
    "context_hash",
    "constitution_version",
    "entry_version",
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class EpochMemoryIntegrityError(RuntimeError):
    """Raised when the hash chain is broken or an entry digest is invalid."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EpochMemoryEntry:
    """Immutable record of a single epoch outcome stored in EpochMemoryStore."""

    seq: int
    epoch_id: str
    winning_agent: Optional[str]                 # None when no winner
    winning_mutation_type: Optional[str]
    winning_strategy_id: Optional[str]
    fitness_delta: float
    proposal_count: int
    accepted_count: int
    context_hash: str
    constitution_version: str
    entry_digest: str
    prev_digest: str
    entry_version: str = _ENTRY_VERSION

    # ------------------------------------------------------------------
    # Canonical digest helpers
    # ------------------------------------------------------------------

    @classmethod
    def _canonical_json(
        cls,
        seq: int,
        epoch_id: str,
        winning_agent: Optional[str],
        winning_mutation_type: Optional[str],
        winning_strategy_id: Optional[str],
        fitness_delta: float,
        proposal_count: int,
        accepted_count: int,
        context_hash: str,
        constitution_version: str,
        entry_version: str,
    ) -> str:
        payload = {k: v for k, v in {
            "seq": seq,
            "epoch_id": epoch_id,
            "winning_agent": winning_agent,
            "winning_mutation_type": winning_mutation_type,
            "winning_strategy_id": winning_strategy_id,
            "fitness_delta": round(float(fitness_delta), 6),
            "proposal_count": proposal_count,
            "accepted_count": accepted_count,
            "context_hash": context_hash,
            "constitution_version": constitution_version,
            "entry_version": entry_version,
        }.items()}
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def compute_digest(
        cls,
        *,
        seq: int,
        epoch_id: str,
        winning_agent: Optional[str],
        winning_mutation_type: Optional[str],
        winning_strategy_id: Optional[str],
        fitness_delta: float,
        proposal_count: int,
        accepted_count: int,
        context_hash: str,
        constitution_version: str,
        entry_version: str = _ENTRY_VERSION,
    ) -> str:
        canonical = cls._canonical_json(
            seq=seq,
            epoch_id=epoch_id,
            winning_agent=winning_agent,
            winning_mutation_type=winning_mutation_type,
            winning_strategy_id=winning_strategy_id,
            fitness_delta=fitness_delta,
            proposal_count=proposal_count,
            accepted_count=accepted_count,
            context_hash=context_hash,
            constitution_version=constitution_version,
            entry_version=entry_version,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Return True iff entry_digest matches the re-computed digest."""
        expected = self.__class__.compute_digest(
            seq=self.seq,
            epoch_id=self.epoch_id,
            winning_agent=self.winning_agent,
            winning_mutation_type=self.winning_mutation_type,
            winning_strategy_id=self.winning_strategy_id,
            fitness_delta=self.fitness_delta,
            proposal_count=self.proposal_count,
            accepted_count=self.accepted_count,
            context_hash=self.context_hash,
            constitution_version=self.constitution_version,
            entry_version=self.entry_version,
        )
        return self.entry_digest == expected

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "epoch_id": self.epoch_id,
            "winning_agent": self.winning_agent,
            "winning_mutation_type": self.winning_mutation_type,
            "winning_strategy_id": self.winning_strategy_id,
            "fitness_delta": self.fitness_delta,
            "proposal_count": self.proposal_count,
            "accepted_count": self.accepted_count,
            "context_hash": self.context_hash,
            "constitution_version": self.constitution_version,
            "entry_version": self.entry_version,
            "entry_digest": self.entry_digest,
            "prev_digest": self.prev_digest,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EpochMemoryEntry":
        # Dual-read compatibility:
        # - legacy rows persisted `context_hash` (historically 8-hex MD5-derived)
        # - transitional/future rows may carry `context_hash_v2` (SHA-256-derived short hash)
        context_hash = str(d.get("context_hash", ""))
        if not context_hash:
            context_hash = str(d.get("context_hash_v2", ""))
        return cls(
            seq=int(d["seq"]),
            epoch_id=str(d["epoch_id"]),
            winning_agent=d.get("winning_agent"),
            winning_mutation_type=d.get("winning_mutation_type"),
            winning_strategy_id=d.get("winning_strategy_id"),
            fitness_delta=float(d.get("fitness_delta", 0.0)),
            proposal_count=int(d.get("proposal_count", 0)),
            accepted_count=int(d.get("accepted_count", 0)),
            context_hash=context_hash,
            constitution_version=str(d.get("constitution_version", "0.9.0")),
            entry_version=str(d.get("entry_version", _ENTRY_VERSION)),
            entry_digest=str(d["entry_digest"]),
            prev_digest=str(d.get("prev_digest", GENESIS_DIGEST)),
        )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class EpochMemoryStore:
    """
    Governed cross-epoch memory store.

    Usage::

        store = EpochMemoryStore()
        store.emit(
            epoch_id="epoch-0042",
            winning_agent="architect",
            winning_mutation_type="structural",
            winning_strategy_id="adaptive_self_mutate",
            fitness_delta=0.12,
            proposal_count=9,
            accepted_count=1,
            context_hash="a3f2b1c0",
            constitution_version="0.9.0",
        )
        entries = store.window()
    """

    def __init__(
        self,
        path: Path = STORE_DEFAULT_PATH,
        window_size: int = MEMORY_WINDOW_SIZE,
    ) -> None:
        self._path = Path(path)
        self._window_size = window_size
        self._entries: List[EpochMemoryEntry] = []
        self._anchor_digest: str = GENESIS_DIGEST   # digest of oldest evicted entry
        self._next_seq: int = 0
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def emit(
        self,
        *,
        epoch_id: str,
        winning_agent: Optional[str],
        winning_mutation_type: Optional[str],
        winning_strategy_id: Optional[str],
        fitness_delta: float,
        proposal_count: int,
        accepted_count: int,
        context_hash: str,
        constitution_version: str,
    ) -> EpochMemoryEntry:
        """
        Append an epoch outcome to the memory ledger.

        Raises EpochMemoryIntegrityError if the store is corrupt.
        Never raises on I/O failure — write errors are swallowed to prevent
        blocking epoch execution (MEMORY-1 degradation path).
        """
        prev = self._entries[-1].entry_digest if self._entries else self._anchor_digest
        seq = self._next_seq

        digest = EpochMemoryEntry.compute_digest(
            seq=seq,
            epoch_id=epoch_id,
            winning_agent=winning_agent,
            winning_mutation_type=winning_mutation_type,
            winning_strategy_id=winning_strategy_id,
            fitness_delta=fitness_delta,
            proposal_count=proposal_count,
            accepted_count=accepted_count,
            context_hash=context_hash,
            constitution_version=constitution_version,
        )

        entry = EpochMemoryEntry(
            seq=seq,
            epoch_id=epoch_id,
            winning_agent=winning_agent,
            winning_mutation_type=winning_mutation_type,
            winning_strategy_id=winning_strategy_id,
            fitness_delta=fitness_delta,
            proposal_count=proposal_count,
            accepted_count=accepted_count,
            context_hash=context_hash,
            constitution_version=constitution_version,
            entry_digest=digest,
            prev_digest=prev,
        )

        self._entries.append(entry)
        self._next_seq += 1

        # Evict oldest when window full; carry its digest as anchor
        while len(self._entries) > self._window_size:
            evicted = self._entries.pop(0)
            self._anchor_digest = evicted.entry_digest

        self._persist()
        return entry

    def window(self, n: Optional[int] = None) -> List[EpochMemoryEntry]:
        """Return the most recent n entries (or all if n is None)."""
        if n is None:
            return list(self._entries)
        return list(self._entries[-n:])

    def head(self) -> Optional[EpochMemoryEntry]:
        """Return the most recent entry, or None if empty."""
        return self._entries[-1] if self._entries else None

    def chain_valid(self) -> bool:
        """Verify the integrity of all entries in the current window."""
        for entry in self._entries:
            if not entry.verify_integrity():
                return False
        # Check prev_digest links
        for i, entry in enumerate(self._entries):
            if i == 0:
                expected_prev = self._anchor_digest
            else:
                expected_prev = self._entries[i - 1].entry_digest
            if entry.prev_digest != expected_prev:
                return False
        return True

    def export_window(self) -> List[Dict[str, Any]]:
        """Serialisable export of the current window (for endpoints / federation)."""
        return [e.to_dict() for e in self._entries]

    def stats(self) -> Dict[str, Any]:
        """Summary statistics for Aponi endpoint consumption."""
        entries = self._entries
        if not entries:
            return {"count": 0, "window_size": self._window_size, "chain_valid": True}

        agent_wins: Dict[str, int] = {}
        strategy_wins: Dict[str, int] = {}
        total_fitness_delta = 0.0
        total_proposals = 0
        total_accepted = 0

        for e in entries:
            if e.winning_agent:
                agent_wins[e.winning_agent] = agent_wins.get(e.winning_agent, 0) + 1
            if e.winning_strategy_id:
                strategy_wins[e.winning_strategy_id] = strategy_wins.get(e.winning_strategy_id, 0) + 1
            total_fitness_delta += e.fitness_delta
            total_proposals += e.proposal_count
            total_accepted += e.accepted_count

        n = len(entries)
        return {
            "count": n,
            "window_size": self._window_size,
            "chain_valid": self.chain_valid(),
            "avg_fitness_delta": round(total_fitness_delta / n, 6) if n else 0.0,
            "total_proposals": total_proposals,
            "total_accepted": total_accepted,
            "acceptance_rate": round(total_accepted / total_proposals, 4) if total_proposals else 0.0,
            "agent_win_counts": agent_wins,
            "strategy_win_counts": strategy_wins,
            "head_seq": entries[-1].seq,
            "anchor_digest_prefix": self._anchor_digest[:8],
            "head_digest_prefix": entries[-1].entry_digest[:8],
        }

    # ------------------------------------------------------------------
    # Internal: persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load entries from disk. On integrity failure, clear and restart."""
        if not self._path.exists():
            return
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
            entries: List[EpochMemoryEntry] = []
            anchor = GENESIS_DIGEST
            previous_digest = anchor
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#anchor:"):
                    anchor = line[len("#anchor:"):]
                    previous_digest = anchor
                    continue
                raw = json.loads(line)
                entry = EpochMemoryEntry.from_dict(raw)
                if not entry.verify_integrity():
                    raise EpochMemoryIntegrityError(
                        f"{_INTEGRITY_REASON_CODE}:entry_digest_mismatch"
                    )
                if entry.prev_digest != previous_digest:
                    raise EpochMemoryIntegrityError(
                        f"{_INTEGRITY_REASON_CODE}:prev_digest_mismatch"
                    )
                entries.append(entry)
                previous_digest = entry.entry_digest
            self._anchor_digest = anchor
            self._entries = entries[-self._window_size:]
            self._next_seq = (self._entries[-1].seq + 1) if self._entries else 0
        except EpochMemoryIntegrityError as exc:
            self._degrade_to_empty(reason_code=_INTEGRITY_REASON_CODE, detail=str(exc))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            self._degrade_to_empty(reason_code=_LOAD_PARSE_REASON_CODE, detail=str(exc))
        except (OSError, UnicodeDecodeError) as exc:
            self._degrade_to_empty(reason_code=_LOAD_IO_REASON_CODE, detail=str(exc))

    def _degrade_to_empty(self, *, reason_code: str, detail: str) -> None:
        """Reset to empty state and emit a structured warning event."""
        self._entries = []
        self._anchor_digest = GENESIS_DIGEST
        self._next_seq = 0
        payload = {
            "event_type": "epoch_memory_store_load_degraded.v1",
            "reason_code": reason_code,
            "path": str(self._path),
            "detail": detail,
        }
        _LOG.warning(
            "EpochMemoryStore load degraded: %s",
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
        )

    def _persist(self) -> None:
        """Atomically write all current window entries to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            lines: List[str] = [f"#anchor:{self._anchor_digest}"]
            for entry in self._entries:
                lines.append(json.dumps(entry.to_dict(), separators=(",", ":")))
            content = "\n".join(lines) + "\n"
            fd, tmp = tempfile.mkstemp(
                dir=self._path.parent, prefix=".epoch_memory_tmp_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(content)
                os.replace(tmp, self._path)
            except Exception:  # noqa: BLE001
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        except Exception:  # noqa: BLE001 — I/O failure must never block epoch
            pass
