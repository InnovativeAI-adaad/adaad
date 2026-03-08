# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from runtime.intelligence.planning import PlanStepVerifier, StrategyPlanner
from runtime.intelligence.strategy import StrategyInput


def test_strategy_planner_converts_backlog_to_ranked_multi_step_plan() -> None:
    planner = StrategyPlanner()
    plan = planner.build_plan(
        StrategyInput(
            cycle_id="cycle-42",
            mutation_score=0.2,
            governance_debt_score=0.1,
            goal_backlog={"reduce_latency": 0.2, "stabilize_replay": 0.9, "improve_coverage": 0.6},
        )
    )

    assert plan.plan_id == "plan-cycle-42"
    assert plan.steps[0].step_id == "step_00_governance_precheck"
    assert plan.steps[1].goal_id == "stabilize_replay"
    assert plan.steps[1].required_governance_checks == ("policy_alignment", "safety_constraints")


def test_plan_step_verifier_requires_governance_checks_before_step_completion() -> None:
    planner = StrategyPlanner()
    verifier = PlanStepVerifier()
    plan = planner.build_plan(
        StrategyInput(
            cycle_id="cycle-verify",
            mutation_score=0.3,
            governance_debt_score=0.1,
            goal_backlog={"secure_merge": 0.8},
        )
    )
    active_step = plan.steps[1]

    blocked = verifier.verify_step_completion(
        step=active_step,
        completion_signals={active_step.success_predicate: True},
        governance_checks={"policy_alignment": True, "safety_constraints": False},
    )
    assert blocked.ok is False
    assert blocked.reason == "governance_check_failed:safety_constraints"

    passed = verifier.verify_step_completion(
        step=active_step,
        completion_signals={active_step.success_predicate: True},
        governance_checks={"policy_alignment": True, "safety_constraints": True},
    )
    assert passed.ok is True
    assert passed.completed_step_id == active_step.step_id
