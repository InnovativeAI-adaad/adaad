# SPDX-License-Identifier: Apache-2.0
"""
EvolutionLoop — top-level epoch orchestration for ADAAD.

Binds all capability modules into a single run_epoch() call:
  Phase 0: Strategy    — FitnessLandscape determines preferred agent
  Phase 1: Propose     — AI agents generate MutationCandidate proposals
  Phase 2: Seed        — PopulationManager deduplicates and caps population
  Phase 3: Evolve      — N generations of score→select→crossover
  Phase 4: Adapt       — WeightAdaptor updates scoring weights
  Phase 5: Record      — FitnessLandscape persists win/loss per mutation type
  Return:  EpochResult dataclass consumed by Orchestrator

simulate_outcomes mode:
  When simulate_outcomes=True, synthetic MutationOutcome objects are derived
  from scored population — enabling full weight adaptation without a live CI
  test runner. Used for unit tests and dry-run development.

Integration with Orchestrator (app/main.py):
  self._evolution_loop = EvolutionLoop(api_key=..., generations=3)
  result = self._evolution_loop.run_epoch(context)
  journal.write_entry('epoch_complete', dataclasses.asdict(result))
"""

from __future__ import annotations

import time
try:
    from runtime.governance import journal as journal_module  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    journal_module = None  # type: ignore[assignment]
from dataclasses import dataclass, field
from typing import List, Optional

from runtime.autonomy.ai_mutation_proposer import CodebaseContext, propose_from_all_agents
from runtime.autonomy.fitness_landscape import FitnessLandscape
from runtime.autonomy.mutation_scaffold import MutationCandidate, MutationScore
from runtime.autonomy.weight_adaptor import MutationOutcome, WeightAdaptor
from runtime.autonomy.penalty_adaptor import build_penalty_outcomes_from_scores, PenaltyAdaptor
from runtime.autonomy.explore_exploit_controller import (
    ExploreExploitController,
    EvolutionMode,
)
from runtime.evolution.population_manager import PopulationManager
from runtime.evolution.mutation_route_optimizer import MutationRouteOptimizer, RouteTier
from runtime.evolution.fast_path_scorer import fast_path_score as _fast_path_score

# ---------------------------------------------------------------------------
# EpochResult
# ---------------------------------------------------------------------------


@dataclass
class EpochResult:
    """
    Observable output of a single evolution epoch.

    Consumed by the Orchestrator for journaling and health endpoint exposure.
    """
    epoch_id:               str
    generation_count:       int
    total_candidates:       int
    accepted_count:         int
    top_mutation_ids:       List[str]      = field(default_factory=list)
    weight_accuracy:        float          = 0.0
    recommended_next_agent: str            = "beast"
    duration_seconds:       float          = 0.0
    evolution_mode:         str            = EvolutionMode.EXPLORE.value
    window_explore_ratio:   float          = 1.0
    # PR-PHASE4-02: semantic scoring provenance
    semantic_scored_count:  int            = 0
    scoring_algorithm_version: str         = "v1.2.0+semantic_diff_v1.0"
    # PR-PHASE4-03: route gate fields
    elevated_mutation_ids:  List[str]      = field(default_factory=list)
    trivial_fast_pathed:    int            = 0


# ---------------------------------------------------------------------------
# EvolutionLoop
# ---------------------------------------------------------------------------


