# SPDX-License-Identifier: Apache-2.0
"""Tests for BanditSelector (UCB1) — Phase 2 agent selection."""

from __future__ import annotations

import math
import pytest

from runtime.autonomy.bandit_selector import (
    AGENTS,
    EXPLORATION_CONSTANT,
    MIN_PULLS_FOR_BANDIT,
    ArmState,
    BanditSelector,
    ThompsonBanditSelector,
)


# ---------------------------------------------------------------------------
# ArmState
# ---------------------------------------------------------------------------

class TestArmState:
    def test_pulls_is_sum(self):
        arm = ArmState(agent="architect", wins=3, losses=2)
        assert arm.pulls == 5

    def test_win_rate_zero_pulls(self):
        arm = ArmState(agent="beast")
        assert arm.win_rate == 0.0

    def test_win_rate_computed(self):
        arm = ArmState(agent="dream", wins=3, losses=1)
        assert arm.win_rate == pytest.approx(0.75)

    def test_ucb1_infinite_for_unpulled(self):
        arm = ArmState(agent="architect")
        assert arm.ucb1_score(total_pulls=10) == float("inf")

    def test_ucb1_score_formula(self):
        # wins=6, losses=4 → win_rate=0.6, pulls=10, total=20
        arm = ArmState(agent="beast", wins=6, losses=4)
        expected = 0.6 + EXPLORATION_CONSTANT * math.sqrt(math.log(20) / 10)
        assert arm.ucb1_score(total_pulls=20) == pytest.approx(expected, rel=1e-6)

    def test_ucb1_zero_total_returns_win_rate(self):
        arm = ArmState(agent="dream", wins=5, losses=5)
        assert arm.ucb1_score(total_pulls=0) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# BanditSelector — basic operation
# ---------------------------------------------------------------------------

class TestBanditSelectorBasic:
    def test_initial_total_pulls_zero(self):
        b = BanditSelector()
        assert b.total_pulls == 0

    def test_is_active_false_below_threshold(self):
        b = BanditSelector()
        for _ in range(MIN_PULLS_FOR_BANDIT - 1):
            b.record("beast", won=True)
        assert not b.is_active

    def test_is_active_true_at_threshold(self):
        b = BanditSelector()
        for _ in range(MIN_PULLS_FOR_BANDIT):
            b.record("beast", won=True)
        assert b.is_active

    def test_select_returns_valid_agent(self):
        b = BanditSelector()
        for _ in range(5):
            b.record("architect", won=True)
        assert b.select() in AGENTS

    def test_select_unpulled_arms_first(self):
        b = BanditSelector()
        b.record("beast", won=True)   # only beast has pulls
        # architect and dream are unpulled → +inf → either will beat beast
        result = b.select()
        assert result in ("architect", "dream")

    def test_deterministic_select(self):
        """Identical state → identical selection."""
        b1, b2 = BanditSelector(), BanditSelector()
        for agent, won in [("architect", True), ("beast", False), ("dream", True),
                           ("architect", True), ("beast", True)]:
            b1.record(agent, won)
            b2.record(agent, won)
        assert b1.select() == b2.select()

    def test_best_exploit_highest_win_rate(self):
        b = BanditSelector()
        for _ in range(8):
            b.record("dream", won=True)
        b.record("dream", won=False)   # 8/9 ≈ 0.889
        for _ in range(5):
            b.record("beast", won=True)
        b.record("beast", won=False)   # 5/6 ≈ 0.833
        assert b.best_exploit() == "dream"


# ---------------------------------------------------------------------------
# UCB1 exploration/exploitation balance
# ---------------------------------------------------------------------------

