# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /telemetry/analytics + GET /telemetry/strategy/{id} — Phase 22 / PR-22-02"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient

from runtime.intelligence.strategy import STRATEGY_TAXONOMY

_TOKEN = "pr22-audit-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def _clear_sink():
    from server import _set_telemetry_sink_for_server
    _set_telemetry_sink_for_server(None)
    yield
    _set_telemetry_sink_for_server(None)


def _populate_sink(tmp_path: Path) -> None:
    from runtime.intelligence.file_telemetry_sink import FileTelemetrySink
    from server import _set_telemetry_sink_for_server
    ledger = tmp_path / "analytics_test.jsonl"
    sink = FileTelemetrySink(ledger, chain_verify_on_open=False)
    for sid in sorted(STRATEGY_TAXONOMY):
        sink.emit({"strategy_id": sid, "outcome": "approved"})
        sink.emit({"strategy_id": sid, "outcome": "rejected"})
    _set_telemetry_sink_for_server(sink)


class TestAnalyticsEndpoint:
    def test_window_size_too_small_returns_422(self, client):
        resp = client.get("/telemetry/analytics?window_size=5", headers=_AUTH)
        assert resp.status_code == 422

    def test_window_size_too_large_returns_422(self, client):
        resp = client.get("/telemetry/analytics?window_size=10001", headers=_AUTH)
        assert resp.status_code == 422

    def test_strategy_stats_count_matches_taxonomy(self, client, tmp_path):
        _populate_sink(tmp_path)
        resp = client.get("/telemetry/analytics", headers=_AUTH)
        d = resp.json()["data"]
        assert len(d["strategy_stats"]) == len(STRATEGY_TAXONOMY)

    def test_status_is_valid(self, client):
        resp = client.get("/telemetry/analytics", headers=_AUTH)
        assert resp.json()["data"]["status"] in {"green", "amber", "red"}

    def test_report_digest_sha256_format(self, client):
        resp = client.get("/telemetry/analytics", headers=_AUTH)
        digest = resp.json()["data"]["report_digest"]
        assert digest.startswith("sha256:")
        assert len(digest) == len("sha256:") + 64

    def test_window_size_param_respected(self, client, tmp_path):
        _populate_sink(tmp_path)
        resp = client.get("/telemetry/analytics?window_size=50", headers=_AUTH)
        assert resp.json()["data"]["window_size"] == 50

    def test_empty_sink_returns_valid_report(self, client):
        resp = client.get("/telemetry/analytics", headers=_AUTH)
        assert resp.status_code == 200
        assert resp.json()["data"]["total_decisions"] == 0

    def test_ledger_chain_valid_is_boolean(self, client):
        resp = client.get("/telemetry/analytics", headers=_AUTH)
        assert isinstance(resp.json()["data"]["ledger_chain_valid"], bool)


class TestStrategyDetailEndpoint:
    def test_valid_strategy_returns_200(self, client):
        resp = client.get("/telemetry/strategy/conservative_hold", headers=_AUTH)
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["strategy_id"] == "conservative_hold"

    def test_unknown_strategy_returns_404(self, client):
        resp = client.get("/telemetry/strategy/unknown_strategy_xyz", headers=_AUTH)
        assert resp.status_code == 404

    def test_adaptive_self_mutate_returns_correct_id(self, client):
        resp = client.get("/telemetry/strategy/adaptive_self_mutate", headers=_AUTH)
        assert resp.json()["data"]["strategy_id"] == "adaptive_self_mutate"
