# SPDX-License-Identifier: Apache-2.0
"""Innovation #16 — Emergent Role Specialization.
Roles emerge from observed behavior patterns, not assignments.
"""
from __future__ import annotations
import json, math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

SPECIALIZATION_WINDOW: int = 50
SPECIALIZATION_THRESHOLD: float = 0.65  # dominance in a category

@dataclass
class EmergentRole:
    agent_id: str
    discovered_role: str         # e.g. "structural_architect", "risk_explorer"
    dominant_target_type: str
    dominant_strategy: str
    risk_preference: float       # 0=conservative, 1=aggressive
    consistency_score: float
    epochs_observed: int

@dataclass
class AgentBehaviorProfile:
    agent_id: str
    target_type_counts: dict[str, int] = field(default_factory=dict)
    strategy_counts: dict[str, int] = field(default_factory=dict)
    risk_scores: list[float] = field(default_factory=list)
    fitness_deltas: list[float] = field(default_factory=list)
    epochs_active: int = 0

    def record_action(self, target_type: str, strategy: str,
                       risk_score: float, fitness_delta: float) -> None:
        self.target_type_counts[target_type] = self.target_type_counts.get(target_type, 0) + 1
        self.strategy_counts[strategy] = self.strategy_counts.get(strategy, 0) + 1
        self.risk_scores.append(risk_score)
        self.fitness_deltas.append(fitness_delta)
        self.epochs_active += 1

    @property
    def dominant_target(self) -> str:
        if not self.target_type_counts:
            return "unknown"
        return max(self.target_type_counts, key=self.target_type_counts.get)

    @property
    def dominant_strategy(self) -> str:
        if not self.strategy_counts:
            return "unknown"
        return max(self.strategy_counts, key=self.strategy_counts.get)

    @property
    def avg_risk(self) -> float:
        return sum(self.risk_scores) / len(self.risk_scores) if self.risk_scores else 0.5

    @property
    def specialization_score(self) -> float:
        if not self.target_type_counts:
            return 0.0
        total = sum(self.target_type_counts.values())
        max_count = max(self.target_type_counts.values())
        return max_count / total if total > 0 else 0.0


ROLE_ARCHETYPES = {
    "structural_architect": {"strategy": "structural_refactor", "risk": (0.0, 0.4)},
    "test_coverage_guardian": {"strategy": "test_coverage_expansion", "risk": (0.0, 0.5)},
    "performance_optimizer": {"strategy": "performance_optimization", "risk": (0.3, 0.7)},
    "safety_hardener": {"strategy": "safety_hardening", "risk": (0.0, 0.3)},
    "adaptive_explorer": {"strategy": "adaptive_self_mutate", "risk": (0.4, 1.0)},
}


class EmergentRoleSpecializer:
    """Discovers agent roles from behavioral patterns."""

    def __init__(self, state_path: Path = Path("data/emergent_roles.json")):
        self.state_path = Path(state_path)
        self._profiles: dict[str, AgentBehaviorProfile] = {}
        self._discovered_roles: dict[str, EmergentRole] = {}
        self._load()

    def record_behavior(self, agent_id: str, target_type: str,
                          strategy: str, risk_score: float,
                          fitness_delta: float) -> None:
        if agent_id not in self._profiles:
            self._profiles[agent_id] = AgentBehaviorProfile(agent_id=agent_id)
        self._profiles[agent_id].record_action(target_type, strategy,
                                                 risk_score, fitness_delta)

    def discover_roles(self) -> dict[str, EmergentRole]:
        """Cluster agents into discovered roles based on behavior."""
        newly_discovered = {}
        for agent_id, profile in self._profiles.items():
            if profile.epochs_active < SPECIALIZATION_WINDOW:
                continue
            if profile.specialization_score < SPECIALIZATION_THRESHOLD:
                continue
            role = self._classify_role(profile)
            newly_discovered[agent_id] = role
            self._discovered_roles[agent_id] = role
        self._save()
        return newly_discovered

    def _classify_role(self, profile: AgentBehaviorProfile) -> EmergentRole:
        dom_strategy = profile.dominant_strategy
        avg_risk = profile.avg_risk
        role_name = "undifferentiated"
        for archetype, criteria in ROLE_ARCHETYPES.items():
            risk_min, risk_max = criteria["risk"]
            if (criteria["strategy"] in dom_strategy and
                    risk_min <= avg_risk <= risk_max):
                role_name = archetype
                break
        if role_name == "undifferentiated":
            role_name = f"emergent_{dom_strategy[:15]}"

        return EmergentRole(
            agent_id=profile.agent_id,
            discovered_role=role_name,
            dominant_target_type=profile.dominant_target,
            dominant_strategy=dom_strategy,
            risk_preference=round(avg_risk, 3),
            consistency_score=round(profile.specialization_score, 4),
            epochs_observed=profile.epochs_active,
        )

    def get_role(self, agent_id: str) -> EmergentRole | None:
        return self._discovered_roles.get(agent_id)

    def _load(self) -> None:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                for k, v in data.get("profiles", {}).items():
                    self._profiles[k] = AgentBehaviorProfile(**v)
            except Exception:
                pass

    def _save(self) -> None:
        import dataclasses
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({
            "profiles": {k: dataclasses.asdict(v) for k, v in self._profiles.items()},
            "discovered_roles": {k: dataclasses.asdict(v)
                                  for k, v in self._discovered_roles.items()},
        }, indent=2))


__all__ = ["EmergentRoleSpecializer", "EmergentRole", "AgentBehaviorProfile",
           "ROLE_ARCHETYPES", "SPECIALIZATION_WINDOW"]
