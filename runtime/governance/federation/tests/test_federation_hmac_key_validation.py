# SPDX-License-Identifier: Apache-2.0
"""Tests for FederationManifest HMAC key length validation (M-05).

Invariants under test
---------------------
- A key of exactly 32 bytes passes silently in both modes.
- A key shorter than 32 bytes emits WARNING (non-federation mode).
- A key shorter than 32 bytes raises FederationHMACKeyError (federation mode).
- deterministic_key_from_env() invokes validate_hmac_key() with correct mode arg.
- The default placeholder key triggers a warning (it is 25 bytes, below threshold).
"""
from __future__ import annotations

import logging

import pytest

from runtime.governance.federation.manifest import (
    FederationHMACKeyError,
    FederationManifest,
    _HMAC_KEY_MIN_LENGTH,
    _MANIFEST_HMAC_DEFAULT,
    validate_hmac_key,
)

_STRONG_KEY = "x" * _HMAC_KEY_MIN_LENGTH  # exactly 32 bytes — minimum valid
_WEAK_KEY = "short"                        # 5 bytes — clearly below threshold
_BOUNDARY_KEY = "x" * (_HMAC_KEY_MIN_LENGTH - 1)  # 31 bytes — one below limit


# ---------------------------------------------------------------------------
# validate_hmac_key — direct unit tests
# ---------------------------------------------------------------------------


