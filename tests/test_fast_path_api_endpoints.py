# SPDX-License-Identifier: Apache-2.0
"""Tests for fast-path intelligence API endpoints (server.py v0.66)."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard
from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# /api/fast-path/stats
# ─────────────────────────────────────────────────────────────────────────────


def test_fast_path_stats_ok():
    res = client.get("/api/fast-path/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "versions" in data
    assert "entropy_thresholds" in data
    assert "route_config" in data


def test_fast_path_stats_versions_present():
    data = client.get("/api/fast-path/stats").json()
    v = data["versions"]
    assert "route_optimizer" in v
    assert "entropy_gate" in v
    assert "fast_path_scorer" in v
    assert "checkpoint_chain" in v


def test_fast_path_stats_entropy_thresholds():
    data = client.get("/api/fast-path/stats").json()
    et = data["entropy_thresholds"]
    assert isinstance(et["warn_bits"], int)
    assert isinstance(et["deny_bits"], int)
    assert et["deny_bits"] > et["warn_bits"]


def test_fast_path_stats_route_config():
    data = client.get("/api/fast-path/stats").json()
    rc = data["route_config"]
    assert "TRIVIAL" in rc["tiers"]
    assert "STANDARD" in rc["tiers"]
    assert "ELEVATED" in rc["tiers"]
    assert isinstance(rc["elevated_path_prefixes"], list)
    assert isinstance(rc["elevated_intent_keywords"], list)
    assert isinstance(rc["trivial_op_types"], list)


# ─────────────────────────────────────────────────────────────────────────────
# /api/fast-path/route-preview
# ─────────────────────────────────────────────────────────────────────────────


def _route(payload):
    return client.post("/api/fast-path/route-preview", json=payload)


def test_route_preview_standard():
    res = _route({
        "mutation_id": "test_mut_001",
        "intent": "refactor",
        "files_touched": ["app/main.py"],
        "loc_added": 20,
        "loc_deleted": 10,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["summary"]["tier"] == "STANDARD"
    assert data["summary"]["skip_heavy_scoring"] is False
    assert data["summary"]["require_human_review"] is False


def test_route_preview_trivial_zero_loc():
    res = _route({
        "mutation_id": "test_mut_002",
        "intent": "doc_update",
        "files_touched": ["README.md"],
        "loc_added": 0,
        "loc_deleted": 0,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["summary"]["tier"] == "TRIVIAL"
    assert data["summary"]["skip_heavy_scoring"] is True


def test_route_preview_elevated_governance_path():
    res = _route({
        "mutation_id": "test_mut_003",
        "intent": "refactor",
        "files_touched": ["runtime/governance/gate.py"],
        "loc_added": 30,
        "loc_deleted": 5,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["summary"]["tier"] == "ELEVATED"
    assert data["summary"]["require_human_review"] is True


def test_route_preview_elevated_security_path():
    res = _route({
        "mutation_id": "test_mut_004",
        "intent": "harden",
        "files_touched": ["security/cryovant.py"],
        "loc_added": 15,
        "loc_deleted": 0,
    })
    assert res.status_code == 200
    assert res.json()["summary"]["tier"] == "ELEVATED"


def test_route_preview_elevated_intent_keyword():
    res = _route({
        "mutation_id": "test_mut_005",
        "intent": "ledger_compaction",
        "files_touched": ["data/ledger.jsonl"],
        "loc_added": 5,
        "loc_deleted": 5,
    })
    assert res.status_code == 200
    assert res.json()["summary"]["tier"] == "ELEVATED"


def test_route_preview_elevated_risk_tag():
    res = _route({
        "mutation_id": "test_mut_006",
        "intent": "fix",
        "files_touched": ["app/auth.py"],
        "loc_added": 10,
        "loc_deleted": 5,
        "risk_tags": ["SECURITY"],
    })
    assert res.status_code == 200
    assert res.json()["summary"]["tier"] == "ELEVATED"


def test_route_preview_decision_payload_fields():
    res = _route({"mutation_id": "test_payload", "intent": "refactor", "loc_added": 5, "loc_deleted": 5})
    data = res.json()
    dec = data["decision"]
    assert "mutation_id" in dec
    assert "tier" in dec
    assert "reasons" in dec
    assert "decision_digest" in dec
    assert "route_version" in dec


def test_route_preview_digest_determinism():
    payload = {"mutation_id": "det_test", "intent": "refactor", "files_touched": ["app/x.py"], "loc_added": 10, "loc_deleted": 5}
    d1 = _route(payload).json()["decision"]["decision_digest"]
    d2 = _route(payload).json()["decision"]["decision_digest"]
    assert d1 == d2


def test_route_preview_elevated_overrides_trivial():
    """Governance path with zero LOC must be ELEVATED, not TRIVIAL."""
    res = _route({
        "mutation_id": "override_test",
        "intent": "doc_update",
        "files_touched": ["runtime/governance/gate.py"],
        "loc_added": 0,
        "loc_deleted": 0,
    })
    assert res.json()["summary"]["tier"] == "ELEVATED"


# ─────────────────────────────────────────────────────────────────────────────
# /api/fast-path/entropy-gate
# ─────────────────────────────────────────────────────────────────────────────


def _gate(payload):
    return client.post("/api/fast-path/entropy-gate", json=payload)


def test_entropy_gate_allow():
    res = _gate({"mutation_id": "eg_001", "estimated_bits": 5, "sources": ["mutation_ops"]})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["result"]["verdict"] == "ALLOW"
    assert data["denied"] is False


def test_entropy_gate_warn():
    res = _gate({"mutation_id": "eg_002", "estimated_bits": 32, "sources": ["prng", "mutation_ops"]})
    assert res.status_code == 200
    assert res.json()["result"]["verdict"] == "WARN"


def test_entropy_gate_deny_high_bits():
    res = _gate({"mutation_id": "eg_003", "estimated_bits": 64, "sources": ["prng"]})
    assert res.status_code == 200
    data = res.json()
    assert data["result"]["verdict"] == "DENY"
    assert data["denied"] is True


def test_entropy_gate_deny_network_source_strict():
    res = _gate({"mutation_id": "eg_004", "estimated_bits": 1, "sources": ["network"], "strict": True})
    assert res.status_code == 200
    assert res.json()["result"]["verdict"] == "DENY"


def test_entropy_gate_warn_network_permissive():
    res = _gate({"mutation_id": "eg_005", "estimated_bits": 1, "sources": ["network"], "strict": False})
    assert res.status_code == 200
    assert res.json()["result"]["verdict"] == "WARN"


def test_entropy_gate_result_fields():
    res = _gate({"mutation_id": "eg_fields", "estimated_bits": 8, "sources": ["prng"]})
    result = res.json()["result"]
    assert "verdict" in result
    assert "gate_digest" in result
    assert "reason" in result
    assert "gate_version" in result
    assert "estimated_bits" in result
    assert "budget_bits" in result


def test_entropy_gate_digest_determinism():
    payload = {"mutation_id": "eg_det", "estimated_bits": 10, "sources": ["prng"]}
    d1 = _gate(payload).json()["result"]["gate_digest"]
    d2 = _gate(payload).json()["result"]["gate_digest"]
    assert d1 == d2


# ─────────────────────────────────────────────────────────────────────────────
# /api/fast-path/checkpoint-chain/verify
# ─────────────────────────────────────────────────────────────────────────────


def test_checkpoint_chain_verify_ok():
    res = client.get("/api/fast-path/checkpoint-chain/verify")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["integrity"] is True
    assert data["chain_length"] >= 1


def test_checkpoint_chain_links_structure():
    data = client.get("/api/fast-path/checkpoint-chain/verify").json()
    links = data["links"]
    assert len(links) > 0
    for link in links:
        assert "epoch_id" in link
        assert "chain_digest" in link
        assert "predecessor_digest" in link
        assert "chain_version" in link


def test_checkpoint_chain_head_and_genesis_present():
    data = client.get("/api/fast-path/checkpoint-chain/verify").json()
    assert "genesis_digest" in data
    assert "head_digest" in data
    assert data["genesis_digest"].startswith("sha256:")
    assert data["head_digest"].startswith("sha256:")


def test_checkpoint_chain_head_ne_genesis_for_multi_link():
    data = client.get("/api/fast-path/checkpoint-chain/verify").json()
    if data["chain_length"] > 1:
        assert data["genesis_digest"] != data["head_digest"]


def test_checkpoint_chain_verify_is_deterministic():
    """Two calls to verify should return the same genesis digest."""
    d1 = client.get("/api/fast-path/checkpoint-chain/verify").json()["genesis_digest"]
    d2 = client.get("/api/fast-path/checkpoint-chain/verify").json()["genesis_digest"]
    # genesis payload is fixed so digest must be stable
    assert d1 == d2


def test_route_preview_legacy_payload_defaults_still_succeed():
    """Legacy-compatible minimal payload retains default-safe behavior."""
    res = _route({"intent": "refactor", "loc_added": 1, "loc_deleted": 0})
    assert res.status_code == 200
    assert res.json()["decision"]["mutation_id"] == "unknown"


def test_route_preview_invalid_loc_type_fails_validation():
    res = _route({"mutation_id": "bad_loc", "intent": "refactor", "loc_added": "1", "loc_deleted": 0})
    assert res.status_code == 422
    assert any(item["loc"][-1] == "loc_added" for item in res.json()["detail"])


def test_route_preview_unknown_field_rejected():
    res = _route({"mutation_id": "bad_extra", "intent": "refactor", "shadow": "x"})
    assert res.status_code == 422
    assert any(item["type"] == "extra_forbidden" for item in res.json()["detail"])


def test_entropy_gate_legacy_payload_defaults_still_succeed():
    res = _gate({"estimated_bits": 0, "sources": []})
    assert res.status_code == 200
    assert res.json()["result"]["estimated_bits"] == 0


def test_entropy_gate_invalid_sources_type_fails_validation():
    res = _gate({"mutation_id": "bad_sources", "estimated_bits": 1, "sources": "network"})
    assert res.status_code == 422
    assert any(item["loc"][-1] == "sources" for item in res.json()["detail"])
