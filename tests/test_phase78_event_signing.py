# SPDX-License-Identifier: Apache-2.0
"""Phase 78 — Production EventSigner tests.

Covers HMACEnvSigner, Ed25519FileSigner/Verifier, and build_signer_from_env factory.
All tests are hermetic — no shared env, no persistent key files across tests.
"""
from __future__ import annotations
import os
import base64
import tempfile
import pytest
from runtime.evolution.event_signing import (
    HMACEnvSigner, Ed25519FileSigner, Ed25519FileVerifier,
    DeterministicMockSigner, SignatureBundle, build_signer_from_env,
)


# ── HMAC Env Signer ───────────────────────────────────────────────────────────

class TestHMACEnvSigner:
    def test_sign_returns_signature_bundle(self):
        s = HMACEnvSigner(secret="test-secret-32chars-padded-xxxxx")
        bundle = s.sign("hello governance")
        assert bundle.algorithm == "hmac-sha256"
        assert bundle.signature.startswith("sig:")
        assert bundle.signing_key_id == "hmac-env-v1"

    def test_sign_is_deterministic(self):
        s = HMACEnvSigner(secret="det-secret")
        assert s.sign("msg") == s.sign("msg")

    def test_verify_valid_signature(self):
        s = HMACEnvSigner(secret="verify-secret")
        bundle = s.sign("governance-message")
        assert s.verify(message="governance-message", signature=bundle) is True

    def test_verify_rejects_tampered_signature(self):
        s = HMACEnvSigner(secret="tamper-secret")
        bundle = s.sign("original")
        tampered = SignatureBundle("sig:deadbeef", bundle.signing_key_id, bundle.algorithm)
        assert s.verify(message="original", signature=tampered) is False

    def test_verify_rejects_wrong_message(self):
        s = HMACEnvSigner(secret="msg-secret")
        bundle = s.sign("correct-message")
        assert s.verify(message="wrong-message", signature=bundle) is False

    def test_missing_secret_raises(self, monkeypatch):
        monkeypatch.delenv("ADAAD_LEDGER_HMAC_SECRET", raising=False)
        with pytest.raises(ValueError, match="ADAAD_LEDGER_HMAC_SECRET"):
            HMACEnvSigner()

    def test_from_env_var(self, monkeypatch):
        monkeypatch.setenv("ADAAD_LEDGER_HMAC_SECRET", "env-secret-value")
        s = HMACEnvSigner()
        bundle = s.sign("env-test")
        assert s.verify(message="env-test", signature=bundle)

    def test_cross_key_verify_fails(self):
        s1 = HMACEnvSigner(secret="key-one")
        s2 = HMACEnvSigner(secret="key-two")
        bundle = s1.sign("message")
        assert s2.verify(message="message", signature=bundle) is False


# ── Ed25519 File Signer ───────────────────────────────────────────────────────

