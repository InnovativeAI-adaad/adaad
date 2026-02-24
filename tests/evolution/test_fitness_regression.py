# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.fitness_regression import RegressionSeverity, emit_fitness_regression_signal


def test_emit_fitness_regression_signal_detects_severe_decline() -> None:
    entries = [
        {"epoch_id": "epoch-1", "cycle_id": f"c-{index:03d}", "fitness_score": score}
        for index, score in enumerate([0.95, 0.91, 0.85, 0.80, 0.74, 0.69, 0.62, 0.58], start=1)
    ]

    signal = emit_fitness_regression_signal(entries, window_size=8)

    assert signal.severity == RegressionSeverity.SEVERE
    assert signal.slope < 0.0
    assert signal.sample_count == 8
    assert any(item.get("rule_id") == "severe_trend_regression" for item in signal.rule_contributors)


def test_emit_fitness_regression_signal_is_stable_for_flat_trend() -> None:
    entries = [
        {"epoch_id": "epoch-1", "cycle_id": f"c-{index:03d}", "fitness_score": 0.72}
        for index in range(1, 6)
    ]

    signal = emit_fitness_regression_signal(entries, window_size=5)

    assert signal.severity == RegressionSeverity.STABLE
    assert signal.slope == 0.0
