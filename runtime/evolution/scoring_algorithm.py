# SPDX-License-Identifier: Apache-2.0
"""Deterministic mutation scoring algorithm for governance decisions."""

from __future__ import annotations

import copy
from types import MappingProxyType
from typing import Any, Dict

from runtime.governance.foundation import (
    RuntimeDeterminismProvider,
    canonical_json,
    default_provider,
    require_replay_safe_provider,
    sha256_prefixed_digest,
)

ALGORITHM_VERSION = "v1.1.0"

SEVERITY_WEIGHTS = MappingProxyType(
    {
        "LOW": 1,
        "MEDIUM": 3,
        "HIGH": 5,
        "CRITICAL": 10,
    }
)

RISK_WEIGHTS = MappingProxyType(
    {
        "API": 30,
        "PERF": 20,
        "SECURITY": 50,
        "DEFAULT": 10,
    }
)

MAX_LOC = 100_000
MAX_FILES = 1_000
MAX_ISSUES = 10_000
MAX_COMPONENT_TERM = 300


class ScoringValidationError(ValueError):
    """Raised when scoring input violates deterministic hard limits."""


def validate_input(scoring_input: Dict[str, Any]) -> None:
    """Validate hard limits to prevent unbounded scoring work."""
    code_diff = scoring_input.get("code_diff", {})
    loc_added = int(code_diff.get("loc_added", 0) or 0)
    loc_deleted = int(code_diff.get("loc_deleted", 0) or 0)
    files_touched = int(code_diff.get("files_touched", 0) or 0)

    if loc_added + loc_deleted > MAX_LOC:
        raise ScoringValidationError(f"LOC exceeds maximum: {loc_added + loc_deleted} > {MAX_LOC}")
    if files_touched > MAX_FILES:
        raise ScoringValidationError(f"Files touched exceeds maximum: {files_touched} > {MAX_FILES}")

    issues = (scoring_input.get("static_analysis", {}) or {}).get("issues", [])
    if len(issues) > MAX_ISSUES:
        raise ScoringValidationError(f"Static analysis issues exceed maximum: {len(issues)} > {MAX_ISSUES}")


def canonicalize_input(scoring_input: Dict[str, Any]) -> str:
    """Canonicalize input without mutating caller-owned data."""
    normalized = copy.deepcopy(scoring_input)

    code_diff = normalized.get("code_diff", {})
    if isinstance(code_diff.get("risk_tags"), list):
        code_diff["risk_tags"] = sorted(str(tag) for tag in code_diff["risk_tags"])

    static_analysis = normalized.get("static_analysis", {})
    issues = static_analysis.get("issues")
    if isinstance(issues, list):
        static_analysis["issues"] = sorted(
            issues,
            key=lambda item: str((item or {}).get("rule_id", "")),
        )

    return canonical_json(normalized)


def compute_input_hash(canonical_input: str) -> str:
    return sha256_prefixed_digest(canonical_input)


def score_tests(test_results: Dict[str, Any]) -> int:
    total = int(test_results.get("total", 0) or 0)
    failed = int(test_results.get("failed", 0) or 0)

    if failed > 0:
        return 0
    if total > 0:
        return 1000
    return 500


def compute_static_penalty(static_analysis: Dict[str, Any]) -> int:
    penalty = 0
    for issue in static_analysis.get("issues", []):
        severity = str((issue or {}).get("severity", "")).upper()
        penalty += 10 * int(SEVERITY_WEIGHTS.get(severity, 0))
    return penalty


def compute_diff_penalty(code_diff: Dict[str, Any]) -> int:
    loc_added = int(code_diff.get("loc_added", 0) or 0)
    loc_deleted = int(code_diff.get("loc_deleted", 0) or 0)
    files_touched = int(code_diff.get("files_touched", 0) or 0)
    return (loc_added + loc_deleted) + (5 * files_touched)


def compute_risk_penalty(code_diff: Dict[str, Any]) -> int:
    penalty = 0
    for tag in code_diff.get("risk_tags", []) or []:
        penalty += int(RISK_WEIGHTS.get(str(tag), RISK_WEIGHTS["DEFAULT"]))
    return penalty