def _generate_ed25519_pem_pair(tmp_path):
    """Generate a fresh Ed25519 key pair, write PEM files, return (priv_path, pub_path)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, PublicFormat, NoEncryption,
    )
    key = Ed25519PrivateKey.generate()
    priv_pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    pub_pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    priv_path = tmp_path / "ed25519_priv.pem"
    pub_path  = tmp_path / "ed25519_pub.pem"
    priv_path.write_bytes(priv_pem)
    pub_path.write_bytes(pub_pem)
    return str(priv_path), str(pub_path)


class TestEd25519FileSigner:
    def test_sign_returns_ed25519_bundle(self, tmp_path):
        priv, _ = _generate_ed25519_pem_pair(tmp_path)
        s = Ed25519FileSigner(key_path=priv)
        bundle = s.sign("ledger-event-payload")
        assert bundle.algorithm == "ed25519"
        assert bundle.signature.startswith("ed25519:")
        assert bundle.signing_key_id.startswith("ed25519:")

    def test_sign_is_deterministic(self, tmp_path):
        """Ed25519 is deterministic (RFC 8032) — same key + message = same sig."""
        priv, _ = _generate_ed25519_pem_pair(tmp_path)
        s = Ed25519FileSigner(key_path=priv)
        b1 = s.sign("determinism-check")
        b2 = s.sign("determinism-check")
        assert b1 == b2

    def test_different_messages_different_signatures(self, tmp_path):
        priv, _ = _generate_ed25519_pem_pair(tmp_path)
        s = Ed25519FileSigner(key_path=priv)
        assert s.sign("msg-a") != s.sign("msg-b")

    def test_missing_key_path_raises(self, monkeypatch):
        monkeypatch.delenv("ADAAD_SIGNING_KEY_PATH", raising=False)
        with pytest.raises(ValueError, match="ADAAD_SIGNING_KEY_PATH"):
            Ed25519FileSigner()

    def test_from_env_var(self, tmp_path, monkeypatch):
        priv, _ = _generate_ed25519_pem_pair(tmp_path)
        monkeypatch.setenv("ADAAD_SIGNING_KEY_PATH", priv)
        s = Ed25519FileSigner()
        bundle = s.sign("env-key-test")
        assert bundle.algorithm == "ed25519"

    def test_verifier_accepts_valid_signature(self, tmp_path):
        priv, pub = _generate_ed25519_pem_pair(tmp_path)
        signer   = Ed25519FileSigner(key_path=priv)
        verifier = Ed25519FileVerifier(key_path=pub)
        bundle = signer.sign("cross-verify-message")
        assert verifier.verify(message="cross-verify-message", signature=bundle) is True

    def test_verifier_rejects_tampered_signature(self, tmp_path):
        priv, pub = _generate_ed25519_pem_pair(tmp_path)
        signer   = Ed25519FileSigner(key_path=priv)
        verifier = Ed25519FileVerifier(key_path=pub)
        bundle = signer.sign("original-message")
        bad_sig = base64.b64encode(b"\x00" * 64).decode()
        tampered = SignatureBundle(f"ed25519:{bad_sig}", bundle.signing_key_id, "ed25519")
        assert verifier.verify(message="original-message", signature=tampered) is False

    def test_verifier_rejects_wrong_algorithm(self, tmp_path):
        _, pub = _generate_ed25519_pem_pair(tmp_path)
        v = Ed25519FileVerifier(key_path=pub)
        bundle = SignatureBundle("sig:abc", "key", "hmac-sha256")
        assert v.verify(message="msg", signature=bundle) is False

    def test_cross_key_verification_fails(self, tmp_path):
        """Signature from key1 is rejected by verifier for key2."""
        k1 = tmp_path / "k1"; k1.mkdir()
        k2 = tmp_path / "k2"; k2.mkdir()
        priv1, _    = _generate_ed25519_pem_pair(k1)
        priv2, pub2 = _generate_ed25519_pem_pair(k2)
        s1 = Ed25519FileSigner(key_path=priv1)
        v2 = Ed25519FileVerifier(key_path=pub2)
        bundle = s1.sign("cross-key-test")
        assert v2.verify(message="cross-key-test", signature=bundle) is False


# ── build_signer_from_env factory ─────────────────────────────────────────────

class TestBuildSignerFromEnv:
    def test_prefers_ed25519_when_key_path_set(self, tmp_path, monkeypatch):
        priv, _ = _generate_ed25519_pem_pair(tmp_path)
        monkeypatch.setenv("ADAAD_SIGNING_KEY_PATH", priv)
        monkeypatch.delenv("ADAAD_LEDGER_HMAC_SECRET", raising=False)
        s = build_signer_from_env()
        assert isinstance(s, Ed25519FileSigner)

    def test_falls_back_to_hmac_when_only_secret_set(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ADAAD_SIGNING_KEY_PATH", raising=False)
        monkeypatch.setenv("ADAAD_LEDGER_HMAC_SECRET", "fallback-secret")
        s = build_signer_from_env()
        assert isinstance(s, HMACEnvSigner)

    def test_falls_back_to_mock_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("ADAAD_SIGNING_KEY_PATH", raising=False)
        monkeypatch.delenv("ADAAD_LEDGER_HMAC_SECRET", raising=False)
        s = build_signer_from_env()
        assert isinstance(s, DeterministicMockSigner)

    def test_factory_signer_produces_valid_bundle(self, tmp_path, monkeypatch):
        priv, _ = _generate_ed25519_pem_pair(tmp_path)
        monkeypatch.setenv("ADAAD_SIGNING_KEY_PATH", priv)
        s = build_signer_from_env()
        bundle = s.sign("factory-test")
        assert bundle.signature
        assert bundle.algorithm in ("ed25519", "hmac-sha256")
