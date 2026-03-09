# SPDX-License-Identifier: Apache-2.0
"""
EvolutionLoop — top-level epoch orchestration for ADAAD.

Binds all capability modules into a single run_epoch() call:
  Phase 0:   Strategy      — FitnessLandscape determines preferred agent
  Phase 0b:  Mode          — ExploreExploitController selects epoch mode
  Phase 0c:  Replay        — ContextReplayInterface injects context_digest + explore_ratio (deferred PR-9-03)
  Phase 1:   Propose       — AI agents generate MutationCandidate proposals
  Phase 1.5: EntropyGate   — PR-PHASE4-04: quarantine nondeterministic proposals
  Phase 2:   Seed          — PopulationManager deduplicates and caps population
  Phase 2.5: RouteGate     — PR-PHASE4-03: classify TRIVIAL/STANDARD/ELEVATED
  Phase 3:   Evolve        — N generations of score/select/crossover
  Phase 4:   Adapt         — WeightAdaptor updates scoring weights
  Phase 5:   Record        — FitnessLandscape persists win/loss per mutation type
  Phase 5b:  E/E commit    — ExploreExploitController epoch commit
  Phase 5c:  Craft Pattern — CraftPatternExtractor writes reasoning pattern to SoulboundLedger
  Phase 5d:  Reward Signal — RewardSignalBridge ingests all scores → RewardLearning pipeline
  Phase 5e:  Bandit Update — AgentBanditSelector.update() with epoch reward signal         [PR-11-A-02]
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
import logging
import os
import re
import time
import traceback
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
# Phase 9: Soulbound Context — CraftPatternExtractor wiring (PR-9-02)
from runtime.memory.craft_pattern_extractor import CraftPatternExtractor
from runtime.memory.soulbound_ledger import SoulboundLedger, DEFAULT_LEDGER_PATH
# Phase 9: ContextReplayInterface — proposal annotation wiring (deferred PR-9-03)
from runtime.memory.context_replay_interface import ContextReplayInterface
# Phase 10: Reward Learning Pipeline — RewardSignalBridge wiring (PR-10-01)
from runtime.memory.reward_signal_bridge import RewardSignalBridge
# Phase 11-A: AgentBanditSelector — reward-profile-informed agent selection (PR-11-A-02)
from runtime.autonomy.agent_bandit_selector import AgentBanditSelector
# Phase 14: ProposalEngine activation — strategy-driven LLM proposal path (PR-14-01)
from runtime.evolution.proposal_engine import ProposalEngine, ProposalRequest
from runtime.intelligence.proposal import Proposal
from runtime.market.market_fitness_integrator import MarketFitnessIntegrator
from runtime.autonomy.roadmap_amendment_engine import GovernanceViolation, MilestoneEntry, RoadmapAmendmentEngine
from runtime.governance.federation.federated_evidence_matrix import FederatedEvidenceMatrix
from security.ledger import journal

_LOG = logging.getLogger(__name__)

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
# Phase 14: _proposal_to_candidate bridge (PR-14-01)
# ---------------------------------------------------------------------------

def _proposal_to_candidate(
    proposal: "Proposal",
    *,
    epoch_id: str,
) -> Optional[MutationCandidate]:
    """Convert a ProposalEngine Proposal to a MutationCandidate for EvolutionLoop.

    Returns None for noop proposals (empty real_diff) — these are silently
    skipped. The bridge preserves all governance invariants: the returned
    MutationCandidate enters the same PopulationManager / GovernanceGate
    pipeline as any agent-originated candidate.

    Phase 14 / PR-14-01: initial implementation.
    Phase 14 / PR-14-02: live signal context population into ProposalRequest.
    """
    if not getattr(proposal, "real_diff", ""):
        return None  # noop proposals have no diff — skip silently

    projected = dict(getattr(proposal, "projected_impact", {}) or {})
    return MutationCandidate(
        mutation_id       = proposal.proposal_id,
        expected_gain     = float(getattr(proposal, "estimated_impact", 0.0)),
        risk_score        = float(projected.get("risk", 0.5)),
        complexity        = float(projected.get("complexity", 0.5)),
        coverage_delta    = float(projected.get("coverage_delta", 0.0)),
        agent_origin      = "proposal_engine",
        epoch_id          = epoch_id,
        python_content    = proposal.real_diff,
        operator_category = "llm_strategy",
        operator_version  = "14.0.0",
    )


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
    amendment_proposed:     bool       = False
    amendment_id:           Optional[str] = None
    # Phase 12 / Track 11-D: live market signal fields (PR-12-D-01)
    live_market_score:      float      = 0.0
    market_confidence:      float      = 0.0
    market_is_synthetic:    bool       = True
    # Phase 13 / Track 11-B: consecutive synthetic epoch count (PR-13-B-01)
    consecutive_synthetic_market_epochs: int = 0


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
        amendment_engine:  Optional[RoadmapAmendmentEngine] = None,
        federated_evidence_matrix: Optional[FederatedEvidenceMatrix] = None,
        craft_pattern_extractor: Optional[CraftPatternExtractor] = None,
        replay_interface: Optional[ContextReplayInterface] = None,
        bandit_selector: Optional[AgentBanditSelector] = None,
        market_integrator: Optional[MarketFitnessIntegrator] = None,
        proposal_engine: Optional[ProposalEngine] = None,
    ) -> None:
        self._api_key          = api_key
        self._generations      = generations
        self._simulate         = simulate_outcomes
        self._adaptor          = WeightAdaptor()
        self._landscape        = FitnessLandscape()
        self._manager          = PopulationManager()
        self._controller       = controller or ExploreExploitController()
        self._amendment_engine = amendment_engine or RoadmapAmendmentEngine()
        self._federated_evidence_matrix = federated_evidence_matrix
        self._router           = MutationRouteOptimizer()
        self._entropy_gate     = EntropyFastGate()
        self._chain_predecessor: str = self._load_chain_tip()
        self._epoch_count      = 0
        self._health_scores:   List[float] = []
        # CF-2 fix: track last epoch score for E/E mode selection (see run_epoch)
        self._last_epoch_health_score: float = 0.0
        # Phase 9: CraftPatternExtractor — wired lazily; ADAAD_SOULBOUND_KEY
        # must be set for the ledger to function. If the extractor is not
        # injected, pattern extraction is skipped silently (no crash).
        self._craft_extractor: Optional[CraftPatternExtractor] = craft_pattern_extractor
        # Phase 9: ContextReplayInterface — injects context_digest + explore_ratio
        # into CodebaseContext before Phase 1 (proposal). Optional; skipped silently
        # if not injected (ADAAD_SOULBOUND_KEY absent or no ledger entries yet).
        self._replay_interface: Optional[ContextReplayInterface] = replay_interface
        # Phase 11-A: AgentBanditSelector — reward-profile-informed agent selection
        # Wired lazily; if not injected, Phase 0d is skipped and Phase 0 falls back
        # to FitnessLandscape win-rate heuristic (backwards-compatible).
        self._bandit_selector: Optional[AgentBanditSelector] = bandit_selector
        # Phase 12 / Track 11-D: MarketFitnessIntegrator — live market signal
        # propagation into EpochResult. Optional; if not injected, market fields
        # default to synthetic fallback values (backwards-compatible).
        self._market_integrator: Optional[MarketFitnessIntegrator] = market_integrator
        # Phase 14: ProposalEngine — strategy-driven LLM proposal path. Optional;
        # if not injected, Phase 1e is skipped silently (backwards-compatible).
        # When injected, generate() runs alongside propose_from_all_agents and the
        # resulting Proposal is bridged to a MutationCandidate that enters the same
        # governed pipeline. Noop proposals (empty real_diff) are silently skipped.
        self._proposal_engine: Optional[ProposalEngine] = proposal_engine
        # Phase 10: RewardSignalBridge — wired lazily; if not injected, reward
        # signal ingestion is skipped silently (backwards-compatible).
        self._reward_bridge: Optional[RewardSignalBridge] = None

    def run_epoch(self, context: CodebaseContext) -> EpochResult:
        t_start  = time.monotonic()
        epoch_id = context.current_epoch_id
        self._epoch_count += 1

        # Phase 0: Strategy — bandit-aware agent recommendation (Phase 11-A)
        # AgentBanditSelector.recommend() is called first so the bandit_rec can
        # override FitnessLandscape.recommended_agent() when it is active and
        # confident. Exception-isolated: bandit failure falls back to landscape.
        _bandit_rec = None
        if self._bandit_selector is not None:
            try:
                _bandit_rec = self._bandit_selector.recommend(epoch_id=epoch_id)
            except Exception:  # noqa: BLE001
                pass

        _preferred = self._landscape.recommended_agent(bandit_rec=_bandit_rec)

        # Phase 0b: Mode selection
        # CF-2 fix: use internally tracked score from previous epoch.
        # Prior implementation called getattr(context, "prior_epoch_score", 0.0)
        # which always returned 0.0 (CodebaseContext has no such field), causing
        # the controller to never exceed EXPLOIT_TRIGGER_SCORE and lock in EXPLORE.
        is_plateau        = self._landscape.is_plateau()
        evolution_mode    = self._controller.select_mode(
            epoch_id=epoch_id,
            epoch_score=self._last_epoch_health_score,
            is_plateau=is_plateau,
        )

        # Phase 0c: Soulbound context replay injection (deferred PR-9-03)
        # Reads craft_pattern entries from the SoulboundLedger (written by Phase 5c)
        # and injects a context_digest annotation + adjusted explore_ratio into
        # CodebaseContext before the proposal agents are called in Phase 1.
        # Exception-isolated: replay failure never blocks proposal.
        # Constitutional invariant: GovernanceGate approval authority is unaffected.
        #
        # Phase 12 / Track 11-C: verify_replay_digest() called before applying
        # injection — if chain has advanced since the digest was computed, the
        # injection is skipped and a context_digest_mismatch.v1 event is emitted.
        if self._replay_interface is not None:
            try:
                replay_injection = self._replay_interface.build_injection(epoch_id=epoch_id)
                if not replay_injection.skipped and replay_injection.signal_quality_ok:
                    # Track 11-C: verify chain integrity before applying context
                    digest_ok = self._replay_interface.verify_replay_digest(
                        digest=replay_injection.context_digest,
                        epoch_id=epoch_id,
                    )
                    if digest_ok:
                        context.explore_ratio = replay_injection.adjusted_explore_ratio
                        context.soulbound_annotation = (
                            f"context_digest={replay_injection.context_digest} "
                            f"dominant_pattern={replay_injection.dominant_pattern} "
                            f"mean_elite_score={replay_injection.mean_elite_score:.4f} "
                            f"valid_entries={replay_injection.valid_entry_count}"
                        )
                    # else: injection skipped silently; mismatch event already emitted
            except Exception:  # noqa: BLE001
                pass

        # Phase 1: Propose
        all_proposals: List[MutationCandidate] = []
        try:
            proposal_batch = propose_from_all_agents(context, self._api_key)
            if isinstance(proposal_batch, dict):
                proposals_by_agent = proposal_batch
            else:
                proposals_by_agent = proposal_batch.proposals_by_agent
            for agent_proposals in proposals_by_agent.values():
                all_proposals.extend(agent_proposals)
        except Exception:
            pass

        # Phase 1e: ProposalEngine — strategy-driven LLM proposal (PR-14-01)
        # Runs alongside Phase 1; outputs bridged to MutationCandidate via
        # _proposal_to_candidate(). Noop proposals (empty real_diff) are silently
        # skipped. Full exception isolation: any failure is a no-op.
        if self._proposal_engine is not None:
            try:
                _engine_req = ProposalRequest(
                    cycle_id=epoch_id,
                    strategy_id="auto",
                    context={},   # Phase 14-02: live signals populated here
                )
                _engine_proposal = self._proposal_engine.generate(_engine_req)
                _engine_candidate = _proposal_to_candidate(_engine_proposal, epoch_id=epoch_id)
                if _engine_candidate is not None:
                    all_proposals.append(_engine_candidate)
            except Exception:  # noqa: BLE001
                pass  # engine failure must never halt the epoch

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

        # Phase 2m (Track 11-D): Live market signal integration — captures
        # IntegrationResult for EpochResult field population. Exception-isolated;
        # defaults to synthetic fallback values when integrator not injected.
        _market_live_score: float = 0.0
        _market_confidence: float = 0.0
        _market_is_synthetic: bool = True
        _market_consec_synthetic: int = 0
        if self._market_integrator is not None:
            try:
                _mkt_result = self._market_integrator.integrate(epoch_id=epoch_id)
                _market_live_score        = _mkt_result.live_market_score
                _market_confidence        = _mkt_result.confidence
                _market_is_synthetic      = _mkt_result.is_synthetic
                _market_consec_synthetic  = _mkt_result.consecutive_synthetic_epochs
            except Exception:  # noqa: BLE001
                pass  # synthetic defaults retained

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

        health_score = self._record_health_score(
            accepted_count=accepted_count,
            total_candidates=total_candidates,
        )
        # CF-2 fix: persist this epoch's health score so the NEXT epoch's
        # select_mode call receives a real signal instead of a stale 0.0.
        self._last_epoch_health_score = health_score

        # Phase 4: Adapt weights
        outcomes        = self._build_outcomes(all_scores)
        updated_weights = self._adaptor.adapt(outcomes)

        # CF-3 fix: always use simulate=True (heuristic mode).
        # Prior code passed simulate=self._simulate which is False in production.
        # When simulate=False, build_penalty_outcomes_from_scores sets
        # actually_risky=None for all outcomes (awaiting post-merge signal that
        # is never injected). PenaltyAdaptor._compute_risk_rate then returns 0.0
        # (no valid signals), driving both penalty weights to the constitutional
        # floor (0.05) after 116 epochs. The heuristic (simulate=True) is the
        # correct baseline signal until real post-merge injection is wired.
        penalty_outcomes = build_penalty_outcomes_from_scores(
            all_scores, simulate=True
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

        # Phase 5c: CraftPatternExtractor — tamper-evident reasoning pattern (PR-9-02)
        # Extracts per-agent scoring patterns from accepted batch and writes to
        # SoulboundLedger as a craft_pattern entry.  Skipped if:
        #   - _craft_extractor is not wired (ADAAD_SOULBOUND_KEY not set)
        #   - accepted_count < MIN_ACCEPTED_MUTATIONS_PER_EPOCH (sparse data)
        # Signal quality flag is set when PenaltyAdaptor velocity is near-zero (CF-3).
        if self._craft_extractor is not None:
            try:
                _vel_risk       = getattr(self._adaptor, "_penalty_adaptor", None)
                _vel_complexity = getattr(self._adaptor, "_penalty_adaptor", None)
                vel_risk        = float(getattr(_vel_risk,        "_velocity_risk",        0.0))
                vel_complexity  = float(getattr(_vel_complexity,  "_velocity_complexity",  0.0))
                self._craft_extractor.extract(
                    epoch_id=epoch_id,
                    accepted_scores=accepted,
                    weight_velocity_risk=vel_risk,
                    weight_velocity_complexity=vel_complexity,
                )
            except Exception:  # noqa: BLE001
                # Pattern extraction failure must never block the epoch
                pass

        # Phase 5d: RewardSignalBridge — reward learning pipeline ingestion (PR-10-01)
        # Converts all MutationScores (accepted + rejected) into reward observations,
        # aggregates a PromotionEvaluation, and writes a fitness_signal to SoulboundLedger.
        # Populates self._reward_bridge.recent_evaluations for PR-10-02 PolicyPromotionController.
        if self._reward_bridge is not None:
            try:
                self._reward_bridge.ingest(
                    epoch_id=epoch_id,
                    all_scores=all_scores,
                )
            except Exception:  # noqa: BLE001
                # Reward signal failure must never block the epoch
                pass
        mean_lineage_proximity = _compute_mean_lineage_proximity(accepted)

        # Phase 5e: AgentBanditSelector update (PR-11-A-02)
        # Update the bandit arm for the agent that recommended the proposals this epoch.
        # Reward signal: avg_reward from RewardSignalBridge if available, else
        # acceptance rate as a proxy (accepted_count / total_candidates).
        if self._bandit_selector is not None and _preferred is not None:
            try:
                if (
                    self._reward_bridge is not None
                    and self._reward_bridge.recent_evaluations
                ):
                    latest_eval = self._reward_bridge.recent_evaluations[-1]
                    reward_signal = float(getattr(latest_eval, "avg_reward", 0.0))
                else:
                    reward_signal = (
                        accepted_count / total_candidates
                        if total_candidates > 0 else 0.0
                    )
                self._bandit_selector.update(
                    agent=_preferred,
                    reward=reward_signal,
                    epoch_id=epoch_id,
                )
            except Exception:  # noqa: BLE001
                pass

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

        amendment_proposed, amendment_id = self._evaluate_m603_amendment_gates(
            epoch_id=epoch_id,
            health_score=health_score,
            checkpoint_digest=cp.chain_digest,
        )

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
            amendment_proposed     = amendment_proposed,
            amendment_id           = amendment_id,
            live_market_score      = _market_live_score,
            market_confidence      = _market_confidence,
            market_is_synthetic    = _market_is_synthetic,
            consecutive_synthetic_market_epochs = _market_consec_synthetic,
        )

    def _evaluate_m603_amendment_gates(
        self,
        *,
        epoch_id: str,
        health_score: float,
        checkpoint_digest: str,
    ) -> Tuple[bool, Optional[str]]:
        try:
            trigger_interval = _read_amendment_trigger_interval()
            if trigger_interval < 5:
                journal.append_tx(
                    tx_type="PHASE6_TRIGGER_INTERVAL_MISCONFIGURED",
                    payload={
                        "epoch_id": epoch_id,
                        "gate_id": "GATE-M603-06",
                        "amendment_trigger_interval": trigger_interval,
                    },
                )
                raise GovernanceViolation("PHASE6_TRIGGER_INTERVAL_MISCONFIGURED")

            if self._epoch_count % trigger_interval != 0:
                journal.append_tx(
                    tx_type="PHASE6_AMENDMENT_NOT_TRIGGERED",
                    payload={"epoch_id": epoch_id, "gate_id": "GATE-M603-01"},
                )
                return False, None

            if health_score < 0.80:
                journal.append_tx(
                    tx_type="PHASE6_HEALTH_GATE_FAIL",
                    payload={
                        "epoch_id": epoch_id,
                        "gate_id": "GATE-M603-02",
                        "health_score": health_score,
                    },
                )
                return False, None

            federation_enabled = os.getenv("ADAAD_FEDERATION_ENABLED", "false").strip().lower() == "true"
            divergence_count = 0
            if federation_enabled:
                matrix = self._federated_evidence_matrix or FederatedEvidenceMatrix(local_repo="local")
                divergence_count = matrix.divergence_count()
                if divergence_count != 0:
                    journal.append_tx(
                        tx_type="PHASE6_FEDERATION_DIVERGENCE_BLOCKS_AMENDMENT",
                        payload={
                            "epoch_id": epoch_id,
                            "gate_id": "GATE-M603-03",
                            "divergence_count": divergence_count,
                        },
                    )
                    return False, None

            prediction_accuracy = float(self._adaptor.prediction_accuracy)
            if prediction_accuracy <= 0.60:
                journal.append_tx(
                    tx_type="PHASE6_PREDICTION_ACCURACY_GATE_FAIL",
                    payload={
                        "epoch_id": epoch_id,
                        "gate_id": "GATE-M603-04",
                        "prediction_accuracy": prediction_accuracy,
                    },
                )
                return False, None

            pending = self._amendment_engine.list_pending()
            if pending:
                pending_id = pending[0].proposal_id
                _LOG.warning(
                    "PHASE6_AMENDMENT_STORM_BLOCKED epoch_id=%s pending_amendment_id=%s",
                    epoch_id,
                    pending_id,
                )
                journal.append_tx(
                    tx_type="PHASE6_AMENDMENT_STORM_BLOCKED",
                    payload={
                        "epoch_id": epoch_id,
                        "gate_id": "GATE-M603-05",
                        "pending_amendment_id": pending_id,
                    },
                )
                return False, None

            proposal = self._amendment_engine.propose(
                proposer_agent="ArchitectAgent",
                milestones=[
                    MilestoneEntry(
                        phase_id=6,
                        title="Autonomous Roadmap Self-Amendment",
                        status="active",
                        target_ver="3.1.0",
                        description="Evolution loop generated amendment proposal based on gate-qualified telemetry.",
                    )
                ],
                rationale=self._build_amendment_rationale(
                    epoch_id=epoch_id,
                    health_score=health_score,
                    prediction_accuracy=prediction_accuracy,
                ),
            )
            journal.append_tx(
                tx_type="roadmap_amendment_proposed",
                payload={
                    "epoch_id": epoch_id,
                    "proposal_id": proposal.proposal_id,
                    "lineage_chain_hash": proposal.lineage_chain_hash,
                    "prior_roadmap_hash": proposal.prior_roadmap_hash,
                    "checkpoint_digest": checkpoint_digest,
                    "gate_ids": [
                        "GATE-M603-01",
                        "GATE-M603-02",
                        "GATE-M603-03",
                        "GATE-M603-04",
                        "GATE-M603-05",
                        "GATE-M603-06",
                    ],
                },
            )
            return True, proposal.proposal_id
        except GovernanceViolation:
            raise
        except Exception:
            _LOG.warning("PHASE6_AMENDMENT_EVAL_ERROR epoch_id=%s", epoch_id, exc_info=True)
            journal.append_tx(
                tx_type="PHASE6_AMENDMENT_EVAL_ERROR",
                payload={
                    "epoch_id": epoch_id,
                    "traceback": traceback.format_exc(),
                },
            )
            return False, None

    def _build_amendment_rationale(
        self,
        *,
        epoch_id: str,
        health_score: float,
        prediction_accuracy: float,
    ) -> str:
        return (
            f"Epoch {epoch_id} passed all M6-03 prerequisite gates with health score "
            f"{health_score:.2f} and prediction accuracy {prediction_accuracy:.2f}. "
            "Proposing roadmap refinement to keep Phase 6 execution aligned with deterministic "
            "governance controls and milestone delivery cadence."
        )

    def _record_health_score(self, *, accepted_count: int, total_candidates: int) -> float:
        score = 1.0 if total_candidates == 0 else accepted_count / max(total_candidates, 1)
        self._health_scores.append(score)
        if len(self._health_scores) > 10:
            self._health_scores = self._health_scores[-10:]
        return round(sum(self._health_scores) / len(self._health_scores), 4)

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


def _read_amendment_trigger_interval() -> int:
    raw = os.getenv("ADAAD_AMENDMENT_TRIGGER_INTERVAL", os.getenv("ADAAD_ROADMAP_AMENDMENT_TRIGGER_INTERVAL", "10"))
    return int(raw)
