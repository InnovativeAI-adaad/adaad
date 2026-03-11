# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/admission-rate endpoint — Phase 26.

Test IDs: T26-EP-01..08
"""

from __future__ import annotations

import json

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient

_TOKEN = "pr26-admission-rate-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestAdmissionRateEndpoint:
    def test_returns_200(self, client):                        # T26-EP-01
        resp = client.get("/governance/admission-rate", headers=_AUTH)
        assert resp.status_code == 200

    def test_schema_version(self, client):                     # T26-EP-02
        resp = client.get("/governance/admission-rate", headers=_AUTH)
        assert resp.json()["schema_version"] == "1.0"

    def test_data_fields_present(self, client):                # T26-EP-03
        resp = client.get("/governance/admission-rate", headers=_AUTH)
        data = resp.json()["data"]
        expected = {
            "admission_rate_score", "admitted_count", "total_count",
            "epochs_in_window", "max_epochs", "report_digest", "tracker_version",
        }
        assert expected.issubset(set(data.keys()))

    def test_empty_tracker_score_is_one(self, client):         # T26-EP-04
        resp = client.get("/governance/admission-rate", headers=_AUTH)
        assert resp.json()["data"]["admission_rate_score"] == pytest.approx(1.0)

    def test_tracker_version(self, client):                    # T26-EP-05
        resp = client.get("/governance/admission-rate", headers=_AUTH)
        assert resp.json()["data"]["tracker_version"] == "26.0"

    def test_digest_sha256_prefixed(self, client):             # T26-EP-06
        resp = client.get("/governance/admission-rate", headers=_AUTH)
        assert resp.json()["data"]["report_digest"].startswith("sha256:")

    def test_no_auth_rejected(self, client):                   # T26-EP-07
        resp = client.get("/governance/admission-rate")
        assert resp.status_code in {401, 403}

    def test_total_count_zero_when_empty(self, client):        # T26-EP-08
        resp = client.get("/governance/admission-rate", headers=_AUTH)
        assert resp.json()["data"]["total_count"] == 0
