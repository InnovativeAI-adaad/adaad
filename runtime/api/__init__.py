# SPDX-License-Identifier: Apache-2.0
"""Public runtime facade package for approved external entrypoints.

Lazy exports are used to avoid cross-layer import cycles in replay/governance
and orchestration modules.
"""

from __future__ import annotations

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
    "extension_sdk_descriptor": ("runtime.api.extensions", "extension_sdk_descriptor"),
}

__all__ = sorted(_EXPORTS.keys())


def _resolve_module(module_name: str) -> Any:
    # lint:fix forbidden_dynamic_execution — explicit module routing — governance-reviewed
    if module_name == "runtime.api.agents":
        from runtime.api import agents as module

        return module
    if module_name == "runtime.api.legacy_modes":
        from runtime.api import legacy_modes as module

        return module
    if module_name == "runtime.api.mutation":
        from runtime.api import mutation as module

        return module
    if module_name == "runtime.api.extensions":
        from runtime.api import extensions as module

        return module
    raise ModuleNotFoundError(module_name)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = _resolve_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
