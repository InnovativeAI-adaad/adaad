# SPDX-License-Identifier: Apache-2.0
"""
IdentityLedger — Morphogenetic Memory (MMEM) — Phase 94 · INNOV-10
=================================================================

Hash-chained, HUMAN-0-gated, append-only store of IdentityStatements.
Encodes the system's formal self-model — consulted by every mutation
proposal before evaluation begins.

Constitutional Invariants (Hard-class):
  MMEM-0         : IdentityLedger.check() MUST never raise. Any failure
                   MUST return IdentityConsistencyResult(consistent=False,
                   fallback_used=True). The mutation pipeline is never
                   blocked by an identity check error.
  MMEM-CHAIN-0   : Every IdentityStatement MUST carry the SHA-256 hash of
                   its predecessor. The genesis statement uses ZERO_HASH.
                   Any chain discontinuity MUST raise ChainIntegrityError.
  MMEM-READONLY-0: IdentityLedger.check() is a READ-ONLY surface. It MUST
                   NOT append, modify, or delete statements. Side-effect-
                   free by contract.
  MMEM-WIRE-0    : EvolutionLoop run_epoch() MUST call IdentityContextInjector
                   before Phase 1 (propose). If the injector is absent or
                   raises, the epoch continues unblocked (degraded mode).
  MMEM-LEDGER-0  : Any append to the IdentityLedger MUST be accompanied by
                   a valid HUMAN-0 attestation token. Appends without
                   attestation MUST raise IdentityAppendWithoutAttestationError.
  MMEM-DETERM-0  : Given identical statements and predecessor hash, the
                   computed statement_hash MUST be identical across runs.
                   No datetime.now(), random, or uuid4() in the hash path.

Architecture:
  ─ persisted as JSONL: one JSON object per line (append-only)
  ─ hash chain: each entry carries predecessor_hash + own statement_hash
  ─ genesis seed loaded from artifacts/governance/phase94/identity_ledger_seed.json
  ─ check() is O(n) read-only scan; no locking required (read-only surface)
  ─ append() is HUMAN-0 gated via attestation_token validation

Scaffold status: IMPLEMENTATION PENDING
  [ ] _load_genesis_seed() — deserialise seed JSON → IdentityStatement list
  [ ] _load_from_file()    — deserialise JSONL ledger
  [ ] _persist()           — append JSONL entry
  [ ] append()             — HUMAN-0 gated add
  [ ] check()              — read-only consistency scan (MMEM-0 / MMEM-READONLY-0)
  [ ] verify_chain()       — full O(n) chain integrity check (MMEM-CHAIN-0)
  [ ] _compute_hash()      — deterministic SHA-256 statement hash (MMEM-DETERM-0)
  [ ] load_genesis()       — class-method to construct from seed artifact
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ZERO_HASH: str = "sha256:" + "0" * 64
GENESIS_SEED_PATH: Path = Path(
    "artifacts/governance/phase94/identity_ledger_seed.json"
)
DEFAULT_LEDGER_PATH: Path = Path("data/identity_ledger.jsonl")

VALID_CATEGORIES = frozenset(
    {"purpose", "architectural_intent", "human_authority",
     "lineage", "failure_mode", "active_goal", "value", "capability",
     "boundary"}
)

# ---------------------------------------------------------------------------
# Exceptions (Hard-class — never swallowed inside IdentityLedger)
# ---------------------------------------------------------------------------


class ChainIntegrityError(Exception):
    """Raised when predecessor_hash chain is broken (MMEM-CHAIN-0)."""


class IdentityAppendWithoutAttestationError(Exception):
    """Raised when append() called without valid HUMAN-0 attestation token (MMEM-LEDGER-0)."""


class IdentityLedgerLoadError(Exception):
    """Raised when ledger file is corrupt or genesis seed is missing."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class IdentityStatement:
    """A single entry in the IdentityLedger hash chain."""

    statement_id: str        # e.g. "IS-001"
    category: str            # one of VALID_CATEGORIES
    statement: str           # plain-language identity assertion
    author: str              # human author handle
    epoch_id: str            # epoch or version context
    predecessor_hash: str    # hash of prior statement; ZERO_HASH for genesis
    statement_hash: str = "" # computed on init if absent (MMEM-DETERM-0)
    human_signoff_token: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.statement_hash:
            self.statement_hash = _compute_hash(
                self.statement_id, self.statement, self.predecessor_hash
            )


@dataclass
class IdentityConsistencyResult:
    """Returned by IdentityLedger.check() — MMEM-0 guarantees no raise."""

    mutation_id: str
    consistent: bool
    consistency_score: float          # [0.0, 1.0]
    violated_statements: List[str] = field(default_factory=list)
    notes: str = ""
    fallback_used: bool = False       # True when MMEM-0 fallback triggered


# ---------------------------------------------------------------------------
# Helpers (MMEM-DETERM-0)
# ---------------------------------------------------------------------------


def _compute_hash(statement_id: str, statement: str, predecessor_hash: str) -> str:
    """Deterministic SHA-256 hash over canonical fields.

    MMEM-DETERM-0: no datetime, random, or uuid in this path.
    TODO: implement
    """
    raise NotImplementedError("_compute_hash — SCAFFOLD: implement in Phase 94")


