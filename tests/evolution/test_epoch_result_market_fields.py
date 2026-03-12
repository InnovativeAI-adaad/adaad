# SPDX-License-Identifier: Apache-2.0
"""Phase 12 / Track 11-D — EpochResult live market signal fields (PR-12-D-01).

Tests verify:
  T12-D-01  EpochResult has live_market_score, market_confidence, market_is_synthetic fields
  T12-D-02  Fields default to synthetic fallback (0.0, 0.0, True) when market integrator absent
  T12-D-03  EvolutionLoop populates fields from MarketFitnessIntegrator.integrate() result
  T12-D-04  Live (non-synthetic) result surfaces correctly in EpochResult
  T12-D-05  Integrator exception is isolated — epoch completes with synthetic defaults
"""
from __future__ import annotations

import dataclasses
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.evolution_loop import EpochResult
from runtime.market.market_fitness_integrator import IntegrationResult, MarketFitnessIntegrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_integration_result(
    *,
    live_market_score: float = 0.72,
    confidence: float = 0.85,
    is_synthetic: bool = False,
) -> IntegrationResult:
    return IntegrationResult(
        epoch_id="ep-test-001",
        live_market_score=live_market_score,
        confidence=confidence,
        is_synthetic=is_synthetic,
        adapter_id="test_adapter",
        lineage_digest="sha256:" + "a" * 64,
        signal_source="live",
    )


def _minimal_epoch_result(**overrides: Any) -> EpochResult:
    base = dict(
        epoch_id="ep-001",
        generation_count=3,
        total_candidates=5,
        accepted_count=2,
    )
    base.update(overrides)
    return EpochResult(**base)


# ---------------------------------------------------------------------------
# T12-D-01: EpochResult has the three market fields
# ---------------------------------------------------------------------------

class TestEpochResultMarketFieldsExist:
    def test_epoch_result_has_live_market_score_field(self):
        result = _minimal_epoch_result()
        assert hasattr(result, "live_market_score")

    def test_epoch_result_has_market_confidence_field(self):
        result = _minimal_epoch_result()
        assert hasattr(result, "market_confidence")

    def test_epoch_result_has_market_is_synthetic_field(self):
        result = _minimal_epoch_result()
        assert hasattr(result, "market_is_synthetic")

    def test_all_three_market_fields_present_in_asdict(self):
        result = _minimal_epoch_result()
        d = dataclasses.asdict(result)
        assert "live_market_score" in d
        assert "market_confidence" in d
        assert "market_is_synthetic" in d


# ---------------------------------------------------------------------------
# T12-D-02: Default values are synthetic fallback
# ---------------------------------------------------------------------------

class TestEpochResultMarketFieldDefaults:
    def test_live_market_score_defaults_to_zero(self):
        result = _minimal_epoch_result()
        assert result.live_market_score == 0.0

    def test_market_confidence_defaults_to_zero(self):
        result = _minimal_epoch_result()
        assert result.market_confidence == 0.0

    def test_market_is_synthetic_defaults_to_true(self):
        result = _minimal_epoch_result()
        assert result.market_is_synthetic is True


# ---------------------------------------------------------------------------
# T12-D-03/04: MarketFitnessIntegrator result surfaces in EpochResult
# ---------------------------------------------------------------------------

