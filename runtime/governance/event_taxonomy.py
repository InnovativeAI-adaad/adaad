# SPDX-License-Identifier: Apache-2.0

"""Canonical governance event taxonomy and normalization helpers."""

from __future__ import annotations

from typing import Any, Mapping

EVENT_TYPE_AGM_STEP_01 = "agm_step_01"
EVENT_TYPE_AGM_STEP_02 = "agm_step_02"
EVENT_TYPE_AGM_STEP_03 = "agm_step_03"
EVENT_TYPE_AGM_STEP_04 = "agm_step_04"
EVENT_TYPE_AGM_STEP_05 = "agm_step_05"
EVENT_TYPE_AGM_STEP_06 = "agm_step_06"
EVENT_TYPE_AGM_STEP_07 = "agm_step_07"
EVENT_TYPE_AGM_STEP_08 = "agm_step_08"
EVENT_TYPE_AGM_STEP_09 = "agm_step_09"
EVENT_TYPE_AGM_STEP_10 = "agm_step_10"
EVENT_TYPE_AGM_STEP_11 = "agm_step_11"
EVENT_TYPE_AGM_STEP_12 = "agm_step_12"

EVENT_TYPE_STEP_FAULT = "step_fault"
EVENT_TYPE_CANONICAL_DECLARED = "canonical_declared"
EVENT_TYPE_EVENT_DEPRECATED = "event_deprecated"
EVENT_TYPE_EVENT_MIGRATED = "event_migrated"
EVENT_TYPE_BUDGET_MODE_CHANGED = "budget_mode_changed"
EVENT_TYPE_ATTRIBUTION_RECORDED = "attribution_recorded"

EVENT_TYPE_CONSTITUTION_ESCALATION = "constitution_escalation"
EVENT_TYPE_REPLAY_FAILURE = "replay_failure"
EVENT_TYPE_REPLAY_DIVERGENCE = "replay_divergence"
EVENT_TYPE_OPERATOR_OVERRIDE = "operator_override"

LEGACY_EVENT_TYPE_FALLBACKS: dict[str, str] = {
    "step_1": EVENT_TYPE_AGM_STEP_01,
    "step_2": EVENT_TYPE_AGM_STEP_02,
    "step_3": EVENT_TYPE_AGM_STEP_03,
    "step_4": EVENT_TYPE_AGM_STEP_04,
    "step_5": EVENT_TYPE_AGM_STEP_05,
    "step_6": EVENT_TYPE_AGM_STEP_06,
    "step_7": EVENT_TYPE_AGM_STEP_07,
    "step_8": EVENT_TYPE_AGM_STEP_08,
    "step_9": EVENT_TYPE_AGM_STEP_09,
    "step_10": EVENT_TYPE_AGM_STEP_10,
    "step_11": EVENT_TYPE_AGM_STEP_11,
    "step_12": EVENT_TYPE_AGM_STEP_12,
    "agm_step_1": EVENT_TYPE_AGM_STEP_01,
    "agm_step_2": EVENT_TYPE_AGM_STEP_02,
    "agm_step_3": EVENT_TYPE_AGM_STEP_03,
    "agm_step_4": EVENT_TYPE_AGM_STEP_04,
    "agm_step_5": EVENT_TYPE_AGM_STEP_05,
    "agm_step_6": EVENT_TYPE_AGM_STEP_06,
    "agm_step_7": EVENT_TYPE_AGM_STEP_07,
    "agm_step_8": EVENT_TYPE_AGM_STEP_08,
    "agm_step_9": EVENT_TYPE_AGM_STEP_09,
    "agm_step_10": EVENT_TYPE_AGM_STEP_10,
    "agm_step_11": EVENT_TYPE_AGM_STEP_11,
    "agm_step_12": EVENT_TYPE_AGM_STEP_12,
    "step_error": EVENT_TYPE_STEP_FAULT,
    "step_failed": EVENT_TYPE_STEP_FAULT,
    "canonical_event_declared": EVENT_TYPE_CANONICAL_DECLARED,
    "event_canonicalized": EVENT_TYPE_CANONICAL_DECLARED,
    "event_deprecation_declared": EVENT_TYPE_EVENT_DEPRECATED,
    "event_migration_declared": EVENT_TYPE_EVENT_MIGRATED,
    "budget_mode_change": EVENT_TYPE_BUDGET_MODE_CHANGED,
    "budget_profile_changed": EVENT_TYPE_BUDGET_MODE_CHANGED,
    "attribution_recorded_v1": EVENT_TYPE_ATTRIBUTION_RECORDED,
    "constitution_escalated": EVENT_TYPE_CONSTITUTION_ESCALATION,
    "manual_override": EVENT_TYPE_OPERATOR_OVERRIDE,
    "operator_manual_override": EVENT_TYPE_OPERATOR_OVERRIDE,
    "replay_check_failed": EVENT_TYPE_REPLAY_FAILURE,
    "replay_verification_failed": EVENT_TYPE_REPLAY_FAILURE,
    "replay_divergence_detected": EVENT_TYPE_REPLAY_DIVERGENCE,
    # LegitimacyEvaluation: mixed-case canonical form must survive normalize_event_type.
    "legitimacyevaluation": "LegitimacyEvaluation",
}


