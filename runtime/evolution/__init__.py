# SPDX-License-Identifier: Apache-2.0
"""Evolution governance and replay runtime package.

This package intentionally uses lazy symbol loading to avoid circular import
cascades across runtime/api and runtime/evolution modules during test and boot
collection.
"""

from __future__ import annotations

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


def _resolve_module(module_name: str) -> Any:
    # lint:fix forbidden_dynamic_execution — explicit module routing — governance-reviewed
    if module_name == "runtime.evolution.epoch":
        from runtime.evolution import epoch as module

        return module
    if module_name == "runtime.evolution.checkpoint_registry":
        from runtime.evolution import checkpoint_registry as module

        return module
    if module_name == "runtime.evolution.checkpoint_verifier":
        from runtime.evolution import checkpoint_verifier as module

        return module
    if module_name == "runtime.evolution.entropy_detector":
        from runtime.evolution import entropy_detector as module

        return module
    if module_name == "runtime.evolution.entropy_policy":
        from runtime.evolution import entropy_policy as module

        return module
    if module_name == "runtime.evolution.entropy_forecast":
        from runtime.evolution import entropy_forecast as module

        return module
    if module_name == "runtime.evolution.governor":
        from runtime.evolution import governor as module

        return module
    if module_name == "runtime.evolution.goal_graph":
        from runtime.evolution import goal_graph as module

        return module
    if module_name == "runtime.evolution.impact":
        from runtime.evolution import impact as module

        return module
    if module_name == "runtime.evolution.lineage_v2":
        from runtime.evolution import lineage_v2 as module

        return module
    if module_name == "runtime.evolution.promotion_events":
        from runtime.evolution import promotion_events as module

        return module
    if module_name == "runtime.evolution.promotion_policy":
        from runtime.evolution import promotion_policy as module

        return module
    if module_name == "runtime.evolution.promotion_state_machine":
        from runtime.evolution import promotion_state_machine as module

        return module
    if module_name == "runtime.evolution.replay":
        from runtime.evolution import replay as module

        return module
    if module_name == "runtime.evolution.evidence_bundle":
        from runtime.evolution import evidence_bundle as module

        return module
    if module_name == "runtime.evolution.economic_fitness":
        from runtime.evolution import economic_fitness as module

        return module
    if module_name == "runtime.evolution.simulation_runner":
        from runtime.evolution import simulation_runner as module

        return module
    if module_name == "runtime.evolution.scoring":
        from runtime.evolution import scoring as module

        return module
    if module_name == "runtime.evolution.scoring_algorithm":
        from runtime.evolution import scoring_algorithm as module

        return module
    if module_name == "runtime.evolution.scoring_ledger":
        from runtime.evolution import scoring_ledger as module

        return module
    if module_name == "runtime.evolution.mutation_credit_ledger":
        from runtime.evolution import mutation_credit_ledger as module

        return module
    if module_name == "runtime.evolution.scoring_validator":
        from runtime.evolution import scoring_validator as module

        return module
    if module_name == "runtime.evolution.replay_verifier":
        from runtime.evolution import replay_verifier as module

        return module
    if module_name == "runtime.evolution.replay_attestation":
        from runtime.evolution import replay_attestation as module

        return module
    if module_name == "runtime.evolution.runtime":
        from runtime.evolution import runtime as module

        return module
    if module_name == "runtime.evolution.fitness_regression":
        from runtime.evolution import fitness_regression as module

        return module
    if module_name == "runtime.evolution.telemetry_audit":
        from runtime.evolution import telemetry_audit as module

        return module
    raise ModuleNotFoundError(module_name)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = _resolve_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
