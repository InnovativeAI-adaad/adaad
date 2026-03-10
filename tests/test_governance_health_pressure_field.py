# SPDX-License-Identifier: Apache-2.0
"""Tests: review_pressure field in GET /governance/health — Phase 24 / PR-24-02"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

_TOKEN = "pr24-gh-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestGovernanceHealthPressureField:
    def _data(self, client) -> dict:
        resp = client.get("/governance/health", headers=_AUTH)
        assert resp.status_code == 200
        return resp.json()["data"]

    def test_review_pressure_field_present(self, client):
        d = self._data(client)
        assert "review_pressure" in d

    def test_pressure_tier_valid(self, client):
        d = self._data(client)
        assert d["review_pressure"]["pressure_tier"] in {"none", "elevated", "critical"}

    def test_advisory_only_is_true(self, client):
        d = self._data(client)
        assert d["review_pressure"]["advisory_only"] is True

    def test_adjusted_tiers_is_list(self, client):
        d = self._data(client)
        assert isinstance(d["review_pressure"]["adjusted_tiers"], list)

    def test_adjustment_digest_is_str(self, client):
        d = self._data(client)
        assert isinstance(d["review_pressure"]["adjustment_digest"], str)

    def test_existing_fields_unchanged(self, client):
        d = self._data(client)
        for key in ("epoch_id", "health_score", "status", "signal_breakdown",
                    "weight_snapshot_digest", "constitution_version",
                    "scoring_algorithm_version", "degraded", "routing_health"):
            assert key in d, f"missing existing field: {key}"
