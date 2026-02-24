# SPDX-License-Identifier: Apache-2.0
"""Self-validation autonomy loop utilities."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

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

    check_results: dict[str, bool] = {}
    for check_name, checker in sorted(post_condition_checks.items()):
        result = bool(checker())
        check_results[check_name] = result
        metrics.log(
            event_type="autonomy_post_condition",
            payload={"cycle_id": cycle_id, "check": check_name, "passed": result},
            level="INFO" if result else "ERROR",
        )

    post_conditions_passed = all(check_results.values()) if check_results else True

    budget_snapshot = None
    if budget_engine is not None:
        budget_snapshot = budget_engine.record_snapshot(
            cycle_id=cycle_id,
            governance_debt_score=governance_debt_score,
            fitness_trend_delta=fitness_trend_delta,
            epoch_pass_rate=epoch_pass_rate,
        )
        active_threshold = budget_snapshot.threshold
    else:
        active_threshold = 0.7 if mutate_threshold is None else float(mutate_threshold)

    if not all_actions_ok or not post_conditions_passed:
        decision = "escalate"
    elif mutation_score >= active_threshold:
        decision = "self_mutate"
    else:
        decision = "hold"

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
            "all_actions_ok": all_actions_ok,
            "post_conditions_passed": post_conditions_passed,
            "mutation_score": mutation_score,
            "mutate_threshold": active_threshold,
            "threshold_source": "adaptive_budget" if budget_snapshot else "static",
            "budget_snapshot_hash": budget_snapshot.snapshot_hash if budget_snapshot else None,
            "decision": decision,
            "total_duration_ms": total_duration_ms,
        },
        level="INFO" if decision != "escalate" else "ERROR",
    )
    return AutonomyLoopResult(
        ok=all_actions_ok,
        post_conditions_passed=post_conditions_passed,
        total_duration_ms=total_duration_ms,
        mutation_score=mutation_score,
        decision=decision,
    )
