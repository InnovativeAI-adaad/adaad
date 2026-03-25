from __future__ import annotations

from typing import Any


def require_audit_scope(authorization: str | None) -> dict[str, Any]:
    import server as _server

    return _server._require_audit_read_scope(authorization)
