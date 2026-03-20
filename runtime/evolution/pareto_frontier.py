# SPDX-License-Identifier: Apache-2.0
"""Phase 82 — ParetoFrontier.

Multi-objective Pareto dominance computation for ADAAD population evolution.

Replaces scalar fitness collapse with a Pareto-optimal frontier: a candidate
A dominates B when A is at least as good on ALL objectives and strictly
better on at least one. Non-dominated candidates form the frontier and are
eligible for promotion (one per niche, via GovernanceGate).

Constitutional Invariants
─────────────────────────
  PARETO-0       Scalar fitness remains available as an advisory signal but
                 never alone drives promotion when Pareto evaluation is active.
  PARETO-DET-0   Given identical candidate sets and objective scores, frontier
                 computation is deterministic and produces identical results.
  PARETO-NONDEG-0 When all candidates are mutually non-dominated (no dominance
                  relationships exist), ALL candidates are frontier members.
                  The frontier is never empty given a non-empty input.
  PARETO-GOV-0   GovernanceGate evaluates each frontier candidate independently.
                 Pareto frontier membership never bypasses gate evaluation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PARETO_VERSION: str = "82.0"

# The 5 Pareto objectives drawn from FitnessEngineV2 signal keys + MutationCandidate fields.
# Each objective is maximised (higher = better).
PARETO_OBJECTIVES: Tuple[str, ...] = (
    "correctness",       # maps to test_fitness / correctness_score
    "efficiency",        # maps to performance_fitness / efficiency_score
    "governance",        # maps to governance_compliance / policy_compliance_score
    "maintainability",   # maps to complexity_fitness (inverted: lower complexity = higher maintainability)
    "coverage_delta",    # maps to MutationCandidate.coverage_delta
)

# Default tolerance for "at-least-as-good" comparison (floating-point safety margin)
DOMINANCE_EPSILON: float = 1e-9


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParetoObjectiveVector:
    """Multi-dimensional objective score for one candidate.

    All objectives are normalised to [0.0, 1.0] where higher = better.

    Attributes
    ----------
    candidate_id:   Unique identifier for the candidate.
    objectives:     Mapping objective_name → float score in [0.0, 1.0].
    scalar_score:   Advisory scalar (e.g. FitnessOrchestrator composite). PARETO-0.
    vector_digest:  SHA-256 of canonical objective vector (determinism anchor).
    """

    candidate_id: str
    objectives: Dict[str, float]
    scalar_score: float = 0.0
    vector_digest: str = ""

    def __post_init__(self) -> None:
        # Compute digest if not provided
        if not self.vector_digest:
            object.__setattr__(self, "vector_digest", _vector_digest(self.candidate_id, self.objectives))

    def get(self, objective: str, default: float = 0.0) -> float:
        return self.objectives.get(objective, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "objectives": dict(self.objectives),
            "scalar_score": self.scalar_score,
            "vector_digest": self.vector_digest,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ParetoObjectiveVector":
        return cls(
            candidate_id=d["candidate_id"],
            objectives=d["objectives"],
            scalar_score=d.get("scalar_score", 0.0),
            vector_digest=d.get("vector_digest", ""),
        )


@dataclass(frozen=True)
class ParetoFrontierResult:
    """Result of one Pareto frontier computation.

    Attributes
    ----------
    frontier_ids:       Sorted candidate_ids of non-dominated candidates.
    dominated_ids:      Sorted candidate_ids of dominated candidates.
    dominance_pairs:    Set of (dominator_id, dominated_id) tuples.
    frontier_digest:    SHA-256 of canonical frontier (PARETO-DET-0 anchor).
    objective_names:    Objectives evaluated.
    schema_version:     Phase version tag.
    """

    frontier_ids: Tuple[str, ...]
    dominated_ids: Tuple[str, ...]
    dominance_pairs: FrozenSet[Tuple[str, str]]
    frontier_digest: str
    objective_names: Tuple[str, ...]
    schema_version: str = PARETO_VERSION

    @property
    def frontier_size(self) -> int:
        return len(self.frontier_ids)

    @property
    def dominated_size(self) -> int:
        return len(self.dominated_ids)

    def is_frontier_member(self, candidate_id: str) -> bool:
        return candidate_id in self.frontier_ids

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frontier_ids": list(self.frontier_ids),
            "dominated_ids": list(self.dominated_ids),
            "dominance_pairs": [list(p) for p in sorted(self.dominance_pairs)],
            "frontier_digest": self.frontier_digest,
            "objective_names": list(self.objective_names),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ParetoFrontierResult":
        return cls(
            frontier_ids=tuple(d["frontier_ids"]),
            dominated_ids=tuple(d["dominated_ids"]),
            dominance_pairs=frozenset(tuple(p) for p in d["dominance_pairs"]),
            frontier_digest=d["frontier_digest"],
            objective_names=tuple(d["objective_names"]),
            schema_version=d.get("schema_version", PARETO_VERSION),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vector_digest(candidate_id: str, objectives: Dict[str, float]) -> str:
    payload = json.dumps(
        {"candidate_id": candidate_id, "objectives": {k: objectives[k] for k in sorted(objectives)}},
        sort_keys=True, separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _frontier_digest(frontier_ids: Sequence[str], objective_names: Sequence[str]) -> str:
    payload = json.dumps(
        {"frontier_ids": sorted(frontier_ids), "objectives": sorted(objective_names)},
        sort_keys=True, separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _dominates(
    a: ParetoObjectiveVector,
    b: ParetoObjectiveVector,
    objectives: Sequence[str],
    epsilon: float = DOMINANCE_EPSILON,
) -> bool:
    """Return True if A Pareto-dominates B.

    A dominates B iff:
      - A is at least as good as B on ALL objectives (within epsilon)
      - A is strictly better than B on AT LEAST ONE objective

    PARETO-DET-0: pure function, deterministic for identical inputs.
    """
    at_least_as_good_all = all(
        a.get(obj) >= b.get(obj) - epsilon for obj in objectives
    )
    strictly_better_one = any(
        a.get(obj) > b.get(obj) + epsilon for obj in objectives
    )
    return at_least_as_good_all and strictly_better_one


# ---------------------------------------------------------------------------
# ParetoFrontier
# ---------------------------------------------------------------------------


class ParetoFrontier:
    """Phase 82 multi-objective Pareto frontier computer.

    Computes the non-dominated frontier from a population of
    ParetoObjectiveVector objects.

    Invariants enforced:
      PARETO-DET-0    Deterministic: identical inputs → identical frontier.
      PARETO-NONDEG-0 Non-empty input → non-empty frontier.
      PARETO-0        Scalar score preserved as advisory; never used for dominance.

    Algorithm: O(n²) naive dominance check — sufficient for population sizes
    up to MAX_POPULATION (12, from PopulationManager). For larger populations
    a divide-and-conquer extension should be applied.
    """

    def __init__(
        self,
        objectives: Sequence[str] = PARETO_OBJECTIVES,
        epsilon: float = DOMINANCE_EPSILON,
    ) -> None:
        self._objectives = tuple(objectives)
        self._epsilon = epsilon

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def compute(
        self, vectors: Sequence[ParetoObjectiveVector]
    ) -> ParetoFrontierResult:
        """Compute the Pareto frontier from a population of objective vectors.

        Parameters
        ----------
        vectors : Sequence of ParetoObjectiveVector (one per candidate).

        Returns
        -------
        ParetoFrontierResult with frontier_ids, dominated_ids, dominance_pairs.

        PARETO-NONDEG-0: if vectors is non-empty, frontier_ids is non-empty.
        PARETO-DET-0: deterministic for identical inputs.
        """
        if not vectors:
            return ParetoFrontierResult(
                frontier_ids=(),
                dominated_ids=(),
                dominance_pairs=frozenset(),
                frontier_digest=_frontier_digest([], self._objectives),
                objective_names=self._objectives,
            )

        # Sort by candidate_id for determinism (PARETO-DET-0)
        sorted_vecs = sorted(vectors, key=lambda v: v.candidate_id)
        n = len(sorted_vecs)

        dominated: set[str] = set()
        pairs: set[Tuple[str, str]] = set()

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if _dominates(sorted_vecs[i], sorted_vecs[j], self._objectives, self._epsilon):
                    dominated.add(sorted_vecs[j].candidate_id)
                    pairs.add((sorted_vecs[i].candidate_id, sorted_vecs[j].candidate_id))

        frontier_ids = tuple(
            sorted(v.candidate_id for v in sorted_vecs if v.candidate_id not in dominated)
        )
        dominated_ids = tuple(sorted(dominated))

        # PARETO-NONDEG-0: frontier must be non-empty for non-empty input
        assert len(frontier_ids) > 0, "PARETO-NONDEG-0 violated: frontier is empty"

        result = ParetoFrontierResult(
            frontier_ids=frontier_ids,
            dominated_ids=dominated_ids,
            dominance_pairs=frozenset(pairs),
            frontier_digest=_frontier_digest(frontier_ids, self._objectives),
            objective_names=self._objectives,
        )
        log.info(
            "PARETO: frontier size=%d dominated=%d total=%d",
            result.frontier_size, result.dominated_size, n,
        )
        return result

    def rank_frontier(
        self,
        frontier_result: ParetoFrontierResult,
        vectors: Sequence[ParetoObjectiveVector],
    ) -> List[Tuple[str, float]]:
        """Rank frontier members by advisory scalar score for tie-breaking.

        PARETO-0: scalar score is advisory only — used for ranking within the
        frontier, never for dominance computation.

        Returns list of (candidate_id, scalar_score) sorted descending by
        scalar_score. Ties broken by candidate_id ascending (determinism).
        """
        vec_map = {v.candidate_id: v for v in vectors}
        frontier_vecs = [
            vec_map[cid] for cid in frontier_result.frontier_ids if cid in vec_map
        ]
        ranked = sorted(
            [(v.candidate_id, v.scalar_score) for v in frontier_vecs],
            key=lambda t: (-t[1], t[0]),
        )
        return ranked

    def objectives(self) -> Tuple[str, ...]:
        return self._objectives


# ---------------------------------------------------------------------------
# Objective vector builder helpers
# ---------------------------------------------------------------------------


def build_objective_vector(
    candidate_id: str,
    *,
    correctness: float = 0.5,
    efficiency: float = 0.5,
    governance: float = 0.5,
    maintainability: float = 0.5,
    coverage_delta: float = 0.5,
    scalar_score: float = 0.0,
) -> ParetoObjectiveVector:
    """Convenience constructor for building ParetoObjectiveVector from named scores."""
    objectives = {
        "correctness": max(0.0, min(1.0, correctness)),
        "efficiency": max(0.0, min(1.0, efficiency)),
        "governance": max(0.0, min(1.0, governance)),
        "maintainability": max(0.0, min(1.0, maintainability)),
        "coverage_delta": max(0.0, min(1.0, coverage_delta)),
    }
    return ParetoObjectiveVector(
        candidate_id=candidate_id,
        objectives=objectives,
        scalar_score=scalar_score,
    )


def build_objective_vector_from_fitness_context(
    candidate_id: str,
    fitness_context: Dict[str, Any],
    *,
    scalar_score: float = 0.0,
) -> ParetoObjectiveVector:
    """Build a ParetoObjectiveVector from a standard FitnessOrchestrator context dict.

    Maps standard context keys to Pareto objectives.
    """
    def _get(key: str) -> float:
        return max(0.0, min(1.0, float(fitness_context.get(key) or 0.5)))

    # maintainability = 1 - complexity proxy (lower complexity = higher maintainability)
    complexity_raw = _get("efficiency_score")  # used as proxy when no explicit complexity
    maintainability = 1.0 - max(0.0, min(1.0, float(fitness_context.get("complexity_score") or (1.0 - complexity_raw))))

    return build_objective_vector(
        candidate_id=candidate_id,
        correctness=_get("correctness_score"),
        efficiency=_get("efficiency_score"),
        governance=_get("policy_compliance_score"),
        maintainability=maintainability,
        coverage_delta=_get("coverage_delta"),
        scalar_score=scalar_score,
    )
