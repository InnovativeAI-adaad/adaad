# SPDX-License-Identifier: Apache-2.0
"""Phase 13 / Track 11-B — consecutive_synthetic_epochs counter (PR-13-B-01).

Tests verify:
  T13-B-01  IntegrationResult has consecutive_synthetic_epochs field (default 0)
  T13-B-02  Counter increments on each synthetic integrate() call
  T13-B-03  Counter resets to 0 on a non-synthetic reading
  T13-B-04  Counter persists across multiple integrate() calls correctly
  T13-B-05  consecutive_synthetic_epochs property mirrors internal counter
  T13-B-06  reset_synthetic_counter() resets to 0
  T13-B-07  Journal event includes consecutive_synthetic_epochs
  T13-B-08  EpochResult.consecutive_synthetic_market_epochs field exists and is populated
"""
from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock, patch

import pytest

from runtime.market.market_fitness_integrator import IntegrationResult, MarketFitnessIntegrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_integrator(synthetic: bool = True) -> MarketFitnessIntegrator:
    """Integrator that always returns synthetic or live depending on flag."""
    integrator = MarketFitnessIntegrator()

    def _mock_do_integrate(epoch_id: str) -> IntegrationResult:
        if synthetic:
            raise RuntimeError("no feed")  # forces synthetic fallback path
        return IntegrationResult(
            epoch_id=epoch_id,
            live_market_score=0.72,
            confidence=0.85,
            is_synthetic=False,
            adapter_id="test",
            lineage_digest="sha256:" + "a" * 64,
            signal_source="live",
        )

    integrator._do_integrate = _mock_do_integrate  # type: ignore[method-assign]
    return integrator


# ---------------------------------------------------------------------------
# T13-B-01: IntegrationResult field exists
# ---------------------------------------------------------------------------

class TestIntegrationResultConsecutiveSyntheticField:
    def test_field_exists_and_defaults_to_zero(self):
        result = IntegrationResult(
            epoch_id="ep-001",
            live_market_score=0.5,
            confidence=0.0,
            is_synthetic=True,
            adapter_id="x",
            lineage_digest="sha256:" + "0" * 64,
            signal_source="synthetic",
        )
        assert hasattr(result, "consecutive_synthetic_epochs")
        assert result.consecutive_synthetic_epochs == 0

    def test_field_in_asdict(self):
        result = IntegrationResult(
            epoch_id="ep-001",
            live_market_score=0.5,
            confidence=0.0,
            is_synthetic=True,
            adapter_id="x",
            lineage_digest="sha256:" + "0" * 64,
            signal_source="synthetic",
        )
        d = dataclasses.asdict(result)
        assert "consecutive_synthetic_epochs" in d

    def test_field_carries_value(self):
        result = IntegrationResult(
            epoch_id="ep-001",
            live_market_score=0.5,
            confidence=0.0,
            is_synthetic=True,
            adapter_id="x",
            lineage_digest="sha256:" + "0" * 64,
            signal_source="synthetic",
            consecutive_synthetic_epochs=7,
        )
        assert result.consecutive_synthetic_epochs == 7


# ---------------------------------------------------------------------------
# T13-B-02: Counter increments on synthetic calls
# ---------------------------------------------------------------------------

class TestCounterIncrements:
    def test_counter_is_1_after_first_synthetic_call(self):
        integrator = _make_integrator(synthetic=True)
        result = integrator.integrate(epoch_id="ep-001")
        assert result.consecutive_synthetic_epochs == 1

    def test_counter_is_3_after_three_synthetic_calls(self):
        integrator = _make_integrator(synthetic=True)
        for i in range(2):
            integrator.integrate(epoch_id=f"ep-{i:03d}")
        result = integrator.integrate(epoch_id="ep-003")
        assert result.consecutive_synthetic_epochs == 3

    def test_property_matches_last_result(self):
        integrator = _make_integrator(synthetic=True)
        integrator.integrate(epoch_id="ep-001")
        integrator.integrate(epoch_id="ep-002")
        assert integrator.consecutive_synthetic_epochs == 2


# ---------------------------------------------------------------------------
# T13-B-03/04: Counter resets on live reading
# ---------------------------------------------------------------------------

