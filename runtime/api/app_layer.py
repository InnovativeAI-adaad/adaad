# SPDX-License-Identifier: Apache-2.0
"""Facade for runtime services consumed by app-layer modules."""

from runtime import ROOT_DIR, fitness, metrics
from runtime.autonomy.mutation_scaffold import MutationCandidate, rank_mutation_candidates
from runtime.capability_graph import get_capabilities, register_capability
from runtime.evolution.entropy_discipline import EntropyBudget, deterministic_context, deterministic_token_with_budget
from runtime.evolution.fitness import FitnessEvaluator
from runtime.evolution.promotion_manifest import PromotionManifestWriter, emit_pr_lifecycle_event
from runtime.governance.branch_manager import BranchManager
from runtime.governance.foundation import RuntimeDeterminismProvider, SeededDeterminismProvider, default_provider, require_replay_safe_provider, safe_get
from runtime.governance.gate_certifier import GateCertifier
from runtime.integrations.aponi_sync import push_to_dashboard
from runtime.intelligence.llm_provider import LLMProviderClient, load_provider_config
from runtime.manifest.generator import generate_tool_manifest
from runtime.metrics_analysis import summarize_preflight_rejections, top_preflight_rejections
from runtime.timeutils import now_iso
from runtime.tools.mutation_fs import file_hash

__all__ = [
    "BranchManager",
    "EntropyBudget",
    "EvolutionKernel",
    "FitnessEvaluator",
    "GateCertifier",
    "LLMProviderClient",
    "MutationCandidate",
    "PromotionManifestWriter",
    "ROOT_DIR",
    "RuntimeDeterminismProvider",
    "SeededDeterminismProvider",
    "default_provider",
    "deterministic_context",
    "deterministic_token_with_budget",
    "emit_pr_lifecycle_event",
    "file_hash",
    "fitness",
    "generate_tool_manifest",
    "get_capabilities",
    "load_provider_config",
    "metrics",
    "now_iso",
    "push_to_dashboard",
    "rank_mutation_candidates",
    "register_capability",
    "require_replay_safe_provider",
    "safe_get",
    "summarize_preflight_rejections",
    "top_preflight_rejections",
]



def __getattr__(name: str):
    if name == "EvolutionKernel":
        from runtime.evolution.evolution_kernel import EvolutionKernel

        return EvolutionKernel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
