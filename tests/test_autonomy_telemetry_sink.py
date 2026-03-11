# SPDX-License-Identifier: Apache-2.0
"""Tests: AutonomyLoop telemetry sink upgrade — Phase 21 / PR-21-02

Covers:
- AutonomyLoop with telemetry_ledger_path=None uses InMemoryTelemetrySink
- AutonomyLoop with telemetry_ledger_path=<tmp> uses FileTelemetrySink
- ADAAD_TELEMETRY_LEDGER_PATH env var respected at construction
- Routing decisions emitted to FileTelemetrySink are persisted and chain-verified
- AutonomyLoop.file_sink and .telemetry_ledger_path properties
- Existing AutonomyLoop tests unaffected (regression gate: router.route works)
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.autonomy.loop import AgentAction, AutonomyLoop, AutonomyLoopResult
from runtime.intelligence.file_telemetry_sink import FileTelemetrySink
from runtime.intelligence.routed_decision_telemetry import InMemoryTelemetrySink


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loop(tmp_path, *, use_path: bool) -> tuple[AutonomyLoop, Path | None]:
    ledger = tmp_path / "telemetry.jsonl" if use_path else None
    loop = AutonomyLoop(telemetry_ledger_path=ledger)
    return loop, ledger


def _run_once(loop: AutonomyLoop, cycle_id: str = "c1") -> AutonomyLoopResult:
    return loop.run(
        cycle_id=cycle_id,
        actions=[AgentAction(agent="a", action="x", duration_ms=1, ok=True)],
        post_condition_checks={},
        mutation_score=0.5,
    )


# ---------------------------------------------------------------------------
# Sink selection tests
# ---------------------------------------------------------------------------


class TestSinkSelection:
    def test_no_path_uses_in_memory_sink(self, tmp_path):
        loop = AutonomyLoop()
        assert loop.file_sink is None
        assert loop.telemetry_ledger_path is None

    def test_explicit_none_path_uses_in_memory_sink(self, tmp_path):
        loop = AutonomyLoop(telemetry_ledger_path=None)
        assert loop.file_sink is None

    def test_explicit_path_uses_file_sink(self, tmp_path):
        ledger = tmp_path / "tel.jsonl"
        loop = AutonomyLoop(telemetry_ledger_path=ledger)
        assert isinstance(loop.file_sink, FileTelemetrySink)
        assert loop.telemetry_ledger_path == ledger

    def test_string_path_accepted(self, tmp_path):
        ledger = tmp_path / "tel.jsonl"
        loop = AutonomyLoop(telemetry_ledger_path=str(ledger))
        assert isinstance(loop.file_sink, FileTelemetrySink)

    def test_env_var_respected(self, tmp_path, monkeypatch):
        ledger = tmp_path / "env_tel.jsonl"
        monkeypatch.setenv("ADAAD_TELEMETRY_LEDGER_PATH", str(ledger))
        loop = AutonomyLoop()
        assert isinstance(loop.file_sink, FileTelemetrySink)

    def test_explicit_kwarg_takes_precedence_over_env(self, tmp_path, monkeypatch):
        env_ledger = tmp_path / "env.jsonl"
        kwarg_ledger = tmp_path / "kwarg.jsonl"
        monkeypatch.setenv("ADAAD_TELEMETRY_LEDGER_PATH", str(env_ledger))
        loop = AutonomyLoop(telemetry_ledger_path=kwarg_ledger)
        assert loop.telemetry_ledger_path == kwarg_ledger

    def test_empty_env_var_falls_back_to_memory(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADAAD_TELEMETRY_LEDGER_PATH", "")
        loop = AutonomyLoop()
        assert loop.file_sink is None


# ---------------------------------------------------------------------------
# Persistence and chain integrity tests
# ---------------------------------------------------------------------------


class TestFileSinkPersistence:
    def test_run_emits_to_file_sink(self, tmp_path):
        ledger = tmp_path / "tel.jsonl"
        loop = AutonomyLoop(telemetry_ledger_path=ledger)
        _run_once(loop)
        assert ledger.exists()
        assert len(loop.file_sink) == 1

    def test_multiple_runs_emit_multiple_records(self, tmp_path):
        ledger = tmp_path / "tel.jsonl"
        loop = AutonomyLoop(telemetry_ledger_path=ledger)
        for i in range(5):
            _run_once(loop, cycle_id=f"c{i}")
        assert len(loop.file_sink) == 5

    def test_chain_integrity_after_runs(self, tmp_path):
        ledger = tmp_path / "tel.jsonl"
        loop = AutonomyLoop(telemetry_ledger_path=ledger)
        _run_once(loop, "c1")
        _run_once(loop, "c2")
        _run_once(loop, "c3")
        assert loop.file_sink.verify_chain() is True


# ---------------------------------------------------------------------------
# Regression gate: existing AutonomyLoop behaviour unchanged
# ---------------------------------------------------------------------------


class TestRegression:
    def test_run_returns_autonomy_loop_result(self, tmp_path):
        loop = AutonomyLoop()
        result = _run_once(loop)
        assert isinstance(result, AutonomyLoopResult)

    def test_run_with_file_sink_returns_autonomy_loop_result(self, tmp_path):
        ledger = tmp_path / "tel.jsonl"
        loop = AutonomyLoop(telemetry_ledger_path=ledger)
        result = _run_once(loop)
        assert isinstance(result, AutonomyLoopResult)

    def test_router_property_accessible(self):
        loop = AutonomyLoop()
        assert loop.router is not None

    def test_reset_epoch_does_not_raise(self):
        loop = AutonomyLoop()
        loop.reset_epoch()  # must not raise

    def test_decision_field_present(self, tmp_path):
        loop = AutonomyLoop()
        result = _run_once(loop)
        assert result.decision in {"hold", "self_mutate", "escalate"}

    def test_intelligence_fields_populated(self, tmp_path):
        loop = AutonomyLoop()
        result = _run_once(loop)
        assert result.intelligence_strategy_id is not None
        assert result.intelligence_outcome is not None
