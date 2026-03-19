# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from security.whaledic_secrets import enforce_whaledic_secret_policy, redact_secret


def test_redact_secret_never_returns_raw_value() -> None:
    secret = "sk-live-abcdefghijklmnopqrstuvwxyz"
    masked = redact_secret(secret)
    assert masked != secret
    assert masked.startswith("sk-l")
    assert masked.endswith("yz")


def test_startup_fails_closed_when_dork_secret_missing() -> None:
    env = {"ADAAD_WHALEDIC_DORK_ENABLED": "1"}
    with pytest.raises(RuntimeError, match="whaledic_secret_missing_required"):
        enforce_whaledic_secret_policy(env)


def test_plaintext_env_fallback_is_forbidden() -> None:
    env = {
        "ADAAD_WHALEDIC_DORK_ENABLED": "1",
        "ADAAD_WHALEDIC_ANTHROPIC_API_KEY": "plaintext-not-allowed",
    }
    with pytest.raises(RuntimeError, match="plaintext_secret_env_forbidden"):
        enforce_whaledic_secret_policy(env)


def test_encrypted_env_secret_loads_and_reports_only_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "security.whaledic_secrets._decrypt_fernet_payload",
        lambda token, fernet_key: "sk-mobile-whaledic-secret",
    )
    env = {
        "ADAAD_WHALEDIC_DORK_ENABLED": "1",
        "ADAAD_SECRETS_FERNET_KEY": "dummy-key",
        "ADAAD_WHALEDIC_ANTHROPIC_API_KEY_ENC": "fernet:encrypted-token",
    }

    result = enforce_whaledic_secret_policy(env)

    assert result.anthropic_key_available is True
    assert result.anthropic_key_redacted is not None
    assert "sk-mobile-whaledic-secret" not in result.anthropic_key_redacted


def test_invalid_encrypted_payload_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_token: str, *, fernet_key: str) -> str:
        raise RuntimeError("whaledic_secret_invalid_encrypted_payload")

    monkeypatch.setattr("security.whaledic_secrets._decrypt_fernet_payload", _raise)

    env = {
        "ADAAD_WHALEDIC_DORK_ENABLED": "1",
        "ADAAD_SECRETS_FERNET_KEY": "dummy-key",
        "ADAAD_WHALEDIC_ANTHROPIC_API_KEY_ENC": "fernet:not-a-valid-token",
    }
    with pytest.raises(RuntimeError, match="whaledic_secret_invalid_encrypted_payload"):
        enforce_whaledic_secret_policy(env)


def test_keyring_backed_retrieval_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("security.whaledic_secrets._keyring_get_password", lambda _svc, _usr: "ledger-token-from-keyring")
    env = {
        "ADAAD_WHALEDIC_LEDGER_AUTH_ENABLED": "true",
        "ADAAD_WHALEDIC_LEDGER_API_TOKEN_KEYRING": "adaad.whaledic:ledger_api",
    }

    result = enforce_whaledic_secret_policy(env)

    assert result.ledger_token_available is True
    assert result.ledger_token_redacted is not None
    assert "ledger-token-from-keyring" not in result.ledger_token_redacted
