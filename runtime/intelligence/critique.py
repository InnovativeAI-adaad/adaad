# SPDX-License-Identifier: Apache-2.0
"""Critique contracts for reviewing generated proposals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.intelligence.proposal import Proposal


@dataclass(frozen=True)
class CritiqueResult:
    approved: bool
    risk_score: float
    notes: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


class CritiqueModule:
    """Baseline deterministic critique for proposal safety gating."""

    def review(self, proposal: Proposal) -> CritiqueResult:
        risk_score = 0.0 if proposal.estimated_impact >= 0.0 else 1.0
        return CritiqueResult(
            approved=risk_score <= 0.5,
            risk_score=risk_score,
            notes="proposal accepted by baseline non-negative impact policy",
            metadata={"proposal_id": proposal.proposal_id},
        )
