# SPDX-License-Identifier: Apache-2.0
"""Critique contracts for reviewing generated proposals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.intelligence.proposal import Proposal


CRITIQUE_DIMENSIONS = (
    "risk",
    "alignment",
    "feasibility",
    "governance",
    "observability",
)


@dataclass(frozen=True)
class CritiqueResult:
    approved: bool
    per_dimension_scores: Mapping[str, float]
    weighted_aggregate: float
    risk_score: float
    notes: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


class CritiqueModule:
    """Baseline deterministic critique for proposal safety gating."""

    def review(self, proposal: Proposal) -> CritiqueResult:
        risk_score = 0.0 if proposal.estimated_impact >= 0.0 else 1.0
        per_dimension_scores = {
            "risk": risk_score,
            "alignment": 1.0,
            "feasibility": 1.0,
            "governance": 1.0,
            "observability": 1.0,
        }
        weighted_aggregate = sum(per_dimension_scores.values()) / len(per_dimension_scores)
        return CritiqueResult(
            approved=risk_score <= 0.5,
            per_dimension_scores=per_dimension_scores,
            weighted_aggregate=weighted_aggregate,
            risk_score=risk_score,
            notes="proposal accepted by baseline non-negative impact policy",
            metadata={"proposal_id": proposal.proposal_id},
        )
