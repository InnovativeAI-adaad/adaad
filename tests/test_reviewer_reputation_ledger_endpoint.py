# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/reviewer-reputation-ledger endpoint — Phase 37.

Test IDs: T37-EP-01..12
"""

from __future__ import annotations

import json

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient

_TOKEN = "pr37-reputation-ledger-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}

_REQUIRED_DATA_KEYS = {
    "entries",
    "total_in_window",
    "total_entries",
    "decision_breakdown",
    "chain_integrity_valid",
    "ledger_digest",
    "ledger_format_version",
}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestReviewerReputationLedgerEndpoint:

    # T37-EP-01 — 200 OK with valid bearer token
    def test_T37_EP_01_status_200(self, client):
        resp = client.get("/governance/reviewer-reputation-ledger", headers=_AUTH)
        assert resp.status_code == 200

    # T37-EP-02 — response includes schema_version "1.0"
    def test_T37_EP_02_schema_version(self, client):
        resp = client.get("/governance/reviewer-reputation-ledger", headers=_AUTH)
        assert resp.json()["schema_version"] == "1.0"

    # T37-EP-03 — data block contains all required keys
    def test_T37_EP_03_required_data_keys(self, client):
        data = client.get("/governance/reviewer-reputation-ledger", headers=_AUTH).json()["data"]
        assert _REQUIRED_DATA_KEYS.issubset(data.keys())

    # T37-EP-04 — entries is a list
    def test_T37_EP_04_entries_is_list(self, client):
        data = client.get("/governance/reviewer-reputation-ledger", headers=_AUTH).json()["data"]
        assert isinstance(data["entries"], list)

    # T37-EP-05 — ledger_format_version is "1.0"
    def test_T37_EP_05_ledger_format_version(self, client):
        data = client.get("/governance/reviewer-reputation-ledger", headers=_AUTH).json()["data"]
        assert data["ledger_format_version"] == "1.0"

    # T37-EP-06 — 401 when authorization header missing
    def test_T37_EP_06_missing_auth_401(self, client):
        resp = client.get("/governance/reviewer-reputation-ledger")
        assert resp.status_code == 401

    # T37-EP-07 — 403 when token lacks audit:read scope
    def test_T37_EP_07_wrong_scope_403(self, client, monkeypatch):
        bad_token = "bad-scope-token"
        monkeypatch.setenv(
            "ADAAD_AUDIT_TOKENS",
            json.dumps({bad_token: ["other:scope"]}),
        )
        resp = client.get(
            "/governance/reviewer-reputation-ledger",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 403

    # T37-EP-08 — total_in_window is a non-negative int
    def test_T37_EP_08_total_in_window_nonneg_int(self, client):
        data = client.get("/governance/reviewer-reputation-ledger", headers=_AUTH).json()["data"]
        assert isinstance(data["total_in_window"], int)
        assert data["total_in_window"] >= 0

    # T37-EP-09 — total_entries is a non-negative int
    def test_T37_EP_09_total_entries_nonneg_int(self, client):
        data = client.get("/governance/reviewer-reputation-ledger", headers=_AUTH).json()["data"]
        assert isinstance(data["total_entries"], int)
        assert data["total_entries"] >= 0

    # T37-EP-10 — total_in_window <= total_entries
    def test_T37_EP_10_window_le_total(self, client):
        data = client.get("/governance/reviewer-reputation-ledger", headers=_AUTH).json()["data"]
        assert data["total_in_window"] <= data["total_entries"]

    # T37-EP-11 — chain_integrity_valid is a bool
    def test_T37_EP_11_chain_integrity_is_bool(self, client):
        data = client.get("/governance/reviewer-reputation-ledger", headers=_AUTH).json()["data"]
        assert isinstance(data["chain_integrity_valid"], bool)

    # T37-EP-12 — decision_breakdown is a dict
    def test_T37_EP_12_decision_breakdown_is_dict(self, client):
        data = client.get("/governance/reviewer-reputation-ledger", headers=_AUTH).json()["data"]
        assert isinstance(data["decision_breakdown"], dict)
