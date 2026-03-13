# SPDX-License-Identifier: Apache-2.0
"""Phase 62 adapter for canonical fitness signal input materialization."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping


PHASE62_ALGORITHM_VERSION = "phase62.v1"
LEGACY_ALGORITHM_VERSION = "legacy.v1"
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class FitnessSignalInput:
    """Narrow, deterministic scoring input contract for Phase 62."""

    epoch_id: str
    mutation_tier: str
    correctness_score: float
    efficiency_score: float
    policy_compliance_score: float
    goal_alignment_score: float
    simulated_market_score: float
    divergence_rejected: bool
    algorithm_version: str


def phase62_fitness_adapter_enabled() -> bool:
    """Return True when the Phase 62 adapter scoring path is enabled."""

    return os.getenv("ADAAD_PHASE62_FITNESS_ADAPTER", "").strip().lower() in _TRUTHY


def adapt_context_to_fitness_signal_input(context: Mapping[str, Any]) -> FitnessSignalInput:
    """Project mutable context dicts to the canonical FitnessSignalInput contract."""

    epoch_id = str(context.get("epoch_id") or "").strip()
    if not epoch_id:
        raise ValueError("fitness_context_missing_epoch_id")

    tier = str(context.get("mutation_tier") or "").strip().lower()
    if not tier:
        tier = "low"

    adapter_enabled = phase62_fitness_adapter_enabled()
    algorithm_version = PHASE62_ALGORITHM_VERSION if adapter_enabled else LEGACY_ALGORITHM_VERSION
    divergence_rejected = bool(context.get("replay_divergence") or context.get("divergence_rejected")) if adapter_enabled else False

    return FitnessSignalInput(
        epoch_id=epoch_id,
        mutation_tier=tier,
        correctness_score=_clamp(context.get("correctness_score", 0.0)),
        efficiency_score=_clamp(context.get("efficiency_score", 0.0)),
        policy_compliance_score=_clamp(context.get("policy_compliance_score", 0.0)),
        goal_alignment_score=_clamp(context.get("goal_alignment_score", 0.0)),
        simulated_market_score=_clamp(context.get("simulated_market_score", 0.0)),
        divergence_rejected=divergence_rejected,
        algorithm_version=algorithm_version,
    )


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "FitnessSignalInput",
    "PHASE62_ALGORITHM_VERSION",
    "LEGACY_ALGORITHM_VERSION",
    "phase62_fitness_adapter_enabled",
    "adapt_context_to_fitness_signal_input",
]

