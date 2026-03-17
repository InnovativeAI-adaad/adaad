# SPDX-License-Identifier: Apache-2.0
import importlib

import pytest


def _call_outcome(func, *args, **kwargs):
    try:
        return ("return", func(*args, **kwargs))
    except Exception as exc:  # pragma: no cover - explicit parity assertion path
        return ("raise", type(exc), str(exc))


@pytest.mark.parametrize(
    ("env", "dev_mode", "legacy_flag", "token"),
    [
        ("dev", "1", "1", "dev-token"),
        ("dev", "0", "1", "dev-token"),
        ("production", "1", "1", "dev-token"),
        ("test", "1", "1", "dev-token"),
    ],
)
def test_verify_session_behavior_unchanged(monkeypatch: pytest.MonkeyPatch, env: str, dev_mode: str, legacy_flag: str, token: str) -> None:
    monkeypatch.setenv("ADAAD_ENV", env)
    monkeypatch.setenv("CRYOVANT_DEV_MODE", dev_mode)
    monkeypatch.setenv("ADAAD_ENABLE_LEGACY_VERIFY_SESSION", legacy_flag)
    monkeypatch.setenv("CRYOVANT_DEV_TOKEN", "dev-token")

    shim = importlib.import_module("security.cryovant")
    legacy = importlib.import_module("security.cryovant_legacy")

    assert _call_outcome(shim.verify_session, token) == _call_outcome(legacy.verify_session, token)


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda legacy: legacy.sign_governance_token(key_id="orchestrator", expires_at=4102444800, nonce="abc123"),
        lambda legacy: "invalid-token",
    ],
)
def test_verify_governance_token_behavior_unchanged(monkeypatch: pytest.MonkeyPatch, token_factory) -> None:
    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.setenv("CRYOVANT_DEV_MODE", "1")
    monkeypatch.setenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", "governance-test-secret")

    shim = importlib.import_module("security.cryovant")
    legacy = importlib.import_module("security.cryovant_legacy")
    token = token_factory(legacy)

    assert _call_outcome(shim.verify_governance_token, token) == _call_outcome(legacy.verify_governance_token, token)


def test_assert_governance_signing_key_boot_behavior_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "production")
    monkeypatch.delenv("ADAAD_GOVERNANCE_SESSION_SIGNING_KEY", raising=False)

    shim = importlib.import_module("security.cryovant")
    legacy = importlib.import_module("security.cryovant_legacy")

    assert _call_outcome(shim.assert_governance_signing_key_boot) == _call_outcome(legacy.assert_governance_signing_key_boot)
