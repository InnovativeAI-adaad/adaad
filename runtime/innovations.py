# SPDX-License-Identifier: Apache-2.0
"""ADAAD-native innovation substrate.

This module introduces deterministic, governance-safe primitives for:
- Capability Seeds
- Vision Mode forecasting
- Mutation Personalities
- Self-Reflective Epochs
- Human-in-the-loop Rituals
- ADAAD Oracle queries over historical events
- Governance plugin execution

Design goals:
- Pure data-in/data-out functions where possible
- Deterministic output ordering
- No direct file IO, network IO, or non-deterministic entropy
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any, Iterable, Mapping, Sequence

from runtime.governance.simulation.epoch_simulator import build_innovation_forecast


@dataclass(frozen=True)
class CapabilitySeed:
    """Human-authored intent seed for evolutionary expansion."""

    seed_id: str
    intent: str
    scaffold: str
    author: str
    lane: str

    def lineage_digest(self) -> str:
        payload = {
            "author": self.author,
            "intent": self.intent,
            "lane": self.lane,
            "scaffold": self.scaffold,
            "seed_id": self.seed_id,
        }
        canonical = str(sorted(payload.items())).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class VisionProjection:
    """Forecast output for Dream -> Vision mode."""

    horizon_epochs: int
    projected_capabilities: tuple[str, ...]
    trajectory_score: float
    dead_end_paths: tuple[str, ...]
    capability_graph_deltas: tuple[dict[str, Any], ...] = ()
    trajectory_bands: dict[str, float] | None = None
    dead_end_diagnostics: tuple[dict[str, str], ...] = ()
    confidence_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class MutationPersonality:
    """Persistent mutation philosophy profile."""

    agent_id: str
    vector: tuple[float, float, float, float]
    philosophy: str


@dataclass(frozen=True)
class ReflectionReport:
    """Meta-evolution snapshot produced every cadence window."""

    epoch_id: str
    dominant_agent: str
    underperforming_agent: str
    rebalance_hint: str


@dataclass(frozen=True)
class RitualEvent:
    """Human-in-the-loop ceremonial checkpoint."""

    ritual_type: str
    epoch_id: str
    summary: str
    approved: bool


@dataclass(frozen=True)
class PluginRuleResult:
    """Deterministic post-constitution plugin evaluation result."""

    plugin_id: str
    passed: bool
    message: str


class GovernancePlugin:
    """Simple deterministic governance plugin protocol."""

    plugin_id: str = "plugin.unknown"

    def evaluate(self, mutation: Mapping[str, Any]) -> PluginRuleResult:
        raise NotImplementedError


class NoNewDependenciesPlugin(GovernancePlugin):
    plugin_id = "gplugin.no_new_dependencies.v1"

    def evaluate(self, mutation: Mapping[str, Any]) -> PluginRuleResult:
        deps = mutation.get("new_dependencies", [])
        passed = not bool(deps)
        return PluginRuleResult(
            plugin_id=self.plugin_id,
            passed=passed,
            message="no new dependencies" if passed else f"blocked dependencies: {deps}",
        )


class DocstringRequiredPlugin(GovernancePlugin):
    plugin_id = "gplugin.docstring_required.v1"

    def evaluate(self, mutation: Mapping[str, Any]) -> PluginRuleResult:
        missing = mutation.get("missing_docstrings", 0)
        passed = int(missing) == 0
        return PluginRuleResult(
            plugin_id=self.plugin_id,
            passed=passed,
            message="docstring coverage complete" if passed else f"missing_docstrings={missing}",
        )


class ADAADInnovationEngine:
    """Coordinator for deterministic innovation features."""

    def evolve_seed(self, seed: CapabilitySeed, epochs: int) -> dict[str, Any]:
        bounded_epochs = max(1, min(int(epochs), 200))
        expansion_score = round(min(1.0, 0.15 + (bounded_epochs * 0.0045)), 4)
        return {
            "seed_id": seed.seed_id,
            "lineage_digest": seed.lineage_digest(),
            "epochs": bounded_epochs,
            "expansion_score": expansion_score,
            "status": "ready_for_governance_gate",
        }

    def run_vision_mode(
        self,
        events: Sequence[Mapping[str, Any]],
        horizon_epochs: int,
        seed_input: str = "vision-default",
    ) -> VisionProjection:
        forecast = build_innovation_forecast(events, horizon_epochs=horizon_epochs, seed_input=seed_input)
        capabilities = [row["capability"] for row in forecast["capability_graph_deltas"] if row.get("capability")]
        dead_end_paths = [row["path_id"] for row in forecast["dead_end_paths"] if row.get("path_id")]
        bands = forecast["trajectory_bands"]
        return VisionProjection(
            horizon_epochs=forecast["horizon_epochs"],
            projected_capabilities=tuple(capabilities[:64]),
            trajectory_score=float(bands.get("base", 0.0)),
            dead_end_paths=tuple(dead_end_paths[:32]),
            capability_graph_deltas=tuple(forecast["capability_graph_deltas"]),
            trajectory_bands=dict(bands),
            dead_end_diagnostics=tuple(forecast["dead_end_paths"]),
            confidence_metadata=dict(forecast["confidence_metadata"]),
        )

    def select_personality(self, profiles: Sequence[MutationPersonality], epoch_id: str) -> MutationPersonality:
        if not profiles:
            raise ValueError("at least one mutation personality profile is required")
        digest = hashlib.sha256(str(epoch_id).encode("utf-8")).hexdigest()
        slot = int(digest[:8], 16) % len(profiles)
        return sorted(profiles, key=lambda p: p.agent_id)[slot]

    def self_reflect(self, epoch_id: str, agent_scores: Mapping[str, float]) -> ReflectionReport:
        if not agent_scores:
            return ReflectionReport(epoch_id=epoch_id, dominant_agent="none", underperforming_agent="none", rebalance_hint="no agent data")
        ranked = sorted(agent_scores.items(), key=lambda item: (item[1], item[0]))
        under = ranked[0][0]
        dom = ranked[-1][0]
        spread = ranked[-1][1] - ranked[0][1]
        hint = "rebalance bandit weights" if spread > 0.2 else "stable distribution"
        return ReflectionReport(epoch_id=epoch_id, dominant_agent=dom, underperforming_agent=under, rebalance_hint=hint)

    def run_plugins(self, mutation: Mapping[str, Any], plugins: Iterable[GovernancePlugin]) -> list[PluginRuleResult]:
        ordered = sorted(plugins, key=lambda p: p.plugin_id)
        return [plugin.evaluate(mutation) for plugin in ordered]

    def answer_oracle(self, question: str, events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        q = question.lower().strip()
        if "divergence" in q:
            rows = [e for e in events if e.get("event_type") == "divergence"][-10:]
            return {"query_type": "divergence_recent", "count": len(rows), "events": rows}
        if "rejected" in q or "reject" in q:
            rows = [e for e in events if e.get("status") == "rejected"][-20:]
            return {"query_type": "rejection_reasoning", "count": len(rows), "events": rows}
        if "contributed" in q or "performance" in q:
            by_agent: dict[str, float] = {}
            for event in events:
                agent = str(event.get("agent_id", "unknown"))
                by_agent[agent] = by_agent.get(agent, 0.0) + float(event.get("fitness_delta", 0.0))
            ranking = sorted(by_agent.items(), key=lambda item: (-item[1], item[0]))
            return {"query_type": "agent_contribution", "ranking": ranking}
        return {"query_type": "generic", "message": "No deterministic oracle template for this question."}

    def story_mode(self, events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        timeline = []
        for row in events:
            timeline.append(
                {
                    "epoch": row.get("epoch_id", ""),
                    "arc": row.get("arc", "core"),
                    "decision": row.get("decision", "none"),
                    "agent": row.get("agent_id", "system"),
                    "outcome": row.get("status", "unknown"),
                }
            )
        return sorted(timeline, key=lambda e: str(e["epoch"]))

    @staticmethod
    def as_serializable(value: Any) -> Any:
        if hasattr(value, "__dataclass_fields__"):
            return asdict(value)
        return value


__all__ = [
    "ADAADInnovationEngine",
    "CapabilitySeed",
    "DocstringRequiredPlugin",
    "GovernancePlugin",
    "MutationPersonality",
    "NoNewDependenciesPlugin",
    "PluginRuleResult",
    "ReflectionReport",
    "RitualEvent",
    "VisionProjection",
]