class TestEvolutionLoopMarketIntegratorWiring:
    """Verify EvolutionLoop calls integrate() and populates EpochResult fields."""

    def _make_loop_with_mock_integrator(self, integration_result: IntegrationResult):
        """Build a minimal EvolutionLoop with a mocked market integrator."""
        from runtime.evolution.evolution_loop import EvolutionLoop

        mock_integrator = MagicMock(spec=MarketFitnessIntegrator)
        mock_integrator.integrate.return_value = integration_result

        loop = EvolutionLoop(
            api_key="test-key",
            simulate_outcomes=True,
            market_integrator=mock_integrator,
        )
        return loop, mock_integrator

    def _run_one_epoch(self, loop):
        from runtime.autonomy.ai_mutation_proposer import CodebaseContext
        ctx = CodebaseContext(
            file_summaries={},
            recent_failures=[],
            current_epoch_id="ep-mkt-001",
        )
        with patch(
            "runtime.evolution.evolution_loop.propose_from_all_agents",
            return_value=[],
        ):
            return loop.run_epoch(ctx)

    def test_integrate_called_with_epoch_id(self):
        ir = _make_integration_result()
        loop, mock_int = self._make_loop_with_mock_integrator(ir)
        self._run_one_epoch(loop)
        mock_int.integrate.assert_called_once_with(epoch_id="ep-mkt-001")

    def test_live_market_score_populated_from_integrator(self):
        ir = _make_integration_result(live_market_score=0.88)
        loop, _ = self._make_loop_with_mock_integrator(ir)
        result = self._run_one_epoch(loop)
        assert result.live_market_score == pytest.approx(0.88)

    def test_market_confidence_populated_from_integrator(self):
        ir = _make_integration_result(confidence=0.76)
        loop, _ = self._make_loop_with_mock_integrator(ir)
        result = self._run_one_epoch(loop)
        assert result.market_confidence == pytest.approx(0.76)

    def test_market_is_synthetic_false_when_live(self):
        ir = _make_integration_result(is_synthetic=False)
        loop, _ = self._make_loop_with_mock_integrator(ir)
        result = self._run_one_epoch(loop)
        assert result.market_is_synthetic is False

    def test_market_is_synthetic_true_when_synthetic(self):
        ir = _make_integration_result(is_synthetic=True, confidence=0.0, live_market_score=0.5)
        loop, _ = self._make_loop_with_mock_integrator(ir)
        result = self._run_one_epoch(loop)
        assert result.market_is_synthetic is True

    def test_no_integrator_injected_yields_synthetic_defaults(self):
        from runtime.evolution.evolution_loop import EvolutionLoop
        from runtime.autonomy.ai_mutation_proposer import CodebaseContext

        loop = EvolutionLoop(api_key="k", simulate_outcomes=True)
        ctx = CodebaseContext(file_summaries={}, recent_failures=[], current_epoch_id="ep-no-mkt")
        with patch(
            "runtime.evolution.evolution_loop.propose_from_all_agents",
            return_value=[],
        ):
            result = loop.run_epoch(ctx)

        # Phase 22 default-on: auto-provisioned MarketFitnessIntegrator returns
        # synthetic baseline 0.5 (not 0.0). market_is_synthetic is True.
        assert result.live_market_score == pytest.approx(0.5, abs=0.1)
        assert result.market_confidence == 0.0
        assert result.market_is_synthetic is True


# ---------------------------------------------------------------------------
# T12-D-05: Integrator exception is isolated — epoch completes
# ---------------------------------------------------------------------------

class TestMarketIntegratorExceptionIsolation:
    def test_integrator_exception_does_not_abort_epoch(self):
        from runtime.evolution.evolution_loop import EvolutionLoop
        from runtime.autonomy.ai_mutation_proposer import CodebaseContext

        mock_integrator = MagicMock(spec=MarketFitnessIntegrator)
        mock_integrator.integrate.side_effect = RuntimeError("feed unavailable")

        loop = EvolutionLoop(
            api_key="k",
            simulate_outcomes=True,
            market_integrator=mock_integrator,
        )
        ctx = CodebaseContext(file_summaries={}, recent_failures=[], current_epoch_id="ep-fail-mkt")
        with patch(
            "runtime.evolution.evolution_loop.propose_from_all_agents",
            return_value=[],
        ):
            result = loop.run_epoch(ctx)

        # epoch completes; fields revert to synthetic defaults
        assert result.live_market_score == 0.0
        assert result.market_confidence == 0.0
        assert result.market_is_synthetic is True
        assert result.epoch_id == "ep-fail-mkt"
