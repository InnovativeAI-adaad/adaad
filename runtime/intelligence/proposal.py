# SPDX-License-Identifier: Apache-2.0
"""Proposal contracts for AGM runtime intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ProposalTargetFile:
    """Target file details included with generated proposal context."""

    path: str
    language: str | None = None
    exists: bool | None = None
    content: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    title: str
    summary: str
    estimated_impact: float
    real_diff: str = ""
    target_files: tuple[ProposalTargetFile, ...] = field(default_factory=tuple)
    projected_impact: Mapping[str, Any] = field(default_factory=dict)
    evidence: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ProposalModule:
    """Factory for creating bounded, typed proposals from strategy outputs."""

    def build(
        self,
        *,
        cycle_id: str,
        strategy_id: str,
        rationale: str,
        real_diff: str = "",
        target_files: tuple[ProposalTargetFile, ...] = (),
        projected_impact: Mapping[str, Any] | None = None,
        evidence: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Proposal:
        merged_metadata = {"cycle_id": cycle_id, "strategy_id": strategy_id}
        merged_metadata.update(dict(metadata or {}))
        return Proposal(
            proposal_id=f"{cycle_id}:{strategy_id}",
            title=f"AGM proposal for {strategy_id}",
            summary=rationale,
            estimated_impact=0.0,
            real_diff=real_diff,
            target_files=tuple(target_files),
            projected_impact=dict(projected_impact or {}),
            evidence=dict(evidence or {}),
            metadata=merged_metadata,
        )
