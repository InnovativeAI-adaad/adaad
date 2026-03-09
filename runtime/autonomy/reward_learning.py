# SPDX-License-Identifier: Apache-2.0
"""Reward schema, offline evaluation, and guarded learning promotion utilities."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from runtime.timeutils import now_iso

DEFAULT_PROFILE_PATH = Path("data/autonomy_learning_profiles.json")


@dataclass(frozen=True)
class RewardSchema:
    """Composable reward function weighting mutation/governance/replay outcomes."""

    mutation_success_weight: float = 0.45
    governance_pass_weight: float = 0.35
    replay_stability_weight: float = 0.20

    def total(self) -> float:
        return (
            float(self.mutation_success_weight)
            + float(self.governance_pass_weight)
            + float(self.replay_stability_weight)
        )


@dataclass(frozen=True)
class LearningObservation:
    """Normalized outcome observation used by the learning controls."""

    mutation_id: str
    accepted: bool
    governance_passed: bool
    replay_stable: bool
    reward_score: float
    replay_stability_score: float
    source_event_id: str = ""


@dataclass(frozen=True)
class PromotionEvaluation:
    """Computed metrics for deciding learning parameter promotions."""

    accepted_count: int
    total_count: int
    acceptance_rate: float
    replay_stability_rate: float
    avg_reward: float


@dataclass(frozen=True)
class PromotionDecision:
    """Result of guarded promotion policy checks."""

    promote: bool
    rollback: bool
    reason: str
    evaluated: PromotionEvaluation


@dataclass(frozen=True)
class ModelProfileVersion:
    """Persisted learning profile and version metadata for auditability."""

    version_id: str
    created_at: str
    parameters: dict[str, float]
    schema: RewardSchema
    parent_version_id: str | None = None


@dataclass(frozen=True)
class MutationDecisionAudit:
    """Decision annotation with attached model/profile version IDs."""

    mutation_id: str
    accepted: bool
    model_version_id: str
    profile_version_id: str
    reward_score: float
    recorded_at: str


class RewardOutcomeIngestor:
    """Ingest mutation/governance/replay events into normalized observations."""

    def __init__(self, schema: RewardSchema | None = None) -> None:
        self._schema = schema or RewardSchema()

    @property
    def schema(self) -> RewardSchema:
        return self._schema

    def ingest(self, event: Mapping[str, Any]) -> LearningObservation:
        payload = event.get("payload", event)
        if not isinstance(payload, Mapping):
            payload = {}
        mutation_id = str(payload.get("mutation_id") or event.get("mutation_id") or "unknown")
        accepted = bool(payload.get("accepted", False))
        governance_passed = bool(
            payload.get("governance_passed", payload.get("governance_ok", False))
        )
        replay_stable = bool(payload.get("replay_stable", payload.get("replay_ok", False)))

        reward = self._reward(accepted=accepted, governance_passed=governance_passed, replay_stable=replay_stable)
        event_id = str(event.get("event_id") or event.get("id") or "")

        return LearningObservation(
            mutation_id=mutation_id,
            accepted=accepted,
            governance_passed=governance_passed,
            replay_stable=replay_stable,
            reward_score=reward,
            replay_stability_score=1.0 if replay_stable else 0.0,
            source_event_id=event_id,
        )

    def _reward(self, *, accepted: bool, governance_passed: bool, replay_stable: bool) -> float:
        weighted = (
            (1.0 if accepted else 0.0) * self._schema.mutation_success_weight
            + (1.0 if governance_passed else 0.0) * self._schema.governance_pass_weight
            + (1.0 if replay_stable else 0.0) * self._schema.replay_stability_weight
        )
        total = self._schema.total()
        if total <= 0.0:
            return 0.0
        return round(weighted / total, 6)


class OfflinePolicyEvaluator:
    """Replay historical ledger events and score candidate policy updates."""

    def __init__(self, ingestor: RewardOutcomeIngestor | None = None) -> None:
        self._ingestor = ingestor or RewardOutcomeIngestor()

    def replay_historical_events(self, events: Iterable[Mapping[str, Any]]) -> PromotionEvaluation:
        observations = [self._ingestor.ingest(event) for event in events]
        return self._summarize(observations)

    @staticmethod
    def _summarize(observations: list[LearningObservation]) -> PromotionEvaluation:
        if not observations:
            return PromotionEvaluation(
                accepted_count=0,
                total_count=0,
                acceptance_rate=0.0,
                replay_stability_rate=0.0,
                avg_reward=0.0,
            )
        total = len(observations)
        accepted_count = sum(1 for obs in observations if obs.accepted)
        replay_stable_count = sum(1 for obs in observations if obs.replay_stable)
        avg_reward = sum(obs.reward_score for obs in observations) / total
        return PromotionEvaluation(
            accepted_count=accepted_count,
            total_count=total,
            acceptance_rate=round(accepted_count / total, 6),
            replay_stability_rate=round(replay_stable_count / total, 6),
            avg_reward=round(avg_reward, 6),
        )


class GuardedPromotionPolicy:
    """Promotion guardrails with rollback triggers on key regressions."""

    def __init__(
        self,
        *,
        max_acceptance_rate_regression: float = 0.05,
        max_replay_stability_regression: float = 0.02,
        min_avg_reward: float = 0.55,
    ) -> None:
        self._acceptance_regression = max(0.0, float(max_acceptance_rate_regression))
        self._replay_regression = max(0.0, float(max_replay_stability_regression))
        self._min_avg_reward = min(1.0, max(0.0, float(min_avg_reward)))

    def evaluate(self, baseline: PromotionEvaluation, candidate: PromotionEvaluation) -> PromotionDecision:
        acceptance_drop = baseline.acceptance_rate - candidate.acceptance_rate
        replay_drop = baseline.replay_stability_rate - candidate.replay_stability_rate

        if acceptance_drop > self._acceptance_regression:
            return PromotionDecision(
                promote=False,
                rollback=True,
                reason=(
                    "acceptance_rate_regression:"
                    f"drop={acceptance_drop:.4f}>allowed={self._acceptance_regression:.4f}"
                ),
                evaluated=candidate,
            )

        if replay_drop > self._replay_regression:
            return PromotionDecision(
                promote=False,
                rollback=True,
                reason=(
                    "replay_stability_regression:"
                    f"drop={replay_drop:.4f}>allowed={self._replay_regression:.4f}"
                ),
                evaluated=candidate,
            )

        if candidate.avg_reward < self._min_avg_reward:
            return PromotionDecision(
                promote=False,
                rollback=False,
                reason=(
                    "avg_reward_below_floor:"
                    f"reward={candidate.avg_reward:.4f}<floor={self._min_avg_reward:.4f}"
                ),
                evaluated=candidate,
            )

        return PromotionDecision(
            promote=True,
            rollback=False,
            reason="promotion_authorized",
            evaluated=candidate,
        )


class LearningProfileRegistry:
    """Persistent profile/model versioning and decision-level audit attachments."""

    def __init__(self, state_path: Path = DEFAULT_PROFILE_PATH) -> None:
        self._path = state_path
        self._state = self._load_state()

    def register_profile(
        self,
        *,
        parameters: Mapping[str, float],
        schema: RewardSchema,
        parent_version_id: str | None = None,
    ) -> ModelProfileVersion:
        payload = {key: float(value) for key, value in dict(parameters).items()}
        version_id = self._derive_version_id(payload, schema)
        profile = ModelProfileVersion(
            version_id=version_id,
            created_at=now_iso(),
            parameters=payload,
            schema=schema,
            parent_version_id=parent_version_id,
        )
        self._state.setdefault("profiles", []).append(asdict(profile))
        self._save_state()
        return profile

    def attach_version_to_mutation_decision(
        self,
        *,
        mutation_id: str,
        accepted: bool,
        reward_score: float,
        model_version_id: str,
        profile_version_id: str,
    ) -> MutationDecisionAudit:
        decision = MutationDecisionAudit(
            mutation_id=str(mutation_id),
            accepted=bool(accepted),
            model_version_id=str(model_version_id),
            profile_version_id=str(profile_version_id),
            reward_score=float(reward_score),
            recorded_at=now_iso(),
        )
        self._state.setdefault("decisions", []).append(asdict(decision))
        self._save_state()
        return decision

    def latest_profile(self) -> ModelProfileVersion | None:
        profiles = self._state.get("profiles", [])
        if not profiles:
            return None
        latest = profiles[-1]
        schema_dict = latest.get("schema", {})
        return ModelProfileVersion(
            version_id=str(latest.get("version_id") or ""),
            created_at=str(latest.get("created_at") or ""),
            parameters={k: float(v) for k, v in dict(latest.get("parameters", {})).items()},
            schema=RewardSchema(
                mutation_success_weight=float(schema_dict.get("mutation_success_weight", 0.45)),
                governance_pass_weight=float(schema_dict.get("governance_pass_weight", 0.35)),
                replay_stability_weight=float(schema_dict.get("replay_stability_weight", 0.20)),
            ),
            parent_version_id=latest.get("parent_version_id"),
        )

    def _derive_version_id(self, parameters: Mapping[str, float], schema: RewardSchema) -> str:
        canonical = {
            "parameters": {k: parameters[k] for k in sorted(parameters)},
            "schema": asdict(schema),
        }
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return f"profile-{digest[:16]}"

    def _load_state(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"profiles": [], "decisions": []}
        try:
            loaded = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError, TypeError):
            return {"profiles": [], "decisions": []}
        if not isinstance(loaded, dict):
            return {"profiles": [], "decisions": []}
        loaded.setdefault("profiles", [])
        loaded.setdefault("decisions", [])
        return loaded

    def _save_state(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._state, indent=2, sort_keys=True))


# Ring buffer size used by RewardSignalBridge — exported here for cross-module
# imports (PR-10-02 PolicyPromotionController tests reference this constant).
OBSERVATION_RING_BUFFER_SIZE: int = 20

__all__ = [
    "GuardedPromotionPolicy",
    "LearningObservation",
    "LearningProfileRegistry",
    "ModelProfileVersion",
    "MutationDecisionAudit",
    "OBSERVATION_RING_BUFFER_SIZE",
    "OfflinePolicyEvaluator",
    "PromotionDecision",
    "PromotionEvaluation",
    "RewardOutcomeIngestor",
    "RewardSchema",
]
