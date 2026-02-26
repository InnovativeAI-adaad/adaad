# SPDX-License-Identifier: Apache-2.0
"""Self-validation autonomy loop utilities."""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Mapping

from runtime import metrics
from runtime.autonomy.adaptive_budget import AutonomyBudgetEngine
from runtime.governance.foundation.determinism import RuntimeDeterminismProvider, default_provider


@dataclass(frozen=True)
class AgentAction:
    agent: str
    action: str
    duration_ms: int
    ok: bool


@dataclass(frozen=True)
class AutonomyLoopResult:
    ok: bool
    post_conditions_passed: bool
    total_duration_ms: int
    mutation_score: float
    decision: str


class AGMStep(IntEnum):
    STEP_1 = 1
    STEP_2 = 2
    STEP_3 = 3
    STEP_4 = 4
    STEP_5 = 5
    STEP_6 = 6
    STEP_7 = 7
    STEP_8 = 8
    STEP_9 = 9
    STEP_10 = 10
    STEP_11 = 11
    STEP_12 = 12


@dataclass(frozen=True)
class AGMStepInput:
    cycle_id: str
    step: AGMStep
    revision_iteration: int
    max_revision_iterations: int
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AGMStepOutput:
    ok: bool
    payload: Mapping[str, Any]
    requires_revision: bool = False
    preflight_passed: bool | None = None
    signature_commit_succeeded: bool | None = None
    fault_reason: str | None = None


@dataclass(frozen=True)
class AGMCycleResult:
    loop_result: AutonomyLoopResult
    completed_steps: tuple[AGMStep, ...]
    revision_iterations: int
    preflight_passed: bool
    signature_commit_succeeded: bool
    recovery_executed: bool


AGMStepHandler = Callable[[AGMStepInput], AGMStepOutput]


def run_agm_cycle(
    *,
    cycle_id: str,
    initial_payload: Mapping[str, Any] | None = None,
    step_handlers: Mapping[AGMStep, AGMStepHandler] | None = None,
    preflight_passed: bool = True,
    signature_commit_succeeded: bool = True,
    max_revision_iterations: int = 3,
    recovery_action: Callable[[str, AGMStep, str], None] | None = None,
) -> AGMCycleResult:
    if max_revision_iterations < 1:
        raise ValueError("max_revision_iterations_must_be_positive")

    payload: dict[str, Any] = dict(initial_payload or {})
    handlers = dict(step_handlers or {})
    completed_steps: list[AGMStep] = []
    revision_iteration = 0
    recovery_executed = False

    for step in AGMStep:
        handler = handlers.get(step)
        if handler is not None:
            output = handler(
                AGMStepInput(
                    cycle_id=cycle_id,
                    step=step,
                    revision_iteration=revision_iteration,
                    max_revision_iterations=max_revision_iterations,
                    payload=payload,
                )
            )
            payload.update(dict(output.payload))
            if output.preflight_passed is not None:
                preflight_passed = output.preflight_passed
            if output.signature_commit_succeeded is not None:
                signature_commit_succeeded = output.signature_commit_succeeded
            if not output.ok:
                reason = output.fault_reason or f"step_{int(step)}_failed"
                metrics.log(
                    event_type="STEP_FAULT",
                    payload={"cycle_id": cycle_id, "step": int(step), "reason": reason},
                    level="ERROR",
                )
                if recovery_action is not None:
                    recovery_action(cycle_id, step, reason)
                    recovery_executed = True
                break

        completed_steps.append(step)

        if step == AGMStep.STEP_5 and not preflight_passed:
            metrics.log(
                event_type="STEP_FAULT",
                payload={"cycle_id": cycle_id, "step": 5, "reason": "preflight_gate_blocked"},
                level="ERROR",
            )
            if recovery_action is not None:
                recovery_action(cycle_id, AGMStep.STEP_5, "preflight_gate_blocked")
                recovery_executed = True
            break

        if step == AGMStep.STEP_8 and handler is not None:
            while output.requires_revision:
                if revision_iteration >= max_revision_iterations:
                    reason = "step_8_revision_limit_reached"
                    metrics.log(
                        event_type="STEP_FAULT",
                        payload={"cycle_id": cycle_id, "step": 8, "reason": reason},
                        level="ERROR",
                    )
                    if recovery_action is not None:
                        recovery_action(cycle_id, AGMStep.STEP_8, reason)
                        recovery_executed = True
                    return AGMCycleResult(
                        loop_result=AutonomyLoopResult(
                            ok=False,
                            post_conditions_passed=False,
                            total_duration_ms=int(payload.get("total_duration_ms", 0)),
                            mutation_score=float(payload.get("mutation_score", 0.0)),
                            decision="escalate",
                        ),
                        completed_steps=tuple(completed_steps),
                        revision_iterations=revision_iteration,
                        preflight_passed=preflight_passed,
                        signature_commit_succeeded=signature_commit_succeeded,
                        recovery_executed=recovery_executed,
                    )
                revision_iteration += 1
                output = handler(
                    AGMStepInput(
                        cycle_id=cycle_id,
                        step=step,
                        revision_iteration=revision_iteration,
                        max_revision_iterations=max_revision_iterations,
                        payload=payload,
                    )
                )
                payload.update(dict(output.payload))

        if step == AGMStep.STEP_11 and not signature_commit_succeeded:
            metrics.log(
                event_type="STEP_FAULT",
                payload={"cycle_id": cycle_id, "step": 11, "reason": "signature_commit_gate_blocked"},
                level="ERROR",
            )
            if recovery_action is not None:
                recovery_action(cycle_id, AGMStep.STEP_11, "signature_commit_gate_blocked")
                recovery_executed = True
            break

    return AGMCycleResult(
        loop_result=AutonomyLoopResult(
            ok=bool(payload.get("all_actions_ok", True)),
            post_conditions_passed=bool(payload.get("post_conditions_passed", True)),
            total_duration_ms=int(payload.get("total_duration_ms", 0)),
            mutation_score=float(payload.get("mutation_score", 0.0)),
            decision=str(payload.get("decision", "hold")),
        ),
        completed_steps=tuple(completed_steps),
        revision_iterations=revision_iteration,
        preflight_passed=preflight_passed,
        signature_commit_succeeded=signature_commit_succeeded,
        recovery_executed=recovery_executed,
    )


