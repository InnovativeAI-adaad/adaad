# SPDX-License-Identifier: Apache-2.0
"""Adaptive autonomy threshold budgeting with hash-chained snapshots."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from runtime.governance.foundation.hashing import ZERO_HASH, sha256_prefixed_digest


@dataclass(frozen=True)
class AutonomyBudgetSnapshot:
    cycle_id: str
    governance_debt_score: float
    fitness_trend_delta: float
    epoch_pass_rate: float
    threshold_floor: float
    threshold_ceiling: float
    threshold: float
    prev_hash: str
    snapshot_hash: str
    created_at_ms: int

    def to_record(self) -> dict[str, object]:
        return asdict(self)


class AutonomyBudgetEngine:
    """Compute and persist adaptive autonomy thresholds from governance/runtime signals."""

    def __init__(
        self,
        *,
        snapshot_path: Path | str = "runtime/autonomy/autonomy_budget.snapshots.jsonl",
        base_threshold: float = 0.7,
        threshold_floor: float = 0.35,
        threshold_ceiling: float = 0.9,
        governance_debt_weight: float = 0.20,
        fitness_trend_weight: float = 0.15,
        epoch_pass_rate_weight: float = 0.30,
    ) -> None:
        self.snapshot_path = Path(snapshot_path)
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.base_threshold = float(base_threshold)
        self.threshold_floor = float(threshold_floor)
        self.threshold_ceiling = float(threshold_ceiling)
        self.governance_debt_weight = float(governance_debt_weight)
        self.fitness_trend_weight = float(fitness_trend_weight)
        self.epoch_pass_rate_weight = float(epoch_pass_rate_weight)

    @staticmethod
    def _clamp(value: float, floor: float, ceiling: float) -> float:
        return max(floor, min(ceiling, value))

    def _normalized_signals(self, governance_debt_score: float, fitness_trend_delta: float, epoch_pass_rate: float) -> tuple[float, float, float]:
        debt = self._clamp(float(governance_debt_score), 0.0, 1.0)
        fitness_delta = self._clamp(float(fitness_trend_delta), -1.0, 1.0)
        pass_rate = self._clamp(float(epoch_pass_rate), 0.0, 1.0)
        return debt, fitness_delta, pass_rate

    def compute_threshold(self, *, governance_debt_score: float, fitness_trend_delta: float, epoch_pass_rate: float) -> float:
        debt, fitness_delta, pass_rate = self._normalized_signals(governance_debt_score, fitness_trend_delta, epoch_pass_rate)
        pass_rate_bias = pass_rate - 0.5
        threshold_raw = (
            self.base_threshold
            + (debt * self.governance_debt_weight)
            - (fitness_delta * self.fitness_trend_weight)
            - (pass_rate_bias * self.epoch_pass_rate_weight)
        )
        return self._clamp(threshold_raw, self.threshold_floor, self.threshold_ceiling)

    def _load_snapshots(self) -> list[AutonomyBudgetSnapshot]:
        if not self.snapshot_path.exists():
            return []
        snapshots: list[AutonomyBudgetSnapshot] = []
        for line in self.snapshot_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            snapshots.append(AutonomyBudgetSnapshot(**payload))
        return snapshots

    def _append_snapshot(self, snapshot: AutonomyBudgetSnapshot) -> None:
        with self.snapshot_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(snapshot.to_record(), sort_keys=True) + "\n")

    def record_snapshot(
        self,
        *,
        cycle_id: str,
        governance_debt_score: float,
        fitness_trend_delta: float,
        epoch_pass_rate: float,
        created_at_ms: int | None = None,
    ) -> AutonomyBudgetSnapshot:
        snapshots = self._load_snapshots()
        prev_hash = snapshots[-1].snapshot_hash if snapshots else ZERO_HASH
        threshold = self.compute_threshold(
            governance_debt_score=governance_debt_score,
            fitness_trend_delta=fitness_trend_delta,
            epoch_pass_rate=epoch_pass_rate,
        )
        created = int(time.time() * 1000) if created_at_ms is None else int(created_at_ms)
        payload = {
            "cycle_id": str(cycle_id),
            "governance_debt_score": float(governance_debt_score),
            "fitness_trend_delta": float(fitness_trend_delta),
            "epoch_pass_rate": float(epoch_pass_rate),
            "threshold_floor": self.threshold_floor,
            "threshold_ceiling": self.threshold_ceiling,
            "threshold": threshold,
            "prev_hash": prev_hash,
            "created_at_ms": created,
        }
        snapshot_hash = sha256_prefixed_digest(payload)
        snapshot = AutonomyBudgetSnapshot(**payload, snapshot_hash=snapshot_hash)
        self._append_snapshot(snapshot)
        return snapshot

    def latest_snapshot(self) -> AutonomyBudgetSnapshot | None:
        snapshots = self._load_snapshots()
        return snapshots[-1] if snapshots else None

    def get_current_threshold(self) -> float:
        latest = self.latest_snapshot()
        if latest is None:
            return self._clamp(self.base_threshold, self.threshold_floor, self.threshold_ceiling)
        return self._clamp(float(latest.threshold), self.threshold_floor, self.threshold_ceiling)


__all__ = ["AutonomyBudgetEngine", "AutonomyBudgetSnapshot"]
