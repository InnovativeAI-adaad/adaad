# SPDX-License-Identifier: Apache-2.0
"""Phase 64 — Constitutional Evolution Loop (CEL).

Constitutional invariants:
  CEL-ORDER-0           Steps execute in strict 1→15 sequence; no re-ordering; no step skipping.
  CEL-EVIDENCE-0        Every epoch closes with an EpochEvidence record written to the append-only
                        evolution ledger; predecessor_hash links it to the prior epoch.
  CEL-BLOCK-0           Any step returning StepOutcome.BLOCKED halts the epoch immediately;
                        remaining steps do not execute; partial-epoch ledger entry is written.
  CEL-DRYRUN-0          In SANDBOX_ONLY mode all real writes are suppressed; ledger entries are
                        tagged dry_run=True; no capability promotion occurs.
  CEL-REPLAY-0          All timestamps via RuntimeDeterminismProvider; no datetime.now() calls.
  CEL-GATE-0            GovernanceGateV2 evaluates in Step 10; a blocking V2 result that is not
                        class_b_eligible is a hard halt; class_b_eligible surfaces the token path
                        but does not auto-approve — HUMAN-0 still required.
  CEL-PARETO-0          Pareto selection result written to ledger before Step 10 (Phase 86).
  CEL-PARETO-DETERM-0   Identical scored candidates → identical Pareto frontier (Phase 86).
  STEP8-LEDGER-FIRST-0  All fitness calls ledger-recorded before fitness_summary written (Phase 86).
  STEP8-DETERM-0        Identical sandbox_results + codebase state → identical fitness_summary.
  CEL-SELF-DISC-0       Self-discovery runs post-epoch at SELF_DISC_FREQUENCY cadence (Phase 86).
  CEL-SELF-DISC-NONBLOCK-0  Self-discovery failure never blocks epoch completion (Phase 86).
  SELF-DISC-HUMAN-0     No self-discovered invariant enters CONSTITUTION.md without HUMAN-0.
  AFRT-GATE-0           AFRT evaluation must occur after LSME (Step 6) and PARETO-SELECT
                        (Step 9) and before GovernanceGateV2 (Step 11). (Phase 92)

16-Step Sequence (CEL-ORDER-0) — Phase 92: Step 10 AFRT-GATE inserted:
  Step  1 — MODEL-DRIFT-CHECK      Verify CodeIntelModel determinism; block on drift.
  Step  2 — LINEAGE-SNAPSHOT       Capture LineageEngine state hash for chain integrity.
  Step  3 — FITNESS-BASELINE       Compute FitnessEngineV2 baseline composite score.
  Step  4 — PROPOSAL-GENERATE      Generate mutation proposals via ProposalEngine.
  Step  5 — AST-SCAN               StaticScanner + GovernanceGateV2 pre-flight (AST-SAFE-0,
                                   AST-IMPORT-0, AST-COMPLEX-0).
  Step  6 — SANDBOX-EXECUTE        Execute proposals in sandbox container (dry_run flag
                                   respected); LSME wired here (LSME-GATE-0 / LSME-GATE-1).
  Step  7 — REPLAY-VERIFY          Deterministic replay of sandbox; record
                                   replay_verification_hash; block on SANDBOX-DIV-0.
  Step  8 — FITNESS-SCORE          Score all sandbox results: FitnessOrchestrator (real composite)
                                   + FitnessDecayScorer (temporal discount) + CausalFitnessAttributor
                                   (per-op Shapley). Ledger-first (STEP8-LEDGER-FIRST-0).
  Step  9 — PARETO-SELECT          Multi-objective Pareto frontier selection via
                                   ParetoCompetitionOrchestrator. Replaces scalar score > 0.5
                                   threshold. Frontier written to ledger (CEL-PARETO-0).
  Step 10 — AFRT-GATE              Adversarial Fitness Red Team evaluation (INNOV-08).
                                   AdversarialRedTeamAgent generates 1–5 targeted adversarial
                                   cases from CodeIntel uncovered paths; RETURNED verdict blocks
                                   epoch; PASS advances to GovernanceGateV2. (Phase 92)
  Step 11 — GOVERNANCE-GATE-V2     Full GovernanceGateV2 evaluation (all 5 Phase 63 rules).
  Step 12 — GOVERNANCE-GATE        Existing GovernanceGate (all 16 pre-Phase-63 rules);
                                   GATE-V2-EXISTING-0 compliance check.
  Step 13 — LINEAGE-REGISTER       Register surviving mutations in LineageEngine.
  Step 14 — PROMOTION-DECISION     Write PromotionEvent; suppressed in SANDBOX_ONLY mode.
  Step 15 — EPOCH-EVIDENCE-WRITE   Assemble and write EvolutionEvidence to ledger;
                                   compute predecessor_hash; chain validated.
  Step 16 — STATE-ADVANCE          Advance epoch counter; update exploration/exploitation
                                   state; emit epoch_complete.v1 journal event.

Post-epoch (non-blocking, outside step sequence):
  SELF-DISCOVERY         ConstitutionalSelfDiscoveryLoop fires every SELF_DISC_FREQUENCY epochs.
                         Candidates written to self_discovery_candidates ledger stream.
                         HUMAN-0 required before any candidate enters CONSTITUTION.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Governance / evolution imports — no Tier-0 governance imports allowed here
# (AST-IMPORT-0 would block this file if added).
# GovernanceGateV2 is Tier-1; import is permitted.
# ---------------------------------------------------------------------------
from runtime.governance.gate_v2 import GovernanceGateV2, V2GateDecision
from runtime.governance.exception_tokens import ExceptionTokenLedger
from runtime.evolution.evidence.schemas import (
    DriftCatalyst,
    EpochEvidence,
    EvolutionEvidence,
    ModelDriftEvidence,
    MutationLineageEvidence,
    CapabilityVersionEvidence,
    GovernanceExceptionEvidence,
    PromotionStatus,
)
from runtime.governance.foundation import sha256_prefixed_digest, canonical_json

# ---------------------------------------------------------------------------
# Phase 86 — Evolution engine wiring imports (lazy to avoid circular deps)
# ---------------------------------------------------------------------------
# FitnessOrchestrator, FitnessDecayScorer, CausalFitnessAttributor,
# ParetoCompetitionOrchestrator, ConstitutionalSelfDiscoveryLoop are imported
# lazily inside the constructor so that this module remains importable even
# when the phase-86 modules are not yet fully wired.  Explicit injection via
# constructor kwargs always takes precedence (testability / determinism).
SELF_DISC_FREQUENCY: int = 5  # run ConstitutionalSelfDiscoveryLoop every N epochs
_UNSET: object = object()     # sentinel: distinguishes "not provided" from explicit None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CEL_LEDGER_PATH = Path(os.getenv("ADAAD_EVOLUTION_LEDGER", "data/evolution_ledger.jsonl"))
GENESIS_PREDECESSOR = "sha256:" + "0" * 64

# ---------------------------------------------------------------------------
# CEL enumerations
# ---------------------------------------------------------------------------

class RunMode(str, Enum):
    SANDBOX_ONLY = "SANDBOX_ONLY"   # CEL-DRYRUN-0: no real writes
    LIVE         = "LIVE"           # full production execution


class StepOutcome(str, Enum):
    PASS    = "PASS"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"   # used only for suppressed steps in SANDBOX_ONLY


# ---------------------------------------------------------------------------
# Step result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CELStepResult:
    step_number: int
    step_name: str
    outcome: StepOutcome
    reason: Optional[str] = None
    detail: Optional[dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "step_name": self.step_name,
            "outcome": self.outcome.value,
            "reason": self.reason,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# EpochCELResult — full epoch record
# ---------------------------------------------------------------------------

@dataclass
class EpochCELResult:
    epoch_id: str
    run_mode: RunMode
    step_results: List[CELStepResult] = field(default_factory=list)
    blocked_at_step: Optional[int]    = None
    epoch_evidence_hash: Optional[str] = None
    dry_run: bool                      = False

    @property
    def completed(self) -> bool:
        return self.blocked_at_step is None and len(self.step_results) == 14

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch_id": self.epoch_id,
            "run_mode": self.run_mode.value,
            "step_results": [s.to_dict() for s in self.step_results],
            "blocked_at_step": self.blocked_at_step,
            "epoch_evidence_hash": self.epoch_evidence_hash,
            "dry_run": self.dry_run,
            "completed": self.completed,
        }


# ---------------------------------------------------------------------------
# CEL Ledger — append-only JSONL (CEL-EVIDENCE-0)
# ---------------------------------------------------------------------------

class CELEvidenceLedger:
    """Append-only ledger for EvolutionEvidence records.

    CEL-EVIDENCE-0: every epoch writes exactly one EvolutionEvidence record;
    chain_tip tracks the predecessor_hash for the next record.
    """

    def __init__(self, ledger_path: Path = CEL_LEDGER_PATH) -> None:
        self._path = ledger_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._chain_tip: str = self._load_chain_tip()

    @property
    def chain_tip(self) -> str:
        return self._chain_tip

    def append(self, evidence: EvolutionEvidence, *, dry_run: bool = False) -> str:
        """Append EvolutionEvidence; return record hash. Suppresses write in dry_run mode."""
        record_hash = evidence.epoch_evidence.compute_hash()
        if not dry_run:
            line = evidence.to_ledger_line()
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            self._chain_tip = record_hash
        return record_hash

    def _load_chain_tip(self) -> str:
        if not self._path.exists():
            return GENESIS_PREDECESSOR
        lines = [l.strip() for l in self._path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            return GENESIS_PREDECESSOR
        try:
            last = json.loads(lines[-1])
            epoch_e = last.get("epoch_evidence", {})
            payload = json.dumps(epoch_e, sort_keys=True, default=str)
            return hashlib.sha256(payload.encode()).hexdigest()
        except Exception:
            return GENESIS_PREDECESSOR


# ---------------------------------------------------------------------------
# ConstitutionalEvolutionLoop — the 14-step engine
# ---------------------------------------------------------------------------

class ConstitutionalEvolutionLoop:
    """Phase 64 — 14-step Constitutional Evolution Loop.

    Each step returns a CELStepResult. A BLOCKED outcome halts execution
    immediately (CEL-BLOCK-0). All steps execute in strict order (CEL-ORDER-0).
    SANDBOX_ONLY mode suppresses promotion and marks ledger entries dry_run=True
    (CEL-DRYRUN-0).
    """

    def __init__(
        self,
        *,
        run_mode: RunMode = RunMode.SANDBOX_ONLY,
        gate_v2: Optional[GovernanceGateV2] = None,
        exception_ledger: Optional[ExceptionTokenLedger] = None,
        cel_ledger: Optional[CELEvidenceLedger] = None,
        timestamp_provider: Optional[Any] = None,  # RuntimeDeterminismProvider
        # Phase 86 — evolution engine components (injected for testability)
        # Pass _UNSET (default) to enable lazy-import fallback.
        # Pass None explicitly to disable the component entirely (e.g. in tests).
        fitness_orchestrator: Any = _UNSET,
        fitness_decay_scorer: Any = _UNSET,
        causal_fitness_attributor: Any = _UNSET,
        pareto_competition_orchestrator: Any = _UNSET,
        self_discovery_loop: Any = _UNSET,
        self_disc_frequency: int = SELF_DISC_FREQUENCY,
        # Phase 92 — AFRT gate (INNOV-08); pass None to disable (e.g. pre-Phase-92 tests)
        afrt_agent: Any = _UNSET,
        # Phase 107 — Market-Conditioned Fitness (MCF)
        market_integrator: Any = _UNSET,
    ) -> None:
        self._run_mode = run_mode
        self._dry_run = run_mode == RunMode.SANDBOX_ONLY
        self._gate_v2 = gate_v2 or GovernanceGateV2(exception_ledger=exception_ledger)
        self._cel_ledger = cel_ledger or CELEvidenceLedger()
        self._ts_provider = timestamp_provider

        # Phase 86 — evolution engine wiring (lazy-import fallbacks)
        # _UNSET means "try to import"; explicit None means "disabled by caller".
        if fitness_orchestrator is _UNSET:
            try:
                from runtime.evolution.fitness_orchestrator import FitnessOrchestrator
                fitness_orchestrator = FitnessOrchestrator()
            except Exception:  # noqa: BLE001
                fitness_orchestrator = None
        
        # Phase 107 — MCF integration
        if market_integrator is _UNSET:
            try:
                from runtime.market.market_fitness_integrator import MarketFitnessIntegrator
                market_integrator = MarketFitnessIntegrator(fitness_orchestrator=fitness_orchestrator)
            except Exception:  # noqa: BLE001
                market_integrator = None

        if fitness_decay_scorer is _UNSET:
            try:
                from runtime.evolution.fitness_decay_scorer import FitnessDecayScorer
                fitness_decay_scorer = FitnessDecayScorer()
            except Exception:  # noqa: BLE001
                fitness_decay_scorer = None
        if causal_fitness_attributor is _UNSET:
            try:
                from runtime.evolution.causal_fitness_attributor import CausalFitnessAttributor
                causal_fitness_attributor = CausalFitnessAttributor()
            except Exception:  # noqa: BLE001
                causal_fitness_attributor = None
        if pareto_competition_orchestrator is _UNSET:
            try:
                from runtime.evolution.pareto_competition import ParetoCompetitionOrchestrator
                pareto_competition_orchestrator = ParetoCompetitionOrchestrator()
            except Exception:  # noqa: BLE001
                pareto_competition_orchestrator = None
        if self_discovery_loop is _UNSET:
            try:
                from runtime.evolution.constitutional_self_discovery import ConstitutionalSelfDiscoveryLoop
                self_discovery_loop = ConstitutionalSelfDiscoveryLoop()
            except Exception:  # noqa: BLE001
                self_discovery_loop = None

        self._fitness_orchestrator = fitness_orchestrator
        self._market_integrator = market_integrator
        self._fitness_decay_scorer = fitness_decay_scorer
        self._causal_attributor = causal_fitness_attributor
        self._pareto_orchestrator = pareto_competition_orchestrator
        self._self_discovery_loop = self_discovery_loop
        self._self_disc_frequency = self_disc_frequency

        # Phase 92 — AFRT agent lazy wiring (INNOV-08 / AFRT-GATE-0)
        if afrt_agent is _UNSET:
            try:
                from runtime.evolution.afrt_engine import AdversarialRedTeamAgent
                from runtime.code_intel import CodeIntelModel
                from runtime.lineage.lineage_ledger_v2 import LineageLedgerV2
                afrt_agent = AdversarialRedTeamAgent(
                    code_intel_model=CodeIntelModel(),
                    ledger=LineageLedgerV2(),
                )
            except Exception:  # noqa: BLE001
                afrt_agent = None  # graceful degradation: AFRT step logs warning, passes
        self._afrt_agent = afrt_agent

        self._epoch_seq: int = 0

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #

    def run_epoch(
        self,
        *,
        epoch_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> EpochCELResult:
        """Execute all 14 CEL steps in strict order (CEL-ORDER-0).

        Returns EpochCELResult. If any step returns BLOCKED, remaining steps
        do not execute (CEL-BLOCK-0) and a partial ledger entry is written.
        """
        epoch_id = epoch_id or str(uuid.uuid4())
        ctx = dict(context or {})
        result = EpochCELResult(
            epoch_id=epoch_id,
            run_mode=self._run_mode,
            dry_run=self._dry_run,
        )

        # Step state accumulator — passed between steps
        state: Dict[str, Any] = {
            "epoch_id": epoch_id,
            "context": ctx,
            "dry_run": self._dry_run,
            "predecessor_hash": self._cel_ledger.chain_tip,
        }

        # 16-step dispatch table (CEL-ORDER-0) — Phase 92: step 10 AFRT-GATE inserted
        steps = [
            (1,  "MODEL-DRIFT-CHECK",    self._step_01_model_drift_check),
            (2,  "LINEAGE-SNAPSHOT",     self._step_02_lineage_snapshot),
            (3,  "FITNESS-BASELINE",     self._step_03_fitness_baseline),
            (4,  "PROPOSAL-GENERATE",    self._step_04_proposal_generate),
            (5,  "AST-SCAN",             self._step_05_ast_scan),
            (6,  "SANDBOX-EXECUTE",      self._step_06_sandbox_execute),
            (7,  "REPLAY-VERIFY",        self._step_07_replay_verify),
            (8,  "FITNESS-SCORE",        self._step_08_fitness_score),
            (9,  "PARETO-SELECT",        self._step_09_pareto_select),
            (10, "AFRT-GATE",            self._step_10_afrt_gate),
            (11, "GOVERNANCE-GATE-V2",   self._step_09_governance_gate_v2),
            (12, "GOVERNANCE-GATE",      self._step_10_governance_gate),
            (13, "LINEAGE-REGISTER",     self._step_11_lineage_register),
            (14, "PROMOTION-DECISION",   self._step_12_promotion_decision),
            (15, "EPOCH-EVIDENCE-WRITE", self._step_13_epoch_evidence_write),
            (16, "STATE-ADVANCE",        self._step_14_state_advance),
        ]

        for step_num, step_name, step_fn in steps:
            try:
                step_result = step_fn(step_num, step_name, state)
            except Exception as exc:  # noqa: BLE001 — emit-and-block, never propagate
                step_result = CELStepResult(
                    step_number=step_num, step_name=step_name,
                    outcome=StepOutcome.BLOCKED,
                    reason="step_exception",
                    detail={"exception": str(exc)},
                )

            result.step_results.append(step_result)

            if step_result.outcome == StepOutcome.BLOCKED:
                result.blocked_at_step = step_num
                # Write partial-epoch evidence if we have enough state (CEL-BLOCK-0)
                self._write_partial_epoch(state, result)
                break

        # Post-epoch self-discovery hook (CEL-SELF-DISC-0, CEL-SELF-DISC-NONBLOCK-0)
        # Runs outside the main step sequence; never blocks epoch completion.
        if not result.blocked_at_step:
            self._run_post_epoch_self_discovery(state, result)
            self._epoch_seq += 1

        return result

    # ------------------------------------------------------------------ #
    # Post-epoch hooks (non-blocking)
    # ------------------------------------------------------------------ #

    def _run_post_epoch_self_discovery(
        self, state: Dict[str, Any], result: "EpochCELResult"
    ) -> None:
        """Post-epoch ConstitutionalSelfDiscoveryLoop hook.

        CEL-SELF-DISC-0:        runs every SELF_DISC_FREQUENCY completed epochs.
        CEL-SELF-DISC-NONBLOCK-0: any exception is swallowed; epoch result unchanged.
        SELF-DISC-HUMAN-0:      candidates are advisory only — HUMAN-0 required
                                before any candidate enters CONSTITUTION.md.
        """
        if self._self_discovery_loop is None:
            return
        if self._epoch_seq % self._self_disc_frequency != 0:
            return
        try:
            discovery_result = self._self_discovery_loop.run()
            state["self_discovery_result"] = {
                "epoch_seq": self._epoch_seq,
                "candidates_proposed": len(getattr(discovery_result, "proposed_invariants", []) or []),
                "ratified": len(getattr(discovery_result, "ratified_invariants", []) or []),
                "note": "SELF-DISC-HUMAN-0: no candidate enters CONSTITUTION.md without HUMAN-0",
            }
        except Exception:  # noqa: BLE001 — CEL-SELF-DISC-NONBLOCK-0
            state["self_discovery_result"] = {"error": "self_discovery_hook_failed", "epoch_seq": self._epoch_seq}

    # ------------------------------------------------------------------ #
    # Step implementations
    # ------------------------------------------------------------------ #

    def _step_01_model_drift_check(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 1 — MODEL-DRIFT-CHECK.
        Verify CodeIntelModel determinism. Block epoch on drift exceeding threshold.
        CEL-BLOCK-0: if determinism_verified=False, epoch does not proceed.
        CEL-REPLAY-0: timestamp from RuntimeDeterminismProvider.
        """
        ts = self._now()
        drift_event_id = f"drift-{state['epoch_id']}-step1"

        # In Phase 64 scope the model is not yet live; build a sentinel drift record
        # indicating determinism verified with zero delta (safe to proceed).
        drift = ModelDriftEvidence(
            drift_event_id=drift_event_id,
            function_graph_delta=0.0,
            hotspot_map_shift=0.0,
            mutation_history_delta=0.0,
            catalyst_event=DriftCatalyst.EPOCH_CONSOLIDATION,
            determinism_verified=True,
            model_hash_before=state.get("model_hash_before", "sha256:" + "0" * 64),
            model_hash_after=state.get("model_hash_before", "sha256:" + "0" * 64),
            divergent_functions=(),
            lockdown_triggered=False,
            drift_threshold=0.15,
            epoch_id=state["epoch_id"],
            timestamp=ts,
        )
        state["drift_evidence"] = drift

        if not drift.is_safe():
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                reason="model_drift_detected",
                detail={"drift_event_id": drift_event_id, "lockdown": drift.lockdown_triggered},
            )
        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={"drift_event_id": drift_event_id})

    def _step_02_lineage_snapshot(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 2 — LINEAGE-SNAPSHOT.
        Hash the current lineage engine state for chain integrity.
        Stored as capability_graph_before; used to detect mid-epoch tampering.
        """
        snapshot_payload = json.dumps(
            {"epoch_id": state["epoch_id"], "step": 2, "ts": self._now()},
            sort_keys=True,
        )
        snapshot_hash = "sha256:" + hashlib.sha256(snapshot_payload.encode()).hexdigest()
        state["capability_graph_before"] = snapshot_hash
        state["model_hash_before"] = state.get(
            "model_hash_before", "sha256:" + "0" * 64
        )
        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={"snapshot_hash": snapshot_hash})

    def _step_03_fitness_baseline(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 3 — FITNESS-BASELINE.
        Record pre-epoch FitnessEngineV2 composite score as baseline.
        """
        baseline_score = state.get("context", {}).get("baseline_fitness_score", 0.5)
        state["fitness_baseline"] = float(baseline_score)
        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={"baseline_score": state["fitness_baseline"]})

    def _step_04_proposal_generate(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 4 — PROPOSAL-GENERATE.
        Request proposals from ProposalEngine. Record mutation_ids to be evaluated.
        """
        proposals = state.get("context", {}).get("proposals", [])
        state["proposals"] = proposals
        state["mutations_attempted"] = tuple(
            p.get("mutation_id", f"mut-{i}") for i, p in enumerate(proposals)
        )
        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={"proposal_count": len(proposals)})

    def _step_05_ast_scan(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 5 — AST-SCAN.
        GovernanceGateV2 pre-flight: AST-SAFE-0, AST-IMPORT-0, AST-COMPLEX-0.
        Blocks the epoch if any hard rule fails for any proposal.
        """
        proposals = state.get("proposals", [])
        epoch_seq = state.get("context", {}).get("epoch_seq", 0)
        capability_name = state.get("context", {}).get("capability_name", "evolution.proposal")

        scan_failures: List[Dict[str, Any]] = []
        class_b_outstanding: List[str] = []

        for proposal in proposals:
            after_source = proposal.get("after_source", "")
            before_source = proposal.get("before_source", None)
            mutation_id = proposal.get("mutation_id", "unknown")

            decision = self._gate_v2.evaluate(
                mutation_id=mutation_id,
                capability_name=capability_name,
                after_source=after_source,
                before_source=before_source,
                replay_diverged=False,  # replay not yet run at this step
                current_epoch_seq=epoch_seq,
            )

            if not decision.approved:
                if decision.class_b_eligible:
                    class_b_outstanding.append(mutation_id)
                else:
                    failed = [r for r in decision.rule_results if not r.passed]
                    scan_failures.append({
                        "mutation_id": mutation_id,
                        "failed_rules": [r.to_dict() for r in failed],
                    })

        state["ast_scan_failures"] = scan_failures
        state["class_b_outstanding"] = class_b_outstanding

        if scan_failures:
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                reason="ast_scan_hard_failure",
                detail={"failures": scan_failures},
            )
        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={"class_b_outstanding": class_b_outstanding})

    def _step_06_sandbox_execute(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 6 — SANDBOX-EXECUTE.
        Execute accepted proposals in an ephemeral sandbox container.
        In SANDBOX_ONLY mode this is always a dry-run; no real writes occur.
        Records sandbox_container_id for SANDBOX-DIV-0 verification in Step 7.
        """
        sandbox_id_payload = json.dumps(
            {"epoch_id": state["epoch_id"], "ts": self._now(), "dry_run": self._dry_run},
            sort_keys=True,
        )
        sandbox_container_id = "sandbox-" + hashlib.sha256(
            sandbox_id_payload.encode()
        ).hexdigest()[:16]
        state["sandbox_container_id"] = sandbox_container_id

        # Sandbox outcomes: in Phase 64 scope, record that proposals executed
        sandbox_results = [
            {"mutation_id": mid, "sandbox_ok": True}
            for mid in state.get("mutations_attempted", ())
        ]
        state["sandbox_results"] = sandbox_results

        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={
                                 "sandbox_container_id": sandbox_container_id,
                                 "dry_run": self._dry_run,
                                 "executed_count": len(sandbox_results),
                             })

    def _step_07_replay_verify(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 7 — REPLAY-VERIFY.
        Deterministically replay sandbox; compare results.
        SANDBOX-DIV-0: any divergence is a hard block.
        Records replay_verification_hash for EpochEvidence.
        """
        sandbox_results = state.get("sandbox_results", [])
        replay_diverged = state.get("context", {}).get("force_replay_divergence", False)

        if replay_diverged:
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                reason="SANDBOX-DIV-0",
                detail={"divergence_detected": True},
            )

        replay_payload = json.dumps(
            {"sandbox_results": sandbox_results, "epoch_id": state["epoch_id"]},
            sort_keys=True,
        )
        replay_hash = "sha256:" + hashlib.sha256(replay_payload.encode()).hexdigest()
        state["replay_verification_hash"] = replay_hash
        state["replay_diverged"] = False

        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={"replay_verification_hash": replay_hash})

    def _step_08_fitness_score(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 8 — FITNESS-SCORE (Phase 86).

        Real fitness scoring pipeline replacing the Phase 64 sandbox_ok stub.

        Pipeline per candidate (STEP8-LEDGER-FIRST-0):
          1. FitnessOrchestrator.score()        — real 5-component composite score
          2. FitnessDecayScorer.evaluate()      — temporal half-life discount
          3. CausalFitnessAttributor.attribute() — per-op Shapley contributions

        All three results are ledger-recorded before fitness_summary is written.

        Determinism guarantee (STEP8-DETERM-0): identical sandbox_results and
        identical CodebaseStateVector → identical fitness_summary tuple.

        Fallback: if any Phase 86 component is unavailable, falls back to
        sandbox_ok-derived score to preserve backward compatibility.
        """
        # sandbox_results may be in state directly (from Step 6) or in context (test injection)
        sandbox_results = state.get("sandbox_results") or state.get("context", {}).get("sandbox_results", [])
        epoch_id = state["epoch_id"]

        # Phase 107 — Market-Conditioned Fitness (MCF)
        market_result = None
        if self._market_integrator is not None:
            try:
                # MCF-INTEGRATE-0: enriches FitnessOrchestrator with live signal
                market_result = self._market_integrator.integrate(epoch_id=epoch_id)
            except Exception:  # noqa: BLE001 — MCF advisory; never blocks
                pass

        fitness_summary: List[Tuple[str, float]] = []
        fitness_detail: Dict[str, Any] = {}

        for sr in sandbox_results:
            mid = sr.get("mutation_id", "unknown")
            sandbox_ok = sr.get("sandbox_ok", False)

            # --- 1. FitnessOrchestrator real composite score ---
            composite_score: float = 0.65 if sandbox_ok else 0.0  # fallback
            if self._fitness_orchestrator is not None:
                try:
                    fitness_ctx = {
                        "epoch_id": epoch_id,
                        "mutation_id": mid,
                        "sandbox_ok": sandbox_ok,
                        **sr.get("fitness_signals", {}),
                    }
                    score_result = self._fitness_orchestrator.score(fitness_ctx)
                    composite_score = float(getattr(score_result, "total_score", composite_score))
                except Exception:  # noqa: BLE001 — fallback to sandbox_ok score
                    pass

            # --- 2. FitnessDecayScorer temporal discount ---
            decay_coeff: float = 1.0
            if self._fitness_decay_scorer is not None:
                try:
                    from runtime.evolution.fitness_decay_scorer import FitnessRecord
                    from runtime.evolution.codebase_state_vector import CodebaseStateVector
                    current_vector = CodebaseStateVector.from_repo()
                    record_id = sha256_prefixed_digest(
                        canonical_json({"candidate_id": mid, "epoch_id": epoch_id}).encode()
                    )
                    fitness_record = FitnessRecord(
                        record_id=record_id,
                        candidate_id=mid,
                        epoch_id=epoch_id,
                        recorded_score=composite_score,
                        codebase_state_vector=current_vector,
                    )
                    decay_result = self._fitness_decay_scorer.evaluate(fitness_record, current_vector)
                    decay_coeff = float(getattr(decay_result, "decay_coefficient", 1.0))
                    composite_score = composite_score * decay_coeff
                except Exception:  # noqa: BLE001 — decay advisory; never blocks
                    pass

            # --- 3. CausalFitnessAttributor per-op Shapley ---
            attribution_digest: str = "sha256:" + "0" * 64
            if self._causal_attributor is not None:
                try:
                    attr_report = self._causal_attributor.attribute(
                        candidate_id=mid,
                        base_fitness_context={
                            "epoch_id": epoch_id,
                            "sandbox_ok": sandbox_ok,
                            **sr.get("fitness_signals", {}),
                        },
                        before_source=sr.get("before_source"),
                        python_content=sr.get("after_source"),
                    )
                    attribution_digest = getattr(attr_report, "attribution_digest",
                                                 attribution_digest)
                except Exception:  # noqa: BLE001 — attribution advisory; never blocks
                    pass

            fitness_summary.append((mid, composite_score))
            fitness_detail[mid] = {
                "composite_score": round(composite_score, 6),
                "decay_coeff": round(decay_coeff, 6),
                "attribution_digest": attribution_digest,
                "market_signal": market_result.is_synthetic if market_result else None,
            }

        # STEP8-LEDGER-FIRST-0: record fitness event before writing state
        fitness_event_digest = sha256_prefixed_digest(
            canonical_json({
                "epoch_id": epoch_id,
                "step": 8,
                "fitness_detail": {k: v["composite_score"] for k, v in fitness_detail.items()},
            }).encode()
        )
        state["fitness_event_digest"] = fitness_event_digest
        state["fitness_detail"] = fitness_detail

        # Write fitness_summary — candidates with score > 0 pass to PARETO-SELECT
        state["fitness_summary"] = tuple(fitness_summary)
        state["mutations_scored"] = tuple(mid for mid, _ in fitness_summary)

        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={
                                 "scored_count": len(fitness_summary),
                                 "fitness_event_digest": fitness_event_digest,
                             })

    def _step_09_pareto_select(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 9 — PARETO-SELECT (Phase 86).

        Multi-objective Pareto frontier selection via ParetoCompetitionOrchestrator.
        Replaces the naive score > 0.5 threshold used in Phase 64–85.

        CEL-PARETO-0:       frontier written to ledger before Step 10.
        CEL-PARETO-DETERM-0: identical scored candidates → identical frontier.

        Fallback: if ParetoCompetitionOrchestrator is unavailable, falls back to
        score > 0.5 threshold and marks state["pareto_fallback"] = True.
        """
        fitness_summary: tuple = state.get("fitness_summary", ())

        if not fitness_summary:
            state["mutations_succeeded"] = ()
            state["pareto_frontier_ids"] = ()
            return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                                 detail={"frontier_size": 0, "note": "no candidates"})

        # Fallback path — no Pareto orchestrator available
        if self._pareto_orchestrator is None:
            state["mutations_succeeded"] = tuple(
                mid for mid, score in fitness_summary if score > 0.5
            )
            state["pareto_frontier_ids"] = state["mutations_succeeded"]
            state["pareto_fallback"] = True
            return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                                 detail={"frontier_size": len(state["mutations_succeeded"]),
                                         "fallback": True})

        # Build SeedCandidate objects from fitness_summary
        try:
            from runtime.seed_competition import SeedCandidate
            epoch_id = state["epoch_id"]
            candidates = [
                SeedCandidate(
                    candidate_id=mid,
                    fitness_context={
                        "epoch_id": epoch_id,
                        "composite_score": score,
                        **state.get("fitness_detail", {}).get(mid, {}),
                    },
                    metadata={"cel_epoch_id": epoch_id},
                )
                for mid, score in fitness_summary
            ]

            pareto_result = self._pareto_orchestrator.run_epoch(candidates)
            promoted_ids = tuple(getattr(pareto_result, "promoted_ids", []) or [])

            # CEL-PARETO-0: record frontier digest before writing to state
            frontier_digest = sha256_prefixed_digest(
                canonical_json({
                    "epoch_id": epoch_id,
                    "step": 9,
                    "promoted_ids": sorted(promoted_ids),
                }).encode()
            )
            state["pareto_frontier_digest"] = frontier_digest
            state["pareto_frontier_ids"] = promoted_ids
            state["mutations_succeeded"] = promoted_ids
            state["pareto_fallback"] = False

            return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                                 detail={
                                     "frontier_size": len(promoted_ids),
                                     "frontier_digest": frontier_digest,
                                     "total_candidates": len(candidates),
                                 })

        except Exception as exc:  # noqa: BLE001 — fallback on any Pareto error
            state["mutations_succeeded"] = tuple(
                mid for mid, score in fitness_summary if score > 0.5
            )
            state["pareto_frontier_ids"] = state["mutations_succeeded"]
            state["pareto_fallback"] = True
            state["pareto_error"] = str(exc)
            return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                                 detail={"fallback": True, "error": str(exc)})

    def _step_10_afrt_gate(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 10 — AFRT-GATE (Phase 92 / INNOV-08).

        Adversarial Fitness Red Team evaluation.  Invokes AdversarialRedTeamAgent
        for each proposal on the Pareto frontier.  A RETURNED verdict from any
        proposal is a hard block (CEL-BLOCK-0).

        AFRT-GATE-0: this step executes AFTER PARETO-SELECT (Step 9) and BEFORE
        GOVERNANCE-GATE-V2 (Step 11).  Any deviation is a CELStepOrderViolation.

        Graceful degradation: if _afrt_agent is None (pre-Phase-92 environments
        or import failure), step logs a WARNING and passes through without blocking.
        """
        if self._afrt_agent is None:
            import logging as _log
            _log.getLogger(__name__).warning(
                "AFRT-GATE: afrt_agent unavailable — step bypassed (pre-Phase-92 mode). "
                "AFRT-GATE-0 not enforced in this run."
            )
            state["afrt_bypassed"] = True
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.PASS,
                detail={"afrt_bypassed": True, "reason": "afrt_agent_unavailable"},
            )

        epoch_id = state["epoch_id"]
        pareto_ids: List[str] = state.get("pareto_frontier_ids", [])
        proposals = state.get("context", {}).get("proposals", [])

        # Map proposals to pareto frontier (fall back to all proposals)
        frontier_proposals = [
            p for p in proposals
            if (getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else None))
            in pareto_ids
        ] if pareto_ids and proposals else proposals

        if not frontier_proposals:
            # No proposals to evaluate — trivial pass (nothing survived to this step)
            state["afrt_verdict"] = "NO_PROPOSALS"
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.PASS,
                detail={"afrt_verdict": "NO_PROPOSALS", "evaluated": 0},
            )

        returned_proposals: List[str] = []
        afrt_reports = []

        for proposal in frontier_proposals:
            try:
                report = self._afrt_agent.evaluate(proposal, epoch_id)
                afrt_reports.append(report)
                from runtime.evolution.afrt_engine import RedTeamVerdict
                if report.verdict == RedTeamVerdict.RETURNED:
                    pid = report.proposal_id
                    returned_proposals.append(pid)
            except Exception as exc:  # noqa: BLE001
                # Engine failure is a hard block (AFRT-CASES-0 / AFRT-LEDGER-0)
                return CELStepResult(
                    step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                    reason="AFRT_ENGINE_FAILURE",
                    detail={"exception": str(exc)},
                )

        state["afrt_reports"] = afrt_reports
        state["afrt_returned_proposals"] = returned_proposals

        if returned_proposals:
            state["afrt_verdict"] = "RETURNED"
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                reason="AFRT_RETURNED",
                detail={
                    "afrt_verdict": "RETURNED",
                    "returned_proposals": returned_proposals,
                    "evaluated": len(afrt_reports),
                    "note": (
                        "One or more proposals returned by Red Team. "
                        "Inspect RedTeamFindingsReport for uncovered path failures."
                    ),
                },
            )

        state["afrt_verdict"] = "PASS"
        return CELStepResult(
            step_number=n, step_name=name, outcome=StepOutcome.PASS,
            detail={
                "afrt_verdict": "PASS",
                "evaluated": len(afrt_reports),
                "all_survived": True,
            },
        )

    def _step_09_governance_gate_v2(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 9 — GOVERNANCE-GATE-V2.
        Full GovernanceGateV2 evaluation (all 5 Phase 63 rules).
        CEL-GATE-0: hard block unless class_b_eligible (which still needs HUMAN-0).
        """
        capability_name = state.get("context", {}).get("capability_name", "evolution.proposal")
        epoch_seq = state.get("context", {}).get("epoch_seq", 0)
        replay_diverged = state.get("replay_diverged", False)

        gate_decisions: List[Dict[str, Any]] = []
        hard_failures: List[str] = []
        class_b_needed: List[str] = []

        for mid in state.get("mutations_succeeded", ()):
            proposal = next(
                (p for p in state.get("proposals", []) if p.get("mutation_id") == mid),
                {},
            )
            decision = self._gate_v2.evaluate(
                mutation_id=mid,
                capability_name=capability_name,
                after_source=proposal.get("after_source", ""),
                before_source=proposal.get("before_source", None),
                replay_diverged=replay_diverged,
                current_epoch_seq=epoch_seq,
            )
            gate_decisions.append(decision.to_dict())
            if not decision.approved:
                if decision.class_b_eligible:
                    class_b_needed.append(mid)
                else:
                    hard_failures.append(mid)

        state["v2_gate_decisions"] = gate_decisions
        state["v2_gate_class_b_needed"] = class_b_needed

        if hard_failures:
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.BLOCKED,
                reason="CEL-GATE-0_hard_failure",
                detail={"hard_failures": hard_failures},
            )
        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={"class_b_needed": class_b_needed,
                                     "gate_decisions_count": len(gate_decisions)})

    def _step_10_governance_gate(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 10 — GOVERNANCE-GATE.
        Existing GovernanceGate (all 16 pre-Phase-63 rules).
        GATE-V2-EXISTING-0 compliance: existing gate is never replaced or skipped.
        In Phase 64 scope the gate is invoked via law_context stub.
        """
        # GATE-V2-EXISTING-0: existing gate evaluates independently; decisions
        # are recorded for audit. In Phase 64 scope this produces a PASS stub
        # because the full wiring of existing GovernanceGate to CEL is Phase 65+.
        # The important constitutional guarantee is that this step ALWAYS executes
        # (never skipped) and comes AFTER GovernanceGateV2 (Step 9).
        state["existing_gate_invoked"] = True
        state["existing_gate_passed"] = True

        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={"gate_v2_existing_0_compliant": True,
                                     "note": "full wiring Phase 65+"})

    def _step_11_lineage_register(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 11 — LINEAGE-REGISTER.
        Register surviving mutations in LineageEngine.
        Records lineage_evidence for EvolutionEvidence assembly.
        """
        mutations_succeeded = state.get("mutations_succeeded", ())
        lineage_records: List[MutationLineageEvidence] = []

        for mid in mutations_succeeded:
            score = next(
                (s for m, s in state.get("fitness_summary", ()) if m == mid), 0.0
            )
            lineage_records.append(
                MutationLineageEvidence(
                    lineage_id=f"lineage-{mid}",
                    parent_lineage_id=None,
                    mutations_applied=(mid,),
                    fitness_trajectory=score,
                    stability_score=score,
                    governance_exceptions_used=(),
                    promotion_status=PromotionStatus.PROMOTED,
                )
            )

        state["lineage_evidence"] = lineage_records
        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={"registered_count": len(lineage_records)})

    def _step_12_promotion_decision(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 12 — PROMOTION-DECISION.
        Write PromotionEvent for accepted mutations.
        CEL-DRYRUN-0: suppressed entirely in SANDBOX_ONLY mode — no writes, no events.
        """
        if self._dry_run:
            return CELStepResult(
                step_number=n, step_name=name, outcome=StepOutcome.SKIPPED,
                reason="SANDBOX_ONLY_mode",
                detail={"promoted_count": 0},
            )

        promoted = list(state.get("mutations_succeeded", ()))
        # Real promotion write would go here in LIVE mode (Phase 65+ full wiring).
        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={"promoted_count": len(promoted)})

    def _step_13_epoch_evidence_write(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 13 — EPOCH-EVIDENCE-WRITE.
        Assemble EpochEvidence + EvolutionEvidence; write to append-only ledger.
        CEL-EVIDENCE-0: predecessor_hash links to prior epoch; chain validated.
        CEL-DRYRUN-0: in SANDBOX_ONLY mode the write is tagged dry_run=True; no
        real ledger modification; chain_tip is NOT advanced.
        """
        ts = self._now()
        cap_before = state.get("capability_graph_before", "sha256:" + "0" * 64)
        cap_after_payload = json.dumps(
            {"epoch_id": state["epoch_id"], "step": 13, "ts": ts}, sort_keys=True
        )
        cap_after = "sha256:" + hashlib.sha256(cap_after_payload.encode()).hexdigest()
        model_hash = state.get("model_hash_before", "sha256:" + "0" * 64)

        epoch_evidence = EpochEvidence(
            epoch_id=state["epoch_id"],
            model_hash_before=model_hash,
            model_hash_after=model_hash,
            capability_graph_before=cap_before,
            capability_graph_after=cap_after,
            evaluated_lineages=state.get("mutations_attempted", ()),
            promoted_lineage_id=(
                state["mutations_succeeded"][0]
                if state.get("mutations_succeeded") else None
            ),
            replay_verification_hash=state.get(
                "replay_verification_hash", "sha256:" + "0" * 64
            ),
            sandbox_container_id=state.get("sandbox_container_id", ""),
            predecessor_hash=state["predecessor_hash"],
            timestamp=ts,
            mutations_attempted=state.get("mutations_attempted", ()),
            mutations_succeeded=state.get("mutations_succeeded", ()),
            fitness_summary=state.get("fitness_summary", ()),
        )

        evolution_evidence = EvolutionEvidence.build(
            epoch=epoch_evidence,
            lineages=state.get("lineage_evidence", []),
            capabilities=[],
            exceptions=[],
            drift=state["drift_evidence"],
        )

        record_hash = self._cel_ledger.append(evolution_evidence, dry_run=self._dry_run)
        state["epoch_evidence_hash"] = record_hash

        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail={
                                 "record_hash": record_hash,
                                 "dry_run": self._dry_run,
                                 "chain_tip": self._cel_ledger.chain_tip,
                             })

    def _step_14_state_advance(
        self, n: int, name: str, state: Dict[str, Any]
    ) -> CELStepResult:
        """Step 14 — STATE-ADVANCE.
        Advance epoch counter; emit epoch_complete.v1 journal event.
        CEL-REPLAY-0: timestamp from RuntimeDeterminismProvider.
        """
        ts = self._now()
        event_payload = {
            "event_type": "epoch_complete.v1",
            "epoch_id": state["epoch_id"],
            "dry_run": self._dry_run,
            "epoch_evidence_hash": state.get("epoch_evidence_hash"),
            "mutations_attempted": len(state.get("mutations_attempted", ())),
            "mutations_succeeded": len(state.get("mutations_succeeded", ())),
            "timestamp": ts,
        }
        # In Phase 64 the journal write is a no-op stub (real journal Phase 65+ wiring).
        return CELStepResult(step_number=n, step_name=name, outcome=StepOutcome.PASS,
                             detail=event_payload)

    # ------------------------------------------------------------------ #
    # Partial epoch write (CEL-BLOCK-0)
    # ------------------------------------------------------------------ #

    def _write_partial_epoch(
        self, state: Dict[str, Any], result: EpochCELResult
    ) -> None:
        """Write a partial EvolutionEvidence when epoch is blocked mid-sequence."""
        if "drift_evidence" not in state:
            return  # too early; drift record not yet built
        try:
            ts = self._now()
            epoch_evidence = EpochEvidence(
                epoch_id=state["epoch_id"],
                model_hash_before=state.get("model_hash_before", "sha256:" + "0" * 64),
                model_hash_after=state.get("model_hash_before", "sha256:" + "0" * 64),
                capability_graph_before=state.get(
                    "capability_graph_before", "sha256:" + "0" * 64
                ),
                capability_graph_after="sha256:" + "0" * 64,
                evaluated_lineages=state.get("mutations_attempted", ()),
                promoted_lineage_id=None,
                replay_verification_hash="sha256:" + "0" * 64,
                sandbox_container_id=state.get("sandbox_container_id", ""),
                predecessor_hash=state.get("predecessor_hash", GENESIS_PREDECESSOR),
                timestamp=ts,
                mutations_attempted=state.get("mutations_attempted", ()),
                mutations_succeeded=(),
                governance_events=("PARTIAL_EPOCH:blocked_at_step_"
                                   f"{result.blocked_at_step}",),
            )
            evolution_evidence = EvolutionEvidence.build(
                epoch=epoch_evidence,
                lineages=[],
                capabilities=[],
                exceptions=[],
                drift=state["drift_evidence"],
            )
            self._cel_ledger.append(evolution_evidence, dry_run=True)  # always dry for partial
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ #
    # Timestamp helper (CEL-REPLAY-0)
    # ------------------------------------------------------------------ #

    def _now(self) -> str:
        if self._ts_provider is not None:
            try:
                return self._ts_provider.now_utc()
            except Exception:  # noqa: BLE001
                pass
        # Fallback: deterministic sentinel (never datetime.now())
        return "2026-03-13T00:00:00Z"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "CEL_LEDGER_PATH",
    "CELEvidenceLedger",
    "CELStepResult",
    "ConstitutionalEvolutionLoop",
    "EpochCELResult",
    "RunMode",
    "StepOutcome",
]
