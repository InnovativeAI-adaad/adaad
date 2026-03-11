# SPDX-License-Identifier: Apache-2.0
"""Tests for strict-env signing key enforcement in cryovant."""

import time

import pytest
pytestmark = pytest.mark.regression_standard

from security.cryovant import (
    MissingSigningKeyError,
    _resolve_hmac_secret,
    sign_governance_token,
    verify_governance_token,
)


@pytest.mark.parametrize("env", ["staging", "production", "prod"])
def test_resolve_hmac_secret_raises_in_strict_env_when_keys_absent(monkeypatch: pytest.MonkeyPatch, env: str) -> None:
    monkeypatch.setenv("ADAAD_ENV", env)
    monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)
    monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_KEY_TEST", raising=False)
    with pytest.raises(MissingSigningKeyError, match="strict_env"):
        _resolve_hmac_secret(
            key_id="test",
            specific_env_prefix="ADAAD_GOVERNANCE_SESSION_KEY_",
            generic_env_var="ADAAD_GOVERNANCE_SESSION_SIGNING_KEY",
            fallback_namespace="adaad-governance-session-dev-secret",
        )


def test_resolve_hmac_secret_returns_fallback_in_dev_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)
    assert (
        _resolve_hmac_secret(
            key_id="k1",
            specific_env_prefix="ADAAD_GOVERNANCE_SESSION_KEY_",
            generic_env_var="ADAAD_GOVERNANCE_SESSION_SIGNING_KEY",
            fallback_namespace="adaad-governance-session-dev-secret",
        )
        == "adaad-governance-session-dev-secret:k1"
    )


@pytest.mark.parametrize("env", ["staging", "production", "prod"])
def test_verify_governance_token_raises_in_strict_env_when_keys_absent(monkeypatch: pytest.MonkeyPatch, env: str) -> None:
    monkeypatch.setenv("ADAAD_ENV", env)
    monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)
    future = int(time.time()) + 3600
    token = f"cryovant-gov-v1:k1:{future}:nonce123:sha256:{'a'*64}"
    with pytest.raises(MissingSigningKeyError):
        verify_governance_token(token)


def test_round_trip_with_explicit_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", "supersecretkey")
    monkeypatch.setenv("ADAAD_ENV", "dev")
    future = int(time.time()) + 3600
    token = sign_governance_token(key_id="k1", expires_at=future, nonce="abc123")
    assert verify_governance_token(token)


@pytest.mark.parametrize("env", ["staging", "production", "prod"])
def test_verify_governance_token_propagates_missing_key_error_not_false(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("ADAAD_ENV", env)
    monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)
    future = int(time.time()) + 3600
    token = f"cryovant-gov-v1:k1:{future}:nonce123:sha256:{'a' * 64}"
    with pytest.raises(MissingSigningKeyError, match="strict_env"):
        verify_governance_token(token)


# --- PR-HARDEN-01 additions ---

def test_env_mode_raises_for_unknown_adaad_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "jupiter")
    from importlib import reload
    import security.cryovant as cryovant
    reload(cryovant)
    with pytest.raises(RuntimeError, match="adaad_env_unknown"):
        cryovant.env_mode()


def test_verify_session_raises_in_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "staging")
    monkeypatch.delenv("CRYOVANT_DEV_MODE", raising=False)
    from importlib import reload
    import security.cryovant as cryovant
    reload(cryovant)
    with pytest.raises(cryovant.GovernanceTokenError, match="strict_env"):
        cryovant.verify_session("any-token")


def test_signature_valid_blocks_dev_sig_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "production")
    monkeypatch.delenv("CRYOVANT_DEV_MODE", raising=False)
    from importlib import reload
    import security.cryovant as cryovant
    reload(cryovant)
    assert not cryovant.signature_valid("cryovant-dev-some-sig")
