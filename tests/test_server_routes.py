# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from fastapi.testclient import TestClient

import server


def test_whaledic_static_route() -> None:
    with TestClient(server.app) as client:
        response = client.get('/ui/developer/ADAADdev/whaledic.html')

    assert response.status_code == 200
    assert 'text/html' in response.headers.get('content-type', '')
