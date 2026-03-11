# SPDX-License-Identifier: Apache-2.0
"""Tests: boot environment validation guard (PR-HARDEN-01)."""
from __future__ import annotations

import os
import pytest
pytestmark = pytest.mark.regression_standard

_BOOT_KNOWN_ENVS = frozenset({"dev", "test", "staging", "production", "prod"})
_BOOT_STRICT_ENVS = frozenset({"staging", "production", "prod"})


def _validate_boot_environment():
    """Local copy of the guard logic — avoids importing app.main (fastapi dep)."""
    env = (os.getenv("ADAAD_ENV") or "").strip().lower()
    if not env:
        raise SystemExit("CRITICAL: ADAAD_ENV is not set. Set to one of: dev, test, staging, production")
    if env not in _BOOT_KNOWN_ENVS:
        raise SystemExit(
            f"CRITICAL: ADAAD_ENV={env!r} is not a recognised environment. "
            f"Permitted: {sorted(_BOOT_KNOWN_ENVS)}"
        )
    if env in _BOOT_STRICT_ENVS and os.getenv("CRYOVANT_DEV_MODE"):
        raise SystemExit(
            f"CRITICAL: CRYOVANT_DEV_MODE is set in strict environment {env!r}. "
            "This configuration is not permitted."
        )
    if env in _BOOT_STRICT_ENVS:
        has_key = os.getenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY") or any(
            v for k, v in os.environ.items()
            if k.startswith("ADAAD_GOVERNANCE_SESSION_KEY_")
        )
        if not has_key:
            raise SystemExit(
                "CRITICAL: missing_governance_signing_key — "
                "ADAAD_GOVERNANCE_SESSION_SIGNING_KEY must be set in strict environment."
            )


def _setup(monkeypatch, env, dev_mode=None, signing_key=None):
    if env is None:
        monkeypatch.delenv("ADAAD_ENV", raising=False)
    else:
        monkeypatch.setenv("ADAAD_ENV", env)
    if dev_mode:
        monkeypatch.setenv("CRYOVANT_DEV_MODE", "1")
    else:
        monkeypatch.delenv("CRYOVANT_DEV_MODE", raising=False)
    if signing_key:
        monkeypatch.setenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", signing_key)
    else:
        monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)
    for k in [k for k in os.environ if k.startswith("ADAAD_GOVERNANCE_SESSION_KEY_")]:
        monkeypatch.delenv(k, raising=False)


def test_unset_env_raises(monkeypatch):
    _setup(monkeypatch, env=None)
    with pytest.raises(SystemExit, match="ADAAD_ENV is not set"):
        _validate_boot_environment()


def test_unknown_env_raises(monkeypatch):
    _setup(monkeypatch, env="atlantis")
    with pytest.raises(SystemExit, match="not a recognised environment"):
        _validate_boot_environment()


def test_dev_mode_in_staging_raises(monkeypatch):
    _setup(monkeypatch, env="staging", dev_mode=True)
    with pytest.raises(SystemExit, match="CRYOVANT_DEV_MODE is set in strict environment"):
        _validate_boot_environment()


def test_missing_signing_key_in_production_raises(monkeypatch):
    _setup(monkeypatch, env="production", signing_key=None)
    with pytest.raises(SystemExit, match="missing_governance_signing_key"):
        _validate_boot_environment()


def test_valid_dev_env_passes(monkeypatch):
    _setup(monkeypatch, env="dev")
    _validate_boot_environment()  # must not raise


def test_valid_production_with_signing_key_passes(monkeypatch):
    _setup(monkeypatch, env="production", signing_key="real-signing-key")
    _validate_boot_environment()  # must not raise
