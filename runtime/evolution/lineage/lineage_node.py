"""
runtime.evolution.lineage.lineage_node
=======================================
LineageNode v2 — immutable ancestry node for a single governed mutation.

Each node represents one ASTDiffPatch that entered the governed pipeline.
Nodes form a DAG via parent_id links. Epoch-level outcome tracking enables
LineageSurvival scoring (LINEAGE-STAB-0).

Invariants
----------
LINEAGE-STAB-0  A lineage is stable when it passes governance in ≥ 2 of
                any 5 consecutive epochs. Failed lineages enter 1-epoch
                cooling suspension.
EPISTASIS-0     Co-occurring mutations tracked via parent_id chain; epistasis
                detected when A+B regresses where A alone and B alone do not.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EpochOutcome(str, Enum):
    PASSED    = "passed"    # governance approved and applied
    REJECTED  = "rejected"  # governance rejected
    COOLING   = "cooling"   # suspended for 1 epoch (LINEAGE-STAB-0)
    PENDING   = "pending"   # queued, not yet evaluated


class MutationNiche(str, Enum):
    PERFORMANCE     = "performance"
    ARCHITECTURE    = "architecture"
    SAFETY          = "safety"
    SIMPLIFICATION  = "simplification"
    EXPERIMENTAL    = "experimental"


@dataclass(frozen=True)
class LineageNode:
    """Immutable ancestry node for a governed mutation.

    Attributes
    ----------
    node_id         SHA-256 derived unique ID.
    patch_hash      ASTDiffPatch.patch_hash this node represents.
    capability_id   Owning CapabilityNode.capability_id (optional).
    niche           Mutation niche this candidate belongs to.
    parent_id       Parent LineageNode.node_id (None = root).
    generation      0-based depth from root.
    epoch_outcomes  Ordered list of EpochOutcome per epoch this was active.
    fitness_scores  Parallel list of composite fitness scores per epoch.
    in_cooling      True if LINEAGE-STAB-0 triggered 1-epoch suspension.
    created_at      ISO-8601 creation timestamp.
    metadata        Arbitrary enrichment.
    node_hash       SHA-256 of canonical state (excluding metadata).
    """

    node_id: str
    patch_hash: str
    capability_id: Optional[str]
    niche: MutationNiche
    parent_id: Optional[str]
    generation: int
    epoch_outcomes: tuple           # tuple[EpochOutcome, ...]
    fitness_scores: tuple           # tuple[float, ...]
    in_cooling: bool
    created_at: str
    metadata: Dict[str, Any]
    node_hash: str

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        patch_hash: str,
        niche: MutationNiche,
        created_at: str,
        capability_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        generation: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "LineageNode":
        metadata = metadata or {}
        node_id = _derive_node_id(patch_hash, parent_id, generation)
        node_hash = _compute_node_hash(node_id, patch_hash, niche, parent_id, generation)
        return cls(
            node_id=node_id,
            patch_hash=patch_hash,
            capability_id=capability_id,
            niche=niche,
            parent_id=parent_id,
            generation=generation,
            epoch_outcomes=(),
            fitness_scores=(),
            in_cooling=False,
            created_at=created_at,
            metadata=metadata,
            node_hash=node_hash,
        )

    # ------------------------------------------------------------------
    # Outcome recording (returns new frozen node)
    # ------------------------------------------------------------------

    def record_outcome(
        self, outcome: EpochOutcome, fitness: float = 0.0
    ) -> "LineageNode":
        """Return a new node with *outcome* appended to epoch_outcomes."""
        new_outcomes = self.epoch_outcomes + (outcome,)
        new_fitness = self.fitness_scores + (_clamp(fitness),)
        cooling = _should_cool(new_outcomes)
        return LineageNode(
            node_id=self.node_id,
            patch_hash=self.patch_hash,
            capability_id=self.capability_id,
            niche=self.niche,
            parent_id=self.parent_id,
            generation=self.generation,
            epoch_outcomes=new_outcomes,
            fitness_scores=new_fitness,
            in_cooling=cooling,
            created_at=self.created_at,
            metadata=self.metadata,
            node_hash=self.node_hash,
        )

    # ------------------------------------------------------------------
    # LINEAGE-STAB-0 helpers
    # ------------------------------------------------------------------

    def survival_score(self) -> float:
        """Fraction of last-5 epochs that passed governance [0.0, 1.0].

        LINEAGE-STAB-0: score ≥ 0.40 (2/5) = stable.
        """
        window = list(self.epoch_outcomes[-5:])
        if not window:
            return 0.0
        passes = sum(1 for o in window if o == EpochOutcome.PASSED)
        return passes / len(window)

    def is_stable(self) -> bool:
        """True if survival_score ≥ 0.40 (LINEAGE-STAB-0)."""
        return self.survival_score() >= 0.40

    def epochs_evaluated(self) -> int:
        return len(self.epoch_outcomes)

    def last_outcome(self) -> Optional[EpochOutcome]:
        return self.epoch_outcomes[-1] if self.epoch_outcomes else None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "patch_hash": self.patch_hash,
            "capability_id": self.capability_id,
            "niche": self.niche.value,
            "parent_id": self.parent_id,
            "generation": self.generation,
            "epoch_outcomes": [o.value for o in self.epoch_outcomes],
            "fitness_scores": list(self.fitness_scores),
            "in_cooling": self.in_cooling,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "node_hash": self.node_hash,
            "survival_score": self.survival_score(),
            "is_stable": self.is_stable(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LineageNode":
        return cls(
            node_id=d["node_id"],
            patch_hash=d["patch_hash"],
            capability_id=d.get("capability_id"),
            niche=MutationNiche(d["niche"]),
            parent_id=d.get("parent_id"),
            generation=int(d.get("generation", 0)),
            epoch_outcomes=tuple(EpochOutcome(o) for o in d.get("epoch_outcomes", [])),
            fitness_scores=tuple(float(f) for f in d.get("fitness_scores", [])),
            in_cooling=bool(d.get("in_cooling", False)),
            created_at=d.get("created_at", ""),
            metadata=d.get("metadata", {}),
            node_hash=d.get("node_hash", ""),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _derive_node_id(patch_hash: str, parent_id: Optional[str], generation: int) -> str:
    state = json.dumps(
        {"patch_hash": patch_hash, "parent_id": parent_id, "generation": generation},
        sort_keys=True,
    )
    return hashlib.sha256(state.encode()).hexdigest()


def _compute_node_hash(
    node_id: str,
    patch_hash: str,
    niche: MutationNiche,
    parent_id: Optional[str],
    generation: int,
) -> str:
    state = json.dumps(
        {
            "node_id": node_id,
            "patch_hash": patch_hash,
            "niche": niche.value,
            "parent_id": parent_id,
            "generation": generation,
        },
        sort_keys=True,
    )
    return hashlib.sha256(state.encode()).hexdigest()


def _should_cool(outcomes: tuple) -> bool:
    """LINEAGE-STAB-0: if last 5 epochs have < 2 passes → cooling."""
    window = list(outcomes[-5:])
    if len(window) < 5:
        return False
    passes = sum(1 for o in window if o == EpochOutcome.PASSED)
    return passes < 2


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))
