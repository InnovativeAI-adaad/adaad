# SPDX-License-Identifier: Apache-2.0
"""Tests for reward ingestion, offline replay evaluation, and guarded promotion."""

from __future__ import annotations

from runtime.autonomy.reward_learning import (
    GuardedPromotionPolicy,
    LearningProfileRegistry,
    OfflinePolicyEvaluator,
    RewardOutcomeIngestor,
    RewardSchema,
)


def test_reward_outcome_ingestion_combines_signals() -> None:
    ingestor = RewardOutcomeIngestor(
        RewardSchema(
            mutation_success_weight=0.5,
            governance_pass_weight=0.3,
            replay_stability_weight=0.2,
        )
    )
    observation = ingestor.ingest(
        {
            "event_id": "evt-1",
            "payload": {
                "mutation_id": "mut-1",
                "accepted": True,
                "governance_passed": True,
                "replay_stable": False,
            },
        }
    )

    assert observation.mutation_id == "mut-1"
    assert observation.reward_score == 0.8
    assert observation.replay_stability_score == 0.0


def test_offline_policy_evaluator_replays_historical_events() -> None:
    evaluator = OfflinePolicyEvaluator()
    evaluation = evaluator.replay_historical_events(
        [
            {"payload": {"mutation_id": "a", "accepted": True, "governance_passed": True, "replay_stable": True}},
            {"payload": {"mutation_id": "b", "accepted": False, "governance_passed": True, "replay_stable": True}},
            {"payload": {"mutation_id": "c", "accepted": True, "governance_passed": False, "replay_stable": False}},
        ]
    )

    assert evaluation.total_count == 3
    assert evaluation.accepted_count == 2
    assert evaluation.acceptance_rate == 0.666667
    assert evaluation.replay_stability_rate == 0.666667


def test_guarded_promotion_rolls_back_on_replay_regression() -> None:
    evaluator = OfflinePolicyEvaluator()
    baseline = evaluator.replay_historical_events(
        [
            {"payload": {"mutation_id": "a", "accepted": True, "governance_passed": True, "replay_stable": True}},
            {"payload": {"mutation_id": "b", "accepted": True, "governance_passed": True, "replay_stable": True}},
        ]
    )
    candidate = evaluator.replay_historical_events(
        [
            {"payload": {"mutation_id": "a", "accepted": True, "governance_passed": True, "replay_stable": True}},
            {"payload": {"mutation_id": "b", "accepted": True, "governance_passed": True, "replay_stable": False}},
        ]
    )

    policy = GuardedPromotionPolicy(max_replay_stability_regression=0.1)
    decision = policy.evaluate(baseline=baseline, candidate=candidate)

    assert decision.promote is False
    assert decision.rollback is True
    assert decision.reason.startswith("replay_stability_regression")


def test_profile_registry_persists_versions_and_decision_audit(tmp_path) -> None:
    registry = LearningProfileRegistry(state_path=tmp_path / "profiles.json")

    profile = registry.register_profile(
        parameters={"learning_rate": 0.03, "momentum": 0.82},
        schema=RewardSchema(),
    )
    decision = registry.attach_version_to_mutation_decision(
        mutation_id="mut-88",
        accepted=True,
        reward_score=0.91,
        model_version_id="model-3",
        profile_version_id=profile.version_id,
    )

    assert profile.version_id.startswith("profile-")
    assert decision.profile_version_id == profile.version_id

    reloaded = LearningProfileRegistry(state_path=tmp_path / "profiles.json")
    latest = reloaded.latest_profile()
    assert latest is not None
    assert latest.version_id == profile.version_id
