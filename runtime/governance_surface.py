# SPDX-License-Identifier: Apache-2.0
"""Governance surface registry for deterministic hashing and runtime lock controls."""

from __future__ import annotations

import os
from typing import Any, Mapping

# Explicit digest surface for governance envelope details.
CANONICAL_DETAIL_WHITELIST = frozenset(
    {
        "ok",
        "reason",
        "validator",
        "details",
        "proposal_id",
        "strategy_score",
        "critique_score",
        "agent_id",
        "proposal_hash",
        "bounds_policy_version",
    }
)

# Runtime-only fields that must never impact replay envelope digests.
VOLATILE_DETAIL_KEYS = frozenset(
    {
        "window_start_ts",
        "window_end_ts",
        "resource_usage_snapshot",
        "limits_snapshot",
        "platform_telemetry",
        "observed_measurements",
        "count",
        "rate_per_hour",
        "entries_considered",
        "entries_scoped",
        "event_types",
        "scope",
        "source",
    }
)


def deterministic_lock_enabled() -> bool:
    return os.getenv("ADAAD_DETERMINISTIC_LOCK", "").strip().lower() in {"1", "true", "yes", "on"}


def canonicalize_governance_details(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if key_s in VOLATILE_DETAIL_KEYS:
                continue
            if key_s in CANONICAL_DETAIL_WHITELIST or key_s.startswith("detail_"):
                cleaned[key_s] = canonicalize_governance_details(item)
            elif isinstance(item, Mapping):
                nested = canonicalize_governance_details(item)
                if nested:
                    cleaned[key_s] = nested
            elif isinstance(item, list):
                cleaned[key_s] = [canonicalize_governance_details(i) for i in item]
        return cleaned
    if isinstance(value, list):
        return [canonicalize_governance_details(item) for item in value]
    return value


__all__ = [
    "CANONICAL_DETAIL_WHITELIST",
    "VOLATILE_DETAIL_KEYS",
    "canonicalize_governance_details",
    "deterministic_lock_enabled",
]
