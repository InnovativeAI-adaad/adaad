# SPDX-License-Identifier: Apache-2.0
"""Claude governed proposal agent for MCP integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ClaudeProposalAgent:
    """Optional deterministic post-processor for already-generated candidates.

    This helper does not call model APIs. Runtime proposal generation should flow
    through ``runtime.intelligence.proposal_adapter.ProposalAdapter``.
    """

    agent_id: str = "claude-proposal-agent"

    def propose(self, context: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """Return candidate proposals from context in deterministic list order."""

        raw_candidates = (context or {}).get("candidates") or []
        return [candidate for candidate in raw_candidates if isinstance(candidate, dict)]

    def score(self, candidate: Dict[str, Any]) -> float:
        value = candidate.get("score", 0.0)
        if not isinstance(value, (int, float)):
            return 0.0
        return float(max(0.0, min(1.0, value)))
