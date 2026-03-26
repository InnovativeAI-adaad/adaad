# SPDX-License-Identifier: Apache-2.0
"""Unified authentication and authorization helpers.

Supports OIDC JWT validation, org/workspace claim enforcement,
service-account credential validation, and role-based action checks.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import HTTPException

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthContext:
    """Normalized auth context produced by the unified validator."""

    scheme: str
    subject: str
    org_id: str | None
    workspace_id: str | None
    roles: tuple[str, ...]
    actions: tuple[str, ...]
    scopes: tuple[str, ...]
    token_type: str
    redaction: str = "sensitive"

    def as_dict(self) -> dict[str, Any]:
        return {
            "scheme": self.scheme,
            "subject": self.subject,
            "org_id": self.org_id,
            "workspace_id": self.workspace_id,
            "roles": list(self.roles),
            "actions": list(self.actions),
            "scopes": list(self.scopes),
            "scope": " ".join(self.scopes),
            "token_type": self.token_type,
            "redaction": self.redaction,
        }


_ROLE_ACTIONS: dict[str, tuple[str, ...]] = {
    "read": ("read",),
    "write": ("read", "write"),
    "approve": ("read", "write", "approve"),
    "merge": ("read", "write", "approve", "merge"),
    "admin": ("read", "write", "approve", "merge"),
}


def _b64url_decode(value: str) -> bytes:
    padding_chars = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding_chars).encode("utf-8"))


def _decode_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid_token") from exc
    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, base64.binascii.Error) as exc:
        raise HTTPException(status_code=401, detail="invalid_token") from exc
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise HTTPException(status_code=401, detail="invalid_token")
    return header, payload, signature_b64


def _load_json_mapping(path: str) -> Mapping[str, Any] | None:
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return None
    except json.JSONDecodeError:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _load_jwks() -> dict[str, Any]:
    inline = os.getenv("ADAAD_AUTH_JWKS_JSON", "").strip()
    if inline:
        try:
            data = json.loads(inline)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            LOG.warning("auth_jwks_json_parse_failed")

    path = os.getenv("ADAAD_AUTH_JWKS_PATH", "").strip()
    if path:
        loaded = _load_json_mapping(path)
        if loaded is not None:
            return dict(loaded)

    url = os.getenv("ADAAD_AUTH_JWKS_URL", "").strip()
    if url:
        try:
            with urlopen(url, timeout=2.0) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
            loaded = json.loads(body)
            if isinstance(loaded, dict):
                return loaded
        except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
            LOG.warning("auth_jwks_url_fetch_failed", extra={"url": url})

    legacy_secret = os.getenv("ADAAD_MCP_JWT_SECRET", "").strip()
    if legacy_secret:
        secret_b64 = base64.urlsafe_b64encode(legacy_secret.encode("utf-8")).decode("utf-8").rstrip("=")
        return {
            "keys": [
                {
                    "kty": "oct",
                    "kid": "legacy-hs256",
                    "alg": "HS256",
                    "k": secret_b64,
                }
            ]
        }

    return {"keys": []}


def _pick_jwk(header: Mapping[str, Any], jwks: Mapping[str, Any]) -> Mapping[str, Any]:
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise HTTPException(status_code=401, detail="invalid_token")
    kid = str(header.get("kid") or "")
    alg = str(header.get("alg") or "")

    if kid:
        for key in keys:
            if isinstance(key, dict) and str(key.get("kid") or "") == kid:
                return key

    if alg:
        for key in keys:
            if isinstance(key, dict) and str(key.get("alg") or "") == alg:
                return key

    if len(keys) == 1 and isinstance(keys[0], dict):
        return keys[0]

    raise HTTPException(status_code=401, detail="invalid_token")


def _verify_signature(header: Mapping[str, Any], token: str, signature_b64: str, jwk: Mapping[str, Any]) -> None:
    alg = str(header.get("alg") or "")
    if alg == "none":
        raise HTTPException(status_code=401, detail="invalid_token")
    signed_content = token.rsplit(".", 1)[0].encode("utf-8")
    try:
        signature = _b64url_decode(signature_b64)
    except (ValueError, base64.binascii.Error) as exc:
        raise HTTPException(status_code=401, detail="invalid_token") from exc

    if alg == "HS256":
        secret = _b64url_decode(str(jwk.get("k") or ""))
        digest = hmac.new(secret, signed_content, hashlib.sha256).digest()
        if not hmac.compare_digest(digest, signature):
            raise HTTPException(status_code=401, detail="invalid_token")
        return

    raise HTTPException(status_code=401, detail="unsupported_token_algorithm")


def _normalized_claim_set(claims: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    scope_raw = str(claims.get("scope") or "").strip()
    scopes: list[str] = [s for s in scope_raw.split(" ") if s]
    extra_scopes = claims.get("scopes")
    if isinstance(extra_scopes, list):
        scopes.extend(str(item) for item in extra_scopes)

    roles_raw = claims.get("roles")
    roles: list[str] = []
    if isinstance(roles_raw, list):
        roles.extend(str(item) for item in roles_raw)

    actions_raw = claims.get("actions")
    actions: list[str] = []
    if isinstance(actions_raw, list):
        actions.extend(str(item) for item in actions_raw)

    for role in roles:
        actions.extend(_ROLE_ACTIONS.get(role, ()))

    if "audit:read" in scopes:
        actions.append("read")
    if "audit:write" in scopes:
        actions.append("write")

    return tuple(sorted(set(scopes))), tuple(sorted(set(roles))), tuple(sorted(set(actions)))


def _validate_standard_claims(claims: Mapping[str, Any]) -> None:
    now = int(time.time())
    exp = int(claims.get("exp", 0) or 0)
    if exp <= 0 or exp < now:
        raise HTTPException(status_code=401, detail="expired_token")

    not_before = int(claims.get("nbf", 0) or 0)
    if not_before and not_before > now:
        raise HTTPException(status_code=401, detail="invalid_token")

    issuer = os.getenv("ADAAD_AUTH_OIDC_ISSUER", "").strip()
    if issuer and str(claims.get("iss") or "") != issuer:
        raise HTTPException(status_code=401, detail="invalid_issuer")

    configured_aud = [a.strip() for a in os.getenv("ADAAD_AUTH_OIDC_AUDIENCE", "").split(",") if a.strip()]
    if configured_aud:
        token_aud = claims.get("aud")
        if isinstance(token_aud, str):
            token_auds = {token_aud}
        elif isinstance(token_aud, list):
            token_auds = {str(item) for item in token_aud}
        else:
            token_auds = set()
        if not token_auds.intersection(set(configured_aud)):
            raise HTTPException(status_code=401, detail="invalid_audience")


def _extract_service_accounts() -> dict[str, dict[str, Any]]:
    raw = os.getenv("ADAAD_SERVICE_ACCOUNT_CREDENTIALS", "").strip()
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        LOG.warning("service_account_credentials_malformed")
        return {}
    if not isinstance(decoded, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for credential_id, value in decoded.items():
        if not isinstance(credential_id, str) or not isinstance(value, dict):
            continue
        normalized[credential_id] = dict(value)
    return normalized


def _authenticate_service_account(token: str) -> AuthContext:
    if "." not in token:
        raise HTTPException(status_code=401, detail="invalid_token")
    credential_id, secret = token.split(".", 1)
    accounts = _extract_service_accounts()
    record = accounts.get(credential_id)
    if not isinstance(record, dict):
        raise HTTPException(status_code=401, detail="invalid_token")
    configured_secret = str(record.get("secret") or "")
    if not configured_secret or not hmac.compare_digest(secret, configured_secret):
        raise HTTPException(status_code=401, detail="invalid_token")

    expires_at = int(record.get("expires_at", 0) or 0)
    if expires_at and expires_at < int(time.time()):
        raise HTTPException(status_code=401, detail="expired_token")

    scopes, roles, actions = _normalized_claim_set(record)
    subject = str(record.get("sub") or f"service-account:{credential_id}")
    return AuthContext(
        scheme="bearer",
        subject=subject,
        org_id=str(record.get("org_id") or "") or None,
        workspace_id=str(record.get("workspace_id") or "") or None,
        roles=roles,
        actions=actions,
        scopes=scopes,
        token_type="service_account",
    )


def _authenticate_legacy_audit_token(token: str) -> AuthContext | None:
    raw = os.getenv("ADAAD_AUDIT_TOKENS", "").strip()
    if not raw:
        return None
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None

    matched_scopes: list[str] | None = None
    for configured_token, scopes in decoded.items():
        if not isinstance(configured_token, str):
            continue
        if hmac.compare_digest(token, configured_token) and isinstance(scopes, list):
            matched_scopes = [str(item) for item in scopes]
            break
    if matched_scopes is None:
        return None

    claims = {"scope": " ".join(matched_scopes), "sub": "audit-token"}
    scopes, roles, actions = _normalized_claim_set(claims)
    return AuthContext(
        scheme="bearer",
        subject="audit-token",
        org_id=None,
        workspace_id=None,
        roles=roles,
        actions=actions,
        scopes=scopes,
        token_type="legacy_token",
    )


def authenticate_bearer(authorization: str | None) -> AuthContext:
    """Authenticate a bearer token and return normalized context."""
    if not authorization:
        raise HTTPException(status_code=401, detail="missing_authentication")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="missing_authentication")

    legacy = _authenticate_legacy_audit_token(token)
    if legacy is not None:
        return legacy

    if token.count(".") == 1:
        return _authenticate_service_account(token)

    header, claims, signature_b64 = _decode_jwt(token)
    jwks = _load_jwks()
    jwk = _pick_jwk(header, jwks)
    _verify_signature(header, token, signature_b64, jwk)
    _validate_standard_claims(claims)
    scopes, roles, actions = _normalized_claim_set(claims)
    if (
        os.getenv("ADAAD_MCP_JWT_SECRET", "").strip()
        and not scopes
        and not roles
        and not actions
    ):
        actions = _ROLE_ACTIONS["merge"]
    return AuthContext(
        scheme="bearer",
        subject=str(claims.get("sub") or "unknown"),
        org_id=str(claims.get("org_id") or "") or None,
        workspace_id=str(claims.get("workspace_id") or "") or None,
        roles=roles,
        actions=actions,
        scopes=scopes,
        token_type="oidc",
    )


def require_action(
    authorization: str | None,
    *,
    action: str,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Authenticate and authorize a principal for a control-plane action."""
    auth = authenticate_bearer(authorization)

    if action not in auth.actions:
        raise HTTPException(status_code=403, detail="insufficient_scope")

    if org_id and auth.org_id and not hmac.compare_digest(org_id, auth.org_id):
        raise HTTPException(status_code=403, detail="org_scope_mismatch")

    if workspace_id and auth.workspace_id and not hmac.compare_digest(workspace_id, auth.workspace_id):
        raise HTTPException(status_code=403, detail="workspace_scope_mismatch")

    return auth.as_dict()


def require_scopes(authorization: str | None, required_scopes: tuple[str, ...]) -> dict[str, Any]:
    """Authenticate and enforce one-or-more required OAuth style scopes."""
    auth = authenticate_bearer(authorization)
    for required in required_scopes:
        if not any(hmac.compare_digest(required, existing) for existing in auth.scopes):
            raise HTTPException(status_code=403, detail="insufficient_scope")
    return auth.as_dict()


__all__ = [
    "AuthContext",
    "authenticate_bearer",
    "require_action",
    "require_scopes",
]