EVENT_TYPE_LEGITIMACY_EVALUATION = "LegitimacyEvaluation"

# Phase 9 — Soulbound Context event types
EVENT_TYPE_CONTEXT_LEDGER_ACCEPTED  = "context_ledger_entry_accepted.v1"
EVENT_TYPE_CONTEXT_LEDGER_REJECTED  = "context_ledger_entry_rejected.v1"
EVENT_TYPE_CONTEXT_TAMPER_DETECTED  = "context_ledger_tamper_detected.v1"
EVENT_TYPE_SOULBOUND_KEY_ROTATION   = "soulbound_key_rotation.v1"
EVENT_TYPE_CRAFT_PATTERN_EXTRACTED  = "craft_pattern_extracted.v1"
EVENT_TYPE_CONTEXT_REPLAY_INJECTED  = "context_replay_injected.v1"
EVENT_TYPE_SOULBOUND_KEY_ABSENT     = "soulbound_key_absent.v1"
# Phase 17 — IntelligenceRouter closure
EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION = "routed_intelligence_decision.v1"

CANONICAL_EVENT_TYPES = {
    EVENT_TYPE_AGM_STEP_01,
    EVENT_TYPE_AGM_STEP_02,
    EVENT_TYPE_AGM_STEP_03,
    EVENT_TYPE_AGM_STEP_04,
    EVENT_TYPE_AGM_STEP_05,
    EVENT_TYPE_AGM_STEP_06,
    EVENT_TYPE_AGM_STEP_07,
    EVENT_TYPE_AGM_STEP_08,
    EVENT_TYPE_AGM_STEP_09,
    EVENT_TYPE_AGM_STEP_10,
    EVENT_TYPE_AGM_STEP_11,
    EVENT_TYPE_AGM_STEP_12,
    EVENT_TYPE_STEP_FAULT,
    EVENT_TYPE_CANONICAL_DECLARED,
    EVENT_TYPE_EVENT_DEPRECATED,
    EVENT_TYPE_EVENT_MIGRATED,
    EVENT_TYPE_BUDGET_MODE_CHANGED,
    EVENT_TYPE_ATTRIBUTION_RECORDED,
    EVENT_TYPE_CONSTITUTION_ESCALATION,
    EVENT_TYPE_REPLAY_FAILURE,
    EVENT_TYPE_REPLAY_DIVERGENCE,
    EVENT_TYPE_OPERATOR_OVERRIDE,
    EVENT_TYPE_LEGITIMACY_EVALUATION,
    # Phase 9 — Soulbound Context
    EVENT_TYPE_CONTEXT_LEDGER_ACCEPTED,
    EVENT_TYPE_CONTEXT_LEDGER_REJECTED,
    EVENT_TYPE_CONTEXT_TAMPER_DETECTED,
    EVENT_TYPE_SOULBOUND_KEY_ROTATION,
    EVENT_TYPE_CRAFT_PATTERN_EXTRACTED,
    EVENT_TYPE_CONTEXT_REPLAY_INJECTED,
    EVENT_TYPE_SOULBOUND_KEY_ABSENT,
    # Phase 17
    EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION,
}


AGM_STEPS = tuple(f"agm_step_{index:02d}" for index in range(1, 13))
AGM_STEP_EVENT_TYPES: dict[str, set[str]] = {
    step: {event_type}
    for step, event_type in zip(
        AGM_STEPS,
        (
            EVENT_TYPE_AGM_STEP_01,
            EVENT_TYPE_AGM_STEP_02,
            EVENT_TYPE_AGM_STEP_03,
            EVENT_TYPE_AGM_STEP_04,
            EVENT_TYPE_AGM_STEP_05,
            EVENT_TYPE_AGM_STEP_06,
            EVENT_TYPE_AGM_STEP_07,
            EVENT_TYPE_AGM_STEP_08,
            EVENT_TYPE_AGM_STEP_09,
            EVENT_TYPE_AGM_STEP_10,
            EVENT_TYPE_AGM_STEP_11,
            EVENT_TYPE_AGM_STEP_12,
        ),
    )
}
AGM_CONTROL_EVENT_TYPES = {
    EVENT_TYPE_STEP_FAULT,
    EVENT_TYPE_CANONICAL_DECLARED,
    EVENT_TYPE_EVENT_DEPRECATED,
    EVENT_TYPE_EVENT_MIGRATED,
    EVENT_TYPE_BUDGET_MODE_CHANGED,
    EVENT_TYPE_ATTRIBUTION_RECORDED,
}

