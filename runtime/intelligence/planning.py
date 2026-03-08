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
    completion_criteria: tuple[str, ...]
    dependency_step_ids: tuple[str, ...]
    required_governance_checks: tuple[str, ...]
    required_replay_checks: tuple[str, ...] = ()


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
    last_transition_reason: str = "not_started"
    rollback_step_index: int = 0


@dataclass(frozen=True)
class PlanVerificationResult:
    ok: bool
    reason: str
    completed_step_id: str | None = None
    rollback_step_index: int | None = None


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
                completion_criteria=("governance.preconditions_ok",),
                dependency_step_ids=(),
                required_governance_checks=("policy_alignment",),
                required_replay_checks=("replay_preconditions_ok",),
            )
        ]
        for index, (goal_id, weight) in enumerate(ranked_goals, start=1):
            normalized_goal_id = goal_id.strip() or f"goal_{index:02d}"
            dependency = steps[-1].step_id
            criteria = (f"goal.{normalized_goal_id}.completed",)
            steps.append(
                PlanStep(
                    step_id=f"step_{index:02d}_{normalized_goal_id}",
                    goal_id=normalized_goal_id,
                    milestone=f"Milestone {index}: advance '{normalized_goal_id}'",
                    success_predicate=criteria[0],
                    completion_criteria=criteria,
                    dependency_step_ids=(dependency,),
                    required_governance_checks=("policy_alignment", "safety_constraints" if weight >= 0.5 else "policy_alignment"),
                    required_replay_checks=("replay_digest_match",),
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
        completed_step_ids: tuple[str, ...],
        completion_signals: Mapping[str, bool],
        governance_checks: Mapping[str, bool],
        replay_checks: Mapping[str, bool],
    ) -> PlanVerificationResult:
        missing_dependency = next((dependency for dependency in step.dependency_step_ids if dependency not in completed_step_ids), None)
        if missing_dependency is not None:
            return PlanVerificationResult(ok=False, reason=f"dependency_not_satisfied:{missing_dependency}")
        missing_check = next((check for check in step.required_governance_checks if not governance_checks.get(check, False)), None)
        if missing_check is not None:
            return PlanVerificationResult(ok=False, reason=f"governance_check_failed:{missing_check}", rollback_step_index=0)
        missing_replay = next((check for check in step.required_replay_checks if not replay_checks.get(check, False)), None)
        if missing_replay is not None:
            return PlanVerificationResult(ok=False, reason=f"replay_check_failed:{missing_replay}", rollback_step_index=0)
        missing_criteria = next((criteria for criteria in step.completion_criteria if not completion_signals.get(criteria, False)), None)
        if missing_criteria is not None:
            return PlanVerificationResult(ok=False, reason=f"criteria_not_satisfied:{missing_criteria}")
        return PlanVerificationResult(ok=True, reason="step_completed", completed_step_id=step.step_id)


def initial_execution_state(plan: PlanArtifact) -> PlanExecutionState:
    return PlanExecutionState(plan_id=plan.plan_id, current_step_index=0, completed_step_ids=(), rollback_step_index=0)


def as_ledger_metrics(*, plan: PlanArtifact, state: PlanExecutionState, decision: str, verification: PlanVerificationResult | None) -> dict[str, Any]:
    active_step = plan.steps[state.current_step_index].step_id if state.current_step_index < len(plan.steps) else "completed"
    return {
        "kind": "plan_progress",
        "plan_id": plan.plan_id,
        "cycle_id": plan.cycle_id,
        "active_step": active_step,
        "completed_steps": list(state.completed_step_ids),
        "last_transition_reason": state.last_transition_reason,
        "rollback_step_index": state.rollback_step_index,
        "decision": decision,
        "verification": verification.reason if verification is not None else "not_evaluated",
    }


def as_transition_metrics(
    *,
    plan: PlanArtifact,
    step: PlanStep | None,
    previous_state: PlanExecutionState,
    current_state: PlanExecutionState,
    verification: PlanVerificationResult | None,
) -> dict[str, Any]:
    return {
        "kind": "plan_transition",
        "plan_id": plan.plan_id,
        "cycle_id": plan.cycle_id,
        "active_step": step.step_id if step is not None else "completed",
        "from_step_index": previous_state.current_step_index,
        "to_step_index": current_state.current_step_index,
        "completed_steps": list(current_state.completed_step_ids),
        "rationale": verification.reason if verification is not None else "not_evaluated",
        "rollback_step_index": current_state.rollback_step_index,
    }
