# SPDX-License-Identifier: Apache-2.0
"""Phase 65 — CEL Wiring Adapter.

Connects ConstitutionalEvolutionLoop to the live ADAAD runtime:
  - Step 4  → ProposalEngine.generate()
  - Step 8  → FitnessEngineV2.score()
  - Step 10 → GovernanceGate.approve_mutation()  (GATE-V2-EXISTING-0)
  - Step 12 → create_promotion_event()            (LIVE mode only)

Constitutional invariants:
  CEL-WIRE-PROP-0   ProposalEngine is called exactly once per epoch in Step 4;
                    noop proposals are recorded but not promoted.
  CEL-WIRE-FIT-0    FitnessEngineV2.score() called for every sandbox-succeeded proposal;
                    FIT-DIV-0 respected (diverged replay → composite=0.0).
  CEL-WIRE-GATE-0   GovernanceGate.approve_mutation() called in Step 10 for every
                    V2-approved proposal; GATE-V2-EXISTING-0 never bypassed.
  CEL-WIRE-PROMO-0  create_promotion_event() called only in LIVE mode (Step 12);
                    SANDBOX_ONLY mode writes no promotion events.
  CEL-WIRE-FAIL-0   Any live-subsystem failure is caught with WARNING log;
                    the step records BLOCKED; the epoch halts (CEL-BLOCK-0).
                    No exception propagates from a wired step.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from runtime.evolution.constitutional_evolution_loop import (
    CELEvidenceLedger,
    CELStepResult,
    ConstitutionalEvolutionLoop,
    EpochCELResult,
    RunMode,
    StepOutcome,
)
from runtime.evolution.fitness_v2 import (
    FitnessConfig,
    FitnessContext,
    FitnessEngineV2,
    FitnessScores,
    ReplayResult,
)
from runtime.evolution.proposal_engine import ProposalEngine, ProposalRequest
from runtime.evolution.promotion_events import create_promotion_event
from runtime.evolution.promotion_state_machine import PromotionState
from runtime.governance.exception_tokens import ExceptionTokenLedger
from runtime.governance.gate import GovernanceGate, GateAxisResult
from runtime.governance.gate_v2 import GovernanceGateV2
from runtime.innovations import ADAADInnovationEngine, GovernancePlugin
from runtime.innovations_wiring import (
    record_personality_impact,
    run_gplugins,
    run_self_reflection,
    run_vision_forecast,
    select_agent_personality,
)

logger = logging.getLogger(__name__)

# Lazy bus import — avoids circular dependency at module load time
def _emit_epoch_start(epoch_id: str, run_mode: str) -> None:
    try:
        from runtime.innovations_bus import emit_epoch_start as _e  # noqa: PLC0415
        _e(epoch_id, run_mode)
    except Exception:  # noqa: BLE001
        pass

def _emit_epoch_end(epoch_id: str, outcome: str, succeeded: int, attempted: int) -> None:
    try:
        from runtime.innovations_bus import emit_epoch_end as _e  # noqa: PLC0415
        _e(epoch_id, outcome, succeeded, attempted)
    except Exception:  # noqa: BLE001
        pass

def _emit_cel_step(epoch_id: str, step_number: int, step_name: str, outcome: str, detail: dict) -> None:
    try:
        from runtime.innovations_bus import emit_cel_step as _e  # noqa: PLC0415
        _e(epoch_id, step_number, step_name, outcome, detail)
    except Exception:  # noqa: BLE001
        pass

def _emit_story_arc_from_state(state: dict) -> None:
    try:
        from runtime.innovations_bus import emit_story_arc as _e  # noqa: PLC0415
        epoch_id = state.get("epoch_id", "")
        personality = state.get("active_personality", {})
        agent = personality.get("agent_id", "system")
        succeeded = state.get("mutations_succeeded", ())
        result = "promoted" if succeeded else "blocked"
        _e(epoch_id, agent, result, title=f"Epoch {epoch_id}")
    except Exception:  # noqa: BLE001
        pass

# ---------------------------------------------------------------------------
# WiringConfig
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WiringConfig:
    """Runtime configuration for the Phase 65 CEL wiring layer."""
    policy_version: str = "v8.7.0"
    actor_id: str       = "ArchitectAgent"
    actor_type: str     = "autonomous_agent"
    noop_strategy_id: str = "s1"  # STRATEGY_TAXONOMY alias for 'fixed'


# ---------------------------------------------------------------------------
# LiveWiredCEL — ConstitutionalEvolutionLoop with all steps wired to live subsystems
# ---------------------------------------------------------------------------

class LiveWiredCEL(ConstitutionalEvolutionLoop):
    """Phase 65: ConstitutionalEvolutionLoop with live subsystem wiring.

    Overrides Steps 4, 8, 10, and 12 to call real subsystems.
    All other steps inherit from the base CEL implementation unchanged.

    CEL-WIRE-FAIL-0: every wired step is wrapped in try/except; any failure
    produces StepOutcome.BLOCKED and halts the epoch. Never propagates.
    """

    def __init__(
        self,
        *,
        run_mode: RunMode = RunMode.SANDBOX_ONLY,
        gate_v2: GovernanceGateV2 | None = None,
        gate: GovernanceGate | None = None,
        fitness_engine: FitnessEngineV2 | None = None,
        proposal_engine: ProposalEngine | None = None,
        exception_ledger: ExceptionTokenLedger | None = None,
        cel_ledger: CELEvidenceLedger | None = None,
        wiring_config: WiringConfig | None = None,
        timestamp_provider: Any | None = None,
        promotion_ledger_path: Path | None = None,
        # Phase 67 — Innovations wiring (all optional; no-ops when absent)
        innovations_engine: ADAADInnovationEngine | None = None,
        gplugins: list[GovernancePlugin | None] = None,
        epoch_seq: int = 0,
    ) -> None:
        super().__init__(
            run_mode=run_mode,
            gate_v2=gate_v2,
            exception_ledger=exception_ledger,
            cel_ledger=cel_ledger,
            timestamp_provider=timestamp_provider,
        )
        self._gate = gate or GovernanceGate()
        self._fitness_engine = fitness_engine or FitnessEngineV2(
            config=FitnessConfig.default()
        )
        self._proposal_engine = proposal_engine or ProposalEngine()
        self._wiring_cfg = wiring_config or WiringConfig()
        self._promo_ledger_path = promotion_ledger_path or Path(
            os.getenv("ADAAD_PROMOTION_LEDGER", "data/promotion_events.jsonl")
        )
        # Phase 67 — stored for injection into step overrides
        self._innovations_engine: ADAADInnovationEngine | None = innovations_engine
        self._gplugins: list[GovernancePlugin] = list(gplugins or [])
        self._epoch_seq: int = epoch_seq

    # ------------------------------------------------------------------ #
    # Step 4 — PROPOSAL-GENERATE (wired to ProposalEngine)
    # ------------------------------------------------------------------ #

    def _step_04_proposal_generate(
        self, n: int, name: str, state: dict[str, Any]
    ) -> CELStepResult:
        """CEL-WIRE-PROP-0: generate proposals via ProposalEngine.generate().

        Phase 67 additions (all fail-safe per CEL-WIRE-FAIL-0):
        - INNOV-VISION-0: Vision Mode forecast injected into proposal context.
        - INNOV-PERSONA-0: Deterministic personality selection injected into context.

        Phase 75 addition (SEED-CEL-HUMAN-0):
        - If state["context"]["seed_proposal_request"] is present, the
          seed-derived ProposalRequest is used in place of the default
          auto-generated request.  Falls back to default if absent.

        Noop proposals are recorded but flagged; they will not be promoted.
        Fail-closed: any ProposalEngine exception → BLOCKED (CEL-WIRE-FAIL-0).
        """
        try:
            epoch_id = state["epoch_id"]
            context = state.get("context", {})
            strategy_id = context.get("strategy_id", self._wiring_cfg.noop_strategy_id)

            # ---- Phase 67: Vision Mode (INNOV-VISION-0) ------------------
            vision_detail: dict[str, Any] = {}
            if self._innovations_engine is not None:
                projection = run_vision_forecast(self._innovations_engine, state)
                if projection is not None:
                    state["vision_projection"] = {
                        "horizon_epochs": projection.horizon_epochs,
                        "trajectory_score": projection.trajectory_score,
                        "projected_capabilities": list(projection.projected_capabilities),
                        "dead_end_paths": list(projection.dead_end_paths),
                    }
                    vision_detail = state["vision_projection"]

            # ---- Phase 67: Personality selection (INNOV-PERSONA-0) -------
            personality_detail: dict[str, Any] = {}
            if self._innovations_engine is not None:
                personality = select_agent_personality(
                    self._innovations_engine, epoch_id, strategy_id=strategy_id
                )
                if personality is not None:
                    state["active_personality"] = {
                        "agent_id": personality.agent_id,
                        "philosophy": personality.philosophy,
                        "vector": list(personality.vector),
                    }
                    personality_detail = state["active_personality"]
                    # Inject philosophy into proposal context so ProposalEngine
                    # may surface it in strategy metadata.
                    context = dict(context)
                    context["mutation_philosophy"] = personality.philosophy
                    context["active_personality_agent"] = personality.agent_id

            # Phase 75 — SEED-CEL-HUMAN-0: prefer seed-derived request if present
            try:
                from runtime.seed_cel_injector import resolve_step4_request  # noqa: PLC0415
                request = resolve_step4_request(
                    state={**state, "context": context},
                    default_cycle_id=epoch_id,
                    default_strategy_id=strategy_id,
                )
            except Exception:  # noqa: BLE001 — CEL-WIRE-FAIL-0: fall back to default
                request = ProposalRequest(
                    cycle_id=epoch_id,
                    strategy_id=strategy_id,
                    context={
                        "mutation_score": context.get("baseline_fitness_score", 0.5),
                        "governance_debt_score": context.get("governance_debt_score", 0.0),
                        "epoch_id": epoch_id,
                        "mutation_philosophy": context.get("mutation_philosophy", ""),
                        "active_personality_agent": context.get("active_personality_agent", ""),
                    },
                )

            proposal = self._proposal_engine.generate(request)

            proposal_dict: dict[str, Any] = {
                "mutation_id": proposal.proposal_id,
                "after_source": context.get(
                    "after_source",
                    f"# proposal: {proposal.title}\ndef noop(): pass\n",
                ),
                "before_source": context.get("before_source", None),
                "is_noop": "noop" in proposal.proposal_id.lower(),
                "estimated_impact": proposal.estimated_impact,
                "title": proposal.title,
            }

            proposals = [proposal_dict]
            state["proposals"] = proposals
            state["mutations_attempted"] = tuple(p["mutation_id"] for p in proposals)
            state["_live_proposals"] = proposals  # tag for Step 12

            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.PASS,
                detail={
                    "proposal_count": len(proposals),
                    "is_noop": proposal_dict["is_noop"],
                    "strategy_id": strategy_id,
                    "proposal_id": proposal.proposal_id,
                    "vision_projection": vision_detail,
                    "active_personality": personality_detail,
                },
            )
        except Exception as exc:  # noqa: BLE001 — CEL-WIRE-FAIL-0
            logger.warning("CEL Step 4 ProposalEngine failure: %s", exc)
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                reason="proposal_engine_failure",
                detail={"exception": str(exc)},
            )

    # ------------------------------------------------------------------ #
    # Step 8 — FITNESS-SCORE (wired to FitnessEngineV2)
    # ------------------------------------------------------------------ #

    def _step_08_fitness_score(
        self, n: int, name: str, state: dict[str, Any]
    ) -> CELStepResult:
        """CEL-WIRE-FIT-0: score proposals via FitnessEngineV2.score().

        FIT-DIV-0: diverged replay → composite=0.0 (enforced inside FitnessEngineV2).
        Fail-closed: any engine exception → BLOCKED (CEL-WIRE-FAIL-0).
        """
        try:
            sandbox_results = state.get("sandbox_results", [])
            epoch_id = state["epoch_id"]
            replay_diverged = state.get("replay_diverged", False)
            fitness_summary: list[tuple[str, float]] = []

            for sr in sandbox_results:
                mid = sr.get("mutation_id", "unknown")
                sandbox_ok = bool(sr.get("sandbox_ok", False))

                fit_ctx = FitnessContext(
                    epoch_id=epoch_id,
                    test_fitness=1.0 if sandbox_ok else 0.0,
                    complexity_fitness=0.7,
                    performance_fitness=0.65,
                    governance_compliance=1.0 if sandbox_ok else 0.0,
                    architectural_fitness=0.5,
                    determinism_fitness=1.0,
                    net_node_additions=0,
                    replay_result=ReplayResult(
                        diverged=replay_diverged,
                        divergence_class="sandbox_div" if replay_diverged else "none",
                    ),
                    code_intel_model_hash=state.get("model_hash_before", ""),
                    epoch_memory_snapshot="",
                    policy_config_hash="",
                )
                scores: FitnessScores = self._fitness_engine.score(fit_ctx)
                fitness_summary.append((mid, scores.composite_score))

            state["fitness_summary"] = tuple(fitness_summary)
            state["mutations_succeeded"] = tuple(
                mid for mid, score in fitness_summary if score > 0.5
            )

            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.PASS,
                detail={
                    "scored_count": len(fitness_summary),
                    "succeeded_count": len(state["mutations_succeeded"]),
                    "fitness_summary": [
                        {"mutation_id": mid, "composite": score}
                        for mid, score in fitness_summary
                    ],
                },
            )
        except Exception as exc:  # noqa: BLE001 — CEL-WIRE-FAIL-0
            logger.warning("CEL Step 8 FitnessEngineV2 failure: %s", exc)
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                reason="fitness_engine_failure",
                detail={"exception": str(exc)},
            )

    # ------------------------------------------------------------------ #
    # Step 10 — GOVERNANCE-GATE (wired to GovernanceGate, GATE-V2-EXISTING-0)
    # ------------------------------------------------------------------ #

    def _step_10_governance_gate(
        self, n: int, name: str, state: dict[str, Any]
    ) -> CELStepResult:
        """CEL-WIRE-GATE-0: call GovernanceGate.approve_mutation() for every V2-approved proposal.

        GATE-V2-EXISTING-0: this step always runs after Step 9; never skipped.
        Any GovernanceGate rejection → BLOCKED (CEL-BLOCK-0 + CEL-WIRE-FAIL-0).
        """
        try:
            mutations_succeeded = list(state.get("mutations_succeeded", ()))
            v2_decisions = {
                d["mutation_id"]: d
                for d in state.get("v2_gate_decisions", [])
            }

            gate_outcomes: list[dict[str, Any]] = []
            rejected: list[str] = []

            for mid in mutations_succeeded:
                v2 = v2_decisions.get(mid, {})
                # Build axis results from V2 rule results
                axis_results = [
                    GateAxisResult(
                        axis="governance_gate_v2",
                        rule_id=r.get("rule_id", "unknown"),
                        ok=bool(r.get("passed", True)),
                        reason=r.get("reason", "ok"),
                    )
                    for r in v2.get("rule_results", [])
                ]

                decision = self._gate.approve_mutation(
                    mutation_id=mid,
                    trust_mode="standard",
                    axis_results=axis_results if axis_results else None,
                    mutation_payload={"epoch_id": state["epoch_id"]},
                    mutation_context={},
                    human_override=False,
                )
                gate_outcomes.append({
                    "mutation_id": mid,
                    "approved": decision.approved,
                    "decision": decision.decision,
                    "decision_id": decision.decision_id,
                })
                if not decision.approved:
                    rejected.append(mid)

            state["gate_outcomes"] = gate_outcomes
            # Remove rejected from succeeded
            state["mutations_succeeded"] = tuple(
                mid for mid in mutations_succeeded if mid not in rejected
            )

            if rejected:
                personality_impact = record_personality_impact(epoch_id=state["epoch_id"], state=state)
                return CELStepResult(
                    step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                    reason="governance_gate_rejection",
                    detail={
                        "rejected": rejected,
                        "gate_v2_existing_0_compliant": True,
                        "personality_impact": personality_impact,
                    },
                )

            # ---- Phase 67: Governance Plugins (GPLUGIN-BLOCK-0) ---------
            gplugin_outcomes: list[dict[str, Any]] = []
            gplugin_blocked: list[str] = []
            if self._innovations_engine is not None and self._gplugins:
                approved_mutations = list(state.get("mutations_succeeded", ()))
                proposals_by_id = {
                    p["mutation_id"]: p
                    for p in state.get("proposals", [])
                }
                for mid in approved_mutations:
                    mutation_payload = proposals_by_id.get(mid, {"mutation_id": mid})
                    plugin_results = run_gplugins(
                        self._innovations_engine,
                        mutation_payload,
                        self._gplugins,
                    )
                    gplugin_outcomes.append({"mutation_id": mid, "results": plugin_results})
                    failed_plugins = [r for r in plugin_results if not r["passed"]]
                    if failed_plugins:
                        gplugin_blocked.append(mid)
                        logger.warning(
                            "CEL Step 10 G-plugin block mutation=%s plugins=%s",
                            mid,
                            [r["plugin_id"] for r in failed_plugins],
                        )

                state["gplugin_outcomes"] = gplugin_outcomes
                if gplugin_blocked:
                    state["mutations_succeeded"] = tuple(
                        mid for mid in state["mutations_succeeded"]
                        if mid not in gplugin_blocked
                    )
                    personality_impact = record_personality_impact(epoch_id=state["epoch_id"], state=state)
                    return CELStepResult(
                        step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                        reason="gplugin_rejection",
                        detail={
                            "blocked_by_gplugin": gplugin_blocked,
                            "gplugin_outcomes": gplugin_outcomes,
                            "gate_v2_existing_0_compliant": True,
                            "personality_impact": personality_impact,
                        },
                    )

            personality_impact = record_personality_impact(epoch_id=state["epoch_id"], state=state)
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.PASS,
                detail={
                    "approved_count": len(gate_outcomes),
                    "gate_v2_existing_0_compliant": True,
                    "gate_outcomes": gate_outcomes,
                    "gplugin_outcomes": gplugin_outcomes,
                    "personality_impact": personality_impact,
                },
            )
        except Exception as exc:  # noqa: BLE001 — CEL-WIRE-FAIL-0
            logger.warning("CEL Step 10 GovernanceGate failure: %s", exc)
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                reason="governance_gate_exception",
                detail={"exception": str(exc), "gate_v2_existing_0_compliant": True},
            )

    # ------------------------------------------------------------------ #
    # Step 12 — PROMOTION-DECISION (wired to create_promotion_event)
    # ------------------------------------------------------------------ #

    def _step_12_promotion_decision(
        self, n: int, name: str, state: dict[str, Any]
    ) -> CELStepResult:
        """CEL-WIRE-PROMO-0: write PromotionEvent for each approved mutation.

        CEL-DRYRUN-0: suppressed in SANDBOX_ONLY — no ledger writes, no events.
        Fail-closed: any failure → BLOCKED (CEL-WIRE-FAIL-0).
        """
        if self._dry_run:
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.SKIPPED,
                reason="SANDBOX_ONLY_mode",
                detail={"promoted_count": 0},
            )

        try:
            mutations_succeeded = list(state.get("mutations_succeeded", ()))
            epoch_id = state["epoch_id"]
            promo_events: list[dict[str, Any]] = []
            prev_hash: str | None = None

            for mid in mutations_succeeded:
                event = create_promotion_event(
                    mutation_id=mid,
                    epoch_id=epoch_id,
                    from_state=PromotionState.PROPOSED,
                    to_state=PromotionState.ACTIVATED,
                    actor_type=self._wiring_cfg.actor_type,
                    actor_id=self._wiring_cfg.actor_id,
                    policy_version=self._wiring_cfg.policy_version,
                    payload={
                        "epoch_evidence_hash": state.get("epoch_evidence_hash", ""),
                        "fitness_composite": next(
                            (s for m, s in state.get("fitness_summary", ()) if m == mid),
                            0.0,
                        ),
                    },
                    prev_event_hash=prev_hash,
                )
                promo_events.append(event)
                prev_hash = event.get("event_hash")

            # Append to promotion ledger
            if promo_events:
                self._promo_ledger_path.parent.mkdir(parents=True, exist_ok=True)
                with self._promo_ledger_path.open("a", encoding="utf-8") as f:
                    for ev in promo_events:
                        f.write(json.dumps(ev, sort_keys=True, default=str) + "\n")

            state["promotion_events"] = promo_events
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.PASS,
                detail={"promoted_count": len(promo_events)},
            )
        except Exception as exc:  # noqa: BLE001 — CEL-WIRE-FAIL-0
            logger.warning("CEL Step 12 PromotionEvent failure: %s", exc)
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                reason="promotion_event_failure",
                detail={"exception": str(exc)},
            )


    # ------------------------------------------------------------------ #
    # Step 14 — STATE-ADVANCE (extended with self-reflection)
    # ------------------------------------------------------------------ #

    def _step_14_state_advance(
        self, n: int, name: str, state: dict[str, Any]
    ) -> CELStepResult:
        """Phase 67/70 extension of STATE-ADVANCE.

        Phase 67: self-reflection on cadence (INNOV-REFLECT-0).
        Phase 70: emit story_arc + cel_step frames to innovations bus.
        """
        base_result = super()._step_14_state_advance(n, name, state)

        # Phase 67 — Self-reflection (INNOV-REFLECT-0) — fail-safe
        self._epoch_seq += 1
        if self._innovations_engine is not None:
            run_self_reflection(
                self._innovations_engine,
                epoch_id=state.get("epoch_id", ""),
                epoch_seq=self._epoch_seq,
                state=state,
            )

        # Phase 70 — Emit story arc for this epoch
        _emit_story_arc_from_state(state)
        # Phase 70 — Emit cel_step frame for step 14
        _emit_cel_step(
            state.get("epoch_id", ""),
            n, name,
            base_result.outcome.value if hasattr(base_result.outcome, "value") else str(base_result.outcome),
            dict(base_result.detail or {}),
        )

        # Merge reflection_report into step detail if produced
        reflection = state.get("reflection_report")
        if reflection is not None:
            merged_detail = dict(base_result.detail or {})
            merged_detail["reflection_report"] = reflection
            return CELStepResult(
                step_number=base_result.step_number,
                step_name=base_result.step_name,
                outcome=base_result.outcome,
                reason=base_result.reason,
                detail=merged_detail,
            )
        return base_result

    def run_epoch(
        self,
        *,
        epoch_id: str | None = None,
        context: dict[str, Any | None] = None,
    ):
        """Phase 70: emit epoch_start/end frames around the base run_epoch.

        Phase 89 — CEL-LIVE-0:
        If ADAAD_ANTHROPIC_API_KEY is present and non-empty, the run_mode
        MUST be RunMode.LIVE.  Running in SANDBOX_ONLY with a live key is a
        constitutional violation — the system must not produce sandbox results
        when it has the capability to run live proposals.
        """
        import uuid  # noqa: PLC0415
        # ── CEL-LIVE-0 enforcement ────────────────────────────────────────
        api_key = os.getenv("ADAAD_ANTHROPIC_API_KEY", "").strip()
        if api_key and self._run_mode is RunMode.SANDBOX_ONLY:
            raise RuntimeError(
                "CEL-LIVE-0 VIOLATION: ADAAD_ANTHROPIC_API_KEY is set but "
                "LiveWiredCEL is running in RunMode.SANDBOX_ONLY.  "
                "Use make_live_wired_cel() which auto-upgrades to RunMode.LIVE "
                "when the key is present, or construct LiveWiredCEL with "
                "run_mode=RunMode.LIVE explicitly."
            )
        # ── end CEL-LIVE-0 ───────────────────────────────────────────────
        eid = epoch_id or str(uuid.uuid4())
        run_mode_str = self._run_mode.value if hasattr(self._run_mode, "value") else str(self._run_mode)
        _emit_epoch_start(eid, run_mode_str)
        result = super().run_epoch(epoch_id=eid, context=context)
        attempted = len(getattr(result, "mutations_attempted", ()) or ())
        succeeded = len(getattr(result, "mutations_succeeded", ()) or ())
        outcome = "pass" if getattr(result, "all_passed", False) else "blocked"
        _emit_epoch_end(eid, outcome, succeeded, attempted)
        return result


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_live_wired_cel(
    *,
    run_mode: RunMode = RunMode.SANDBOX_ONLY,
    exception_ledger_path: Path | None = None,
    cel_ledger_path: Path | None = None,
    promotion_ledger_path: Path | None = None,
    wiring_config: WiringConfig | None = None,
) -> LiveWiredCEL:
    """Construct a fully wired LiveWiredCEL with default subsystem instances.

    Phase 89 — CEL-LIVE-0:
    If ADAAD_ANTHROPIC_API_KEY is present and non-empty, *run_mode* is
    automatically upgraded to RunMode.LIVE regardless of the caller-supplied
    value.  This ensures that a system with a valid key never silently runs
    in sandbox mode.  The upgrade is logged at INFO level.
    """
    # ── CEL-LIVE-0: auto-upgrade ──────────────────────────────────────────
    import logging as _log  # noqa: PLC0415
    _factory_log = _log.getLogger(__name__)
    api_key = os.getenv("ADAAD_ANTHROPIC_API_KEY", "").strip()
    if api_key and run_mode is RunMode.SANDBOX_ONLY:
        _factory_log.info(
            "make_live_wired_cel: ADAAD_ANTHROPIC_API_KEY detected — "
            "upgrading run_mode SANDBOX_ONLY → LIVE (CEL-LIVE-0)"
        )
        run_mode = RunMode.LIVE
    # ── end auto-upgrade ─────────────────────────────────────────────────
    exc_ledger = ExceptionTokenLedger(
        ledger_path=exception_ledger_path or Path(
            os.getenv("ADAAD_EXCEPTION_LEDGER", "data/exception_tokens.jsonl")
        )
    )
    cel_ledger = CELEvidenceLedger(
        ledger_path=cel_ledger_path or Path(
            os.getenv("ADAAD_EVOLUTION_LEDGER", "data/evolution_ledger.jsonl")
        )
    )
    gate_v2 = GovernanceGateV2(exception_ledger=exc_ledger)

    return LiveWiredCEL(
        run_mode=run_mode,
        gate_v2=gate_v2,
        exception_ledger=exc_ledger,
        cel_ledger=cel_ledger,
        promotion_ledger_path=promotion_ledger_path,
        wiring_config=wiring_config or WiringConfig(),
    )


# ---------------------------------------------------------------------------
# Phase 65: Environment-flag helpers for EvolutionLoop routing
# ---------------------------------------------------------------------------

# Read once at import time; tests may reload module via importlib.
_CEL_ENABLED: bool = os.getenv("ADAAD_CEL_ENABLED", "false").lower() == "true"
_SANDBOX_ONLY: bool = os.getenv("ADAAD_SANDBOX_ONLY", "false").lower() == "true"


def is_cel_enabled() -> bool:
    """Return True when ADAAD_CEL_ENABLED=true in environment.

    This flag gates the EvolutionLoop.run_epoch() routing decision.
    Default: False — legacy loop is used unless explicitly opted in.
    """
    return os.getenv("ADAAD_CEL_ENABLED", "false").lower() == "true"


def assert_cel_enabled_or_raise() -> None:
    """Raise RuntimeError if CEL is not enabled.

    Called from EvolutionLoop._run_cel_epoch() as a guard; ensures
    the caller set ADAAD_CEL_ENABLED=true before attempting live execution.
    """
    if not is_cel_enabled():
        raise RuntimeError(
            "CEL is not enabled. Set ADAAD_CEL_ENABLED=true in environment "
            "to activate the Constitutional Evolution Loop."
        )


def build_cel(
    *,
    sandbox_only: bool | None = None,
    exception_ledger_path: Path | None = None,
    cel_ledger_path: Path | None = None,
    promotion_ledger_path: Path | None = None,
    wiring_config: WiringConfig | None = None,
) -> "LiveWiredCEL":
    """Build and return a fully wired LiveWiredCEL.

    Phase 65: sandbox_only defaults to ADAAD_SANDBOX_ONLY env var (false
    in production). Previously the CEL always defaulted to SANDBOX_ONLY.

    Args:
        sandbox_only: Override ADAAD_SANDBOX_ONLY env var if provided.
        exception_ledger_path: Path override for ExceptionTokenLedger.
        cel_ledger_path: Path override for CELEvidenceLedger.
        promotion_ledger_path: Path override for promotion events JSONL.
        wiring_config: WiringConfig override (policy version, actor id).

    Returns:
        LiveWiredCEL fully constructed and ready for epoch execution.
    """
    effective_sandbox = (
        os.getenv("ADAAD_SANDBOX_ONLY", "false").lower() == "true"
        if sandbox_only is None
        else sandbox_only
    )
    run_mode = RunMode.SANDBOX_ONLY if effective_sandbox else RunMode.LIVE

    cel = make_live_wired_cel(
        run_mode=run_mode,
        exception_ledger_path=exception_ledger_path,
        cel_ledger_path=cel_ledger_path,
        promotion_ledger_path=promotion_ledger_path,
        wiring_config=wiring_config,
    )

    mode_label = "SANDBOX_ONLY (dry-run)" if effective_sandbox else "LIVE (production)"
    logger.info(
        "build_cel: LiveWiredCEL constructed in %s mode. "
        "run_mode=%s sandbox_only=%s",
        mode_label, run_mode.value, effective_sandbox,
    )
    return cel


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "LiveWiredCEL",
    "WiringConfig",
    "WiringConfig",
    "make_live_wired_cel",
    "build_cel",
    "is_cel_enabled",
    "assert_cel_enabled_or_raise",
]