class EvolutionLoop:
    """
    Main epoch controller. Instantiate once in Orchestrator.__init__().

    Args:
        api_key:          Anthropic API key for Claude mutation proposals.
        generations:      GA generations per epoch (default 3).
        simulate_outcomes: When True, derive outcomes from scored population
                          rather than requiring real CI signal (default False).
        landscape_path:   Override FitnessLandscape persistence path.
        adaptor_path:     Override WeightAdaptor persistence path.
    """

    def __init__(
        self,
        api_key:            str,
        generations:        int  = 3,
        simulate_outcomes:  bool = False,
        controller:         Optional[ExploreExploitController] = None,
    ) -> None:
        self._api_key          = api_key
        self._generations      = generations
        self._simulate         = simulate_outcomes
        self._adaptor          = WeightAdaptor()
        self._landscape        = FitnessLandscape()
        self._manager          = PopulationManager()
        self._controller       = controller or ExploreExploitController()
        self._route_optimizer  = MutationRouteOptimizer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_epoch(self, context: CodebaseContext) -> EpochResult:
        """
        Execute a complete evolution epoch and return the result.

        Args:
            context: Current codebase snapshot (file summaries, failures, epoch_id).

        Returns:
            EpochResult dataclass with all epoch-level metrics.
        """
        t_start = time.monotonic()
        epoch_id = context.current_epoch_id

        # Phase 0: Strategy — which agent should lead this epoch?
        preferred_agent = self._landscape.recommended_agent()

        # Phase 0b: Mode selection — Explore or Exploit?
        #   epoch_score from prior epoch is not available at proposal time;
        #   use landscape plateau signal as the primary driver.
        is_plateau = self._landscape.is_plateau()
        prior_epoch_score = float(
            getattr(context, "prior_epoch_score", 0.0) or 0.0
        )
        evolution_mode = self._controller.select_mode(
            epoch_id=epoch_id,
            epoch_score=prior_epoch_score,
            is_plateau=is_plateau,
        )

        # Phase 1: Propose — call Claude for all three agents
        all_proposals: List[MutationCandidate] = []
        try:
            proposals_by_agent = propose_from_all_agents(context, self._api_key)
            for agent_proposals in proposals_by_agent.values():
                all_proposals.extend(agent_proposals)
        except Exception:  # noqa: BLE001 — graceful degradation
            pass  # Empty population handled by PopulationManager

        total_candidates = len(all_proposals)

        # Phase 2: Seed population
        self._manager.set_weights(self._adaptor.current_weights)
        self._manager.seed(all_proposals)

        # Phase 2.5: Route — classify each candidate before deep scoring
        _elevated_ids: List[str] = []
        _trivial_count: int = 0
        _routed_proposals: List = []
        for _cand in self._manager.population:
            try:
                _rd = self._route_optimizer.route(
                    mutation_id=_cand.mutation_id,
                    op_types=list(getattr(_cand, 'op_types', []) or []),
                    file_paths=list(getattr(_cand, 'file_paths', []) or []),
                    intent=str(getattr(_cand, 'description', '') or ''),
                    loc_delta=int(getattr(_cand, 'expected_gain', 0) or 0),
                )
                if _rd.tier is RouteTier.ELEVATED:
                    _elevated_ids.append(_cand.mutation_id)
                elif _rd.tier is RouteTier.TRIVIAL:
                    _trivial_count += 1
            except Exception:  # noqa: BLE001
                pass
        _route_decision_digest = journal_module.append_tx(
            "mutation_route_decision",
            {"elevated": _elevated_ids, "trivial_count": _trivial_count,
             "epoch_id": epoch_id}
        ) if journal_module else {}

        # Phase 3: Evolve for N generations
        all_scores: List[MutationScore] = []
        for _ in range(self._generations):
            gen_scores = self._manager.evolve_generation()
            all_scores.extend(gen_scores)

        # Collect final accepted candidates
        accepted = [s for s in all_scores if s.accepted]
        accepted_count = len(accepted)

        # PR-PHASE4-02: count candidates where semantic scoring was active
        semantic_scored_count = sum(
            1 for c in all_proposals
            if getattr(c, 'python_content', None) is not None
        )

        # Phase 4: Adapt weights
        outcomes = self._build_outcomes(all_scores)
        updated_weights = self._adaptor.adapt(outcomes)

        # Phase 3: inject scored candidates into PenaltyAdaptor for richer risk signals
        penalty_outcomes = build_penalty_outcomes_from_scores(
            all_scores, simulate=self._simulate
        )
        if hasattr(self._adaptor, '_penalty_adaptor'):
            updated_weights = self._adaptor._penalty_adaptor.adapt(
                updated_weights, penalty_outcomes, self._adaptor.epoch_count
            )
            # Write back adapted weights so evolution loop uses them
            self._adaptor._weights = updated_weights

        # Phase 5: Record landscape
        for score in accepted:
            # Use agent_origin as a proxy for mutation_type mapping
            mut_type = self._agent_to_type(score.agent_origin)
            self._landscape.record(mut_type, won=score.score > 0.50)

        # Phase 5b: Commit epoch to E/E controller
        #   Compute epoch fitness score as mean of accepted scores (or 0 if none)
        epoch_fitness = (
            round(sum(s.score for s in accepted) / len(accepted), 4)
            if accepted else 0.0
        )
        self._controller.commit_epoch(epoch_id=epoch_id, mode=evolution_mode)

        # Top-5 mutation IDs by score
        unique_ids: List[str] = []
        seen_ids: set = set()
        for s in sorted(all_scores, key=lambda x: -x.score):
            if s.mutation_id not in seen_ids:
                unique_ids.append(s.mutation_id)
                seen_ids.add(s.mutation_id)
            if len(unique_ids) >= 5:
                break

        return EpochResult(
            epoch_id=epoch_id,
            generation_count=self._generations,
            total_candidates=total_candidates,
            accepted_count=accepted_count,
            top_mutation_ids=unique_ids,
            weight_accuracy=round(self._adaptor.prediction_accuracy, 4),
            recommended_next_agent=self._landscape.recommended_agent(),
            duration_seconds=round(time.monotonic() - t_start, 3),
            evolution_mode=evolution_mode.value,
            window_explore_ratio=round(self._controller.window_explore_ratio(), 4),
            semantic_scored_count=semantic_scored_count,
            scoring_algorithm_version="v1.2.0+semantic_diff_v1.0",
            elevated_mutation_ids=_elevated_ids,
            trivial_fast_pathed=_trivial_count,
        )

    # ------------------------------------------------------------------
    # Outcome construction (simulate mode)
    # ------------------------------------------------------------------

    def _build_outcomes(self, scores: List[MutationScore]) -> List[MutationOutcome]:
        """
        Build MutationOutcome list for WeightAdaptor.

        In simulate mode: 'improved' is approximated as score > 0.40.
        In production: caller injects real outcomes (post-CI signal).
        """
        if not self._simulate:
            # Production: no synthetic outcomes — return empty to skip adaptation
            # until real outcomes are injected by Orchestrator post-merge.
            return []

        return [
            MutationOutcome(
                mutation_id=s.mutation_id,
                accepted=s.accepted,
                improved=s.score > 0.40,
                predicted_accept=s.accepted,
            )
            for s in scores
        ]

    @staticmethod
    def _agent_to_type(agent_origin: str) -> str:
        """Map agent_origin string to canonical mutation_type for landscape."""
        mapping = {
            "architect": "structural",
            "dream":     "experimental",
            "beast":     "performance",
            "crossover": "behavioral",
        }
        return mapping.get(agent_origin, "behavioral")
