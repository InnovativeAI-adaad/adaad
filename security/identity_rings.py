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
from typing import Mapping


@dataclass(frozen=True)
class IdentityRingToken:
    ring: str
    subject_id: str
    digest: str


def build_ring_token(ring: str, subject_id: str, claims: Mapping[str, str]) -> IdentityRingToken:
    payload = {
        "claims": sorted((str(k), str(v)) for k, v in claims.items()),
        "ring": str(ring),
        "subject_id": str(subject_id),
    }
    digest = hashlib.sha256(str(payload).encode("utf-8")).hexdigest()
    return IdentityRingToken(ring=str(ring), subject_id=str(subject_id), digest=digest)


__all__ = ["IdentityRingToken", "build_ring_token"]
