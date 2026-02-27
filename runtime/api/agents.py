# SPDX-License-Identifier: Apache-2.0
"""Approved runtime facade for legacy agent and mutation entrypoints.

This module intentionally lazily resolves exports to avoid circular imports
between runtime/api and runtime/evolution modules during startup.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "agent_path_from_id": ("app.agents.discovery", "agent_path_from_id"),
    "iter_agent_dirs": ("app.agents.discovery", "iter_agent_dirs"),
    "resolve_agent_id": ("app.agents.discovery", "resolve_agent_id"),
    "MutationEngine": ("app.agents.mutation_engine", "MutationEngine"),
    "MutationRequest": ("app.agents.mutation_request", "MutationRequest"),
    "MutationTarget": ("app.agents.mutation_request", "MutationTarget"),
    "adapt_generated_request_payload": ("app.agents.mutation_strategies", "adapt_generated_request_payload"),
    "load_skill_weights": ("app.agents.mutation_strategies", "load_skill_weights"),
    "select_strategy": ("app.agents.mutation_strategies", "select_strategy"),
}

__all__ = sorted(_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
