# SPDX-License-Identifier: Apache-2.0
"""Strategy primitives for AGM-style runtime decisioning.

Phase 16: Mutation Strategy Taxonomy Expansion — 2 -> 6 context-driven strategies.

Strategy selection priority (high -> low):
  safety_hardening > structural_refactor > test_coverage_expansion
  > performance_optimization > adaptive_self_mutate > conservative_hold

All strategies are deterministic: identical StrategyInput always yields identical
StrategyDecision. strategy_id is constrained to STRATEGY_TAXONOMY — unknown IDs
raise ValueError at selection time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Public taxonomy registry — Phase 16
# ---------------------------------------------------------------------------

STRATEGY_TAXONOMY: frozenset[str] = frozenset(
    {
        "adaptive_self_mutate",
        "conservative_hold",
        "structural_refactor",
        "test_coverage_expansion",
        "performance_optimization",
        "safety_hardening",
    }
)

# Priority order for disambiguation when multiple strategies qualify with equal payoff.
# Lower index = higher priority. Payoff always takes precedence over priority.
_STRATEGY_PRIORITY: tuple[str, ...] = (
    "safety_hardening",
    "structural_refactor",
    "test_coverage_expansion",
    "performance_optimization",
    "adaptive_self_mutate",
    "conservative_hold",
)

_PRIORITY_MIN_CONFIDENCE: float = 0.55


def _priority(strategy_id: str) -> int:
    try:
        return _STRATEGY_PRIORITY.index(strategy_id)
    except ValueError:
        return len(_STRATEGY_PRIORITY)


# ---------------------------------------------------------------------------
# Data contracts (unchanged public interface)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyInput:
    """Typed context consumed by strategy selection."""

    cycle_id: str
    mutation_score: float
    governance_debt_score: float
    horizon_cycles: int = 1
    resource_budget: float = 1.0
    goal_backlog: Mapping[str, float] = field(default_factory=dict)
    lineage_health: float = 1.0
    signals: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyDecision:
    """Normalized strategy output consumed by proposal generation."""

    strategy_id: str
    rationale: str
    confidence: float
    goal_plan: tuple[str, ...] = ()
    priority_queue: tuple[str, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.strategy_id not in STRATEGY_TAXONOMY:
            raise ValueError(
                f"strategy_id '{self.strategy_id}' not in STRATEGY_TAXONOMY; "
                f"valid IDs: {sorted(STRATEGY_TAXONOMY)}"
            )


# ---------------------------------------------------------------------------
# StrategyModule — Phase 16 six-strategy deterministic selector
# ---------------------------------------------------------------------------


class StrategyModule:
    """Deterministic, side-effect-free strategy module.

    Expanded in Phase 16 from 2 to 6 strategies. Selection is a pure function
    of StrategyInput — no external state, no randomness.

    Sorting rule: primary = payoff desc; secondary = priority asc (tiebreak);
    tertiary = lexicographic on strategy_id (full determinism guarantee).
    """

    # Trigger thresholds
    _SAFETY_HARDENING_DEBT_THRESHOLD: float = 0.70
    _STRUCTURAL_REFACTOR_LINEAGE_THRESHOLD: float = 0.50
    _TEST_COVERAGE_DEBT_THRESHOLD: float = 0.55
    _PERFORMANCE_OPT_MUTATION_THRESHOLD: float = 0.60
    _PERFORMANCE_OPT_MARKET_THRESHOLD: float = 0.40
    _ADAPTIVE_MUTATION_THRESHOLD: float = 0.70
    _ADAPTIVE_BUDGET_THRESHOLD: float = 0.60
    _CONSERVATIVE_LINEAGE_THRESHOLD: float = 0.80
    _CONSERVATIVE_HORIZON_THRESHOLD: int = 9

    def select(self, context: StrategyInput) -> StrategyDecision:  # noqa: C901
        n_debt = self._normalize(context.governance_debt_score)
        n_lineage = self._normalize(context.lineage_health)
        n_mutation = self._normalize(context.mutation_score)
        n_budget = self._normalize(context.resource_budget)
        n_horizon = self._normalize_horizon(context.horizon_cycles)
        backlog_pressure = self._normalize(
            sum(max(v, 0.0) for v in context.goal_backlog.values()) / 4.0
        )

        candidates: list[tuple[str, float, str]] = []

        # 1. safety_hardening — critical debt (>= 0.70)
        if context.governance_debt_score >= self._SAFETY_HARDENING_DEBT_THRESHOLD:
            payoff = self._normalize(0.80 * n_debt + 0.20 * (1.0 - n_lineage))
            candidates.append((
                "safety_hardening",
                payoff,
                "governance_debt_score above critical threshold; safety hardening required",
            ))

        # 2. structural_refactor — lineage decay (< 0.50)
        if context.lineage_health < self._STRUCTURAL_REFACTOR_LINEAGE_THRESHOLD:
            payoff = self._normalize(
                0.75 * (1.0 - n_lineage) + 0.25 * backlog_pressure
            )
            candidates.append((
                "structural_refactor",
                payoff,
                "lineage_health below threshold; structural refactor prioritised",
            ))

        # 3. test_coverage_expansion — elevated but not critical debt [0.55, 0.70)
        if (
            context.governance_debt_score >= self._TEST_COVERAGE_DEBT_THRESHOLD
            and context.governance_debt_score < self._SAFETY_HARDENING_DEBT_THRESHOLD
        ):
            payoff = self._normalize(
                0.65 * n_debt + 0.20 * backlog_pressure + 0.15 * (1.0 - n_lineage)
            )
            candidates.append((
                "test_coverage_expansion",
                payoff,
                "governance_debt elevated; test coverage expansion reduces debt accumulation",
            ))

        # 4. performance_optimization — mutation headroom + market pressure
        if context.mutation_score >= self._PERFORMANCE_OPT_MUTATION_THRESHOLD:
            market_pressure = self._normalize(
                float(context.signals.get("market_fitness_score", 0.0))
            )
            if market_pressure >= self._PERFORMANCE_OPT_MARKET_THRESHOLD or context.mutation_score >= 0.80:
                payoff = self._normalize(
                    0.55 * n_mutation + 0.30 * market_pressure + 0.15 * n_budget
                )
                candidates.append((
                    "performance_optimization",
                    payoff,
                    "mutation headroom and market fitness pressure favour performance optimisation",
                ))

        # 5. adaptive_self_mutate — high mutation + budget
        if (
            context.mutation_score >= self._ADAPTIVE_MUTATION_THRESHOLD
            and context.resource_budget >= self._ADAPTIVE_BUDGET_THRESHOLD
        ):
            payoff = self._normalize(0.70 * n_mutation + 0.30 * n_budget - 0.10 * n_debt)
            candidates.append((
                "adaptive_self_mutate",
                payoff,
                "ranked objective 'deliver_immediate_mutation_gain' highest with deterministic payoff mapping",
            ))

        # 6. conservative_hold — stable lineage + long horizon
        if (
            context.lineage_health >= self._CONSERVATIVE_LINEAGE_THRESHOLD
            and context.horizon_cycles >= self._CONSERVATIVE_HORIZON_THRESHOLD
        ):
            payoff = self._normalize(0.55 * n_lineage + 0.45 * n_horizon - 0.10 * n_debt)
            candidates.append((
                "conservative_hold",
                payoff,
                "ranked objective 'preserve_lineage_health' highest with deterministic payoff mapping",
            ))

        # Guarantee non-empty set: add both legacy strategies if nothing qualified
        if not candidates:
            payoff_am = self._normalize(0.70 * n_mutation + 0.30 * n_budget - 0.10 * n_debt)
            payoff_ch = self._normalize(0.55 * n_lineage + 0.45 * n_horizon - 0.10 * n_debt)
            candidates = [
                (
                    "adaptive_self_mutate",
                    payoff_am,
                    "ranked objective 'deliver_immediate_mutation_gain' highest with deterministic payoff mapping",
                ),
                (
                    "conservative_hold",
                    payoff_ch,
                    "ranked objective 'preserve_lineage_health' highest with deterministic payoff mapping",
                ),
            ]

        # Sort: payoff desc primary; priority asc secondary; lexicographic tertiary
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (-c[1], _priority(c[0]), c[0]),
        )

        chosen_id, chosen_payoff, chosen_rationale = sorted_candidates[0]
        priority_queue = tuple(c[0] for c in sorted_candidates)

        # Confidence: gap between top and second payoff, floored at minimum
        second_payoff = sorted_candidates[1][1] if len(sorted_candidates) > 1 else chosen_payoff
        raw_confidence = 0.55 + (chosen_payoff - second_payoff) * 0.45
        confidence = self._normalize(max(raw_confidence, _PRIORITY_MIN_CONFIDENCE))

        goal_plan = self._derive_goal_plan(context)

        return StrategyDecision(
            strategy_id=chosen_id,
            rationale=chosen_rationale,
            confidence=confidence,
            goal_plan=goal_plan,
            priority_queue=priority_queue,
            parameters={
                "horizon_cycles": int(max(context.horizon_cycles, 1)),
                "strategy_taxonomy_version": "16.0",
                "normalized": {
                    "mutation": n_mutation,
                    "governance_debt": n_debt,
                    "resource_budget": n_budget,
                    "lineage_health": n_lineage,
                    "horizon": n_horizon,
                },
                "candidates": [
                    {"strategy_id": c[0], "payoff": c[1]} for c in sorted_candidates
                ],
            },
        )

    def _derive_goal_plan(self, context: StrategyInput) -> tuple[str, ...]:
        n_mutation = self._normalize(context.mutation_score)
        n_debt = self._normalize(context.governance_debt_score)
        n_lineage = self._normalize(context.lineage_health)
        n_horizon = self._normalize_horizon(context.horizon_cycles)
        n_budget = self._normalize(context.resource_budget)
        backlog_pressure = self._normalize(
            sum(max(v, 0.0) for v in context.goal_backlog.values()) / 4.0
        )

        objective_scores = (
            (
                "deliver_immediate_mutation_gain",
                self._normalize(n_mutation * (0.75 + 0.25 * n_budget)),
                "short",
            ),
            (
                "reduce_backlog_risk",
                self._normalize(backlog_pressure * (0.6 + 0.4 * n_budget)),
                "short",
            ),
            (
                "improve_governance_stability",
                self._normalize((1.0 - n_debt) * (0.5 + 0.5 * n_horizon)),
                "medium",
            ),
            (
                "preserve_lineage_health",
                self._normalize(n_lineage * (0.4 + 0.6 * n_horizon)),
                "medium",
            ),
        )

        ranked = tuple(
            sorted(
                objective_scores,
                key=lambda o: (-o[1], 0 if o[2] == "short" else 1, o[0]),
            )
        )
        return tuple(obj_id for obj_id, _, _ in ranked)

    @staticmethod
    def _normalize(value: float) -> float:
        return min(max(round(float(value), 6), 0.0), 1.0)

    def _normalize_horizon(self, cycles: int) -> float:
        bounded = min(max(int(cycles), 1), 12)
        return self._normalize(bounded / 12.0)
