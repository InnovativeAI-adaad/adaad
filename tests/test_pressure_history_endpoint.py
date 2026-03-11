# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/pressure-history endpoint — Phase 25 / PR-25-02"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient

_TOKEN = "pr25-ph-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    import server
    server._pressure_audit_ledger = None  # reset module state
    from server import app
    return TestClient(app, raise_server_exceptions=True)


def _seed_ledger(tmp_path: Path, health_scores: list[float]) -> Path:
    from runtime.governance.health_pressure_adaptor import HealthPressureAdaptor
    from runtime.governance.pressure_audit_ledger import PressureAuditLedger
    p = tmp_path / "pressure.jsonl"
    adaptor = HealthPressureAdaptor()
    ledger = PressureAuditLedger(p)
    for h in health_scores:
        ledger.emit(adaptor.compute(h))
    return p


class TestPressureHistoryEndpoint:
    def test_returns_200_with_schema(self, client, monkeypatch):
        monkeypatch.delenv("ADAAD_PRESSURE_LEDGER_PATH", raising=False)
        resp = client.get("/governance/pressure-history", headers=_AUTH)
        assert resp.status_code == 200
        assert "schema_version" in resp.json()
        assert "data" in resp.json()

    def test_no_auth_returns_401(self, client, monkeypatch):
        monkeypatch.delenv("ADAAD_PRESSURE_LEDGER_PATH", raising=False)
        resp = client.get("/governance/pressure-history")
        assert resp.status_code == 401

    def test_ledger_inactive_without_env(self, client, monkeypatch):
        monkeypatch.delenv("ADAAD_PRESSURE_LEDGER_PATH", raising=False)
        resp = client.get("/governance/pressure-history", headers=_AUTH)
        assert resp.json()["data"]["ledger_active"] is False

    def test_ledger_active_with_env_and_records(self, client, tmp_path, monkeypatch):
        p = _seed_ledger(tmp_path, [0.70, 0.90, 0.50])
        monkeypatch.setenv("ADAAD_PRESSURE_LEDGER_PATH", str(p))
        resp = client.get("/governance/pressure-history", headers=_AUTH)
        assert resp.json()["data"]["ledger_active"] is True

    def test_records_is_list(self, client, monkeypatch):
        monkeypatch.delenv("ADAAD_PRESSURE_LEDGER_PATH", raising=False)
        resp = client.get("/governance/pressure-history", headers=_AUTH)
        assert isinstance(resp.json()["data"]["records"], list)

    def test_tier_frequency_is_dict(self, client, tmp_path, monkeypatch):
        p = _seed_ledger(tmp_path, [0.70, 0.90, 0.50])
        monkeypatch.setenv("ADAAD_PRESSURE_LEDGER_PATH", str(p))
        resp = client.get("/governance/pressure-history", headers=_AUTH)
        assert isinstance(resp.json()["data"]["tier_frequency"], dict)

    def test_total_queried_is_int(self, client, tmp_path, monkeypatch):
        p = _seed_ledger(tmp_path, [0.70, 0.90])
        monkeypatch.setenv("ADAAD_PRESSURE_LEDGER_PATH", str(p))
        resp = client.get("/governance/pressure-history", headers=_AUTH)
        assert isinstance(resp.json()["data"]["total_queried"], int)

    def test_pressure_tier_filter(self, client, tmp_path, monkeypatch):
        p = _seed_ledger(tmp_path, [0.70, 0.90, 0.50, 0.70])
        monkeypatch.setenv("ADAAD_PRESSURE_LEDGER_PATH", str(p))
        resp = client.get(
            "/governance/pressure-history?pressure_tier=elevated",
            headers=_AUTH,
        )
        records = resp.json()["data"]["records"]
        assert all(r["pressure_tier"] == "elevated" for r in records)

    def test_limit_too_large_returns_422(self, client, monkeypatch):
        monkeypatch.delenv("ADAAD_PRESSURE_LEDGER_PATH", raising=False)
        resp = client.get("/governance/pressure-history?limit=501", headers=_AUTH)
        assert resp.status_code == 422

    def test_ledger_path_is_str_or_null(self, client, monkeypatch):
        monkeypatch.delenv("ADAAD_PRESSURE_LEDGER_PATH", raising=False)
        data = client.get("/governance/pressure-history", headers=_AUTH).json()["data"]
        assert data["ledger_path"] is None or isinstance(data["ledger_path"], str)

    def test_records_have_required_fields(self, client, tmp_path, monkeypatch):
        p = _seed_ledger(tmp_path, [0.70])
        monkeypatch.setenv("ADAAD_PRESSURE_LEDGER_PATH", str(p))
        resp = client.get("/governance/pressure-history", headers=_AUTH)
        records = resp.json()["data"]["records"]
        assert len(records) == 1
        for key in ("pressure_tier", "health_band", "adjustment_digest"):
            assert key in records[0]

    def test_schema_version_1_0(self, client, monkeypatch):
        monkeypatch.delenv("ADAAD_PRESSURE_LEDGER_PATH", raising=False)
        resp = client.get("/governance/pressure-history", headers=_AUTH)
        assert resp.json()["schema_version"] == "1.0"
