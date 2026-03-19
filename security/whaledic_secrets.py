# SPDX-License-Identifier: Apache-2.0
"""Whale.Dic secret loading for dork + ledger APIs.

Security goals:
- Never allow plaintext secrets committed in repository-backed config files.
- Support encrypted environment blobs and OS keyring retrieval.
- Fail closed when required secrets are missing/invalid.
"""

from __future__ import annotations

import base64
import importlib
import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class SecretPolicyResult:
    anthropic_key_available: bool
    ledger_token_available: bool
    anthropic_key_redacted: str | None
    ledger_token_redacted: str | None


def _env_true(env: Mapping[str, str], key: str) -> bool:
    return str(env.get(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def redact_secret(secret: str) -> str:
    value = (secret or "").strip()
    if not value:
        return "[REDACTED:empty]"
    if len(value) <= 6:
        return "[REDACTED:short]"
    return f"{value[:4]}...{value[-2:]}"


def _decrypt_fernet_payload(token: str, *, fernet_key: str) -> str:
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("whaledic_secret_backend_unavailable:cryptography") from exc

    try:
        fernet = Fernet(fernet_key.encode("utf-8"))
        decrypted = fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except (ValueError, InvalidToken) as exc:
        raise RuntimeError("whaledic_secret_invalid_encrypted_payload") from exc
    if not decrypted.strip():
        raise RuntimeError("whaledic_secret_invalid_empty_after_decrypt")
    return decrypted.strip()


def _load_from_encrypted_env(*, env: Mapping[str, str], encrypted_var: str) -> str | None:
    payload = str(env.get(encrypted_var, "")).strip()
    if not payload:
        return None

    if payload.startswith("fernet:"):
        payload = payload.split(":", 1)[1].strip()

    fernet_key = str(env.get("ADAAD_SECRETS_FERNET_KEY", "")).strip()
    if not fernet_key:
        raise RuntimeError("whaledic_secret_missing_fernet_key")
    return _decrypt_fernet_payload(payload, fernet_key=fernet_key)


def _keyring_get_password(service_name: str, username: str) -> str | None:
    if importlib.util.find_spec("keyring") is None:
        raise RuntimeError("whaledic_secret_backend_unavailable:keyring")
    import keyring  # type: ignore

    return keyring.get_password(service_name, username)


def _load_from_keyring_ref(*, env: Mapping[str, str], keyring_ref_var: str) -> str | None:
    ref = str(env.get(keyring_ref_var, "")).strip()
    if not ref:
        return None

    if ":" not in ref:
        raise RuntimeError(f"whaledic_secret_invalid_keyring_ref:{keyring_ref_var}")
    service_name, username = ref.split(":", 1)
    service_name = service_name.strip()
    username = username.strip()
    if not service_name or not username:
        raise RuntimeError(f"whaledic_secret_invalid_keyring_ref:{keyring_ref_var}")

    secret = _keyring_get_password(service_name, username)
    if secret is None or not str(secret).strip():
        raise RuntimeError(f"whaledic_secret_missing_in_keyring:{keyring_ref_var}")
    return str(secret).strip()


def _decode_prefixed_payload(payload: str) -> str:
    if payload.startswith("b64:"):
        try:
            return base64.b64decode(payload.split(":", 1)[1].encode("utf-8")).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("whaledic_secret_invalid_b64_payload") from exc
    return payload


def _load_secret(
    *,
    env: Mapping[str, str],
    plaintext_env_var: str,
    encrypted_env_var: str,
    keyring_ref_var: str,
    required: bool,
) -> str | None:
    plaintext = str(env.get(plaintext_env_var, "")).strip()
    if plaintext:
        raise RuntimeError(f"plaintext_secret_env_forbidden:{plaintext_env_var}")

    encrypted_secret = _load_from_encrypted_env(env=env, encrypted_var=encrypted_env_var)
    keyring_secret = _load_from_keyring_ref(env=env, keyring_ref_var=keyring_ref_var)

    choices = [s for s in (encrypted_secret, keyring_secret) if s is not None]
    if len(choices) > 1:
        raise RuntimeError(f"whaledic_secret_multiple_sources:{encrypted_env_var}:{keyring_ref_var}")

    secret = choices[0] if choices else None
    if secret is not None:
        secret = _decode_prefixed_payload(secret).strip()

    if required and not secret:
        raise RuntimeError(f"whaledic_secret_missing_required:{encrypted_env_var}:{keyring_ref_var}")

    return secret


def enforce_whaledic_secret_policy(env: Mapping[str, str] | None = None) -> SecretPolicyResult:
    scope = env if env is not None else os.environ

    require_dork_secret = _env_true(scope, "ADAAD_WHALEDIC_DORK_ENABLED")
    require_ledger_secret = _env_true(scope, "ADAAD_WHALEDIC_LEDGER_AUTH_ENABLED")

    anthropic_secret = _load_secret(
        env=scope,
        plaintext_env_var="ADAAD_WHALEDIC_ANTHROPIC_API_KEY",
        encrypted_env_var="ADAAD_WHALEDIC_ANTHROPIC_API_KEY_ENC",
        keyring_ref_var="ADAAD_WHALEDIC_ANTHROPIC_API_KEY_KEYRING",
        required=require_dork_secret,
    )
    ledger_token = _load_secret(
        env=scope,
        plaintext_env_var="ADAAD_WHALEDIC_LEDGER_API_TOKEN",
        encrypted_env_var="ADAAD_WHALEDIC_LEDGER_API_TOKEN_ENC",
        keyring_ref_var="ADAAD_WHALEDIC_LEDGER_API_TOKEN_KEYRING",
        required=require_ledger_secret,
    )

    return SecretPolicyResult(
        anthropic_key_available=bool(anthropic_secret),
        ledger_token_available=bool(ledger_token),
        anthropic_key_redacted=redact_secret(anthropic_secret) if anthropic_secret else None,
        ledger_token_redacted=redact_secret(ledger_token) if ledger_token else None,
    )


__all__ = [
    "SecretPolicyResult",
    "enforce_whaledic_secret_policy",
    "redact_secret",
]
