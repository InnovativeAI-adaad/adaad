# SPDX-License-Identifier: Apache-2.0
"""Public runtime facade package for approved external entrypoints.

Lazy exports are used to avoid cross-layer import cycles in replay/governance
and orchestration modules.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "MutationEngine": ("runtime.api.agents", "MutationEngine"),
    "MutationRequest": ("runtime.api.agents", "MutationRequest"),
    "MutationTarget": ("runtime.api.agents", "MutationTarget"),
    "adapt_generated_request_payload": ("runtime.api.agents", "adapt_generated_request_payload"),
    "agent_path_from_id": ("runtime.api.agents", "agent_path_from_id"),
    "iter_agent_dirs": ("runtime.api.agents", "iter_agent_dirs"),
    "load_skill_weights": ("runtime.api.agents", "load_skill_weights"),
    "resolve_agent_id": ("runtime.api.agents", "resolve_agent_id"),
    "select_strategy": ("runtime.api.agents", "select_strategy"),
    "BeastModeLoop": ("runtime.api.legacy_modes", "BeastModeLoop"),
    "DreamMode": ("runtime.api.legacy_modes", "DreamMode"),
    "MutationExecutor": ("runtime.api.mutation", "MutationExecutor"),
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
