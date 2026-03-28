# SPDX-License-Identifier: Apache-2.0
"""
IdentityLedger — Morphogenetic Memory (MMEM) — Phase 94 · INNOV-10
=================================================================

Hash-chained, HUMAN-0-gated, append-only store of IdentityStatements.
Encodes the system's formal self-model — consulted by every mutation
proposal before evaluation begins.

Constitutional Invariants (Hard-class):
  MMEM-0         : check() MUST never raise. Failure returns fallback_used=True.
  MMEM-CHAIN-0   : Every IdentityStatement MUST carry the SHA-256 hash of its
                   predecessor. Any chain discontinuity MUST raise ChainIntegrityError.
  MMEM-READONLY-0: check() is READ-ONLY. No append, modify, or delete.
  MMEM-WIRE-0    : run_epoch() MUST call IdentityContextInjector before Phase 1.
  MMEM-LEDGER-0  : append() without attestation_token raises
                   IdentityAppendWithoutAttestationError.
  MMEM-DETERM-0  : Identical inputs → identical statement_hash. No datetime/random/uuid4.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

ZERO_HASH: str = "sha256:" + "0" * 64
GENESIS_SEED_PATH: Path = Path("artifacts/governance/phase94/identity_ledger_seed.json")
DEFAULT_LEDGER_PATH: Path = Path("data/identity_ledger.jsonl")

VALID_CATEGORIES = frozenset(
    {"purpose", "architectural_intent", "human_authority",
     "lineage", "failure_mode", "active_goal", "value", "capability", "boundary"}
)

# Anti-pattern tables — static, deterministic (MMEM-DETERM-0)
_ANTI_PATTERNS: dict = {
    "human_authority": [
        "autonomous release", "bypass human", "remove gate", "delegate to",
        "skip human", "without human", "no human", "remove human",
        "allow autonomous", "automatic promotion", "remove human-0",
        "bypass human-0", "skip human-0",
    ],
    "failure_mode": [
        "silently pass", "ignore error", "suppress exception", "fail open",
        "swallow exception", "silent failure",
    ],
    "lineage": [
        "skip ledger", "no audit", "untracked", "outside pipeline",
        "remove ledger", "bypass ledger",
    ],
    "architectural_intent": [
        "remove governance", "bypass gate", "skip gate", "remove pipeline",
        "remove constitutional",
    ],
}


# ---------------------------------------------------------------------------
# Exceptions
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
    statement_id: str
    category: str
    statement: str
    author: str
    epoch_id: str
    predecessor_hash: str
    statement_hash: str = ""
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
    consistency_score: float
    violated_statements: List[str] = field(default_factory=list)
    notes: str = ""
    fallback_used: bool = False


# ---------------------------------------------------------------------------
# Helpers (MMEM-DETERM-0)
# ---------------------------------------------------------------------------

def _compute_hash(statement_id: str, statement: str, predecessor_hash: str) -> str:
    """Deterministic SHA-256. No datetime/random/uuid4 (MMEM-DETERM-0)."""
    payload = {
        "id": statement_id,
        "predecessor": predecessor_hash,
        "statement": statement,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return "sha256:" + digest


def _score_consistency(
    statements: List[IdentityStatement],
    mutation_intent: str,
    diff_summary: str,
) -> Tuple[float, List[str]]:
    """Deterministic keyword/anti-pattern heuristic scoring (MMEM-DETERM-0)."""
    if not statements:
        return 1.0, []

    combined = (mutation_intent + " " + diff_summary).lower()
    violated_ids: List[str] = []
    scores: List[float] = []

    for stmt in statements:
        stmt_score = 1.0
        for pattern in _ANTI_PATTERNS.get(stmt.category, []):
            if pattern in combined:
                stmt_score -= 0.4
        stmt_score = max(0.0, stmt_score)
        scores.append(stmt_score)
        if stmt_score < 0.7:
            violated_ids.append(stmt.statement_id)

    aggregate = sum(scores) / len(scores)
    return round(min(1.0, max(0.0, aggregate)), 6), violated_ids


# ---------------------------------------------------------------------------
# IdentityLedger
# ---------------------------------------------------------------------------

class IdentityLedger:
    """Hash-chained, HUMAN-0-gated identity store."""

    def __init__(
        self,
        ledger_path: Path = DEFAULT_LEDGER_PATH,
        genesis_seed_path: Path = GENESIS_SEED_PATH,
    ) -> None:
        self._ledger_path = Path(ledger_path)
        self._genesis_seed_path = Path(genesis_seed_path)
        self._statements: List[IdentityStatement] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(
        self,
        mutation_id: str,
        mutation_intent: str,
        diff_summary: str = "",
    ) -> IdentityConsistencyResult:
        """Read-only identity consistency check. NEVER raises (MMEM-0)."""
        try:
            return self._check_impl(mutation_id, mutation_intent, diff_summary)
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
        """Inner implementation — called under MMEM-0 guard. READ-ONLY (MMEM-READONLY-0)."""
        # Distinguish None (corrupt state) from empty list (valid, trivially consistent).
        # None raises AttributeError so MMEM-0 outer guard produces fallback_used=True.
        if self._statements is None:
            raise AttributeError(
                "MMEM-0: _statements is None — corrupt ledger state"
            )
        if len(self._statements) == 0:
            return IdentityConsistencyResult(
                mutation_id=mutation_id,
                consistent=True,
                consistency_score=1.0,
                notes="No statements loaded — trivially consistent",
            )
        score, violated = _score_consistency(
            self._statements, mutation_intent, diff_summary
        )
        return IdentityConsistencyResult(
            mutation_id=mutation_id,
            consistent=(len(violated) == 0),
            consistency_score=score,
            violated_statements=violated,
            notes=f"{len(violated)} statement(s) flagged" if violated else "",
        )

    def append(
        self,
        category: str,
        statement: str,
        author: str,
        epoch_id: str,
        attestation_token: str,
    ) -> IdentityStatement:
        """Append a new IdentityStatement. HUMAN-0 gated (MMEM-LEDGER-0)."""
        # MMEM-LEDGER-0: validate BEFORE any state mutation
        if not attestation_token or not attestation_token.strip():
            raise IdentityAppendWithoutAttestationError(
                "MMEM-LEDGER-0: attestation_token required for IdentityLedger.append()"
            )
        predecessor_hash = (
            self._statements[-1].statement_hash if self._statements else ZERO_HASH
        )
        next_num = len(self._statements) + 1
        statement_id = f"IS-{next_num:03d}"
        stmt = IdentityStatement(
            statement_id=statement_id,
            category=category,
            statement=statement,
            author=author,
            epoch_id=epoch_id,
            predecessor_hash=predecessor_hash,
            statement_hash="",
            human_signoff_token=attestation_token,
        )
        self._persist(stmt)
        self._statements.append(stmt)
        return stmt

    def verify_chain(self) -> bool:
        """Full O(n) chain integrity verification (MMEM-CHAIN-0)."""
        if not self._statements:
            return True
        for i, stmt in enumerate(self._statements):
            expected_hash = _compute_hash(
                stmt.statement_id, stmt.statement, stmt.predecessor_hash
            )
            if expected_hash != stmt.statement_hash:
                raise ChainIntegrityError(
                    f"Hash mismatch at {stmt.statement_id}: "
                    f"expected {expected_hash[:20]}... stored {stmt.statement_hash[:20]}..."
                )
            if i > 0:
                expected_pred = self._statements[i - 1].statement_hash
                if stmt.predecessor_hash != expected_pred:
                    raise ChainIntegrityError(
                        f"Predecessor mismatch at {stmt.statement_id}: "
                        f"expected {expected_pred[:20]}... got {stmt.predecessor_hash[:20]}..."
                    )
        return True

    def statements(self) -> List[IdentityStatement]:
        return list(self._statements)

    def __len__(self) -> int:
        return len(self._statements)

    # ------------------------------------------------------------------
    # Private loaders
    # ------------------------------------------------------------------

    def _load_genesis_seed(self) -> None:
        """Deserialise genesis seed JSON → IdentityStatement list.

        Builds internal hash chain from scratch via _compute_hash.
        seed's statement_digest/chain_hash are attestation metadata only.
        """
        path = self._genesis_seed_path
        if not path.exists():
            raise IdentityLedgerLoadError(f"genesis seed not found: {path}")
        try:
            with open(path, encoding="utf-8") as f:
                seed = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise IdentityLedgerLoadError(f"genesis seed corrupt: {exc}") from exc

        raw_stmts = seed.get("statements")
        if not raw_stmts or not isinstance(raw_stmts, list):
            raise IdentityLedgerLoadError("genesis seed missing 'statements' list")

        attestation = seed.get("human0_attestation", {})
        attestation_id = attestation.get("attestation_id", "")
        version = seed.get("version", "v9.26.0")

        predecessor = ZERO_HASH
        self._statements = []

        for entry in raw_stmts:
            for req in ("statement_id", "category", "statement"):
                if req not in entry:
                    raise IdentityLedgerLoadError(
                        f"genesis statement missing required field '{req}': {entry}"
                    )
            stmt = IdentityStatement(
                statement_id=entry["statement_id"],
                category=entry["category"],
                statement=entry["statement"],
                author=entry.get("author", attestation.get("governor", "Dustin L. Reid")),
                epoch_id=entry.get("epoch_id", version),
                predecessor_hash=predecessor,
                statement_hash="",
                human_signoff_token=entry.get("human_signoff_token", attestation_id),
                rationale=entry.get("rationale", ""),
            )
            predecessor = stmt.statement_hash
            self._statements.append(stmt)

    def _persist(self, stmt: IdentityStatement) -> None:
        """Append a statement record to the JSONL ledger file."""
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "statement_id": stmt.statement_id,
            "category": stmt.category,
            "statement": stmt.statement,
            "author": stmt.author,
            "epoch_id": stmt.epoch_id,
            "predecessor_hash": stmt.predecessor_hash,
            "statement_hash": stmt.statement_hash,
            "human_signoff_token": stmt.human_signoff_token,
            "rationale": stmt.rationale,
        }
        with open(self._ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")

    # ------------------------------------------------------------------
    # Class-method constructors
    # ------------------------------------------------------------------

    @classmethod
    def load_genesis(
        cls,
        genesis_seed_path: Path = GENESIS_SEED_PATH,
        ledger_path: Path = DEFAULT_LEDGER_PATH,
    ) -> "IdentityLedger":
        """Construct an IdentityLedger pre-loaded from the genesis seed."""
        instance = cls(ledger_path=ledger_path, genesis_seed_path=genesis_seed_path)
        instance._load_genesis_seed()
        return instance


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
