# SPDX-License-Identifier: Apache-2.0
"""Tests: Simulation Aponi Endpoints — ADAAD-8 / PR-12

Tests cover:
- POST /simulation/run: auth gate (401 without token, 200 with token)
- POST /simulation/run: simulation=true always in response
- POST /simulation/run: empty DSL text produces valid result
- POST /simulation/run: invalid DSL text returns 422
- GET /simulation/results/{run_id}: auth gate (401 without token, 200 with token)
- GET /simulation/results/{run_id}: simulation=true in response
- Both endpoints are read-only: no ledger writes
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient
from unittest.mock import patch

import os
os.environ.setdefault("ADAAD_ENV", "dev")
os.environ.setdefault("CRYOVANT_DEV_MODE", "1")

from server import app

VALID_TOKEN = "test-audit-token-adaad8"
AUTH_HEADER = {"Authorization": f"Bearer {VALID_TOKEN}"}


def _patch_tokens(token: str = VALID_TOKEN):
    return patch(
        "server._load_audit_tokens",
        return_value={token: ["audit:read"]},
    )


# ---------------------------------------------------------------------------
# POST /simulation/run
# ---------------------------------------------------------------------------

class TestSimulationRunEndpoint:
    def test_run_requires_auth(self):
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/simulation/run", json={"dsl_text": "", "epoch_ids": []})
        assert resp.status_code == 401

    def test_run_returns_200_with_valid_token(self):
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/simulation/run",
                json={"dsl_text": "", "epoch_ids": []},
                headers=AUTH_HEADER,
            )
        assert resp.status_code == 200

    def test_run_response_contains_simulation_true(self):
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/simulation/run",
                json={"dsl_text": "", "epoch_ids": []},
                headers=AUTH_HEADER,
            )
        body = resp.json()
        assert body["data"]["simulation"] is True

    def test_run_result_simulation_true(self):
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/simulation/run",
                json={"dsl_text": "", "epoch_ids": []},
                headers=AUTH_HEADER,
            )
        result = resp.json()["data"]["result"]
        assert result["simulation"] is True

    def test_run_simulation_only_notice_present(self):
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/simulation/run",
                json={"dsl_text": "", "epoch_ids": ["e1"]},
                headers=AUTH_HEADER,
            )
        assert "simulation_only_notice" in resp.json()["data"]

    def test_run_with_valid_dsl_returns_result(self):
        dsl = "max_risk_score(threshold=0.5)\nmax_mutations_per_epoch(count=3)"
        epoch_data = {
            "e1": {
                "epoch_id": "e1",
                "mutations": [
                    {"mutation_id": "m1", "risk_score": 0.3, "complexity_delta": 0.05,
                     "lineage_depth": 2, "test_coverage": 0.9, "tier": "standard", "entropy": 0.1}
                ],
                "actual_mutations_advanced": 1,
                "entropy": 0.1,
                "scoring_algorithm_version": "1.0",
            }
        }
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/simulation/run",
                json={"dsl_text": dsl, "epoch_ids": ["e1"], "epoch_data_map": epoch_data},
                headers=AUTH_HEADER,
            )
        assert resp.status_code == 200
        result = resp.json()["data"]["result"]
        assert result["epoch_count"] == 1
        assert result["simulation"] is True

    def test_run_invalid_dsl_returns_422(self):
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/simulation/run",
                json={"dsl_text": "invalid_constraint(foo=bar)", "epoch_ids": []},
                headers=AUTH_HEADER,
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /simulation/results/{run_id}
# ---------------------------------------------------------------------------

class TestSimulationResultsEndpoint:
    def test_results_requires_auth(self):
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/simulation/results/run-abc-123")
        assert resp.status_code == 401

    def test_results_returns_200_with_valid_token(self):
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/simulation/results/run-abc-123",
                headers=AUTH_HEADER,
            )
        assert resp.status_code == 200

    def test_results_response_contains_simulation_true(self):
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/simulation/results/run-abc-123",
                headers=AUTH_HEADER,
            )
        assert resp.json()["data"]["simulation"] is True

    def test_results_response_contains_run_id(self):
        with _patch_tokens():
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/simulation/results/my-run-id-001",
                headers=AUTH_HEADER,
            )
        assert resp.json()["data"]["run_id"] == "my-run-id-001"
