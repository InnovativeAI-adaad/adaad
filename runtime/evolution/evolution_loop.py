# SPDX-License-Identifier: Apache-2.0
"""
EvolutionLoop — top-level epoch orchestration for ADAAD.

Binds all capability modules into a single run_epoch() call:
  Phase 0:   Strategy      — FitnessLandscape determines preferred agent
  Phase 0b:  Mode          — ExploreExploitController selects epoch mode
  Phase 1:   Propose       — AI agents generate MutationCandidate proposals
  Phase 1.5: EntropyGate   — PR-PHASE4-04: quarantine nondeterministic proposals
  Phase 2:   Seed          — PopulationManager deduplicates and caps population
  Phase 2.5: RouteGate     — PR-PHASE4-03: classify TRIVIAL/STANDARD/ELEVATED
  Phase 3:   Evolve        — N generations of score/select/crossover
  Phase 4:   Adapt         — WeightAdaptor updates scoring weights
  Phase 5:   Record        — FitnessLandscape persists win/loss per mutation type
  Phase 5b:  E/E commit    — ExploreExploitController epoch commit
  Phase 6:   Checkpoint    — PR-PHASE4-05: anchor EpochResult to CheckpointChain
  Return:    EpochResult dataclass consumed by Orchestrator

simulate_outcomes mode:
  When simulate_outcomes=True, synthetic MutationOutcome objects are derived
  from scored population enabling full weight adaptation without a live CI
  test runner. Used for unit tests and dry-run development.

Integration with Orchestrator (app/main.py):
  self._evolution_loop = EvolutionLoop(api_key=..., generations=3)
  result = self._evolution_loop.run_epoch(context)
  journal.write_entry('epoch_complete', dataclasses.asdict(result))
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from runtime.autonomy.ai_mutation_proposer import CodebaseContext, propose_from_all_agents
from runtime.autonomy.fitness_landscape import FitnessLandscape
from runtime.autonomy.mutation_scaffold import MutationCandidate, MutationScore
from runtime.autonomy.weight_adaptor import MutationOutcome, WeightAdaptor
from runtime.autonomy.penalty_adaptor import build_penalty_outcomes_from_scores
from runtime.autonomy.explore_exploit_controller import (
    ExploreExploitController,
    EvolutionMode,
)
from runtime.evolution.population_manager import PopulationManager
from runtime.evolution.mutation_route_optimizer import MutationRouteOptimizer, RouteTier
from runtime.evolution.fast_path_scorer import fast_path_score
from runtime.evolution.entropy_fast_gate import EntropyFastGate, GateVerdict
from runtime.evolution.checkpoint_chain import checkpoint_chain_digest, ZERO_HASH

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CHAIN_PATH = Path(__file__).resolve().parents[2] / "data" / "checkpoint_chain.jsonl"

_NONDETERMINISTIC_PATTERNS: List[Tuple[str, str]] = [
    (r"\brandom\b",    "runtime_rng"),
    (r"\buuid\b",      "runtime_rng"),
    (r"time\.time\(",  "runtime_rng"),
    (r"time\.now\(",   "runtime_rng"),
    (r"\bos\.urandom", "runtime_rng"),
    (r"\bnetwork\b",   "network"),
    (r"\brequests\.",  "network"),
    (r"\bsocket\.",    "network"),
]


# ---------------------------------------------------------------------------
# EpochResult
# ---------------------------------------------------------------------------


@dataclass
class EpochResult:
    """
    Observable output of a single evolution epoch.

    Phase 4 additions (v2.2.0):
      elevated_mutation_ids  -- IDs flagged for human review (PR-PHASE4-03)
      trivial_fast_pathed    -- count of TRIVIAL mutations via FastPathScorer
      entropy_quarantined    -- proposals denied by EntropyFastGate (PR-PHASE4-04)
      entropy_warned         -- proposals warned by EntropyFastGate
      checkpoint_digest      -- SHA-256 chain digest anchoring this epoch (PR-PHASE4-05)
      mean_lineage_proximity -- mean semantic proximity to accepted ancestors (PR-PHASE4-07)
    """
    epoch_id:               str
    generation_count:       int
    total_candidates:       int
    accepted_count:         int
    top_mutation_ids:       List[str]  = field(default_factory=list)
    weight_accuracy:        float      = 0.0
    recommended_next_agent: str        = "beast"
    duration_seconds:       float      = 0.0
    evolution_mode:         str        = EvolutionMode.EXPLORE.value
    window_explore_ratio:   float      = 1.0
    elevated_mutation_ids:  List[str]  = field(default_factory=list)
    trivial_fast_pathed:    int        = 0
    entropy_quarantined:    int        = 0
    entropy_warned:         int        = 0
    checkpoint_digest:      str        = ""
    mean_lineage_proximity: float      = 0.0


# ---------------------------------------------------------------------------
# EvolutionLoop
# ---------------------------------------------------------------------------


class EvolutionLoop:
    """Main epoch controller. Instantiate once in Orchestrator.__init__()."""

    def __init__(
        self,
        api_key:           str,
        generations:       int  = 3,
        simulate_outcomes: bool = False,
        controller:        Optional[ExploreExploitController] = None,
    ) -> None:
        self._api_key          = api_key
        self._generations      = generations
        self._simulate         = simulate_outcomes
        self._adaptor          = WeightAdaptor()
        self._landscape        = FitnessLandscape()
        self._manager          = PopulationManager()
        self._controller       = controller or ExploreExploitController()
        self._router           = MutationRouteOptimizer()
        self._entropy_gate     = EntropyFastGate()
        self._chain_predecessor: str = self._load_chain_tip()

    def run_epoch(self, context: CodebaseContext) -> EpochResult:
        t_start  = time.monotonic()
        epoch_id = context.current_epoch_id

        # Phase 0: Strategy
        _preferred = self._landscape.recommended_agent()

        # Phase 0b: Mode selection
        is_plateau        = self._landscape.is_plateau()
        prior_epoch_score = float(getattr(context, "prior_epoch_score", 0.0) or 0.0)
        evolution_mode    = self._controller.select_mode(
            epoch_id=epoch_id,
            epoch_score=prior_epoch_score,
            is_plateau=is_plateau,
        )

        # Phase 1: Propose
        all_proposals: List[MutationCandidate] = []
        try:
            proposals_by_agent = propose_from_all_agents(context, self._api_key)
            for agent_proposals in proposals_by_agent.values():
                all_proposals.extend(agent_proposals)
        except Exception:
            pass

        total_candidates = len(all_proposals)

        # Phase 1.5: EntropyFastGate (PR-PHASE4-04)
        entropy_quarantined = 0
        entropy_warned      = 0
        clean_proposals: List[MutationCandidate] = []

        for candidate in all_proposals:
            content  = candidate.python_content or ""
            sources  = _detect_entropy_sources(content)
            result   = self._entropy_gate.evaluate(
                mutation_id    = candidate.mutation_id,
                estimated_bits = len(sources) * 8,
                sources        = sources,
            )
            if result.denied:
                entropy_quarantined += 1
            else:
                if result.verdict == GateVerdict.WARN:
                    entropy_warned += 1
                clean_proposals.append(candidate)

        # Phase 2: Seed population
        self._manager.set_weights(self._adaptor.current_weights)
        self._manager.seed(clean_proposals)

        # Phase 2.5: Route Gate (PR-PHASE4-03)
        trivial_fast_pathed:   int       = 0
        elevated_mutation_ids: List[str] = []
        trivial_scores:        List[MutationScore] = []
        trivial_ids:           set = set()

        for candidate in list(self._manager.population):
            content  = candidate.python_content or ""
            loc_add  = content.count("\n") if content else 0
            decision = self._router.route(
                mutation_id   = candidate.mutation_id,
                intent        = _infer_intent(candidate),
                ops           = [{"type": _infer_intent(candidate)}],
                files_touched = [],
                loc_added     = loc_add,
                loc_deleted   = 0,
                risk_tags     = _infer_risk_tags(candidate),
            )
            if decision.tier == RouteTier.TRIVIAL:
                trivial_ids.add(candidate.mutation_id)
                fp = fast_path_score(
                    mutation_id = candidate.mutation_id,
                    reason      = decision.reasons[0] if decision.reasons else "trivial",
                    loc_added   = loc_add,
                    loc_deleted = 0,
                )
                trivial_scores.append(MutationScore(
                    mutation_id  = candidate.mutation_id,
                    score        = float(fp["score"]),
                    accepted     = float(fp["score"]) >= 0.10,
                    agent_origin = candidate.agent_origin,
                    epoch_id     = epoch_id,
                ))
                trivial_fast_pathed += 1
            elif decision.tier == RouteTier.ELEVATED:
                elevated_mutation_ids.append(candidate.mutation_id)

        if trivial_ids:
            self._manager._population = [
                c for c in self._manager._population
                if c.mutation_id not in trivial_ids
            ]

        # Phase 3: Evolve (STANDARD + ELEVATED only)
        all_scores: List[MutationScore] = list(trivial_scores)
        for _ in range(self._generations):
            gen_scores = self._manager.evolve_generation()
            all_scores.extend(gen_scores)

        accepted       = [s for s in all_scores if s.accepted]
        accepted_count = len(accepted)

        # Phase 4: Adapt weights
        outcomes        = self._build_outcomes(all_scores)
        updated_weights = self._adaptor.adapt(outcomes)

        penalty_outcomes = build_penalty_outcomes_from_scores(
            all_scores, simulate=self._simulate
        )
        if hasattr(self._adaptor, "_penalty_adaptor"):
            updated_weights = self._adaptor._penalty_adaptor.adapt(
                updated_weights, penalty_outcomes, self._adaptor.epoch_count
            )
            self._adaptor._weights = updated_weights

        # Phase 5: Record landscape
        for score in accepted:
            self._landscape.record(self._agent_to_type(score.agent_origin), won=score.score > 0.50)

        # Phase 5b: E/E commit
        self._controller.commit_epoch(epoch_id=epoch_id, mode=evolution_mode)

        # PR-PHASE4-07 scaffold
        mean_lineage_proximity = _compute_mean_lineage_proximity(accepted)

        # Top-5 IDs
        unique_ids: List[str] = []
        seen_ids:   set = set()
        for s in sorted(all_scores, key=lambda x: -x.score):
            if s.mutation_id not in seen_ids:
                unique_ids.append(s.mutation_id)
                seen_ids.add(s.mutation_id)
            if len(unique_ids) >= 5:
                break

        # Phase 6: CheckpointChain (PR-PHASE4-05)
        mode_str = evolution_mode.value if hasattr(evolution_mode, "value") else str(evolution_mode)
        cp = checkpoint_chain_digest(
            {
                "epoch_id":            epoch_id,
                "accepted_count":      accepted_count,
                "total_candidates":    total_candidates,
                "trivial_fast_pathed": trivial_fast_pathed,
                "entropy_quarantined": entropy_quarantined,
                "evolution_mode":      mode_str,
                "top_mutation_ids":    unique_ids,
            },
            epoch_id           = epoch_id,
            predecessor_digest = self._chain_predecessor,
        )
        self._chain_predecessor = cp.chain_digest
        _append_chain_entry(cp, _CHAIN_PATH)

        return EpochResult(
            epoch_id               = epoch_id,
            generation_count       = self._generations,
            total_candidates       = total_candidates,
            accepted_count         = accepted_count,
            top_mutation_ids       = unique_ids,
            weight_accuracy        = round(self._adaptor.prediction_accuracy, 4),
            recommended_next_agent = self._landscape.recommended_agent(),
            duration_seconds       = round(time.monotonic() - t_start, 3),
            evolution_mode         = mode_str,
            window_explore_ratio   = round(self._controller.window_explore_ratio(), 4),
            elevated_mutation_ids  = elevated_mutation_ids,
            trivial_fast_pathed    = trivial_fast_pathed,
            entropy_quarantined    = entropy_quarantined,
            entropy_warned         = entropy_warned,
            checkpoint_digest      = cp.chain_digest,
            mean_lineage_proximity = mean_lineage_proximity,
        )

    def _build_outcomes(self, scores: List[MutationScore]) -> List[MutationOutcome]:
        if not self._simulate:
            return []
        return [
            MutationOutcome(
                mutation_id      = s.mutation_id,
                accepted         = s.accepted,
                improved         = s.score > 0.40,
                predicted_accept = s.accepted,
            )
            for s in scores
        ]

    @staticmethod
    def _agent_to_type(agent_origin: str) -> str:
        return {
            "architect": "structural",
            "dream":     "experimental",
            "beast":     "performance",
            "crossover": "behavioral",
        }.get(agent_origin, "behavioral")

    @staticmethod
    def _load_chain_tip() -> str:
        if not _CHAIN_PATH.exists():
            return ZERO_HASH
        try:
            last = ""
            with _CHAIN_PATH.open("r", encoding="utf-8") as fh:
                for line in fh:
                    s = line.strip()
                    if s:
                        last = s
            return json.loads(last).get("chain_digest") or ZERO_HASH if last else ZERO_HASH
        except Exception:
            return ZERO_HASH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_entropy_sources(content: str) -> List[str]:
    found: List[str] = []
    seen:  set = set()
    for pattern, source in _NONDETERMINISTIC_PATTERNS:
        if source not in seen and re.search(pattern, content):
            found.append(source)
            seen.add(source)
    return found


def _infer_intent(candidate: MutationCandidate) -> str:
    return {
        "architect": "structural_refactor",
        "dream":     "experimental",
    }.get(candidate.agent_origin.lower(), "performance_fix")


def _infer_risk_tags(candidate: MutationCandidate) -> List[str]:
    tags: List[str] = []
    if candidate.risk_score > 0.70:
        tags.append("high_risk")
    if candidate.complexity > 0.70:
        tags.append("high_complexity")
    return tags


def _append_chain_entry(cp, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "epoch_id":           cp.epoch_id,
                "predecessor_digest": cp.predecessor_digest,
                "payload_digest":     cp.payload_digest,
                "chain_digest":       cp.chain_digest,
            }, sort_keys=True) + "\n")
    except Exception:
        pass


def _compute_mean_lineage_proximity(accepted: List[MutationScore]) -> float:
    if not accepted:
        return 0.0
    scores = [getattr(ms, "lineage_proximity", 0.0) for ms in accepted]
    return round(sum(scores) / len(scores), 4) if scores else 0.0
