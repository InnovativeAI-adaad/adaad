"""Promotion gate integrating sandbox and fitness thresholds."""

from __future__ import annotations

from dataclasses import dataclass

from sandbox.sandbox_executor import SandboxResult


@dataclass(frozen=True)
class PromotionPolicy:
    min_fitness: float = 0.6
    min_revenue: float = 0.5


@dataclass(frozen=True)
class PromotionDecision:
    approved: bool
    reason: str
    ledger_hash: str | None = None


def evaluate_promotion(result: SandboxResult, policy: PromotionPolicy, *, ledger_hash: str | None = None) -> PromotionDecision:
    if result.status != "pass":
        return PromotionDecision(approved=False, reason="sandbox_failed")
    if result.fitness_score < policy.min_fitness:
        return PromotionDecision(approved=False, reason="fitness_below_threshold")
    if result.revenue_score < policy.min_revenue:
        return PromotionDecision(approved=False, reason="revenue_below_threshold")
    return PromotionDecision(approved=True, reason="approved", ledger_hash=ledger_hash)
