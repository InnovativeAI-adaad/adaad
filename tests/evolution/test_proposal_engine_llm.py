# SPDX-License-Identifier: Apache-2.0
"""Tests for LLM-activated ProposalEngine.generate().

Coverage:
  - Noop fallback when no API key configured
  - LLM path: happy path with mock adapter
  - LLM path: adapter raises → fail-closed noop returned (no exception)
  - Strategy input mapping from ProposalRequest.context
  - Proposal fields populated from LLM response
"""

from __future__ import annotations

from typing import Any, Mapping
from unittest.mock import MagicMock, patch

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.proposal_engine import ProposalEngine, ProposalRequest, _noop_proposal
from runtime.intelligence.proposal import Proposal, ProposalModule
from runtime.intelligence.proposal_adapter import ProposalAdapter
from runtime.intelligence.strategy import StrategyDecision, StrategyInput, StrategyModule


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _make_proposal(proposal_id: str = "c1:s1") -> Proposal:
    return Proposal(
        proposal_id=proposal_id,
        title="Mock proposal",
        summary="LLM-generated summary",
        estimated_impact=0.72,
        real_diff="--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new",
        metadata={"cycle_id": "c1", "strategy_id": "s1"},
    )


def _make_adapter(proposal: Proposal) -> ProposalAdapter:
    adapter = MagicMock(spec=ProposalAdapter)
    adapter.build_from_strategy.return_value = proposal
    return adapter


# ────────────────────────────────────────────────────────────────────────────
# Noop path
# ────────────────────────────────────────────────────────────────────────────

class TestNoopFallback:
    def test_no_api_key_returns_noop(self):
        engine = ProposalEngine(env={"ADAAD_ANTHROPIC_API_KEY": ""})
        req = ProposalRequest(cycle_id="c1", strategy_id="s1")
        result = engine.generate(req)

        assert result.proposal_id.endswith(":noop")
        assert result.metadata.get("noop_reason") == "no_api_key_configured"
        assert result.metadata.get("governance_continuity") == "preserved"

    def test_noop_helper_fields(self):
        req = ProposalRequest(cycle_id="cyc42", strategy_id="strat-x")
        result = _noop_proposal(req, "test_reason")

        assert result.cycle_id_in_meta() if hasattr(result, "cycle_id_in_meta") else True
        assert result.metadata["cycle_id"] == "cyc42"
        assert result.metadata["strategy_id"] == "strat-x"
        assert result.metadata["noop_reason"] == "test_reason"

    def test_adapter_raises_returns_noop_not_exception(self):
        adapter = MagicMock(spec=ProposalAdapter)
        adapter.build_from_strategy.side_effect = RuntimeError("llm_timeout")

        engine = ProposalEngine(adapter=adapter)
        req = ProposalRequest(cycle_id="c9", strategy_id="s9")
        result = engine.generate(req)

        assert result.proposal_id.endswith(":noop")
        assert result.metadata["noop_reason"] == "RuntimeError"

    def test_strategy_module_raises_returns_noop(self):
        mock_strategy = MagicMock(spec=StrategyModule)
        mock_strategy.select.side_effect = ValueError("bad_context")
        adapter = _make_adapter(_make_proposal())

        engine = ProposalEngine(adapter=adapter, strategy_module=mock_strategy)
        req = ProposalRequest(cycle_id="c8", strategy_id="s8")
        result = engine.generate(req)

        assert result.proposal_id.endswith(":noop")
        assert result.metadata["noop_reason"] == "ValueError"


# ────────────────────────────────────────────────────────────────────────────
# Happy path — LLM-backed proposal
# ────────────────────────────────────────────────────────────────────────────

