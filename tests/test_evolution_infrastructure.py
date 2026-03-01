# SPDX-License-Identifier: Apache-2.0

from runtime.evolution.entropy_discipline import (
    EntropyBudget,
    deterministic_context,
    deterministic_token,
    deterministic_token_with_budget
)
from runtime.evolution.fitness import FitnessEvaluator
from runtime.evolution.replay_mode import ReplayMode, normalize_replay_mode, parse_replay_args
from runtime.recovery.tier_manager import RecoveryPolicy, RecoveryTierLevel, TierManager


def test_entropy_budget_consumption_is_immutable() -> None:
    budget = EntropyBudget()
    updated = budget.consume("random")
    assert budget.random_samples == 0
    assert updated.random_samples == 1


def test_entropy_deterministic_context_rules() -> None:
    assert deterministic_context(replay_mode="strict", recovery_tier="none")
    assert deterministic_context(replay_mode="off", recovery_tier="governance")
    assert deterministic_context(replay_mode="off", recovery_tier="none")


def test_deterministic_token_stability() -> None:
    t1 = deterministic_token(epoch_id="epoch-1", bundle_id="b1", agent_id="a1")
    t2 = deterministic_token(epoch_id="epoch-1", bundle_id="b1", agent_id="a1")
    t3 = deterministic_token(epoch_id="epoch-1", bundle_id="b2", agent_id="a1")
    assert t1 == t2
    assert t1 != t3


def test_deterministic_token_with_budget_consumes_random_sample() -> None:
    token, budget = deterministic_token_with_budget("seed", "ctx", budget=EntropyBudget())
    assert isinstance(token, int)
    assert budget.random_samples == 1



def test_fitness_evaluator_basic_paths() -> None:
    evaluator = FitnessEvaluator()
    bad = evaluator.evaluate_content("def broken(")
    assert not bad.passed_syntax
    good = evaluator.evaluate_content("mutation: candidate", constitution_ok=True)
    assert good.passed_syntax


def test_replay_mode_normalization_and_properties() -> None:
    assert normalize_replay_mode(True) == ReplayMode.AUDIT
    assert normalize_replay_mode("full") == ReplayMode.AUDIT
    assert normalize_replay_mode("strict") == ReplayMode.STRICT
    assert ReplayMode.STRICT.fail_closed
    assert ReplayMode.AUDIT.should_verify
    assert not ReplayMode.OFF.should_verify


def test_parse_replay_args_contract() -> None:
    assert parse_replay_args("audit", "epoch-1") == (ReplayMode.AUDIT, "epoch-1")
    assert parse_replay_args(False) == (ReplayMode.OFF, "")
    assert parse_replay_args(None) == (ReplayMode.OFF, "")


def test_recovery_policy_and_ordering() -> None:
    assert RecoveryTierLevel.NONE < RecoveryTierLevel.ADVISORY
    assert RecoveryTierLevel.CRITICAL > RecoveryTierLevel.CONSERVATIVE
    critical = RecoveryPolicy.for_tier(RecoveryTierLevel.CRITICAL)
    assert critical.fail_close
    assert not critical.allow_web_fetch


def test_tier_manager_escalation_signals() -> None:
    manager = TierManager()
    manager.record_governance_violation()
    manager.record_governance_violation()
    manager.record_governance_violation()
    assert manager.evaluate_tier() == RecoveryTierLevel.GOVERNANCE


def test_tier_manager_deescalates_only_after_recovery_window() -> None:
    manager = TierManager(violation_window_seconds=3600, recovery_window_seconds=60)
    manager.apply_tier(RecoveryTierLevel.GOVERNANCE, "seed")
    manager.tier_history[-1] = manager.tier_history[-1].__class__(
        timestamp=manager.tier_history[-1].timestamp - 120,
        from_tier=manager.tier_history[-1].from_tier,
        to_tier=manager.tier_history[-1].to_tier,
        reason=manager.tier_history[-1].reason,
        metrics_snapshot=manager.tier_history[-1].metrics_snapshot,
    )
    manager.auto_evaluate_and_apply("auto")
    assert manager.current_tier == RecoveryTierLevel.NONE


def test_tier_manager_does_not_deescalate_before_recovery_window() -> None:
    manager = TierManager(violation_window_seconds=3600, recovery_window_seconds=10_000)
    manager.apply_tier(RecoveryTierLevel.GOVERNANCE, "seed")
    manager.auto_evaluate_and_apply("auto")
    assert manager.current_tier == RecoveryTierLevel.GOVERNANCE
