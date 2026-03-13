# SPDX-License-Identifier: Apache-2.0
"""Path guard utilities for agent-scoped mutation targets."""

from __future__ import annotations

from pathlib import Path


class AgentPathEscapeError(ValueError):
    """Raised when a candidate path escapes the governed agent root."""

    reason_code = "path_outside_agent_root"

    def __init__(self, candidate: str) -> None:
        super().__init__(f"{self.reason_code}:{candidate}")
        self.candidate = candidate


def resolve_agent_scoped_path(agent_dir: Path, candidate: str | Path) -> Path:
    """Resolve a candidate path and ensure it is contained under ``agent_dir``."""
    root = agent_dir.resolve()
    candidate_path = Path(candidate)
    if candidate_path.is_absolute():
        raise AgentPathEscapeError(str(candidate_path))

    resolved = (root / candidate_path).resolve()
    if not resolved.is_relative_to(root):
        raise AgentPathEscapeError(str(candidate_path))
    return resolved


__all__ = ["AgentPathEscapeError", "resolve_agent_scoped_path"]
