# SPDX-License-Identifier: Apache-2.0
"""
PopulationManager — GA-style population evolution for ADAAD.

Implements:
- seed(): fingerprint-based deduplication + MAX_POPULATION cap.
- evolve_generation(): score → select elites → crossover → advance.
- BLX-alpha crossover (alpha=0.5) for numeric MutationCandidate fields.
- Diversity enforcement via MD5 fingerprint of rounded numeric fields.
- Elitism: top ELITE_SIZE candidates survive each generation unchanged.

Constants:
  ELITE_SIZE      = 3   (top survivors per generation)
  MAX_POPULATION  = 12  (hard cap post-deduplication)
  CROSSOVER_RATE  = 0.4 (per-generation crossover probability)
  BLX_ALPHA       = 0.5 (blend crossover extension factor)
"""

from __future__ import annotations

import hashlib
import random
from typing import List, Optional

from runtime.autonomy.mutation_scaffold import (
    MutationCandidate,
    MutationScore,
    PopulationState,
    ScoringWeights,
    rank_mutation_candidates,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELITE_SIZE:     int   = 3
MAX_POPULATION: int   = 12
CROSSOVER_RATE: float = 0.4
BLX_ALPHA:      float = 0.5


# ---------------------------------------------------------------------------
# PopulationManager
# ---------------------------------------------------------------------------


class PopulationManager:
    """
    Genetic Algorithm population controller for one epoch.

    Lifecycle:
        manager = PopulationManager()
        manager.set_weights(scoring_weights)
        manager.seed(all_proposals_flat_list)
        scores = manager.evolve_generation()   # call N times
        top = manager.top_candidates(n=5)
    """

    def __init__(self) -> None:
        self._population: List[MutationCandidate] = []
        self._state   = PopulationState()
        self._weights: Optional[ScoringWeights] = None
        self._rng     = random.Random()  # seeded lazily — deterministic via caller

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def set_weights(self, weights: ScoringWeights) -> None:
        """Inject adaptive scoring weights for this epoch."""
        self._weights = weights

    def seed(self, candidates: List[MutationCandidate]) -> None:
        """
        Initialise population from a flat list of proposals.

        Steps:
        1. enforce_diversity() deduplicates by numeric fingerprint.
        2. Caps at MAX_POPULATION (12) — excess dropped.
        """
        self._population = self._enforce_diversity(candidates)[:MAX_POPULATION]
        self._state = PopulationState()

    # ------------------------------------------------------------------
    # Evolution
    # ------------------------------------------------------------------

    def evolve_generation(self) -> List[MutationScore]:
        """
        Run one generation: score → elect elites → crossover → cap.

        Returns:
            Sorted list of MutationScore for the current population.
        """
        if not self._population:
            return []

        # Score current population
        scores = rank_mutation_candidates(
            self._population,
            weights=self._weights,
            population_state=self._state,
        )

        # Elect elites
        elite_scores = [s for s in scores if s.accepted][:ELITE_SIZE]
        elite_ids    = [s.mutation_id for s in elite_scores]
        for eid in elite_ids:
            self._state.record_elite(eid)

        # Build elite candidate lookup
        elite_map = {c.mutation_id: c for c in self._population if c.mutation_id in elite_ids}
        elites    = [elite_map[eid] for eid in elite_ids if eid in elite_map]

        # Crossover phase
        children: List[MutationCandidate] = []
        if len(elites) >= 2 and random.random() < CROSSOVER_RATE:
            for i in range(min(len(elites) - 1, ELITE_SIZE)):
                child = self._crossover(elites[i], elites[(i + 1) % len(elites)])
                if child:
                    children.append(child)

        # Merge elites + children, deduplicate, cap
        merged = elites + children + [
            c for c in self._population if c.mutation_id not in elite_ids
        ]
        self._population = self._enforce_diversity(merged)[:MAX_POPULATION]
        self._state.advance_generation()

        return scores

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def top_candidates(self, n: int = 5) -> List[MutationCandidate]:
        """Return top-n candidates by score."""
        scores = rank_mutation_candidates(
            self._population,
            weights=self._weights,
            population_state=self._state,
        )
        top_ids = [s.mutation_id for s in scores[:n]]
        lookup  = {c.mutation_id: c for c in self._population}
        return [lookup[mid] for mid in top_ids if mid in lookup]

    @property
    def population(self) -> List[MutationCandidate]:
        """Current population snapshot (read-only intent)."""
        return list(self._population)

    @property
    def state(self) -> PopulationState:
        return self._state

    # ------------------------------------------------------------------
    # GA internals
    # ------------------------------------------------------------------

    def _crossover(
        self,
        parent_a: MutationCandidate,
        parent_b: MutationCandidate,
    ) -> Optional[MutationCandidate]:
        """
        BLX-alpha crossover on numeric fields.

        Child mutation_id: blend of parent IDs to preserve lineage slug.
        parent_id: set to parent_a.mutation_id for elitism bonus eligibility.
        """
        import time as _time
        child_id = f"cross-{parent_a.mutation_id[:8]}-{parent_b.mutation_id[:8]}-{int(_time.time())}"
        return MutationCandidate(
            mutation_id=child_id,
            expected_gain=self._blend(parent_a.expected_gain,  parent_b.expected_gain),
            risk_score=   self._blend(parent_a.risk_score,     parent_b.risk_score),
            complexity=   self._blend(parent_a.complexity,     parent_b.complexity),
            coverage_delta=self._blend(parent_a.coverage_delta, parent_b.coverage_delta),
            strategic_horizon=self._blend(parent_a.strategic_horizon, parent_b.strategic_horizon),
            forecast_roi=self._blend(parent_a.forecast_roi,   parent_b.forecast_roi),
            parent_id=parent_a.mutation_id,
            generation=self._state.generation + 1,
            agent_origin="crossover",
            epoch_id=parent_a.epoch_id,
            source_context_hash=parent_a.source_context_hash,
        )

    @staticmethod
    def _blend(a: float, b: float, alpha: float = BLX_ALPHA) -> float:
        """
        BLX-alpha blend crossover for a single numeric field.

        Result range: [lo - extent, hi + extent] where extent = (hi-lo)*alpha.
        Not clamped to [0,1] — scoring engine handles out-of-range gracefully.
        """
        lo, hi = min(a, b), max(a, b)
        extent = (hi - lo) * alpha
        return round(random.uniform(lo - extent, hi + extent), 4)

    @staticmethod
    def _fingerprint(candidate: MutationCandidate) -> str:
        """
        8-hex MD5 fingerprint over 4 numeric fields at 3 d.p. precision.

        Near-duplicates (same scores to 3 d.p.) share a fingerprint and are
        deduplicated — genetic diversity beats marginal score precision.
        """
        key = f"{candidate.expected_gain:.3f}|{candidate.risk_score:.3f}|" \
              f"{candidate.complexity:.3f}|{candidate.coverage_delta:.3f}"
        return hashlib.md5(key.encode()).hexdigest()[:8]

    @classmethod
    def _enforce_diversity(
        cls,
        candidates: List[MutationCandidate],
    ) -> List[MutationCandidate]:
        """
        Deduplicate candidates by fingerprint, preserving insertion order.
        """
        seen: set = set()
        result: List[MutationCandidate] = []
        for c in candidates:
            fp = cls._fingerprint(c)
            if fp not in seen:
                seen.add(fp)
                result.append(c)
        return result
