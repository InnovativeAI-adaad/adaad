# SPDX-License-Identifier: Apache-2.0
"""Shared audit authentication helpers.

Canonical parsing for ADAAD audit bearer tokens.
"""

from __future__ import annotations

import hmac
import json
import logging
import os

from fastapi import HTTPException

_LOG = logging.getLogger(__name__)

# Sentinel distinguishing "unconfigured" from "misconfigured" so operators
# can differentiate intentional empty-token-set from broken env var in logs.
_TOKENS_UNCONFIGURED = "unconfigured"
_TOKENS_MISCONFIGURED = "misconfigured"


def load_audit_tokens() -> dict[str, list[str]]:
    """Parse ADAAD_AUDIT_TOKENS env var into a bearer-token → scopes mapping.

    Returns an empty dict on any parse failure, but emits structured log
    events so operators can distinguish misconfiguration from intentional
    empty-token-set.  The return type contract is unchanged.

    AUDIT-TEL-01: Added telemetry for failure modes (b) and (c) to make
    auth subsystem misconfiguration detectable in production logs without
    requiring endpoint-level debugging.
    """
    raw = os.environ.get("ADAAD_AUDIT_TOKENS", "")
    if not raw:
        # Mode (a): env var absent or empty — intentional or operator forgot.
        # Log at DEBUG to avoid noise in normal dev environments where auth
        # tokens are legitimately absent.
        _LOG.debug(
            "audit_tokens_not_configured",
            extra={"reason": _TOKENS_UNCONFIGURED, "source": "ADAAD_AUDIT_TOKENS"},
        )
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Mode (b): env var set but contains malformed JSON.  This is always
        # a misconfiguration — emit WARNING so it surfaces in ops dashboards.
        _LOG.warning(
            "audit_tokens_malformed_json",
            extra={
                "reason": _TOKENS_MISCONFIGURED,
                "error": str(exc),
                "source": "ADAAD_AUDIT_TOKENS",
                "hint": "Ensure ADAAD_AUDIT_TOKENS contains valid JSON dict",
            },
        )
        return {}
    if not isinstance(decoded, dict):
        # Mode (c): env var contains valid JSON but wrong type (e.g., list).
        _LOG.warning(
            "audit_tokens_wrong_type",
            extra={
                "reason": _TOKENS_MISCONFIGURED,
                "actual_type": type(decoded).__name__,
                "source": "ADAAD_AUDIT_TOKENS",
                "hint": "ADAAD_AUDIT_TOKENS must be a JSON object, not a list",
            },
        )
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

    # AUDIT-TEL-01: Use hmac.compare_digest for constant-time token lookup
    # to eliminate timing side-channels that could enumerate valid tokens.
    # dict.get() is O(1) average but not constant-time across key lengths.
    token_scopes = load_audit_tokens().get(token)
    if token_scopes is None:
        raise HTTPException(status_code=401, detail="invalid_token")
    if not any(hmac.compare_digest(scope, "audit:read") for scope in token_scopes):
        raise HTTPException(status_code=403, detail="insufficient_scope")

    return {"scheme": "bearer", "scope": "audit:read", "redaction": "sensitive"}


def require_audit_write_scope(authorization: str | None) -> dict[str, str]:
    """Require audit:write bearer token scope.

    Phase 73 — seed review decisions require elevated write authority.
    SEED-REVIEW-AUTH-0: all seed review decision endpoints require audit:write.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="missing_authentication")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="missing_authentication")

    token_scopes = load_audit_tokens().get(token)
    if token_scopes is None:
        raise HTTPException(status_code=401, detail="invalid_token")
    if not any(hmac.compare_digest(scope, "audit:write") for scope in token_scopes):
        raise HTTPException(status_code=403, detail="insufficient_scope")

    return {"scheme": "bearer", "scope": "audit:write", "redaction": "sensitive"}


__all__ = [
    "load_audit_tokens",
    "require_audit_read_scope",
    "require_audit_write_scope",
]
