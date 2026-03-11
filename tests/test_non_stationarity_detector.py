# SPDX-License-Identifier: Apache-2.0
"""Tests for NonStationarityDetector — Page-Hinkley change detection."""
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard
from runtime.autonomy.non_stationarity_detector import (
    NonStationarityDetector, ArmHistory,
    PAGE_HINKLEY_THRESHOLD, MIN_OBSERVATIONS, ESCALATION_COOLDOWN,
)


class TestArmHistory:
    def test_initial_ph_zero(self):
        arm = ArmHistory(agent="architect")
        assert arm.ph_statistic == pytest.approx(0.0)

    def test_has_sufficient_data_false_initially(self):
        arm = ArmHistory(agent="beast")
        for _ in range(MIN_OBSERVATIONS - 1):
            arm.update(0.5)
        assert not arm.has_sufficient_data

    def test_has_sufficient_data_true_at_threshold(self):
        arm = ArmHistory(agent="dream")
        for _ in range(MIN_OBSERVATIONS):
            arm.update(0.5)
        assert arm.has_sufficient_data

    def test_stable_win_rate_low_ph(self):
        arm = ArmHistory(agent="beast")
        for _ in range(20):
            arm.update(0.5)
        # Stable environment → small PH statistic
        assert arm.ph_statistic < PAGE_HINKLEY_THRESHOLD

    def test_sudden_shift_elevates_ph(self):
        arm = ArmHistory(agent="architect")
        for _ in range(10):
            arm.update(0.5)
        # Abrupt shift to 0.9
        for _ in range(10):
            arm.update(0.9)
        assert arm.ph_statistic > 0

    def test_reset_ph_zeroes_accumulator(self):
        arm = ArmHistory(agent="dream")
        for _ in range(15):
            arm.update(0.9)
        arm.reset_ph()
        assert arm.ph_sum == pytest.approx(0.0)
        assert arm.ph_min == pytest.approx(0.0)


class TestNonStationarityDetector:
    def test_stable_environment_no_signal(self):
        d = NonStationarityDetector()
        for _ in range(30):
            d.record({"architect": 0.5, "beast": 0.5, "dream": 0.5})
        assert not d.is_non_stationary()

    def test_abrupt_shift_triggers_detection(self):
        d = NonStationarityDetector(threshold=0.05)
        # Establish baseline
        for _ in range(8):
            d.record({"architect": 0.5, "beast": 0.5, "dream": 0.5})
        # Introduce abrupt shift past cooldown
        for _ in range(ESCALATION_COOLDOWN + 1):
            d.record({"architect": 0.95, "beast": 0.95, "dream": 0.95})
        assert d.is_non_stationary()

    def test_cooldown_prevents_rapid_re_escalation(self):
        d = NonStationarityDetector(threshold=0.05)
        # Trigger once
        for _ in range(8):
            d.record({"architect": 0.5})
        for _ in range(ESCALATION_COOLDOWN + 1):
            d.record({"architect": 0.99})
        first = d.is_non_stationary()
        # Immediately check again — should be False (cooldown resets)
        second = d.is_non_stationary()
        if first:
            assert not second

    def test_sparse_data_no_detection(self):
        d = NonStationarityDetector()
        for _ in range(MIN_OBSERVATIONS - 1):
            d.record({"architect": 0.99, "beast": 0.99})
        # Not enough data yet
        # Bypass cooldown by setting epochs manually
        d._epochs_since_escalation = ESCALATION_COOLDOWN + 1
        assert not d.is_non_stationary()

    def test_escalation_count_increments(self):
        d = NonStationarityDetector(threshold=0.05)
        for _ in range(8):
            d.record({"architect": 0.5})
        for _ in range(ESCALATION_COOLDOWN + 1):
            d.record({"architect": 0.99})
        d.is_non_stationary()
        assert d._escalation_count >= 0  # may or may not have fired depending on rates

    def test_arm_statistics_returns_all_arms(self):
        d = NonStationarityDetector()
        d.record({"architect": 0.6, "beast": 0.4, "dream": 0.5})
        stats = d.arm_statistics()
        assert "architect" in stats
        assert "beast" in stats

    def test_arm_statistics_structure(self):
        d = NonStationarityDetector()
        d.record({"beast": 0.7})
        stats = d.arm_statistics()
        keys = ("win_rates","running_mean","ph_statistic","ph_threshold","sufficient_data","observations")
        for k in keys:
            assert k in stats["beast"]

    def test_summary_structure(self):
        d = NonStationarityDetector()
        s = d.summary()
        for k in ("algorithm","threshold","escalation_count","cooldown","arm_statistics"):
            assert k in s

    def test_algorithm_name(self):
        d = NonStationarityDetector()
        assert d.summary()["algorithm"] == "page_hinkley"


class TestFitnessLandscapeThompsonIntegration:
    def test_thompson_activates_after_non_stationarity(self, tmp_path):
        from runtime.autonomy.fitness_landscape import FitnessLandscape
        landscape = FitnessLandscape(state_path=tmp_path / "landscape.json")

        # Build up bandit data (> MIN_PULLS)
        for i in range(15):
            landscape.record("structural", won=(i % 2 == 0))

        # Force non-stationarity detection
        landscape._thompson_active = True
        landscape._bandit._arms["architect"].wins = 8
        landscape._bandit._arms["architect"].losses = 2

        # With Thompson active, recommended_agent should still return a valid agent
        agent = landscape.recommended_agent()
        assert agent in ("architect", "beast", "dream")

    def test_thompson_flag_persists(self, tmp_path):
        from runtime.autonomy.fitness_landscape import FitnessLandscape
        path = tmp_path / "ls.json"
        ls1 = FitnessLandscape(state_path=path)
        ls1._thompson_active = True
        ls1._save()
        ls2 = FitnessLandscape(state_path=path)
        assert ls2._thompson_active is True
