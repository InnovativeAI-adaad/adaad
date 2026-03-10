# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/mutation-ledger endpoint — Phase 38.

Test IDs: T38-EP-01..12
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

_TOKEN = "pr38-mutation-ledger-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}

_REQUIRED_DATA_KEYS = {
    "entries",
    "total_in_window",
    "total_entries",
    "promoted_count",
    "last_hash",
    "ledger_version",
}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestMutationLedgerEndpoint:

    # T38-EP-01 — 200 OK with valid bearer token
    def test_T38_EP_01_status_200(self, client):
        resp = client.get("/governance/mutation-ledger", headers=_AUTH)
        assert resp.status_code == 200

    # T38-EP-02 — response includes schema_version "1.0"
    def test_T38_EP_02_schema_version(self, client):
        resp = client.get("/governance/mutation-ledger", headers=_AUTH)
        assert resp.json()["schema_version"] == "1.0"

    # T38-EP-03 — data block contains all required keys
    def test_T38_EP_03_required_data_keys(self, client):
        data = client.get("/governance/mutation-ledger", headers=_AUTH).json()["data"]
        assert _REQUIRED_DATA_KEYS.issubset(data.keys())

    # T38-EP-04 — entries is a list
    def test_T38_EP_04_entries_is_list(self, client):
        data = client.get("/governance/mutation-ledger", headers=_AUTH).json()["data"]
        assert isinstance(data["entries"], list)

    # T38-EP-05 — ledger_version is "1.0"
    def test_T38_EP_05_ledger_version(self, client):
        data = client.get("/governance/mutation-ledger", headers=_AUTH).json()["data"]
        assert data["ledger_version"] == "1.0"

    # T38-EP-06 — 401 when authorization header missing
    def test_T38_EP_06_missing_auth_401(self, client):
        resp = client.get("/governance/mutation-ledger")
        assert resp.status_code == 401

    # T38-EP-07 — 403 when token lacks audit:read scope
    def test_T38_EP_07_wrong_scope_403(self, client, monkeypatch):
        bad_token = "bad-scope-token"
        monkeypatch.setenv(
            "ADAAD_AUDIT_TOKENS",
            json.dumps({bad_token: ["other:scope"]}),
        )
        resp = client.get(
            "/governance/mutation-ledger",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 403

    # T38-EP-08 — total_in_window is a non-negative int
    def test_T38_EP_08_total_in_window_nonneg_int(self, client):
        data = client.get("/governance/mutation-ledger", headers=_AUTH).json()["data"]
        assert isinstance(data["total_in_window"], int)
        assert data["total_in_window"] >= 0

    # T38-EP-09 — total_entries is a non-negative int
    def test_T38_EP_09_total_entries_nonneg_int(self, client):
        data = client.get("/governance/mutation-ledger", headers=_AUTH).json()["data"]
        assert isinstance(data["total_entries"], int)
        assert data["total_entries"] >= 0

    # T38-EP-10 — total_in_window <= total_entries
    def test_T38_EP_10_window_le_total(self, client):
        data = client.get("/governance/mutation-ledger", headers=_AUTH).json()["data"]
        assert data["total_in_window"] <= data["total_entries"]

    # T38-EP-11 — promoted_count is a non-negative int
    def test_T38_EP_11_promoted_count_nonneg_int(self, client):
        data = client.get("/governance/mutation-ledger", headers=_AUTH).json()["data"]
        assert isinstance(data["promoted_count"], int)
        assert data["promoted_count"] >= 0

    # T38-EP-12 — last_hash is a string starting with "sha256:"
    def test_T38_EP_12_last_hash_sha256_prefix(self, client):
        data = client.get("/governance/mutation-ledger", headers=_AUTH).json()["data"]
        assert isinstance(data["last_hash"], str)
        assert data["last_hash"].startswith("sha256:")
