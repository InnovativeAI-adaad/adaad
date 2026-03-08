# SPDX-License-Identifier: Apache-2.0
"""Signer/verifier abstractions for AGM ledger events."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SignatureBundle:
    signature: str
    signing_key_id: str
    algorithm: str


class EventSigner:
    """Production signer interface (typically KMS/HSM backed)."""

    def sign(self, message: str) -> SignatureBundle:
        raise NotImplementedError


class EventVerifier:
    """Production verifier interface (typically KMS/HSM backed)."""

    def verify(self, *, message: str, signature: SignatureBundle) -> bool:
        raise NotImplementedError


class DeterministicMockSigner(EventSigner, EventVerifier):
    """Deterministic test signer/verifier for hermetic unit tests."""

    def __init__(self, *, key_id: str = "mock-kms-key", secret: str = "mock-ledger-secret", algorithm: str = "hmac-sha256"):
        self.key_id = key_id
        self.secret = secret.encode("utf-8")
        self.algorithm = algorithm

    def sign(self, message: str) -> SignatureBundle:
        digest = hmac.new(self.secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
        return SignatureBundle(signature=f"sig:{digest}", signing_key_id=self.key_id, algorithm=self.algorithm)

    def verify(self, *, message: str, signature: SignatureBundle) -> bool:
        if signature.algorithm != self.algorithm or signature.signing_key_id != self.key_id:
            return False
        expected = self.sign(message).signature
        return hmac.compare_digest(expected, signature.signature)


class HMACKeyringVerifier(EventVerifier):
    """EventVerifier implementation backed by a keyring of HMAC secrets."""

    def __init__(self, keyring: dict[str, str]) -> None:
        self._keyring = {key_id: secret.encode("utf-8") for key_id, secret in keyring.items()}

    def verify(self, *, message: str, signature: SignatureBundle) -> bool:
        secret = self._keyring.get(signature.signing_key_id)
        if secret is None or signature.algorithm != "hmac-sha256":
            return False
        expected = hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature.signature, f"sig:{expected}")


def load_hmac_keyring_from_env(var_name: str = "ADAAD_LEDGER_SIGNING_KEYS") -> dict[str, str]:
    raw = os.getenv(var_name, "{}")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"{var_name} must be a JSON object of key_id -> secret")
    return {str(k): str(v) for k, v in parsed.items()}


__all__ = [
    "DeterministicMockSigner",
    "EventSigner",
    "EventVerifier",
    "HMACKeyringVerifier",
    "SignatureBundle",
    "load_hmac_keyring_from_env",
]
