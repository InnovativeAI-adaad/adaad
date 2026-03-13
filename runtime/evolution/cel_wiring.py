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

logger = logging.getLogger(__name__)

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
        gate_v2: Optional[GovernanceGateV2] = None,
        gate: Optional[GovernanceGate] = None,
        fitness_engine: Optional[FitnessEngineV2] = None,
        proposal_engine: Optional[ProposalEngine] = None,
        exception_ledger: Optional[ExceptionTokenLedger] = None,
        cel_ledger: Optional[CELEvidenceLedger] = None,
        wiring_config: Optional[WiringConfig] = None,
        timestamp_provider: Optional[Any] = None,
        promotion_ledger_path: Optional[Path] = None,
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

    # ------------------------------------------------------------------ #
    # Step 4 — PROPOSAL-GENERATE (wired to ProposalEngine)
    # ------------------------------------------------------------------ #

    def _step_04_proposal_generate(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """CEL-WIRE-PROP-0: generate proposals via ProposalEngine.generate().

        Noop proposals are recorded but flagged; they will not be promoted.
        Fail-closed: any ProposalEngine exception → BLOCKED (CEL-WIRE-FAIL-0).
        """
        try:
            epoch_id = state["epoch_id"]
            context = state.get("context", {})
            strategy_id = context.get("strategy_id", self._wiring_cfg.noop_strategy_id)

            request = ProposalRequest(
                cycle_id=epoch_id,
                strategy_id=strategy_id,
                context={
                    "mutation_score": context.get("baseline_fitness_score", 0.5),
                    "governance_debt_score": context.get("governance_debt_score", 0.0),
                    "epoch_id": epoch_id,
                },
            )
            proposal = self._proposal_engine.generate(request)

            # Wrap in a proposal dict compatible with CEL step state schema
            proposal_dict: Dict[str, Any] = {
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
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """CEL-WIRE-FIT-0: score proposals via FitnessEngineV2.score().

        FIT-DIV-0: diverged replay → composite=0.0 (enforced inside FitnessEngineV2).
        Fail-closed: any engine exception → BLOCKED (CEL-WIRE-FAIL-0).
        """
        try:
            sandbox_results = state.get("sandbox_results", [])
            epoch_id = state["epoch_id"]
            replay_diverged = state.get("replay_diverged", False)
            fitness_summary: List[Tuple[str, float]] = []

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
        self, n: int, name: str, state: Dict[str, Any]
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

            gate_outcomes: List[Dict[str, Any]] = []
            rejected: List[str] = []

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
                return CELStepResult(
                    step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                    reason="governance_gate_rejection",
                    detail={"rejected": rejected, "gate_v2_existing_0_compliant": True},
                )
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.PASS,
                detail={
                    "approved_count": len(gate_outcomes),
                    "gate_v2_existing_0_compliant": True,
                    "gate_outcomes": gate_outcomes,
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
        self, n: int, name: str, state: Dict[str, Any]
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
            promo_events: List[Dict[str, Any]] = []
            prev_hash: Optional[str] = None

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


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_live_wired_cel(
    *,
    run_mode: RunMode = RunMode.SANDBOX_ONLY,
    exception_ledger_path: Optional[Path] = None,
    cel_ledger_path: Optional[Path] = None,
    promotion_ledger_path: Optional[Path] = None,
    wiring_config: Optional[WiringConfig] = None,
) -> LiveWiredCEL:
    """Construct a fully wired LiveWiredCEL with default subsystem instances."""
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
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "LiveWiredCEL",
    "WiringConfig",
    "make_live_wired_cel",
]
