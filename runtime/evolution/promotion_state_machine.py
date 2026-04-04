# SPDX-License-Identifier: Apache-2.0
"""Promotion lifecycle state machine used by mutation governance."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping

from security import cryovant


class PromotionState(Enum):
    PROPOSED = "proposed"
    CERTIFIED = "certified"
    ACTIVATED = "activated"
    REJECTED = "rejected"


_DEFAULT_CANARY_STAGES: tuple[dict[str, Any], ...] = (
    {
        "stage_id": "canary_small",
        "cohort_ids": ["cohort_a", "cohort_b"],
        "rollback_threshold": 1,
        "halt_on_fail": True,
    },
    {
        "stage_id": "canary_medium",
        "cohort_ids": ["cohort_c", "cohort_d"],
        "rollback_threshold": 2,
        "halt_on_fail": True,
    },
)


def canary_stage_definitions() -> List[Dict[str, Any]]:
    """Return deterministic default canary stage definitions."""
    return [dict(stage, cohort_ids=list(stage.get("cohort_ids") or [])) for stage in _DEFAULT_CANARY_STAGES]


_ALLOWED_TRANSITIONS: dict[PromotionState, frozenset[PromotionState]] = {
    PromotionState.PROPOSED: frozenset({PromotionState.CERTIFIED, PromotionState.REJECTED}),
    PromotionState.CERTIFIED: frozenset({PromotionState.ACTIVATED, PromotionState.REJECTED}),
    PromotionState.ACTIVATED: frozenset({PromotionState.REJECTED}),
    PromotionState.REJECTED: frozenset(),
}


class TransitionGuardFailed(RuntimeError):
    """Raised when a promotion transition guard check fails."""

    def __init__(self, reason: str, guard_report: Dict[str, Any]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.guard_report = guard_report


def founders_law_check() -> tuple[bool, list[str]]:
    """Stubbed Founder’s Law check for promotion transitions."""
    return True, []


@dataclass
class PromotionTransitionContext:
    signature: str = ""
    trust_mode: str = "dev"
    fitness_score: float | None = None
    fitness_threshold: float = 0.0
    cert_refs: Mapping[str, Any] = field(default_factory=dict)
    founders_law_check: Callable[[], tuple[bool, list[str]]] = founders_law_check


_TRANSITION_RULES: dict[tuple[PromotionState, PromotionState], dict[str, Any]] = {
    (PromotionState.PROPOSED, PromotionState.CERTIFIED): {"require_fitness": False, "allowed_trust_modes": frozenset({"dev", "prod"})},
    (PromotionState.CERTIFIED, PromotionState.ACTIVATED): {"require_fitness": True, "allowed_trust_modes": frozenset({"dev", "prod"})},
    (PromotionState.PROPOSED, PromotionState.REJECTED): {"require_fitness": False, "allowed_trust_modes": frozenset({"dev", "prod"})},
    (PromotionState.CERTIFIED, PromotionState.REJECTED): {"require_fitness": False, "allowed_trust_modes": frozenset({"dev", "prod"})},
    (PromotionState.ACTIVATED, PromotionState.REJECTED): {"require_fitness": False, "allowed_trust_modes": frozenset({"dev", "prod"})},
}


def can_transition(current: PromotionState, nxt: PromotionState) -> bool:
    return nxt in _ALLOWED_TRANSITIONS[current]


def evaluate_transition_guards(current: PromotionState, nxt: PromotionState, context: PromotionTransitionContext) -> Dict[str, Any]:
    rule = _TRANSITION_RULES.get((current, nxt))
    if rule is None:
        return {"ok": False, "reason": "undeclared_transition"}

    trust_mode = (context.trust_mode or "dev").strip().lower()
    signature_ok = cryovant.signature_valid(context.signature)
    founders_ok, founders_failures = context.founders_law_check()
    fitness_ok = True
    if rule["require_fitness"]:
        fitness_ok = context.fitness_score is not None and context.fitness_score >= context.fitness_threshold

    return {
        "ok": signature_ok and founders_ok and fitness_ok and trust_mode in rule["allowed_trust_modes"],
        "cryovant_signature_validity": {"ok": signature_ok},
        "founders_law_invariant_gate": {"ok": founders_ok, "failures": founders_failures},
        "fitness_threshold_gate": {
            "ok": fitness_ok,
            "required": bool(rule["require_fitness"]),
            "score": context.fitness_score,
            "threshold": context.fitness_threshold,
        },
        "trust_mode_compatibility_gate": {
            "ok": trust_mode in rule["allowed_trust_modes"],
            "trust_mode": trust_mode,
            "allowed": sorted(rule["allowed_trust_modes"]),
        },
    }


def require_transition(current: PromotionState, nxt: PromotionState, context: PromotionTransitionContext | None = None) -> Dict[str, Any]:
    if not can_transition(current, nxt):
        raise ValueError(f"invalid promotion transition: {current.value} -> {nxt.value}")
    guard_report = {"ok": True}
    if context is not None:
        guard_report = evaluate_transition_guards(current, nxt, context)
        if not guard_report["ok"]:
            raise TransitionGuardFailed(f"guard_failed:{current.value}->{nxt.value}", guard_report)
    return guard_report


__all__ = [
    "PromotionState",
    "PromotionTransitionContext",
    "TransitionGuardFailed",
    "can_transition",
    "evaluate_transition_guards",
    "require_transition",
    "canary_stage_definitions",
    "founders_law_check",
]
