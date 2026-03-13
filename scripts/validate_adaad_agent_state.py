#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate `.adaad_agent_state.json` presence and schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = REPO_ROOT / ".adaad_agent_state.json"
REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "last_completed_pr",
    "next_pr",
    "active_phase",
    "last_invocation",
    "blocked_reason",
    "blocked_at_gate",
    "blocked_at_tier",
    "last_gate_results",
    "open_findings",
    "value_checkpoints_reached",
    "pending_evidence_rows",
}
ALLOWED_GATE_RESULTS = {"pass", "fail", "not_run", "not_applicable"}


def _validate_state(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS.difference(payload.keys()))
    if missing:
        errors.append(f"missing_keys:{','.join(missing)}")

    if payload.get("schema_version") != "1.5.0":
        errors.append("schema_version:expected_1.5.0")

    for key in ("last_completed_pr", "next_pr", "active_phase"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key}:expected_non_empty_string")

    for key in ("blocked_reason", "blocked_at_gate", "blocked_at_tier", "last_invocation"):
        value = payload.get(key)
        if value is not None and not isinstance(value, str):
            errors.append(f"{key}:expected_string_or_null")

    gate_results = payload.get("last_gate_results")
    if not isinstance(gate_results, dict):
        errors.append("last_gate_results:expected_object")
    else:
        for tier in ("tier_0", "tier_1", "tier_2", "tier_3"):
            value = gate_results.get(tier)
            if value not in ALLOWED_GATE_RESULTS:
                errors.append(f"last_gate_results.{tier}:invalid_status")

    for key in ("open_findings", "value_checkpoints_reached", "pending_evidence_rows"):
        value = payload.get(key)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            errors.append(f"{key}:expected_list_of_non_empty_strings")

    return errors


def main() -> int:
    if not STATE_PATH.exists():
        print("adaad_agent_state_validation:failed:missing_file")
        return 1

    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"adaad_agent_state_validation:failed:read_error:{exc}")
        return 1

    if not isinstance(payload, dict):
        print("adaad_agent_state_validation:failed:root_must_be_object")
        return 1

    errors = _validate_state(payload)
    if errors:
        print("adaad_agent_state_validation:failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print("adaad_agent_state_validation:ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
