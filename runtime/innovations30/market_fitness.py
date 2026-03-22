# SPDX-License-Identifier: Apache-2.0
"""Innovation #22 — Market-Conditioned Fitness.
Real external signals feed into fitness scoring.
"""
from __future__ import annotations
import json, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

@dataclass
class ExternalSignal:
    signal_id: str
    source: str          # "github_stars" | "benchmark_rank" | "api_latency"
    value: float         # normalized 0–1
    direction: float     # -1 (worsening), 0 (stable), +1 (improving)
    timestamp: float
    weight: float = 0.10


class MarketConditionedFitness:
    """Anchors fitness to external market validation signals."""

    def __init__(self, signals_path: Path = Path("data/market_signals.jsonl"),
                 signal_weight: float = 0.10):
        self.signals_path = Path(signals_path)
        self.signal_weight = signal_weight
        self._signals: dict[str, ExternalSignal] = {}
        self._load()

    def register_signal(self, signal: ExternalSignal) -> None:
        self._signals[signal.signal_id] = signal
        self._persist(signal)

    def adjust_fitness(self, base_fitness: float, mutation_id: str) -> float:
        """Adjust fitness score based on recent market signal directions."""
        if not self._signals:
            return base_fitness
        recent = [s for s in self._signals.values()
                   if time.time() - s.timestamp < 86400 * 7]  # 7 days
        if not recent:
            return base_fitness
        avg_direction = sum(s.direction * s.weight for s in recent) / len(recent)
        # Positive market signals boost fitness slightly; negative penalize
        adjustment = avg_direction * self.signal_weight
        return max(0.0, min(1.0, base_fitness + adjustment))

    def market_health_score(self) -> float:
        if not self._signals:
            return 1.0
        values = [s.value for s in self._signals.values()]
        return round(sum(values) / len(values), 4)

    def _load(self) -> None:
        if not self.signals_path.exists():
            return
        for line in self.signals_path.read_text().splitlines():
            try:
                d = json.loads(line)
                s = ExternalSignal(**d)
                self._signals[s.signal_id] = s
            except Exception:
                pass

    def _persist(self, signal: ExternalSignal) -> None:
        import dataclasses
        self.signals_path.parent.mkdir(parents=True, exist_ok=True)
        with self.signals_path.open("a") as f:
            f.write(json.dumps(dataclasses.asdict(signal)) + "\n")


__all__ = ["MarketConditionedFitness", "ExternalSignal"]
