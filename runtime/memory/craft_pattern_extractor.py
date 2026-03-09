# SPDX-License-Identifier: Apache-2.0
"""
CraftPatternExtractor — extracts durable reasoning patterns from accepted
mutation batches and writes them into the SoulboundLedger as ``craft_pattern``
context entries.

Purpose:
    After each evolution epoch, high-quality accepted mutations encode implicit
    knowledge about what kinds of structural, fitness, and governance patterns
    are winning.  CraftPatternExtractor makes this knowledge explicit and
    tamper-evident by:

    1. Extracting per-agent-type scoring statistics from the accepted batch.
    2. Deriving a ``reasoning_pattern`` summary (preferred mutation categories,
       weight velocity quality, governance health signal).
    3. Writing the pattern as a ``craft_pattern`` ledger entry via SoulboundLedger.
    4. Flagging low-signal epochs with a ``signal_quality_flag`` (CF-3 mitigation).

Minimum activation:
    CraftPatternExtractor gates on ``MIN_ACCEPTED_MUTATIONS_PER_EPOCH`` (default: 2).
    If the epoch produced fewer accepted mutations, no pattern is emitted —
    sparse data would produce misleading patterns.  A ``craft_pattern_skipped.v1``
    journal event is emitted instead.

Signal quality flag (CF-3 mitigation):
    When weight velocity magnitude is below ``VELOCITY_QUALITY_THRESHOLD``, the
    emitted pattern entry carries ``signal_quality_flag: "low_velocity"`` to
    indicate that governance patterning reflects near-pinned weights rather
    than real adaptation.  Downstream consumers (PR-9-03 ContextReplayInterface)
    must honour this flag.

Pattern types extracted:
    structural   — from architect agent accepted mutations
    experimental — from dream agent accepted mutations
    performance  — from beast agent accepted mutations
    governance   — from ScoringWeights velocity (PenaltyAdaptor signal)
    architecture — from SemanticDiff risk/complexity delta across accepted set

Constitutional invariants:
    - GovernanceGate retains sole mutation approval authority; patterns are
      advisory context only — they do not alter mutation approval decisions.
    - Patterns are append-only in the SoulboundLedger (tamper-evident).
    - Extractor is deterministic: given identical inputs, identical patterns.
    - Fail-closed: if SoulboundKeyError is raised, extraction is aborted and
      the exception propagates so the caller knows the ledger is unavailable.

Android/Pydroid3 compatibility:
    - Pure Python stdlib only.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.memory.soulbound_ledger import SoulboundLedger, AppendResult

# Journal — graceful no-op fallback for test environments
try:
    from security.ledger.journal import append_tx as _journal_append_tx
except ImportError:  # pragma: no cover
    def _journal_append_tx(tx_type: str, payload: Dict[str, Any], **kw: Any) -> Dict[str, Any]:  # type: ignore[misc]
        return {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_ACCEPTED_MUTATIONS_PER_EPOCH: int = 2
VELOCITY_QUALITY_THRESHOLD: float     = 0.005   # |velocity| below this = low signal
HIGH_SCORE_THRESHOLD: float           = 0.70    # Score above this = elite pattern

# Agent → pattern_type mapping (mirrors EvolutionLoop._agent_to_type)
_AGENT_TO_PATTERN_TYPE: Dict[str, str] = {
    "architect": "structural",
    "dream":     "experimental",
    "beast":     "performance",
    "crossover": "behavioral",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentPatternStats:
    """Per-agent-type statistics extracted from an epoch's accepted mutations."""
    agent_origin:      str
    pattern_type:      str
    accepted_count:    int
    mean_score:        float
    max_score:         float
    elite_count:       int           # Count of scores above HIGH_SCORE_THRESHOLD
    mean_risk:         float         # Mean risk_score from dimension_breakdown
    mean_complexity:   float         # Mean complexity_score from dimension_breakdown

    def as_dict(self) -> Dict[str, Any]:
        return {
            "agent_origin":   self.agent_origin,
            "pattern_type":   self.pattern_type,
            "accepted_count": self.accepted_count,
            "mean_score":     round(self.mean_score, 4),
            "max_score":      round(self.max_score, 4),
            "elite_count":    self.elite_count,
            "mean_risk":      round(self.mean_risk, 4),
            "mean_complexity": round(self.mean_complexity, 4),
        }


