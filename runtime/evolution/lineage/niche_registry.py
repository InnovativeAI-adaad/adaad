"""
runtime.evolution.lineage.niche_registry
=========================================
NicheRegistry — 5 independent mutation niches + cross-niche hybrid breeding.

Each niche maintains an independent pool of LineageNode candidates.
The top candidate from any two niches can be combined into a hybrid
candidate (cross-niche breeding), extending the evolutionary search space
beyond single-strategy optimisation.

5 niches: performance, architecture, safety, simplification, experimental
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from runtime.evolution.lineage.lineage_node import LineageNode, MutationNiche


@dataclass
class NichePool:
    """A single niche's candidate pool, sorted by survival_score desc."""
    niche: MutationNiche
    nodes: List[LineageNode] = field(default_factory=list)

    def add(self, node: LineageNode) -> None:
        if node.niche != self.niche:
            raise ValueError(
                f"Node niche {node.niche} != pool niche {self.niche}"
            )
        self.nodes.append(node)
        self.nodes.sort(key=lambda n: n.survival_score(), reverse=True)

    def top(self) -> Optional[LineageNode]:
        return self.nodes[0] if self.nodes else None

    def size(self) -> int:
        return len(self.nodes)

    def stable_nodes(self) -> List[LineageNode]:
        return [n for n in self.nodes if n.is_stable()]

    def cooling_nodes(self) -> List[LineageNode]:
        return [n for n in self.nodes if n.in_cooling]


@dataclass
class HybridCandidate:
    """Cross-niche hybrid: merges signals from two top-niche candidates.

    Attributes
    ----------
    parent_a_node_id    node_id of the first niche's top candidate.
    parent_b_node_id    node_id of the second niche's top candidate.
    niche_a             First parent's niche.
    niche_b             Second parent's niche.
    hybrid_patch_hash   Combined hash representing the hybrid identity.
    blended_fitness     Average of the two parents' latest fitness scores.
    hybrid_id           Deterministic SHA-256 of parent node IDs.
    """
    parent_a_node_id: str
    parent_b_node_id: str
    niche_a: MutationNiche
    niche_b: MutationNiche
    hybrid_patch_hash: str
    blended_fitness: float
    hybrid_id: str

    def to_dict(self) -> dict:
        return {
            "parent_a_node_id": self.parent_a_node_id,
            "parent_b_node_id": self.parent_b_node_id,
            "niche_a": self.niche_a.value,
            "niche_b": self.niche_b.value,
            "hybrid_patch_hash": self.hybrid_patch_hash,
            "blended_fitness": self.blended_fitness,
            "hybrid_id": self.hybrid_id,
        }


class NicheRegistry:
    """Manages 5 independent mutation niches and cross-niche breeding.

    Usage
    -----
    registry = NicheRegistry()
    registry.register(node)
    hybrid = registry.breed(MutationNiche.PERFORMANCE, MutationNiche.SAFETY)
    """

    ALL_NICHES = list(MutationNiche)

    def __init__(self) -> None:
        self._pools: Dict[MutationNiche, NichePool] = {
            niche: NichePool(niche=niche)
            for niche in self.ALL_NICHES
        }

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, node: LineageNode) -> None:
        """Add *node* to its niche pool."""
        self._pools[node.niche].add(node)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def pool(self, niche: MutationNiche) -> NichePool:
        return self._pools[niche]

    def top_candidate(self, niche: MutationNiche) -> Optional[LineageNode]:
        return self._pools[niche].top()

    def all_tops(self) -> Dict[MutationNiche, Optional[LineageNode]]:
        return {niche: pool.top() for niche, pool in self._pools.items()}

    def total_candidates(self) -> int:
        return sum(p.size() for p in self._pools.values())

    def stable_count(self) -> int:
        return sum(len(p.stable_nodes()) for p in self._pools.values())

    def cooling_count(self) -> int:
        return sum(len(p.cooling_nodes()) for p in self._pools.values())

    # ------------------------------------------------------------------
    # Cross-niche breeding
    # ------------------------------------------------------------------

    def breed(
        self,
        niche_a: MutationNiche,
        niche_b: MutationNiche,
    ) -> Optional[HybridCandidate]:
        """Combine top candidates from two niches into a HybridCandidate.

        Returns None if either niche has no top candidate.
        """
        if niche_a == niche_b:
            raise ValueError("Cannot breed within the same niche.")

        node_a = self._pools[niche_a].top()
        node_b = self._pools[niche_b].top()

        if node_a is None or node_b is None:
            return None

        # Blend fitness: average of last recorded score per parent
        fit_a = node_a.fitness_scores[-1] if node_a.fitness_scores else 0.0
        fit_b = node_b.fitness_scores[-1] if node_b.fitness_scores else 0.0
        blended = (fit_a + fit_b) / 2.0

        # Hybrid identity
        hybrid_id = _hybrid_id(node_a.node_id, node_b.node_id)
        hybrid_patch_hash = _hybrid_patch_hash(node_a.patch_hash, node_b.patch_hash)

        return HybridCandidate(
            parent_a_node_id=node_a.node_id,
            parent_b_node_id=node_b.node_id,
            niche_a=niche_a,
            niche_b=niche_b,
            hybrid_patch_hash=hybrid_patch_hash,
            blended_fitness=blended,
            hybrid_id=hybrid_id,
        )

    def all_possible_hybrids(self) -> List[HybridCandidate]:
        """Generate all C(5,2)=10 possible cross-niche hybrids."""
        niches = self.ALL_NICHES
        hybrids = []
        for i in range(len(niches)):
            for j in range(i + 1, len(niches)):
                h = self.breed(niches[i], niches[j])
                if h is not None:
                    hybrids.append(h)
        return hybrids

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def registry_hash(self) -> str:
        state = json.dumps(
            {
                niche.value: [n.node_hash for n in pool.nodes]
                for niche, pool in self._pools.items()
            },
            sort_keys=True,
        )
        return hashlib.sha256(state.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "pools": {
                niche.value: {
                    "size": pool.size(),
                    "stable": len(pool.stable_nodes()),
                    "cooling": len(pool.cooling_nodes()),
                    "top": pool.top().to_dict() if pool.top() else None,
                }
                for niche, pool in self._pools.items()
            },
            "total_candidates": self.total_candidates(),
            "stable_count": self.stable_count(),
            "registry_hash": self.registry_hash(),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hybrid_id(node_a_id: str, node_b_id: str) -> str:
    a, b = sorted([node_a_id, node_b_id])
    return hashlib.sha256(f"{a}:{b}".encode()).hexdigest()


def _hybrid_patch_hash(hash_a: str, hash_b: str) -> str:
    a, b = sorted([hash_a, hash_b])
    return hashlib.sha256(f"hybrid:{a}:{b}".encode()).hexdigest()
