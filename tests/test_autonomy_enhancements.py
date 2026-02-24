# SPDX-License-Identifier: Apache-2.0

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime.autonomy.adaptive_budget import AutonomyBudgetEngine
from runtime.autonomy.loop import AgentAction, run_self_check_loop
from runtime.autonomy.mutation_scaffold import MutationCandidate, rank_mutation_candidates
from runtime.autonomy.roles import SandboxPermission, default_role_specs
from runtime.autonomy.scoreboard import build_scoreboard_views
from runtime.governance.foundation.determinism import SeededDeterminismProvider, SystemDeterminismProvider


class AutonomyEnhancementTest(unittest.TestCase):
    def test_default_roles_define_required_agents(self) -> None:
        roles = default_role_specs()
        self.assertEqual(
            set(roles.keys()),
            {"ArchitectAgent", "ExecutorAgent", "ValidatorAgent", "MutatorAgent", "ClaudeProposalAgent", "GovernanceAgent"},
        )
        self.assertEqual(roles["GovernanceAgent"].sandbox_permission, SandboxPermission.GOVERNANCE)
        self.assertIn("adjudicate(proposal)", roles["GovernanceAgent"].interface)
        self.assertEqual(roles["ClaudeProposalAgent"].interface, ("propose(context)", "score(candidate)"))

    def test_autonomy_loop_escalates_on_failed_post_condition(self) -> None:
        actions = [
            AgentAction(agent="ExecutorAgent", action="apply_patch", duration_ms=25, ok=True),
            AgentAction(agent="ValidatorAgent", action="run_tests", duration_ms=30, ok=True),
        ]
        result = run_self_check_loop(
            cycle_id="cycle-1",
            actions=actions,
            post_condition_checks={"tests_pass": lambda: False},
            mutation_score=0.95,
            mutate_threshold=0.8,
        )
        self.assertEqual(result.decision, "escalate")
        self.assertFalse(result.post_conditions_passed)

    def test_rank_mutation_candidates_is_deterministic(self) -> None:
        candidates = [
            MutationCandidate("m2", expected_gain=0.70, risk_score=0.20, complexity=0.15, coverage_delta=0.10),
            MutationCandidate("m1", expected_gain=0.70, risk_score=0.20, complexity=0.15, coverage_delta=0.10),
            MutationCandidate("m3", expected_gain=0.40, risk_score=0.30, complexity=0.35, coverage_delta=0.00),
        ]
        ranked = rank_mutation_candidates(candidates, acceptance_threshold=0.2)
        self.assertEqual([item.mutation_id for item in ranked], ["m1", "m2", "m3"])
        self.assertTrue(ranked[0].accepted)

    def test_scoreboard_builds_required_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.jsonl"
            with mock.patch("runtime.metrics.METRICS_PATH", metrics_path):
                from runtime import metrics

                metrics.log("autonomy_action", {"agent": "ExecutorAgent", "duration_ms": 40, "ok": True})
                metrics.log("mutation_executed", {"ok": True})
                metrics.log("sandbox_validation_failed", {"reason": "missing_signature"})

                scoreboard = build_scoreboard_views(limit=50)

        self.assertIn("performance_by_agent", scoreboard)
        self.assertIn("mutation_outcomes", scoreboard)
        self.assertIn("sandbox_failure_reasons", scoreboard)
        self.assertIn("ExecutorAgent", scoreboard["performance_by_agent"])
        self.assertEqual(scoreboard["mutation_outcomes"].get("mutation_executed"), 1)
        self.assertEqual(scoreboard["sandbox_failure_reasons"].get("missing_signature"), 1)


    def test_scoreboard_handles_missing_metrics_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "missing_metrics.jsonl"
            with mock.patch("runtime.metrics.METRICS_PATH", metrics_path):
                scoreboard = build_scoreboard_views(limit=25)

        self.assertEqual(scoreboard["performance_by_agent"], {})
        self.assertEqual(scoreboard["mutation_outcomes"], {})
        self.assertEqual(scoreboard["sandbox_failure_reasons"], {})

    def test_scoreboard_ignores_malformed_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.jsonl"
            metrics_path.write_text(
                '{"event":"autonomy_action","payload":{"agent":"ExecutorAgent","duration_ms":"not-an-int"}}\n'
                '{"event":"sandbox_validation_failed","payload":"not-a-dict"}\n',
                encoding="utf-8",
            )
            with mock.patch("runtime.metrics.METRICS_PATH", metrics_path):
                scoreboard = build_scoreboard_views(limit=50)

        self.assertEqual(scoreboard["performance_by_agent"]["ExecutorAgent"]["avg_duration_ms"], 0.0)
        self.assertEqual(scoreboard["sandbox_failure_reasons"]["unknown"], 1)

    def test_adaptive_budget_snapshot_persistence_and_hash_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "budget.jsonl"
            engine = AutonomyBudgetEngine(
                snapshot_path=snapshot_path,
                base_threshold=0.7,
                threshold_floor=0.4,
                threshold_ceiling=0.9,
            )

            first = engine.record_snapshot(
                cycle_id="cycle-a",
                governance_debt_score=0.2,
                fitness_trend_delta=0.1,
                epoch_pass_rate=0.8,
                created_at_ms=101,
            )
            second = engine.record_snapshot(
                cycle_id="cycle-b",
                governance_debt_score=1.5,
                fitness_trend_delta=-2.0,
                epoch_pass_rate=-1.0,
                created_at_ms=202,
            )

            self.assertEqual(second.prev_hash, first.snapshot_hash)
            self.assertEqual(engine.latest_snapshot().snapshot_hash, second.snapshot_hash)
            self.assertEqual(engine.get_current_threshold(), second.threshold)
            self.assertGreaterEqual(second.threshold, 0.4)
            self.assertLessEqual(second.threshold, 0.9)

    def test_autonomy_loop_uses_budget_engine_threshold(self) -> None:
        actions = [AgentAction(agent="ExecutorAgent", action="apply_patch", duration_ms=12, ok=True)]
        with tempfile.TemporaryDirectory() as tmp:
            engine = AutonomyBudgetEngine(
                snapshot_path=Path(tmp) / "budget.jsonl",
                base_threshold=0.7,
                threshold_floor=0.35,
                threshold_ceiling=0.9,
            )
            result = run_self_check_loop(
                cycle_id="cycle-budget",
                actions=actions,
                post_condition_checks={"tests_pass": lambda: True},
                mutation_score=0.65,
                mutate_threshold=0.5,
                budget_engine=engine,
                governance_debt_score=0.5,
                fitness_trend_delta=0.0,
                epoch_pass_rate=0.9,
            )

            threshold = engine.get_current_threshold()
            self.assertGreater(threshold, 0.5)
            self.assertEqual(result.decision, "hold")


    def test_autonomy_cycle_summary_deterministic_under_strict_provider(self) -> None:
        actions = [AgentAction(agent="ExecutorAgent", action="apply_patch", duration_ms=7, ok=True)]

        class _StepProvider:
            deterministic = True

            def __init__(self) -> None:
                from datetime import datetime, timedelta, timezone

                self._base = datetime(2026, 1, 1, tzinfo=timezone.utc)
                self._step = timedelta(milliseconds=25)
                self._calls = 0

            def now_utc(self):
                value = self._base + (self._step * self._calls)
                self._calls += 1
                return value

        provider = _StepProvider()

        with mock.patch("runtime.metrics.log") as log_mock:
            result = run_self_check_loop(
                cycle_id="cycle-deterministic-summary",
                actions=actions,
                post_condition_checks={"tests_pass": lambda: True},
                mutation_score=0.75,
                mutate_threshold=0.7,
                replay_mode="strict",
                provider=provider,
            )

        self.assertEqual(result.total_duration_ms, 25)
        summary_call = log_mock.call_args_list[-1]
        self.assertEqual(summary_call.kwargs["event_type"], "autonomy_cycle_summary")
        self.assertEqual(
            summary_call.kwargs["payload"],
            {
                "cycle_id": "cycle-deterministic-summary",
                "all_actions_ok": True,
                "post_conditions_passed": True,
                "mutation_score": 0.75,
                "mutate_threshold": 0.7,
                "threshold_source": "static",
                "budget_snapshot_hash": None,
                "decision": "self_mutate",
                "total_duration_ms": 25,
            },
        )

    def test_autonomy_loop_decision_semantics_unchanged_with_elapsed_override(self) -> None:
        actions_ok = [AgentAction(agent="ExecutorAgent", action="apply_patch", duration_ms=3, ok=True)]
        actions_fail = [AgentAction(agent="ExecutorAgent", action="apply_patch", duration_ms=3, ok=False)]

        escalate = run_self_check_loop(
            cycle_id="cycle-escalate",
            actions=actions_fail,
            post_condition_checks={"tests_pass": lambda: True},
            mutation_score=1.0,
            mutate_threshold=0.1,
            elapsed_duration_ms=9,
        )
        self.assertEqual(escalate.decision, "escalate")

        self_mutate = run_self_check_loop(
            cycle_id="cycle-self-mutate",
            actions=actions_ok,
            post_condition_checks={"tests_pass": lambda: True},
            mutation_score=0.8,
            mutate_threshold=0.7,
            elapsed_duration_ms=9,
        )
        self.assertEqual(self_mutate.decision, "self_mutate")

        hold = run_self_check_loop(
            cycle_id="cycle-hold",
            actions=actions_ok,
            post_condition_checks={"tests_pass": lambda: True},
            mutation_score=0.6,
            mutate_threshold=0.7,
            elapsed_duration_ms=9,
        )
        self.assertEqual(hold.decision, "hold")

    def test_autonomy_loop_backward_compatible_without_provider(self) -> None:
        actions = [AgentAction(agent="ExecutorAgent", action="apply_patch", duration_ms=10, ok=True)]

        with mock.patch("runtime.autonomy.loop.time.time", side_effect=[10.0, 10.05]):
            result = run_self_check_loop(
                cycle_id="cycle-compat",
                actions=actions,
                post_condition_checks={"tests_pass": lambda: True},
                mutation_score=0.2,
                mutate_threshold=0.3,
            )

        self.assertEqual(result.total_duration_ms, 50)
        self.assertEqual(result.decision, "hold")


    def test_autonomy_loop_strict_allows_elapsed_override_without_provider(self) -> None:
        actions = [AgentAction(agent="ExecutorAgent", action="apply_patch", duration_ms=10, ok=True)]

        result = run_self_check_loop(
            cycle_id="cycle-strict-elapsed",
            actions=actions,
            post_condition_checks={"tests_pass": lambda: True},
            mutation_score=0.2,
            mutate_threshold=0.3,
            replay_mode="strict",
            elapsed_duration_ms=42,
        )

        self.assertEqual(result.total_duration_ms, 42)
        self.assertEqual(result.decision, "hold")

    def test_adaptive_budget_snapshot_hash_deterministic_for_identical_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "cycle_id": "cycle-deterministic",
                "governance_debt_score": 0.25,
                "fitness_trend_delta": -0.2,
                "epoch_pass_rate": 0.7,
            }
            provider = SeededDeterminismProvider(seed="budget-seed")
            first_engine = AutonomyBudgetEngine(
                snapshot_path=Path(tmp) / "first.jsonl",
                provider=provider,
                replay_mode="strict",
            )
            second_engine = AutonomyBudgetEngine(
                snapshot_path=Path(tmp) / "second.jsonl",
                provider=provider,
                replay_mode="strict",
            )

            first = first_engine.record_snapshot(**payload)
            second = second_engine.record_snapshot(**payload)

            self.assertEqual(first.snapshot_hash, second.snapshot_hash)
            self.assertEqual(first.created_at_ms, second.created_at_ms)

    def test_adaptive_budget_strict_rejects_missing_deterministic_timestamp_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = AutonomyBudgetEngine(
                snapshot_path=Path(tmp) / "strict.jsonl",
                replay_mode="strict",
                provider=SystemDeterminismProvider(),
            )

            with self.assertRaisesRegex(RuntimeError, "deterministic_timestamp_required"):
                engine.record_snapshot(
                    cycle_id="cycle-strict",
                    governance_debt_score=0.4,
                    fitness_trend_delta=0.0,
                    epoch_pass_rate=1.0,
                )

    def test_adaptive_budget_hash_chain_continuity_across_appended_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "continuity.jsonl"
            writer = AutonomyBudgetEngine(
                snapshot_path=snapshot_path,
                provider=SeededDeterminismProvider(seed="chain"),
                replay_mode="strict",
            )
            first = writer.record_snapshot(
                cycle_id="cycle-1",
                governance_debt_score=0.1,
                fitness_trend_delta=0.2,
                epoch_pass_rate=0.9,
            )

            appender = AutonomyBudgetEngine(
                snapshot_path=snapshot_path,
                provider=SeededDeterminismProvider(seed="chain"),
                replay_mode="strict",
            )
            second = appender.record_snapshot(
                cycle_id="cycle-2",
                governance_debt_score=0.3,
                fitness_trend_delta=-0.1,
                epoch_pass_rate=0.95,
            )
            third = appender.record_snapshot(
                cycle_id="cycle-3",
                governance_debt_score=0.5,
                fitness_trend_delta=0.0,
                epoch_pass_rate=0.8,
            )

            self.assertEqual(second.prev_hash, first.snapshot_hash)
            self.assertEqual(third.prev_hash, second.snapshot_hash)


if __name__ == "__main__":
    unittest.main()
