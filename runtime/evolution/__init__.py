# SPDX-License-Identifier: Apache-2.0
"""Evolution governance and replay runtime package.

This package intentionally uses lazy symbol loading to avoid circular import
cascades across runtime/api and runtime/evolution modules during test and boot
collection.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "EpochManager": ("runtime.evolution.epoch", "EpochManager"),
    "EpochState": ("runtime.evolution.epoch", "EpochState"),
    "CheckpointRegistry": ("runtime.evolution.checkpoint_registry", "CheckpointRegistry"),
    "verify_checkpoint_chain": ("runtime.evolution.checkpoint_verifier", "verify_checkpoint_chain"),
    "detect_entropy_metadata": ("runtime.evolution.entropy_detector", "detect_entropy_metadata"),
    "EntropyPolicy": ("runtime.evolution.entropy_policy", "EntropyPolicy"),
    "enforce_entropy_policy": ("runtime.evolution.entropy_policy", "enforce_entropy_policy"),
    "EntropyBudgetForecaster": ("runtime.evolution.entropy_forecast", "EntropyBudgetForecaster"),
    "EvolutionGovernor": ("runtime.evolution.governor", "EvolutionGovernor"),
    "GovernanceDecision": ("runtime.evolution.governor", "GovernanceDecision"),
    "RecoveryTier": ("runtime.evolution.governor", "RecoveryTier"),
    "GoalGraph": ("runtime.evolution.goal_graph", "GoalGraph"),
    "GoalNode": ("runtime.evolution.goal_graph", "GoalNode"),
    "ImpactScorer": ("runtime.evolution.impact", "ImpactScorer"),
    "ImpactScore": ("runtime.evolution.impact", "ImpactScore"),
    "LineageEvent": ("runtime.evolution.lineage_v2", "LineageEvent"),
    "LineageLedgerV2": ("runtime.evolution.lineage_v2", "LineageLedgerV2"),
    "EpochStartEvent": ("runtime.evolution.lineage_v2", "EpochStartEvent"),
    "EpochEndEvent": ("runtime.evolution.lineage_v2", "EpochEndEvent"),
    "MutationBundleEvent": ("runtime.evolution.lineage_v2", "MutationBundleEvent"),
    "create_promotion_event": ("runtime.evolution.promotion_events", "create_promotion_event"),
    "derive_event_id": ("runtime.evolution.promotion_events", "derive_event_id"),
    "PromotionPolicyEngine": ("runtime.evolution.promotion_policy", "PromotionPolicyEngine"),
    "PromotionPolicyError": ("runtime.evolution.promotion_policy", "PromotionPolicyError"),
    "PromotionState": ("runtime.evolution.promotion_state_machine", "PromotionState"),
    "can_transition": ("runtime.evolution.promotion_state_machine", "can_transition"),
    "require_transition": ("runtime.evolution.promotion_state_machine", "require_transition"),
    "ReplayEngine": ("runtime.evolution.replay", "ReplayEngine"),
    "EvidenceBundleBuilder": ("runtime.evolution.evidence_bundle", "EvidenceBundleBuilder"),
    "EvidenceBundleError": ("runtime.evolution.evidence_bundle", "EvidenceBundleError"),
    "EconomicFitnessEvaluator": ("runtime.evolution.economic_fitness", "EconomicFitnessEvaluator"),
    "EconomicFitnessResult": ("runtime.evolution.economic_fitness", "EconomicFitnessResult"),
    "SimulationRunner": ("runtime.evolution.simulation_runner", "SimulationRunner"),
    "authority_threshold": ("runtime.evolution.scoring", "authority_threshold"),
    "clamp_score": ("runtime.evolution.scoring", "clamp_score"),
    "compute_score": ("runtime.evolution.scoring_algorithm", "compute_score"),
    "ScoringLedger": ("runtime.evolution.scoring_ledger", "ScoringLedger"),
    "MutationCreditLedger": ("runtime.evolution.mutation_credit_ledger", "MutationCreditLedger"),
    "MutationCreditEvent": ("runtime.evolution.mutation_credit_ledger", "MutationCreditEvent"),
    "MutationCreditLedgerError": ("runtime.evolution.mutation_credit_ledger", "MutationCreditLedgerError"),
    "validate_scoring_payload": ("runtime.evolution.scoring_validator", "validate_scoring_payload"),
    "ReplayVerifier": ("runtime.evolution.replay_verifier", "ReplayVerifier"),
    "ReplayProofBuilder": ("runtime.evolution.replay_attestation", "ReplayProofBuilder"),
    "verify_replay_proof_bundle": ("runtime.evolution.replay_attestation", "verify_replay_proof_bundle"),
    "EvolutionRuntime": ("runtime.evolution.runtime", "EvolutionRuntime"),
    "FitnessRegressionSignal": ("runtime.evolution.fitness_regression", "FitnessRegressionSignal"),
    "RegressionSeverity": ("runtime.evolution.fitness_regression", "RegressionSeverity"),
    "emit_fitness_regression_signal": ("runtime.evolution.fitness_regression", "emit_fitness_regression_signal"),
    "detect_entropy_drift": ("runtime.evolution.telemetry_audit", "detect_entropy_drift"),
    "get_epoch_entropy_breakdown": ("runtime.evolution.telemetry_audit", "get_epoch_entropy_breakdown"),
    "get_epoch_entropy_envelope_summary": ("runtime.evolution.telemetry_audit", "get_epoch_entropy_envelope_summary"),
}


__all__ = sorted(_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
