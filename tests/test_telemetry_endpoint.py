# SPDX-License-Identifier: Apache-2.0
"""Tests: GET /telemetry/decisions endpoint — Phase 21 / PR-21-02"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

_TOKEN = "pr21-audit-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestTelemetryDecisionsEndpoint:
    def test_limit_over_500_returns_422(self, client):
        resp = client.get("/telemetry/decisions?limit=501", headers=_AUTH)
        assert resp.status_code == 422

    def test_sink_type_field_present(self, client):
        from server import _set_telemetry_sink_for_server
        _set_telemetry_sink_for_server(None)
        resp = client.get("/telemetry/decisions", headers=_AUTH)
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["sink_type"] in {"file", "memory"}

    def test_sink_type_file_when_file_sink_active(self, client, tmp_path):
        from runtime.intelligence.file_telemetry_sink import FileTelemetrySink
        from server import _set_telemetry_sink_for_server
        ledger = tmp_path / "test_tel.jsonl"
        sink = FileTelemetrySink(ledger, chain_verify_on_open=False)
        sink.emit({"strategy_id": "conservative_hold", "outcome": "approved", "cycle_id": "t1"})
        _set_telemetry_sink_for_server(sink)
        try:
            resp = client.get("/telemetry/decisions", headers=_AUTH)
            assert resp.status_code == 200
            d = resp.json()["data"]
            assert d["sink_type"] == "file"
            assert d["ledger_path"] is not None
            assert len(d["decisions"]) == 1
        finally:
            _set_telemetry_sink_for_server(None)

    def test_strategy_id_filter(self, client, tmp_path):
        from runtime.intelligence.file_telemetry_sink import FileTelemetrySink
        from server import _set_telemetry_sink_for_server
        ledger = tmp_path / "filter_tel.jsonl"
        sink = FileTelemetrySink(ledger, chain_verify_on_open=False)
        sink.emit({"strategy_id": "exploratory_probe", "outcome": "approved"})
        sink.emit({"strategy_id": "conservative_hold", "outcome": "rejected"})
        _set_telemetry_sink_for_server(sink)
        try:
            resp = client.get("/telemetry/decisions?strategy_id=exploratory_probe", headers=_AUTH)
            d = resp.json()["data"]
            assert d["total_queried"] == 1
            assert d["decisions"][0]["strategy_id"] == "exploratory_probe"
        finally:
            _set_telemetry_sink_for_server(None)

    def test_pagination_limit_offset(self, client, tmp_path):
        from runtime.intelligence.file_telemetry_sink import FileTelemetrySink
        from server import _set_telemetry_sink_for_server
        ledger = tmp_path / "page_tel.jsonl"
        sink = FileTelemetrySink(ledger, chain_verify_on_open=False)
        for i in range(10):
            sink.emit({"strategy_id": "hold", "outcome": "approved", "seq": i})
        _set_telemetry_sink_for_server(sink)
        try:
            resp = client.get("/telemetry/decisions?limit=3&offset=0", headers=_AUTH)
            d = resp.json()["data"]
            assert len(d["decisions"]) == 3
        finally:
            _set_telemetry_sink_for_server(None)
