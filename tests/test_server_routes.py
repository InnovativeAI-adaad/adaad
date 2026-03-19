# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import server


def test_whaledic_static_route() -> None:
    with TestClient(server.app) as client:
        response = client.get('/ui/developer/ADAADdev/whaledic.html')

    assert response.status_code == 200
    assert 'text/html' in response.headers.get('content-type', '')
    assert 'window.__anthropic_key_available' in response.text


def test_whaledic_static_route_blocks_path_traversal() -> None:
    with TestClient(server.app) as client:
        response = client.get('/ui/developer/ADAADdev/%2e%2e/%2e%2e/etc/passwd')

    assert response.status_code == 404
    assert response.json().get('detail') == 'path_traversal_blocked'


def test_server_startup_fails_when_required_whaledic_secret_missing(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_WHALEDIC_DORK_ENABLED", "1")
    monkeypatch.delenv("ADAAD_WHALEDIC_ANTHROPIC_API_KEY_ENC", raising=False)
    monkeypatch.delenv("ADAAD_WHALEDIC_ANTHROPIC_API_KEY_KEYRING", raising=False)

    with pytest.raises(RuntimeError, match="whaledic_secret_missing_required"):
        with TestClient(server.app):
            pass

    monkeypatch.delenv("ADAAD_WHALEDIC_DORK_ENABLED", raising=False)
