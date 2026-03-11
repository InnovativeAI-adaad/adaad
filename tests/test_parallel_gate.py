# SPDX-License-Identifier: Apache-2.0
"""Tests for runtime.governance.parallel_gate."""

from __future__ import annotations

import time

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.gate import GateAxisResult
from runtime.governance.parallel_gate import (
    PARALLEL_GATE_VERSION,
    ParallelAxisSpec,
    ParallelGovernanceGate,
)


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _always_pass() -> tuple[bool, str]:
    return True, "ok"


def _always_fail() -> tuple[bool, str]:
    return False, "rule_violation"


def _slow_pass(delay: float = 0.05) -> tuple[bool, str]:
    time.sleep(delay)
    return True, "ok_after_delay"


def _law_pass(ctx):
    class _Decision:
        passed = True
        decision = "pass"
        reason_codes: list = []
        failed_rules: list = []
    return _Decision()


def _law_fail(ctx):
    class _Decision:
        passed = False
        decision = "reject"
        reason_codes = ["founders_law_violation"]
        failed_rules = [{"axis": "founders_law", "rule_id": "core_rule"}]
    return _Decision()


def _noop_tx(event_type, payload):
    return {}


# ---------------------------------------------------------------------------
# evaluate_axes_parallel
# ---------------------------------------------------------------------------


def test_all_axes_pass():
    gate = ParallelGovernanceGate(law_enforcer=_law_pass, tx_writer=_noop_tx)
    specs = [
        ParallelAxisSpec("entropy", "budget_ok", _always_pass),
        ParallelAxisSpec("constitution", "tier_ok", _always_pass),
        ParallelAxisSpec("replay", "digest_ok", _always_pass),
    ]
    results = gate.evaluate_axes_parallel(specs)
    assert len(results) == 3
    assert all(r.ok for r in results)


def test_results_are_sorted_deterministically():
    gate = ParallelGovernanceGate(law_enforcer=_law_pass, tx_writer=_noop_tx)
    specs = [
        ParallelAxisSpec("z_axis", "rule_z", _always_pass),
        ParallelAxisSpec("a_axis", "rule_a", _always_pass),
        ParallelAxisSpec("m_axis", "rule_m", _always_pass),
    ]
    results = gate.evaluate_axes_parallel(specs)
    axes = [r.axis for r in results]
    assert axes == sorted(axes)


def test_failed_axis_recorded():
    gate = ParallelGovernanceGate(law_enforcer=_law_pass, tx_writer=_noop_tx)
    specs = [
        ParallelAxisSpec("entropy", "budget_ok", _always_pass),
        ParallelAxisSpec("constitution", "tier_ok", _always_fail),
    ]
    results = gate.evaluate_axes_parallel(specs)
    failed = [r for r in results if not r.ok]
    assert len(failed) == 1
    assert failed[0].axis == "constitution"
    assert "rule_violation" in failed[0].reason


def test_timeout_axis_recorded_as_failure():
    gate = ParallelGovernanceGate(law_enforcer=_law_pass, tx_writer=_noop_tx)
    # Give the axis 0.001 s timeout but the probe sleeps 0.5 s
    specs = [
        ParallelAxisSpec("slow", "slow_rule", lambda: _slow_pass(0.5), timeout_seconds=0.001),
    ]
    results = gate.evaluate_axes_parallel(specs)
    assert len(results) == 1
    assert results[0].ok is False
    assert "axis_timeout" in results[0].reason


def test_exception_in_axis_recorded_as_failure():
    def _boom() -> tuple[bool, str]:
        raise RuntimeError("probe_explosion")

    gate = ParallelGovernanceGate(law_enforcer=_law_pass, tx_writer=_noop_tx)
    specs = [ParallelAxisSpec("exploding", "rule_x", _boom)]
    results = gate.evaluate_axes_parallel(specs)
    assert results[0].ok is False
    assert "axis_exception" in results[0].reason


# ---------------------------------------------------------------------------
# approve_mutation_parallel
# ---------------------------------------------------------------------------


def test_approve_all_pass():
    gate = ParallelGovernanceGate(law_enforcer=_law_pass, tx_writer=_noop_tx)
    specs = [
        ParallelAxisSpec("entropy", "budget_ok", _always_pass),
        ParallelAxisSpec("constitution", "tier_ok", _always_pass),
    ]
    decision = gate.approve_mutation_parallel(
        mutation_id="mut_001",
        trust_mode="standard",
        axis_specs=specs,
    )
    assert decision.approved is True
    assert decision.decision == "approve"
    assert decision.mutation_id == "mut_001"


def test_reject_when_axis_fails():
    gate = ParallelGovernanceGate(law_enforcer=_law_pass, tx_writer=_noop_tx)
    specs = [
        ParallelAxisSpec("entropy", "budget_ok", _always_pass),
        ParallelAxisSpec("constitution", "tier_ok", _always_fail),
    ]
    decision = gate.approve_mutation_parallel(
        mutation_id="mut_002",
        trust_mode="standard",
        axis_specs=specs,
    )
    assert decision.approved is False
    assert decision.decision == "reject"


def test_reject_when_law_fails():
    gate = ParallelGovernanceGate(law_enforcer=_law_fail, tx_writer=_noop_tx)
    specs = [ParallelAxisSpec("entropy", "budget_ok", _always_pass)]
    decision = gate.approve_mutation_parallel(
        mutation_id="mut_003",
        trust_mode="standard",
        axis_specs=specs,
    )
    assert decision.approved is False
    assert "founders_law_violation" in decision.reason_codes


def test_decision_id_is_deterministic_for_identical_inputs():
    """Same axes + same outcomes must produce the same decision_id."""
    gate = ParallelGovernanceGate(law_enforcer=_law_pass, tx_writer=_noop_tx)

    def _make_specs():
        return [
            ParallelAxisSpec("entropy", "budget_ok", _always_pass),
            ParallelAxisSpec("constitution", "tier_ok", _always_pass),
        ]

    d1 = gate.approve_mutation_parallel(
        mutation_id="mut_det", trust_mode="standard", axis_specs=_make_specs()
    )
    d2 = gate.approve_mutation_parallel(
        mutation_id="mut_det", trust_mode="standard", axis_specs=_make_specs()
    )
    assert d1.decision_id == d2.decision_id


def test_tx_writer_called():
    events = []

    def _capture_tx(event_type, payload):
        events.append((event_type, payload))
        return {}

    gate = ParallelGovernanceGate(law_enforcer=_law_pass, tx_writer=_capture_tx)
    specs = [ParallelAxisSpec("entropy", "budget_ok", _always_pass)]
    gate.approve_mutation_parallel(
        mutation_id="mut_tx", trust_mode="standard", axis_specs=specs
    )
    assert len(events) == 1
    assert events[0][0] == "mutation_parallel_gate_decision"
