# SPDX-License-Identifier: Apache-2.0
"""Deterministic rolling fitness regression and regression signal derivation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import sqrt
from typing import Any, Dict, Iterable, List, Mapping


class RegressionSeverity(str, Enum):
    STABLE = "stable"
    WATCH = "watch"
    SEVERE = "severe"


@dataclass(frozen=True)
class FitnessRegressionSignal:
    epoch_mean_fitness: float
    window_size: int
    sample_count: int
    slope: float
    intercept: float
    r_squared: float
    slope_stderr: float
    confidence_score: float
    severity: RegressionSeverity
    rule_contributors: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch_mean_fitness": self.epoch_mean_fitness,
            "window_size": self.window_size,
            "sample_count": self.sample_count,
            "slope": self.slope,
            "intercept": self.intercept,
            "r_squared": self.r_squared,
            "slope_stderr": self.slope_stderr,
            "confidence_score": self.confidence_score,
            "severity": self.severity.value,
            "rule_contributors": self.rule_contributors,
        }


def emit_fitness_regression_signal(entries: Iterable[Mapping[str, object]], *, window_size: int = 8) -> FitnessRegressionSignal:
    points = _rolling_epoch_mean_fitness(entries, window_size=max(2, int(window_size)))
    slope, intercept, r_squared, slope_stderr = _linear_regression(points)

    confidence_score = max(0.0, min(1.0, (r_squared * 0.7) + (max(0.0, -slope) * 5.0)))
    severity = RegressionSeverity.STABLE
    contributors: List[Dict[str, Any]] = []

    if slope <= -0.010:
        contributors.append({"rule_id": "negative_slope", "value": slope, "threshold": -0.010, "triggered": True})
        severity = RegressionSeverity.WATCH
    if r_squared >= 0.55 and slope <= -0.015:
        contributors.append({"rule_id": "high_confidence_decline", "value": r_squared, "threshold": 0.55, "triggered": True})
        severity = RegressionSeverity.WATCH
    if slope <= -0.025 and r_squared >= 0.65 and len(points) >= max(4, window_size // 2):
        contributors.append({"rule_id": "severe_trend_regression", "value": slope, "threshold": -0.025, "triggered": True})
        severity = RegressionSeverity.SEVERE
    if slope_stderr > 0.030:
        contributors.append({"rule_id": "high_slope_uncertainty", "value": slope_stderr, "threshold": 0.030, "triggered": True})

    if not contributors:
        contributors.append({"rule_id": "no_regression_detected", "triggered": True})

    epoch_mean_fitness = (sum(point[1] for point in points) / len(points)) if points else 0.0
    return FitnessRegressionSignal(
        epoch_mean_fitness=epoch_mean_fitness,
        window_size=max(2, int(window_size)),
        sample_count=len(points),
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        slope_stderr=slope_stderr,
        confidence_score=confidence_score,
        severity=severity,
        rule_contributors=contributors,
    )


def _rolling_epoch_mean_fitness(entries: Iterable[Mapping[str, object]], window_size: int) -> List[tuple[float, float]]:
    rows = [dict(item) for item in entries if isinstance(item, Mapping)]
    rows.sort(key=lambda item: (str(item.get("epoch_id") or ""), str(item.get("cycle_id") or "")))

    values: List[float] = []
    for row in rows:
        values.append(_fitness_value(row))

    points: List[tuple[float, float]] = []
    if not values:
        return points

    start_idx = max(0, len(values) - window_size)
    selected = values[start_idx:]
    for index, _ in enumerate(selected):
        prefix = selected[: index + 1]
        mean_fitness = sum(prefix) / len(prefix)
        points.append((float(index), float(mean_fitness)))
    return points


def _fitness_value(row: Mapping[str, object]) -> float:
    if "fitness_score" in row:
        return float(row.get("fitness_score") or 0.0)
    if "goal_score_delta" in row:
        base = 0.5 + (float(row.get("goal_score_delta") or 0.0) / 2.0)
        return max(0.0, min(1.0, base))
    return 0.0


def _linear_regression(points: List[tuple[float, float]]) -> tuple[float, float, float, float]:
    n = len(points)
    if n < 2:
        return (0.0, points[0][1] if n == 1 else 0.0, 0.0, 0.0)

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n

    ss_xx = sum((x - x_mean) ** 2 for x in xs)
    if ss_xx <= 0.0:
        return (0.0, y_mean, 0.0, 0.0)

    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in points)
    slope = ss_xy / ss_xx
    intercept = y_mean - (slope * x_mean)

    y_hat = [(slope * x) + intercept for x in xs]
    ss_res = sum((y - yh) ** 2 for y, yh in zip(ys, y_hat))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    r_squared = max(0.0, min(1.0, 1.0 - (ss_res / ss_tot))) if ss_tot > 0.0 else 0.0

    dof = max(1, n - 2)
    sigma2 = ss_res / dof
    slope_stderr = sqrt(sigma2 / ss_xx) if ss_xx > 0.0 else 0.0
    return (float(slope), float(intercept), float(r_squared), float(slope_stderr))


__all__ = ["FitnessRegressionSignal", "RegressionSeverity", "emit_fitness_regression_signal"]
