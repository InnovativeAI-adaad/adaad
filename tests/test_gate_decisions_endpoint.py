# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/gate-decisions endpoint — Phase 36.

Test IDs: T36-EP-01..12
"""

from __future__ import annotations

import json

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient

_TOKEN = "pr36-gate-decisions-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}

_REQUIRED_DATA_KEYS = {
    "records",
    "total_in_window",
    "approval_rate",
    "rejection_rate",
    "human_override_count",
    "decision_breakdown",
    "failed_rules_frequency",
    "trust_mode_breakdown",
    "ledger_version",
}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestGateDecisionsEndpoint:

    # T36-EP-01 — 200 OK with valid bearer token
    def test_T36_EP_01_status_200(self, client):
        resp = client.get("/governance/gate-decisions", headers=_AUTH)
        assert resp.status_code == 200

    # T36-EP-02 — response includes schema_version
    def test_T36_EP_02_schema_version(self, client):
        resp = client.get("/governance/gate-decisions", headers=_AUTH)
        assert resp.json()["schema_version"] == "1.0"

    # T36-EP-03 — data block contains all required keys
    def test_T36_EP_03_required_data_keys(self, client):
        data = client.get("/governance/gate-decisions", headers=_AUTH).json()["data"]
        assert _REQUIRED_DATA_KEYS.issubset(data.keys())

    # T36-EP-04 — records is a list
    def test_T36_EP_04_records_is_list(self, client):
        data = client.get("/governance/gate-decisions", headers=_AUTH).json()["data"]
        assert isinstance(data["records"], list)

    # T36-EP-05 — ledger_version is "35.0"
    def test_T36_EP_05_ledger_version(self, client):
        data = client.get("/governance/gate-decisions", headers=_AUTH).json()["data"]
        assert data["ledger_version"] == "35.0"

    # T36-EP-06 — 401 when authorization header missing
    def test_T36_EP_06_missing_auth_401(self, client):
        resp = client.get("/governance/gate-decisions")
        assert resp.status_code == 401

    # T36-EP-07 — 403 when token lacks audit:read scope
    def test_T36_EP_07_wrong_scope_403(self, client, monkeypatch):
        bad_token = "bad-scope-token"
        monkeypatch.setenv(
            "ADAAD_AUDIT_TOKENS",
            json.dumps({bad_token: ["other:scope"]}),
        )
        resp = client.get(
            "/governance/gate-decisions",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 403

    # T36-EP-08 — approval_rate is a float in [0.0, 1.0]
    def test_T36_EP_08_approval_rate_float_range(self, client):
        data = client.get("/governance/gate-decisions", headers=_AUTH).json()["data"]
        rate = data["approval_rate"]
        assert isinstance(rate, float)
        assert 0.0 <= rate <= 1.0

    # T36-EP-09 — rejection_rate is a float in [0.0, 1.0]
    def test_T36_EP_09_rejection_rate_float_range(self, client):
        data = client.get("/governance/gate-decisions", headers=_AUTH).json()["data"]
        rate = data["rejection_rate"]
        assert isinstance(rate, float)
        assert 0.0 <= rate <= 1.0

    # T36-EP-10 — approval_rate + rejection_rate == 1.0 (complement invariant)
    def test_T36_EP_10_rate_complement_invariant(self, client):
        data = client.get("/governance/gate-decisions", headers=_AUTH).json()["data"]
        assert abs(data["approval_rate"] + data["rejection_rate"] - 1.0) < 1e-5

    # T36-EP-11 — human_override_count is a non-negative int
    def test_T36_EP_11_human_override_count_nonneg_int(self, client):
        data = client.get("/governance/gate-decisions", headers=_AUTH).json()["data"]
        count = data["human_override_count"]
        assert isinstance(count, int)
        assert count >= 0

    # T36-EP-12 — decision_breakdown is a dict
    def test_T36_EP_12_decision_breakdown_is_dict(self, client):
        data = client.get("/governance/gate-decisions", headers=_AUTH).json()["data"]
        assert isinstance(data["decision_breakdown"], dict)
