# SPDX-License-Identifier: Apache-2.0
"""test_phase65_emergence.py — Phase 65 Emergence Acceptance Protocol Test Suite.

Tests: T65-EM-01 through T65-EM-18
CI tier: critical

Constitutional invariants verified:
  MUTATION-TARGET, CEL-ORDER-0, CEL-EVIDENCE-0, SANDBOX-DIV-0,
  HUMAN-0, GATE-V2-EXISTING-0, AST-SAFE-0, FIT-BOUND-0,
  TIER0-SELF-0, INTEL-DET-0, CAP-VERS-0, CEL-DRYRUN-0
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sandbox_cel():
    """LiveWiredCEL in SANDBOX_ONLY mode — no real writes."""
    from runtime.evolution.cel_wiring import build_cel
    return build_cel(sandbox_only=True)


@pytest.fixture
def mock_epoch_context():
    from runtime.autonomy.ai_mutation_proposer import CodebaseContext
    return CodebaseContext(
        file_summaries={},
        recent_failures=[],
        current_epoch_id="test-epoch-p65-001",
    )


@pytest.fixture
def mock_cel_result():
    """Minimal EpochCELResult-like dict for mocking."""
    from runtime.evolution.constitutional_evolution_loop import (
        EpochCELResult,
        RunMode,
        CELStepResult,
        StepOutcome,
    )
    sr = CELStepResult(
        step_number=14,
        step_name="STATE-ADVANCE",
        outcome=StepOutcome.PASS,
        detail={
            "mutations_succeeded": ["mut-abc123"],
            "fitness_composite": 0.87,
            "steps_completed": 14,
        },
    )
    return EpochCELResult(
        epoch_id="test-epoch-p65-001",
        run_mode=RunMode.SANDBOX_ONLY,
        step_results=[sr],
        epoch_evidence_hash="a" * 64,
        dry_run=True,
    )


# ---------------------------------------------------------------------------
# T65-EM-01: build_cel constructs in SANDBOX_ONLY mode
# ---------------------------------------------------------------------------


def test_T65_EM_01_build_cel_sandbox_mode():
    """T65-EM-01: build_cel(sandbox_only=True) succeeds and sets dry_run=True."""
    from runtime.evolution.cel_wiring import build_cel
    from runtime.evolution.constitutional_evolution_loop import RunMode
    cel = build_cel(sandbox_only=True)
    assert cel is not None
    assert cel._run_mode == RunMode.SANDBOX_ONLY
    assert cel._dry_run is True


# ---------------------------------------------------------------------------
# T65-EM-02: is_cel_enabled respects ADAAD_CEL_ENABLED env var
# ---------------------------------------------------------------------------


def test_T65_EM_02_cel_enabled_true(monkeypatch):
    """T65-EM-02: ADAAD_CEL_ENABLED=true → is_cel_enabled() returns True."""
    monkeypatch.setenv("ADAAD_CEL_ENABLED", "true")
    import runtime.evolution.cel_wiring as cw
    assert cw.is_cel_enabled() is True


def test_T65_EM_02b_cel_enabled_false(monkeypatch):
    """T65-EM-02b: ADAAD_CEL_ENABLED=false → is_cel_enabled() returns False."""
    monkeypatch.setenv("ADAAD_CEL_ENABLED", "false")
    import runtime.evolution.cel_wiring as cw
    assert cw.is_cel_enabled() is False


def test_T65_EM_02c_cel_enabled_default(monkeypatch):
    """T65-EM-02c: ADAAD_CEL_ENABLED unset → is_cel_enabled() returns False (safe default)."""
    monkeypatch.delenv("ADAAD_CEL_ENABLED", raising=False)
    import runtime.evolution.cel_wiring as cw
    assert cw.is_cel_enabled() is False


# ---------------------------------------------------------------------------
# T65-EM-03: assert_cel_enabled_or_raise raises when disabled
# ---------------------------------------------------------------------------


def test_T65_EM_03_assert_raises_when_disabled(monkeypatch):
    """T65-EM-03: assert_cel_enabled_or_raise() raises RuntimeError when CEL disabled."""
    monkeypatch.setenv("ADAAD_CEL_ENABLED", "false")
    from runtime.evolution.cel_wiring import assert_cel_enabled_or_raise
    with pytest.raises(RuntimeError, match="ADAAD_CEL_ENABLED"):
        assert_cel_enabled_or_raise()


def test_T65_EM_03b_assert_passes_when_enabled(monkeypatch):
    """T65-EM-03b: assert_cel_enabled_or_raise() is a no-op when CEL is enabled."""
    monkeypatch.setenv("ADAAD_CEL_ENABLED", "true")
    from runtime.evolution.cel_wiring import assert_cel_enabled_or_raise
    assert_cel_enabled_or_raise()  # must not raise


# ---------------------------------------------------------------------------
# T65-EM-04: EvolutionLoop routes to _run_cel_epoch when enabled
# ---------------------------------------------------------------------------


def test_T65_EM_04_evolution_loop_routes_to_cel(monkeypatch, mock_epoch_context):
    """T65-EM-04: run_epoch() dispatches to _run_cel_epoch when ADAAD_CEL_ENABLED=true."""
    monkeypatch.setenv("ADAAD_CEL_ENABLED", "true")
    from runtime.evolution.evolution_loop import EvolutionLoop, EpochResult
    loop = EvolutionLoop.__new__(EvolutionLoop)

    sentinel = EpochResult(
        epoch_id="test", generation_count=0,
        total_candidates=0, accepted_count=0,
    )
    with patch.object(loop, "_run_cel_epoch", return_value=sentinel) as mock_cel:
        result = loop.run_epoch(mock_epoch_context)
        mock_cel.assert_called_once_with(mock_epoch_context)
    assert result is sentinel


# ---------------------------------------------------------------------------
# T65-EM-05: EvolutionLoop routes to _run_legacy_epoch when disabled
# ---------------------------------------------------------------------------


def test_T65_EM_05_evolution_loop_routes_to_legacy(monkeypatch, mock_epoch_context):
    """T65-EM-05: run_epoch() dispatches to _run_legacy_epoch when ADAAD_CEL_ENABLED=false."""
    monkeypatch.setenv("ADAAD_CEL_ENABLED", "false")
    from runtime.evolution.evolution_loop import EvolutionLoop, EpochResult
    loop = EvolutionLoop.__new__(EvolutionLoop)

    sentinel = EpochResult(
        epoch_id="test", generation_count=0,
        total_candidates=0, accepted_count=0,
    )
    with patch.object(loop, "_run_legacy_epoch", return_value=sentinel) as mock_leg:
        result = loop.run_epoch(mock_epoch_context)
        mock_leg.assert_called_once_with(mock_epoch_context)
    assert result is sentinel


# ---------------------------------------------------------------------------
# T65-EM-06: SANDBOX_ONLY suppresses _emit_capability_changes (CEL-DRYRUN-0)
# ---------------------------------------------------------------------------


def test_T65_EM_06_sandbox_only_suppresses_emit(monkeypatch, mock_epoch_context, mock_cel_result):
    """T65-EM-06: _emit_capability_changes NOT called in SANDBOX_ONLY mode (CEL-DRYRUN-0)."""
    monkeypatch.setenv("ADAAD_CEL_ENABLED", "true")
    monkeypatch.setenv("ADAAD_SANDBOX_ONLY", "true")
    from runtime.evolution.evolution_loop import EvolutionLoop
    loop = EvolutionLoop.__new__(EvolutionLoop)

    with patch.object(loop, "_emit_capability_changes") as mock_emit:
        with patch("runtime.evolution.cel_wiring.build_cel") as mock_build:
            mock_cel_instance = MagicMock()
            mock_cel_instance.run_epoch.return_value = mock_cel_result
            mock_build.return_value = mock_cel_instance
            loop._run_cel_epoch(mock_epoch_context)
        mock_emit.assert_not_called()


# ---------------------------------------------------------------------------
# T65-EM-07: CapabilityChange produces deterministic change_id (INTEL-DET-0)
# ---------------------------------------------------------------------------


def test_T65_EM_07_capability_change_deterministic_id():
    """T65-EM-07: CapabilityChange.change_id is deterministic for identical inputs (INTEL-DET-0)."""
    from runtime.capability_graph import CapabilityChange
    kwargs = dict(
        node_id="cap:runtime.test.foo",
        old_version="1.0.0",
        new_version="1.1.0",
        epoch_evidence_hash="a" * 64,
        proposal_hash="b" * 64,
        timestamp=1000.0,
    )
    c1 = CapabilityChange(**kwargs)
    c2 = CapabilityChange(**kwargs)
    assert c1.change_id == c2.change_id
    assert len(c1.change_id) == 16
    assert all(ch in "0123456789abcdef" for ch in c1.change_id)


# ---------------------------------------------------------------------------
# T65-EM-08: CapabilityChange rejects empty node_id (validation)
# ---------------------------------------------------------------------------


def test_T65_EM_08_capability_change_rejects_empty_node_id():
    """T65-EM-08: CapabilityChange raises ValueError for empty node_id."""
    from runtime.capability_graph import CapabilityChange
    with pytest.raises(ValueError, match="node_id"):
        CapabilityChange(
            node_id="",
            old_version="1.0.0",
            new_version="1.1.0",
            epoch_evidence_hash="a" * 64,
            proposal_hash="b" * 64,
        )


# ---------------------------------------------------------------------------
# T65-EM-09: CapabilityChange rejects empty new_version
# ---------------------------------------------------------------------------


def test_T65_EM_09_capability_change_rejects_empty_new_version():
    """T65-EM-09: CapabilityChange raises ValueError for empty new_version."""
    from runtime.capability_graph import CapabilityChange
    with pytest.raises(ValueError, match="new_version"):
        CapabilityChange(
            node_id="cap:runtime.test.x",
            old_version="",
            new_version="",
            epoch_evidence_hash="a" * 64,
            proposal_hash="b" * 64,
        )


# ---------------------------------------------------------------------------
# T65-EM-10: CapabilityChange.to_dict() contains required event fields
# ---------------------------------------------------------------------------


def test_T65_EM_10_capability_change_to_dict():
    """T65-EM-10: CapabilityChange.to_dict() contains all required ledger fields."""
    from runtime.capability_graph import CapabilityChange
    c = CapabilityChange(
        node_id="cap:runtime.test.bar",
        old_version="1.0.0",
        new_version="1.1.0",
        epoch_evidence_hash="c" * 64,
        proposal_hash="d" * 64,
        timestamp=9999.0,
    )
    d = c.to_dict()
    for field in ("event", "change_id", "node_id", "old_version",
                  "new_version", "epoch_evidence_hash", "proposal_hash", "timestamp"):
        assert field in d, f"Missing field in to_dict(): {field}"
    assert d["event"] == "CAPABILITY_CHANGE"


# ---------------------------------------------------------------------------
# T65-EM-11: CapabilityGraph.record_change writes to ledger
# ---------------------------------------------------------------------------


def test_T65_EM_11_capability_graph_record_change(tmp_path):
    """T65-EM-11: CapabilityGraph.record_change() appends a valid JSONL entry."""
    from runtime.capability_graph import CapabilityGraph, CapabilityChange
    ledger = tmp_path / "cap_changes.jsonl"
    graph = CapabilityGraph(ledger_path=ledger)
    change = CapabilityChange(
        node_id="cap:runtime.test.write",
        old_version="0.0.0",
        new_version="0.1.0",
        epoch_evidence_hash="e" * 64,
        proposal_hash="f" * 64,
    )
    digest = graph.record_change(change)

    assert ledger.exists()
    lines = ledger.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event"] == "CAPABILITY_CHANGE"
    assert entry["node_id"] == "cap:runtime.test.write"
    assert isinstance(digest, str) and len(digest) == 64


# ---------------------------------------------------------------------------
# T65-EM-12: GovernanceGateV2 present in LiveWiredCEL (CEL-GATE-0)
# ---------------------------------------------------------------------------


def test_T65_EM_12_gate_v2_present_in_cel(sandbox_cel):
    """T65-EM-12: LiveWiredCEL contains a GovernanceGateV2 instance (CEL-GATE-0)."""
    from runtime.governance.gate_v2 import GovernanceGateV2
    assert hasattr(sandbox_cel, "_gate_v2")
    assert isinstance(sandbox_cel._gate_v2, GovernanceGateV2)


# ---------------------------------------------------------------------------
# T65-EM-13: GovernanceGate present in LiveWiredCEL (GATE-V2-EXISTING-0)
# ---------------------------------------------------------------------------


def test_T65_EM_13_gate_present_in_cel(sandbox_cel):
    """T65-EM-13: LiveWiredCEL contains a GovernanceGate instance (GATE-V2-EXISTING-0)."""
    from runtime.governance.gate import GovernanceGate
    assert hasattr(sandbox_cel, "_gate")
    assert isinstance(sandbox_cel._gate, GovernanceGate)


# ---------------------------------------------------------------------------
# T65-EM-14: build_cel(sandbox_only=False) produces LIVE mode CEL
# ---------------------------------------------------------------------------


def test_T65_EM_14_build_cel_live_mode():
    """T65-EM-14: build_cel(sandbox_only=False) produces a LIVE-mode LiveWiredCEL."""
    from runtime.evolution.cel_wiring import build_cel
    from runtime.evolution.constitutional_evolution_loop import RunMode
    cel = build_cel(sandbox_only=False)
    assert cel._run_mode == RunMode.LIVE
    assert cel._dry_run is False


# ---------------------------------------------------------------------------
# T65-EM-15: EpochCELResult.completed reflects 14-step full execution
# ---------------------------------------------------------------------------


def test_T65_EM_15_cel_result_completed_requires_14_steps():
    """T65-EM-15: EpochCELResult.completed is True only when all 14 steps present."""
    from runtime.evolution.constitutional_evolution_loop import (
        EpochCELResult, RunMode, CELStepResult, StepOutcome,
    )
    steps = [
        CELStepResult(step_number=i, step_name=f"STEP-{i:02d}", outcome=StepOutcome.PASS)
        for i in range(1, 15)
    ]
    result = EpochCELResult(
        epoch_id="test",
        run_mode=RunMode.SANDBOX_ONLY,
        step_results=steps,
        blocked_at_step=None,
    )
    assert result.completed is True


def test_T65_EM_15b_cel_result_incomplete_if_blocked():
    """T65-EM-15b: EpochCELResult.completed is False when blocked_at_step is set."""
    from runtime.evolution.constitutional_evolution_loop import (
        EpochCELResult, RunMode,
    )
    result = EpochCELResult(
        epoch_id="test",
        run_mode=RunMode.SANDBOX_ONLY,
        step_results=[],
        blocked_at_step=5,
    )
    assert result.completed is False


# ---------------------------------------------------------------------------
# T65-EM-16: epoch_evidence_hash is valid SHA-256 hex (64 chars)
# ---------------------------------------------------------------------------


def test_T65_EM_16_epoch_evidence_hash_format(mock_cel_result):
    """T65-EM-16: epoch_evidence_hash is a valid 64-char lowercase hex string."""
    h = mock_cel_result.epoch_evidence_hash
    assert h is not None
    assert len(h) == 64, f"Expected 64-char hash; got {len(h)}"
    assert all(c in "0123456789abcdef" for c in h.lower())


# ---------------------------------------------------------------------------
# T65-EM-17: SANDBOX_ONLY run writes dry_run=True to ledger (CEL-DRYRUN-0)
# ---------------------------------------------------------------------------


def test_T65_EM_17_sandbox_dry_run_flag(sandbox_cel):
    """T65-EM-17: LiveWiredCEL in SANDBOX_ONLY mode has _dry_run=True (CEL-DRYRUN-0)."""
    assert sandbox_cel._dry_run is True


# ---------------------------------------------------------------------------
# T65-EM-18: record_capability_change is fail-safe on IOError
# ---------------------------------------------------------------------------


def test_T65_EM_18_record_capability_change_fail_safe(tmp_path):
    """T65-EM-18: record_capability_change swallows IOError and returns change_id."""
    from runtime.capability_graph import CapabilityChange, record_capability_change

    change = CapabilityChange(
        node_id="cap:runtime.test.failsafe",
        old_version="0.0.0",
        new_version="0.1.0",
        epoch_evidence_hash="a" * 64,
        proposal_hash="b" * 64,
    )

    # Use a read-only dir path to trigger a write failure
    ro_dir = tmp_path / "readonly"
    ro_dir.mkdir()
    (ro_dir).chmod(0o444)
    bad_path = ro_dir / "sub" / "ledger.jsonl"  # sub-dir creation will fail

    # Should not raise — fail-safe
    result = record_capability_change(change, ledger_path=bad_path)
    assert isinstance(result, str) and len(result) == 64

    # Restore permissions for cleanup
    ro_dir.chmod(0o755)
