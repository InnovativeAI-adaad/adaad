# SPDX-License-Identifier: Apache-2.0
"""Deterministic persisted personality profile store for innovations wiring."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from runtime.innovations import MutationPersonality


DEFAULT_PERSONALITY_PROFILES: List[MutationPersonality] = [
    MutationPersonality(agent_id="architect", vector=(0.9, 0.2, 0.3, 0.1), philosophy="minimalist"),
    MutationPersonality(agent_id="dream", vector=(0.6, 0.8, 0.4, 0.2), philosophy="exploratory"),
    MutationPersonality(agent_id="beast", vector=(0.5, 0.5, 0.9, 0.8), philosophy="aggressive"),
]


@dataclass(frozen=True)
class PersonaEpochRecord:
    epoch_id: str
    agent_id: str
    philosophy: str
    vector: tuple[float, float, float, float]
    strategy_id: str
    impact_score: float
    outcome: str
    mutation_ids: tuple[str, ...]


class PersonalityProfileStore:
    """File-backed deterministic profile store rooted in ``data/``."""

    def __init__(self, profiles_path: Path | str = "data/personality_profiles.json", records_path: Path | str = "data/persona_epoch_records.jsonl") -> None:
        self._profiles_path = Path(profiles_path)
        self._records_path = Path(records_path)

    def load_profiles(self) -> List[MutationPersonality]:
        state = self._load_state()
        profiles: List[MutationPersonality] = []
        for row in state.get("profiles", []):
            vector = tuple(float(v) for v in row.get("vector", (0.5, 0.5, 0.5, 0.5)))
            if len(vector) != 4:
                vector = (0.5, 0.5, 0.5, 0.5)
            profiles.append(
                MutationPersonality(
                    agent_id=str(row.get("agent_id", "unknown")),
                    philosophy=str(row.get("philosophy", "balanced")),
                    vector=vector,
                )
            )
        return sorted(profiles, key=lambda p: p.agent_id)

    def record_selection(self, *, epoch_id: str, profile: MutationPersonality, strategy_id: str = "") -> None:
        record = PersonaEpochRecord(
            epoch_id=str(epoch_id),
            agent_id=profile.agent_id,
            philosophy=profile.philosophy,
            vector=tuple(float(v) for v in profile.vector),
            strategy_id=str(strategy_id),
            impact_score=0.0,
            outcome="pending",
            mutation_ids=(),
        )
        self._upsert_epoch_record(record)

    def record_impact(self, *, epoch_id: str, active_personality: Mapping[str, Any], fitness_summary: Sequence[tuple[str, float]], mutations_succeeded: Sequence[str]) -> Dict[str, Any]:
        agent_id = str(active_personality.get("agent_id", "")).strip()
        if not agent_id:
            return {}
        profile = self._profile_by_id(agent_id)
        if profile is None:
            return {}

        scores = [float(score) for _, score in fitness_summary]
        impact_score = round(sum(scores) / max(1, len(scores)), 6)
        outcome = "win" if bool(mutations_succeeded) else "loss"
        delta = 0.02 if outcome == "win" else -0.01

        vector_before = tuple(float(v) for v in profile["vector"])
        vector_after = tuple(max(0.0, min(1.0, round(v + delta, 6))) for v in vector_before)

        profile["vector"] = list(vector_after)
        profile["revision"] = int(profile.get("revision", 0)) + 1
        profile["wins"] = int(profile.get("wins", 0)) + (1 if outcome == "win" else 0)
        profile["losses"] = int(profile.get("losses", 0)) + (1 if outcome == "loss" else 0)
        profile["updated_epoch"] = str(epoch_id)

        state = self._load_state()
        state_profiles = {str(p.get("agent_id", "")): p for p in state.get("profiles", [])}
        state_profiles[agent_id] = profile
        state["profiles"] = [state_profiles[k] for k in sorted(state_profiles)]
        history = list(state.get("history", []))
        history.append({
            "epoch_id": str(epoch_id),
            "agent_id": agent_id,
            "philosophy": str(profile.get("philosophy", "")),
            "outcome": outcome,
            "impact_score": impact_score,
            "vector_before": list(vector_before),
            "vector_after": list(vector_after),
        })
        state["history"] = history[-250:]
        self._save_state(state)

        record = PersonaEpochRecord(
            epoch_id=str(epoch_id),
            agent_id=agent_id,
            philosophy=str(profile.get("philosophy", "")),
            vector=vector_after,
            strategy_id=str(active_personality.get("strategy_id", "")),
            impact_score=impact_score,
            outcome=outcome,
            mutation_ids=tuple(str(m) for m in mutations_succeeded),
        )
        self._upsert_epoch_record(record)
        return {
            "agent_id": agent_id,
            "outcome": outcome,
            "impact_score": impact_score,
            "vector_before": list(vector_before),
            "vector_after": list(vector_after),
            "wins": profile["wins"],
            "losses": profile["losses"],
            "revision": profile["revision"],
        }

    def snapshot(self) -> Dict[str, Any]:
        state = self._load_state()
        state["profiles"] = sorted(state.get("profiles", []), key=lambda p: str(p.get("agent_id", "")))
        return state

    def _profile_by_id(self, agent_id: str) -> Dict[str, Any] | None:
        state = self._load_state()
        for row in state.get("profiles", []):
            if str(row.get("agent_id", "")) == agent_id:
                return dict(row)
        return None

    def _load_state(self) -> Dict[str, Any]:
        if not self._profiles_path.exists():
            return self._default_state()
        try:
            raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return self._default_state()
            raw.setdefault("profiles", self._default_state()["profiles"])
            raw.setdefault("history", [])
            return raw
        except Exception:  # noqa: BLE001
            return self._default_state()

    def _save_state(self, state: Mapping[str, Any]) -> None:
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    def _default_state(self) -> Dict[str, Any]:
        return {
            "schema_version": "v1",
            "profiles": [
                {
                    "agent_id": p.agent_id,
                    "philosophy": p.philosophy,
                    "vector": list(p.vector),
                    "revision": 0,
                    "wins": 0,
                    "losses": 0,
                    "updated_epoch": "",
                }
                for p in sorted(DEFAULT_PERSONALITY_PROFILES, key=lambda x: x.agent_id)
            ],
            "history": [],
        }

    def _upsert_epoch_record(self, record: PersonaEpochRecord) -> None:
        self._records_path.parent.mkdir(parents=True, exist_ok=True)
        existing: Dict[str, Dict[str, Any]] = {}
        if self._records_path.exists():
            for line in self._records_path.read_text(encoding="utf-8").splitlines():
                row = line.strip()
                if not row:
                    continue
                try:
                    data = json.loads(row)
                    key = str(data.get("epoch_id", ""))
                    if key:
                        existing[key] = data
                except Exception:  # noqa: BLE001
                    continue
        existing[record.epoch_id] = {
            "epoch_id": record.epoch_id,
            "agent_id": record.agent_id,
            "philosophy": record.philosophy,
            "vector": list(record.vector),
            "strategy_id": record.strategy_id,
            "impact_score": record.impact_score,
            "outcome": record.outcome,
            "mutation_ids": list(record.mutation_ids),
        }
        lines = [json.dumps(existing[k], sort_keys=True) for k in sorted(existing)]
        self._records_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = [
    "DEFAULT_PERSONALITY_PROFILES",
    "PersonaEpochRecord",
    "PersonalityProfileStore",
]
