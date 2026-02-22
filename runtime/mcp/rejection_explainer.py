# SPDX-License-Identifier: Apache-2.0
"""Explain rejected mutation lifecycle guard failures."""

from __future__ import annotations

from typing import Any, Dict, List

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
    entries: List[Dict[str, Any]] = [
        e
        for e in journal.read_entries(limit=5000)
        if isinstance(e, dict)
        and str(e.get("action") or "") == "mutation_lifecycle_rejected"
        and str((e.get("payload") or {}).get("mutation_id") or "") == mutation_id
    ]
    if not entries:
        raise KeyError("mutation_not_found")
    payload = entries[-1].get("payload") if isinstance(entries[-1].get("payload"), dict) else {}
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
