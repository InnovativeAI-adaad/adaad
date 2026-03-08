# SPDX-License-Identifier: Apache-2.0
"""Canonical governance decision execution pipeline."""

from __future__ import annotations

from typing import Any, Mapping

from runtime import constitution
from runtime.governance.decision_contract import CONTRACT_VERSION


def evaluate_mutation_decision(
    request: Any,
    tier: constitution.Tier,
    *,
    envelope_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute mutation approval through the canonical governance pipeline."""
    if envelope_state is not None:
        with constitution.deterministic_envelope_scope(dict(envelope_state)):
            verdict = constitution.evaluate_mutation(request, tier)
    else:
        verdict = constitution.evaluate_mutation(request, tier)

    canonical_verdict = dict(verdict)
    canonical_verdict["contract_version"] = CONTRACT_VERSION
    canonical_verdict["rule_evaluation_order"] = [
        row.get("rule")
        for row in canonical_verdict.get("verdicts", [])
        if isinstance(row, Mapping) and row.get("rule")
    ]
    return canonical_verdict


__all__ = ["evaluate_mutation_decision"]
