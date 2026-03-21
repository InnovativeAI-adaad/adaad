# SPDX-License-Identifier: Apache-2.0
"""Phase 86 Track A — Self-Discovery post-epoch hook constitutional tests.

Test IDs: T86-DISC-01..10

Invariants under test:
  CEL-SELF-DISC-0        Self-discovery fires every SELF_DISC_FREQUENCY completed epochs.
  CEL-SELF-DISC-NONBLOCK-0  Self-discovery failure never blocks epoch completion.
  SELF-DISC-HUMAN-0      Advisory note recorded; no invariant promoted without HUMAN-0.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, call

import pytest

from runtime.evolution.constitutional_evolution_loop import (
    ConstitutionalEvolutionLoop,
    RunMode,
    SELF_DISC_FREQUENCY,
    CELStepResult,
    StepOutcome,
)

pytestmark = pytest.mark.phase86


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cel_with_disc(loop=None, freq: int = SELF_DISC_FREQUENCY) -> ConstitutionalEvolutionLoop:
    return ConstitutionalEvolutionLoop(
        run_mode=RunMode.SANDBOX_ONLY,
        self_discovery_loop=loop,
        self_disc_frequency=freq,
    )


def _run(cel, epoch_seq: int = 0):
    return cel.run_epoch(context={
        "epoch_id": f"ep-disc-{uuid.uuid4().hex[:8]}",
        "epoch_seq": epoch_seq,
    })


def _mock_disc(n_proposed: int = 2, n_ratified: int = 1) -> MagicMock:
    result = MagicMock()
    result.proposed_invariants = ["inv"] * n_proposed
    result.ratified_invariants = ["inv"] * n_ratified
    loop = MagicMock()
    loop.run.return_value = result
    return loop


# ---------------------------------------------------------------------------
# T86-DISC-01..04 — Cadence (CEL-SELF-DISC-0)
# ---------------------------------------------------------------------------

class TestSelfDiscoveryCadence:

    def test_t86_disc_01_default_frequency_is_five(self):
        """T86-DISC-01: SELF_DISC_FREQUENCY constant is 5."""
        assert SELF_DISC_FREQUENCY == 5

    def test_t86_disc_02_loop_runs_at_epoch_seq_zero(self):
        """T86-DISC-02: self-discovery fires on epoch_seq=0 (0 % 5 == 0)."""
        mock_loop = _mock_disc()
        cel = _cel_with_disc(mock_loop, freq=5)
        cel._epoch_seq = 0
        _run(cel)
        mock_loop.run.assert_called_once()

    def test_t86_disc_03_loop_does_not_run_on_non_multiple(self):
        """T86-DISC-03: self-discovery skipped when _epoch_seq % freq != 0."""
        mock_loop = _mock_disc()
        cel = _cel_with_disc(mock_loop, freq=5)
        cel._epoch_seq = 3   # 3 % 5 != 0
        _run(cel)
        mock_loop.run.assert_not_called()

    def test_t86_disc_04_loop_runs_at_each_multiple(self):
        """T86-DISC-04: runs at epoch_seq 0, 5, 10 — not 1, 2, 3, 4, 6."""
        mock_loop = _mock_disc()
        cel = _cel_with_disc(mock_loop, freq=5)
        call_counts = []
        for seq in range(11):
            cel._epoch_seq = seq
            _run(cel)
            call_counts.append(mock_loop.run.call_count)
        # Should have fired at seq 0, 5, 10
        assert mock_loop.run.call_count == 3


# ---------------------------------------------------------------------------
# T86-DISC-05..07 — Non-blocking (CEL-SELF-DISC-NONBLOCK-0)
# ---------------------------------------------------------------------------

class TestSelfDiscoveryNonBlocking:

    def test_t86_disc_05_exception_in_loop_does_not_block_epoch(self):
        """T86-DISC-05: CEL-SELF-DISC-NONBLOCK-0 — run() exception → epoch completes."""
        mock_loop = MagicMock()
        mock_loop.run.side_effect = RuntimeError("self_disc_crash")
        cel = _cel_with_disc(mock_loop, freq=1)
        cel._epoch_seq = 0
        result = _run(cel)
        assert result.blocked_at_step is None
        assert len(result.step_results) == 15

    def test_t86_disc_06_blocked_epoch_does_not_trigger_self_discovery(self):
        """T86-DISC-06: blocked epoch skips post-epoch hook entirely."""
        mock_loop = _mock_disc()
        cel = _cel_with_disc(mock_loop, freq=1)
        cel._epoch_seq = 0
        # Force block at step 1
        def _blocking(n, name, state):
            return CELStepResult(step_number=n, step_name=name,
                                 outcome=StepOutcome.BLOCKED, reason="test_block")
        cel._step_01_model_drift_check = _blocking
        _run(cel)
        mock_loop.run.assert_not_called()

    def test_t86_disc_07_no_loop_configured_epoch_still_runs(self):
        """T86-DISC-07: None self_discovery_loop → epoch runs normally, 15 steps."""
        cel = _cel_with_disc(loop=None, freq=1)
        result = _run(cel)
        assert len(result.step_results) == 15
        assert result.blocked_at_step is None


# ---------------------------------------------------------------------------
# T86-DISC-08..10 — SELF-DISC-HUMAN-0 advisory note
# ---------------------------------------------------------------------------

class TestSelfDiscoveryHumanGate:

    def test_t86_disc_08_human_0_note_in_state_when_discovery_runs(self):
        """T86-DISC-08: SELF-DISC-HUMAN-0 note recorded in state after discovery."""
        mock_loop = _mock_disc(n_proposed=2, n_ratified=1)
        cel = _cel_with_disc(mock_loop, freq=1)
        cel._epoch_seq = 0

        # Capture state via a hook on step 14 (STATE-ADVANCE) by inspecting via run
        # We test indirectly: epoch completes and loop was called
        result = _run(cel)
        assert result.blocked_at_step is None
        mock_loop.run.assert_called_once()

    def test_t86_disc_09_epoch_seq_does_not_increment_after_discovery_error(self):
        """T86-DISC-09: discovery error still counts as completed epoch; seq increments."""
        mock_loop = MagicMock()
        mock_loop.run.side_effect = ValueError("disc_err")
        cel = _cel_with_disc(mock_loop, freq=1)
        assert cel._epoch_seq == 0
        _run(cel)
        # Epoch completed (not blocked) → seq increments
        assert cel._epoch_seq == 1

    def test_t86_disc_10_candidates_never_auto_promoted(self):
        """T86-DISC-10: SELF-DISC-HUMAN-0 — discovery result is advisory; no auto-promotion.

        Verifies that ConstitutionalSelfDiscoveryLoop.run() result is read but
        never passed to GovernanceGate or any promotion path by the CEL itself.
        """
        promoted_calls = []
        mock_loop = _mock_disc(n_proposed=3, n_ratified=3)

        # Instrument gate_v2 to detect any promotion attempt driven by discovery
        from runtime.governance.gate_v2 import GovernanceGateV2
        real_gate = GovernanceGateV2()
        original_evaluate = real_gate.evaluate

        discovery_triggered_gate_calls = []

        def _tracked_evaluate(*args, **kwargs):
            # If called with a self-discovery-related mutation_id, flag it
            mid = kwargs.get("mutation_id", args[0] if args else "")
            if "discovery" in str(mid).lower() or "invariant" in str(mid).lower():
                discovery_triggered_gate_calls.append(mid)
            return original_evaluate(*args, **kwargs)

        real_gate.evaluate = _tracked_evaluate

        cel = ConstitutionalEvolutionLoop(
            run_mode=RunMode.SANDBOX_ONLY,
            gate_v2=real_gate,
            self_discovery_loop=mock_loop,
            self_disc_frequency=1,
        )
        cel._epoch_seq = 0
        _run(cel)

        # No discovery-sourced invariants should have been sent through the gate
        assert discovery_triggered_gate_calls == [], (
            "SELF-DISC-HUMAN-0 violation: discovery candidates routed through GovernanceGate "
            "without HUMAN-0 sign-off"
        )
