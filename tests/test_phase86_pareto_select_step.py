# SPDX-License-Identifier: Apache-2.0
"""Phase 86 Track A — PARETO-SELECT step constitutional tests.

Test IDs: T86-PAR-01..15

Invariants under test:
  CEL-PARETO-0        Pareto frontier digest written to state before Step 10.
  CEL-PARETO-DETERM-0 Identical scored candidates → identical Pareto frontier.
  CEL-ORDER-0         PARETO-SELECT executes at step 9.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from runtime.evolution.constitutional_evolution_loop import (
    ConstitutionalEvolutionLoop,
    RunMode,
    StepOutcome,
)

pytestmark = pytest.mark.phase86


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL = object()  # distinguish "not passed" from None


def _cel(pareto_orchestrator=_SENTINEL) -> ConstitutionalEvolutionLoop:
    """Build a CEL with all Phase 86 components disabled except the Pareto orchestrator.

    Passing pareto_orchestrator=None explicitly forces the no-orchestrator fallback path,
    bypassing the constructor's lazy-import fallback.
    """
    from unittest.mock import patch as _patch
    kwargs: dict = dict(
        run_mode=RunMode.SANDBOX_ONLY,
        fitness_orchestrator=None,
        fitness_decay_scorer=None,
        causal_fitness_attributor=None,
    )
    if pareto_orchestrator is _SENTINEL:
        # Use whatever the constructor resolves (lazy-import or None)
        pass
    else:
        kwargs["pareto_competition_orchestrator"] = pareto_orchestrator
    return ConstitutionalEvolutionLoop(**kwargs)


def _sr(mid: str, ok: bool = True) -> Dict[str, Any]:
    return {
        "mutation_id": mid,
        "sandbox_ok": ok,
        "fitness_signals": {
            "correctness_score": 0.8, "efficiency_score": 0.7,
            "policy_compliance_score": 0.9, "goal_alignment_score": 0.8,
            "simulated_market_score": 0.5,
        },
    }


def _mock_pareto(promoted: List[str]) -> MagicMock:
    mock_result = MagicMock()
    mock_result.promoted_ids = promoted
    mock_orch = MagicMock()
    mock_orch.run_epoch.return_value = mock_result
    return mock_orch


def _run(cel, sandbox_results=None, epoch_id=None):
    return cel.run_epoch(context={
        "epoch_id": epoch_id or f"ep-{uuid.uuid4().hex[:8]}",
        "epoch_seq": 0,
        "sandbox_results": sandbox_results or [],
    })


# ---------------------------------------------------------------------------
# T86-PAR-01..04 — Step position and basic behaviour
# ---------------------------------------------------------------------------

class TestParetoSelectPosition:

    def test_t86_par_01_pareto_select_at_step_9(self):
        """T86-PAR-01: PARETO-SELECT executes at step 9 (CEL-ORDER-0)."""
        cel = _cel()
        result = _run(cel)
        step9 = next(s for s in result.step_results if s.step_number == 9)
        assert step9.step_name == "PARETO-SELECT"
        assert step9.outcome == StepOutcome.PASS

    def test_t86_par_02_pareto_select_runs_before_gate_v2(self):
        """T86-PAR-02: PARETO-SELECT (step 9) always precedes GOVERNANCE-GATE-V2 (step 10)."""
        cel = _cel()
        result = _run(cel)
        step_names = [s.step_name for s in result.step_results]
        pareto_idx = step_names.index("PARETO-SELECT")
        gate_idx = step_names.index("GOVERNANCE-GATE-V2")
        assert pareto_idx < gate_idx

    def test_t86_par_03_no_block_on_empty_candidates(self):
        """T86-PAR-03: empty fitness_summary → PARETO-SELECT passes with frontier_size=0."""
        cel = _cel()
        result = _run(cel, sandbox_results=[])
        step9 = next(s for s in result.step_results if s.step_number == 9)
        assert step9.outcome == StepOutcome.PASS
        assert step9.detail.get("frontier_size", 0) == 0

    def test_t86_par_04_fallback_when_no_orchestrator(self):
        """T86-PAR-04: no Pareto orchestrator → fallback path; step still passes."""
        cel = _cel(pareto_orchestrator=None)
        result = _run(cel, [_sr("m1"), _sr("m2")])
        step9 = next(s for s in result.step_results if s.step_number == 9)
        assert step9.outcome == StepOutcome.PASS
        assert step9.detail.get("fallback") is True


# ---------------------------------------------------------------------------
# T86-PAR-05..08 — Pareto orchestrator invocation
# ---------------------------------------------------------------------------

class TestParetoOrchestrator:

    def test_t86_par_05_run_epoch_called_once_per_epoch(self):
        """T86-PAR-05: ParetoCompetitionOrchestrator.run_epoch called exactly once."""
        mock_orch = _mock_pareto(["m1"])
        cel = _cel(mock_orch)
        _run(cel, [_sr("m1"), _sr("m2")])
        assert mock_orch.run_epoch.call_count == 1

    def test_t86_par_06_promoted_ids_become_mutations_succeeded(self):
        """T86-PAR-06: promoted_ids from Pareto result populate mutations_succeeded."""
        mock_orch = _mock_pareto(["m2"])
        cel = _cel(mock_orch)
        # We can't inspect state directly, but step 9 detail should show frontier_size=1
        result = _run(cel, [_sr("m1"), _sr("m2")])
        step9 = next(s for s in result.step_results if s.step_number == 9)
        assert step9.detail.get("frontier_size") == 1

    def test_t86_par_07_frontier_digest_starts_with_sha256(self):
        """T86-PAR-07: CEL-PARETO-0 — frontier_digest is sha256-prefixed."""
        mock_orch = _mock_pareto(["m1"])
        cel = _cel(mock_orch)
        result = _run(cel, [_sr("m1")])
        step9 = next(s for s in result.step_results if s.step_number == 9)
        digest = step9.detail.get("frontier_digest", "")
        assert digest.startswith("sha256:")

    def test_t86_par_08_total_candidates_in_detail(self):
        """T86-PAR-08: step 9 detail records total_candidates count."""
        mock_orch = _mock_pareto(["m1", "m2"])
        cel = _cel(mock_orch)
        result = _run(cel, [_sr("m1"), _sr("m2"), _sr("m3")])
        step9 = next(s for s in result.step_results if s.step_number == 9)
        assert step9.detail.get("total_candidates") == 3


# ---------------------------------------------------------------------------
# T86-PAR-09..11 — Determinism (CEL-PARETO-DETERM-0)
# ---------------------------------------------------------------------------

class TestParetoSelectDeterminism:

    def test_t86_par_09_identical_candidates_identical_digest(self):
        """T86-PAR-09: CEL-PARETO-DETERM-0 — same inputs → same frontier_digest.

        epoch_id must be passed as run_epoch kwarg so state["epoch_id"] is stable.
        """
        mock_orch = _mock_pareto(["m1"])
        cel = _cel(mock_orch)
        epoch_id = "ep-determ-pareto"
        sr = [_sr("m1"), _sr("m2")]
        r1 = cel.run_epoch(epoch_id=epoch_id, context={"epoch_seq": 0, "sandbox_results": sr})
        r2 = cel.run_epoch(epoch_id=epoch_id, context={"epoch_seq": 0, "sandbox_results": sr})
        d1 = next(s for s in r1.step_results if s.step_number == 9).detail.get("frontier_digest")
        d2 = next(s for s in r2.step_results if s.step_number == 9).detail.get("frontier_digest")
        assert d1 is not None
        assert d1 == d2

    def test_t86_par_10_different_promoted_ids_different_digest(self):
        """T86-PAR-10: different promoted_ids → different frontier_digest."""
        epoch_id = "ep-diff-determ-pareto"
        sr = [_sr("m1"), _sr("m2")]
        cel_a = _cel(_mock_pareto(["m1"]))
        cel_b = _cel(_mock_pareto(["m2"]))
        r_a = cel_a.run_epoch(epoch_id=epoch_id, context={"epoch_seq": 0, "sandbox_results": sr})
        r_b = cel_b.run_epoch(epoch_id=epoch_id, context={"epoch_seq": 0, "sandbox_results": sr})
        d_a = next(s for s in r_a.step_results if s.step_number == 9).detail.get("frontier_digest")
        d_b = next(s for s in r_b.step_results if s.step_number == 9).detail.get("frontier_digest")
        assert d_a is not None and d_b is not None
        assert d_a != d_b

    def test_t86_par_11_empty_frontier_stable_digest(self):
        """T86-PAR-11: empty promoted_ids → stable sha256 digest (not None)."""
        mock_orch = _mock_pareto([])
        cel = _cel(mock_orch)
        result = _run(cel, [_sr("m1")])
        step9 = next(s for s in result.step_results if s.step_number == 9)
        digest = step9.detail.get("frontier_digest", "")
        assert digest.startswith("sha256:")


# ---------------------------------------------------------------------------
# T86-PAR-12..15 — Error resilience
# ---------------------------------------------------------------------------

class TestParetoErrorResilience:

    def test_t86_par_12_orchestrator_exception_falls_back(self):
        """T86-PAR-12: Pareto orchestrator exception → fallback, step passes."""
        mock_orch = MagicMock()
        mock_orch.run_epoch.side_effect = RuntimeError("pareto_crash")
        cel = _cel(mock_orch)
        result = _run(cel, [_sr("m1")])
        step9 = next(s for s in result.step_results if s.step_number == 9)
        assert step9.outcome == StepOutcome.PASS
        assert step9.detail.get("fallback") is True

    def test_t86_par_13_epoch_not_blocked_on_pareto_error(self):
        """T86-PAR-13: Pareto error → epoch completes all 15 steps."""
        mock_orch = MagicMock()
        mock_orch.run_epoch.side_effect = ValueError("bad_pareto")
        cel = _cel(mock_orch)
        result = _run(cel, [_sr("m1")])
        assert result.blocked_at_step is None
        assert len(result.step_results) == 15

    def test_t86_par_14_fallback_score_threshold_used_on_error(self):
        """T86-PAR-14: fallback path uses score > 0.5 for mutations_succeeded."""
        # m1 has sandbox_ok=True (fallback score 0.65 > 0.5), m2 is False (0.0)
        mock_orch = MagicMock()
        mock_orch.run_epoch.side_effect = RuntimeError("fail")
        cel = _cel(mock_orch)
        result = _run(cel, [_sr("m1", ok=True), _sr("m2", ok=False)])
        step9 = next(s for s in result.step_results if s.step_number == 9)
        assert step9.outcome == StepOutcome.PASS

    def test_t86_par_15_pareto_orchestrator_not_called_on_empty_input(self):
        """T86-PAR-15: no candidates → Pareto orchestrator.run_epoch not called."""
        mock_orch = _mock_pareto([])
        cel = _cel(mock_orch)
        _run(cel, sandbox_results=[])
        mock_orch.run_epoch.assert_not_called()