def run_self_check_loop(
    *,
    cycle_id: str,
    actions: list[AgentAction],
    post_condition_checks: dict[str, Callable[[], bool]],
    mutation_score: float,
    mutate_threshold: float | None = None,
    budget_engine: AutonomyBudgetEngine | None = None,
    governance_debt_score: float = 0.0,
    fitness_trend_delta: float = 0.0,
    epoch_pass_rate: float = 1.0,
    replay_mode: str = "off",
    recovery_tier: str | None = None,
    provider: RuntimeDeterminismProvider | None = None,
    duration_ms: int | None = None,
    elapsed_duration_ms: int | None = None,
) -> AutonomyLoopResult:
    warnings.warn(
        "run_self_check_loop is deprecated; use run_agm_cycle instead",
        DeprecationWarning,
        stacklevel=2,
    )
    effective_provider = provider or (budget_engine.provider if budget_engine is not None else None) or default_provider()

    mode = replay_mode.strip().lower()
    tier = (recovery_tier or "").strip().lower()
    strict_or_audit = mode in {"strict", "audit"} or tier == "audit"

    duration_override_ms = duration_ms if duration_ms is not None else elapsed_duration_ms

    started_ts: float | None = None
    if duration_override_ms is None:
        if strict_or_audit:
            if not getattr(effective_provider, "deterministic", False):
                raise RuntimeError("deterministic_timestamp_required")
            started_ts = effective_provider.now_utc().timestamp()
        else:
            started_ts = time.time()
    budget_snapshot = None
    active_threshold = 0.7 if mutate_threshold is None else float(mutate_threshold)

    step8_state = {"revision_remaining": 0}

    def _step2_action_logger(step_input: AGMStepInput) -> AGMStepOutput:
        all_actions_ok = True
        for action in actions:
            metrics.log(
                event_type="autonomy_action",
                payload={
                    "cycle_id": cycle_id,
                    "agent": action.agent,
                    "action": action.action,
                    "duration_ms": action.duration_ms,
                    "ok": action.ok,
                },
                level="INFO" if action.ok else "ERROR",
                element_id=action.agent,
            )
            if not action.ok:
                all_actions_ok = False
        return AGMStepOutput(ok=True, payload={"all_actions_ok": all_actions_ok})

    def _step3_post_checks(step_input: AGMStepInput) -> AGMStepOutput:
        check_results: dict[str, bool] = {}
        for check_name, checker in sorted(post_condition_checks.items()):
            result = bool(checker())
            check_results[check_name] = result
            metrics.log(
                event_type="autonomy_post_condition",
                payload={"cycle_id": cycle_id, "check": check_name, "passed": result},
                level="INFO" if result else "ERROR",
            )
        return AGMStepOutput(ok=True, payload={"post_conditions_passed": all(check_results.values()) if check_results else True})

    def _step4_threshold(step_input: AGMStepInput) -> AGMStepOutput:
        nonlocal budget_snapshot, active_threshold
        if budget_engine is not None:
            budget_snapshot = budget_engine.record_snapshot(
                cycle_id=cycle_id,
                governance_debt_score=governance_debt_score,
                fitness_trend_delta=fitness_trend_delta,
                epoch_pass_rate=epoch_pass_rate,
            )
            active_threshold = budget_snapshot.threshold
        return AGMStepOutput(ok=True, payload={"mutate_threshold": active_threshold})

    def _step6_decide(step_input: AGMStepInput) -> AGMStepOutput:
        all_actions_ok = bool(step_input.payload.get("all_actions_ok", True))
        post_conditions_passed = bool(step_input.payload.get("post_conditions_passed", True))
        if not all_actions_ok or not post_conditions_passed:
            decision = "escalate"
        elif mutation_score >= active_threshold:
            decision = "self_mutate"
        else:
            decision = "hold"
        return AGMStepOutput(ok=True, payload={"decision": decision, "mutation_score": mutation_score})

    def _step8_revision(step_input: AGMStepInput) -> AGMStepOutput:
        requires_revision = bool(step8_state["revision_remaining"] > 0)
        if requires_revision:
            step8_state["revision_remaining"] -= 1
        return AGMStepOutput(ok=True, payload={}, requires_revision=requires_revision)

    cycle_result = run_agm_cycle(
        cycle_id=cycle_id,
        initial_payload={
            "mutation_score": mutation_score,
            "all_actions_ok": True,
            "post_conditions_passed": True,
        },
        step_handlers={
            AGMStep.STEP_2: _step2_action_logger,
            AGMStep.STEP_3: _step3_post_checks,
            AGMStep.STEP_4: _step4_threshold,
            AGMStep.STEP_6: _step6_decide,
            AGMStep.STEP_8: _step8_revision,
        },
    )

    if duration_override_ms is not None:
        total_duration_ms = int(duration_override_ms)
    elif strict_or_audit:
        finished_ts = effective_provider.now_utc().timestamp()
        total_duration_ms = int((finished_ts - (started_ts or finished_ts)) * 1000)
    else:
        total_duration_ms = int((time.time() - (started_ts or time.time())) * 1000)
    metrics.log(
        event_type="autonomy_cycle_summary",
        payload={
            "cycle_id": cycle_id,
            "all_actions_ok": cycle_result.loop_result.ok,
            "post_conditions_passed": cycle_result.loop_result.post_conditions_passed,
            "mutation_score": mutation_score,
            "mutate_threshold": active_threshold,
            "threshold_source": "adaptive_budget" if budget_snapshot else "static",
            "budget_snapshot_hash": budget_snapshot.snapshot_hash if budget_snapshot else None,
            "decision": cycle_result.loop_result.decision,
            "total_duration_ms": total_duration_ms,
        },
        level="INFO" if cycle_result.loop_result.decision != "escalate" else "ERROR",
    )
    return AutonomyLoopResult(
        ok=cycle_result.loop_result.ok,
        post_conditions_passed=cycle_result.loop_result.post_conditions_passed,
        total_duration_ms=total_duration_ms,
        mutation_score=mutation_score,
        decision=cycle_result.loop_result.decision,
    )