def _score_consistency(
    statements: List[IdentityStatement],
    mutation_intent: str,
    diff_summary: str,
) -> tuple[float, List[str]]:
    """Return (score, violated_ids) — purely functional, read-only.

    TODO: implement keyword-based + semantic heuristic scoring.
    """
    raise NotImplementedError("_score_consistency — SCAFFOLD: implement in Phase 94")


# ---------------------------------------------------------------------------
# IdentityLedger
# ---------------------------------------------------------------------------


class IdentityLedger:
    """Hash-chained, HUMAN-0-gated identity store.

    Constitutional surface:
      - check()   — MMEM-0: never raises, read-only (MMEM-READONLY-0)
      - append()  — MMEM-LEDGER-0: requires attestation_token
      - verify_chain() — MMEM-CHAIN-0: O(n) integrity scan

    TODO: implement all methods marked with SCAFFOLD.
    """

    def __init__(
        self,
        ledger_path: Path = DEFAULT_LEDGER_PATH,
        genesis_seed_path: Path = GENESIS_SEED_PATH,
    ) -> None:
        self._ledger_path = Path(ledger_path)
        self._genesis_seed_path = Path(genesis_seed_path)
        self._statements: List[IdentityStatement] = []
        # SCAFFOLD: _load() not yet implemented
        # self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(
        self,
        mutation_id: str,
        mutation_intent: str,
        diff_summary: str = "",
    ) -> IdentityConsistencyResult:
        """Read-only identity consistency check. NEVER raises (MMEM-0).

        Returns IdentityConsistencyResult with fallback_used=True on any error.

        SCAFFOLD: returns degraded fallback until implemented.
        """
        # MMEM-0 outer guard — never let exceptions propagate
        try:
            return self._check_impl(mutation_id, mutation_intent, diff_summary)
        except NotImplementedError:
            # Scaffold fallback — consistent=True, degraded
            return IdentityConsistencyResult(
                mutation_id=mutation_id,
                consistent=True,
                consistency_score=1.0,
                notes="SCAFFOLD: check() not yet implemented — degraded pass",
                fallback_used=True,
            )
        except Exception as exc:  # noqa: BLE001
            return IdentityConsistencyResult(
                mutation_id=mutation_id,
                consistent=False,
                consistency_score=0.0,
                notes=f"MMEM-0 fallback triggered: {exc!r}",
                fallback_used=True,
            )

    def _check_impl(
        self,
        mutation_id: str,
        mutation_intent: str,
        diff_summary: str,
    ) -> IdentityConsistencyResult:
        """Inner implementation — called by check() under MMEM-0 guard.

        SCAFFOLD: implement in Phase 94.
        """
        raise NotImplementedError("_check_impl — SCAFFOLD")

    def append(
        self,
        category: str,
        statement: str,
        author: str,
        epoch_id: str,
        attestation_token: str,
    ) -> IdentityStatement:
        """Append a new IdentityStatement. HUMAN-0 gated (MMEM-LEDGER-0).

        Raises:
          IdentityAppendWithoutAttestationError — if attestation_token is empty/invalid.
          ChainIntegrityError — if chain hash cannot be computed.

        SCAFFOLD: implement in Phase 94.
        """
        raise NotImplementedError("append — SCAFFOLD")

    def verify_chain(self) -> bool:
        """Full O(n) chain integrity verification (MMEM-CHAIN-0).

        Returns True if all predecessor_hash links are intact.
        Raises ChainIntegrityError on first discontinuity.

        SCAFFOLD: implement in Phase 94.
        """
        raise NotImplementedError("verify_chain — SCAFFOLD")

    def statements(self) -> List[IdentityStatement]:
        """Read-only view of loaded statements."""
        return list(self._statements)

    def __len__(self) -> int:
        return len(self._statements)

    # ------------------------------------------------------------------
    # Private loaders
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load genesis seed then JSONL ledger overrides.

        SCAFFOLD: implement in Phase 94.
        """
        raise NotImplementedError("_load — SCAFFOLD")

    def _load_genesis_seed(self) -> None:
        """Deserialise artifacts/governance/phase94/identity_ledger_seed.json.

        SCAFFOLD: implement in Phase 94.
        """
        raise NotImplementedError("_load_genesis_seed — SCAFFOLD")

    def _persist(self, stmt: IdentityStatement) -> None:
        """Append a statement record to the JSONL ledger file.

        SCAFFOLD: implement in Phase 94.
        """
        raise NotImplementedError("_persist — SCAFFOLD")

    # ------------------------------------------------------------------
    # Class-method constructors
    # ------------------------------------------------------------------

    @classmethod
    def load_genesis(
        cls,
        genesis_seed_path: Path = GENESIS_SEED_PATH,
        ledger_path: Path = DEFAULT_LEDGER_PATH,
    ) -> "IdentityLedger":
        """Construct an IdentityLedger pre-loaded from the genesis seed.

        SCAFFOLD: implement in Phase 94.
        """
        raise NotImplementedError("load_genesis — SCAFFOLD")


__all__ = [
    "IdentityLedger",
    "IdentityStatement",
    "IdentityConsistencyResult",
    "ChainIntegrityError",
    "IdentityAppendWithoutAttestationError",
    "IdentityLedgerLoadError",
    "ZERO_HASH",
    "GENESIS_SEED_PATH",
    "DEFAULT_LEDGER_PATH",
    "VALID_CATEGORIES",
]
