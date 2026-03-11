# SPDX-License-Identifier: Apache-2.0
"""Cross-endpoint contract matrix tests for endpoint schema + auth behavior."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

_TOKEN = "contract-matrix-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


SchemaValidator = Callable[[dict[str, Any]], None]
SetupCallback = Callable[[pytest.MonkeyPatch], None]


@pytest.fixture(autouse=True)
def _set_audit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


@pytest.fixture
def client() -> TestClient:
    import server

    server._pressure_audit_ledger = None
    server._set_telemetry_sink_for_server(None)
    return TestClient(server.app, raise_server_exceptions=True)


def _validate_telemetry_decisions_schema(body: dict[str, Any]) -> None:
    data = body["data"]
    assert "decisions" in data
    assert "total_queried" in data
    assert "ledger_path" in data
    assert "sink_type" in data


def _validate_telemetry_analytics_schema(body: dict[str, Any]) -> None:
    required = {
        "status",
        "health_score",
        "strategy_stats",
        "dominant_strategy",
        "dominant_share",
        "stale_strategy_ids",
        "drift_max",
        "window_size",
        "total_decisions",
        "window_decisions",
        "ledger_chain_valid",
        "report_digest",
    }
    assert required.issubset(body["data"].keys())


def _validate_governance_schema_stub(body: dict[str, Any]) -> None:
    assert "schema_version" in body
    assert "data" in body


def _clear_pressure_ledger_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADAAD_PRESSURE_LEDGER_PATH", raising=False)


STANDARD_ENDPOINT_MATRIX = [
    pytest.param(
        "/telemetry/decisions",
        "bearer:audit_read",
        200,
        _validate_telemetry_decisions_schema,
        None,
        id="telemetry-decisions-standard",
        marks=pytest.mark.regression_standard,
    ),
    pytest.param(
        "/telemetry/analytics",
        "bearer:audit_read",
        200,
        _validate_telemetry_analytics_schema,
        None,
        id="telemetry-analytics-standard",
        marks=pytest.mark.regression_standard,
    ),
    pytest.param(
        "/governance/routing-health",
        "bearer:audit_read",
        200,
        _validate_governance_schema_stub,
        None,
        id="governance-routing-health",
        marks=pytest.mark.governance_gate,
    ),
    pytest.param(
        "/governance/review-pressure",
        "bearer:audit_read",
        200,
        _validate_governance_schema_stub,
        None,
        id="governance-review-pressure",
        marks=pytest.mark.governance_gate,
    ),
    pytest.param(
        "/governance/pressure-history",
        "bearer:audit_read",
        200,
        _validate_governance_schema_stub,
        _clear_pressure_ledger_env,
        id="governance-pressure-history",
        marks=pytest.mark.governance_gate,
    ),
]


@pytest.mark.parametrize(
    "path,auth_mode,expected_status,schema_validator,setup_callback",
    STANDARD_ENDPOINT_MATRIX,
)
def test_contract_matrix_standard_endpoints(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    auth_mode: str,
    expected_status: int,
    schema_validator: SchemaValidator,
    setup_callback: SetupCallback | None,
) -> None:
    if setup_callback is not None:
        setup_callback(monkeypatch)

    headers = _AUTH if auth_mode == "bearer:audit_read" else {}
    response = client.get(path, headers=headers)

    assert response.status_code == expected_status
    schema_validator(response.json())


@pytest.mark.parametrize(
    "path,auth_mode,expected_status",
    [
        pytest.param(
            "/telemetry/decisions",
            "none",
            401,
            id="telemetry-decisions-no-auth",
            marks=pytest.mark.regression_standard,
        ),
        pytest.param(
            "/telemetry/analytics",
            "none",
            401,
            id="telemetry-analytics-no-auth",
            marks=pytest.mark.regression_standard,
        ),
        pytest.param(
            "/governance/routing-health",
            "none",
            401,
            id="governance-routing-health-no-auth",
            marks=pytest.mark.governance_gate,
        ),
        pytest.param(
            "/governance/review-pressure",
            "none",
            401,
            id="governance-review-pressure-no-auth",
            marks=pytest.mark.governance_gate,
        ),
        pytest.param(
            "/governance/pressure-history",
            "none",
            401,
            id="governance-pressure-history-no-auth",
            marks=pytest.mark.governance_gate,
        ),
    ],
)
def test_contract_matrix_standard_auth_failures(
    client: TestClient,
    path: str,
    auth_mode: str,
    expected_status: int,
) -> None:
    headers = _AUTH if auth_mode == "bearer:audit_read" else {}
    response = client.get(path, headers=headers)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "path,auth_mode,expected_status",
    [
        pytest.param(
            "/governance/admission-status",
            "none",
            {401, 403},
            id="governance-admission-divergent-auth",
            marks=pytest.mark.governance_gate,
        )
    ],
)
def test_contract_matrix_governance_auth_divergence(
    client: TestClient,
    path: str,
    auth_mode: str,
    expected_status: set[int],
) -> None:
    headers = _AUTH if auth_mode == "bearer:audit_read" else {}
    response = client.get(path, headers=headers)
    assert response.status_code in expected_status
