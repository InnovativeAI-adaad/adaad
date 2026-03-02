# SPDX-License-Identifier: Apache-2.0
"""Fail-closed verification for boot-critical signed artifacts."""

from __future__ import annotations

from pathlib import Path

from runtime.governance.policy_artifact import GovernancePolicyError, load_governance_policy


def verify_required_artifacts() -> dict[str, str]:
    checks: dict[str, str] = {}
    policy_path = Path("governance/governance_policy_v1.json")
    try:
        policy = load_governance_policy(policy_path)
    except (GovernancePolicyError, FileNotFoundError, ValueError) as exc:
        raise ValueError(f"governance_policy:{exc}") from exc
    checks["governance_policy"] = policy.fingerprint
    return checks