class TestUCB1Balance:
    def test_exploration_bonus_favors_less_sampled(self):
        b = BanditSelector()
        # architect: 10 wins, 0 losses → win_rate=1.0, pulls=10
        for _ in range(10):
            b.record("architect", won=True)
        # beast: 1 win, 0 losses → win_rate=1.0, pulls=1 (exploration bonus larger)
        b.record("beast", won=True)
        # With total_pulls=11, beast has higher UCB1 than architect despite equal win_rate
        scores = b.ucb1_scores()
        assert scores["beast"] > scores["architect"]

    def test_high_win_rate_exploited_when_well_sampled(self):
        b = BanditSelector()
        # Give all agents equal pulls; architect has best win rate
        for _ in range(5):
            b.record("architect", won=True)
        for _ in range(2):
            b.record("beast", won=True)
        b.record("beast", won=False)
        for _ in range(3):
            b.record("dream", won=True)
        for _ in range(3):
            b.record("dream", won=False)
        # After more epochs when exploration bonuses equalize, architect should lead
        # Add many more pulls to reduce exploration bonus dominance
        for _ in range(20):
            b.record("architect", won=True)
        for _ in range(20):
            b.record("beast", won=False)
        assert b.best_exploit() == "architect"


# ---------------------------------------------------------------------------
# Persistence round-trip
# ---------------------------------------------------------------------------

class TestBanditSelectorPersistence:
    def test_to_state_round_trip(self):
        b = BanditSelector()
        b.record("architect", won=True)
        b.record("beast", won=False)
        b.record("dream", won=True)
        state = b.to_state()
        b2 = BanditSelector.from_state(state)
        assert b2.total_pulls == 3
        assert b2._arms["architect"].wins == 1
        assert b2._arms["beast"].losses == 1

    def test_from_state_unknown_keys_ignored(self):
        state = {"algorithm": "ucb1", "exploration_c": 1.4142, "arms": {
            "architect": {"wins": 2, "losses": 1},
            "unknown_agent": {"wins": 99, "losses": 0},   # should be ignored
        }}
        b = BanditSelector.from_state(state)
        assert "unknown_agent" not in b._arms

    def test_exploration_constant_preserved(self):
        b = BanditSelector(exploration_c=0.5)
        b.record("beast", won=True)
        state = b.to_state()
        b2 = BanditSelector.from_state(state)
        assert b2._c == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Bootstrap from FitnessLandscape records
# ---------------------------------------------------------------------------

class TestFromLandscapeRecords:
    def test_structural_maps_to_architect(self):
        records = {"structural": {"wins": 5, "losses": 2}}
        b = BanditSelector.from_landscape_records(records)
        assert b._arms["architect"].wins == 5
        assert b._arms["architect"].losses == 2

    def test_performance_maps_to_beast(self):
        records = {"performance": {"wins": 3, "losses": 1}}
        b = BanditSelector.from_landscape_records(records)
        assert b._arms["beast"].wins == 3

    def test_unknown_type_maps_to_dream(self):
        records = {"experimental_patch": {"wins": 2, "losses": 4}}
        b = BanditSelector.from_landscape_records(records)
        assert b._arms["dream"].wins == 2
        assert b._arms["dream"].losses == 4

    def test_custom_agent_type_map(self):
        records = {"hotfix": {"wins": 7, "losses": 0}}
        b = BanditSelector.from_landscape_records(
            records, agent_type_map={"hotfix": "architect"}
        )
        assert b._arms["architect"].wins == 7


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestBanditSelectorSummary:
    def test_summary_structure(self):
        b = BanditSelector()
        b.record("architect", won=True)
        s = b.summary()
        assert s["algorithm"] == "ucb1"
        assert "total_pulls" in s
        assert "is_active" in s
        assert "ucb1_scores" in s
        assert "arms" in s

    def test_summary_selected_none_when_no_pulls(self):
        b = BanditSelector()
        assert b.summary()["selected"] is None


# ---------------------------------------------------------------------------
# ThompsonBanditSelector (Phase 3 extension — verify it runs deterministically
# when seeded, but is NOT integrated in v2.0.0)
# ---------------------------------------------------------------------------

class TestThompsonBanditSelector:
    def test_seeded_determinism(self):
        import random
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        t1 = ThompsonBanditSelector(rng=rng1)
        t2 = ThompsonBanditSelector(rng=rng2)
        for agent, won in [("architect", True), ("beast", False), ("dream", True)]:
            t1.record(agent, won)
            t2.record(agent, won)
        assert t1.select() == t2.select()

    def test_returns_valid_agent(self):
        import random
        rng = random.Random(99)
        t = ThompsonBanditSelector(rng=rng)
        t.record("dream", won=True)
        assert t.select() in AGENTS