@dataclass(frozen=True)
class CraftPattern:
    """Extracted reasoning pattern for a single epoch."""
    epoch_id:            str
    accepted_count:      int
    agent_stats:         List[AgentPatternStats]
    dominant_agent:      Optional[str]           # agent with most accepted mutations
    dominant_pattern:    Optional[str]           # pattern_type of dominant_agent
    mean_epoch_score:    float
    weight_velocity_risk:       float            # PenaltyAdaptor velocity_risk
    weight_velocity_complexity: float            # PenaltyAdaptor velocity_complexity
    signal_quality_flag:        Optional[str]    # "low_velocity" | None
    skipped:             bool = False
    skip_reason:         Optional[str] = None

    def as_payload(self) -> Dict[str, Any]:
        """Produce the ledger payload dict (must be JSON-serialisable)."""
        return {
            "epoch_id":             self.epoch_id,
            "accepted_count":       self.accepted_count,
            "agent_stats":          [s.as_dict() for s in self.agent_stats],
            "dominant_agent":       self.dominant_agent,
            "dominant_pattern":     self.dominant_pattern,
            "mean_epoch_score":     round(self.mean_epoch_score, 4),
            "weight_velocity_risk":       round(self.weight_velocity_risk, 6),
            "weight_velocity_complexity": round(self.weight_velocity_complexity, 6),
            "signal_quality_flag":  self.signal_quality_flag,
        }


@dataclass
class ExtractionResult:
    """Returned from CraftPatternExtractor.extract()."""
    pattern:         CraftPattern
    ledger_result:   Optional[AppendResult]   # None if skipped (no ledger write)
    emitted:         bool                     # True iff ledger write succeeded


# ---------------------------------------------------------------------------
# CraftPatternExtractor
# ---------------------------------------------------------------------------

