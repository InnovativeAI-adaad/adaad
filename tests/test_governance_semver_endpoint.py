# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import server

pytestmark = pytest.mark.regression_standard

_TOKEN = "semver-audit-token"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture(autouse=True)
def _set_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_AUDIT_TOKENS", json.dumps({_TOKEN: ["audit:read"]}))


def test_semver_endpoint_requires_authentication() -> None:
    with TestClient(server.app) as client:
        response = client.get("/governance/semver/m-001")
    assert response.status_code == 401


def test_semver_endpoint_returns_latest_verdict_and_history(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    audit_path = tmp_path / "semver.jsonl"
    rows = [
        {
            "mutation_id": "m-001",
            "declared_impact": "patch",
            "detected_impact": "minor",
            "contract_honored": False,
            "violations": ["Declared 'patch' but detected 'minor'."],
            "verdict_digest": "sha256:" + "1" * 64,
            "timestamp": 100.0,
        },
        {
            "mutation_id": "m-001",
            "declared_impact": "minor",
            "detected_impact": "minor",
            "contract_honored": True,
            "violations": [],
            "verdict_digest": "sha256:" + "2" * 64,
            "timestamp": 200.0,
        },
        {
            "mutation_id": "m-002",
            "declared_impact": "patch",
            "detected_impact": "patch",
            "contract_honored": True,
            "violations": [],
            "verdict_digest": "sha256:" + "3" * 64,
            "timestamp": 300.0,
        },
    ]
    audit_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(server, "SEMVER_AUDIT_PATH", audit_path)

    with TestClient(server.app) as client:
        response = client.get(
            "/governance/semver/m-001?history_limit=10&diff_text=%2Bdef%20new_api%28%29%3A",
            headers=_AUTH,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["innovation"] == 24
    assert payload["mutation_id"] == "m-001"
    assert payload["contract_status"] == "PASS"
    assert payload["history_count"] == 2
    assert len(payload["audit_history"]) == 2
    assert payload["verdict"]["verdict_digest"] == "sha256:" + "2" * 64
    assert payload["analysis"]["detected_impact"] == "minor"


def test_semver_endpoint_returns_unknown_when_no_verdict(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    audit_path = tmp_path / "empty.jsonl"
    audit_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(server, "SEMVER_AUDIT_PATH", audit_path)

    with TestClient(server.app) as client:
        response = client.get("/governance/semver/missing-id", headers=_AUTH)

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_status"] == "UNKNOWN"
    assert payload["verdict"] is None
    assert payload["history_count"] == 0
    assert payload["audit_history"] == []
