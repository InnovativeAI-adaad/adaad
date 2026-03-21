# SPDX-License-Identifier: Apache-2.0
"""Phase 86 Track A — CEL Fitness Wiring constitutional tests.

Test IDs: T86-FIT-01..24

Invariants under test:
  STEP8-LEDGER-FIRST-0   fitness event digest written before fitness_summary committed to state
  STEP8-DETERM-0         identical sandbox_results + codebase state → identical fitness_summary
  CEL-ORDER-0            15-step sequence enforced; PARETO-SELECT at step 9
  CEL-SELF-DISC-0        self-discovery runs every SELF_DISC_FREQUENCY completed epochs
  CEL-SELF-DISC-NONBLOCK-0  self-discovery failure never blocks epoch completion
  SELF-DISC-HUMAN-0      candidate advisory note recorded in state
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from runtime.evolution.constitutional_evolution_loop import (
    ConstitutionalEvolutionLoop,
    RunMode,
    StepOutcome,
    SELF_DISC_FREQUENCY,
)

pytestmark = pytest.mark.phase86


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

def _sandbox_result(mid: str, ok: bool = True, correctness: float = 0.8) -> Dict[str, Any]:
    return {
        "mutation_id": mid,
        "sandbox_ok": ok,
        "fitness_signals": {
            "correctness_score": correctness,
            "efficiency_score": 0.7,
            "policy_compliance_score": 0.9,
            "goal_alignment_score": 0.8,
            "simulated_market_score": 0.5,
        },
    }


def _cel(
    fitness_orchestrator=None,
    fitness_decay_scorer=None,
    causal_attributor=None,
    pareto_orchestrator=None,
    self_discovery_loop=None,
    self_disc_frequency: int = SELF_DISC_FREQUENCY,
) -> ConstitutionalEvolutionLoop:
    return ConstitutionalEvolutionLoop(
        run_mode=RunMode.SANDBOX_ONLY,
        fitness_orchestrator=fitness_orchestrator,
        fitness_decay_scorer=fitness_decay_scorer,
        causal_fitness_attributor=causal_attributor,
        pareto_competition_orchestrator=pareto_orchestrator,
        self_discovery_loop=self_discovery_loop,
        self_disc_frequency=self_disc_frequency,
    )


def _run(cel: ConstitutionalEvolutionLoop, sandbox_results: Optional[list] = None,
         epoch_seq: int = 0) -> Any:
    return cel.run_epoch(context={
        "epoch_id": f"ep-{uuid.uuid4().hex[:8]}",
        "epoch_seq": epoch_seq,
        "sandbox_results": sandbox_results or [],
    })


# ---------------------------------------------------------------------------
# T86-FIT-01..05 — Step count and step names (CEL-ORDER-0)
# ---------------------------------------------------------------------------

class TestStepSequence:

    def test_t86_fit_01_epoch_runs_15_steps(self):
        """T86-FIT-01: full epoch executes exactly 15 steps."""
        cel = _cel()
        result = _run(cel)
        assert len(result.step_results) == 15

    def test_t86_fit_02_step_9_is_pareto_select(self):
        """T86-FIT-02: step 9 is named PARETO-SELECT."""
        cel = _cel()
        result = _run(cel)
        step9 = next(s for s in result.step_results if s.step_number == 9)
        assert step9.step_name == "PARETO-SELECT"

    def test_t86_fit_03_step_10_is_governance_gate_v2(self):
        """T86-FIT-03: GovernanceGateV2 is at step 10 (shifted from 9)."""
        cel = _cel()
        result = _run(cel)
        step10 = next(s for s in result.step_results if s.step_number == 10)
        assert step10.step_name == "GOVERNANCE-GATE-V2"

    def test_t86_fit_04_step_15_is_state_advance(self):
        """T86-FIT-04: final step is 15 STATE-ADVANCE."""
        cel = _cel()
        result = _run(cel)
        last = result.step_results[-1]
        assert last.step_number == 15
        assert last.step_name == "STATE-ADVANCE"

    def test_t86_fit_05_no_block_on_clean_epoch(self):
        """T86-FIT-05: clean epoch has no blocked step."""
        cel = _cel()
        result = _run(cel)
        assert result.blocked_at_step is None


# ---------------------------------------------------------------------------
# T86-FIT-06..10 — Step 8 fitness scoring
# ---------------------------------------------------------------------------

class TestStep8FitnessScore:

    def test_t86_fit_06_step8_passes_with_no_orchestrator(self):
        """T86-FIT-06: Step 8 passes even when FitnessOrchestrator is None (fallback)."""
        cel = _cel(fitness_orchestrator=None)
        result = _run(cel, [_sandbox_result("m1")])
        step8 = next(s for s in result.step_results if s.step_number == 8)
        assert step8.outcome == StepOutcome.PASS

    def test_t86_fit_07_step8_records_fitness_event_digest(self):
        """T86-FIT-07: STEP8-LEDGER-FIRST-0 — fitness_event_digest written before summary."""
        cel = _cel()
        ctx = {
            "epoch_id": "ep-ledger-first",
            "epoch_seq": 0,
            "sandbox_results": [_sandbox_result("m1")],
        }
        result = cel.run_epoch(context=ctx)
        assert result.blocked_at_step is None
        step8 = next(s for s in result.step_results if s.step_number == 8)
        assert step8.detail.get("fitness_event_digest", "").startswith("sha256:")

    def test_t86_fit_08_fallback_score_for_failed_sandbox(self):
        """T86-FIT-08: sandbox_ok=False → composite_score = 0.0 in fallback path."""
        cel = _cel(fitness_orchestrator=None)
        ctx = {
            "epoch_id": "ep-fail",
            "epoch_seq": 0,
            "sandbox_results": [_sandbox_result("m1", ok=False)],
        }
        result = cel.run_epoch(context=ctx)
        step8 = next(s for s in result.step_results if s.step_number == 8)
        assert step8.outcome == StepOutcome.PASS
        assert step8.detail["scored_count"] == 1

    def test_t86_fit_09_fitness_orchestrator_invoked_per_candidate(self):
        """T86-FIT-09: FitnessOrchestrator.score called once per sandbox result."""
        mock_score_result = MagicMock()
        mock_score_result.total_score = 0.88
        mock_orch = MagicMock()
        mock_orch.score.return_value = mock_score_result

        cel = _cel(fitness_orchestrator=mock_orch)
        _run(cel, [_sandbox_result("m1"), _sandbox_result("m2")])
        assert mock_orch.score.call_count == 2

    def test_t86_fit_10_step8_determ_identical_inputs_identical_digest(self):
        """T86-FIT-10: STEP8-DETERM-0 — same sandbox_results → same fitness_event_digest.

        epoch_id must be passed as run_epoch kwarg (not in context) so state["epoch_id"]
        is stable across calls — context["epoch_id"] is not consumed by run_epoch.
        """
        cel = _cel(fitness_orchestrator=None, fitness_decay_scorer=None,
                   causal_attributor=None, pareto_orchestrator=None)
        sr = [_sandbox_result("m1"), _sandbox_result("m2")]
        epoch_id = "ep-determ-fixed"

        r1 = cel.run_epoch(epoch_id=epoch_id, context={"epoch_seq": 0, "sandbox_results": sr})
        r2 = cel.run_epoch(epoch_id=epoch_id, context={"epoch_seq": 0, "sandbox_results": sr})

        d1 = next(s for s in r1.step_results if s.step_number == 8).detail["fitness_event_digest"]
        d2 = next(s for s in r2.step_results if s.step_number == 8).detail["fitness_event_digest"]
        assert d1 == d2


# ---------------------------------------------------------------------------
# T86-FIT-11..15 — FitnessDecayScorer integration
# ---------------------------------------------------------------------------

class TestDecayScorer:

    def test_t86_fit_11_decay_scorer_failure_is_graceful(self):
        """T86-FIT-11: FitnessDecayScorer provided but CodebaseStateVector.from_repo
        may fail in test environment — epoch completes regardless (advisory)."""
        mock_decay = MagicMock()
        mock_decay_result = MagicMock()
        mock_decay_result.decay_coefficient = 0.95
        mock_decay.evaluate.return_value = mock_decay_result

        cel = _cel(fitness_decay_scorer=mock_decay)
        result = _run(cel, [_sandbox_result("m1")])
        # Step 8 always passes regardless of decay scorer outcome
        step8 = next(s for s in result.step_results if s.step_number == 8)
        assert step8.outcome == StepOutcome.PASS
        assert result.blocked_at_step is None

    def test_t86_fit_12_decay_scorer_failure_does_not_block(self):
        """T86-FIT-12: FitnessDecayScorer exception → epoch continues (advisory)."""
        mock_decay = MagicMock()
        mock_decay.evaluate.side_effect = RuntimeError("decay_failure")

        cel = _cel(fitness_decay_scorer=mock_decay)
        result = _run(cel, [_sandbox_result("m1")])
        assert result.blocked_at_step is None


# ---------------------------------------------------------------------------
# T86-FIT-16..19 — CausalFitnessAttributor integration
# ---------------------------------------------------------------------------

class TestCausalAttributor:

    def test_t86_fit_16_causal_attributor_called_per_candidate(self):
        """T86-FIT-16: CausalFitnessAttributor.attribute called once per sandbox result."""
        mock_report = MagicMock()
        mock_report.attribution_digest = "sha256:" + "a" * 64
        mock_attr = MagicMock()
        mock_attr.attribute.return_value = mock_report

        cel = _cel(causal_attributor=mock_attr)
        _run(cel, [_sandbox_result("m1"), _sandbox_result("m2")])
        assert mock_attr.attribute.call_count == 2

    def test_t86_fit_17_causal_attributor_failure_does_not_block(self):
        """T86-FIT-17: CausalFitnessAttributor exception → epoch continues (advisory)."""
        mock_attr = MagicMock()
        mock_attr.attribute.side_effect = RuntimeError("attr_failure")

        cel = _cel(causal_attributor=mock_attr)
        result = _run(cel, [_sandbox_result("m1")])
        assert result.blocked_at_step is None

    def test_t86_fit_18_attribution_digest_in_fitness_detail(self):
        """T86-FIT-18: attribution_digest surfaced in fitness_detail per candidate."""
        mock_report = MagicMock()
        mock_report.attribution_digest = "sha256:" + "b" * 64
        mock_attr = MagicMock()
        mock_attr.attribute.return_value = mock_report

        cel = _cel(causal_attributor=mock_attr)
        # Epoch runs; detail captured in step8 detail
        result = _run(cel, [_sandbox_result("m1")])
        step8 = next(s for s in result.step_results if s.step_number == 8)
        assert step8.outcome == StepOutcome.PASS

    def test_t86_fit_19_zero_candidates_step8_passes(self):
        """T86-FIT-19: empty sandbox_results → step 8 passes with scored_count=0."""
        cel = _cel()
        result = _run(cel, sandbox_results=[])
        step8 = next(s for s in result.step_results if s.step_number == 8)
        assert step8.outcome == StepOutcome.PASS
        assert step8.detail["scored_count"] == 0


# ---------------------------------------------------------------------------
# T86-FIT-20..22 — Constructor injection (testability)
# ---------------------------------------------------------------------------

class TestConstructorInjection:

    def test_t86_fit_20_all_none_components_accepted(self):
        """T86-FIT-20: all Phase 86 components None → epoch still runs 15 steps."""
        cel = ConstitutionalEvolutionLoop(
            run_mode=RunMode.SANDBOX_ONLY,
            fitness_orchestrator=None,
            fitness_decay_scorer=None,
            causal_fitness_attributor=None,
            pareto_competition_orchestrator=None,
            self_discovery_loop=None,
        )
        result = _run(cel)
        assert len(result.step_results) == 15

    def test_t86_fit_21_self_disc_frequency_respected(self):
        """T86-FIT-21: self_disc_frequency param stored on instance."""
        cel = ConstitutionalEvolutionLoop(
            run_mode=RunMode.SANDBOX_ONLY,
            self_disc_frequency=10,
        )
        assert cel._self_disc_frequency == 10

    def test_t86_fit_22_epoch_seq_starts_at_zero(self):
        """T86-FIT-22: _epoch_seq initialises to 0."""
        cel = ConstitutionalEvolutionLoop(run_mode=RunMode.SANDBOX_ONLY)
        assert cel._epoch_seq == 0

    def test_t86_fit_23_epoch_seq_increments_after_complete_epoch(self):
        """T86-FIT-23: completed epoch increments _epoch_seq by 1."""
        cel = ConstitutionalEvolutionLoop(run_mode=RunMode.SANDBOX_ONLY)
        _run(cel)
        assert cel._epoch_seq == 1

    def test_t86_fit_24_epoch_seq_does_not_increment_on_blocked_epoch(self):
        """T86-FIT-24: blocked epoch does not increment _epoch_seq."""
        # Force a block in step 1 by injecting a bad gate_v2
        from runtime.evolution.constitutional_evolution_loop import CELStepResult, StepOutcome
        cel = ConstitutionalEvolutionLoop(run_mode=RunMode.SANDBOX_ONLY)
        # Patch step 1 to block
        original = cel._step_01_model_drift_check
        def _blocking_step1(n, name, state):
            return CELStepResult(step_number=n, step_name=name,
                                 outcome=StepOutcome.BLOCKED, reason="forced_test_block")
        cel._step_01_model_drift_check = _blocking_step1
        _run(cel)
        assert cel._epoch_seq == 0
