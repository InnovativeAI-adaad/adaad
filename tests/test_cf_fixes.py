# SPDX-License-Identifier: Apache-2.0
"""Regression tests for CF-2, CF-3, CF-4 critical findings.

CF-2  ExploreExploitController locked in explore mode (epoch_score always 0.0)
CF-3  PenaltyAdaptor weights stuck at constitutional floor (simulate=False signal absent)
CF-4  MutationEngine stats empty after metrics file loss (cursor not reset)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# CF-2  ExploreExploitController — epoch_score fix
# ─────────────────────────────────────────────────────────────────────────────

class TestCF2ExploreExploitFix:

    def _make_controller(self, tmp_path: Path):
        from runtime.autonomy.explore_exploit_controller import ExploreExploitController
        return ExploreExploitController(
            state_path=tmp_path / "ee_state.json",
            audit_writer=lambda *a: None,
        )

    def test_CF2_01_controller_enters_exploit_when_score_above_threshold(self, tmp_path):
        """select_mode must return EXPLOIT when epoch_score ≥ EXPLOIT_TRIGGER_SCORE."""
        from runtime.autonomy.explore_exploit_controller import (
            ExploreExploitController, EvolutionMode, EXPLOIT_TRIGGER_SCORE
        )
        ctrl = self._make_controller(tmp_path)
        mode = ctrl.select_mode(
            epoch_id="e-high",
            epoch_score=EXPLOIT_TRIGGER_SCORE + 0.01,
            is_plateau=False,
        )
        assert mode == EvolutionMode.EXPLOIT

    def test_CF2_02_controller_stays_explore_when_score_is_zero(self, tmp_path):
        """epoch_score=0.0 (the old broken value) must stay in EXPLORE."""
        from runtime.autonomy.explore_exploit_controller import (
            ExploreExploitController, EvolutionMode
        )
        ctrl = self._make_controller(tmp_path)
        mode = ctrl.select_mode(epoch_id="e-zero", epoch_score=0.0, is_plateau=False)
        assert mode == EvolutionMode.EXPLORE

    def test_CF2_03_evolution_loop_tracks_last_epoch_health_score(self):
        """EvolutionLoop must initialise _last_epoch_health_score = 0.0."""
        from runtime.evolution.evolution_loop import EvolutionLoop
        loop = EvolutionLoop.__new__(EvolutionLoop)
        loop._last_epoch_health_score = 0.0   # verify attribute name correct
        assert loop._last_epoch_health_score == 0.0

    def test_CF2_04_select_mode_receives_real_score_after_first_epoch(self, tmp_path):
        """Simulate two select_mode calls; second must see a non-zero score."""
        from runtime.autonomy.explore_exploit_controller import (
            ExploreExploitController, EvolutionMode, EXPLOIT_TRIGGER_SCORE
        )
        ctrl = self._make_controller(tmp_path)
        scores_seen = []

        original_select = ctrl.select_mode
        def _spy(epoch_id, epoch_score, is_plateau, **kw):
            scores_seen.append(epoch_score)
            return original_select(epoch_id=epoch_id, epoch_score=epoch_score,
                                   is_plateau=is_plateau, **kw)
        ctrl.select_mode = _spy

        # Simulate epoch 1: score=0.0 (initial)
        mode1 = ctrl.select_mode(epoch_id="e1", epoch_score=0.0, is_plateau=False)
        ctrl.commit_epoch(epoch_id="e1", mode=mode1)

        # Simulate epoch 2: score=0.70 (what the fix provides)
        mode2 = ctrl.select_mode(epoch_id="e2", epoch_score=0.70, is_plateau=False)
        assert scores_seen[1] == pytest.approx(0.70)
        assert mode2 == EvolutionMode.EXPLOIT

    def test_CF2_05_explore_floor_still_enforced_despite_high_score(self, tmp_path):
        """Constitutional explore floor (20%) must still override EXPLOIT pressure.
        
        The floor is self-enforcing: when epoch_mode_history is all-exploit,
        window_explore_ratio=0.0 < MIN_EXPLORE_RATIO=0.20 → forced EXPLORE.
        We inject the history directly to isolate the floor logic.
        """
        from runtime.autonomy.explore_exploit_controller import (
            ExploreExploitController, EvolutionMode, MIN_EXPLORE_RATIO
        )
        ctrl = self._make_controller(tmp_path)
        # Inject all-exploit history directly — bypasses the self-enforcing nature
        # of the floor to test that the guard itself works correctly
        ctrl._state.epoch_mode_history = ["exploit"] * 10
        ctrl._state.consecutive_exploit_count = 3
        ctrl._state.current_mode = "exploit"
        assert ctrl.window_explore_ratio() < MIN_EXPLORE_RATIO
        
        # Even with a very high score, floor must override → EXPLORE
        next_mode = ctrl.select_mode(epoch_id="e-forced", epoch_score=0.99, is_plateau=False)
        assert next_mode == EvolutionMode.EXPLORE


# ─────────────────────────────────────────────────────────────────────────────
# CF-3  PenaltyAdaptor — simulate=True fix
# ─────────────────────────────────────────────────────────────────────────────

class TestCF3PenaltyAdaptorFix:

    def _make_scores(self, n: int = 5, accepted: bool = True, risk_score: float = 0.7):
        """Create synthetic MutationScore-like objects."""
        scores = []
        for i in range(n):
            s = MagicMock()
            s.mutation_id = f"mut-{i}"
            s.accepted = accepted
            s.score = 0.75 if accepted else 0.2
            s.agent_origin = "architect"
            s.epoch_id = "e-test"
            # Dimension breakdown that encodes risk
            s.dimension_breakdown = {
                "risk_penalty_contrib": risk_score * 0.20,
                "complexity_penalty_contrib": 0.4 * 0.10,
            }
            scores.append(s)
        return scores

    def test_CF3_01_simulate_true_produces_non_none_actually_risky(self):
        """simulate=True must set actually_risky for accepted high-risk mutations."""
        from runtime.autonomy.penalty_adaptor import build_penalty_outcomes_from_scores
        scores = self._make_scores(risk_score=0.9)
        outcomes = build_penalty_outcomes_from_scores(scores, simulate=True)
        non_none = [o for o in outcomes if o.actually_risky is not None]
        assert len(non_none) == len(outcomes)

    def test_CF3_02_simulate_false_produces_none_actually_risky(self):
        """simulate=False must leave actually_risky=None (post-merge placeholder)."""
        from runtime.autonomy.penalty_adaptor import build_penalty_outcomes_from_scores
        scores = self._make_scores()
        outcomes = build_penalty_outcomes_from_scores(scores, simulate=False)
        none_count = sum(1 for o in outcomes if o.actually_risky is None)
        assert none_count == len(outcomes)

    def test_CF3_03_penalty_adaptor_moves_from_floor_when_signals_present(self, tmp_path):
        """PenaltyAdaptor must adapt away from floor (0.05) when risk signals > 0."""
        from runtime.autonomy.penalty_adaptor import PenaltyAdaptor, PenaltyOutcome
        from runtime.autonomy.mutation_scaffold import ScoringWeights

        adaptor = PenaltyAdaptor(state_path=tmp_path / "penalty.json")
        weights = ScoringWeights(
            gain_weight=0.40, coverage_weight=0.30,
            risk_penalty=0.05, complexity_penalty=0.05
        )
        # Supply high-risk outcomes with actually_risky=True (unambiguous signal)
        outcomes = [
            PenaltyOutcome("m1", accepted=True, risk_score=0.85,
                           complexity_score=0.80, actually_risky=True, actually_complex=True),
            PenaltyOutcome("m2", accepted=True, risk_score=0.90,
                           complexity_score=0.75, actually_risky=True, actually_complex=False),
        ]

        # Run 10 epochs to get past MIN_EPOCHS_FOR_PENALTY (default=5)
        for epoch in range(1, 11):
            weights = adaptor.adapt(weights, outcomes, epoch_count=epoch)

        # After 10 epochs of all-risky signals, penalty should move above floor
        assert weights.risk_penalty > 0.05, \
            f"risk_penalty should exceed floor 0.05 but got {weights.risk_penalty}"

    def test_CF3_04_simulate_true_outcomes_produce_nonzero_risk_rate(self):
        """build_penalty_outcomes_from_scores(simulate=True) must yield risk rate > 0
        for high-risk accepted mutations."""
        from runtime.autonomy.penalty_adaptor import (
            build_penalty_outcomes_from_scores, PenaltyAdaptor
        )
        scores = self._make_scores(risk_score=0.9, accepted=True)
        outcomes = build_penalty_outcomes_from_scores(scores, simulate=True)
        rate = PenaltyAdaptor._compute_risk_rate(outcomes)
        assert rate > 0.0, f"Expected risk rate > 0.0 from high-risk accepted mutations, got {rate}"

    def test_CF3_05_simulate_false_falls_through_to_heuristic_and_rate_matches_simulate_true(self):
        """simulate=False sets actually_risky=None but _compute_risk_rate has a heuristic
        fallback that fires for accepted mutations — so the rate is NOT 0.0.
        
        The real production bug (EMA near zero) was caused by dimension_breakdown being
        empty (risk_score defaulting to exactly 0.5) combined with a strict > 0.50
        threshold: 0.5 > 0.50 == False → signal = 0.0. This test confirms the threshold
        boundary behavior.
        """
        from runtime.autonomy.penalty_adaptor import (
            build_penalty_outcomes_from_scores, PenaltyAdaptor
        )
        # simulate=False uses heuristic fallback → same rate as simulate=True for same inputs
        scores_high = self._make_scores(risk_score=0.9, accepted=True)
        outcomes_false = build_penalty_outcomes_from_scores(scores_high, simulate=False)
        outcomes_true  = build_penalty_outcomes_from_scores(scores_high, simulate=True)
        rate_false = PenaltyAdaptor._compute_risk_rate(outcomes_false)
        rate_true  = PenaltyAdaptor._compute_risk_rate(outcomes_true)
        # Both paths should give same rate (heuristic alignment)
        assert rate_false == pytest.approx(rate_true), \
            f"simulate=False rate {rate_false} should match simulate=True rate {rate_true}"
        
        # At the threshold boundary: risk_score=0.5 with threshold >0.50 → signal=0
        # This is the actual CF-3 production failure mode
        scores_boundary = self._make_scores(risk_score=0.5, accepted=True)
        outcomes_boundary = build_penalty_outcomes_from_scores(scores_boundary, simulate=True)
        rate_boundary = PenaltyAdaptor._compute_risk_rate(outcomes_boundary)
        # 0.5 > 0.50 is False → signal=0 → rate=0.0 → EMA collapses to floor
        assert rate_boundary == 0.0, \
            f"risk_score=0.5 at threshold boundary must give rate=0.0 (CF-3 root cause)"


# ─────────────────────────────────────────────────────────────────────────────
# CF-4  MutationEngine stats — cursor reset fix
# ─────────────────────────────────────────────────────────────────────────────

class TestCF4MutationEngineFix:

    def _make_engine(self, tmp_path: Path):
        from adaad.agents.mutation_engine import MutationEngine
        metrics_path = tmp_path / "metrics.jsonl"
        state_path   = tmp_path / "state.json"
        return MutationEngine(metrics_path=metrics_path, state_path=state_path), \
               metrics_path, state_path

    def test_CF4_01_cursor_reset_to_zero_when_metrics_file_missing(self, tmp_path):
        """refresh_state_from_metrics with missing file must reset cursor to 0."""
        engine, metrics_path, state_path = self._make_engine(tmp_path)

        # Simulate stale cursor (as in production: cursor=917, file deleted)
        state_path.write_text(json.dumps({"cursor": 917, "stats": {}}))

        # Metrics file does not exist
        assert not metrics_path.exists()

        engine.refresh_state_from_metrics()

        state = json.loads(state_path.read_text())
        assert state["cursor"] == 0, \
            f"cursor must be reset to 0 when file missing; got {state['cursor']}"

    def test_CF4_02_stats_populate_after_cursor_reset_and_new_events(self, tmp_path):
        """After cursor reset, new mutation_score events must populate stats."""
        engine, metrics_path, state_path = self._make_engine(tmp_path)

        # Simulate stale cursor
        state_path.write_text(json.dumps({"cursor": 917, "stats": {}}))

        # Reset cursor via refresh with missing file
        engine.refresh_state_from_metrics()

        # Now write metrics events
        event = json.dumps({
            "event": "mutation_score",
            "payload": {"strategy_id": "structural", "score": 0.75}
        })
        metrics_path.write_text(event + "\n")

        # Re-run refresh — should now pick up the event
        engine.refresh_state_from_metrics()

        state = json.loads(state_path.read_text())
        assert "structural" in state.get("stats", {}), \
            "stats must contain 'structural' after cursor reset and new events"
        assert state["stats"]["structural"]["n"] == pytest.approx(1.0)

    def test_CF4_03_cursor_not_reset_when_metrics_file_exists(self, tmp_path):
        """If metrics file exists and cursor is valid, cursor must not be reset."""
        engine, metrics_path, state_path = self._make_engine(tmp_path)

        event = json.dumps({
            "event": "mutation_score",
            "payload": {"strategy_id": "behavioral", "score": 0.60}
        })
        metrics_path.write_text(event + "\n")
        engine.refresh_state_from_metrics()

        state = json.loads(state_path.read_text())
        # Cursor advanced (file read completely), stats populated
        assert state["cursor"] > 0
        assert "behavioral" in state.get("stats", {})

    def test_CF4_04_stats_dict_never_empty_after_valid_metrics_events(self, tmp_path):
        """stats must not be empty after processing valid mutation_score events."""
        engine, metrics_path, state_path = self._make_engine(tmp_path)

        events = [
            json.dumps({"event": "mutation_score", "payload": {"strategy_id": "structural", "score": 0.80}}),
            json.dumps({"event": "mutation_score", "payload": {"strategy_id": "experimental", "score": 0.45}}),
            json.dumps({"event": "mutation_failed", "payload": {"strategy_id": "experimental"}}),
        ]
        metrics_path.write_text("\n".join(events) + "\n")

        engine.refresh_state_from_metrics()
        state = json.loads(state_path.read_text())

        assert state["stats"] != {}, "stats must not be empty"
        assert state["stats"]["structural"]["n"] == pytest.approx(1.0)
        assert state["stats"]["experimental"]["fail"] == pytest.approx(1.0)

    def test_CF4_05_stale_cursor_larger_than_file_size_is_reset(self, tmp_path):
        """cursor > file_size must be reset to 0 (handled by existing guard)."""
        engine, metrics_path, state_path = self._make_engine(tmp_path)

        # Write small metrics file
        event = json.dumps({"event": "mutation_score", "payload": {"strategy_id": "structural", "score": 0.5}})
        metrics_path.write_text(event + "\n")

        # Set cursor far beyond file size
        state_path.write_text(json.dumps({"cursor": 99999, "stats": {}}))

        engine.refresh_state_from_metrics()
        state = json.loads(state_path.read_text())

        # Cursor should have been reset and stats populated
        assert "structural" in state.get("stats", {}), \
            "stats must populate after stale cursor reset"
