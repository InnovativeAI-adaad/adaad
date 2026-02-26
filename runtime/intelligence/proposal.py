# SPDX-License-Identifier: Apache-2.0
"""Proposal contracts for AGM runtime intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    title: str
    summary: str
    estimated_impact: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ProposalModule:
    """Factory for creating bounded, typed proposals from strategy outputs."""

    def build(self, *, cycle_id: str, strategy_id: str, rationale: str) -> Proposal:
        return Proposal(
            proposal_id=f"{cycle_id}:{strategy_id}",
            title=f"AGM proposal for {strategy_id}",
            summary=rationale,
            estimated_impact=0.0,
            metadata={"cycle_id": cycle_id, "strategy_id": strategy_id},
        )
