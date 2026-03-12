# SPDX-License-Identifier: Apache-2.0
"""Phase 23 — Container Isolation as production default

PR-23-01  _container_rollout_enabled() defaults True (opt-out model)
PR-23-02  Explicit opt-out values disable container isolation
PR-23-03  _default_isolation_backend() returns ContainerIsolationBackend in SANDBOX tier
PR-23-04  _default_isolation_backend() returns ProcessIsolationBackend when opted out
PR-23-05  Non-SANDBOX tier always uses ProcessIsolationBackend regardless of rollout flag
PR-23-06  runtime_hardening_capabilities reflects enabled state for default config
PR-23-07  Any unrecognised/truthy value for ADAAD_SANDBOX_CONTAINER_ROLLOUT enables container
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

# We reload executor to pick up monkeypatched env vars cleanly
import runtime.sandbox.executor as _executor_module
from runtime.sandbox.isolation import (
    ContainerIsolationBackend,
    ProcessIsolationBackend,
    runtime_hardening_capabilities,
)

pytestmark = pytest.mark.autonomous_critical


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rollout_enabled(env_val: str | None) -> bool:
    """Test _container_rollout_enabled() by calling it directly with env patched."""
    import runtime.sandbox.executor as _mod
    if env_val is None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ADAAD_SANDBOX_CONTAINER_ROLLOUT", None)
            return _mod._container_rollout_enabled()
    with patch.dict(os.environ, {"ADAAD_SANDBOX_CONTAINER_ROLLOUT": env_val}):
        return _mod._container_rollout_enabled()


def _default_backend(*, rollout: str | None, tier: str = "SANDBOX"):
    """Test _default_isolation_backend() with env patched inline."""
    import runtime.sandbox.executor as _mod

    env_patch = {"ADAAD_FORCE_TIER": tier}
    if rollout is not None:
        env_patch["ADAAD_SANDBOX_CONTAINER_ROLLOUT"] = rollout
    save_rollout = os.environ.pop("ADAAD_SANDBOX_CONTAINER_ROLLOUT", None)
    save_tier = os.environ.pop("ADAAD_FORCE_TIER", None)
    try:
        with patch.dict(os.environ, env_patch):
            if rollout is None:
                os.environ.pop("ADAAD_SANDBOX_CONTAINER_ROLLOUT", None)
            return _mod._default_isolation_backend()
    finally:
        if save_rollout is not None:
            os.environ["ADAAD_SANDBOX_CONTAINER_ROLLOUT"] = save_rollout
        if save_tier is not None:
            os.environ["ADAAD_FORCE_TIER"] = save_tier


# ---------------------------------------------------------------------------
# PR-23-01 — default is True (no env var set)
# ---------------------------------------------------------------------------

def test_pr23_01_default_container_rollout_is_true():
    result = _rollout_enabled(None)
    assert result is True


# ---------------------------------------------------------------------------
# PR-23-02 — explicit opt-out values disable container isolation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("val", ["off", "false", "0", "no", "disabled"])
def test_pr23_02_explicit_opt_out_disables_container(val):
    result = _rollout_enabled(val)
    assert result is False


# ---------------------------------------------------------------------------
# PR-23-03 — SANDBOX tier + rollout enabled → ContainerIsolationBackend
# ---------------------------------------------------------------------------

def test_pr23_03_sandbox_tier_default_returns_container_backend():
    backend = _default_backend(rollout=None, tier="SANDBOX")
    assert isinstance(backend, ContainerIsolationBackend)


# ---------------------------------------------------------------------------
# PR-23-04 — SANDBOX tier + opt-out → ProcessIsolationBackend
# ---------------------------------------------------------------------------

def test_pr23_04_sandbox_tier_opted_out_returns_process_backend():
    backend = _default_backend(rollout="off", tier="SANDBOX")
    assert isinstance(backend, ProcessIsolationBackend)


# ---------------------------------------------------------------------------
# PR-23-05 — Non-SANDBOX tier always uses ProcessIsolationBackend
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tier", ["PRODUCTION", "STAGING", "DEV"])
def test_pr23_05_non_sandbox_tier_uses_process_backend(tier):
    backend = _default_backend(rollout=None, tier=tier)
    assert isinstance(backend, ProcessIsolationBackend)


# ---------------------------------------------------------------------------
# PR-23-06 — runtime_hardening_capabilities reflects enabled for default config
# ---------------------------------------------------------------------------

def test_pr23_06_hardening_capabilities_enabled_by_default():
    caps = runtime_hardening_capabilities(container_rollout_enabled=True)
    assert caps["kernel_seccomp_filter_enforcement"]["implemented"] is True
    assert caps["kernel_seccomp_filter_enforcement"]["status"] == "enabled"
    assert caps["namespace_cgroup_hard_isolation"]["implemented"] is True
    assert caps["namespace_cgroup_hard_isolation"]["status"] == "enabled"


# ---------------------------------------------------------------------------
# PR-23-07 — unrecognised / truthy values enable container isolation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("val", ["1", "true", "on", "docker", "yes", "TRUE"])
def test_pr23_07_truthy_values_enable_container(val):
    result = _rollout_enabled(val)
    assert result is True
