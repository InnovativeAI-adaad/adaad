# SPDX-License-Identifier: Apache-2.0
"""Runtime facade exposing orchestrator-safe runtime services."""

from runtime import metrics
from runtime.boot import BootPreflightService
from runtime.capability_graph import register_capability
from runtime.constitution import (
    CONSTITUTION_VERSION,
    determine_tier,
    deterministic_envelope_scope,
    get_forced_tier,
)
from runtime.element_registry import dump, register
from runtime.evolution import EvolutionRuntime
from runtime.evolution.checkpoint_verifier import CheckpointVerificationError, CheckpointVerifier
from runtime.evolution.lineage_v2 import LineageIntegrityError
from runtime.evolution.replay_attestation import ReplayProofBuilder
from runtime.evolution.replay_mode import ReplayMode, normalize_replay_mode
from runtime.evolution.replay_service import ReplayVerificationService
from runtime.fitness_v2 import score_mutation_enhanced
from runtime.founders_law import (
    RULE_ARCHITECT_SCAN,
    RULE_CONSTITUTION_VERSION,
    RULE_KEY_ROTATION,
    RULE_LEDGER_INTEGRITY,
    RULE_MUTATION_ENGINE,
    RULE_PLATFORM_RESOURCES,
    RULE_WARM_POOL,
    enforce_law,
)
from runtime.governance.foundation import default_provider
from runtime.governance.decision_pipeline import evaluate_mutation_decision as evaluate_mutation
from runtime.manifest.generator import generate_tool_manifest
from runtime.mcp.server import create_app as create_mcp_app
from runtime.platform.android_monitor import AndroidMonitor
from runtime.platform.storage_manager import StorageManager
from runtime.recovery.ledger_guardian import AutoRecoveryHook, SnapshotManager
from runtime.recovery.tier_manager import RecoveryPolicy, RecoveryTierLevel, TierManager
from runtime.timeutils import now_iso
from runtime.warm_pool import WarmPool

__all__ = [
    "AutoRecoveryHook",
    "AndroidMonitor",
    "BootPreflightService",
    "CONSTITUTION_VERSION",
    "CheckpointVerificationError",
    "CheckpointVerifier",
    "EvolutionRuntime",
    "LineageIntegrityError",
    "RULE_ARCHITECT_SCAN",
    "RULE_CONSTITUTION_VERSION",
    "RULE_KEY_ROTATION",
    "RULE_LEDGER_INTEGRITY",
    "RULE_MUTATION_ENGINE",
    "RULE_PLATFORM_RESOURCES",
    "RULE_WARM_POOL",
    "RecoveryPolicy",
    "RecoveryTierLevel",
    "ReplayMode",
    "ReplayProofBuilder",
    "ReplayVerificationService",
    "SnapshotManager",
    "StorageManager",
    "TierManager",
    "WarmPool",
    "create_mcp_app",
    "default_provider",
    "determine_tier",
    "deterministic_envelope_scope",
    "dump",
    "enforce_law",
    "evaluate_mutation",
    "generate_tool_manifest",
    "get_forced_tier",
    "metrics",
    "normalize_replay_mode",
    "now_iso",
    "register",
    "register_capability",
    "score_mutation_enhanced",
]
