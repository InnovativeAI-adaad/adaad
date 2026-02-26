# SPDX-License-Identifier: Apache-2.0
"""Autonomy enhancement modules for role contracts, loops, and scoring."""

from .adaptive_budget import AutonomyBudgetEngine, AutonomyBudgetSnapshot
from .loop import AGMCycleResult, AGMStep, AGMStepInput, AGMStepOutput, AutonomyLoopResult, run_agm_cycle, run_self_check_loop
from .mutation_scaffold import MutationCandidate, rank_mutation_candidates
from .roles import AgentRoleSpec, SandboxPermission, default_role_specs
from .scoreboard import build_scoreboard_views

__all__ = [
    "AgentRoleSpec",
    "AutonomyBudgetEngine",
    "AutonomyBudgetSnapshot",
    "AGMCycleResult",
    "AGMStep",
    "AGMStepInput",
    "AGMStepOutput",
    "AutonomyLoopResult",
    "MutationCandidate",
    "SandboxPermission",
    "build_scoreboard_views",
    "default_role_specs",
    "rank_mutation_candidates",
    "run_agm_cycle",
    "run_self_check_loop",
]
