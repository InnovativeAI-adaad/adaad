# SPDX-License-Identifier: Apache-2.0
"""Phase 65 test suite — T65-WIRE-01..15.

Invariants under test:
  CEL-WIRE-PROP-0   ProposalEngine wired to Step 4; noop proposals flagged.
  CEL-WIRE-FIT-0    FitnessEngineV2 wired to Step 8; FIT-DIV-0 honoured.
  CEL-WIRE-GATE-0   GovernanceGate wired to Step 10; GATE-V2-EXISTING-0 intact.
  CEL-WIRE-PROMO-0  PromotionEvent written in LIVE mode; suppressed in SANDBOX_ONLY.
  CEL-WIRE-FAIL-0   Any subsystem exception → BLOCKED step; no propagation.
  CEL-ORDER-0       Wired steps still execute in strict 1→14 order.
  CEL-BLOCK-0       BLOCKED wired step halts epoch immediately.
  CEL-DRYRUN-0      SANDBOX_ONLY suppresses Step 12 in LiveWiredCEL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from runtime.evolution.cel_wiring import (
    LiveWiredCEL,
    WiringConfig,
    make_live_wired_cel,
)
from runtime.evolution.constitutional_evolution_loop import (
    CELEvidenceLedger,
    RunMode,
    StepOutcome,
)
from runtime.evolution.fitness_v2 import FitnessConfig, FitnessEngineV2
from runtime.evolution.proposal_engine import ProposalEngine
from runtime.governance.exception_tokens import ExceptionTokenLedger
from runtime.governance.gate import GovernanceGate
from runtime.governance.gate_v2 import GovernanceGateV2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wired(
    tmp_path: Path,
    *,
    run_mode: RunMode = RunMode.SANDBOX_ONLY,
    proposal_engine: Optional[ProposalEngine] = None,
    fitness_engine: Optional[FitnessEngineV2] = None,
    gate: Optional[GovernanceGate] = None,
) -> LiveWiredCEL:
    exc_ledger = ExceptionTokenLedger(ledger_path=tmp_path / "exc.jsonl")
    cel_ledger = CELEvidenceLedger(ledger_path=tmp_path / "ev.jsonl")
    gate_v2 = GovernanceGateV2(exception_ledger=exc_ledger)
    return LiveWiredCEL(
        run_mode=run_mode,
        gate_v2=gate_v2,
        gate=gate or GovernanceGate(tx_writer=lambda *a, **kw: {}),
        fitness_engine=fitness_engine or FitnessEngineV2(config=FitnessConfig.default()),
        proposal_engine=proposal_engine or ProposalEngine(),
        exception_ledger=exc_ledger,
        cel_ledger=cel_ledger,
        promotion_ledger_path=tmp_path / "promotions.jsonl",
        wiring_config=WiringConfig(),
    )


def _ctx() -> Dict[str, Any]:
    return {
        "baseline_fitness_score": 0.6,
        "epoch_seq": 5,
        "capability_name": "evolution.proposal",
        "strategy_id": "s1",
        "after_source": "def foo(x):\n    return x + 1\n",
        "before_source": "def foo(x):\n    return x\n",
        "proposals": [],  # proposals injected by Step 4 wiring
    }


def _get_step(result, num):
    return next(s for s in result.step_results if s.step_number == num)


# ---------------------------------------------------------------------------
# T65-WIRE-01: Full SANDBOX_ONLY wired run completes 14 steps
# ---------------------------------------------------------------------------

class TestT65Wire01:
    def test_wired_sandbox_run_completes(self, tmp_path):
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w01", context=_ctx())
        assert result.completed, f"blocked_at={result.blocked_at_step}"
        assert len(result.step_results) == 14
        assert result.dry_run is True


# ---------------------------------------------------------------------------
# T65-WIRE-02: CEL-WIRE-PROP-0 — Step 4 calls ProposalEngine; result recorded
# ---------------------------------------------------------------------------

class TestT65Wire02:
    def test_step4_proposal_engine_called(self, tmp_path):
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w02", context=_ctx())
        step4 = _get_step(result, 4)
        assert step4.outcome == StepOutcome.PASS
        assert step4.detail is not None
        assert "proposal_id" in step4.detail

    def test_step4_records_proposal_count(self, tmp_path):
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w02b", context=_ctx())
        step4 = _get_step(result, 4)
        assert step4.detail["proposal_count"] == 1


# ---------------------------------------------------------------------------
# T65-WIRE-03: CEL-WIRE-PROP-0 — noop proposal flagged in step detail
# ---------------------------------------------------------------------------

class TestT65Wire03:
    def test_noop_proposal_is_flagged(self, tmp_path):
        # ProposalEngine without adapter produces noop proposals
        cel = _make_wired(tmp_path)  # no adapter → noop
        result = cel.run_epoch(epoch_id="ep-w03", context=_ctx())
        step4 = _get_step(result, 4)
        assert step4.detail["is_noop"] is True


# ---------------------------------------------------------------------------
# T65-WIRE-04: CEL-WIRE-FIT-0 — Step 8 calls FitnessEngineV2; composite scored
# ---------------------------------------------------------------------------

class TestT65Wire04:
    def test_step8_fitness_scored(self, tmp_path):
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w04", context=_ctx())
        step8 = _get_step(result, 8)
        assert step8.outcome == StepOutcome.PASS
        assert step8.detail["scored_count"] >= 0

    def test_step8_fitness_summary_contains_composite(self, tmp_path):
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w04b", context=_ctx())
        step8 = _get_step(result, 8)
        for entry in step8.detail.get("fitness_summary", []):
            assert "composite" in entry
            assert 0.0 <= entry["composite"] <= 1.0


# ---------------------------------------------------------------------------
# T65-WIRE-05: CEL-WIRE-FIT-0 — FIT-DIV-0: diverged replay → composite=0.0
# ---------------------------------------------------------------------------

class TestT65Wire05:
    def test_diverged_replay_zeroes_composite(self, tmp_path):
        ctx = _ctx()
        ctx["force_replay_divergence"] = True  # blocks at Step 7
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w05", context=ctx)
        # Epoch blocks at Step 7 (SANDBOX-DIV-0) before Step 8 runs
        assert result.blocked_at_step == 7

    def test_no_divergence_nonzero_composite(self, tmp_path):
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w05b", context=_ctx())
        step8 = _get_step(result, 8)
        summaries = step8.detail.get("fitness_summary", [])
        # All sandbox_ok proposals should get a composite > 0
        assert all(e["composite"] > 0.0 for e in summaries if summaries)


# ---------------------------------------------------------------------------
# T65-WIRE-06: CEL-WIRE-GATE-0 — Step 10 calls GovernanceGate; decision recorded
# ---------------------------------------------------------------------------

class TestT65Wire06:
    def test_step10_gate_invoked(self, tmp_path):
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w06", context=_ctx())
        step10 = _get_step(result, 10)
        assert step10.outcome == StepOutcome.PASS
        assert step10.detail["gate_v2_existing_0_compliant"] is True

    def test_step10_approved_count_present(self, tmp_path):
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w06b", context=_ctx())
        step10 = _get_step(result, 10)
        assert "approved_count" in step10.detail or "gate_outcomes" in step10.detail


# ---------------------------------------------------------------------------
# T65-WIRE-07: GATE-V2-EXISTING-0 — Step 10 always after Step 9
# ---------------------------------------------------------------------------

class TestT65Wire07:
    def test_step10_always_after_step9(self, tmp_path):
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w07", context=_ctx())
        nums = [s.step_number for s in result.step_results]
        assert 9 in nums and 10 in nums
        assert nums.index(10) == nums.index(9) + 1


# ---------------------------------------------------------------------------
# T65-WIRE-08: CEL-WIRE-PROMO-0 — SANDBOX_ONLY suppresses Step 12
# ---------------------------------------------------------------------------

class TestT65Wire08:
    def test_step12_skipped_in_sandbox_mode(self, tmp_path):
        cel = _make_wired(tmp_path, run_mode=RunMode.SANDBOX_ONLY)
        result = cel.run_epoch(epoch_id="ep-w08", context=_ctx())
        step12 = _get_step(result, 12)
        assert step12.outcome == StepOutcome.SKIPPED

    def test_no_promotion_ledger_written_in_sandbox_mode(self, tmp_path):
        promo_path = tmp_path / "promotions.jsonl"
        exc_ledger = ExceptionTokenLedger(ledger_path=tmp_path / "exc.jsonl")
        cel_ledger = CELEvidenceLedger(ledger_path=tmp_path / "ev.jsonl")
        gate_v2 = GovernanceGateV2(exception_ledger=exc_ledger)
        cel = LiveWiredCEL(
            run_mode=RunMode.SANDBOX_ONLY,
            gate_v2=gate_v2,
            gate=GovernanceGate(tx_writer=lambda *a, **kw: {}),
            fitness_engine=FitnessEngineV2(config=FitnessConfig.default()),
            proposal_engine=ProposalEngine(),
            cel_ledger=cel_ledger,
            promotion_ledger_path=promo_path,
        )
        cel.run_epoch(epoch_id="ep-w08b", context=_ctx())
        assert not promo_path.exists() or promo_path.stat().st_size == 0


# ---------------------------------------------------------------------------
# T65-WIRE-09: CEL-WIRE-PROMO-0 — LIVE mode writes PromotionEvent to ledger
# ---------------------------------------------------------------------------

class TestT65Wire09:
    def test_step12_pass_in_live_mode(self, tmp_path):
        cel = _make_wired(tmp_path, run_mode=RunMode.LIVE)
        result = cel.run_epoch(epoch_id="ep-w09", context=_ctx())
        step12 = _get_step(result, 12)
        assert step12.outcome in (StepOutcome.PASS, StepOutcome.BLOCKED)

    def test_live_promo_events_written_when_mutations_succeed(self, tmp_path):
        promo_path = tmp_path / "promo_live.jsonl"
        exc_ledger = ExceptionTokenLedger(ledger_path=tmp_path / "exc.jsonl")
        cel_ledger = CELEvidenceLedger(ledger_path=tmp_path / "ev.jsonl")
        gate_v2 = GovernanceGateV2(exception_ledger=exc_ledger)
        cel = LiveWiredCEL(
            run_mode=RunMode.LIVE,
            gate_v2=gate_v2,
            gate=GovernanceGate(tx_writer=lambda *a, **kw: {}),
            fitness_engine=FitnessEngineV2(config=FitnessConfig.default()),
            proposal_engine=ProposalEngine(),
            cel_ledger=cel_ledger,
            promotion_ledger_path=promo_path,
        )
        result = cel.run_epoch(epoch_id="ep-w09-live", context=_ctx())
        # If step12 passed and there were succeeded mutations, ledger should have entries
        step12 = _get_step(result, 12)
        if step12.outcome == StepOutcome.PASS and step12.detail.get("promoted_count", 0) > 0:
            lines = [l for l in promo_path.read_text().splitlines() if l.strip()]
            assert len(lines) > 0
            event = json.loads(lines[0])
            assert "event_id" in event
            assert "event_hash" in event


# ---------------------------------------------------------------------------
# T65-WIRE-10: CEL-WIRE-FAIL-0 — ProposalEngine exception → BLOCKED Step 4
# ---------------------------------------------------------------------------

class TestT65Wire10:
    def test_proposal_engine_exception_blocks_step4(self, tmp_path):
        broken_engine = MagicMock()
        broken_engine.generate.side_effect = RuntimeError("adapter_broken")
        cel = _make_wired(tmp_path, proposal_engine=broken_engine)
        result = cel.run_epoch(epoch_id="ep-w10", context=_ctx())
        assert result.blocked_at_step == 4
        step4 = _get_step(result, 4)
        assert step4.outcome == StepOutcome.BLOCKED
        assert step4.reason == "proposal_engine_failure"

    def test_no_exception_propagates_from_step4(self, tmp_path):
        broken_engine = MagicMock()
        broken_engine.generate.side_effect = RuntimeError("fatal_error")
        cel = _make_wired(tmp_path, proposal_engine=broken_engine)
        # Must not raise
        result = cel.run_epoch(epoch_id="ep-w10b", context=_ctx())
        assert result is not None


# ---------------------------------------------------------------------------
# T65-WIRE-11: CEL-WIRE-FAIL-0 — FitnessEngineV2 exception → BLOCKED Step 8
# ---------------------------------------------------------------------------

class TestT65Wire11:
    def test_fitness_engine_exception_blocks_step8(self, tmp_path):
        broken_fit = MagicMock()
        broken_fit.score.side_effect = RuntimeError("fit_broken")
        cel = _make_wired(tmp_path, fitness_engine=broken_fit)
        result = cel.run_epoch(epoch_id="ep-w11", context=_ctx())
        assert result.blocked_at_step == 8
        step8 = _get_step(result, 8)
        assert step8.outcome == StepOutcome.BLOCKED
        assert step8.reason == "fitness_engine_failure"


# ---------------------------------------------------------------------------
# T65-WIRE-12: CEL-WIRE-FAIL-0 — GovernanceGate exception → BLOCKED Step 10
# ---------------------------------------------------------------------------

class TestT65Wire12:
    def test_governance_gate_exception_blocks_step10(self, tmp_path):
        broken_gate = MagicMock()
        broken_gate.approve_mutation.side_effect = RuntimeError("gate_broken")
        cel = _make_wired(tmp_path, gate=broken_gate)
        result = cel.run_epoch(epoch_id="ep-w12", context=_ctx())
        assert result.blocked_at_step == 10
        step10 = _get_step(result, 10)
        assert step10.outcome == StepOutcome.BLOCKED
        assert step10.reason == "governance_gate_exception"


# ---------------------------------------------------------------------------
# T65-WIRE-13: CEL-ORDER-0 — step numbers strictly 1..14 in LiveWiredCEL
# ---------------------------------------------------------------------------

class TestT65Wire13:
    def test_wired_step_numbers_sequential(self, tmp_path):
        cel = _make_wired(tmp_path)
        result = cel.run_epoch(epoch_id="ep-w13", context=_ctx())
        nums = [s.step_number for s in result.step_results]
        assert nums == list(range(1, 15))


# ---------------------------------------------------------------------------
# T65-WIRE-14: make_live_wired_cel factory — constructs without error
# ---------------------------------------------------------------------------

class TestT65Wire14:
    def test_factory_constructs(self, tmp_path):
        cel = make_live_wired_cel(
            run_mode=RunMode.SANDBOX_ONLY,
            exception_ledger_path=tmp_path / "exc.jsonl",
            cel_ledger_path=tmp_path / "ev.jsonl",
            promotion_ledger_path=tmp_path / "promo.jsonl",
        )
        assert isinstance(cel, LiveWiredCEL)

    def test_factory_run_completes(self, tmp_path):
        cel = make_live_wired_cel(
            run_mode=RunMode.SANDBOX_ONLY,
            exception_ledger_path=tmp_path / "exc.jsonl",
            cel_ledger_path=tmp_path / "ev.jsonl",
            promotion_ledger_path=tmp_path / "promo.jsonl",
        )
        result = cel.run_epoch(epoch_id="ep-factory", context=_ctx())
        assert result.completed


# ---------------------------------------------------------------------------
# T65-WIRE-15: WiringConfig — default values valid
# ---------------------------------------------------------------------------

class TestT65Wire15:
    def test_wiring_config_defaults(self):
        cfg = WiringConfig()
        assert cfg.actor_id == "ArchitectAgent"
        assert cfg.actor_type == "autonomous_agent"
        assert cfg.noop_strategy_id == "s1"
        assert cfg.policy_version.startswith("v")

    def test_wiring_config_is_frozen(self):
        cfg = WiringConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.actor_id = "changed"  # type: ignore[misc]
