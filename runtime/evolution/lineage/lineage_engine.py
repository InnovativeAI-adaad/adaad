"""
runtime.evolution.lineage.lineage_engine
==========================================
LineageEngine — the central Phase 61 coordinator.

Integrates:
  LineageNode       immutable ancestry nodes
  CompatibilityMatrix  epistasis detection (EPISTASIS-0)
  NicheRegistry     5 independent niches + cross-niche breeding

Responsibilities
----------------
1. Register new ASTDiffPatch candidates as LineageNodes.
2. Record epoch outcomes → trigger LINEAGE-STAB-0 cooling when needed.
3. Detect epistasis when two mutations co-occur with joint regression.
4. Provide the lineage chain for any node (root → leaf).
5. Generate epoch summary for operator dashboards.

Invariants
----------
LINEAGE-STAB-0  lineage stable iff ≥ 2/5 last epochs passed; else 1-epoch cool.
EPISTASIS-0     epistatic pairs cooled EPISTASIS_COOLING_EPOCHS epochs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from runtime.evolution.lineage.lineage_node import (
    LineageNode, EpochOutcome, MutationNiche,
)
from runtime.evolution.lineage.compatibility_matrix import (
    CompatibilityMatrix, CoOccurrenceRecord,
)
from runtime.evolution.lineage.niche_registry import NicheRegistry, HybridCandidate


# ---------------------------------------------------------------------------
# Epoch summary
# ---------------------------------------------------------------------------

@dataclass
class EpochLineageSummary:
    """Snapshot of lineage health at the end of an epoch.

    Attributes
    ----------
    epoch_id                Epoch identifier.
    nodes_registered        Total nodes registered this epoch.
    nodes_evaluated         Nodes that received an outcome this epoch.
    stable_count            Nodes meeting LINEAGE-STAB-0 threshold.
    cooling_count           Nodes in 1-epoch cooling suspension.
    epistasis_pairs         Currently active epistatic pairs.
    hybrid_candidates       Cross-niche hybrids generated this epoch.
    engine_hash             Deterministic snapshot hash.
    """
    epoch_id: str
    nodes_registered: int
    nodes_evaluated: int
    stable_count: int
    cooling_count: int
    epistasis_pairs: int
    hybrid_candidates: int
    engine_hash: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class LineageEngine:
    """Central Phase 61 lineage coordinator.

    Usage
    -----
    engine = LineageEngine()

    # Register a new patch candidate
    node = engine.register(
        patch_hash="abc123...",
        niche=MutationNiche.PERFORMANCE,
        created_at="2026-03-13T00:00:00Z",
        capability_id="evolution.loop",
        parent_id=None,
    )

    # Record epoch outcome
    engine.record_outcome(node.node_id, EpochOutcome.PASSED, fitness=0.82)

    # Detect epistasis between co-submitted pair
    engine.record_co_occurrence("hash_a", "hash_b", epoch_id="E01",
                                a_alone=True, b_alone=True, joint=False)
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, LineageNode] = {}       # node_id → LineageNode
        self._patch_to_node: Dict[str, str] = {}       # patch_hash → node_id
        self._compat = CompatibilityMatrix()
        self._niches = NicheRegistry()
        self._epoch_new_nodes: List[str] = []          # node_ids registered this epoch
        self._epoch_evaluated: List[str] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        patch_hash: str,
        niche: MutationNiche,
        created_at: str,
        capability_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LineageNode:
        """Create and register a new LineageNode for *patch_hash*."""
        # Derive generation from parent
        generation = 0
        if parent_id and parent_id in self._nodes:
            generation = self._nodes[parent_id].generation + 1

        node = LineageNode.create(
            patch_hash=patch_hash,
            niche=niche,
            created_at=created_at,
            capability_id=capability_id,
            parent_id=parent_id,
            generation=generation,
            metadata=metadata,
        )
        self._nodes[node.node_id] = node
        self._patch_to_node[patch_hash] = node.node_id
        self._niches.register(node)
        self._epoch_new_nodes.append(node.node_id)
        return node

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        node_id: str,
        outcome: EpochOutcome,
        fitness: float = 0.0,
    ) -> LineageNode:
        """Append *outcome* to node; apply LINEAGE-STAB-0 if needed."""
        if node_id not in self._nodes:
            raise KeyError(f"LineageNode {node_id!r} not found.")

        node = self._nodes[node_id]
        updated = node.record_outcome(outcome, fitness)
        self._nodes[node_id] = updated

        # Re-register in niche pool with updated scores
        self._niches.pool(updated.niche).nodes = [
            (updated if n.node_id == node_id else n)
            for n in self._niches.pool(updated.niche).nodes
        ]
        self._niches.pool(updated.niche).nodes.sort(
            key=lambda n: n.survival_score(), reverse=True
        )
        self._epoch_evaluated.append(node_id)
        return updated

    # ------------------------------------------------------------------
    # Epistasis / co-occurrence
    # ------------------------------------------------------------------

    def record_co_occurrence(
        self,
        patch_a: str,
        patch_b: str,
        epoch_id: str,
        a_passed_alone: bool,
        b_passed_alone: bool,
        joint_passed: bool,
    ) -> CoOccurrenceRecord:
        """Record mutation co-occurrence; detect epistasis (EPISTASIS-0)."""
        return self._compat.record(
            patch_a, patch_b, epoch_id,
            a_passed_alone, b_passed_alone, joint_passed,
        )

    def is_epistatic_pair(self, patch_a: str, patch_b: str) -> bool:
        return self._compat.is_epistatic_pair(patch_a, patch_b)

    # ------------------------------------------------------------------
    # Lineage chain
    # ------------------------------------------------------------------

    def lineage_chain(self, node_id: str) -> List[LineageNode]:
        """Return ancestor chain from root to *node_id* (inclusive)."""
        chain = []
        current_id: Optional[str] = node_id
        seen: set = set()
        while current_id:
            if current_id in seen:
                break
            seen.add(current_id)
            node = self._nodes.get(current_id)
            if node is None:
                break
            chain.append(node)
            current_id = node.parent_id
        chain.reverse()
        return chain

    def lineage_depth(self, node_id: str) -> int:
        return len(self.lineage_chain(node_id))

    # ------------------------------------------------------------------
    # Niches
    # ------------------------------------------------------------------

    def breed(
        self, niche_a: MutationNiche, niche_b: MutationNiche
    ) -> Optional[HybridCandidate]:
        return self._niches.breed(niche_a, niche_b)

    def all_hybrids(self) -> List[HybridCandidate]:
        return self._niches.all_possible_hybrids()

    # ------------------------------------------------------------------
    # Epoch lifecycle
    # ------------------------------------------------------------------

    def end_epoch(self, epoch_id: str) -> EpochLineageSummary:
        """Advance epoch counters; return health summary."""
        self._compat.advance_epoch()

        summary = EpochLineageSummary(
            epoch_id=epoch_id,
            nodes_registered=len(self._epoch_new_nodes),
            nodes_evaluated=len(set(self._epoch_evaluated)),
            stable_count=self._niches.stable_count(),
            cooling_count=self._niches.cooling_count(),
            epistasis_pairs=len(self._compat.epistatic_pairs()),
            hybrid_candidates=len(self.all_hybrids()),
            engine_hash=self.engine_hash(),
        )
        self._epoch_new_nodes.clear()
        self._epoch_evaluated.clear()
        return summary

    # ------------------------------------------------------------------
    # Integrity / serialisation
    # ------------------------------------------------------------------

    def node(self, node_id: str) -> Optional[LineageNode]:
        return self._nodes.get(node_id)

    def node_by_patch(self, patch_hash: str) -> Optional[LineageNode]:
        nid = self._patch_to_node.get(patch_hash)
        return self._nodes.get(nid) if nid else None

    def total_nodes(self) -> int:
        return len(self._nodes)

    def engine_hash(self) -> str:
        state = json.dumps(
            {
                "nodes": sorted(self._nodes.keys()),
                "matrix": self._compat.matrix_hash(),
                "niches": self._niches.registry_hash(),
            },
            sort_keys=True,
        )
        return hashlib.sha256(state.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "total_nodes": self.total_nodes(),
            "niches": self._niches.to_dict(),
            "compat": self._compat.to_dict(),
            "engine_hash": self.engine_hash(),
        }
