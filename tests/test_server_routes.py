# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from fastapi.testclient import TestClient

import server


def test_whaledic_static_route() -> None:
    with TestClient(server.app) as client:
        response = client.get('/ui/developer/ADAADdev/whaledic.html')

    assert response.status_code == 200
    assert 'text/html' in response.headers.get('content-type', '')


def test_whaledic_static_route_blocks_path_traversal() -> None:
    with TestClient(server.app) as client:
        response = client.get('/ui/developer/ADAADdev/%2e%2e/%2e%2e/etc/passwd')

    assert response.status_code == 404
    assert response.json().get('detail') == 'path_traversal_blocked'
