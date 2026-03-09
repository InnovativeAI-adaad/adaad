# SPDX-License-Identifier: Apache-2.0
"""
Tests for Constitution v0.6.0 — bandit_arm_integrity_invariant (Phase 11-A PR-11-A-03).

Test IDs: T11-C-01 through T11-C-03
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.constitution import VALIDATOR_REGISTRY, CONSTITUTION_VERSION


def _run_validator(state: dict | None, *, env_overrides: dict | None = None) -> dict:
    """Run the bandit_arm_integrity_invariant validator with the given arm state."""
    validator_fn = VALIDATOR_REGISTRY["bandit_arm_integrity_invariant"]

    # Build a mock MutationRequest (validator ignores it)
    from unittest.mock import MagicMock
    req = MagicMock()

    env = {}
    if state is not None:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False, encoding="utf-8"
        )
        json.dump(state, tmp)
        tmp.flush()
        tmp.close()
        env["ADAAD_BANDIT_STATE_PATH"] = tmp.name
    else:
        # Ensure non-existent path
        env["ADAAD_BANDIT_STATE_PATH"] = "/tmp/adaad_no_bandit_state_should_not_exist_xyz.json"

    if env_overrides:
        env.update(env_overrides)

    with patch.dict("os.environ", env, clear=False):
        return validator_fn(req)


# ---------------------------------------------------------------------------
# T11-C-01: Non-negative arm stats pass the validator
# ---------------------------------------------------------------------------

def test_t11_c_01_valid_arm_stats_pass():
    """T11-C-01: Arm stats with non-negative values and no consecutive violation pass."""
    state = {
        "strategy": "ucb1",
        "arms": {
            "architect": {
                "pull_count": 5, "reward_mass": 3.5, "loss_mass": 1.5,
                "consecutive_recommendations": 3
            },
            "dream": {
                "pull_count": 3, "reward_mass": 1.8, "loss_mass": 1.2,
                "consecutive_recommendations": 0
            },
            "beast": {
                "pull_count": 4, "reward_mass": 2.0, "loss_mass": 2.0,
                "consecutive_recommendations": 0
            },
        }
    }
    result = _run_validator(state)
    assert result["ok"] is True
    assert result["details"]["arm_stats_non_negative"] is True
    assert result["details"]["consecutive_epoch_cap_respected"] is True
    assert result["details"]["bandit_active"] is True


def test_t11_c_01b_absent_state_file_passes_advisory():
    """T11-C-01b: Absent state file passes with bandit_active=False (advisory pass)."""
    result = _run_validator(None)
    assert result["ok"] is True
    assert result["details"]["bandit_active"] is False


# ---------------------------------------------------------------------------
# T11-C-02: Consecutive epoch cap enforced
# ---------------------------------------------------------------------------

def test_t11_c_02_consecutive_violation_fails():
    """T11-C-02: Agent exceeding MAX_CONSECUTIVE_BANDIT_EPOCHS causes violation."""
    state = {
        "strategy": "ucb1",
        "arms": {
            "architect": {
                "pull_count": 15, "reward_mass": 12.0, "loss_mass": 3.0,
                "consecutive_recommendations": 11   # exceeds cap of 10
            },
            "dream": {
                "pull_count": 2, "reward_mass": 0.8, "loss_mass": 1.2,
                "consecutive_recommendations": 0
            },
            "beast": {
                "pull_count": 2, "reward_mass": 0.7, "loss_mass": 1.3,
                "consecutive_recommendations": 0
            },
        }
    }
    result = _run_validator(state)
    assert result["ok"] is False
    assert result["details"]["consecutive_epoch_cap_respected"] is False
    violations = result["details"]["consecutive_violations"]
    assert any(v["agent"] == "architect" for v in violations)


def test_t11_c_02b_custom_cap_via_env():
    """T11-C-02b: ADAAD_BANDIT_MAX_CONSECUTIVE_EPOCHS env var overrides cap."""
    state = {
        "strategy": "ucb1",
        "arms": {
            "architect": {
                "pull_count": 5, "reward_mass": 3.0, "loss_mass": 2.0,
                "consecutive_recommendations": 4  # exceeds cap of 3 but not cap of 10
            },
            "dream": {"pull_count": 1, "reward_mass": 0.5, "loss_mass": 0.5,
                      "consecutive_recommendations": 0},
            "beast": {"pull_count": 1, "reward_mass": 0.5, "loss_mass": 0.5,
                      "consecutive_recommendations": 0},
        }
    }
    # With cap=3, consecutive_recommendations=4 should fail
    result_strict = _run_validator(state, env_overrides={"ADAAD_BANDIT_MAX_CONSECUTIVE_EPOCHS": "3"})
    assert result_strict["ok"] is False

    # With cap=10 (default), consecutive_recommendations=4 should pass
    result_default = _run_validator(state, env_overrides={"ADAAD_BANDIT_MAX_CONSECUTIVE_EPOCHS": "10"})
    assert result_default["ok"] is True


# ---------------------------------------------------------------------------
# T11-C-03: Negative arm stats blocked
# ---------------------------------------------------------------------------

def test_t11_c_03_negative_reward_mass_fails():
    """T11-C-03: Negative reward_mass in any arm triggers arm_stats_non_negative failure."""
    state = {
        "strategy": "ucb1",
        "arms": {
            "architect": {
                "pull_count": 5, "reward_mass": -0.1,   # corrupted
                "loss_mass": 5.1, "consecutive_recommendations": 0
            },
            "dream": {"pull_count": 3, "reward_mass": 1.5, "loss_mass": 1.5,
                      "consecutive_recommendations": 0},
            "beast": {"pull_count": 2, "reward_mass": 1.0, "loss_mass": 1.0,
                      "consecutive_recommendations": 0},
        }
    }
    result = _run_validator(state)
    assert result["ok"] is False
    assert result["details"]["arm_stats_non_negative"] is False
    assert "architect" in result["details"]["negative_arms"]


def test_t11_c_03b_constitution_version_is_0_6_0():
    """T11-C-03b: CONSTITUTION_VERSION constant is 0.6.0 after Phase 11-A release."""
    assert CONSTITUTION_VERSION == "0.6.0"


def test_t11_c_03c_bandit_rule_in_registry():
    """T11-C-03c: VALIDATOR_REGISTRY contains bandit_arm_integrity_invariant entry."""
    assert "bandit_arm_integrity_invariant" in VALIDATOR_REGISTRY
    assert callable(VALIDATOR_REGISTRY["bandit_arm_integrity_invariant"])
