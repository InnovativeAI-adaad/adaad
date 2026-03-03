# SPDX-License-Identifier: Apache-2.0
"""Runtime facade for mutation execution dependencies."""

from runtime import ROOT_DIR, metrics
from runtime.analysis.impact_predictor import ImpactPredictor
from runtime.evolution import EvolutionRuntime
from runtime.evolution.entropy_detector import detect_entropy_metadata, observed_entropy_from_telemetry
from runtime.evolution.entropy_discipline import deterministic_context, deterministic_id
from runtime.evolution.entropy_policy import EntropyPolicy, enforce_entropy_policy
from runtime.evolution.fitness_orchestrator import FitnessOrchestrator
from runtime.evolution.goal_graph import GoalGraph
from runtime.evolution.promotion_events import create_promotion_event
from runtime.evolution.promotion_policy import PromotionPolicyEngine
from runtime.evolution.promotion_state_machine import PromotionState, require_transition
from runtime.governance.mutation_risk_scorer import MutationRiskScorer
from runtime.governance.foundation import RuntimeDeterminismProvider, default_provider, require_replay_safe_provider
from runtime.invariants import verify_all
from runtime.manifest.generator import generate_manifest, write_manifest
from runtime.mutation_lifecycle import LifecycleTransitionError, MutationLifecycleContext, transition as lifecycle_transition
from runtime.sandbox.executor import HardenedSandboxExecutor
from runtime.test_sandbox import TestSandbox, TestSandboxResult, TestSandboxStatus
from runtime.timeutils import now_iso
from runtime.tools.mutation_tx import MutationTargetError, MutationTransaction

__all__ = [
    "EntropyPolicy",
    "EvolutionRuntime",
    "FitnessOrchestrator",
    "GoalGraph",
    "HardenedSandboxExecutor",
    "ImpactPredictor",
    "LifecycleTransitionError",
    "MutationLifecycleContext",
    "MutationTargetError",
    "MutationTransaction",
    "PromotionPolicyEngine",
    "PromotionState",
    "MutationRiskScorer",
    "ROOT_DIR",
    "RuntimeDeterminismProvider",
    "TestSandbox",
    "TestSandboxResult",
    "TestSandboxStatus",
    "create_promotion_event",
    "default_provider",
    "detect_entropy_metadata",
    "deterministic_context",
    "deterministic_id",
    "enforce_entropy_policy",
    "generate_manifest",
    "lifecycle_transition",
    "metrics",
    "now_iso",
    "observed_entropy_from_telemetry",
    "require_replay_safe_provider",
    "require_transition",
    "verify_all",
    "write_manifest",
]