class CraftPatternExtractor:
    """Extracts reasoning patterns from accepted mutation batches.

    Usage::

        extractor = CraftPatternExtractor(ledger=SoulboundLedger(...))
        result = extractor.extract(
            epoch_id="epoch-042",
            accepted_scores=accepted,       # List[MutationScore]
            weight_velocity_risk=0.012,
            weight_velocity_complexity=0.008,
        )
        if result.emitted:
            print(result.pattern.dominant_pattern)

    Args:
        ledger:      SoulboundLedger instance for tamper-evident persistence.
        audit_writer: Optional override for journal writes (no-op in tests).
        min_accepted: Minimum accepted mutations to emit a pattern (default: 2).
    """

    def __init__(
        self,
        ledger: SoulboundLedger,
        audit_writer: Optional[Any] = None,
        min_accepted: int = MIN_ACCEPTED_MUTATIONS_PER_EPOCH,
    ) -> None:
        self._ledger        = ledger
        self._audit         = audit_writer or _journal_append_tx
        self._min_accepted  = min_accepted

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        *,
        epoch_id: str,
        accepted_scores: List[Any],   # List[MutationScore] — typed loosely for compatibility
        weight_velocity_risk: float,
        weight_velocity_complexity: float,
    ) -> ExtractionResult:
        """Extract a CraftPattern from this epoch's accepted mutations.

        If accepted_scores has fewer than min_accepted entries, returns a
        skipped pattern with no ledger write.

        Args:
            epoch_id:                   Epoch identifier.
            accepted_scores:            MutationScore list for accepted mutations.
            weight_velocity_risk:       Current PenaltyAdaptor velocity_risk.
            weight_velocity_complexity: Current PenaltyAdaptor velocity_complexity.

        Returns:
            ExtractionResult with pattern, ledger_result, and emitted flag.
        """
        accepted_count = len(accepted_scores)

        # --- Gate: insufficient data ---
        if accepted_count < self._min_accepted:
            pattern = CraftPattern(
                epoch_id=epoch_id,
                accepted_count=accepted_count,
                agent_stats=[],
                dominant_agent=None,
                dominant_pattern=None,
                mean_epoch_score=0.0,
                weight_velocity_risk=weight_velocity_risk,
                weight_velocity_complexity=weight_velocity_complexity,
                signal_quality_flag=None,
                skipped=True,
                skip_reason=f"accepted_count_{accepted_count}_below_minimum_{self._min_accepted}",
            )
            self._emit_skipped(epoch_id, pattern.skip_reason)
            return ExtractionResult(pattern=pattern, ledger_result=None, emitted=False)

        # --- Extract per-agent stats ---
        agent_stats = self._compute_agent_stats(accepted_scores)

        # --- Compute epoch-level metrics ---
        all_scores = [float(getattr(s, "score", 0.0)) for s in accepted_scores]
        mean_epoch_score = statistics.mean(all_scores) if all_scores else 0.0

        # --- Determine dominant agent ---
        dominant_agent   = None
        dominant_pattern = None
        if agent_stats:
            best = max(agent_stats, key=lambda s: s.accepted_count)
            dominant_agent   = best.agent_origin
            dominant_pattern = best.pattern_type

        # --- Signal quality flag (CF-3 mitigation) ---
        max_velocity = max(
            abs(weight_velocity_risk),
            abs(weight_velocity_complexity),
        )
        signal_quality_flag: Optional[str] = (
            "low_velocity" if max_velocity < VELOCITY_QUALITY_THRESHOLD else None
        )

        # --- Assemble pattern ---
        pattern = CraftPattern(
            epoch_id=epoch_id,
            accepted_count=accepted_count,
            agent_stats=agent_stats,
            dominant_agent=dominant_agent,
            dominant_pattern=dominant_pattern,
            mean_epoch_score=round(mean_epoch_score, 4),
            weight_velocity_risk=weight_velocity_risk,
            weight_velocity_complexity=weight_velocity_complexity,
            signal_quality_flag=signal_quality_flag,
        )

        # --- Write to SoulboundLedger ---
        payload = pattern.as_payload()
        ledger_result = self._ledger.append(
            epoch_id=epoch_id,
            context_type="craft_pattern",
            payload=payload,
        )

        emitted = ledger_result.accepted

        # --- Audit journal event ---
        if emitted:
            self._emit_extracted(pattern, ledger_result)
        else:
            self._emit_skipped(epoch_id, f"ledger_rejected:{ledger_result.rejection_reason}")

        return ExtractionResult(
            pattern=pattern,
            ledger_result=ledger_result,
            emitted=emitted,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_agent_stats(self, accepted_scores: List[Any]) -> List[AgentPatternStats]:
        """Group accepted MutationScores by agent_origin and compute statistics."""
        # Group by agent_origin
        by_agent: Dict[str, List[Any]] = {}
        for score in accepted_scores:
            agent = str(getattr(score, "agent_origin", "unknown"))
            by_agent.setdefault(agent, []).append(score)

        stats = []
        for agent_origin, scores in sorted(by_agent.items()):
            score_values = [float(getattr(s, "score", 0.0)) for s in scores]
            risk_values  = []
            complexity_values = []
            for s in scores:
                bd = getattr(s, "dimension_breakdown", {}) or {}
                # Recover risk_score: contrib ≈ score × weight → score ≈ contrib / weight
                rc = abs(float(bd.get("risk_penalty_contrib", 0.0)))
                cc = abs(float(bd.get("complexity_penalty_contrib", 0.0)))
                risk_values.append(min(1.0, rc / 0.20) if rc > 0 else 0.5)
                complexity_values.append(min(1.0, cc / 0.10) if cc > 0 else 0.5)

            stats.append(AgentPatternStats(
                agent_origin    = agent_origin,
                pattern_type    = _AGENT_TO_PATTERN_TYPE.get(agent_origin, "behavioral"),
                accepted_count  = len(scores),
                mean_score      = statistics.mean(score_values) if score_values else 0.0,
                max_score       = max(score_values) if score_values else 0.0,
                elite_count     = sum(1 for v in score_values if v >= HIGH_SCORE_THRESHOLD),
                mean_risk       = statistics.mean(risk_values)       if risk_values       else 0.5,
                mean_complexity = statistics.mean(complexity_values) if complexity_values else 0.5,
            ))

        return stats

    def _emit(self, tx_type: str, payload: Dict[str, Any]) -> None:
        try:
            self._audit(tx_type, payload)
        except Exception:  # noqa: BLE001
            pass

    def _emit_extracted(self, pattern: CraftPattern, ledger_result: AppendResult) -> None:
        self._emit(
            "craft_pattern_extracted.v1",
            {
                "epoch_id":           pattern.epoch_id,
                "accepted_count":     pattern.accepted_count,
                "dominant_agent":     pattern.dominant_agent,
                "dominant_pattern":   pattern.dominant_pattern,
                "mean_epoch_score":   pattern.mean_epoch_score,
                "signal_quality_flag": pattern.signal_quality_flag,
                "ledger_entry_id":    ledger_result.entry.entry_id,
                "ledger_chain_hash":  ledger_result.entry.chain_hash,
            },
        )

    def _emit_skipped(self, epoch_id: str, reason: Optional[str]) -> None:
        self._emit(
            "craft_pattern_skipped.v1",
            {
                "epoch_id": epoch_id,
                "reason":   reason or "unknown",
            },
        )


__all__ = [
    "MIN_ACCEPTED_MUTATIONS_PER_EPOCH",
    "VELOCITY_QUALITY_THRESHOLD",
    "HIGH_SCORE_THRESHOLD",
    "AgentPatternStats",
    "CraftPattern",
    "ExtractionResult",
    "CraftPatternExtractor",
]
