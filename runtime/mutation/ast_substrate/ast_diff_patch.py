"""
runtime.mutation.ast_substrate.ast_diff_patch
=============================================
ASTDiffPatch — the DNA of ADAAD mutation.

Every code mutation is represented as a single, governed, hash-verifiable
ASTDiffPatch.  This is the primitive that flows from ProposalEngine through
StaticSafetyScanner → SandboxTournament → GovernanceGate → PatchApplicator.

Invariants
----------
PATCH-SIZE-0   max_ast_nodes=40, max_files=2 enforced at construction.
SANDBOX-DIV-0  before_ast_hash and after_ast_hash derived from ast.dump()
               (formatting-invariant).  Divergence = rejection.
TIER0-SELF-0   Tier-0 bound modules may not appear as target_file.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class MutationKind(str, Enum):
    REFACTOR        = "refactor"       # pure structural improvement
    HOTFIX          = "hotfix"         # targeted defect correction
    PERFORMANCE     = "performance"    # speed / resource optimisation
    SIMPLIFICATION  = "simplification" # complexity reduction
    EXPERIMENTAL    = "experimental"   # exploratory / niche expansion


class RiskClass(str, Enum):
    CLASS_A = "class_a"  # standard gate — deterministic approval possible
    CLASS_B = "class_b"  # exception token required for approval


# ---------------------------------------------------------------------------
# Constants (PATCH-SIZE-0)
# ---------------------------------------------------------------------------

MAX_AST_NODES: int = 40
MAX_FILES: int = 2


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PatchSizeViolation(Exception):
    """Raised when PATCH-SIZE-0 is violated at construction."""


class PatchHashError(Exception):
    """Raised when a hash computed from source does not match stored value."""


# ---------------------------------------------------------------------------
# Core dataclass
# ---------------------------------------------------------------------------

@dataclass
class ASTDiffPatch:
    """The DNA primitive: a single governed, hash-verifiable code mutation.

    Attributes
    ----------
    mutation_kind       Category of mutation (MutationKind enum).
    target_file         Primary source file path being mutated.
    before_source       Original source text before the patch.
    after_source        Proposed source text after the patch.
    intent              Natural-language description of the change.
    risk_class          Class A (standard gate) or Class B (exception token).
    capability_id       Owning capability from CapabilityRegistry (optional).
    auxiliary_files     Additional files modified (len ≤ MAX_FILES-1).
    metadata            Arbitrary enrichment data.
    before_ast_hash     sha256(ast.dump(ast.parse(before_source))).
    after_ast_hash      sha256(ast.dump(ast.parse(after_source))).
    patch_hash          sha256 of the full patch state (SANDBOX-DIV-0).
    before_node_count   AST node count in before_source.
    after_node_count    AST node count in after_source.
    delta_node_count    after_node_count - before_node_count.
    """

    mutation_kind: MutationKind
    target_file: str
    before_source: str
    after_source: str
    intent: str
    risk_class: RiskClass = RiskClass.CLASS_A
    capability_id: Optional[str] = None
    auxiliary_files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # computed — populated by __post_init__
    before_ast_hash: str = field(default="", init=False)
    after_ast_hash: str = field(default="", init=False)
    patch_hash: str = field(default="", init=False)
    before_node_count: int = field(default=0, init=False)
    after_node_count: int = field(default=0, init=False)
    delta_node_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        # Normalise enum fields (accept raw string values)
        if isinstance(self.mutation_kind, str):
            self.mutation_kind = MutationKind(self.mutation_kind)
        if isinstance(self.risk_class, str):
            self.risk_class = RiskClass(self.risk_class)

        # Parse both sources — will raise SyntaxError on invalid Python
        before_tree = ast.parse(self.before_source, filename=self.target_file)
        after_tree = ast.parse(self.after_source, filename=self.target_file)

        # Formatting-invariant AST hashes (SANDBOX-DIV-0)
        self.before_ast_hash = _ast_hash(before_tree)
        self.after_ast_hash = _ast_hash(after_tree)

        # Node counts
        self.before_node_count = _node_count(before_tree)
        self.after_node_count = _node_count(after_tree)
        self.delta_node_count = self.after_node_count - self.before_node_count

        # PATCH-SIZE-0 — enforce after counts are computed
        total_files = 1 + len(self.auxiliary_files)
        if total_files > MAX_FILES:
            raise PatchSizeViolation(
                f"PATCH-SIZE-0: patch spans {total_files} files, max={MAX_FILES}"
            )
        if abs(self.delta_node_count) > MAX_AST_NODES:
            raise PatchSizeViolation(
                f"PATCH-SIZE-0: |delta_nodes|={abs(self.delta_node_count)} "
                f"exceeds max={MAX_AST_NODES}"
            )

        # Canonical patch hash — binds entire state (SANDBOX-DIV-0)
        self.patch_hash = self._compute_patch_hash()

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def verify_before_hash(self, actual_source: str) -> bool:
        """Return True if *actual_source* on disk matches before_ast_hash."""
        try:
            tree = ast.parse(actual_source, filename=self.target_file)
            return _ast_hash(tree) == self.before_ast_hash
        except SyntaxError:
            return False

    def verify_after_hash(self, applied_source: str) -> bool:
        """Return True if *applied_source* matches after_ast_hash (SANDBOX-DIV-0)."""
        try:
            tree = ast.parse(applied_source, filename=self.target_file)
            return _ast_hash(tree) == self.after_ast_hash
        except SyntaxError:
            return False

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_kind": self.mutation_kind.value,
            "target_file": self.target_file,
            "before_source": self.before_source,
            "after_source": self.after_source,
            "intent": self.intent,
            "risk_class": self.risk_class.value,
            "capability_id": self.capability_id,
            "auxiliary_files": self.auxiliary_files,
            "metadata": self.metadata,
            "before_ast_hash": self.before_ast_hash,
            "after_ast_hash": self.after_ast_hash,
            "patch_hash": self.patch_hash,
            "before_node_count": self.before_node_count,
            "after_node_count": self.after_node_count,
            "delta_node_count": self.delta_node_count,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, default=str)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASTDiffPatch":
        patch = cls(
            mutation_kind=MutationKind(d["mutation_kind"]),
            target_file=d["target_file"],
            before_source=d["before_source"],
            after_source=d["after_source"],
            intent=d["intent"],
            risk_class=RiskClass(d.get("risk_class", "class_a")),
            capability_id=d.get("capability_id"),
            auxiliary_files=d.get("auxiliary_files", []),
            metadata=d.get("metadata", {}),
        )
        return patch

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_patch_hash(self) -> str:
        state = {
            "mutation_kind": self.mutation_kind.value,
            "target_file": self.target_file,
            "before_ast_hash": self.before_ast_hash,
            "after_ast_hash": self.after_ast_hash,
            "intent": self.intent,
            "risk_class": self.risk_class.value,
            "delta_node_count": self.delta_node_count,
        }
        canonical = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def __repr__(self) -> str:
        return (
            f"ASTDiffPatch(kind={self.mutation_kind.value}, "
            f"file={self.target_file!r}, "
            f"delta_nodes={self.delta_node_count:+d}, "
            f"risk={self.risk_class.value})"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ast_hash(tree: ast.AST) -> str:
    """SHA-256 of ast.dump() — formatting-invariant (SANDBOX-DIV-0)."""
    canonical = ast.dump(tree, indent=None)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _node_count(tree: ast.AST) -> int:
    return sum(1 for _ in ast.walk(tree))
