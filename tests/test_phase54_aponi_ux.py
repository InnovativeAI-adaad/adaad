# SPDX-License-Identifier: Apache-2.0
"""
Phase 54 tests — Aponi UX: Governance & Memory panels

Test IDs: T54-U01..U08
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

_TEST_TOKEN = "test-audit-read-token"
_AUDIT_TOKENS_ENV = json.dumps({_TEST_TOKEN: ["audit:read"]})


@pytest.fixture(scope="module")
def client(monkeypatch_module):
    monkeypatch_module.setenv("ADAAD_AUDIT_TOKENS", _AUDIT_TOKENS_ENV)
    from server import app
    return TestClient(app)


@pytest.fixture(scope="module")
def monkeypatch_module(tmp_path_factory):
    """Module-scoped monkeypatch that sets env vars before server import."""
    os.environ["ADAAD_AUDIT_TOKENS"] = _AUDIT_TOKENS_ENV
    yield
    os.environ.pop("ADAAD_AUDIT_TOKENS", None)


@pytest.fixture(scope="module")
def auth_client():
    os.environ["ADAAD_AUDIT_TOKENS"] = _AUDIT_TOKENS_ENV
    from server import app
    return TestClient(app)


@pytest.fixture(scope="module")
def aponi_html():
    with open("ui/aponi/index.html", encoding="utf-8") as f:
        return f.read()


class TestAponiUXT54U:

    def test_T54_U01_epoch_memory_endpoint_registered(self, auth_client):
        """T54-U01: GET /intelligence/epoch-memory returns 200."""
        res = auth_client.get("/intelligence/epoch-memory",
                              headers={"Authorization": f"Bearer {_TEST_TOKEN}"})
        assert res.status_code == 200

    def test_T54_U02_epoch_memory_has_ok_field(self, auth_client):
        """T54-U02: response contains ok=True."""
        res = auth_client.get("/intelligence/epoch-memory",
                              headers={"Authorization": f"Bearer {_TEST_TOKEN}"})
        data = res.json()
        assert data.get("ok") is True

    def test_T54_U03_epoch_memory_has_advisory_note(self, auth_client):
        """T54-U03: response contains advisory_note field."""
        res = auth_client.get("/intelligence/epoch-memory",
                              headers={"Authorization": f"Bearer {_TEST_TOKEN}"})
        data = res.json()
        assert "advisory_note" in data
        assert "advisory" in data["advisory_note"].lower()

    def test_T54_U04_epoch_memory_has_stats_and_signal(self, auth_client):
        """T54-U04: response has stats, learning_signal, and window fields."""
        res = auth_client.get("/intelligence/epoch-memory",
                              headers={"Authorization": f"Bearer {_TEST_TOKEN}"})
        data = res.json()
        assert "stats" in data
        assert "learning_signal" in data
        assert "window" in data

    def test_T54_U05_epoch_memory_stats_shape(self, auth_client):
        """T54-U05: stats has required keys."""
        res = auth_client.get("/intelligence/epoch-memory",
                              headers={"Authorization": f"Bearer {_TEST_TOKEN}"})
        stats = res.json()["stats"]
        for key in ("count", "window_size", "chain_valid"):
            assert key in stats, f"Missing key: {key}"

    def test_T54_U06_aponi_html_has_governance_tab(self, aponi_html):
        """T54-U06: Aponi HTML includes governance tab markup."""
        assert 'data-tab="governance"' in aponi_html
        assert "viewGovernance" in aponi_html

    def test_T54_U07_aponi_html_has_memory_tab(self, aponi_html):
        """T54-U07: Aponi HTML includes memory tab markup."""
        assert 'data-tab="memory"' in aponi_html
        assert "viewMemory" in aponi_html

    def test_T54_U08_aponi_html_has_fetch_functions(self, aponi_html):
        """T54-U08: Memory/governance fetch functions present in Aponi HTML."""
        assert "fetchGovernanceData" in aponi_html
        assert "fetchMemoryData" in aponi_html
        assert "epoch-memory" in aponi_html
        assert "governance/health" in aponi_html

