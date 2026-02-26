# SPDX-License-Identifier: Apache-2.0
"""Signer/verifier abstractions for AGM ledger events."""

from __future__ import annotations

import hashlib
import hmac
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

