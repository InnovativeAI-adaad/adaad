# SPDX-License-Identifier: Apache-2.0
"""Tests for runtime.evolution.entropy_fast_gate."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.entropy_fast_gate import (
    DEFAULT_DENY_BITS,
    DEFAULT_WARN_BITS,
    EntropyFastGate,
    EntropyGateResult,
    FAST_GATE_VERSION,
    GateVerdict,
    ZERO_COST_SOURCES,
)


@pytest.fixture()
def gate() -> EntropyFastGate:
    return EntropyFastGate()


@pytest.fixture()
def permissive_gate() -> EntropyFastGate:
    return EntropyFastGate(strict=False)


# ---------------------------------------------------------------------------
# ALLOW cases
# ---------------------------------------------------------------------------


def test_low_entropy_allows(gate):
    result = gate.evaluate(
        mutation_id="mut_001",
        estimated_bits=10,
        sources=["mutation_ops"],
    )
    assert result.verdict is GateVerdict.ALLOW
    assert result.denied is False


def test_zero_bits_allows(gate):
    result = gate.evaluate(mutation_id="mut_002", estimated_bits=0, sources=[])
    assert result.verdict is GateVerdict.ALLOW


def test_zero_cost_sources_do_not_escalate(gate):
    result = gate.evaluate(
        mutation_id="mut_003",
        estimated_bits=5,
        sources=list(ZERO_COST_SOURCES),
    )
    assert result.verdict is GateVerdict.ALLOW
    assert result.active_sources == ()


# ---------------------------------------------------------------------------
# WARN cases
# ---------------------------------------------------------------------------


def test_bits_at_warn_threshold_warns(gate):
    result = gate.evaluate(
        mutation_id="mut_010",
        estimated_bits=DEFAULT_WARN_BITS,
        sources=["prng", "mutation_ops"],
    )
    assert result.verdict is GateVerdict.WARN


def test_bits_between_warn_and_deny_warns(gate):
    mid = (DEFAULT_WARN_BITS + DEFAULT_DENY_BITS) // 2
    result = gate.evaluate(mutation_id="mut_011", estimated_bits=mid, sources=["clock"])
    assert result.verdict is GateVerdict.WARN


# ---------------------------------------------------------------------------
# DENY cases
# ---------------------------------------------------------------------------


def test_bits_at_deny_threshold_denies(gate):
    result = gate.evaluate(
        mutation_id="mut_020",
        estimated_bits=DEFAULT_DENY_BITS,
        sources=["prng"],
    )
    assert result.verdict is GateVerdict.DENY
    assert result.denied is True


def test_network_source_denies_in_strict_mode(gate):
    result = gate.evaluate(
        mutation_id="mut_021",
        estimated_bits=5,
        sources=["network", "mutation_ops"],
    )
    assert result.verdict is GateVerdict.DENY
    assert "nondeterministic_source" in result.reason


def test_sandbox_nondeterminism_denies_in_strict_mode(gate):
    result = gate.evaluate(
        mutation_id="mut_022",
        estimated_bits=1,
        sources=["sandbox_nondeterminism"],
    )
    assert result.verdict is GateVerdict.DENY


def test_runtime_rng_denies_in_strict_mode(gate):
    result = gate.evaluate(
        mutation_id="mut_023",
        estimated_bits=1,
        sources=["runtime_rng"],
    )
    assert result.verdict is GateVerdict.DENY


# ---------------------------------------------------------------------------
# Permissive (strict=False) mode
# ---------------------------------------------------------------------------


def test_nondeterministic_source_warns_in_permissive_mode(permissive_gate):
    result = permissive_gate.evaluate(
        mutation_id="mut_030",
        estimated_bits=5,
        sources=["network"],
    )
    assert result.verdict is GateVerdict.WARN


# ---------------------------------------------------------------------------
# Custom thresholds
# ---------------------------------------------------------------------------


def test_custom_thresholds():
    gate = EntropyFastGate(warn_bits=10, deny_bits=20)
    r_allow = gate.evaluate(mutation_id="m1", estimated_bits=9, sources=["prng"])
    r_warn = gate.evaluate(mutation_id="m2", estimated_bits=10, sources=["prng"])
    r_deny = gate.evaluate(mutation_id="m3", estimated_bits=20, sources=["prng"])
    assert r_allow.verdict is GateVerdict.ALLOW
    assert r_warn.verdict is GateVerdict.WARN
    assert r_deny.verdict is GateVerdict.DENY


def test_invalid_thresholds_raise():
    with pytest.raises(ValueError, match="entropy_gate_invalid_thresholds"):
        EntropyFastGate(warn_bits=50, deny_bits=10)
    with pytest.raises(ValueError):
        EntropyFastGate(warn_bits=-1, deny_bits=10)


# ---------------------------------------------------------------------------
# Digest determinism
# ---------------------------------------------------------------------------


def test_identical_inputs_produce_identical_digest(gate):
    r1 = gate.evaluate(mutation_id="mut_x", estimated_bits=15, sources=["prng"])
    r2 = gate.evaluate(mutation_id="mut_x", estimated_bits=15, sources=["prng"])
    assert r1.gate_digest == r2.gate_digest


def test_different_mutation_ids_produce_different_digest(gate):
    r1 = gate.evaluate(mutation_id="mut_a", estimated_bits=5, sources=["prng"])
    r2 = gate.evaluate(mutation_id="mut_b", estimated_bits=5, sources=["prng"])
    assert r1.gate_digest != r2.gate_digest


# ---------------------------------------------------------------------------
# to_payload roundtrip
# ---------------------------------------------------------------------------


def test_to_payload_structure(gate):
    result = gate.evaluate(mutation_id="mut_p", estimated_bits=10, sources=["prng"])
    payload = result.to_payload()
    assert payload["mutation_id"] == "mut_p"
    assert payload["gate_version"] == FAST_GATE_VERSION
    assert "verdict" in payload
    assert "gate_digest" in payload
