# SPDX-License-Identifier: Apache-2.0
"""Shared audit authentication helpers.

Canonical parsing for ADAAD audit bearer tokens.
"""

from __future__ import annotations

import json
import logging
import os

from security.unified_auth import require_scopes

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
        _LOG.debug(
            "audit_tokens_not_configured",
            extra={"reason": _TOKENS_UNCONFIGURED, "source": "ADAAD_AUDIT_TOKENS"},
        )
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
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
    auth = require_scopes(authorization, ("audit:read",))
    return {
        "scheme": str(auth["scheme"]),
        "scope": "audit:read",
        "redaction": str(auth.get("redaction") or "sensitive"),
    }


def require_audit_write_scope(authorization: str | None) -> dict[str, str]:
    """Require audit:write bearer token scope.

    Phase 73 — seed review decisions require elevated write authority.
    SEED-REVIEW-AUTH-0: all seed review decision endpoints require audit:write.
    """
    auth = require_scopes(authorization, ("audit:write",))
    return {
        "scheme": str(auth["scheme"]),
        "scope": "audit:write",
        "redaction": str(auth.get("redaction") or "sensitive"),
    }


__all__ = [
    "load_audit_tokens",
    "require_audit_read_scope",
    "require_audit_write_scope",
]
