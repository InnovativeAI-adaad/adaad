# SPDX-License-Identifier: Apache-2.0
"""Deterministic planning utilities for strategy backlog execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from runtime.intelligence.strategy import StrategyInput


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    goal_id: str
    milestone: str
    success_predicate: str
    required_governance_checks: tuple[str, ...]


@dataclass(frozen=True)
class PlanArtifact:
    plan_id: str
    cycle_id: str
    backlog_snapshot: tuple[tuple[str, float], ...]
    steps: tuple[PlanStep, ...]


@dataclass(frozen=True)
class PlanExecutionState:
    plan_id: str
    current_step_index: int
    completed_step_ids: tuple[str, ...]
    progress_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanVerificationResult:
    ok: bool
    reason: str
    completed_step_id: str | None = None


class StrategyPlanner:
    """Convert strategy backlog goals into deterministic multi-step plans."""

    def build_plan(self, context: StrategyInput) -> PlanArtifact:
        ranked_goals = tuple(
            sorted(
                ((goal_id, float(max(weight, 0.0))) for goal_id, weight in context.goal_backlog.items()),
                key=lambda item: (-item[1], item[0]),
            )
        )
        if not ranked_goals:
            ranked_goals = (("maintain_operational_stability", 1.0),)

        steps: list[PlanStep] = [
            PlanStep(
                step_id="step_00_governance_precheck",
                goal_id="governance_precheck",
                milestone="Governance preconditions validated",
                success_predicate="governance.preconditions_ok",
                required_governance_checks=("policy_alignment",),
            )
        ]
        for index, (goal_id, weight) in enumerate(ranked_goals, start=1):
            normalized_goal_id = goal_id.strip() or f"goal_{index:02d}"
            steps.append(
                PlanStep(
                    step_id=f"step_{index:02d}_{normalized_goal_id}",
                    goal_id=normalized_goal_id,
                    milestone=f"Milestone {index}: advance '{normalized_goal_id}'",
                    success_predicate=f"goal.{normalized_goal_id}.completed",
                    required_governance_checks=("policy_alignment", "safety_constraints" if weight >= 0.5 else "policy_alignment"),
                )
            )

        return PlanArtifact(
            plan_id=f"plan-{context.cycle_id}",
            cycle_id=context.cycle_id,
            backlog_snapshot=ranked_goals,
            steps=tuple(steps),
        )


class PlanStepVerifier:
    """Evaluate step completion with governance checks before advancing plan state."""

    def verify_step_completion(
        self,
        *,
        step: PlanStep,
        completion_signals: Mapping[str, bool],
        governance_checks: Mapping[str, bool],
    ) -> PlanVerificationResult:
        missing_check = next((check for check in step.required_governance_checks if not governance_checks.get(check, False)), None)
        if missing_check is not None:
            return PlanVerificationResult(ok=False, reason=f"governance_check_failed:{missing_check}")
        if not completion_signals.get(step.success_predicate, False):
            return PlanVerificationResult(ok=False, reason=f"predicate_not_satisfied:{step.success_predicate}")
        return PlanVerificationResult(ok=True, reason="step_completed", completed_step_id=step.step_id)


def initial_execution_state(plan: PlanArtifact) -> PlanExecutionState:
    return PlanExecutionState(plan_id=plan.plan_id, current_step_index=0, completed_step_ids=())


def as_ledger_metrics(*, plan: PlanArtifact, state: PlanExecutionState, decision: str, verification: PlanVerificationResult | None) -> dict[str, Any]:
    active_step = plan.steps[state.current_step_index].step_id if state.current_step_index < len(plan.steps) else "completed"
    return {
        "kind": "plan_progress",
        "plan_id": plan.plan_id,
        "cycle_id": plan.cycle_id,
        "active_step": active_step,
        "completed_steps": list(state.completed_step_ids),
        "decision": decision,
        "verification": verification.reason if verification is not None else "not_evaluated",
    }
