# SPDX-License-Identifier: Apache-2.0
"""Proposal generation entrypoint for AGM evolution steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.intelligence.proposal import Proposal


@dataclass(frozen=True)
class ProposalRequest:
    cycle_id: str
    strategy_id: str
    context: Mapping[str, Any] = field(default_factory=dict)


class ProposalEngine:
    """Stable generator API used by AGM execution loops."""

    def generate(self, request: ProposalRequest) -> Proposal:
        summary = f"Generated proposal for strategy '{request.strategy_id}'"
        return Proposal(
            proposal_id=f"{request.cycle_id}:{request.strategy_id}:generated",
            title=f"Evolution proposal {request.strategy_id}",
            summary=summary,
            estimated_impact=0.0,
            metadata={"context": dict(request.context)},
        )
