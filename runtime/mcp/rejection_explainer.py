# SPDX-License-Identifier: Apache-2.0
"""Explain rejected mutation lifecycle guard failures."""

from __future__ import annotations

from typing import Any, Dict

from security.ledger import journal


def _steps_for_gate(gate: str) -> list[str]:
    mapping = {
        "cryovant_signature_validity": ["Ensure signature uses active key", "Regenerate signature over canonical payload"],
        "founders_law_invariant_gate": ["Address listed invariant failures", "Re-run preflight before resubmission"],
        "fitness_threshold_gate": ["Improve mutation quality and tests", "Reduce risky scope or complexity"],
        "trust_mode_compatibility_gate": ["Use an allowed trust mode", "Ask reviewer to adjust environment policy"],
        "cert_reference_gate": ["Attach required certification references", "Complete staged->certified governance review"],
    }
    return mapping.get(gate, ["Inspect guard report", "Address failing checks and resubmit"])


def explain_rejection(mutation_id: str) -> Dict[str, Any]:
    entry = journal.read_latest_entry_by_action_and_mutation_id(
        action="mutation_lifecycle_rejected",
        mutation_id=mutation_id,
        limit=5000,
    )
    if entry is None:
        raise KeyError("mutation_not_found")
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    guard = payload.get("guard_report") if isinstance(payload.get("guard_report"), dict) else {}

    failures = []
    for gate, result in guard.items():
        if isinstance(result, dict) and result.get("ok") is False:
            failures.append(
                {
                    "gate": gate,
                    "explanation": f"{gate} failed during lifecycle transition.",
                    "remediation_steps": _steps_for_gate(gate),
                }
            )

    return {"mutation_id": mutation_id, "gate_failures": failures}


__all__ = ["explain_rejection"]
