# SPDX-License-Identifier: Apache-2.0
"""Narrow orchestration surface for policy-gated privileged runtime actions."""

from __future__ import annotations

from typing import Any, Callable, Mapping, TypeVar

from runtime.governance.policy_adapter import GovernancePolicyAdapter


T = TypeVar("T")


class GovernanceDeniedError(RuntimeError):
    """Raised when governance policy blocks a privileged runtime operation."""


class RuntimeDirector:
    """Coordinates privileged calls through governance policy checks."""

    def __init__(self, policy_adapter: GovernancePolicyAdapter | None = None) -> None:
        self.policy_adapter = policy_adapter or GovernancePolicyAdapter()

    def execute_privileged(
        self,
        operation: str,
        context: Mapping[str, Any],
        action: Callable[[], T],
    ) -> T:
        payload = {
            "operation": operation,
            "actor": str(context.get("actor", "system")),
            "actor_tier": str(context.get("actor_tier", "stable")),
            "fail_closed": bool(context.get("fail_closed", False)),
            "emergency_override": bool(context.get("emergency_override", False)),
            "override_token_verified": bool(context.get("override_token_verified", False)),
        }
        decision = self.policy_adapter.evaluate(payload)
        if not decision.allowed:
            raise GovernanceDeniedError(f"governance_denied:{operation}:{decision.reason}")
        return action()


__all__ = ["GovernanceDeniedError", "RuntimeDirector"]
