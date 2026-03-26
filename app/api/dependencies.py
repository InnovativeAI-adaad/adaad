from __future__ import annotations

from typing import Any

from fastapi import Depends, Header

from runtime.audit_auth import require_audit_read_scope


def auth_context(authorization: str | None = Header(default=None)) -> str | None:
    """Extract the shared Authorization header context for API dependencies."""
    return authorization


def require_audit_scope(authorization: str | None = Depends(auth_context)) -> dict[str, Any]:
    """Enforce read-level access and return normalized auth metadata."""
    return require_audit_read_scope(authorization)


def require_gate_open() -> dict[str, Any]:
    """Enforce that the Cryovant gate is open and return gate metadata."""
    import server as _server

    return _server._assert_gate_open()
