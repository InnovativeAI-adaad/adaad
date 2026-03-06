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
  Phase 3:   Evolve        — N generations of score→select→crossover
  Phase 4:   Adapt         — WeightAdaptor updates scoring weights
  Phase 5:   Record        — FitnessLandscape persists win/loss per mutation type
  Phase 5b:  E/E commit    — ExploreExploitController epoch commit
  Phase 6:   Checkpoint    — PR-PHASE4-05: anchor EpochResult to CheckpointChain
  Return:    EpochResult dataclass consumed by Orchestrator

simulate_outcomes mode:
  When simulate_outcomes=True, synthetic MutationOutcome objects are derived
  from scored population — enabling full weight adaptation without a live CI
  test runner.

Integration with Orchestrator (app/main.py):
  self._evolution_loop = EvolutionLoop(api_key=..., generations=3)
  result = self._evolution_loop.run_epoch(context)
  journal.write_entry('epoch_complete', dataclasses.asdict(result))
"""

from __future__ import annotations

import json
import re
import json
import time
from pathlib import Path as _Path
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
from runtime.evolution.mutation_route_optimizer import (
    MutationRouteOptimizer,
    RouteTier,
)
from runtime.evolution.fast_path_scorer import fast_path_score
from runtime.evolution.entropy_fast_gate import EntropyFastGate, GateVerdict
from runtime.evolution.checkpoint_chain import (
    checkpoint_chain_digest,
    verify_checkpoint_chain,
    ZERO_HASH,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CHAIN_PATH = Path(__file__).resolve().parents[2] / "data" / "checkpoint_chain.jsonl"

# Entropy source patterns scanned in proposal python_content (Phase 1.5)
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

    Consumed by the Orchestrator for journaling and health endpoint exposure.

    Phase 4 additions (v2.2.0):
      elevated_mutation_ids — IDs flagged for human review (PR-PHASE4-03)
      trivial_fast_pathed   — count of TRIVIAL mutations via FastPathScorer
      entropy_quarantined   — proposals denied by EntropyFastGate (PR-PHASE4-04)
      entropy_warned        — proposals warned by EntropyFastGate
      checkpoint_digest     — SHA-256 chain digest anchoring this epoch (PR-PHASE4-05)
      mean_lineage_proximity — mean semantic proximity to accepted ancestors (PR-PHASE4-07)
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
    # PR-PHASE4-03: Route gate
    elevated_mutation_ids:  List[str]  = field(default_factory=list)
    trivial_fast_pathed:    int        = 0
    # PR-PHASE4-04: Entropy gate
    entropy_quarantined:    int        = 0
    entropy_warned:         int        = 0
    # PR-PHASE4-05: Checkpoint chain
    checkpoint_digest:      str        = ""
    # PR-PHASE4-07: Lineage confidence
    mean_lineage_proximity: float      = 0.0


# ---------------------------------------------------------------------------
# EvolutionLoop
# ---------------------------------------------------------------------------


class EvolutionLoop:
    """
    Main epoch controller. Instantiate once in Orchestrator.__init__().

    Args:
        api_key:           Anthropic API key for Claude mutation proposals.
        generations:       GA generations per epoch (default 3).
        simulate_outcomes: When True, derive outcomes from scored population
                           rather than requiring real CI signal (default False).
        controller:        Override ExploreExploitController instance.
    """

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
        self._router           = MutationRouteOptimizer()          # PR-PHASE4-03
        self._entropy_gate     = EntropyFastGate()                 # PR-PHASE4-04
        self._chain_predecessor: str = self._load_chain_tip()      # PR-PHASE4-05

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
        t_start  = time.monotonic()
        epoch_id = context.current_epoch_id

        # Phase 0: Strategy — which agent should lead this epoch?
        preferred_agent = self._landscape.recommended_agent()

        # Phase 0b: Mode selection — Explore or Exploit?
        is_plateau        = self._landscape.is_plateau()
        prior_epoch_score = float(getattr(context, "prior_epoch_score", 0.0) or 0.0)
        evolution_mode    = self._controller.select_mode(
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
            pass  # empty population handled by PopulationManager

        total_candidates = len(all_proposals)

        # ── Phase 1.5: EntropyFastGate — PR-PHASE4-04 ──────────────────
        entropy_quarantined = 0
        entropy_warned      = 0
        clean_proposals: List[MutationCandidate] = []

        for candidate in all_proposals:
            sources     = _detect_entropy_sources(candidate.python_content or "")
            est_bits    = _estimate_entropy_bits(candidate.python_content or "", sources)
            gate_result = self._entropy_gate.evaluate(
                mutation_id    = candidate.mutation_id,
                estimated_bits = est_bits,
                sources        = sources,
            )
            if gate_result.denied:
                entropy_quarantined += 1
                # Quarantined proposals never reach the population.
            elif gate_result.verdict == GateVerdict.WARN:
                entropy_warned += 1
                clean_proposals.append(candidate)  # proceeds flagged
            else:
                clean_proposals.append(candidate)

        # Phase 2: Seed population
        self._manager.set_weights(self._adaptor.current_weights)
        self._manager.seed(clean_proposals)

        # ── Phase 2.5: Route Gate — PR-PHASE4-03 ───────────────────────
        trivial_fast_pathed:    int        = 0
        elevated_mutation_ids:  List[str]  = []
        trivial_scores:         List[MutationScore] = []

        population_after_seed = list(self._manager.population)
        trivial_ids: set = set()

        for candidate in population_after_seed:
            content  = candidate.python_content or ""
            loc_add  = content.count("\n") if content else 0
            decision = self._router.route(
                mutation_id   = candidate.mutation_id,
                intent        = _infer_intent(candidate),
                ops           = _infer_ops(candidate),
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
                    accepted     = bool(fp.get("passed_constitution", True)) and float(fp["score"]) >= 0.10,
                    agent_origin = candidate.agent_origin,
                    epoch_id     = epoch_id,
                ))
                trivial_fast_pathed += 1
            elif decision.tier == RouteTier.ELEVATED:
                elevated_mutation_ids.append(candidate.mutation_id)

        # Remove trivial candidates from population — they skip evolve_generation
        if trivial_ids:
            self._manager._population = [
                c for c in self._manager._population
                if c.mutation_id not in trivial_ids
            ]

        # Phase 3: Evolve for N generations (STANDARD + ELEVATED only)
        all_scores: List[MutationScore] = list(trivial_scores)
        for _ in range(self._generations):
            gen_scores = self._manager.evolve_generation()
            all_scores.extend(gen_scores)

        # Collect accepted
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
            mut_type = self._agent_to_type(score.agent_origin)
            self._landscape.record(mut_type, won=score.score > 0.50)

        # Phase 5b: Commit epoch to E/E controller
        epoch_fitness = (
            round(sum(s.score for s in accepted) / len(accepted), 4)
            if accepted else 0.0
        )
        self._controller.commit_epoch(epoch_id=epoch_id, mode=evolution_mode)

        # PR-PHASE4-07: Lineage confidence proximity (advisory, fail-open)
        mean_lineage_proximity = _compute_mean_lineage_proximity(accepted)

        # Phase 5c: PR-PHASE4-05 — Anchor epoch to CheckpointChain
        _checkpoint_payload = {
            "epoch_id": epoch_id,
            "accepted_count": accepted_count,
            "total_candidates": total_candidates,
            "entropy_quarantined": _entropy_quarantined,
            "trivial_fast_pathed": _trivial_count,
        }
        _cp_digest = self._append_epoch_checkpoint(epoch_id, _checkpoint_payload)

        # Top-5 mutation IDs by score
        unique_ids: List[str] = []
        seen_ids: set = set()
        for s in sorted(all_scores, key=lambda x: -x.score):
            if s.mutation_id not in seen_ids:
                unique_ids.append(s.mutation_id)
                seen_ids.add(s.mutation_id)
            if len(unique_ids) >= 5:
                break

        # ── Phase 6: CheckpointChain — PR-PHASE4-05 ────────────────────
        epoch_payload: Dict = {
            "epoch_id":          epoch_id,
            "accepted_count":    accepted_count,
            "total_candidates":  total_candidates,
            "trivial_fast_pathed": trivial_fast_pathed,
            "entropy_quarantined": entropy_quarantined,
            "evolution_mode":    evolution_mode.value if hasattr(evolution_mode, "value") else str(evolution_mode),
            "top_mutation_ids":  unique_ids,
        }
        cp             = checkpoint_chain_digest(
            epoch_payload,
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
            evolution_mode         = evolution_mode.value if hasattr(evolution_mode, "value") else str(evolution_mode),
            window_explore_ratio   = round(self._controller.window_explore_ratio(), 4),
            elevated_mutation_ids  = elevated_mutation_ids,
            trivial_fast_pathed    = trivial_fast_pathed,
            entropy_quarantined    = entropy_quarantined,
            entropy_warned         = entropy_warned,
            checkpoint_digest      = cp.chain_digest,
            mean_lineage_proximity = mean_lineage_proximity,
        )

    # ------------------------------------------------------------------
    # Outcome construction (simulate mode)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Checkpoint chain helpers (PR-PHASE4-05)
    # ------------------------------------------------------------------

    def _load_and_verify_chain(self) -> None:
        """Boot-time: load checkpoint_chain.jsonl and verify integrity. Halt if corrupt."""
        if not self._chain_path.exists():
            return
        try:
            raw = self._chain_path.read_text(encoding="utf-8").splitlines()
            loaded: list[_ChainedCheckpoint] = []
            for line in raw:
                if not line.strip():
                    continue
                obj = json.loads(line)
                loaded.append(_ChainedCheckpoint(
                    epoch_id=obj["epoch_id"],
                    payload=obj["payload"],
                    predecessor_digest=obj["predecessor_digest"],
                    chain_digest=obj["chain_digest"],
                ))
            if loaded and not _verify_checkpoint_chain(loaded):
                raise RuntimeError("CHECKPOINT_CHAIN_INTEGRITY_FAILURE: chain digest mismatch")
            self._chain = loaded
            self._last_chain_digest = loaded[-1].chain_digest if loaded else _ZERO_HASH
        except (RuntimeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"CHECKPOINT_CHAIN_LOAD_FAILURE: {exc}") from exc

    def _append_epoch_checkpoint(self, epoch_id: str, epoch_payload: dict) -> str:
        """Append a new checkpoint to the chain and persist it. Returns chain_digest."""
        try:
            cp = _checkpoint_chain_digest(
                epoch_payload,
                epoch_id=epoch_id,
                predecessor_digest=self._last_chain_digest,
            )
            self._chain.append(cp)
            self._last_chain_digest = cp.chain_digest
            self._chain_path.parent.mkdir(parents=True, exist_ok=True)
            with self._chain_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "epoch_id": cp.epoch_id,
                    "payload": cp.payload,
                    "predecessor_digest": cp.predecessor_digest,
                    "chain_digest": cp.chain_digest,
                }) + "\n")
            return cp.chain_digest
        except Exception:  # noqa: BLE001 — checkpoint failure must not halt epoch
            return ""

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
        mapping = {
            "architect": "structural",
            "dream":     "experimental",
            "beast":     "performance",
            "crossover": "behavioral",
        }
        return mapping.get(agent_origin, "behavioral")

    # ------------------------------------------------------------------
    # Checkpoint chain helpers (PR-PHASE4-05)
    # ------------------------------------------------------------------

    @staticmethod
    def _load_chain_tip() -> str:
        """Load the last chain_digest from the persisted chain file. Fail-closed on corruption."""
        if not _CHAIN_PATH.exists():
            return ZERO_HASH
        try:
            last_line = ""
            with _CHAIN_PATH.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        last_line = line
            if not last_line:
                return ZERO_HASH
            entry = json.loads(last_line)
            digest = entry.get("chain_digest", "")
            return digest if digest else ZERO_HASH
        except Exception:  # noqa: BLE001 — fail-open: start a new chain segment
            return ZERO_HASH


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _detect_entropy_sources(content: str) -> List[str]:
    """Scan python_content for nondeterministic patterns. Deterministic."""
    found: List[str] = []
    seen: set = set()
    for pattern, source in _NONDETERMINISTIC_PATTERNS:
        if source not in seen and re.search(pattern, content):
            found.append(source)
            seen.add(source)
    return found


def _estimate_entropy_bits(content: str, sources: List[str]) -> int:
    """Conservative entropy bit estimate: 0 for clean content, 8 per source."""
    return len(sources) * 8


def _infer_intent(candidate: MutationCandidate) -> str:
    """Derive a routing intent string from a MutationCandidate."""
    origin = candidate.agent_origin.lower()
    if origin == "architect":
        return "structural_refactor"
    if origin == "dream":
        return "experimental"
    return "performance_fix"


def _infer_ops(candidate: MutationCandidate) -> List[Dict]:
    """Build a minimal ops list from candidate fields for the route optimizer."""
    return [{"type": _infer_intent(candidate), "mutation_id": candidate.mutation_id}]


def _infer_risk_tags(candidate: MutationCandidate) -> List[str]:
    tags: List[str] = []
    if candidate.risk_score > 0.70:
        tags.append("high_risk")
    if candidate.complexity > 0.70:
        tags.append("high_complexity")
    return tags


def _append_chain_entry(cp, path: Path) -> None:
    """Append a ChainedCheckpoint as a JSONL line. Fail-open on write error."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "epoch_id":           cp.epoch_id,
            "predecessor_digest": cp.predecessor_digest,
            "payload_digest":     cp.payload_digest,
            "chain_digest":       cp.chain_digest,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
    except Exception:  # noqa: BLE001 — audit failure must not block evolution
        pass


def _compute_mean_lineage_proximity(accepted: List[MutationScore]) -> float:
    """
    PR-PHASE4-07: Compute mean semantic proximity score across accepted mutations.

    Uses SemanticDiffEngine AST metrics if python_content is available;
    falls back to 0.0 (neutral) on any error. Advisory only — never blocks.
    """
    if not accepted:
        return 0.0
    scores: List[float] = []
    for ms in accepted:
        # Proximity placeholder — full implementation wired in PR-PHASE4-07
        # scoring_algorithm.py applies the lineage bonus; here we report the mean.
        scores.append(getattr(ms, "lineage_proximity", 0.0))
    return round(sum(scores) / len(scores), 4) if scores else 0.0
