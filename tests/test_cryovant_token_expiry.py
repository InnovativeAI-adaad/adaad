# SPDX-License-Identifier: Apache-2.0
"""Tests for governance token expiry enforcement."""

import time

import pytest
pytestmark = pytest.mark.regression_standard

from security.cryovant import MissingSigningKeyError, TokenExpiredError, sign_governance_token, verify_governance_token


def test_expired_token_raises_token_expired_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", "testkey")
    monkeypatch.setenv("ADAAD_ENV", "dev")
    past = int(time.time()) - 1
    token = sign_governance_token(key_id="k1", expires_at=past, nonce="nonce-exp")
    with pytest.raises(TokenExpiredError, match="governance_token_expired"):
        verify_governance_token(token)


def test_future_token_does_not_raise_expiry_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", "testkey")
    monkeypatch.setenv("ADAAD_ENV", "dev")
    future = int(time.time()) + 3600
    token = sign_governance_token(key_id="k1", expires_at=future, nonce="nonce-ok")
    assert verify_governance_token(token) is True


def test_token_expired_error_is_distinct_from_missing_key_error() -> None:
    assert not issubclass(TokenExpiredError, MissingSigningKeyError)
    assert not issubclass(MissingSigningKeyError, TokenExpiredError)


@pytest.mark.parametrize("env", ["staging", "production", "prod"])
def test_expired_token_raises_even_in_strict_envs(monkeypatch: pytest.MonkeyPatch, env: str) -> None:
    monkeypatch.setenv("ADAAD_ENV", env)
    monkeypatch.setenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", "strictkey")
    past = int(time.time()) - 60
    token = sign_governance_token(key_id="k2", expires_at=past, nonce="n1")
    with pytest.raises(TokenExpiredError):
        verify_governance_token(token)
