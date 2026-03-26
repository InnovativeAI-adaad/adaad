# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi import HTTPException

from security.unified_auth import require_action


def _hs256_jwt(secret: str, payload: dict[str, object], *, kid: str = "legacy-hs256") -> str:
    header = {"alg": "HS256", "typ": "JWT", "kid": kid}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    body = f"{header_b64}.{payload_b64}".encode()
    sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode().rstrip("=")
    return f"{header_b64}.{payload_b64}.{sig}"


@pytest.mark.regression_standard
def test_oidc_validation_with_issuer_audience_and_rbac(monkeypatch):
    secret = "oidc-secret"
    monkeypatch.setenv("ADAAD_AUTH_OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("ADAAD_AUTH_OIDC_AUDIENCE", "adaad-api")
    jwks = {
        "keys": [
            {
                "kty": "oct",
                "kid": "k1",
                "alg": "HS256",
                "k": base64.urlsafe_b64encode(secret.encode()).decode().rstrip("="),
            }
        ]
    }
    monkeypatch.setenv("ADAAD_AUTH_JWKS_JSON", json.dumps(jwks))

    token = _hs256_jwt(
        secret,
        {
            "sub": "operator-1",
            "iss": "https://issuer.example.com",
            "aud": "adaad-api",
            "exp": int(time.time()) + 300,
            "roles": ["approve"],
            "org_id": "org-1",
            "workspace_id": "ws-1",
        },
        kid="k1",
    )

    result = require_action(f"Bearer {token}", action="approve", org_id="org-1", workspace_id="ws-1")
    assert result["subject"] == "operator-1"
    assert "approve" in result["actions"]


@pytest.mark.regression_standard
def test_service_account_rotation_supports_multiple_credentials(monkeypatch):
    creds = {
        "svc-old": {"secret": "old-secret", "roles": ["write"], "sub": "service-account:ci"},
        "svc-new": {"secret": "new-secret", "roles": ["write"], "sub": "service-account:ci"},
    }
    monkeypatch.setenv("ADAAD_SERVICE_ACCOUNT_CREDENTIALS", json.dumps(creds))

    old_result = require_action("Bearer svc-old.old-secret", action="write")
    new_result = require_action("Bearer svc-new.new-secret", action="write")
    assert old_result["subject"] == "service-account:ci"
    assert new_result["subject"] == "service-account:ci"


@pytest.mark.regression_standard
def test_workspace_scope_mismatch_rejected(monkeypatch):
    creds = {
        "svc-bot": {
            "secret": "secret",
            "roles": ["merge"],
            "org_id": "org-main",
            "workspace_id": "ws-alpha",
        }
    }
    monkeypatch.setenv("ADAAD_SERVICE_ACCOUNT_CREDENTIALS", json.dumps(creds))

    with pytest.raises(HTTPException) as exc:
        require_action("Bearer svc-bot.secret", action="merge", workspace_id="ws-beta")
    assert exc.value.status_code == 403
    assert exc.value.detail == "workspace_scope_mismatch"
