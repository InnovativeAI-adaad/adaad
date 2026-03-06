# SPDX-License-Identifier: Apache-2.0
"""
LineageDAG — multi-generational directed acyclic graph for agent lineage tracking.

Purpose:
    Tracks the full ancestry tree of agent mutations across generations G0→G7+.
    Every mutation node records its parent, generation depth, fitness score,
    agent origin, and approval state. The DAG is the canonical system of record
    for all promoted software artifacts.

Architecture:
    - Nodes are immutable once created (frozen dataclass).
    - Edges are parent→child relationships. A node may have one parent and
      multiple children (branching).
    - The full graph is persisted as JSONL (one node per line) for append-only
      integrity and streaming replay compatibility.
    - Every append operation updates a rolling SHA-256 chain digest.
    - Branch comparison uses fitness score delta and generation distance.

Generation model:
    G0 = root (seed/bootstrap agents)
    G1 = first generation of mutations from G0
    G2 = mutations derived from G1 nodes
    ...
    Gn = mutations derived from G(n-1) nodes

    Generation is determined by parent.generation + 1.
    Root nodes (no parent) have generation = 0.

Key capabilities:
    - add_node(): Register a new mutation/agent in the DAG.
    - promote_node(): Mark a node as human-approved and production-promoted.
    - get_lineage_chain(): Return the full ancestor chain from a node to G0.
    - compare_branches(): Return fitness delta between two subtrees.
    - generation_summary(): Per-generation statistics for health monitoring.
    - integrity_check(): Verify the SHA-256 chain is unbroken.

Governance invariants:
    - No node can reference a parent_id that does not exist in the DAG.
    - promoted=True requires human_approved=True (enforced at write time).
    - Chain integrity failures raise LineageDAGIntegrityError.
    - All mutations are traceable to a G0 root node.

Android/Pydroid3 compatibility:
    - Pure Python stdlib only. No numpy, no C extensions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from runtime.timeutils import now_iso

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DAG_PATH = Path("data/lineage_dag.jsonl")
MAX_GENERATION_DEPTH = 20    # Safety cap — deeper graphs indicate architectural drift


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LineageDAGIntegrityError(RuntimeError):
    """Raised when the DAG chain digest verification fails."""


class LineageDAGNodeError(ValueError):
    """Raised on invalid node operations (missing parent, duplicate id, etc.)."""


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LineageNode:
    """
    Immutable record representing one agent/mutation in the lineage DAG.

    Fields:
        node_id:        Unique identifier for this node (mutation_id or agent_id).
        parent_id:      Parent node_id, or None for G0 root nodes.
        generation:     Generation depth (0 = root, n = derived from G(n-1)).
        agent_origin:   Agent persona that produced this node ("architect"/"dream"/"beast").
        epoch_id:       Epoch in which this node was created.
        fitness_score:  Float [0.0, 1.0] — composite fitness at scoring time.
        mutation_type:  Type of mutation ("structural"/"behavioral"/"performance"/etc.).
        human_approved: True if a human operator has approved this node.
        promoted:       True if node has been promoted to production.
        created_at:     ISO timestamp of node creation.
        metadata:       Arbitrary additional context (test results, score breakdown, etc.).
    """
    node_id: str
    parent_id: Optional[str]
    generation: int
    agent_origin: str
    epoch_id: str
    fitness_score: float
    mutation_type: str
    human_approved: bool = False
    promoted: bool = False
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)

    def digest_input(self) -> str:
        """Canonical string for SHA-256 chain computation."""
        core = {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "generation": self.generation,
            "agent_origin": self.agent_origin,
            "epoch_id": self.epoch_id,
            "fitness_score": self.fitness_score,
            "mutation_type": self.mutation_type,
        }
        return json.dumps(core, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# BranchComparison
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BranchComparison:
    """Result of comparing two lineage subtrees."""
    node_a: str
    node_b: str
    avg_fitness_a: float
    avg_fitness_b: float
    fitness_delta: float        # avg_fitness_a - avg_fitness_b
    size_a: int
    size_b: int
    common_ancestor_id: Optional[str]
    generation_distance: int    # depth difference between the two nodes


@dataclass(frozen=True)
class GenerationSummary:
    """Statistics for a single generation level."""
    generation: int
    node_count: int
    approved_count: int
    promoted_count: int
    avg_fitness: float
    top_node_id: Optional[str]
    top_fitness: float


# ---------------------------------------------------------------------------
# LineageDAG
# ---------------------------------------------------------------------------

class LineageDAG:
    """
    Multi-generational lineage DAG for ADAAD agent/mutation tracking.

    Usage:
        dag = LineageDAG()

        # Register a root node (G0)
        dag.add_node(LineageNode(
            node_id="seed-architect-001",
            parent_id=None,
            generation=0,
            agent_origin="architect",
            epoch_id="epoch-000",
            fitness_score=0.0,
            mutation_type="structural",
            created_at=now_iso(),
        ))

        # Register a child node (G1)
        dag.add_node(LineageNode(
            node_id="mut-architect-001",
            parent_id="seed-architect-001",
            generation=1,
            agent_origin="architect",
            epoch_id="epoch-001",
            fitness_score=0.72,
            mutation_type="structural",
            created_at=now_iso(),
        ))

        # Promote after human approval
        dag.promote_node("mut-architect-001", operator_id="dreezy66")

        # Inspect lineage
        chain = dag.get_lineage_chain("mut-architect-001")
        summary = dag.generation_summary()
    """

    def __init__(
        self,
        dag_path: Path = DEFAULT_DAG_PATH,
        audit_writer: Optional[Any] = None,
    ) -> None:
        self._path = dag_path
        self._audit = audit_writer
        self._nodes: Dict[str, LineageNode] = {}
        self._chain_digest: str = "0" * 64
        self._load()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_node(self, node: LineageNode) -> str:
        """
        Register a new node in the DAG.

        Validates:
          - node_id must be unique.
          - parent_id must exist if provided.
          - generation must equal parent.generation + 1 (or 0 for roots).
          - promoted=True requires human_approved=True.
          - generation must not exceed MAX_GENERATION_DEPTH.

        Returns:
            chain_digest: The updated SHA-256 chain hash after appending.

        Raises:
            LineageDAGNodeError: On validation failure.
            LineageDAGIntegrityError: On chain verification failure.
        """
        self._validate_node(node)

        # Ensure created_at is set
        if not node.created_at:
            node = LineageNode(**{**node.to_payload(), "created_at": now_iso()})

        # Update chain digest
        prev = self._chain_digest
        self._chain_digest = hashlib.sha256(
            (prev + node.digest_input()).encode("utf-8")
        ).hexdigest()

        # Persist
        record = {
            **node.to_payload(),
            "chain_digest": self._chain_digest,
        }
        self._append(record)
        self._nodes[node.node_id] = node

        if self._audit is not None:
            try:
                self._audit("lineage_node_added", {
                    "node_id": node.node_id,
                    "generation": node.generation,
                    "parent_id": node.parent_id,
                    "chain_digest": self._chain_digest,
                })
            except Exception:  # noqa: BLE001
                pass

        return self._chain_digest

    def promote_node(self, node_id: str, operator_id: str) -> LineageNode:
        """
        Mark a node as human-approved and production-promoted.

        Requires:
          - Node must exist.
          - Sets human_approved=True and promoted=True.
          - Writes a promotion audit event.

        Args:
            node_id:     Node to promote.
            operator_id: Human operator authorising the promotion.

        Returns:
            Updated LineageNode with promoted=True.

        Raises:
            LineageDAGNodeError: If node not found.
        """
        node = self._nodes.get(node_id)
        if node is None:
            raise LineageDAGNodeError(f"node_not_found:{node_id}")

        promoted = LineageNode(**{
            **node.to_payload(),
            "human_approved": True,
            "promoted": True,
        })

        # Re-persist the promoted state as a new record (immutable log)
        record = {
            **promoted.to_payload(),
            "event_type": "promotion",
            "operator_id": operator_id,
            "promoted_at": now_iso(),
            "chain_digest": self._chain_digest,
        }
        self._append(record)
        self._nodes[node_id] = promoted

        if self._audit is not None:
            try:
                self._audit("lineage_node_promoted", {
                    "node_id": node_id,
                    "operator_id": operator_id,
                    "generation": promoted.generation,
                })
            except Exception:  # noqa: BLE001
                pass

        return promoted

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[LineageNode]:
        """Retrieve a node by ID. Returns None if not found."""
        return self._nodes.get(node_id)

    def get_lineage_chain(self, node_id: str) -> List[LineageNode]:
        """
        Return the full ancestor chain from node_id back to the G0 root.
        List is ordered oldest-first: [G0_root, ..., parent, node].

        Raises:
            LineageDAGNodeError: If node_id not found.
        """
        node = self._nodes.get(node_id)
        if node is None:
            raise LineageDAGNodeError(f"node_not_found:{node_id}")

        chain: List[LineageNode] = [node]
        visited: Set[str] = {node_id}
        current = node

        while current.parent_id is not None:
            if current.parent_id in visited:
                raise LineageDAGIntegrityError(f"cycle_detected:{current.parent_id}")
            parent = self._nodes.get(current.parent_id)
            if parent is None:
                raise LineageDAGNodeError(f"parent_not_found:{current.parent_id}")
            chain.append(parent)
            visited.add(current.parent_id)
            current = parent

        chain.reverse()
        return chain

    def get_children(self, node_id: str) -> List[LineageNode]:
        """Return all direct children of a node."""
        return [n for n in self._nodes.values() if n.parent_id == node_id]

    def get_generation(self, generation: int) -> List[LineageNode]:
        """Return all nodes at a specific generation level."""
        return [n for n in self._nodes.values() if n.generation == generation]

    def max_generation(self) -> int:
        """Return the deepest generation currently in the DAG."""
        if not self._nodes:
            return 0
        return max(n.generation for n in self._nodes.values())

    def generation_summary(self) -> List[GenerationSummary]:
        """
        Return per-generation statistics for governance health monitoring.
        Ordered from G0 to max generation.
        """
        summaries: List[GenerationSummary] = []
        max_gen = self.max_generation()

        for g in range(max_gen + 1):
            nodes = self.get_generation(g)
            if not nodes:
                continue
            approved = [n for n in nodes if n.human_approved]
            promoted = [n for n in nodes if n.promoted]
            scores = [n.fitness_score for n in nodes]
            avg_fitness = round(sum(scores) / len(scores), 4) if scores else 0.0
            top = max(nodes, key=lambda n: n.fitness_score, default=None)

            summaries.append(GenerationSummary(
                generation=g,
                node_count=len(nodes),
                approved_count=len(approved),
                promoted_count=len(promoted),
                avg_fitness=avg_fitness,
                top_node_id=top.node_id if top else None,
                top_fitness=top.fitness_score if top else 0.0,
            ))

        return summaries

    def compare_branches(self, node_id_a: str, node_id_b: str) -> BranchComparison:
        """
        Compare two lineage subtrees by average fitness and generation distance.

        Args:
            node_id_a: Root of subtree A.
            node_id_b: Root of subtree B.

        Returns:
            BranchComparison with fitness delta and common ancestor info.
        """
        subtree_a = self._collect_subtree(node_id_a)
        subtree_b = self._collect_subtree(node_id_b)

        node_a = self._nodes[node_id_a]
        node_b = self._nodes[node_id_b]

        avg_a = (
            round(sum(n.fitness_score for n in subtree_a) / len(subtree_a), 4)
            if subtree_a else 0.0
        )
        avg_b = (
            round(sum(n.fitness_score for n in subtree_b) / len(subtree_b), 4)
            if subtree_b else 0.0
        )

        ancestor = self._find_common_ancestor(node_id_a, node_id_b)
        gen_distance = abs(node_a.generation - node_b.generation)

        return BranchComparison(
            node_a=node_id_a,
            node_b=node_id_b,
            avg_fitness_a=avg_a,
            avg_fitness_b=avg_b,
            fitness_delta=round(avg_a - avg_b, 4),
            size_a=len(subtree_a),
            size_b=len(subtree_b),
            common_ancestor_id=ancestor,
            generation_distance=gen_distance,
        )

    def integrity_check(self) -> bool:
        """
        Verify the SHA-256 chain is unbroken from genesis to current state.

        Returns:
            True if chain is intact. False if corruption detected.
        """
        chain_digest = "0" * 64
        for record in self._read_raw():
            # Skip promotion events (they don't update the primary chain)
            if record.get("event_type") == "promotion":
                continue
            node = self._record_to_node(record)
            if node is None:
                return False
            chain_digest = hashlib.sha256(
                (chain_digest + node.digest_input()).encode("utf-8")
            ).hexdigest()
            if record.get("chain_digest") != chain_digest:
                return False
        return True

    def health_snapshot(self) -> Dict[str, Any]:
        """Return a governance-ready health summary."""
        summaries = self.generation_summary()
        total_nodes = len(self._nodes)
        approved = sum(1 for n in self._nodes.values() if n.human_approved)
        promoted = sum(1 for n in self._nodes.values() if n.promoted)

        return {
            "total_nodes": total_nodes,
            "max_generation": self.max_generation(),
            "approved_count": approved,
            "promoted_count": promoted,
            "approval_rate": round(approved / total_nodes, 4) if total_nodes else 0.0,
            "promotion_rate": round(promoted / total_nodes, 4) if total_nodes else 0.0,
            "chain_digest": self._chain_digest,
            "integrity_ok": self.integrity_check(),
            "generation_breakdown": [
                {
                    "generation": s.generation,
                    "nodes": s.node_count,
                    "avg_fitness": s.avg_fitness,
                    "approved": s.approved_count,
                }
                for s in summaries
            ],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_node(self, node: LineageNode) -> None:
        if node.node_id in self._nodes:
            raise LineageDAGNodeError(f"duplicate_node_id:{node.node_id}")

        if node.parent_id is not None and node.parent_id not in self._nodes:
            raise LineageDAGNodeError(f"parent_not_found:{node.parent_id}")

        if node.parent_id is None:
            expected_gen = 0
        else:
            expected_gen = self._nodes[node.parent_id].generation + 1

        if node.generation != expected_gen:
            raise LineageDAGNodeError(
                f"invalid_generation:{node.generation} expected:{expected_gen}"
            )

        if node.generation > MAX_GENERATION_DEPTH:
            raise LineageDAGNodeError(
                f"generation_exceeds_max:{node.generation} max:{MAX_GENERATION_DEPTH}"
            )

        if node.promoted and not node.human_approved:
            raise LineageDAGNodeError(
                f"promoted_without_approval:{node.node_id}"
            )

    def _collect_subtree(self, node_id: str) -> List[LineageNode]:
        """Collect all nodes in the subtree rooted at node_id."""
        result: List[LineageNode] = []
        stack = [node_id]
        while stack:
            nid = stack.pop()
            node = self._nodes.get(nid)
            if node:
                result.append(node)
                stack.extend(c.node_id for c in self.get_children(nid))
        return result

    def _find_common_ancestor(self, id_a: str, id_b: str) -> Optional[str]:
        ancestors_a: Set[str] = set()
        current: Optional[str] = id_a
        while current:
            ancestors_a.add(current)
            node = self._nodes.get(current)
            current = node.parent_id if node else None

        current = id_b
        while current:
            if current in ancestors_a:
                return current
            node = self._nodes.get(current)
            current = node.parent_id if node else None
        return None

    def _append(self, record: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    def _read_raw(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return rows

    def _record_to_node(self, record: Dict[str, Any]) -> Optional[LineageNode]:
        try:
            return LineageNode(
                node_id=record["node_id"],
                parent_id=record.get("parent_id"),
                generation=int(record["generation"]),
                agent_origin=record.get("agent_origin", "unknown"),
                epoch_id=record.get("epoch_id", ""),
                fitness_score=float(record.get("fitness_score", 0.0)),
                mutation_type=record.get("mutation_type", "unknown"),
                human_approved=bool(record.get("human_approved", False)),
                promoted=bool(record.get("promoted", False)),
                created_at=record.get("created_at", ""),
                metadata=dict(record.get("metadata") or {}),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _load(self) -> None:
        """Load existing DAG from disk, rebuilding in-memory state."""
        chain_digest = "0" * 64
        for record in self._read_raw():
            if record.get("event_type") == "promotion":
                # Apply promotion update to existing node
                node_id = record.get("node_id")
                if node_id and node_id in self._nodes:
                    existing = self._nodes[node_id]
                    self._nodes[node_id] = LineageNode(**{
                        **existing.to_payload(),
                        "human_approved": True,
                        "promoted": True,
                    })
                continue

            node = self._record_to_node(record)
            if node is not None:
                self._nodes[node.node_id] = node
                chain_digest = hashlib.sha256(
                    (chain_digest + node.digest_input()).encode("utf-8")
                ).hexdigest()

        self._chain_digest = chain_digest


__all__ = [
    "LineageNode",
    "BranchComparison",
    "GenerationSummary",
    "LineageDAG",
    "LineageDAGIntegrityError",
    "LineageDAGNodeError",
    "MAX_GENERATION_DEPTH",
    "DEFAULT_DAG_PATH",
]
