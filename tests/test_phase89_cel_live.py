# SPDX-License-Identifier: Apache-2.0
"""Phase 89 smoke tests — LLM Proposal Pipeline Activation.

Invariants exercised:
    CEL-LIVE-0        sandbox+key → RuntimeError; no-key → sandbox OK; factory auto-upgrades
    REPLAY-CAPTURE-0  ProposalCaptureEvent written before response used; ledger persistent
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_provider_result(ok=True, payload=None, error_code=None):
    from runtime.intelligence.llm_provider import LLMProviderResult
    return LLMProviderResult(
        ok=ok,
        payload=payload or {"title": "test", "summary": "s", "real_diff": "d",
                             "target_files": [], "projected_impact": {}, "metadata": {}},
        error_code=error_code,
    )


def _make_adapter(tmp_path, provider_result=None):
    """Return a ProposalAdapter wired to a temp capture ledger and mock provider."""
    from runtime.evolution.proposal_capture import ProposalCaptureLedger
    from runtime.intelligence.llm_provider import LLMProviderClient, LLMProviderConfig
    from runtime.intelligence.proposal import ProposalModule
    from runtime.intelligence.proposal_adapter import ProposalAdapter

    ledger = ProposalCaptureLedger(ledger_path=tmp_path / "capture.jsonl")
    mock_client = MagicMock(spec=LLMProviderClient)
    mock_client.request_json.return_value = provider_result or _mock_provider_result()
    proposal_module = ProposalModule()
    return ProposalAdapter(
        provider_client=mock_client,
        proposal_module=proposal_module,
        capture_ledger=ledger,
    ), ledger


def _strategy_input(cycle_id="c-ph89-test"):
    from runtime.intelligence.strategy import StrategyInput
    return StrategyInput(
        cycle_id=cycle_id,
        mutation_score=0.7,
        governance_debt_score=0.1,
        signals={"fitness": 0.7},
    )


def _strategy_decision(strategy_id="adaptive_self_mutate"):
    from runtime.intelligence.strategy import StrategyDecision
    return StrategyDecision(
        strategy_id=strategy_id,
        rationale="phase89 test",
        confidence=0.9,
    )


# ---------------------------------------------------------------------------
# REPLAY-CAPTURE-0
# ---------------------------------------------------------------------------

class TestReplayCapture0:
    """REPLAY-CAPTURE-0: capture event written before response used downstream."""

    def test_capture_event_written_on_successful_call(self, tmp_path):
        adapter, ledger = _make_adapter(tmp_path)
        adapter.build_from_strategy(
            context=_strategy_input(cycle_id="c-rc0-001"),
            strategy=_strategy_decision(),
            epoch_id="ep-89-rc0",
            call_index=0,
        )
        entries = ledger.entries()
        assert len(entries) == 1
        e = entries[0]
        assert e.cycle_id == "c-rc0-001"
        assert e.epoch_id == "ep-89-rc0"
        assert e.call_index == 0
        assert e.strategy_id == "adaptive_self_mutate"
        assert e.provider_ok is True
        assert e.prompt_hash  # non-empty
        assert e.response_hash  # non-empty

    def test_capture_event_written_on_failed_call(self, tmp_path):
        """Capture event must be written even when provider returns ok=False."""
        failed_result = _mock_provider_result(ok=False, payload={}, error_code="provider_request_failed")
        adapter, ledger = _make_adapter(tmp_path, provider_result=failed_result)
        adapter.build_from_strategy(
            context=_strategy_input(cycle_id="c-rc0-002"),
            strategy=_strategy_decision(),
            epoch_id="ep-89-rc0-fail",
            call_index=0,
        )
        entries = ledger.entries()
        assert len(entries) == 1
        assert entries[0].provider_ok is False
        assert entries[0].error_code == "provider_request_failed"

    def test_multiple_calls_increment_index(self, tmp_path):
        adapter, ledger = _make_adapter(tmp_path)
        for i in range(3):
            adapter.build_from_strategy(
                context=_strategy_input(cycle_id=f"c-multi-{i:03d}"),
                strategy=_strategy_decision(),
                epoch_id="ep-89-multi",
                call_index=i,
            )
        entries = ledger.entries()
        assert len(entries) == 3
        assert [e.call_index for e in entries] == [0, 1, 2]

    def test_response_hash_verifiable(self, tmp_path):
        adapter, ledger = _make_adapter(tmp_path)
        adapter.build_from_strategy(
            context=_strategy_input(cycle_id="c-hash-001"),
            strategy=_strategy_decision(),
            epoch_id="ep-89-hash",
            call_index=0,
        )
        e = ledger.entries()[0]
        # Re-hash stored response_text — must match recorded response_hash
        import hashlib
        expected = hashlib.sha256(e.response_text.encode()).hexdigest()
        assert e.response_hash == expected

    def test_ledger_persists_across_instances(self, tmp_path):
        """ProposalCaptureLedger loads events written by a previous instance."""
        from runtime.evolution.proposal_capture import ProposalCaptureLedger, ProposalCaptureEvent

        path = tmp_path / "cap.jsonl"
        e = ProposalCaptureEvent.build(
            epoch_id="ep-persist", cycle_id="c-persist", call_index=0,
            strategy_id="conservative_hold",
            system_prompt="sys", user_prompt="usr",
            response_text='{"title":"x"}', provider_ok=True,
        )
        ledger1 = ProposalCaptureLedger(ledger_path=path)
        ledger1.append(e)

        ledger2 = ProposalCaptureLedger(ledger_path=path)
        entries = ledger2.entries()
        assert len(entries) == 1
        assert entries[0].cycle_id == "c-persist"

    def test_get_by_cycle_and_index(self, tmp_path):
        from runtime.evolution.proposal_capture import ProposalCaptureLedger, ProposalCaptureEvent

        ledger = ProposalCaptureLedger(ledger_path=tmp_path / "cap.jsonl")
        for i in range(3):
            ledger.append(ProposalCaptureEvent.build(
                epoch_id="ep-get", cycle_id=f"c-get-{i}", call_index=i,
                strategy_id="adaptive_self_mutate",
                system_prompt="s", user_prompt="u",
                response_text=f'{{"i":{i}}}', provider_ok=True,
            ))
        found = ledger.get(cycle_id="c-get-1", call_index=1)
        assert found is not None
        assert found.cycle_id == "c-get-1"
        assert ledger.get(cycle_id="c-nonexistent", call_index=0) is None


# ---------------------------------------------------------------------------
# CEL-LIVE-0
# ---------------------------------------------------------------------------

class TestCelLive0:
    """CEL-LIVE-0: sandbox+key is a constitutional violation."""

    def test_sandbox_without_key_ok(self):
        """No key → sandbox mode is legal."""
        from runtime.evolution.cel_wiring import make_live_wired_cel, RunMode
        env = {k: v for k, v in os.environ.items() if k != "ADAAD_ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            cel = make_live_wired_cel(run_mode=RunMode.SANDBOX_ONLY)
        assert cel._run_mode is RunMode.SANDBOX_ONLY

    def test_factory_upgrades_to_live_when_key_present(self):
        """Factory must auto-upgrade SANDBOX_ONLY → LIVE when key is set."""
        from runtime.evolution.cel_wiring import make_live_wired_cel, RunMode
        env = {**os.environ, "ADAAD_ANTHROPIC_API_KEY": "sk-test-key-ph89"}
        with patch.dict(os.environ, env, clear=True):
            cel = make_live_wired_cel(run_mode=RunMode.SANDBOX_ONLY)
        assert cel._run_mode is RunMode.LIVE

    def test_factory_preserves_live_mode_with_key(self):
        """Factory with run_mode=LIVE and a key → still LIVE (no regression)."""
        from runtime.evolution.cel_wiring import make_live_wired_cel, RunMode
        env = {**os.environ, "ADAAD_ANTHROPIC_API_KEY": "sk-test-key-ph89"}
        with patch.dict(os.environ, env, clear=True):
            cel = make_live_wired_cel(run_mode=RunMode.LIVE)
        assert cel._run_mode is RunMode.LIVE

    def test_run_epoch_raises_on_sandbox_with_live_key(self):
        """CEL-LIVE-0: run_epoch must raise when key present + sandbox mode."""
        from runtime.evolution.cel_wiring import make_live_wired_cel, RunMode, LiveWiredCEL
        from runtime.evolution.constitutional_evolution_loop import RunMode as _RM

        # Build a sandbox CEL bypassing the factory (direct construction)
        cel_sandbox = make_live_wired_cel(run_mode=RunMode.SANDBOX_ONLY)
        # Manually set sandbox mode to simulate the violation
        object.__setattr__(cel_sandbox, "_run_mode", RunMode.SANDBOX_ONLY)

        env = {**os.environ, "ADAAD_ANTHROPIC_API_KEY": "sk-live-key-test"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="CEL-LIVE-0"):
                cel_sandbox.run_epoch(epoch_id="ep-violation-test")

    def test_run_epoch_sandbox_no_key_does_not_raise(self):
        """No key → run_epoch in sandbox mode must not raise CEL-LIVE-0."""
        from runtime.evolution.cel_wiring import make_live_wired_cel, RunMode

        env = {k: v for k, v in os.environ.items() if k != "ADAAD_ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            cel = make_live_wired_cel(run_mode=RunMode.SANDBOX_ONLY)
            # run_epoch will execute — may fail on missing context but NOT on CEL-LIVE-0
            try:
                cel.run_epoch(epoch_id="ep-no-key-sandbox")
            except RuntimeError as e:
                assert "CEL-LIVE-0" not in str(e), f"CEL-LIVE-0 raised unexpectedly: {e}"
            except Exception:
                pass  # Other errors are fine — we only care about CEL-LIVE-0


# ---------------------------------------------------------------------------
# ProposalCaptureEvent unit tests
# ---------------------------------------------------------------------------

class TestProposalCaptureEvent:
    def test_build_produces_valid_hashes(self):
        from runtime.evolution.proposal_capture import ProposalCaptureEvent
        import hashlib
        e = ProposalCaptureEvent.build(
            epoch_id="ep-unit", cycle_id="c-unit", call_index=0,
            strategy_id="safety_hardening",
            system_prompt="sys", user_prompt="usr",
            response_text='{"x":1}', provider_ok=True,
        )
        expected_prompt = hashlib.sha256(("sys\nusr").encode()).hexdigest()
        expected_resp   = hashlib.sha256(('{"x":1}').encode()).hexdigest()
        assert e.prompt_hash   == expected_prompt
        assert e.response_hash == expected_resp

    def test_to_dict_round_trips(self):
        from runtime.evolution.proposal_capture import ProposalCaptureEvent
        e = ProposalCaptureEvent.build(
            epoch_id="ep", cycle_id="c", call_index=0,
            strategy_id="conservative_hold",
            system_prompt="s", user_prompt="u",
            response_text="{}", provider_ok=False, error_code="missing_api_key",
        )
        d = e.to_dict()
        assert d["provider_ok"] is False
        assert d["error_code"] == "missing_api_key"
        assert d["schema_version"] == "89.0"

    def test_schema_version(self):
        from runtime.evolution.proposal_capture import ProposalCaptureEvent, _SCHEMA_VERSION
        assert _SCHEMA_VERSION == "89.0"
        e = ProposalCaptureEvent.build(
            epoch_id="ep", cycle_id="c", call_index=0, strategy_id="test",
            system_prompt="s", user_prompt="u", response_text="{}", provider_ok=True,
        )
        assert e.schema_version == "89.0"
