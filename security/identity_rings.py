# SPDX-License-Identifier: Apache-2.0
"""Cryovant identity ring primitives.

Implements deterministic identity envelopes for four trust rings:
- device
- agent
- human
- federation
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

from security.ring_claims import canonicalize_ring_claims


@dataclass(frozen=True)
class IdentityRingToken:
    ring: str
    subject_id: str
    digest: str


def build_ring_token(ring: str, subject_id: str, claims: Mapping[str, Any]) -> IdentityRingToken:
    canonical_claims = canonicalize_ring_claims(ring=ring, subject_id=subject_id, claims=claims)
    digest = hashlib.sha256(canonical_claims.encode("utf-8")).hexdigest()
    return IdentityRingToken(ring=str(ring).strip().lower(), subject_id=str(subject_id).strip(), digest=digest)


__all__ = ["IdentityRingToken", "build_ring_token"]
