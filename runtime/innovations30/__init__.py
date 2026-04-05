# SPDX-License-Identifier: Apache-2.0
"""ADAAD 30 Innovations — runtime/innovations30/

All 30 novel capabilities described in ADAAD_30_INNOVATIONS.md,
implemented as production-ready modules.

Boot completeness gate:
    Call boot_completeness_check() at system startup.  Raises RuntimeError
    (fail-closed, invariant INNOV-COMPLETE-0) if any of the 30 innovation
    modules fails to import or is missing its primary export class.

Constitutional invariants:
    INNOV-COMPLETE-0  All 30 innovation modules must be importable at boot.
                      Missing any module is a blocking startup failure.
    INNOV-DETERM-0    All innovation computations must be deterministic for
                      equal inputs (ADAADInnovationEngine contract).
"""
from __future__ import annotations

import importlib
from typing import Any

# ── Canonical innovation registry ────────────────────────────────────────────
# Maps innovation number → (module_path, primary_class_name)
# Used by boot_completeness_check() and for external introspection.
# [INNOV-COMPLETE-0] — this list is the single source of truth; any mismatch
# between this registry and the filesystem is a blocking startup failure.
REGISTERED_INNOVATIONS: dict[int, tuple[str, str]] = {
    1:  ("runtime.innovations30.invariant_discovery",          "InvariantDiscoveryEngine"),
    2:  ("runtime.innovations30.constitutional_tension",       "ConstitutionalTensionResolver"),
    3:  ("runtime.innovations30.graduated_invariants",         "GraduatedInvariantPromoter"),
    4:  ("runtime.innovations30.intent_preservation",         "IntentPreservationVerifier"),
    5:  ("runtime.innovations30.temporal_regret",              "TemporalRegretScorer"),
    6:  ("runtime.innovations30.counterfactual_fitness",       "CounterfactualFitnessSimulator"),
    7:  ("runtime.innovations30.epistemic_decay",              "EpistemicDecayEngine"),
    8:  ("runtime.innovations30.red_team_agent",               "RedTeamAgent"),
    9:  ("runtime.innovations30.aesthetic_fitness",            "AestheticFitnessScorer"),
    10: ("runtime.innovations30.morphogenetic_memory",         "MorphogeneticMemory"),
    11: ("runtime.innovations30.dream_state",                  "DreamStateEngine"),
    12: ("runtime.innovations30.mutation_genealogy",           "MutationGenealogyAnalyzer"),
    13: ("runtime.innovations30.knowledge_transfer",           "InstitutionalMemoryTransfer"),
    14: ("runtime.innovations30.constitutional_jury",          "ConstitutionalJury"),
    15: ("runtime.innovations30.reputation_staking",           "ReputationStakingLedger"),
    16: ("runtime.innovations30.emergent_roles",               "EmergentRoleSpecializer"),
    17: ("runtime.innovations30.agent_postmortem",             "AgentPostMortemSystem"),
    18: ("runtime.innovations30.temporal_governance",          "TemporalGovernanceEngine"),
    19: ("runtime.innovations30.governance_archaeology",       "GovernanceArchaeologist"),
    20: ("runtime.innovations30.constitutional_stress_test",   "ConstitutionalStressTester"),
    21: ("runtime.innovations30.governance_bankruptcy",        "GovernanceBankruptcyProtocol"),
    22: ("runtime.innovations30.market_fitness",               "MarketConditionedFitness"),
    23: ("runtime.innovations30.regulatory_compliance",        "RegulatoryComplianceEngine"),
    24: ("runtime.innovations30.semantic_version_enforcer",    "SemanticVersionEnforcer"),
    25: ("runtime.innovations30.hardware_adaptive_fitness",    "HardwareAdaptiveFitness"),
    26: ("runtime.innovations30.constitutional_entropy_budget","ConstitutionalEntropyBudget"),
    27: ("runtime.innovations30.blast_radius_model",           "BlastRadiusModeler"),
    28: ("runtime.innovations30.self_awareness_invariant",     "SelfAwarenessInvariant"),
    29: ("runtime.innovations30.curiosity_engine",             "CuriosityEngine"),
    30: ("runtime.innovations30.mirror_test",                  "MirrorTestEngine"),
}

INNOVATION_COUNT: int = 30
INNOVATION_VERSION: str = "1.1.0"   # bumped: boot gate + MARKET-HALT-0


def boot_completeness_check() -> dict[str, Any]:
    """Verify all 30 innovations are importable.  Fail-closed.

    [INNOV-COMPLETE-0] Returns a report dict.  Raises RuntimeError if any
    module is missing or its primary class cannot be imported.

    Returns:
        {
          "status": "ok" | "failed",
          "total": 30,
          "loaded": N,
          "missing": [innovation_number, ...],
          "errors":  {innovation_number: error_message, ...},
        }
    """
    missing: list[int] = []
    errors: dict[int, str] = {}
    loaded = 0

    for num, (mod_path, cls_name) in REGISTERED_INNOVATIONS.items():
        try:
            # lint:fix forbidden_dynamic_execution — innovation module discovery — governance-reviewed
            mod = importlib.import_module(mod_path)  # lint:fix forbidden_dynamic_execution
            if not hasattr(mod, cls_name):
                raise AttributeError(
                    f"Module '{mod_path}' has no attribute '{cls_name}'"
                )
            loaded += 1
        except Exception as exc:  # noqa: BLE001
            missing.append(num)
            errors[num] = str(exc)

    status = "ok" if not missing else "failed"
    report: dict[str, Any] = {
        "status": status,
        "total": INNOVATION_COUNT,
        "loaded": loaded,
        "missing": sorted(missing),
        "errors": errors,
    }

    if missing:
        # [INNOV-COMPLETE-0] fail-closed — never let a partial innovation set run
        raise RuntimeError(
            f"[INNOV-COMPLETE-0] Boot completeness check FAILED. "
            f"{len(missing)}/{INNOVATION_COUNT} innovations failed to import: "
            f"{missing}. Errors: {errors}. "
            f"System cannot start with incomplete innovation set."
        )

    return report


def verify_all_importable() -> tuple[bool, dict[str, Any]]:
    """Non-raising version of boot_completeness_check for diagnostics.

    Returns:
        (True, report)  if all 30 load successfully
        (False, report) otherwise — caller decides whether to abort
    """
    try:
        report = boot_completeness_check()
        return True, report
    except RuntimeError as exc:
        return False, {
            "status": "failed",
            "total": INNOVATION_COUNT,
            "loaded": INNOVATION_COUNT - len(REGISTERED_INNOVATIONS),
            "error": str(exc),
        }


def get_innovation_class(number: int) -> type:
    """Import and return the primary class for innovation N (1-indexed).

    Raises KeyError for unknown number, ImportError if module is broken.
    """
    if number not in REGISTERED_INNOVATIONS:
        raise KeyError(
            f"Innovation #{number} not in REGISTERED_INNOVATIONS "
            f"(valid: 1–{INNOVATION_COUNT})"
        )
    mod_path, cls_name = REGISTERED_INNOVATIONS[number]
    # lint:fix forbidden_dynamic_execution — innovation module resolution — governance-reviewed
    mod = importlib.import_module(mod_path)  # lint:fix forbidden_dynamic_execution
    return getattr(mod, cls_name)


__all__ = [
    "INNOVATION_COUNT",
    "INNOVATION_VERSION",
    "REGISTERED_INNOVATIONS",
    "boot_completeness_check",
    "verify_all_importable",
    "get_innovation_class",
]