class TestValidateHMACKey:
    def test_strong_key_passes_silently(self) -> None:
        """A key of exactly _HMAC_KEY_MIN_LENGTH bytes must not raise or warn."""
        validate_hmac_key(_STRONG_KEY)

    def test_strong_key_passes_federation_mode(self) -> None:
        """A strong key must not raise even when federation_mode_enabled=True."""
        validate_hmac_key(_STRONG_KEY, federation_mode_enabled=True)

    def test_key_longer_than_minimum_passes(self) -> None:
        """Keys longer than minimum must always pass."""
        validate_hmac_key("y" * 64)

    def test_weak_key_logs_warning_non_federation_mode(self, caplog) -> None:
        """Weak key in non-federation mode emits WARNING, does not raise."""
        with caplog.at_level(logging.WARNING, logger="runtime.governance.federation.manifest"):
            validate_hmac_key(_WEAK_KEY, federation_mode_enabled=False)
        assert "federation_hmac_key_weak" in caplog.text
        assert str(len(_WEAK_KEY)) in caplog.text

    def test_weak_key_raises_in_federation_mode(self) -> None:
        """Weak key with federation_mode_enabled=True must raise fail-closed."""
        with pytest.raises(FederationHMACKeyError, match="federation_hmac_key_weak"):
            validate_hmac_key(_WEAK_KEY, federation_mode_enabled=True)

    def test_boundary_key_one_below_minimum_raises(self) -> None:
        """A key of exactly min-1 bytes must fail closed in federation mode."""
        with pytest.raises(FederationHMACKeyError):
            validate_hmac_key(_BOUNDARY_KEY, federation_mode_enabled=True)

    def test_boundary_key_one_below_warns_non_federation(self, caplog) -> None:
        """A key of exactly min-1 bytes warns in non-federation mode."""
        with caplog.at_level(logging.WARNING, logger="runtime.governance.federation.manifest"):
            validate_hmac_key(_BOUNDARY_KEY, federation_mode_enabled=False)
        assert "federation_hmac_key_weak" in caplog.text

    def test_error_message_contains_rotation_guidance(self) -> None:
        """Error message must include rotation guidance for operator clarity."""
        with pytest.raises(FederationHMACKeyError) as exc_info:
            validate_hmac_key(_WEAK_KEY, federation_mode_enabled=True)
        assert "Rotate the key" in str(exc_info.value)
        assert str(_HMAC_KEY_MIN_LENGTH) in str(exc_info.value)

    def test_empty_key_raises_federation_mode(self) -> None:
        """An empty key must raise in federation mode."""
        with pytest.raises(FederationHMACKeyError):
            validate_hmac_key("", federation_mode_enabled=True)

    def test_empty_key_warns_non_federation(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            validate_hmac_key("", federation_mode_enabled=False)
        assert "federation_hmac_key_weak" in caplog.text


# ---------------------------------------------------------------------------
# Default placeholder key
# ---------------------------------------------------------------------------


class TestDefaultPlaceholderKey:
    def test_default_key_is_below_minimum(self) -> None:
        """The default placeholder key is intentionally short — must warn."""
        assert len(_MANIFEST_HMAC_DEFAULT) < _HMAC_KEY_MIN_LENGTH, (
            "Default key unexpectedly meets the minimum. Update the default or adjust "
            "this test — but do NOT increase the default key length silently."
        )

    def test_default_key_warns_non_federation(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger="runtime.governance.federation.manifest"):
            validate_hmac_key(_MANIFEST_HMAC_DEFAULT, federation_mode_enabled=False)
        assert "federation_hmac_key_weak" in caplog.text

    def test_default_key_raises_federation_mode(self) -> None:
        with pytest.raises(FederationHMACKeyError):
            validate_hmac_key(_MANIFEST_HMAC_DEFAULT, federation_mode_enabled=True)


# ---------------------------------------------------------------------------
# deterministic_key_from_env integration
# ---------------------------------------------------------------------------


class TestDeterministicKeyFromEnv:
    def test_returns_env_value_when_set(self, monkeypatch) -> None:
        monkeypatch.setenv("ADAAD_FEDERATION_MANIFEST_HMAC_KEY", _STRONG_KEY)
        key = FederationManifest.deterministic_key_from_env()
        assert key == _STRONG_KEY

    def test_returns_default_when_env_unset(self, monkeypatch) -> None:
        monkeypatch.delenv("ADAAD_FEDERATION_MANIFEST_HMAC_KEY", raising=False)
        key = FederationManifest.deterministic_key_from_env()
        assert key == _MANIFEST_HMAC_DEFAULT

    def test_strong_env_key_passes_federation_mode(self, monkeypatch) -> None:
        monkeypatch.setenv("ADAAD_FEDERATION_MANIFEST_HMAC_KEY", _STRONG_KEY)
        key = FederationManifest.deterministic_key_from_env(federation_mode_enabled=True)
        assert key == _STRONG_KEY

    def test_weak_env_key_raises_federation_mode(self, monkeypatch) -> None:
        monkeypatch.setenv("ADAAD_FEDERATION_MANIFEST_HMAC_KEY", _WEAK_KEY)
        with pytest.raises(FederationHMACKeyError):
            FederationManifest.deterministic_key_from_env(federation_mode_enabled=True)

    def test_default_key_raises_federation_mode(self, monkeypatch) -> None:
        monkeypatch.delenv("ADAAD_FEDERATION_MANIFEST_HMAC_KEY", raising=False)
        with pytest.raises(FederationHMACKeyError):
            FederationManifest.deterministic_key_from_env(federation_mode_enabled=True)

    def test_default_key_warns_non_federation_mode(self, monkeypatch, caplog) -> None:
        monkeypatch.delenv("ADAAD_FEDERATION_MANIFEST_HMAC_KEY", raising=False)
        with caplog.at_level(logging.WARNING):
            FederationManifest.deterministic_key_from_env(federation_mode_enabled=False)
        assert "federation_hmac_key_weak" in caplog.text


# ---------------------------------------------------------------------------
# Existing sign/verify contract unaffected by validation changes
# ---------------------------------------------------------------------------


class TestManifestSignVerifyUnchanged:
    """Guard: HMAC validation must not break the existing sign/verify contract."""

    def _make_manifest(self) -> FederationManifest:
        return FederationManifest(
            node_id="node-a",
            law_version="1.0",
            trust_mode="full",
            epoch_id="epoch-001",
            active_modules=["evolution", "fitness"],
        )

    def test_sign_and_verify_with_strong_key(self) -> None:
        manifest = self._make_manifest()
        signed = manifest.sign_manifest(_STRONG_KEY)
        assert signed.verify_manifest(_STRONG_KEY) is True

    def test_verify_fails_with_wrong_key(self) -> None:
        manifest = self._make_manifest()
        signed = manifest.sign_manifest(_STRONG_KEY)
        wrong_key = "z" * _HMAC_KEY_MIN_LENGTH
        assert signed.verify_manifest(wrong_key) is False
