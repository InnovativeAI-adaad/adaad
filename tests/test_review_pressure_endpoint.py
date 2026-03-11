# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/review-pressure endpoint — Phase 24 / PR-24-02"""
from __future__ import annotations

import json

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient

from runtime.governance.review_pressure import DEFAULT_TIER_CONFIG

_TOKEN = "pr24-rp-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestReviewPressureEndpoint:
    def test_returns_200_with_schema(self, client):
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        assert resp.status_code == 200
        d = resp.json()
        assert "data" in d
        assert "schema_version" in d

    def test_no_auth_returns_401(self, client):
        resp = client.get("/governance/review-pressure")
        assert resp.status_code == 401

    def test_advisory_only_is_true(self, client):
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        assert resp.json()["data"]["advisory_only"] is True

    def test_pressure_tier_valid(self, client):
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        assert resp.json()["data"]["pressure_tier"] in {"none", "elevated", "critical"}

    def test_health_band_valid(self, client):
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        assert resp.json()["data"]["health_band"] in {"green", "amber", "red"}

    def test_adjusted_tiers_is_list(self, client):
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        assert isinstance(resp.json()["data"]["adjusted_tiers"], list)

    def test_adjustment_digest_sha256(self, client):
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        digest = resp.json()["data"]["adjustment_digest"]
        assert digest.startswith("sha256:")

    def test_proposed_tier_config_has_all_tiers(self, client):
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        ptc = resp.json()["data"]["proposed_tier_config"]
        for tier in DEFAULT_TIER_CONFIG:
            assert tier in ptc

    def test_adaptor_version(self, client):
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        assert resp.json()["data"]["adaptor_version"] == "24.0"

    def test_baseline_tier_config_matches_default(self, client):
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        btc = resp.json()["data"]["baseline_tier_config"]
        for tier, cfg in DEFAULT_TIER_CONFIG.items():
            assert btc[tier]["base_count"] == cfg["base_count"]
            assert btc[tier]["min_count"] == cfg["min_count"]
            assert btc[tier]["max_count"] == cfg["max_count"]
