# SPDX-License-Identifier: Apache-2.0

from unittest import mock

import pytest
pytestmark = pytest.mark.regression_standard

from security.cryovant import GovernanceTokenError, verify_session


def generate_valid_dev_token(monkeypatch: pytest.MonkeyPatch) -> str:
    token = "dev-token"
    monkeypatch.setenv("CRYOVANT_DEV_TOKEN", token)
    return token


@pytest.mark.parametrize("env", ["production", "staging", "prod", "test"])
def test_verify_session_rejected_in_strict_and_test_envs(monkeypatch: pytest.MonkeyPatch, env: str) -> None:
    monkeypatch.setenv("ADAAD_ENV", env)
    monkeypatch.delenv("CRYOVANT_DEV_MODE", raising=False)

    with pytest.raises(GovernanceTokenError):
        verify_session("any-token")


def test_verify_session_dev_without_dev_mode_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.delenv("CRYOVANT_DEV_MODE", raising=False)

    with pytest.raises(GovernanceTokenError):
        verify_session("any-token")


def test_verify_session_dev_mode_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.setenv("CRYOVANT_DEV_MODE", "1")
    token = generate_valid_dev_token(monkeypatch)

    with mock.patch("security.cryovant.metrics.log") as metrics_log:
        assert verify_session(token) is True

    metrics_log.assert_called_once_with(
        event_type="verify_session_legacy_path_used",
        payload={"env": "dev"},
        level="WARNING",
        element_id="Water",
    )



def test_verify_session_unset_env_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADAAD_ENV", raising=False)

    with pytest.raises(GovernanceTokenError):
        verify_session("any-token")


def test_verify_session_unknown_env_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "unknown")

    with pytest.raises(GovernanceTokenError):
        verify_session("any-token")


def test_verify_session_dev_mode_rejected_when_legacy_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.setenv("CRYOVANT_DEV_MODE", "1")
    monkeypatch.setenv("CRYOVANT_DEV_TOKEN", "dev-token")
    monkeypatch.setenv("ADAAD_ENABLE_LEGACY_VERIFY_SESSION", "0")

    with pytest.raises(GovernanceTokenError, match="verify_session_legacy_flag_disabled"):
        verify_session("dev-token")
