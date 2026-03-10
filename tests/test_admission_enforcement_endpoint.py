# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/admission-enforcement endpoint — Phase 28.

Test IDs: T28-EP-01..10
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

_TOKEN = "pr28-enforcement-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))
    monkeypatch.delenv("ADAAD_SEVERITY_ESCALATIONS", raising=False)


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestAdmissionEnforcementEndpoint:
    def test_T28_EP_01_returns_200(self, client):
        resp = client.get("/governance/admission-enforcement", headers=_AUTH)
        assert resp.status_code == 200

    def test_T28_EP_02_schema_version_present(self, client):
        resp = client.get("/governance/admission-enforcement", headers=_AUTH)
        assert resp.json()["schema_version"] == "1.0"

    def test_T28_EP_03_data_contains_required_keys(self, client):
        resp = client.get("/governance/admission-enforcement", headers=_AUTH)
        data = resp.json()["data"]
        for key in ("escalation_mode", "blocked", "block_reason",
                    "verdict_digest", "enforcer_version", "decision"):
            assert key in data, f"missing key: {key}"

    def test_T28_EP_04_advisory_only_always_true(self, client):
        resp = client.get("/governance/admission-enforcement", headers=_AUTH)
        assert resp.json()["data"]["decision"]["advisory_only"] is True

    def test_T28_EP_05_default_escalation_mode_advisory(self, client):
        resp = client.get("/governance/admission-enforcement", headers=_AUTH)
        assert resp.json()["data"]["escalation_mode"] == "advisory"

    def test_T28_EP_06_blocked_false_in_advisory_mode(self, client):
        resp = client.get("/governance/admission-enforcement", headers=_AUTH)
        assert resp.json()["data"]["blocked"] is False

    def test_T28_EP_07_risk_score_query_param_accepted(self, client):
        resp = client.get(
            "/governance/admission-enforcement",
            params={"risk_score": 0.10},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["decision"]["mutation_risk_score"] == pytest.approx(0.10)

    def test_T28_EP_08_blocking_mode_via_env_var(self, client, monkeypatch):
        monkeypatch.setenv(
            "ADAAD_SEVERITY_ESCALATIONS",
            json.dumps({"admission_band_enforcement": "blocking"}),
        )
        # Even in blocking mode, GREEN band should not be blocked
        resp = client.get(
            "/governance/admission-enforcement",
            params={"risk_score": 0.10},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["escalation_mode"] == "blocking"
        # health defaults to 1.0 → green → not blocked
        assert data["blocked"] is False

    def test_T28_EP_09_enforcer_version_is_28(self, client):
        resp = client.get("/governance/admission-enforcement", headers=_AUTH)
        assert resp.json()["data"]["enforcer_version"] == "28.0"

    def test_T28_EP_10_requires_auth(self, client):
        resp = client.get("/governance/admission-enforcement")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# T29-EP — Phase 29: /governance/admission-audit enforcement fields
# ---------------------------------------------------------------------------

class TestAdmissionAuditPhase29Fields:
    """Verify Phase 29 enforcement fields appear in admission-audit response."""

    def test_T29_EP_01_audit_response_has_blocked_count(self, client):
        resp = client.get("/governance/admission-audit", headers=_AUTH)
        assert "blocked_count" in resp.json()["data"]

    def test_T29_EP_02_audit_response_has_enforcement_rate(self, client):
        resp = client.get("/governance/admission-audit", headers=_AUTH)
        assert "enforcement_rate" in resp.json()["data"]

    def test_T29_EP_03_audit_response_has_escalation_breakdown(self, client):
        resp = client.get("/governance/admission-audit", headers=_AUTH)
        assert "escalation_breakdown" in resp.json()["data"]

    def test_T29_EP_04_blocked_count_is_int(self, client):
        resp = client.get("/governance/admission-audit", headers=_AUTH)
        assert isinstance(resp.json()["data"]["blocked_count"], int)

    def test_T29_EP_05_ledger_version_is_29(self, client):
        resp = client.get("/governance/admission-audit", headers=_AUTH)
        assert resp.json()["data"]["ledger_version"] == "29.0"

    def test_T29_EP_06_blocked_only_param_accepted(self, client):
        resp = client.get(
            "/governance/admission-audit",
            params={"blocked_only": True},
            headers=_AUTH,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"]["records"], list)
