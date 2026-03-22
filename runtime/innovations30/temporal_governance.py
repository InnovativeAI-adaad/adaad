# SPDX-License-Identifier: Apache-2.0
"""Innovation #18 — Temporal Governance Windows.
Rules with activation_conditions on system health state.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class GovernanceWindow:
    rule_name: str
    baseline_severity: str
    high_health_severity: str     # when health > HIGH_HEALTH_THRESHOLD
    low_health_severity: str      # when health < LOW_HEALTH_THRESHOLD
    high_health_threshold: float = 0.85
    low_health_threshold: float = 0.60

    def effective_severity(self, health_score: float) -> str:
        if health_score >= self.high_health_threshold:
            return self.high_health_severity
        elif health_score < self.low_health_threshold:
            return self.low_health_severity
        return self.baseline_severity


# Default temporal windows for existing constitutional rules
DEFAULT_WINDOWS: list[GovernanceWindow] = [
    GovernanceWindow("lineage_continuity", "blocking", "warning", "blocking"),
    GovernanceWindow("single_file_scope", "blocking", "warning", "blocking"),
    GovernanceWindow("ast_validity", "blocking", "blocking", "blocking"),
    GovernanceWindow("entropy_budget", "warning", "advisory", "blocking"),
    GovernanceWindow("replay_determinism", "warning", "advisory", "blocking"),
]


class TemporalGovernanceEngine:
    """Adjusts rule severities based on current system health."""

    def __init__(self, windows: list[GovernanceWindow] | None = None,
                 state_path: Path = Path("data/temporal_governance_state.jsonl")):
        self.windows = {w.rule_name: w for w in (windows or DEFAULT_WINDOWS)}
        self.state_path = Path(state_path)

    def effective_severity(self, rule_name: str, health_score: float) -> str:
        window = self.windows.get(rule_name)
        if window is None:
            return "blocking"  # unknown rule: fail-closed
        return window.effective_severity(health_score)

    def get_adjusted_ruleset(self, health_score: float) -> dict[str, str]:
        """Return {rule_name → effective_severity} for current health."""
        return {name: w.effective_severity(health_score)
                for name, w in self.windows.items()}

    def register_window(self, window: GovernanceWindow) -> None:
        self.windows[window.rule_name] = window

    def log_adjustment(self, epoch_id: str, health_score: float) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "epoch_id": epoch_id,
            "health_score": round(health_score, 4),
            "adjustments": self.get_adjusted_ruleset(health_score),
        }
        with self.state_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


__all__ = ["TemporalGovernanceEngine", "GovernanceWindow", "DEFAULT_WINDOWS"]