class TestCounterReset:
    def test_counter_resets_to_0_on_live_reading(self):
        integrator = _make_integrator(synthetic=True)
        # Three synthetic
        for i in range(3):
            integrator.integrate(epoch_id=f"ep-{i:03d}")
        assert integrator.consecutive_synthetic_epochs == 3
        # Switch to live
        integrator._do_integrate = lambda eid: IntegrationResult(  # type: ignore
            epoch_id=eid, live_market_score=0.8, confidence=0.9,
            is_synthetic=False, adapter_id="live", lineage_digest="sha256:" + "b" * 64,
            signal_source="live",
        )
        result = integrator.integrate(epoch_id="ep-live")
        assert result.consecutive_synthetic_epochs == 0
        assert integrator.consecutive_synthetic_epochs == 0

    def test_counter_increments_again_after_reset(self):
        integrator = _make_integrator(synthetic=True)
        integrator.integrate(epoch_id="ep-001")
        # Live reading resets
        integrator._do_integrate = lambda eid: IntegrationResult(  # type: ignore
            epoch_id=eid, live_market_score=0.8, confidence=0.9,
            is_synthetic=False, adapter_id="live", lineage_digest="sha256:" + "b" * 64,
            signal_source="live",
        )
        integrator.integrate(epoch_id="ep-live")
        # Back to synthetic
        integrator._do_integrate = lambda eid: (_ for _ in ()).throw(RuntimeError("no feed"))  # type: ignore
        result = integrator.integrate(epoch_id="ep-synth")
        assert result.consecutive_synthetic_epochs == 1


# ---------------------------------------------------------------------------
# T13-B-06: reset_synthetic_counter()
# ---------------------------------------------------------------------------

class TestResetSyntheticCounter:
    def test_reset_clears_counter(self):
        integrator = _make_integrator(synthetic=True)
        for i in range(4):
            integrator.integrate(epoch_id=f"ep-{i:03d}")
        assert integrator.consecutive_synthetic_epochs == 4
        integrator.reset_synthetic_counter()
        assert integrator.consecutive_synthetic_epochs == 0

    def test_reset_then_integrate_counts_from_one(self):
        integrator = _make_integrator(synthetic=True)
        for i in range(4):
            integrator.integrate(epoch_id=f"ep-{i:03d}")
        integrator.reset_synthetic_counter()
        result = integrator.integrate(epoch_id="ep-after-reset")
        assert result.consecutive_synthetic_epochs == 1


# ---------------------------------------------------------------------------
# T13-B-07: Journal event includes consecutive_synthetic_epochs
# ---------------------------------------------------------------------------

class TestJournalEventIncludesCounter:
    def test_journal_event_has_consecutive_synthetic_epochs(self):
        events = []

        def _capture(event_type, payload):
            events.append({"type": event_type, "payload": payload})

        integrator = MarketFitnessIntegrator(journal_fn=_capture)
        integrator._do_integrate = lambda eid: (_ for _ in ()).throw(RuntimeError("no feed"))  # type: ignore
        integrator.integrate(epoch_id="ep-001")

        integrate_events = [e for e in events if "integrated" in e["type"]]
        assert len(integrate_events) == 1
        assert "consecutive_synthetic_epochs" in integrate_events[0]["payload"]
        assert integrate_events[0]["payload"]["consecutive_synthetic_epochs"] == 1


# ---------------------------------------------------------------------------
# T13-B-08: EpochResult.consecutive_synthetic_market_epochs
# ---------------------------------------------------------------------------

class TestEpochResultConsecutiveSyntheticField:
    def test_epoch_result_has_field(self):
        from runtime.evolution.evolution_loop import EpochResult
        result = EpochResult(
            epoch_id="ep-001",
            generation_count=3,
            total_candidates=5,
            accepted_count=2,
        )
        assert hasattr(result, "consecutive_synthetic_market_epochs")
        assert result.consecutive_synthetic_market_epochs == 0

    def test_epoch_result_field_populated_from_integrator(self):
        from runtime.evolution.evolution_loop import EvolutionLoop, EpochResult
        from runtime.autonomy.ai_mutation_proposer import CodebaseContext

        mock_integrator = MagicMock(spec=MarketFitnessIntegrator)
        mock_integrator.integrate.return_value = IntegrationResult(
            epoch_id="ep-p13",
            live_market_score=0.5,
            confidence=0.0,
            is_synthetic=True,
            adapter_id="synth",
            lineage_digest="sha256:" + "0" * 64,
            signal_source="synthetic",
            consecutive_synthetic_epochs=4,
        )

        loop = EvolutionLoop(api_key="k", simulate_outcomes=True, market_integrator=mock_integrator)
        ctx = CodebaseContext(file_summaries={}, recent_failures=[], current_epoch_id="ep-p13")
        with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value=[]):
            result = loop.run_epoch(ctx)

        assert result.consecutive_synthetic_market_epochs == 4
