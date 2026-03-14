# SPDX-License-Identifier: Apache-2.0
"""Canonical identity-ring claim schema and deterministic canonicalization helpers."""

from __future__ import annotations

import json
from typing import Any, Mapping

ALLOWED_RINGS: tuple[str, ...] = ("device", "agent", "human", "federation")
RING_REQUIRED_CLAIMS: dict[str, tuple[str, ...]] = {
    "device": ("device_id", "device_key_id"),
    "agent": ("agent_id", "agent_version"),
    "human": ("human_id", "human_role"),
    "federation": ("federation_id", "source_repo", "target_repo"),
}


def canonicalize_ring_claims(ring: str, subject_id: str, claims: Mapping[str, Any]) -> str:
    """Return deterministic JSON canonical form for ring claims.

    Raises ValueError on malformed payloads.
    """

    normalized_ring = str(ring or "").strip().lower()
    normalized_subject = str(subject_id or "").strip()
    if normalized_ring not in ALLOWED_RINGS:
        raise ValueError(f"ring_unknown:{normalized_ring or '<empty>'}")
    if not normalized_subject:
        raise ValueError("subject_id_required")
    if not isinstance(claims, Mapping):
        raise ValueError("claims_must_be_mapping")

    normalized_claims: dict[str, str] = {}
    for key, value in claims.items():
        k = str(key or "").strip()
        v = str(value or "").strip()
        if not k:
            raise ValueError("claim_key_empty")
        if not v:
            raise ValueError(f"claim_value_empty:{k}")
        normalized_claims[k] = v

    required = RING_REQUIRED_CLAIMS[normalized_ring]
    missing = [name for name in required if not normalized_claims.get(name)]
    if missing:
        raise ValueError(f"claims_missing_required:{','.join(missing)}")

    canonical_payload = {
        "ring": normalized_ring,
        "subject_id": normalized_subject,
        "claims": normalized_claims,
    }
    return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


__all__ = [
    "ALLOWED_RINGS",
    "RING_REQUIRED_CLAIMS",
    "canonicalize_ring_claims",
]
