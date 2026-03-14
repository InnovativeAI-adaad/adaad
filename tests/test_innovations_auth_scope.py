# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import server

pytestmark = pytest.mark.regression_standard

_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/innovations/oracle"),
    ("GET", "/innovations/story-mode"),
    ("GET", "/innovations/federation-map"),
    ("POST", "/innovations/seeds/register"),
]


def _request(client: TestClient, method: str, path: str, headers: dict[str, str] | None = None):
    if method == "GET":
        return client.get(path, headers=headers or {})
    return client.post(path, headers=headers or {}, json=[])


@pytest.mark.parametrize(("method", "path"), _ENDPOINTS)
def test_innovations_requires_authentication(method: str, path: str) -> None:
    with TestClient(server.app) as client:
        response = _request(client, method, path)

    assert response.status_code == 401
    assert response.json() == {"detail": "missing_authentication"}


@pytest.mark.parametrize(("method", "path"), _ENDPOINTS)
def test_innovations_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch, method: str, path: str) -> None:
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({"known-token": ["audit:read"]}))
    with TestClient(server.app) as client:
        response = _request(client, method, path, {"Authorization": "Bearer wrong-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


@pytest.mark.parametrize(("method", "path"), _ENDPOINTS)
def test_innovations_rejects_insufficient_scope(monkeypatch: pytest.MonkeyPatch, method: str, path: str) -> None:
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({"audit-token": ["metrics:read"]}))
    with TestClient(server.app) as client:
        response = _request(client, method, path, {"Authorization": "Bearer audit-token"})

    assert response.status_code == 403
    assert response.json() == {"detail": "insufficient_scope"}


@pytest.mark.parametrize(("method", "path"), _ENDPOINTS)
def test_innovations_accepts_valid_scope(monkeypatch: pytest.MonkeyPatch, method: str, path: str) -> None:
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({"audit-token": ["audit:read"]}))
    with TestClient(server.app) as client:
        response = _request(client, method, path, {"Authorization": "Bearer audit-token"})

    assert response.status_code == 200
