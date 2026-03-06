# SPDX-License-Identifier: Apache-2.0
"""Federation manifest primitives for deterministic file-based exchange."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import logging
import os
from typing import Any, Dict, List

_MANIFEST_HMAC_ENV = "ADAAD_FEDERATION_MANIFEST_HMAC_KEY"
_MANIFEST_HMAC_DEFAULT = "adaad-federation-v0.70.0"
_HMAC_KEY_MIN_LENGTH = 32

log = logging.getLogger(__name__)


class FederationHMACKeyError(RuntimeError):
    """Raised when the federation HMAC key fails the minimum-length contract.

    Invariant: federation_hmac_key_weak is a fail-closed boot contract violation.
    Any federation subsystem initialised without a key of at least
    ``_HMAC_KEY_MIN_LENGTH`` bytes is considered operationally unsafe.
    """


def validate_hmac_key(key: str, *, federation_mode_enabled: bool = False) -> None:
    """Assert HMAC key meets minimum length contract (M-05).

    Parameters
    ----------
    key:
        Raw HMAC key string sourced from ``ADAAD_FEDERATION_MANIFEST_HMAC_KEY``.
    federation_mode_enabled:
        When *True*, a weak key causes a fail-closed ``FederationHMACKeyError``.
        When *False*, the violation is emitted as a ``WARNING`` only (dev/test
        environments where the default placeholder key is acceptable).

    Raises
    ------
    FederationHMACKeyError
        If ``federation_mode_enabled`` is *True* and ``len(key) < 32``.
    """
    if len(key) >= _HMAC_KEY_MIN_LENGTH:
        return

    msg = (
        f"federation_hmac_key_weak: ADAAD_FEDERATION_MANIFEST_HMAC_KEY is only "
        f"{len(key)} bytes; minimum required is {_HMAC_KEY_MIN_LENGTH}. "
        "Rotate the key before enabling federation mode."
    )
    if federation_mode_enabled:
        raise FederationHMACKeyError(msg)
    log.warning(msg)


@dataclass(frozen=True)
class FederationManifest:
    node_id: str
    law_version: str
    trust_mode: str
    epoch_id: str
    active_modules: List[str]
    hmac_signature: str = ""

    def canonical_payload(self) -> Dict[str, Any]:
        return {
            "active_modules": sorted(self.active_modules),
            "epoch_id": self.epoch_id,
            "law_version": self.law_version,
            "node_id": self.node_id,
            "trust_mode": self.trust_mode,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))

    def sign_manifest(self, key: str) -> "FederationManifest":
        digest = hmac.new(key.encode("utf-8"), self.canonical_json().encode("utf-8"), hashlib.sha256).hexdigest()
        return FederationManifest(
            node_id=self.node_id,
            law_version=self.law_version,
            trust_mode=self.trust_mode,
            epoch_id=self.epoch_id,
            active_modules=list(self.active_modules),
            hmac_signature=f"hmac-sha256:{digest}",
        )

    def verify_manifest(self, public_key: str) -> bool:
        expected = self.sign_manifest(public_key).hmac_signature
        return hmac.compare_digest(self.hmac_signature, expected)

    @classmethod
    def deterministic_key_from_env(cls, *, federation_mode_enabled: bool = False) -> str:
        """Load HMAC key from environment and validate minimum length (M-05).

        Parameters
        ----------
        federation_mode_enabled:
            Passed through to :func:`validate_hmac_key`; when *True* a weak
            key raises :class:`FederationHMACKeyError` (fail-closed).
        """
        key = os.getenv(_MANIFEST_HMAC_ENV, _MANIFEST_HMAC_DEFAULT)
        validate_hmac_key(key, federation_mode_enabled=federation_mode_enabled)
        return key

    def to_dict(self) -> Dict[str, Any]:
        payload = self.canonical_payload()
        payload["hmac_signature"] = self.hmac_signature
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FederationManifest":
        return cls(
            node_id=str(payload["node_id"]),
            law_version=str(payload["law_version"]),
            trust_mode=str(payload["trust_mode"]),
            epoch_id=str(payload["epoch_id"]),
            active_modules=[str(module) for module in payload.get("active_modules", [])],
            hmac_signature=str(payload.get("hmac_signature", "")),
        )


__all__ = ["FederationManifest", "FederationHMACKeyError", "validate_hmac_key"]
