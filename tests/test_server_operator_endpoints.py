from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

import server


class _FakeLedger:
    def read_all(self):
        return [
            {
                "type": "MutationBundleEvent",
                "ts": "2026-01-01T00:00:00Z",
                "payload": {
                    "epoch_id": "epoch-1",
                    "bundle_id": "mut-1",
                    "impact": 0.9,
                    "risk_tier": "low",
                    "applied": True,
                },
            }
        ]

    def list_epoch_ids(self):
        return ["epoch-1"]

    def read_epoch(self, epoch_id: str):
        return [
            {
                "type": "EpochStartEvent",
                "ts": "2026-01-01T00:00:00Z",
                "payload": {"epoch_id": epoch_id},
            },
            {
                "type": "MutationBundleEvent",
                "ts": "2026-01-01T00:01:00Z",
                "payload": {"epoch_id": epoch_id, "bundle_id": "mut-1", "impact": 0.9},
            },
        ]

    def get_expected_epoch_digest(self, epoch_id: str):
        return "sha256:" + "1" * 64

    def compute_incremental_epoch_digest(self, epoch_id: str):
        return "sha256:" + "2" * 64


def test_operator_mutations_endpoint_schema(monkeypatch) -> None:
    monkeypatch.setattr(server, "LineageLedgerV2", _FakeLedger)

    with TestClient(server.app) as client:
        response = client.get("/api/mutations")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload
    server.MutationView.model_validate(payload[0])


def test_operator_epochs_endpoint_schema(monkeypatch) -> None:
    monkeypatch.setattr(server, "LineageLedgerV2", _FakeLedger)

    with TestClient(server.app) as client:
        response = client.get("/api/epochs")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload
    server.EpochView.model_validate(payload[0])


def test_constitution_status_endpoint_schema(monkeypatch) -> None:
    monkeypatch.setattr(server.constitution, "CONSTITUTION_VERSION", "0.2.0")
    monkeypatch.setattr(server.constitution, "POLICY_HASH", "abc123")
    monkeypatch.setattr(server.constitution, "boot_sanity_check", lambda: {"ok": True})

    with TestClient(server.app) as client:
        response = client.get("/api/constitution/status")

    assert response.status_code == 200
    server.ConstitutionStatus.model_validate(response.json())


@dataclass(frozen=True)
class _Decision:
    strategy: object
    proposal: object
    critique: object

    @property
    def outcome(self) -> str:
        return "execute"


def test_system_intelligence_endpoint_schema(monkeypatch) -> None:
    @dataclass(frozen=True)
    class _Part:
        value: str

    class _Router:
        def route(self, _context):
            return _Decision(strategy=_Part("strategy"), proposal=_Part("proposal"), critique=_Part("critique"))

    monkeypatch.setattr(server, "rolling_determinism_score", lambda window=100: {"rolling_score": 1.0, "sample_size": 1})
    monkeypatch.setattr(server, "mutation_rate_snapshot", lambda window_sec=3600: {"rate_per_hour": 1.0, "count": 1})
    monkeypatch.setattr(server, "IntelligenceRouter", _Router)

    with TestClient(server.app) as client:
        response = client.get("/api/system/intelligence")

    assert response.status_code == 200
    server.SystemIntelligenceView.model_validate(response.json())


def test_post_proposal_delegates_to_mcp_validation_and_queue(monkeypatch) -> None:
    class _Request:
        authority_level = "governor-review"

    observed: dict[str, object] = {}

    def _fake_validate(payload):
        observed["payload"] = payload
        return _Request(), {"passed": True, "verdicts": []}

    def _fake_append(*, proposal_id: str, request):
        observed["proposal_id"] = proposal_id
        observed["request"] = request
        return {"hash": "queuehash"}

    class _Provider:
        def next_id(self, *, label: str, length: int):
            observed["label"] = label
            observed["length"] = length
            return "proposal-123"

    monkeypatch.setattr(server, "validate_proposal", _fake_validate)
    monkeypatch.setattr(server, "append_proposal", _fake_append)
    monkeypatch.setattr(server, "default_provider", lambda: _Provider())

    with TestClient(server.app) as client:
        response = client.post("/api/mutations/proposals", json={"intent": "optimize"})

    assert response.status_code == 200
    payload = response.json()
    server.ProposalResponse.model_validate(payload)
    assert observed["payload"] == {"intent": "optimize"}
    assert observed["proposal_id"] == "proposal-123"


def test_mock_endpoints_disabled_by_default() -> None:
    with TestClient(server.app) as client:
        response = client.get("/api/status")

    assert response.status_code == 404
    assert response.json() == {"detail": "mock_endpoints_disabled"}


def test_api_health_includes_version_and_runtime_profile() -> None:
    with TestClient(server.app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("version"), str)
    runtime_profile = payload.get("runtime_profile")
    assert isinstance(runtime_profile, dict)
    assert "present" in runtime_profile
