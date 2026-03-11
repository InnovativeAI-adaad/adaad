# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.governance_gate

from pathlib import Path

from runtime.director import GovernanceDeniedError, RuntimeDirector
from runtime.governance.policy_adapter import GovernancePolicyAdapter


def _write_policy(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_policy_adapter_allows_privileged_operation_for_production_tier(tmp_path: Path) -> None:
    base = _write_policy(
        tmp_path / "base.rego",
        "package adaad.governance\ndefault allow = false\nallow { input.actor_tier == \"production\" }\n",
    )
    adapter = GovernancePolicyAdapter(policy_paths=[base])

    decision = adapter.evaluate({"operation": "mutation.apply", "actor": "sample_agent", "actor_tier": "production", "fail_closed": False})

    assert decision.allowed is True
    assert decision.decision == "allow"


def test_policy_adapter_denies_insufficient_tier(tmp_path: Path) -> None:
    base = _write_policy(
        tmp_path / "base.rego",
        "package adaad.governance\ndefault allow = false\nallow { input.actor_tier == \"production\" }\n",
    )
    adapter = GovernancePolicyAdapter(policy_paths=[base])

    decision = adapter.evaluate({"operation": "mutation.apply", "actor": "test_subject", "actor_tier": "stable", "fail_closed": False})

    assert decision.allowed is False
    assert decision.reason == "insufficient_tier"


def test_policy_overlay_precedence_supports_override(tmp_path: Path) -> None:
    base = _write_policy(
        tmp_path / "base.rego",
        "package adaad.governance\ndefault allow = false\nallow { input.actor_tier == \"production\" }\n",
    )
    overlay = _write_policy(
        tmp_path / "overlay.rego",
        "package adaad.governance\ndefault allow = false\nallow { input.emergency_override == true }\n",
    )
    adapter = GovernancePolicyAdapter(policy_paths=[base, overlay])

    decision = adapter.evaluate(
        {
            "operation": "mutation.apply",
            "actor": "test_subject",
            "actor_tier": "stable",
            "fail_closed": False,
            "emergency_override": True,
            "override_token_verified": True,
        }
    )

    assert decision.allowed is True
    assert decision.reason == "emergency_override"


def test_policy_adapter_fail_closed_when_bundle_missing(tmp_path: Path) -> None:
    adapter = GovernancePolicyAdapter(policy_paths=[tmp_path / "missing.rego"])

    decision = adapter.evaluate({"operation": "mutation.apply", "actor": "sample_agent", "actor_tier": "production", "fail_closed": False})

    assert decision.allowed is False
    assert decision.reason.startswith("policy_unavailable")


def test_runtime_director_denies_when_policy_engine_unavailable(tmp_path: Path) -> None:
    adapter = GovernancePolicyAdapter(policy_paths=[tmp_path / "missing.rego"])
    director = RuntimeDirector(policy_adapter=adapter)

    try:
        director.execute_privileged(
            "mutation.apply",
            {"actor": "sample_agent", "actor_tier": "production", "fail_closed": False},
            lambda: "ok",
        )
    except GovernanceDeniedError as exc:
        assert "policy_unavailable" in str(exc)
    else:
        raise AssertionError("expected governance denial")
