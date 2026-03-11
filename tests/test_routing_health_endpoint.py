# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /governance/routing-health endpoint — Phase 23 / PR-23-02"""
from __future__ import annotations

import json

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient

_TOKEN = "pr23-audit-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestRoutingHealthEndpoint:
    def test_returns_200_with_schema(self, client):
        resp = client.get("/governance/routing-health", headers=_AUTH)
        assert resp.status_code == 200
        d = resp.json()
        assert "data" in d
        assert "schema_version" in d

    def test_no_auth_returns_401(self, client):
        resp = client.get("/governance/routing-health")
        assert resp.status_code == 401

    def test_window_size_too_small_returns_422(self, client):
        resp = client.get("/governance/routing-health?window_size=5", headers=_AUTH)
        assert resp.status_code == 422

    def test_window_size_too_large_returns_422(self, client):
        resp = client.get("/governance/routing-health?window_size=10001", headers=_AUTH)
        assert resp.status_code == 422

    def test_available_false_when_no_file_sink(self, client):
        from server import _set_telemetry_sink_for_server
        _set_telemetry_sink_for_server(None)
        resp = client.get("/governance/routing-health", headers=_AUTH)
        assert resp.status_code == 200
        assert resp.json()["data"]["available"] is False

    def test_available_true_with_file_sink(self, client, tmp_path):
        from runtime.intelligence.file_telemetry_sink import FileTelemetrySink
        from server import _set_telemetry_sink_for_server
        ledger = tmp_path / "rh.jsonl"
        sink = FileTelemetrySink(ledger, chain_verify_on_open=False)
        for _ in range(15):
            sink.emit({"strategy_id": "conservative_hold", "outcome": "approved"})
        _set_telemetry_sink_for_server(sink)
        try:
            resp = client.get("/governance/routing-health", headers=_AUTH)
            assert resp.json()["data"]["available"] is True
        finally:
            _set_telemetry_sink_for_server(None)

    def test_status_in_valid_set(self, client):
        resp = client.get("/governance/routing-health", headers=_AUTH)
        assert resp.json()["data"]["status"] in {"green", "amber", "red"}

    def test_health_score_in_range(self, client):
        resp = client.get("/governance/routing-health", headers=_AUTH)
        h = resp.json()["data"]["health_score"]
        assert 0.0 <= h <= 1.0

    def test_strategy_stats_is_list(self, client):
        resp = client.get("/governance/routing-health", headers=_AUTH)
        assert isinstance(resp.json()["data"]["strategy_stats"], list)

    def test_ledger_chain_valid_is_bool(self, client):
        resp = client.get("/governance/routing-health", headers=_AUTH)
        assert isinstance(resp.json()["data"]["ledger_chain_valid"], bool)

    def test_report_digest_none_when_unavailable(self, client):
        from server import _set_telemetry_sink_for_server
        _set_telemetry_sink_for_server(None)
        resp = client.get("/governance/routing-health", headers=_AUTH)
        assert resp.json()["data"]["report_digest"] is None

    def test_report_digest_sha256_when_available(self, client, tmp_path):
        from runtime.intelligence.file_telemetry_sink import FileTelemetrySink
        from server import _set_telemetry_sink_for_server
        ledger = tmp_path / "rh2.jsonl"
        sink = FileTelemetrySink(ledger, chain_verify_on_open=False)
        for _ in range(15):
            sink.emit({"strategy_id": "exploratory_probe", "outcome": "approved"})
        _set_telemetry_sink_for_server(sink)
        try:
            resp = client.get("/governance/routing-health", headers=_AUTH)
            digest = resp.json()["data"]["report_digest"]
            assert digest is not None
            assert digest.startswith("sha256:")
        finally:
            _set_telemetry_sink_for_server(None)
