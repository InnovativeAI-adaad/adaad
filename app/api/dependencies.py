from __future__ import annotations

from typing import Any

from fastapi import Depends, Header


def auth_context(authorization: str | None = Header(default=None)) -> str | None:
    """Extract the shared Authorization header context for API dependencies."""
    return authorization


def require_audit_scope(authorization: str | None = Depends(auth_context)) -> dict[str, Any]:
    """Enforce audit:read scope and return normalized auth metadata."""
    import server as _server

    return _server._require_audit_read_scope(authorization)


def require_gate_open() -> dict[str, Any]:
    """Enforce that the Cryovant gate is open and return gate metadata."""
    import server as _server

    return _server._assert_gate_open()
