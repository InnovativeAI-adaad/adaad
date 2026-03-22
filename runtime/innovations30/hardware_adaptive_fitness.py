# SPDX-License-Identifier: Apache-2.0
"""Innovation #25 — Hardware-Adaptive Fitness.
Fitness weights adjusted to the deployment target hardware profile.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass
class HardwareProfile:
    profile_id: str
    architecture: str         # "arm64" | "x86_64" | "x86"
    ram_mb: int
    is_battery_constrained: bool
    thermal_envelope: str     # "low" | "medium" | "high"
    storage_mb: int

    @classmethod
    def android_minimal(cls) -> "HardwareProfile":
        return cls(profile_id="android-minimal", architecture="arm64",
                   ram_mb=512, is_battery_constrained=True,
                   thermal_envelope="low", storage_mb=1024)

    @classmethod
    def server_standard(cls) -> "HardwareProfile":
        return cls(profile_id="server-standard", architecture="x86_64",
                   ram_mb=8192, is_battery_constrained=False,
                   thermal_envelope="high", storage_mb=102400)

    @classmethod
    def desktop_moderate(cls) -> "HardwareProfile":
        return cls(profile_id="desktop-moderate", architecture="x86_64",
                   ram_mb=2048, is_battery_constrained=False,
                   thermal_envelope="medium", storage_mb=10240)


# Base fitness dimension weights
BASE_WEIGHTS: dict[str, float] = {
    "correctness_score": 0.30,
    "efficiency_score": 0.25,
    "policy_compliance_score": 0.20,
    "goal_alignment_score": 0.15,
    "simulated_market_score": 0.10,
}


class HardwareAdaptiveFitness:
    """Adjusts fitness weights based on deployment hardware profile."""

    def __init__(self, profile: HardwareProfile | None = None):
        self.profile = profile or HardwareProfile.desktop_moderate()

    def adapted_weights(self) -> dict[str, float]:
        weights = dict(BASE_WEIGHTS)

        if self.profile.is_battery_constrained:
            # Memory & efficiency critical on battery devices
            weights["efficiency_score"] *= 1.8
            weights["correctness_score"] *= 1.2
            weights["simulated_market_score"] *= 0.5

        if self.profile.ram_mb < 1024:
            # Memory-constrained: efficiency matters most
            weights["efficiency_score"] *= 2.0
            weights["goal_alignment_score"] *= 0.7

        if self.profile.thermal_envelope == "low":
            # Low thermal budget: penalize compute-heavy mutations
            weights["efficiency_score"] *= 1.5
            weights["policy_compliance_score"] *= 1.3

        if self.profile.architecture == "x86_64" and not self.profile.is_battery_constrained:
            # Server: correctness and compliance most important
            weights["correctness_score"] *= 1.5
            weights["policy_compliance_score"] *= 1.4

        # Renormalize to sum to 1.0
        total = sum(weights.values())
        return {k: round(v / total, 4) for k, v in weights.items()}

    def score_with_profile(self, base_scores: dict[str, float]) -> float:
        weights = self.adapted_weights()
        return round(sum(base_scores.get(k, 0.0) * w
                         for k, w in weights.items()), 4)

    def profile_description(self) -> str:
        return (f"{self.profile.architecture} | {self.profile.ram_mb}MB RAM | "
                f"battery={'yes' if self.profile.is_battery_constrained else 'no'} | "
                f"thermal={self.profile.thermal_envelope}")


__all__ = ["HardwareAdaptiveFitness", "HardwareProfile", "BASE_WEIGHTS"]
