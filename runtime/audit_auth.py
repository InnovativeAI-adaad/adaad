# SPDX-License-Identifier: Apache-2.0
"""Shared audit authentication helpers.

Canonical parsing for ADAAD audit bearer tokens.
"""

from __future__ import annotations

import json
import os

from fastapi import HTTPException


def load_audit_tokens() -> dict[str, list[str]]:
    raw = os.environ.get("ADAAD_AUDIT_TOKENS", "")
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(decoded, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for token, scopes in decoded.items():
        if not isinstance(token, str):
            continue
        if isinstance(scopes, list):
            normalized[token] = [str(scope) for scope in scopes]
    return normalized


def require_audit_read_scope(authorization: str | None) -> dict[str, str]:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing_authentication")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="missing_authentication")

    token_scopes = load_audit_tokens().get(token)
    if token_scopes is None:
        raise HTTPException(status_code=401, detail="invalid_token")
    if "audit:read" not in token_scopes:
        raise HTTPException(status_code=403, detail="insufficient_scope")

    return {"scheme": "bearer", "scope": "audit:read", "redaction": "sensitive"}


__all__ = ["load_audit_tokens", "require_audit_read_scope"]
