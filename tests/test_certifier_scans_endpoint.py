# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/certifier-scans endpoint — Phase 34.

Test IDs: T34-EP-01..12
"""

from __future__ import annotations

import json

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient

_TOKEN = "pr34-certifier-scans-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}

_REQUIRED_DATA_KEYS = {
    "records",
    "total_in_window",
    "rejection_rate",
    "certification_rate",
    "mutation_blocked_count",
    "fail_closed_count",
    "escalation_breakdown",
    "ledger_version",
}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestCertifierScansEndpoint:

    # T34-EP-01 — 200 OK on authenticated request
    def test_T34_EP_01_returns_200(self, client):
        resp = client.get("/governance/certifier-scans", headers=_AUTH)
        assert resp.status_code == 200

    # T34-EP-02 — schema_version == "1.0"
    def test_T34_EP_02_schema_version(self, client):
        body = client.get("/governance/certifier-scans", headers=_AUTH).json()
        assert body["schema_version"] == "1.0"

    # T34-EP-03 — all required data keys present
    def test_T34_EP_03_required_data_keys(self, client):
        data = client.get("/governance/certifier-scans", headers=_AUTH).json()["data"]
        for key in _REQUIRED_DATA_KEYS:
            assert key in data, f"missing data key: {key}"

    # T34-EP-04 — records is a list
    def test_T34_EP_04_records_is_list(self, client):
        data = client.get("/governance/certifier-scans", headers=_AUTH).json()["data"]
        assert isinstance(data["records"], list)

    # T34-EP-05 — ledger_version is "33.0"
    def test_T34_EP_05_ledger_version(self, client):
        data = client.get("/governance/certifier-scans", headers=_AUTH).json()["data"]
        assert data["ledger_version"] == "33.0"

    # T34-EP-06 — limit param accepted, returns 200
    def test_T34_EP_06_limit_param_accepted(self, client):
        resp = client.get(
            "/governance/certifier-scans", params={"limit": 5}, headers=_AUTH
        )
        assert resp.status_code == 200

    # T34-EP-07 — rejected_only param accepted, returns 200
    def test_T34_EP_07_rejected_only_param_accepted(self, client):
        resp = client.get(
            "/governance/certifier-scans", params={"rejected_only": True}, headers=_AUTH
        )
        assert resp.status_code == 200

    # T34-EP-08 — 401 on missing Authorization header
    def test_T34_EP_08_missing_auth_401(self, client):
        resp = client.get("/governance/certifier-scans")
        assert resp.status_code == 401

    # T34-EP-09 — 403 on valid token with insufficient scope
    def test_T34_EP_09_wrong_scope_403(self, client, monkeypatch):
        bad_token = "bad-scope-token"
        monkeypatch.setenv(
            "ADAAD_AUDIT_TOKENS",
            json.dumps({bad_token: ["write:mutations"]}),
        )
        resp = client.get(
            "/governance/certifier-scans",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 403

    # T34-EP-10 — rejection_rate is a float in [0.0, 1.0]
    def test_T34_EP_10_rejection_rate_is_float_in_range(self, client):
        data = client.get("/governance/certifier-scans", headers=_AUTH).json()["data"]
        rr = data["rejection_rate"]
        assert isinstance(rr, float)
        assert 0.0 <= rr <= 1.0

    # T34-EP-11 — certification_rate + rejection_rate == 1.0
    def test_T34_EP_11_certification_plus_rejection_equals_1(self, client):
        data = client.get("/governance/certifier-scans", headers=_AUTH).json()["data"]
        total = round(data["certification_rate"] + data["rejection_rate"], 9)
        assert total == pytest.approx(1.0)

    # T34-EP-12 — escalation_breakdown is a dict
    def test_T34_EP_12_escalation_breakdown_is_dict(self, client):
        data = client.get("/governance/certifier-scans", headers=_AUTH).json()["data"]
        assert isinstance(data["escalation_breakdown"], dict)
