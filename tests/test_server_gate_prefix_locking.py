# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from fastapi.testclient import TestClient

import server


def _protected_probe_path(prefix: str) -> str:
    return f"{prefix}probe" if prefix.endswith("/") else prefix


def test_protected_prefixes_consistently_return_locked_when_gate_locked(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_GATE_LOCKED", "1")
    monkeypatch.setenv("ADAAD_GATE_REASON", "maintenance-window")

    with TestClient(server.app) as client:
        for prefix in server._GATE_PROTECTED_PREFIXES:
            response = client.get(_protected_probe_path(prefix))
            assert response.status_code == 423
            assert response.headers.get("X-ADAAD-GATE") == "locked"


def test_open_paths_keep_existing_behavior_when_gate_locked(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_GATE_LOCKED", "1")
    monkeypatch.setenv("ADAAD_GATE_REASON", "maintenance-window")

    with TestClient(server.app) as client:
        health = client.get("/api/health")
        version = client.get("/api/version")
        nexus_health = client.get("/api/nexus/health")

    assert health.status_code == 200
    assert version.status_code == 200

    # Existing semantics: open middleware path, but endpoint itself reflects lock.
    assert nexus_health.status_code == 423
    assert nexus_health.headers.get("X-ADAAD-GATE") == "locked"
