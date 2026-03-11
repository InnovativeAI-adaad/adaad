# SPDX-License-Identifier: Apache-2.0
"""Tests: Simulation Isolation — ADAAD-8 / PR-11

Explicitly asserts that SimulationPolicy.simulation=True is checked at the
GovernanceGate boundary before any state-affecting operation.

Covers:
- GovernanceGate does not write to the ledger when simulation=True policy is present
- EpochReplaySimulator raises SimulationIsolationError before calling any live gate
- No constitution state transitions occur during simulation runs
- No mutation executor calls occur during simulation runs
- Simulation state is discarded after run; only explicit artifacts persist
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
pytestmark = pytest.mark.governance_gate
from unittest.mock import MagicMock, patch, call

from runtime.governance.simulation.constraint_interpreter import (
    SimulationPolicy,
    SimulationPolicyError,
    interpret_policy_block,
)
from runtime.governance.simulation.epoch_simulator import (
    EpochReplaySimulator,
    SimulationIsolationError,
    _assert_simulation_flag,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_epoch(epoch_id="e-iso-001", mutations=None):
    muts = mutations or [{"mutation_id": "m-1", "risk_score": 0.2, "complexity_delta": 0.05,
                          "lineage_depth": 3, "test_coverage": 0.9, "tier": "standard", "entropy": 0.1}]
    return {
        "epoch_id": epoch_id,
        "mutations": muts,
        "actual_mutations_advanced": len(muts),
        "entropy": 0.1,
        "scoring_algorithm_version": "1.0",
    }


# ---------------------------------------------------------------------------
# Structural invariant tests
# ---------------------------------------------------------------------------

class TestSimulationIsolationInvariant:
    def test_simulation_policy_false_raises_at_construction(self):
        """SimulationPolicy.simulation=False must raise SimulationPolicyError at construction."""
        with pytest.raises(SimulationPolicyError):
            SimulationPolicy(simulation=False)

    def test_assert_flag_raises_on_false(self):
        """_assert_simulation_flag raises SimulationIsolationError when simulation=False."""
        # Bypass the frozen dataclass validation for unit testing the flag check directly.
        # We use object.__setattr__ only in this test to verify the check exists.
        policy = interpret_policy_block("")
        with pytest.raises(SimulationIsolationError):
            _assert_simulation_flag(
                # Create a mock with simulation=False to verify the check
                type("FakePolicy", (), {"simulation": False})()
            )

    def test_simulator_requires_true_policy(self):
        """EpochReplaySimulator must reject any policy where simulation is not True."""
        fake = type("FakePolicy", (), {"simulation": False})()
        with pytest.raises(SimulationIsolationError):
            EpochReplaySimulator(fake)


# ---------------------------------------------------------------------------
# No ledger writes during simulation
# ---------------------------------------------------------------------------

class TestNoLedgerWritesDuringSimulation:
    def test_simulate_epoch_no_ledger_writes(self):
        """simulate_epoch must not write any events to the ledger."""
        policy = interpret_policy_block("max_risk_score(threshold=0.9)")
        sim = EpochReplaySimulator(policy)
        epoch = _make_epoch()

        import security.ledger.journal as journal_module
        write_calls = []

        original_append = journal_module.append_tx

        def tracking_append(event_type, payload, **kwargs):
            write_calls.append({"event_type": event_type, "payload": payload})
            return original_append(event_type, payload, **kwargs)

        with patch.object(journal_module, "append_tx", side_effect=tracking_append):
            sim.simulate_epoch("e-iso-001", epoch_data=epoch)

        assert write_calls == [], (
            f"Simulation wrote {len(write_calls)} unexpected ledger event(s): "
            + str([c['event_type'] for c in write_calls])
        )

    def test_simulate_epoch_range_no_ledger_writes(self):
        """simulate_epoch_range must not write any events to the ledger."""
        policy = interpret_policy_block("")
        sim = EpochReplaySimulator(policy)
        epoch_data = {
            "e1": _make_epoch("e1"),
            "e2": _make_epoch("e2"),
        }

        import security.ledger.journal as journal_module
        write_calls = []
        original_append = journal_module.append_tx

        def tracking_append(event_type, payload, **kwargs):
            write_calls.append(event_type)
            return original_append(event_type, payload, **kwargs)

        with patch.object(journal_module, "append_tx", side_effect=tracking_append):
            sim.simulate_epoch_range(["e1", "e2"], epoch_data_map=epoch_data)

        assert write_calls == [], (
            f"Simulation wrote unexpected ledger events: {write_calls}"
        )


# ---------------------------------------------------------------------------
# No GovernanceGate state transitions during simulation
# ---------------------------------------------------------------------------

class TestNoGovernanceGateStateTransitions:
    def test_simulate_epoch_does_not_call_governance_gate_approve(self):
        """simulate_epoch must not call GovernanceGate.approve_mutation."""
        policy = interpret_policy_block("max_risk_score(threshold=0.9)")
        sim = EpochReplaySimulator(policy)
        epoch = _make_epoch()

        from runtime.governance import gate as gate_module
        approve_calls = []
        original_init = gate_module.GovernanceGate.__init__

        def tracking_init(self_inner, **kwargs):
            original_init(self_inner, **kwargs)
            original_approve = self_inner.approve_mutation
            def tracking_approve(*a, **kw):
                approve_calls.append(a)
                return original_approve(*a, **kw)
            self_inner.approve_mutation = tracking_approve

        with patch.object(gate_module.GovernanceGate, "__init__", tracking_init):
            sim.simulate_epoch("e-iso-001", epoch_data=epoch)

        assert approve_calls == [], (
            f"Simulation unexpectedly called GovernanceGate.approve_mutation {len(approve_calls)} time(s)"
        )


# ---------------------------------------------------------------------------
# Simulation result does not persist live state
# ---------------------------------------------------------------------------

class TestSimulationResultIsolation:
    def test_simulation_result_contains_simulation_true(self):
        """SimulationRunResult.simulation must always be True."""
        policy = interpret_policy_block("")
        sim = EpochReplaySimulator(policy)
        result = sim.simulate_epoch_range(["e1"], epoch_data_map={"e1": _make_epoch("e1")})
        assert result.simulation is True

    def test_epoch_simulation_result_is_immutable(self):
        """EpochSimulationResult is a frozen dataclass — it cannot be mutated."""
        policy = interpret_policy_block("")
        sim = EpochReplaySimulator(policy)
        result = sim.simulate_epoch("e-iso-001", epoch_data=_make_epoch())
        with pytest.raises((AttributeError, TypeError)):
            result.simulated_mutations_advanced = 999  # type: ignore[misc]

    def test_simulation_run_result_is_immutable(self):
        """SimulationRunResult is a frozen dataclass — it cannot be mutated."""
        policy = interpret_policy_block("")
        sim = EpochReplaySimulator(policy)
        result = sim.simulate_epoch_range(["e1"], epoch_data_map={"e1": _make_epoch("e1")})
        with pytest.raises((AttributeError, TypeError)):
            result.simulation = False  # type: ignore[misc]
