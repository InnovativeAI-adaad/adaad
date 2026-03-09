# SPDX-License-Identifier: Apache-2.0
"""CritiqueSignalBuffer — epoch-scoped per-strategy critique outcome accumulator.

Phase 18: Accumulates approved/rejected outcomes and floor-breach events per
strategy_id within an epoch. `breach_rate()` is consumed by StrategyModule to
apply a payoff penalty to strategies that consistently produce breaching proposals.

Design principles:
- Append-only within an epoch. No retroactive modification.
- Deterministic: identical record sequence → identical breach_rate().
- Unknown strategy_id → breach_rate() returns 0.0 (no penalty on first appearance).
- reset_epoch() clears all state explicitly — not automatic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


_BREACH_PENALTY_WEIGHT: float = 0.20
"""Maximum payoff reduction per strategy due to critique breach rate.

breach_rate ∈ [0.0, 1.0]; penalty = breach_rate × 0.20.
Cannot exceed 0.20 regardless of breach history.
"""


@dataclass
class CritiqueSignalBuffer:
    """Epoch-scoped accumulator of critique outcomes per strategy_id.

    Thread-unsafe — designed for single-epoch, single-threaded use within
    IntelligenceRouter. For multi-threaded use, wrap in an external lock.
    """

    _total: dict[str, int] = field(default_factory=dict)
    _breaches: dict[str, int] = field(default_factory=dict)

    def record(
        self,
        *,
        strategy_id: str,
        approved: bool,
        risk_flags: Sequence[str] | None = None,
    ) -> None:
        """Record a critique outcome for strategy_id.

        Args:
            strategy_id: The strategy that produced the reviewed proposal.
            approved: Whether CritiqueModule approved the proposal.
            risk_flags: List of floor-breach flag strings from CritiqueResult.
        """
        self._total[strategy_id] = self._total.get(strategy_id, 0) + 1
        if not approved or (risk_flags and len(risk_flags) > 0):
            self._breaches[strategy_id] = self._breaches.get(strategy_id, 0) + 1

    def breach_rate(self, strategy_id: str) -> float:
        """Return the breach rate for strategy_id in [0.0, 1.0].

        Returns 0.0 for unseen strategy_ids (no penalty on first appearance).
        Breach rate = breaches / total, clamped [0.0, 1.0].
        """
        total = self._total.get(strategy_id, 0)
        if total == 0:
            return 0.0
        breaches = self._breaches.get(strategy_id, 0)
        return min(1.0, max(0.0, breaches / total))

    def breach_penalty(self, strategy_id: str) -> float:
        """Return the payoff penalty for strategy_id.

        penalty = breach_rate(strategy_id) × _BREACH_PENALTY_WEIGHT
        Maximum penalty is _BREACH_PENALTY_WEIGHT (0.20).
        """
        return round(self.breach_rate(strategy_id) * _BREACH_PENALTY_WEIGHT, 6)

    def reset_epoch(self) -> None:
        """Clear all accumulated signal — call at epoch boundary."""
        self._total.clear()
        self._breaches.clear()

    def total_count(self, strategy_id: str) -> int:
        """Total critique outcomes recorded for strategy_id."""
        return self._total.get(strategy_id, 0)

    def breach_count(self, strategy_id: str) -> int:
        """Breach count for strategy_id."""
        return self._breaches.get(strategy_id, 0)

    def snapshot(self) -> dict[str, dict[str, float]]:
        """Return deterministic snapshot of all tracked strategies.

        Format: {strategy_id: {total, breaches, breach_rate, penalty}}
        """
        all_ids = sorted(set(self._total) | set(self._breaches))
        return {
            sid: {
                "total": float(self._total.get(sid, 0)),
                "breaches": float(self._breaches.get(sid, 0)),
                "breach_rate": self.breach_rate(sid),
                "penalty": self.breach_penalty(sid),
            }
            for sid in all_ids
        }
