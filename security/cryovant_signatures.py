# SPDX-License-Identifier: Apache-2.0
"""Signature and HMAC operations for Cryovant migration."""

from security.cryovant_legacy import (
    MissingSigningKeyError,
    _ARTIFACT_HMAC_CONFIG,
    _HMAC_SIGNATURE_PREFIX,
    _active_key_paths,
    _canonical_signature,
    _dev_signature_allowed,
    _legacy_static_signature_allowed,
    _parse_sha256_signature,
    _resolve_hmac_secret,
    dev_signature_allowed,
    sign_artifact_hmac_digest,
    sign_hmac_digest,
    signature_valid,
    verify_artifact_hmac_digest_signature,
    verify_hmac_digest_signature,
    verify_payload_signature,
    verify_signature,
)

__all__ = [
    "MissingSigningKeyError",
    "_ARTIFACT_HMAC_CONFIG",
    "_HMAC_SIGNATURE_PREFIX",
    "_active_key_paths",
    "_canonical_signature",
    "_dev_signature_allowed",
    "_legacy_static_signature_allowed",
    "_parse_sha256_signature",
    "_resolve_hmac_secret",
    "dev_signature_allowed",
    "sign_artifact_hmac_digest",
    "sign_hmac_digest",
    "signature_valid",
    "verify_artifact_hmac_digest_signature",
    "verify_hmac_digest_signature",
    "verify_payload_signature",
    "verify_signature",
]
