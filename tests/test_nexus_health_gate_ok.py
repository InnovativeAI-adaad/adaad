"""
T-NEXUS-HEALTH — /api/nexus/health must return gate_ok field.

Root cause that prompted this test:
  probeHealth() in ui/aponi/index.html checks `data.gate_ok !== true`.
  nexus_health() was returning `ok` but NOT `gate_ok`.
  Result: gate_ok always falsy → UI locked even when gate is open.
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ADAAD_ENV", "dev")
os.environ.setdefault("CRYOVANT_DEV_MODE", "1")


@pytest.fixture(scope="module")
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=False)


class TestNexusHealthGateOk:
    def test_returns_200(self, client):
        res = client.get("/api/nexus/health")
        assert res.status_code == 200

    def test_gate_ok_field_present(self, client):
        """gate_ok must be present — UI probeHealth() checks data.gate_ok !== true."""
        data = client.get("/api/nexus/health").json()
        assert "gate_ok" in data, (
            "gate_ok missing from /api/nexus/health — UI will always show LOCKED"
        )

    def test_gate_ok_is_true_when_unlocked(self, client):
        """gate_ok must be boolean True (not just truthy) — UI uses strict !== true."""
        data = client.get("/api/nexus/health").json()
        assert data["gate_ok"] is True, (
            f"gate_ok={data['gate_ok']!r} — UI checks `=== true`, must be exactly True"
        )

    def test_ok_field_also_present(self, client):
        data = client.get("/api/nexus/health").json()
        assert "ok" in data

    def test_ok_matches_gate_ok(self, client):
        """ok and gate_ok must agree — both reflect gate open/closed state."""
        data = client.get("/api/nexus/health").json()
        assert data["ok"] == data["gate_ok"]

    def test_protocol_field_present(self, client):
        data = client.get("/api/nexus/health").json()
        assert data.get("protocol") == "adaad-gate/1.0"

    def test_gate_subobject_present(self, client):
        data = client.get("/api/nexus/health").json()
        assert isinstance(data.get("gate"), dict)

    def test_gate_locked_false_when_open(self, client):
        data = client.get("/api/nexus/health").json()
        assert data["gate"]["locked"] is False
