# SPDX-License-Identifier: Apache-2.0
"""
SoulboundKey — HMAC-ENV keying for the Soulbound Context Ledger.

Purpose:
    Provides a consistent, fail-closed HMAC signing key for the SoulboundLedger.
    The key is sourced from the environment variable ``ADAAD_SOULBOUND_KEY``
    (hex-encoded, minimum 32 bytes / 64 hex chars). This mirrors the
    ``ADAAD_FEDERATION_HMAC_KEY`` pattern established in Phase 5.

Fail-closed contract:
    - If the env var is absent → SoulboundKeyError raised at get_key() call time.
    - If the env var is present but malformed (non-hex, too short) → SoulboundKeyError.
    - The absence sentinel is NEVER silently swapped for an insecure default.
    - Tests that need a key must inject one via the env var or use the test helper.

Rotation:
    Key rotation is performed by rotating ADAAD_SOULBOUND_KEY in the environment
    and calling rotate_key() on a running SoulboundLedger instance.  The ledger
    emits a ``soulbound_key_rotation.v1`` journal event on every rotation.

Architecture note:
    SoulboundKey is a pure stateless module — it reads env on demand and performs
    no caching, so it is always consistent with the current environment state.
    This is intentional: it supports key rotation without restart.

Constitutional invariants:
    - Fail-closed: missing or malformed key → SoulboundKeyError, never a default.
    - Deterministic: given the same env state, get_key() returns the same bytes.
    - No side effects: module import has zero side effects.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Final

ENV_VAR: Final[str] = "ADAAD_SOULBOUND_KEY"
MIN_KEY_BYTES: Final[int] = 32   # 256-bit minimum — 64 hex chars in env


class SoulboundKeyError(RuntimeError):
    """Raised when ADAAD_SOULBOUND_KEY is absent or malformed.

    This is a fail-closed sentinel: callers must not catch this and continue.
    Governance policy: if the soulbound key is unavailable, ledger operations
    are blocked — no ledger entry is accepted without a valid HMAC.
    """


def get_key() -> bytes:
    """Return the raw HMAC key bytes from the environment.

    Raises:
        SoulboundKeyError: if ADAAD_SOULBOUND_KEY is absent or malformed.

    Returns:
        bytes of length ≥ MIN_KEY_BYTES.
    """
    raw = os.environ.get(ENV_VAR)
    if raw is None:
        raise SoulboundKeyError(
            f"Environment variable {ENV_VAR!r} is not set. "
            "Soulbound ledger operations are fail-closed without a key. "
            "Set a 64-hex-char (256-bit) value to enable the ledger."
        )
    raw = raw.strip()
    try:
        key_bytes = bytes.fromhex(raw)
    except ValueError as exc:
        raise SoulboundKeyError(
            f"{ENV_VAR!r} is not valid hex: {exc}. "
            "Provide a hex-encoded key of at least 64 hex chars (32 bytes)."
        ) from exc
    if len(key_bytes) < MIN_KEY_BYTES:
        raise SoulboundKeyError(
            f"{ENV_VAR!r} decoded to {len(key_bytes)} bytes; "
            f"minimum is {MIN_KEY_BYTES} bytes ({MIN_KEY_BYTES * 2} hex chars)."
        )
    return key_bytes


def sign(data: bytes, *, key: bytes | None = None) -> str:
    """Return a hex HMAC-SHA256 signature for *data* using the soulbound key.

    Args:
        data: Bytes to sign (typically canonical JSON of a ledger entry).
        key:  Override key for testing; if None, get_key() is called.

    Returns:
        Lowercase hex HMAC-SHA256 digest string (64 chars).

    Raises:
        SoulboundKeyError: if key is None and ADAAD_SOULBOUND_KEY is invalid.
    """
    signing_key = key if key is not None else get_key()
    return hmac.new(signing_key, data, hashlib.sha256).hexdigest()


def verify(data: bytes, signature: str, *, key: bytes | None = None) -> bool:
    """Verify a hex HMAC-SHA256 signature against *data*.

    Uses hmac.compare_digest for constant-time comparison.

    Args:
        data:      Bytes that were signed.
        signature: Expected hex HMAC-SHA256 digest.
        key:       Override key for testing; if None, get_key() is called.

    Returns:
        True if the signature matches, False otherwise.

    Raises:
        SoulboundKeyError: if key is None and ADAAD_SOULBOUND_KEY is invalid.
    """
    signing_key = key if key is not None else get_key()
    expected = hmac.new(signing_key, data, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected.encode("ascii"), signature.encode("ascii"))
    except Exception:  # noqa: BLE001
        return False


__all__ = [
    "ENV_VAR",
    "MIN_KEY_BYTES",
    "SoulboundKeyError",
    "get_key",
    "sign",
    "verify",
]