def _clamp_term(value: Any, *, max_value: int = MAX_COMPONENT_TERM) -> int:
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(max_value, numeric))


def compute_long_horizon_sustainability_term(scoring_input: Dict[str, Any]) -> int:
    sustainability = scoring_input.get("sustainability")
    if isinstance(sustainability, dict):
        score = sustainability.get("score", sustainability.get("long_horizon_score", 0))
    else:
        score = scoring_input.get("long_horizon_sustainability_score", 0)
    return _clamp_term(score)


def compute_resource_efficiency_term(scoring_input: Dict[str, Any]) -> int:
    efficiency = scoring_input.get("resource_efficiency")
    if isinstance(efficiency, dict):
        score = efficiency.get("score", efficiency.get("efficiency_score", 0))
    else:
        score = scoring_input.get("resource_efficiency_score", 0)
    return _clamp_term(score)


def compute_cross_agent_synergy_term(scoring_input: Dict[str, Any]) -> int:
    synergy = scoring_input.get("cross_agent_synergy")
    if isinstance(synergy, dict):
        score = synergy.get("score", synergy.get("synergy_score", 0))
    else:
        score = scoring_input.get("cross_agent_synergy_score", 0)
    return _clamp_term(score)


def compute_score(
    scoring_input: Dict[str, Any],
    *,
    provider: RuntimeDeterminismProvider | None = None,
    replay_mode: str = "off",
    recovery_tier: str | None = None,
) -> Dict[str, Any]:
    """Compute deterministic score with canonical hashing and bounded arithmetic."""
    runtime_provider = provider or default_provider()
    require_replay_safe_provider(runtime_provider, replay_mode=replay_mode, recovery_tier=recovery_tier)

    validate_input(scoring_input)
    canonical_input = canonicalize_input(scoring_input)
    input_hash = compute_input_hash(canonical_input)

    test_score = score_tests(scoring_input.get("test_results", {}))
    static_penalty = compute_static_penalty(scoring_input.get("static_analysis", {}))
    diff_penalty = compute_diff_penalty(scoring_input.get("code_diff", {}))
    risk_penalty = compute_risk_penalty(scoring_input.get("code_diff", {}))
    sustainability_term = compute_long_horizon_sustainability_term(scoring_input)
    resource_efficiency_term = compute_resource_efficiency_term(scoring_input)
    cross_agent_synergy_term = compute_cross_agent_synergy_term(scoring_input)

    final_score = max(
        0,
        test_score
        + sustainability_term
        + resource_efficiency_term
        + cross_agent_synergy_term
        - static_penalty
        - diff_penalty
        - risk_penalty,
    )

    return {
        "mutation_id": scoring_input.get("mutation_id", ""),
        "epoch_id": scoring_input.get("epoch_id", ""),
        "score": int(final_score),
        "input_hash": input_hash,
        "algorithm_version": ALGORITHM_VERSION,
        "constitution_hash": scoring_input.get("constitution_hash", ""),
        "timestamp": runtime_provider.iso_now(),
        "components": {
            "test_score": int(test_score),
            "static_penalty": int(static_penalty),
            "diff_penalty": int(diff_penalty),
            "risk_penalty": int(risk_penalty),
            "long_horizon_sustainability_term": int(sustainability_term),
            "resource_efficiency_term": int(resource_efficiency_term),
            "cross_agent_synergy_term": int(cross_agent_synergy_term),
        },
    }


__all__ = [
    "ALGORITHM_VERSION",
    "MAX_FILES",
    "MAX_COMPONENT_TERM",
    "MAX_ISSUES",
    "MAX_LOC",
    "RISK_WEIGHTS",
    "SEVERITY_WEIGHTS",
    "ScoringValidationError",
    "canonicalize_input",
    "compute_cross_agent_synergy_term",
    "compute_diff_penalty",
    "compute_input_hash",
    "compute_long_horizon_sustainability_term",
    "compute_risk_penalty",
    "compute_resource_efficiency_term",
    "compute_score",
    "compute_static_penalty",
    "score_tests",
    "validate_input",
]
