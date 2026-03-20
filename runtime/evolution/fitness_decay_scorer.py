# SPDX-License-Identifier: Apache-2.0
"""Phase 84 — FitnessDecayScorer and FitnessRecord.

Detects fitness decay: a mutation that scored well when it was first
evaluated may become harmful as the surrounding codebase evolves.

FitnessRecord extends the historical score with a CodebaseStateVector
snapshot taken at scoring time. FitnessDecayScorer re-evaluates records
against the current codebase state and emits FitnessDecayEvent entries
to the ledger when decay crosses the alert threshold.

Constitutional Invariants
─────────────────────────
  TFHL-0       Fitness decay re-evaluation is read-only on historical records.
               No ledger entry is ever modified. FitnessDecayEvent is a NEW
               append-only entry — it does not alter the original score entry.
  TFHL-DET-0   Identical codebase state + decay parameters → identical
               adjusted scores and drift magnitudes.
  TFHL-DECAY-0 Decay model is deterministic exponential:
                 adjusted = recorded × exp(−k × drift)
               where k = DECAY_RATE_CONSTANT (default 2.0).
               Adjusted score is clamped to [0.0, 1.0].
  TFHL-ALERT-0 FitnessDecayEvent is emitted when adjusted_score drops below
               DECAY_ALERT_THRESHOLD (default 0.6). Events are advisory.
  TFHL-ADVISORY-0 FitnessDecayEvent is advisory. GovernanceGate is never
               invoked by this module.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from runtime.evolution.codebase_state_vector import CodebaseStateVector

log = logging.getLogger(__name__)

TFHL_VERSION: str = "84.0"

# Decay model constants
DECAY_RATE_CONSTANT: float = 2.0          # k in exp(-k × drift)
DECAY_ALERT_THRESHOLD: float = 0.60       # TFHL-ALERT-0
HALF_LIFE_EPOCHS_DEFAULT: int = 20        # advisory half-life in epochs


# ---------------------------------------------------------------------------
# FitnessRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FitnessRecord:
    """Historical fitness record extended with codebase state snapshot.

    Attributes
    ----------
    record_id:               Deterministic SHA-256 of (candidate_id + epoch_id).
    candidate_id:            Source mutation candidate.
    epoch_id:                Epoch at which this score was recorded.
    recorded_score:          Raw FitnessOrchestrator score at time of recording.
    codebase_state_vector:   CodebaseStateVector snapshot at scoring time.
    half_life_epochs:        Advisory half-life (informational, not enforced).
    recorded_at_utc:         ISO-8601 UTC timestamp of the original scoring.
    schema_version:          TFHL schema version.
    """

    record_id: str
    candidate_id: str
    epoch_id: str
    recorded_score: float
    codebase_state_vector: CodebaseStateVector
    half_life_epochs: int = HALF_LIFE_EPOCHS_DEFAULT
    recorded_at_utc: str = ""
    schema_version: str = TFHL_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "candidate_id": self.candidate_id,
            "epoch_id": self.epoch_id,
            "recorded_score": round(self.recorded_score, 6),
            "codebase_state_vector": self.codebase_state_vector.to_dict(),
            "half_life_epochs": self.half_life_epochs,
            "recorded_at_utc": self.recorded_at_utc,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FitnessRecord":
        return cls(
            record_id=d["record_id"],
            candidate_id=d["candidate_id"],
            epoch_id=d["epoch_id"],
            recorded_score=d["recorded_score"],
            codebase_state_vector=CodebaseStateVector.from_dict(d["codebase_state_vector"]),
            half_life_epochs=d.get("half_life_epochs", HALF_LIFE_EPOCHS_DEFAULT),
            recorded_at_utc=d.get("recorded_at_utc", ""),
            schema_version=d.get("schema_version", TFHL_VERSION),
        )

    @classmethod
    def create(
        cls,
        candidate_id: str,
        epoch_id: str,
        recorded_score: float,
        codebase_state_vector: CodebaseStateVector,
        half_life_epochs: int = HALF_LIFE_EPOCHS_DEFAULT,
    ) -> "FitnessRecord":
        """Factory with deterministic record_id."""
        payload = f"{candidate_id}|{epoch_id}"
        record_id = "tfhl-" + hashlib.sha256(payload.encode()).hexdigest()[:16]
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return cls(
            record_id=record_id,
            candidate_id=candidate_id,
            epoch_id=epoch_id,
            recorded_score=max(0.0, min(1.0, recorded_score)),
            codebase_state_vector=codebase_state_vector,
            half_life_epochs=half_life_epochs,
            recorded_at_utc=ts,
        )


# ---------------------------------------------------------------------------
# FitnessDecayResult — output of one decay evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FitnessDecayResult:
    """Result of evaluating fitness decay for one FitnessRecord.

    Attributes
    ----------
    record_id:        Source FitnessRecord.record_id.
    candidate_id:     Source candidate.
    drift_magnitude:  CodebaseStateVector.drift_from() value [0.0, 1.0].
    recorded_score:   Original fitness score.
    adjusted_score:   Decay-adjusted score [0.0, 1.0]. TFHL-DECAY-0.
    decay_factor:     exp(-k × drift) applied.
    alert_triggered:  True when adjusted_score < DECAY_ALERT_THRESHOLD.
    decay_digest:     SHA-256 of canonical decay inputs (TFHL-DET-0).
    """

    record_id: str
    candidate_id: str
    drift_magnitude: float
    recorded_score: float
    adjusted_score: float
    decay_factor: float
    alert_triggered: bool
    decay_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "candidate_id": self.candidate_id,
            "drift_magnitude": round(self.drift_magnitude, 6),
            "recorded_score": round(self.recorded_score, 6),
            "adjusted_score": round(self.adjusted_score, 6),
            "decay_factor": round(self.decay_factor, 6),
            "alert_triggered": self.alert_triggered,
            "decay_digest": self.decay_digest,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FitnessDecayResult":
        return cls(**d)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decay_factor(drift: float, k: float = DECAY_RATE_CONSTANT) -> float:
    """TFHL-DECAY-0: exp(−k × drift). Deterministic pure function."""
    return math.exp(-k * max(0.0, drift))


def _adjusted_score(recorded: float, drift: float, k: float = DECAY_RATE_CONSTANT) -> float:
    """TFHL-DECAY-0: recorded × exp(−k × drift), clamped to [0.0, 1.0]."""
    return max(0.0, min(1.0, recorded * _decay_factor(drift, k)))


def _decay_digest(
    record_id: str, drift: float, k: float, threshold: float
) -> str:
    payload = json.dumps(
        {"record_id": record_id, "drift": round(drift, 6), "k": k, "threshold": threshold},
        sort_keys=True, separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# FitnessDecayScorer
# ---------------------------------------------------------------------------


class FitnessDecayScorer:
    """Phase 84 fitness decay scorer.

    Evaluates stored FitnessRecord objects against a current
    CodebaseStateVector and emits FitnessDecayEvent ledger entries
    when scores drop below DECAY_ALERT_THRESHOLD.

    TFHL-0: strictly read-only on historical records.
    TFHL-DET-0: deterministic for identical inputs.
    TFHL-ADVISORY-0: never invokes GovernanceGate.
    """

    def __init__(
        self,
        *,
        ledger: Optional[Any] = None,
        decay_rate: float = DECAY_RATE_CONSTANT,
        alert_threshold: float = DECAY_ALERT_THRESHOLD,
    ) -> None:
        self._ledger = ledger
        self._k = decay_rate
        self._threshold = alert_threshold

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def evaluate(
        self,
        record: FitnessRecord,
        current_vector: CodebaseStateVector,
    ) -> FitnessDecayResult:
        """Evaluate decay for one FitnessRecord against current codebase state.

        TFHL-0: record is not modified.
        TFHL-DET-0: deterministic.
        TFHL-DECAY-0: adjusted = recorded × exp(-k × drift).
        TFHL-ALERT-0: ledger event emitted if adjusted < threshold.
        """
        drift = record.codebase_state_vector.drift_from(current_vector)
        factor = _decay_factor(drift, self._k)
        adjusted = _adjusted_score(record.recorded_score, drift, self._k)
        alert = adjusted < self._threshold
        digest = _decay_digest(record.record_id, drift, self._k, self._threshold)

        result = FitnessDecayResult(
            record_id=record.record_id,
            candidate_id=record.candidate_id,
            drift_magnitude=drift,
            recorded_score=record.recorded_score,
            adjusted_score=adjusted,
            decay_factor=factor,
            alert_triggered=alert,
            decay_digest=digest,
        )

        log.debug(
            "TFHL: candidate=%s drift=%.4f recorded=%.4f adjusted=%.4f alert=%s",
            record.candidate_id, drift, record.recorded_score, adjusted, alert,
        )

        if alert and self._ledger is not None:
            self._emit_decay_event(record, result)

        return result

    def evaluate_batch(
        self,
        records: Sequence[FitnessRecord],
        current_vector: CodebaseStateVector,
    ) -> List[FitnessDecayResult]:
        """Evaluate a batch of FitnessRecords. Returns results sorted by adjusted_score asc.

        TFHL-DET-0: sorted output — most decayed first.
        """
        results = [self.evaluate(r, current_vector) for r in records]
        return sorted(results, key=lambda r: (r.adjusted_score, r.record_id))

    def scan_summary(
        self,
        records: Sequence[FitnessRecord],
        current_vector: CodebaseStateVector,
    ) -> Dict[str, Any]:
        """Return a summary dict of decay scan results for governance artifacts."""
        results = self.evaluate_batch(records, current_vector)
        alerted = [r for r in results if r.alert_triggered]
        return {
            "schema_version": TFHL_VERSION,
            "total_records": len(records),
            "alerted_count": len(alerted),
            "alert_threshold": self._threshold,
            "decay_rate_constant": self._k,
            "worst_decay": results[0].to_dict() if results else None,
            "alerted_candidate_ids": [r.candidate_id for r in alerted],
            "current_vector_id": current_vector.vector_id,
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _emit_decay_event(
        self, record: FitnessRecord, result: FitnessDecayResult
    ) -> None:
        """TFHL-ALERT-0: append FitnessDecayEvent to ledger (non-blocking).

        TFHL-0: new append-only event; original record untouched.
        """
        try:
            self._ledger.append_event(
                "FitnessDecayEvent",
                {
                    "record_id": record.record_id,
                    "candidate_id": record.candidate_id,
                    "epoch_id": record.epoch_id,
                    "drift_magnitude": round(result.drift_magnitude, 6),
                    "recorded_score": round(result.recorded_score, 6),
                    "adjusted_score": round(result.adjusted_score, 6),
                    "decay_factor": round(result.decay_factor, 6),
                    "alert_threshold": self._threshold,
                    "decay_digest": result.decay_digest,
                    "schema_version": TFHL_VERSION,
                },
            )
            log.warning(
                "TFHL-ALERT-0: FitnessDecayEvent emitted for candidate=%s "
                "adjusted=%.4f threshold=%.4f",
                record.candidate_id, result.adjusted_score, self._threshold,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("TFHL: ledger write failed (non-blocking): %s", exc)