LEGACY_STEP_FALLBACKS: dict[str, str] = {
    str(index): f"agm_step_{index:02d}" for index in range(1, 13)
}
LEGACY_STEP_FALLBACKS.update(
    {
        f"step_{index}": f"agm_step_{index:02d}" for index in range(1, 13)
    }
)
LEGACY_STEP_FALLBACKS.update(
    {
        f"agm_step_{index}": f"agm_step_{index:02d}" for index in range(1, 13)
    }
)


def normalize_agm_step(agm_step: Any) -> str:
    """Normalize an AGM step designator to canonical ``agm_step_XX`` format."""

    candidate = str(agm_step or "").strip().lower()
    if candidate in AGM_STEP_EVENT_TYPES:
        return candidate
    return LEGACY_STEP_FALLBACKS.get(candidate, "")


def normalize_event_type(entry: Mapping[str, Any]) -> str:
    """Resolve a normalized event type from mixed legacy and canonical fields."""

    event_type = str(entry.get("event_type", "")).strip().lower()
    if event_type in CANONICAL_EVENT_TYPES:
        return event_type
    if event_type in LEGACY_EVENT_TYPE_FALLBACKS:
        return LEGACY_EVENT_TYPE_FALLBACKS[event_type]

    event_name = str(entry.get("event", "")).strip().lower()
    if event_name in LEGACY_EVENT_TYPE_FALLBACKS:
        return LEGACY_EVENT_TYPE_FALLBACKS[event_name]

    if event_type:
        return event_type

    return event_name


def validate_event_type_for_agm_step(*, event_type: str, agm_step: Any = None) -> str:
    """Validate an event type against canonical AGM taxonomy for an optional step."""

    normalized_event_type = normalize_event_type({"event_type": event_type})
    if not normalized_event_type:
        raise ValueError("event_type_missing")

    normalized_agm_step = normalize_agm_step(agm_step)
    if agm_step is None or str(agm_step).strip() == "":
        return normalized_event_type
    if not normalized_agm_step:
        raise ValueError(f"agm_step_unknown:{agm_step}")

    allowed_event_types = AGM_STEP_EVENT_TYPES[normalized_agm_step] | AGM_CONTROL_EVENT_TYPES
    if normalized_event_type not in allowed_event_types:
        raise ValueError(f"event_type_not_allowed:{normalized_event_type}:{normalized_agm_step}")
    return normalized_event_type


def validate_agm_event(entry: Mapping[str, Any]) -> str:
    """Validate an event mapping and return normalized event type."""

    event_type = str(entry.get("event_type") or entry.get("event") or "")
    return validate_event_type_for_agm_step(event_type=event_type, agm_step=entry.get("agm_step"))


__all__ = [
    "AGM_CONTROL_EVENT_TYPES",
    "AGM_STEP_EVENT_TYPES",
    "AGM_STEPS",
    "CANONICAL_EVENT_TYPES",
    # Phase 9
    "EVENT_TYPE_CONTEXT_LEDGER_ACCEPTED",
    "EVENT_TYPE_CONTEXT_LEDGER_REJECTED",
    "EVENT_TYPE_CONTEXT_TAMPER_DETECTED",
    "EVENT_TYPE_SOULBOUND_KEY_ROTATION",
    "EVENT_TYPE_CRAFT_PATTERN_EXTRACTED",
    "EVENT_TYPE_CONTEXT_REPLAY_INJECTED",
    "EVENT_TYPE_SOULBOUND_KEY_ABSENT",
    "EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION",
    "EVENT_TYPE_AGM_STEP_01",
    "EVENT_TYPE_AGM_STEP_02",
    "EVENT_TYPE_AGM_STEP_03",
    "EVENT_TYPE_AGM_STEP_04",
    "EVENT_TYPE_AGM_STEP_05",
    "EVENT_TYPE_AGM_STEP_06",
    "EVENT_TYPE_AGM_STEP_07",
    "EVENT_TYPE_AGM_STEP_08",
    "EVENT_TYPE_AGM_STEP_09",
    "EVENT_TYPE_AGM_STEP_10",
    "EVENT_TYPE_AGM_STEP_11",
    "EVENT_TYPE_AGM_STEP_12",
    "EVENT_TYPE_ATTRIBUTION_RECORDED",
    "EVENT_TYPE_BUDGET_MODE_CHANGED",
    "EVENT_TYPE_CANONICAL_DECLARED",
    "EVENT_TYPE_CONSTITUTION_ESCALATION",
    "EVENT_TYPE_EVENT_DEPRECATED",
    "EVENT_TYPE_EVENT_MIGRATED",
    "EVENT_TYPE_OPERATOR_OVERRIDE",
    "EVENT_TYPE_REPLAY_DIVERGENCE",
    "EVENT_TYPE_REPLAY_FAILURE",
    "EVENT_TYPE_STEP_FAULT",
    "LEGACY_EVENT_TYPE_FALLBACKS",
    "normalize_agm_step",
    "normalize_event_type",
    "validate_agm_event",
    "validate_event_type_for_agm_step",
]
