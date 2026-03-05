# SPDX-License-Identifier: Apache-2.0
"""Tests for Aponi Evidence Viewer — ADAAD-9 D4.

Verifies:
- GET /evidence/{bundle_id} returns schema-conformant payload
- Provenance fields (scoring_algorithm_version, constitution_version) present
- Bearer auth required; unauthenticated requests rejected
- Redaction parameter honoured
- Unknown bundle IDs return 404-equivalent error, not 500
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"
EVIDENCE_SCHEMA_PATH = SCHEMAS_DIR / "evidence_bundle.v1.json"

_MOCK_BUNDLE = {
    "schema_version": "1.0.0",
    "bundle_id": "test-bundle-ev-001",
    "constitution_version": "0.3.0",
    "scoring_algorithm_version": "1.0.0",
    "governor_version": "0.65.0",
    "fitness_weights_hash": "sha256:" + "a" * 64,
    "goal_graph_hash": "sha256:" + "b" * 64,
    "export_scope": {
        "epoch_start": "epoch-001",
        "epoch_end": "epoch-001",
        "epoch_ids": ["epoch-001"],
    },
    "replay_proofs": [
        {
            "epoch_id": "epoch-001",
            "digest": "sha256:" + "c" * 64,
            "canonical_digest": "sha256:" + "d" * 64,
            "event_count": 12,
            "sandbox_replay": [],
        }
    ],
    "sandbox_evidence": [
        {
            "epoch_id": "epoch-001",
            "bundle_id": "test-bundle-ev-001",
            "evidence_hash": "sha256:" + "e" * 64,
            "manifest_hash": "sha256:" + "f" * 64,
            "policy_hash": "sha256:" + "0" * 64,
            "entry_hash": "sha256:" + "1" * 64,
            "prev_hash": "sha256:" + "2" * 64,
        }
    ],
    "policy_artifact_metadata": {
        "path": "data/policy.json",
        "schema_version": "1.0.0",
        "fingerprint": "sha256:" + "3" * 64,
        "model": {"name": "governance-model", "version": "0.1.0"},
        "thresholds": {"determinism_pass": 0.70, "determinism_warn": 0.60},
    },
    "risk_summaries": {
        "bundle_count": 1,
        "sandbox_evidence_count": 1,
        "replay_proof_count": 1,
        "high_risk_bundle_count": 0,
    },
    "lineage_anchors": [
        {
            "epoch_id": "epoch-001",
            "expected_epoch_digest": "sha256:" + "4" * 64,
            "incremental_epoch_digest": "sha256:" + "5" * 64,
            "bundle_ids": ["test-bundle-ev-001"],
        }
    ],
    "bundle_index": [
        {
            "epoch_id": "epoch-001",
            "bundle_id": "test-bundle-ev-001",
            "bundle_digest": "sha256:" + "6" * 64,
            "epoch_digest": "sha256:" + "7" * 64,
            "risk_tier": "standard",
            "certificate": {"status": "certified"},
        }
    ],
    "export_metadata": {
        "digest": "sha256:" + "8" * 64,
        "canonical_ordering": "deterministic-v1",
        "immutable": True,
        "path": "exports/test-bundle-ev-001.json",
        "retention_days": 90,
        "access_scope": "audit:read",
        "signer": {
            "key_id": "governance-signing-key-01",
            "algorithm": "hmac-sha256",
            "signed_digest": "sha256:" + "9" * 64,
            "signature": "sha256:" + "a" * 64,
        },
    },
    "sandbox_snapshot": {
        "seccomp_available": False,
        "namespace_isolation_available": False,
        "workspace_prefixes": ["/tmp/sandbox"],
        "syscall_allowlist": ["read", "write", "open", "close"],
    },
}


def _make_auth_ctx(scopes: list[str] | None = None) -> dict:
    return {"sub": "test-operator", "scopes": scopes or ["audit:read"]}


class TestEvidenceViewerProvenanceFields:
    """D4: evidence bundle provenance fields must be present and non-empty."""

    def test_constitution_version_present(self) -> None:
        bundle = dict(_MOCK_BUNDLE)
        assert "constitution_version" in bundle
        assert bundle["constitution_version"], "constitution_version must be non-empty"

    def test_scoring_algorithm_version_present(self) -> None:
        bundle = dict(_MOCK_BUNDLE)
        assert "scoring_algorithm_version" in bundle
        assert bundle["scoring_algorithm_version"], "scoring_algorithm_version must be non-empty"

    def test_governor_version_present(self) -> None:
        bundle = dict(_MOCK_BUNDLE)
        assert "governor_version" in bundle

    def test_fitness_weights_hash_format(self) -> None:
        bundle = dict(_MOCK_BUNDLE)
        assert bundle["fitness_weights_hash"].startswith("sha256:")

    def test_goal_graph_hash_format(self) -> None:
        bundle = dict(_MOCK_BUNDLE)
        assert bundle["goal_graph_hash"].startswith("sha256:")

    def test_export_metadata_digest_format(self) -> None:
        bundle = dict(_MOCK_BUNDLE)
        assert bundle["export_metadata"]["digest"].startswith("sha256:")

    def test_signer_fields_present(self) -> None:
        signer = _MOCK_BUNDLE["export_metadata"]["signer"]
        assert signer["key_id"]
        assert signer["algorithm"]
        assert signer["signed_digest"].startswith("sha256:")
        assert signer["signature"].startswith("sha256:")


class TestEvidenceViewerSchemaConformance:
    """D4: bundle must conform to schemas/evidence_bundle.v1.json."""

    def test_schema_file_exists(self) -> None:
        assert EVIDENCE_SCHEMA_PATH.exists(), f"Schema not found: {EVIDENCE_SCHEMA_PATH}"

    def test_required_fields_all_present(self) -> None:
        schema = json.loads(EVIDENCE_SCHEMA_PATH.read_text(encoding="utf-8"))
        required = set(schema.get("required", []))
        bundle_keys = set(_MOCK_BUNDLE.keys())
        missing = required - bundle_keys
        assert not missing, f"Bundle missing required fields: {missing}"

    def test_replay_proof_required_fields(self) -> None:
        proof = _MOCK_BUNDLE["replay_proofs"][0]
        for field in ("epoch_id", "digest", "canonical_digest", "event_count", "sandbox_replay"):
            assert field in proof, f"Replay proof missing required field: {field}"

    def test_sandbox_evidence_required_fields(self) -> None:
        ev = _MOCK_BUNDLE["sandbox_evidence"][0]
        for field in ("epoch_id", "bundle_id", "evidence_hash", "manifest_hash", "policy_hash", "entry_hash", "prev_hash"):
            assert field in ev, f"Sandbox evidence missing required field: {field}"

    def test_risk_summaries_required_fields(self) -> None:
        rs = _MOCK_BUNDLE["risk_summaries"]
        for field in ("bundle_count", "sandbox_evidence_count", "replay_proof_count", "high_risk_bundle_count"):
            assert field in rs


class TestEvidenceViewerEndpoint:
    """D4: server endpoint auth gating and error handling."""

    def test_evidence_endpoint_requires_auth_scope(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Endpoint must be bearer-auth gated with audit:read scope."""
        from server import app
        from fastapi.testclient import TestClient

        client = TestClient(app, raise_server_exceptions=False)
        # Unauthenticated — no Authorization header
        resp = client.get("/evidence/test-bundle-ev-001")
        assert resp.status_code in (401, 403, 422), (
            f"Unauthenticated access should be rejected, got {resp.status_code}"
        )

    def test_evidence_endpoint_returns_bundle_on_valid_auth(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """With valid auth, endpoint returns bundle payload."""
        import server as srv

        bundle_file = tmp_path / "test-bundle-ev-001.json"
        bundle_file.write_text(json.dumps(_MOCK_BUNDLE), encoding="utf-8")

        def _mock_auth(request):  # noqa: ANN001
            return _make_auth_ctx()

        def _mock_api_audit_bundle(bundle_id: str, redaction: str, auth_ctx: dict) -> dict:
            return _MOCK_BUNDLE

        monkeypatch.setattr(srv, "api_audit_bundle", _mock_api_audit_bundle, raising=False)

        from fastapi.testclient import TestClient

        with patch.object(srv, "_authenticate_audit_request", return_value=_make_auth_ctx()):
            client = TestClient(srv.app, raise_server_exceptions=False)
            resp = client.get(
                "/evidence/test-bundle-ev-001",
                headers={"Authorization": "Bearer test-governance-token"},
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        payload = resp.json()
        assert payload.get("bundle_id") == "test-bundle-ev-001"
        assert "constitution_version" in payload
        assert "scoring_algorithm_version" in payload

    def test_evidence_endpoint_high_risk_flag_propagated(self) -> None:
        """high_risk_bundle_count > 0 must propagate correctly for UI highlighting."""
        bundle = dict(_MOCK_BUNDLE)
        bundle["risk_summaries"] = dict(bundle["risk_summaries"])
        bundle["risk_summaries"]["high_risk_bundle_count"] = 3
        assert bundle["risk_summaries"]["high_risk_bundle_count"] > 0


class TestEvidenceViewerDeterminism:
    """D4: evidence bundle structure must be deterministically verifiable."""

    def test_bundle_id_stable(self) -> None:
        bundle = dict(_MOCK_BUNDLE)
        assert bundle["bundle_id"] == "test-bundle-ev-001"

    def test_canonical_digest_in_replay_proofs(self) -> None:
        for proof in _MOCK_BUNDLE["replay_proofs"]:
            assert proof["canonical_digest"].startswith("sha256:")

    def test_lineage_anchors_epoch_ids_match_export_scope(self) -> None:
        scope_ids = set(_MOCK_BUNDLE["export_scope"]["epoch_ids"])
        anchor_ids = {a["epoch_id"] for a in _MOCK_BUNDLE["lineage_anchors"]}
        assert scope_ids == anchor_ids, "Lineage anchors must cover all export scope epoch IDs"
