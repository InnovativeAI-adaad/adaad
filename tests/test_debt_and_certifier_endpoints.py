# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/debt + POST /governance/certify — Phase 31.

Test IDs: T31-EP-01..20
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient

_TOKEN = "pr31-debt-certifier-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# T31-EP-01..10 — GET /governance/debt
# ---------------------------------------------------------------------------

class TestGovernanceDebtEndpoint:
    def test_T31_EP_01_returns_200(self, client):
        resp = client.get("/governance/debt", headers=_AUTH)
        assert resp.status_code == 200

    def test_T31_EP_02_schema_version(self, client):
        assert client.get("/governance/debt", headers=_AUTH).json()["schema_version"] == "1.0"

    def test_T31_EP_03_data_keys_present(self, client):
        data = client.get("/governance/debt", headers=_AUTH).json()["data"]
        for key in (
            "epoch_id", "epoch_index", "compound_debt_score", "breach_threshold",
            "threshold_breached", "warning_count", "warning_weighted_sum",
            "decayed_prior_debt", "applied_decay_epochs", "warning_rules",
            "snapshot_hash", "debt_ledger_schema",
        ):
            assert key in data, f"missing: {key}"

    def test_T31_EP_04_compound_debt_is_float(self, client):
        data = client.get("/governance/debt", headers=_AUTH).json()["data"]
        assert isinstance(data["compound_debt_score"], (int, float))

    def test_T31_EP_05_threshold_breached_is_bool(self, client):
        data = client.get("/governance/debt", headers=_AUTH).json()["data"]
        assert isinstance(data["threshold_breached"], bool)

    def test_T31_EP_06_debt_schema_version(self, client):
        data = client.get("/governance/debt", headers=_AUTH).json()["data"]
        assert data["debt_ledger_schema"] == "1.0"

    def test_T31_EP_07_snapshot_hash_present(self, client):
        data = client.get("/governance/debt", headers=_AUTH).json()["data"]
        assert data["snapshot_hash"].startswith("sha256:")

    def test_T31_EP_08_zero_state_has_zero_debt(self, client):
        data = client.get("/governance/debt", headers=_AUTH).json()["data"]
        # Zero-state snapshot (no real epoch data) should have compound_debt_score=0
        assert data["compound_debt_score"] == pytest.approx(0.0)

    def test_T31_EP_09_warning_rules_is_list(self, client):
        data = client.get("/governance/debt", headers=_AUTH).json()["data"]
        assert isinstance(data["warning_rules"], list)

    def test_T31_EP_10_requires_auth(self, client):
        resp = client.get("/governance/debt")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# T31-EP-11..20 — POST /governance/certify
# ---------------------------------------------------------------------------

class TestGovernanceCertifyEndpoint:
    def _certify(self, client, file_path: str, **kwargs):
        body = {"file_path": file_path, **kwargs}
        return client.post("/governance/certify", json=body, headers=_AUTH)

    def test_T31_EP_11_returns_200_for_existing_file(self, client):
        # Use a known clean governance file
        resp = self._certify(client, "runtime/governance/mutation_admission.py")
        assert resp.status_code == 200

    def test_T31_EP_12_schema_version(self, client):
        resp = self._certify(client, "runtime/governance/mutation_admission.py")
        assert resp.json()["schema_version"] == "1.0"

    def test_T31_EP_13_data_has_status(self, client):
        data = self._certify(client, "runtime/governance/mutation_admission.py").json()["data"]
        assert data["status"] in ("CERTIFIED", "REJECTED")

    def test_T31_EP_14_data_has_passed_bool(self, client):
        data = self._certify(client, "runtime/governance/mutation_admission.py").json()["data"]
        assert isinstance(data["passed"], bool)

    def test_T31_EP_15_data_has_escalation(self, client):
        data = self._certify(client, "runtime/governance/mutation_admission.py").json()["data"]
        assert data["escalation"] in ("advisory", "conservative", "governance", "critical")

    def test_T31_EP_16_missing_file_returns_200_rejected(self, client):
        data = self._certify(client, "runtime/governance/nonexistent_module_xyz.py").json()["data"]
        assert data["status"] == "REJECTED"
        assert data["passed"] is False

    def test_T31_EP_17_absolute_path_rejected_422(self, client):
        resp = self._certify(client, "/etc/passwd")
        assert resp.status_code == 422

    def test_T31_EP_18_path_traversal_rejected_422(self, client):
        resp = self._certify(client, "../../etc/passwd")
        assert resp.status_code == 422

    def test_T31_EP_19_missing_file_path_rejected_422(self, client):
        resp = client.post("/governance/certify", json={}, headers=_AUTH)
        assert resp.status_code == 422

    def test_T31_EP_20_requires_auth(self, client):
        resp = client.post(
            "/governance/certify",
            json={"file_path": "runtime/governance/mutation_admission.py"},
        )
        assert resp.status_code in (401, 403)
