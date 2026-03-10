# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/threat-scans endpoint — Phase 30.

Test IDs: T30-EP-01..10
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

_TOKEN = "pr30-threat-scan-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestThreatScansEndpoint:
    def test_T30_EP_01_returns_200(self, client):
        resp = client.get("/governance/threat-scans", headers=_AUTH)
        assert resp.status_code == 200

    def test_T30_EP_02_schema_version_present(self, client):
        assert client.get("/governance/threat-scans", headers=_AUTH).json()["schema_version"] == "1.0"

    def test_T30_EP_03_data_keys_present(self, client):
        data = client.get("/governance/threat-scans", headers=_AUTH).json()["data"]
        for key in ("records", "total_in_window", "triggered_rate", "escalation_rate",
                    "avg_risk_score", "recommendation_breakdown", "risk_level_breakdown",
                    "ledger_version"):
            assert key in data, f"missing: {key}"

    def test_T30_EP_04_records_is_list(self, client):
        data = client.get("/governance/threat-scans", headers=_AUTH).json()["data"]
        assert isinstance(data["records"], list)

    def test_T30_EP_05_ledger_version_30(self, client):
        data = client.get("/governance/threat-scans", headers=_AUTH).json()["data"]
        assert data["ledger_version"] == "30.0"

    def test_T30_EP_06_limit_param_accepted(self, client):
        resp = client.get("/governance/threat-scans", params={"limit": 5}, headers=_AUTH)
        assert resp.status_code == 200

    def test_T30_EP_07_recommendation_filter_accepted(self, client):
        resp = client.get(
            "/governance/threat-scans",
            params={"recommendation": "escalate"},
            headers=_AUTH,
        )
        assert resp.status_code == 200

    def test_T30_EP_08_triggered_only_param_accepted(self, client):
        resp = client.get(
            "/governance/threat-scans",
            params={"triggered_only": True},
            headers=_AUTH,
        )
        assert resp.status_code == 200

    def test_T30_EP_09_triggered_rate_is_float(self, client):
        data = client.get("/governance/threat-scans", headers=_AUTH).json()["data"]
        assert isinstance(data["triggered_rate"], float)

    def test_T30_EP_10_requires_auth(self, client):
        resp = client.get("/governance/threat-scans")
        assert resp.status_code in (401, 403)
