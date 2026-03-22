# SPDX-License-Identifier: Apache-2.0
"""Innovation #30 — The Mirror Test.

Every 50 epochs, present the system with historical mutation proposals
(outcomes redacted) and measure how accurately it predicts:
  - Which constitutional rules fired
  - Pass/fail outcome
  - Approximate fitness score

Low accuracy triggers ConstitutionalCalibrationEpoch before resuming.
"""
from __future__ import annotations
import hashlib, json, statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

MIRROR_TEST_INTERVAL: int = 50
CALIBRATION_THRESHOLD: float = 0.60  # below this → calibration epoch
MIRROR_TEST_SAMPLE: int = 20

@dataclass
class MirrorPrediction:
    mutation_id: str
    predicted_pass: bool
    predicted_rules_fired: list[str]
    predicted_fitness: float
    actual_pass: bool
    actual_rules_fired: list[str]
    actual_fitness: float

    @property
    def pass_correct(self) -> bool:
        return self.predicted_pass == self.actual_pass

    @property
    def rules_precision(self) -> float:
        if not self.predicted_rules_fired:
            return 1.0 if not self.actual_rules_fired else 0.0
        correct = set(self.predicted_rules_fired) & set(self.actual_rules_fired)
        return len(correct) / max(len(self.predicted_rules_fired), len(self.actual_rules_fired))

    @property
    def fitness_error(self) -> float:
        return abs(self.predicted_fitness - self.actual_fitness)


@dataclass
class MirrorTestResult:
    epoch_id: str
    sample_size: int
    pass_accuracy: float
    rules_precision: float
    fitness_mae: float
    overall_score: float
    requires_calibration: bool
    predictions: list[MirrorPrediction] = field(default_factory=list)
    result_digest: str = ""

    def __post_init__(self):
        if not self.result_digest:
            payload = json.dumps({
                "epoch_id": self.epoch_id,
                "pass_accuracy": round(self.overall_score, 6),
                "sample_size": self.sample_size,
            }, sort_keys=True)
            self.result_digest = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


class MirrorTestEngine:
    """Measures whether ADAAD understands its own governance decisions."""

    def __init__(self, state_path: Path = Path("data/mirror_test_state.jsonl"),
                 interval: int = MIRROR_TEST_INTERVAL,
                 calibration_threshold: float = CALIBRATION_THRESHOLD):
        self.state_path = Path(state_path)
        self.interval = interval
        self.threshold = calibration_threshold

    def should_run(self, epoch_seq: int) -> bool:
        return epoch_seq > 0 and epoch_seq % self.interval == 0

    def run(self, epoch_id: str, historical_records: list[dict[str, Any]],
            predictor_fn) -> MirrorTestResult:
        """Run mirror test using predictor_fn(record) -> MirrorPrediction."""
        sample = historical_records[-MIRROR_TEST_SAMPLE:]
        predictions = [predictor_fn(r) for r in sample]

        pass_acc = statistics.mean(p.pass_correct for p in predictions) if predictions else 0.0
        rules_prec = statistics.mean(p.rules_precision for p in predictions) if predictions else 0.0
        fitness_mae = statistics.mean(p.fitness_error for p in predictions) if predictions else 1.0
        overall = (pass_acc * 0.5 + rules_prec * 0.3 + max(0.0, 1.0 - fitness_mae) * 0.2)

        result = MirrorTestResult(
            epoch_id=epoch_id,
            sample_size=len(predictions),
            pass_accuracy=round(pass_acc, 4),
            rules_precision=round(rules_prec, 4),
            fitness_mae=round(fitness_mae, 4),
            overall_score=round(overall, 4),
            requires_calibration=overall < self.threshold,
            predictions=predictions,
        )
        self._persist(result)
        return result

    def last_score(self) -> float | None:
        if not self.state_path.exists():
            return None
        try:
            last = self.state_path.read_text().splitlines()[-1]
            return json.loads(last).get("overall_score")
        except Exception:
            return None

    def _persist(self, result: MirrorTestResult) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {k: v for k, v in asdict(result).items() if k != "predictions"}
        with self.state_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


__all__ = ["MirrorTestEngine", "MirrorTestResult", "MirrorPrediction",
           "MIRROR_TEST_INTERVAL", "CALIBRATION_THRESHOLD"]
