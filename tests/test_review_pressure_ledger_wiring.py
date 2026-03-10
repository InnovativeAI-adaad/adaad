# SPDX-License-Identifier: Apache-2.0
"""Tests: PressureAuditLedger wired into GET /governance/review-pressure — Phase 25 / PR-25-02"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TOKEN = "pr25-rp-wire-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch):
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client():
    import server
    server._pressure_audit_ledger = None
    from server import app
    return TestClient(app, raise_server_exceptions=True)


class TestReviewPressureLedgerWiring:
    def test_ledger_inactive_without_env(self, client, monkeypatch):
        monkeypatch.delenv("ADAAD_PRESSURE_LEDGER_PATH", raising=False)
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        assert resp.json()["data"]["ledger_active"] is False

    def test_ledger_sequence_null_when_inactive(self, client, monkeypatch):
        monkeypatch.delenv("ADAAD_PRESSURE_LEDGER_PATH", raising=False)
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        assert resp.json()["data"]["ledger_sequence"] is None

    def test_ledger_active_with_env(self, client, tmp_path, monkeypatch):
        import server
        server._pressure_audit_ledger = None
        p = tmp_path / "rp_wire.jsonl"
        monkeypatch.setenv("ADAAD_PRESSURE_LEDGER_PATH", str(p))
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        assert resp.json()["data"]["ledger_active"] is True

    def test_ledger_sequence_int_when_active(self, client, tmp_path, monkeypatch):
        import server
        server._pressure_audit_ledger = None
        p = tmp_path / "rp_wire2.jsonl"
        monkeypatch.setenv("ADAAD_PRESSURE_LEDGER_PATH", str(p))
        resp = client.get("/governance/review-pressure", headers=_AUTH)
        assert isinstance(resp.json()["data"]["ledger_sequence"], int)

    def test_ledger_file_exists_after_call(self, client, tmp_path, monkeypatch):
        import server
        server._pressure_audit_ledger = None
        p = tmp_path / "rp_wire3.jsonl"
        monkeypatch.setenv("ADAAD_PRESSURE_LEDGER_PATH", str(p))
        client.get("/governance/review-pressure", headers=_AUTH)
        assert p.exists()

    def test_two_calls_increment_sequence(self, client, tmp_path, monkeypatch):
        import server
        server._pressure_audit_ledger = None
        p = tmp_path / "rp_wire4.jsonl"
        monkeypatch.setenv("ADAAD_PRESSURE_LEDGER_PATH", str(p))
        resp1 = client.get("/governance/review-pressure", headers=_AUTH)
        resp2 = client.get("/governance/review-pressure", headers=_AUTH)
        seq1 = resp1.json()["data"]["ledger_sequence"]
        seq2 = resp2.json()["data"]["ledger_sequence"]
        assert seq2 == seq1 + 1
