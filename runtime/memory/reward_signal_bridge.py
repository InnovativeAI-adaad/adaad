# SPDX-License-Identifier: Apache-2.0
"""
RewardSignalBridge — bridges EvolutionLoop mutation outcomes into the
RewardLearning pipeline and persists normalized reward observations in
the SoulboundLedger as tamper-evident ``fitness_signal`` context entries.

Purpose:
    The ``reward_learning.py`` module (Phases 0–7 scaffolding) defines
    RewardOutcomeIngestor, OfflinePolicyEvaluator, GuardedPromotionPolicy,
    and LearningProfileRegistry — but has never been wired into the live
    mutation pipeline.  RewardSignalBridge closes this gap.

    After each epoch, RewardSignalBridge:
    1. Converts every accepted/rejected MutationScore into a LearningObservation
       via RewardOutcomeIngestor.
    2. Aggregates observations into a PromotionEvaluation via OfflinePolicyEvaluator.
    3. Persists the aggregate as a ``fitness_signal`` ledger entry (Phase 9 ledger).
    4. Emits a ``reward_signal_ingested.v1`` journal event.
    5. Stores the per-epoch observation batch in a ring buffer for PR-10-02
       PolicyPromotionController consumption.

Wiring location:
    EvolutionLoop Phase 5d — runs after Phase 5c (CraftPatternExtractor),
    before Phase 6 (Checkpoint).

Constitutional invariants:
    - GovernanceGate retains sole mutation approval authority; reward signals
      are advisory learning input only — they never gate or approve mutations.
    - Fail-closed: if SoulboundKeyError is raised, bridge writes are blocked
      but the exception is isolated (epoch continues).
    - Deterministic: identical MutationScore inputs → identical observations.
    - Append-only: observations written to ledger are immutable.

Android/Pydroid3 compatibility:
    - Pure Python stdlib only.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from runtime.autonomy.reward_learning import (
    LearningObservation,
    OfflinePolicyEvaluator,
    PromotionEvaluation,
    RewardOutcomeIngestor,
    RewardSchema,
)
from runtime.memory.soulbound_ledger import SoulboundLedger

# Journal — graceful no-op fallback
try:
    from security.ledger.journal import append_tx as _journal_append_tx
except ImportError:  # pragma: no cover
    def _journal_append_tx(tx_type: str, payload: Dict[str, Any], **kw: Any) -> Dict[str, Any]:  # type: ignore[misc]
        return {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OBSERVATION_RING_BUFFER_SIZE: int = 20    # Max epochs retained for downstream use
MIN_SCORES_FOR_SIGNAL: int       = 1      # Minimum MutationScores to emit a signal


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EpochRewardSignal:
    """Aggregated reward signal for a single epoch."""
    epoch_id:               str
    total_candidates:       int
    accepted_count:         int
    avg_reward:             float
    acceptance_rate:        float
    replay_stability_rate:  float
    observations_count:     int
    ledger_entry_id:        str     # Entry ID in SoulboundLedger; empty if skipped
    ledger_accepted:        bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "epoch_id":              self.epoch_id,
            "total_candidates":      self.total_candidates,
            "accepted_count":        self.accepted_count,
            "avg_reward":            round(self.avg_reward, 4),
            "acceptance_rate":       round(self.acceptance_rate, 4),
            "replay_stability_rate": round(self.replay_stability_rate, 4),
            "observations_count":    self.observations_count,
            "ledger_entry_id":       self.ledger_entry_id,
            "ledger_accepted":       self.ledger_accepted,
        }


@dataclass
class BridgeResult:
    """Result from RewardSignalBridge.ingest()."""
    signal:  EpochRewardSignal
    emitted: bool
    skip_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# RewardSignalBridge
# ---------------------------------------------------------------------------

class RewardSignalBridge:
    """Bridges EvolutionLoop mutation scores → RewardLearning pipeline.

    Usage::

        bridge = RewardSignalBridge(ledger=SoulboundLedger(...))
        result = bridge.ingest(
            epoch_id="epoch-042",
            all_scores=all_scores,      # List[MutationScore]
        )
        # result.signal.avg_reward, result.signal.acceptance_rate available

        # PolicyPromotionController reads from:
        bridge.recent_evaluations  # Deque[PromotionEvaluation]

    Args:
        ledger:          SoulboundLedger for fitness_signal persistence.
        schema:          RewardSchema weights (defaults to standard 0.45/0.35/0.20).
        audit_writer:    Optional journal override (no-op in tests).
        key_override:    HMAC key override for tests.
        min_scores:      Minimum score count to emit a signal.
    """

    def __init__(
        self,
        ledger: SoulboundLedger,
        schema: Optional[RewardSchema] = None,
        audit_writer: Optional[Any] = None,
        min_scores: int = MIN_SCORES_FOR_SIGNAL,
    ) -> None:
        self._ledger       = ledger
        self._ingestor     = RewardOutcomeIngestor(schema=schema or RewardSchema())
        self._evaluator    = OfflinePolicyEvaluator(ingestor=self._ingestor)
        self._audit        = audit_writer or _journal_append_tx
        self._min_scores   = min_scores
        # Ring buffer: PolicyPromotionController reads from this
        self.recent_evaluations: Deque[PromotionEvaluation] = collections.deque(
            maxlen=OBSERVATION_RING_BUFFER_SIZE
        )
        self.recent_signals: Deque[EpochRewardSignal] = collections.deque(
            maxlen=OBSERVATION_RING_BUFFER_SIZE
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(
        self,
        *,
        epoch_id: str,
        all_scores: List[Any],   # List[MutationScore]
    ) -> BridgeResult:
        """Ingest MutationScores for one epoch and persist reward signal.

        Converts each MutationScore to a LearningObservation, aggregates
        into a PromotionEvaluation, and writes a ``fitness_signal`` ledger
        entry in the SoulboundLedger.

        Args:
            epoch_id:    Epoch identifier.
            all_scores:  All MutationScore objects from this epoch (accepted + rejected).

        Returns:
            BridgeResult with EpochRewardSignal and emitted flag.
        """
        if len(all_scores) < self._min_scores:
            signal = self._empty_signal(epoch_id, len(all_scores))
            self.recent_signals.append(signal)
            return BridgeResult(signal=signal, emitted=False,
                                skip_reason=f"score_count_{len(all_scores)}_below_minimum_{self._min_scores}")

        # --- Convert to events for RewardOutcomeIngestor ---
        events = [self._score_to_event(s) for s in all_scores]

        # --- Aggregate via OfflinePolicyEvaluator ---
        evaluation = self._evaluator.replay_historical_events(events)
        self.recent_evaluations.append(evaluation)

        # --- Count accepted ---
        accepted_count = sum(1 for s in all_scores if getattr(s, "accepted", False))
        total_count    = len(all_scores)

        # --- Build ledger payload ---
        payload: Dict[str, Any] = {
            "epoch_id":              epoch_id,
            "total_candidates":      total_count,
            "accepted_count":        accepted_count,
            "avg_reward":            round(evaluation.avg_reward, 4),
            "acceptance_rate":       round(evaluation.acceptance_rate, 6),
            "replay_stability_rate": round(evaluation.replay_stability_rate, 6),
            "observations_count":    evaluation.total_count,
            "reward_schema": {
                "mutation_success_weight": self._ingestor.schema.mutation_success_weight,
                "governance_pass_weight":  self._ingestor.schema.governance_pass_weight,
                "replay_stability_weight": self._ingestor.schema.replay_stability_weight,
            },
        }

        # --- Write to SoulboundLedger ---
        entry_id       = ""
        ledger_accepted = False
        try:
            ledger_result  = self._ledger.append(
                epoch_id=epoch_id,
                context_type="fitness_signal",
                payload=payload,
            )
            entry_id       = ledger_result.entry.entry_id if ledger_result.accepted else ""
            ledger_accepted = ledger_result.accepted
        except Exception:  # noqa: BLE001 — never block epoch
            pass

        signal = EpochRewardSignal(
            epoch_id               = epoch_id,
            total_candidates       = total_count,
            accepted_count         = accepted_count,
            avg_reward             = round(evaluation.avg_reward, 4),
            acceptance_rate        = round(evaluation.acceptance_rate, 4),
            replay_stability_rate  = round(evaluation.replay_stability_rate, 4),
            observations_count     = evaluation.total_count,
            ledger_entry_id        = entry_id,
            ledger_accepted        = ledger_accepted,
        )
        self.recent_signals.append(signal)
        self._emit_ingested(signal)

        return BridgeResult(signal=signal, emitted=True)

    @property
    def last_evaluation(self) -> Optional[PromotionEvaluation]:
        """Return the most recent PromotionEvaluation, or None."""
        return self.recent_evaluations[-1] if self.recent_evaluations else None

    @property
    def last_signal(self) -> Optional[EpochRewardSignal]:
        """Return the most recent EpochRewardSignal, or None."""
        return self.recent_signals[-1] if self.recent_signals else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_to_event(score: Any) -> Dict[str, Any]:
        """Convert a MutationScore to a RewardOutcomeIngestor-compatible event dict."""
        return {
            "mutation_id":       str(getattr(score, "mutation_id", "") or ""),
            "accepted":          bool(getattr(score, "accepted", False)),
            "governance_passed": bool(getattr(score, "accepted", False)),  # accepted implies gate pass
            "replay_stable":     bool(getattr(score, "accepted", False)),  # heuristic: accepted = stable
            "event_id":          str(getattr(score, "mutation_id", "") or ""),
        }

    @staticmethod
    def _empty_signal(epoch_id: str, count: int) -> EpochRewardSignal:
        return EpochRewardSignal(
            epoch_id=epoch_id, total_candidates=count, accepted_count=0,
            avg_reward=0.0, acceptance_rate=0.0, replay_stability_rate=0.0,
            observations_count=0, ledger_entry_id="", ledger_accepted=False,
        )

    def _emit(self, tx_type: str, payload: Dict[str, Any]) -> None:
        try:
            self._audit(tx_type, payload)
        except Exception:  # noqa: BLE001
            pass

    def _emit_ingested(self, signal: EpochRewardSignal) -> None:
        self._emit(
            "reward_signal_ingested.v1",
            {
                "epoch_id":          signal.epoch_id,
                "avg_reward":        signal.avg_reward,
                "acceptance_rate":   signal.acceptance_rate,
                "accepted_count":    signal.accepted_count,
                "total_candidates":  signal.total_candidates,
                "ledger_entry_id":   signal.ledger_entry_id,
            },
        )


__all__ = [
    "OBSERVATION_RING_BUFFER_SIZE",
    "MIN_SCORES_FOR_SIGNAL",
    "EpochRewardSignal",
    "BridgeResult",
    "RewardSignalBridge",
]
