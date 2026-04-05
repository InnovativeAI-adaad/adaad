# SPDX-License-Identifier: Apache-2.0
"""Unified agent contract for provider-agnostic execution."""

from __future__ import annotations

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class UnifiedAgent(Protocol):
    """
    Mandatory interface for all ADAAD intelligence backends.
    Satisfied by Claude, Gemini, and Codex adapters.
    """

    def info(self) -> Dict[str, Any]:
        """Return descriptive metadata for the agent instance."""
        pass

    def run(self, input: Any = None) -> Dict[str, Any]:
        """Execute the agent against the provided input payload."""
        pass

    def mutate(self, src: str) -> str:
        """Produce a deterministic mutation of source content."""
        pass

    def score(self, output: Dict[str, Any]) -> float:
        """Score an output payload for downstream selection logic."""
        pass


__all__ = ["UnifiedAgent"]