class TestLLMHappyPath:
    def test_generate_returns_llm_proposal(self):
        expected = _make_proposal("c1:s1")
        adapter = _make_adapter(expected)
        engine = ProposalEngine(adapter=adapter)

        req = ProposalRequest(cycle_id="c1", strategy_id="s1")
        result = engine.generate(req)

        assert result is expected
        adapter.build_from_strategy.assert_called_once()

    def test_strategy_input_passed_to_adapter(self):
        expected = _make_proposal()
        adapter = _make_adapter(expected)
        engine = ProposalEngine(adapter=adapter)

        req = ProposalRequest(
            cycle_id="cyc5",
            strategy_id="adaptive",
            context={
                "mutation_score": 0.8,
                "governance_debt_score": 0.1,
                "horizon_cycles": 3,
                "resource_budget": 0.9,
                "lineage_health": 0.95,
                "goal_backlog": {"reduce_tech_debt": 0.4},
                "custom_signal": "value",
            },
        )
        engine.generate(req)

        call_kwargs = adapter.build_from_strategy.call_args.kwargs
        ctx: StrategyInput = call_kwargs["context"]
        assert ctx.cycle_id == "cyc5"
        assert ctx.mutation_score == pytest.approx(0.8)
        assert ctx.governance_debt_score == pytest.approx(0.1)
        assert ctx.horizon_cycles == 3
        assert ctx.lineage_health == pytest.approx(0.95)
        assert ctx.signals.get("custom_signal") == "value"

    def test_strategy_decision_passed_to_adapter(self):
        expected = _make_proposal()
        adapter = _make_adapter(expected)

        mock_strategy = MagicMock(spec=StrategyModule)
        fixed_decision = StrategyDecision(
            strategy_id="conservative_hold",
            rationale="test rationale",
            confidence=0.77,
        )
        mock_strategy.select.return_value = fixed_decision

        engine = ProposalEngine(adapter=adapter, strategy_module=mock_strategy)
        req = ProposalRequest(cycle_id="c2", strategy_id="s2")
        engine.generate(req)

        call_kwargs = adapter.build_from_strategy.call_args.kwargs
        assert call_kwargs["strategy"] is fixed_decision

    def test_context_defaults_produce_valid_strategy_input(self):
        expected = _make_proposal()
        adapter = _make_adapter(expected)
        engine = ProposalEngine(adapter=adapter)

        req = ProposalRequest(cycle_id="c3", strategy_id="s3")
        engine.generate(req)

        call_kwargs = adapter.build_from_strategy.call_args.kwargs
        ctx: StrategyInput = call_kwargs["context"]
        assert ctx.mutation_score == pytest.approx(0.5)
        assert ctx.governance_debt_score == pytest.approx(0.0)
        assert ctx.resource_budget == pytest.approx(1.0)
        assert ctx.lineage_health == pytest.approx(1.0)
        assert ctx.horizon_cycles == 1

    def test_code_intel_context_keys_propagate_via_signals_passthrough(self):
        expected = _make_proposal()
        adapter = _make_adapter(expected)
        engine = ProposalEngine(adapter=adapter)

        req = ProposalRequest(
            cycle_id="cyc6",
            strategy_id="adaptive",
            context={
                "mutation_score": 0.7,
                "capability_target": "runtime.evolution.evolution_loop.EvolutionLoop.run_epoch",
                "hotspot_functions": (
                    "runtime.evolution.evolution_loop.EvolutionLoop.run_epoch",
                    "runtime.evolution.proposal_engine.ProposalEngine.generate",
                ),
                "fragility_score": 0.42,
                "fragility_delta": -0.07,
            },
        )
        engine.generate(req)

        call_kwargs = adapter.build_from_strategy.call_args.kwargs
        ctx: StrategyInput = call_kwargs["context"]
        assert ctx.mutation_score == pytest.approx(0.7)
        assert ctx.signals["capability_target"] == (
            "runtime.evolution.evolution_loop.EvolutionLoop.run_epoch"
        )
        assert ctx.signals["hotspot_functions"] == (
            "runtime.evolution.evolution_loop.EvolutionLoop.run_epoch",
            "runtime.evolution.proposal_engine.ProposalEngine.generate",
        )
        assert ctx.signals["fragility_score"] == pytest.approx(0.42)
        assert ctx.signals["fragility_delta"] == pytest.approx(-0.07)


# ────────────────────────────────────────────────────────────────────────────
# Auto-configuration from environment
# ────────────────────────────────────────────────────────────────────────────

class TestEnvConfiguration:
    def test_no_env_key_sets_none_adapter(self):
        engine = ProposalEngine(env={})
        assert engine._adapter is None

    def test_env_key_present_builds_adapter(self):
        with patch("runtime.evolution.proposal_engine.LLMProviderClient") as MockClient, \
             patch("runtime.evolution.proposal_engine.ProposalAdapter") as MockAdapter:
            MockAdapter.return_value = MagicMock(spec=ProposalAdapter)
            engine = ProposalEngine(env={"ADAAD_ANTHROPIC_API_KEY": "sk-test"})
            assert engine._adapter is not None
