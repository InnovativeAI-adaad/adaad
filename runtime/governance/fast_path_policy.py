# SPDX-License-Identifier: Apache-2.0
"""Operating mode and gate requirements policy."""

from __future__ import annotations

import os
from enum import Enum
from typing import Set

from runtime.governance.change_classifier import ChangeType


class OperatingMode(Enum):
    DEV_FAST = "dev_fast"
    GOVERNED_RELEASE = "governed_release"


def get_operating_mode() -> OperatingMode:
    """Resolve operating mode from environment or CLI flags."""
    # Default to DEV_FAST locally, GOVERNED_RELEASE in CI
    is_ci = os.getenv("CI", "false").lower() == "true"
    fast_flag = os.getenv("ADAAD_FAST_MODE", "false").lower() == "true"
    
    if is_ci or not fast_flag:
        return OperatingMode.GOVERNED_RELEASE
    return OperatingMode.DEV_FAST


def get_required_gate_tiers(mode: OperatingMode, change_type: ChangeType) -> Set[int]:
    """Map mode and change type to mandatory gate tiers (0, 1, 2, 3)."""
    if mode == OperatingMode.GOVERNED_RELEASE:
        return {0, 1, 2, 3}
    
    # DEV_FAST Path
    if change_type == ChangeType.NON_FUNCTIONAL:
        # Docs/comments only: Skip tests, mutation, and replay.
        # Still require Tier 0 (static checks like schema/arch) for basic health.
        return {0}
    
    # Functional changes in DEV_FAST: Standard stack minus documentation evidence (T3)
    return {0, 1}


def should_skip_gate(gate_name: str, tier: int, mode: OperatingMode, change_type: ChangeType) -> bool:
    """Return True if a specific gate should be bypassed under the current policy."""
    required_tiers = get_required_gate_tiers(mode, change_type)
    
    if tier not in required_tiers:
        return True
        
    # Progressive Hardening: high-risk paths always require full stack
    # (implemented in orchestrator/gate logic)
    return False


__all__ = ["OperatingMode", "get_operating_mode", "get_required_gate_tiers", "should_skip_gate"]
