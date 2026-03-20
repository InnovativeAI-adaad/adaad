# SPDX-License-Identifier: Apache-2.0
"""Signer/verifier abstractions for AGM ledger events.

Constitutional invariants
─────────────────────────
  EVENT-SIGN-ABSTRACT-0  EventSigner and EventVerifier are abstract base
                         classes; direct instantiation is a runtime error.
  EVENT-SIGN-DETERM-0    Implementations must be deterministic: identical
                         (message, key) inputs produce identical SignatureBundle
                         outputs.
  EVENT-SIGN-COMPARE-0   Signature comparison must use hmac.compare_digest
                         to prevent timing-oracle attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SignatureBundle:
    signature: str
    signing_key_id: str
    algorithm: str


class EventSigner(ABC):
    """Abstract base: production signer interface (typically KMS/HSM backed).

    Subclasses must implement sign() deterministically.
    See DeterministicMockSigner for test usage; KMS wiring is Phase 78+.
    """

    @abstractmethod
    def sign(self, message: str) -> SignatureBundle:
        """Sign *message* and return a SignatureBundle.

        Must be deterministic: identical (message, key) → identical bundle.
        """


class EventVerifier(ABC):
    """Abstract base: production verifier interface (typically KMS/HSM backed).

    Subclasses must implement verify() using constant-time comparison.
    """

    @abstractmethod
    def verify(self, *, message: str, signature: SignatureBundle) -> bool:
        """Return True iff *signature* is valid for *message*."""


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


class HMACEnvSigner(EventSigner, EventVerifier):
    """Production HMAC signer backed by ADAAD_LEDGER_HMAC_SECRET env var.

    Constitutional invariants:
      LEDGER-SIGN-0   Every event is signed before ledger append.
      LEDGER-SIGN-DETERM-0  Same (message, key) → same SignatureBundle.
    """

    _ENV_VAR = "ADAAD_LEDGER_HMAC_SECRET"

    def __init__(self, *, key_id: str = "hmac-env-v1", secret: str | None = None) -> None:
        import os
        raw = secret or os.environ.get(self._ENV_VAR, "")
        if not raw:
            raise ValueError(
                f"HMACEnvSigner: {self._ENV_VAR} not set — "
                "set the env var or pass secret= explicitly"
            )
        self.key_id = key_id
        self._secret = raw.encode("utf-8")

    def sign(self, message: str) -> SignatureBundle:
        digest = hmac.new(self._secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
        return SignatureBundle(signature=f"sig:{digest}", signing_key_id=self.key_id, algorithm="hmac-sha256")

    def verify(self, *, message: str, signature: SignatureBundle) -> bool:
        if signature.algorithm != "hmac-sha256" or signature.signing_key_id != self.key_id:
            return False
        expected = self.sign(message).signature
        return hmac.compare_digest(expected, signature.signature)


class Ed25519FileSigner(EventSigner):
    """Production Ed25519 signer backed by a PEM key file.

    Key file path is read from ADAAD_SIGNING_KEY_PATH env var, or passed
    directly as key_path. Supports both raw and PEM-encoded private keys.

    Constitutional invariants:
      LEDGER-SIGN-0        Every event signed before ledger append.
      LEDGER-SIGN-ED25519  Signatures use Ed25519 — non-repudiable, compact.
      LEDGER-VERIFY-ED25519 Public key verifiable independently of signer.
    """

    _ENV_VAR = "ADAAD_SIGNING_KEY_PATH"

    def __init__(self, *, key_path: str | None = None) -> None:
        import os
        path = key_path or os.environ.get(self._ENV_VAR)
        if not path:
            raise ValueError(
                f"Ed25519FileSigner: no key path — set {self._ENV_VAR} or pass key_path="
            )
        self._key_path = path
        self._private_key = self._load_key(path)

    @staticmethod
    def _load_key(path: str):
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        raw = open(path, "rb").read()
        key = load_pem_private_key(raw, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(f"Ed25519FileSigner: key at {path!r} is not an Ed25519 private key")
        return key

    def sign(self, message: str) -> SignatureBundle:
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        import base64
        sig_bytes = self._private_key.sign(message.encode("utf-8"))
        pub_bytes = self._private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        key_id = "ed25519:" + base64.b64encode(pub_bytes[:8]).decode()
        return SignatureBundle(
            signature="ed25519:" + base64.b64encode(sig_bytes).decode(),
            signing_key_id=key_id,
            algorithm="ed25519",
        )


class Ed25519FileVerifier(EventVerifier):
    """Verifier counterpart for Ed25519FileSigner.

    Accepts a public key PEM file path via ADAAD_VERIFY_KEY_PATH or key_path=.
    LEDGER-VERIFY-ED25519: independently verifiable without the signing key.
    """

    _ENV_VAR = "ADAAD_VERIFY_KEY_PATH"

    def __init__(self, *, key_path: str | None = None) -> None:
        import os
        path = key_path or os.environ.get(self._ENV_VAR)
        if not path:
            raise ValueError(f"Ed25519FileVerifier: set {self._ENV_VAR} or pass key_path=")
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        self._public_key = load_pem_public_key(open(path, "rb").read())

    def verify(self, *, message: str, signature: SignatureBundle) -> bool:
        if signature.algorithm != "ed25519":
            return False
        import base64
        from cryptography.exceptions import InvalidSignature
        try:
            sig_bytes = base64.b64decode(signature.signature.removeprefix("ed25519:"))
            self._public_key.verify(sig_bytes, message.encode("utf-8"))
            return True
        except (InvalidSignature, Exception):
            return False


def build_signer_from_env() -> EventSigner:
    """Factory: build the best available production signer from environment.

    Priority:
      1. Ed25519FileSigner if ADAAD_SIGNING_KEY_PATH is set
      2. HMACEnvSigner if ADAAD_LEDGER_HMAC_SECRET is set
      3. DeterministicMockSigner (dev/test only — logs WARNING)

    LEDGER-SIGN-0: callers should always use this factory rather than
    instantiating signers directly, so the active backend is env-configurable.
    """
    import logging, os
    log = logging.getLogger(__name__)
    if os.environ.get("ADAAD_SIGNING_KEY_PATH"):
        return Ed25519FileSigner()
    if os.environ.get("ADAAD_LEDGER_HMAC_SECRET"):
        return HMACEnvSigner()
    log.warning(
        "build_signer_from_env: no signing key configured — "
        "using DeterministicMockSigner (not for production). "
        "Set ADAAD_SIGNING_KEY_PATH or ADAAD_LEDGER_HMAC_SECRET."
    )
    return DeterministicMockSigner()


__all__ = [
    "DeterministicMockSigner",
    "Ed25519FileSigner",
    "Ed25519FileVerifier",
    "EventSigner",
    "EventVerifier",
    "HMACEnvSigner",
    "HMACKeyringVerifier",
    "SignatureBundle",
    "build_signer_from_env",
    "load_hmac_keyring_from_env",
]
