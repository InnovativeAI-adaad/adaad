# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/admission-status endpoint — Phase 25.

Test IDs: T25-EP-01..12
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

_TOKEN = "pr25-admission-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestAdmissionStatusEndpoint:
    def test_returns_200_with_schema(self, client):               # T25-EP-01
        resp = client.get("/governance/admission-status", headers=_AUTH)
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_version"] == "1.0"
        assert "data" in body

    def test_data_fields_present(self, client):                   # T25-EP-02
        resp = client.get("/governance/admission-status", headers=_AUTH)
        data = resp.json()["data"]
        expected = {
            "health_score", "mutation_risk_score", "admission_band",
            "risk_threshold", "admitted", "admits_all", "epoch_paused",
            "deferral_reason", "advisory_only", "decision_digest",
            "controller_version",
        }
        assert expected.issubset(set(data.keys()))

    def test_advisory_only_always_true(self, client):             # T25-EP-03
        resp = client.get("/governance/admission-status", headers=_AUTH)
        assert resp.json()["data"]["advisory_only"] is True

    def test_controller_version(self, client):                    # T25-EP-04
        resp = client.get("/governance/admission-status", headers=_AUTH)
        assert resp.json()["data"]["controller_version"] == "25.0"

    def test_default_risk_score(self, client):                    # T25-EP-05
        resp = client.get("/governance/admission-status", headers=_AUTH)
        assert resp.json()["data"]["mutation_risk_score"] == pytest.approx(0.50, abs=1e-6)

    def test_custom_risk_score_low(self, client):                 # T25-EP-06
        resp = client.get(
            "/governance/admission-status",
            params={"risk_score": 0.10},
            headers=_AUTH,
        )
        assert resp.json()["data"]["mutation_risk_score"] == pytest.approx(0.10, abs=1e-6)

    def test_custom_risk_score_high(self, client):                # T25-EP-07
        resp = client.get(
            "/governance/admission-status",
            params={"risk_score": 0.90},
            headers=_AUTH,
        )
        data = resp.json()["data"]
        assert data["mutation_risk_score"] == pytest.approx(0.90, abs=1e-6)

    def test_digest_is_sha256_prefixed(self, client):             # T25-EP-08
        resp = client.get("/governance/admission-status", headers=_AUTH)
        digest = resp.json()["data"]["decision_digest"]
        assert digest.startswith("sha256:")

    def test_admission_band_valid_values(self, client):           # T25-EP-09
        resp = client.get("/governance/admission-status", headers=_AUTH)
        band = resp.json()["data"]["admission_band"]
        assert band in {"green", "amber", "red", "halt"}

    def test_risk_threshold_is_float(self, client):               # T25-EP-10
        resp = client.get("/governance/admission-status", headers=_AUTH)
        rt = resp.json()["data"]["risk_threshold"]
        assert isinstance(rt, float)

    def test_no_auth_rejected(self, client):                      # T25-EP-11
        resp = client.get("/governance/admission-status")
        assert resp.status_code in {401, 403}

    def test_clamped_risk_score_above_1(self, client):            # T25-EP-12
        resp = client.get(
            "/governance/admission-status",
            params={"risk_score": 5.0},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["mutation_risk_score"] == pytest.approx(1.0, abs=1e-6)
