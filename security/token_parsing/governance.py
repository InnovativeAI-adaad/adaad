# SPDX-License-Identifier: Apache-2.0
"""Governance token parsing primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedGovernanceToken:
    key_id: str
    expires_at: int
    nonce: str
    signature: str


def is_valid_governance_token_field(value: str) -> bool:
    candidate = str(value or "")
    if not candidate.strip() or candidate != candidate.strip():
        return False
    return ":" not in candidate


def parse_governance_token(candidate: str) -> ParsedGovernanceToken | None:
    parts = str(candidate or "").strip().split(":", 5)
    if len(parts) != 6:
        return None
    prefix, key_id, expires_at_raw, nonce, sig_prefix, digest = parts
    if prefix != "cryovant-gov-v1" or sig_prefix != "sha256":
        return None
    if not is_valid_governance_token_field(key_id) or not is_valid_governance_token_field(nonce):
        return None
    try:
        expires_at = int(expires_at_raw)
    except ValueError:
        return None
    return ParsedGovernanceToken(
        key_id=key_id,
        expires_at=expires_at,
        nonce=nonce,
        signature=f"{sig_prefix}:{digest}",
    )
