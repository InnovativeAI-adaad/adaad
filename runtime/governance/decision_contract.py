# SPDX-License-Identifier: Apache-2.0
"""Canonical governance decision contract definitions.

This module defines a single mutation-approval contract used across runtime
call sites:
- input schema
- deterministic rule evaluation order
- output schema
- constitutional rule-to-executable identifier mapping
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping

from runtime import constitution

CONTRACT_VERSION = "governance-decision.v1"
RULE_APPLICABILITY_PATH = Path("governance/rule_applicability.yaml")
POLICY_REGO_PATH = Path("governance/policies.rego")

DECISION_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["request", "tier"],
    "properties": {
        "request": {
            "type": "object",
            "required": ["agent_id", "intent", "ops"],
        },
        "tier": {"type": "string", "enum": [tier.name for tier in constitution.Tier]},
        "envelope_state": {"type": "object"},
    },
}

DECISION_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": [
        "contract_version",
        "constitution_version",
        "policy_hash",
        "tier",
        "passed",
        "verdicts",
        "blocking_failures",
        "warnings",
        "governance_envelope",
    ],
}


def constitutional_rule_registry() -> Dict[str, str]:
    """Map constitutional rule names to executable validator identifiers."""
    return {
        rule.name: f"{rule.validator.__module__}.{rule.validator.__name__}"
        for rule in constitution.RULES
    }


def evaluation_order_for_tier(tier: constitution.Tier) -> List[str]:
    """Return deterministic evaluation order for the requested tier."""
    ordered = constitution._order_rules_with_dependencies(constitution.get_rules_for_tier(tier))
    return [rule.name for rule, _severity in ordered]


def declared_artifact_rules() -> Dict[str, List[str]]:
    """Load declared rule sets from governance artifacts used for drift checks."""
    policy_rules = [rule.name for rule in constitution.RULES]

    applicability_raw = constitution.yaml.safe_load(RULE_APPLICABILITY_PATH.read_text(encoding="utf-8"))
    applicability_rules: List[str] = []
    if isinstance(applicability_raw, Mapping):
        for entry in applicability_raw.get("rules", []):
            if isinstance(entry, Mapping):
                name = str(entry.get("name", "")).strip()
                if name:
                    applicability_rules.append(name)

    rego_source = POLICY_REGO_PATH.read_text(encoding="utf-8") if POLICY_REGO_PATH.exists() else ""
    rego_operations: List[str] = []
    for line in rego_source.splitlines():
        stripped = line.strip().strip(",")
        if stripped.startswith('"') and stripped.endswith('"') and "mutation." in stripped:
            rego_operations.append(stripped.strip('"'))

    return {
        "constitution_policy": sorted(set(policy_rules)),
        "rule_applicability": sorted(set(applicability_rules)),
        "rego_operations": sorted(set(rego_operations)),
    }


__all__ = [
    "CONTRACT_VERSION",
    "DECISION_INPUT_SCHEMA",
    "DECISION_OUTPUT_SCHEMA",
    "constitutional_rule_registry",
    "declared_artifact_rules",
    "evaluation_order_for_tier",
]
