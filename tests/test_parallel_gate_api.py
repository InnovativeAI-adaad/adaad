# SPDX-License-Identifier: Apache-2.0
"""Tests for Parallel Governance Gate API endpoints (server.py v0.66)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server import app

client = TestClient(app)

# ─────────────────────────────────────────────────────────────────────────────
# /api/governance/parallel-gate/probe-library
# ─────────────────────────────────────────────────────────────────────────────


def test_probe_library_ok():
    res = client.get("/api/governance/parallel-gate/probe-library")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "axes" in data
    assert data["total_probes"] > 0


def test_probe_library_expected_axes():
    data = client.get("/api/governance/parallel-gate/probe-library").json()
    axes = data["axes"]
    for expected in ["entropy", "constitution", "founders_law", "lineage", "sandbox", "replay"]:
        assert expected in axes, f"axis '{expected}' missing from probe library"


def test_probe_library_rule_structure():
    data = client.get("/api/governance/parallel-gate/probe-library").json()
    for axis, rules in data["axes"].items():
        for rule in rules:
            assert "rule_id" in rule
            assert "default_ok" in rule
            assert "default_reason" in rule


def test_probe_library_axes_sorted():
    data = client.get("/api/governance/parallel-gate/probe-library").json()
    keys = list(data["axes"].keys())
    assert keys == sorted(keys)


# ─────────────────────────────────────────────────────────────────────────────
# /api/governance/parallel-gate/evaluate  — happy paths
# ─────────────────────────────────────────────────────────────────────────────


APPROVE_SPECS = [
    {"axis": "entropy",      "rule_id": "budget_ok"},
    {"axis": "entropy",      "rule_id": "source_clean"},
    {"axis": "constitution", "rule_id": "tier_ok"},
    {"axis": "constitution", "rule_id": "hash_valid"},
    {"axis": "lineage",      "rule_id": "chain_intact"},
    {"axis": "sandbox",      "rule_id": "preflight_ok"},
]

REJECT_SPECS = [
    {"axis": "entropy",      "rule_id": "budget_exceeded"},
    {"axis": "constitution", "rule_id": "tier_violated"},
    {"axis": "lineage",      "rule_id": "chain_broken"},
    {"axis": "sandbox",      "rule_id": "preflight_failed"},
]


def _eval(payload):
    return client.post("/api/governance/parallel-gate/evaluate", json=payload)


def test_evaluate_standard_approve():
    res = _eval({
        "mutation_id": "t_approve_001",
        "trust_mode": "standard",
        "axis_specs": APPROVE_SPECS,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["decision"]["approved"] is True
    assert data["decision"]["decision"] == "approve"


def test_evaluate_full_rejection():
    res = _eval({
        "mutation_id": "t_reject_001",
        "trust_mode": "elevated",
        "axis_specs": REJECT_SPECS,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["decision"]["approved"] is False
    assert data["decision"]["decision"] == "reject"


def test_evaluate_response_structure():
    res = _eval({"mutation_id": "t_struct", "trust_mode": "standard", "axis_specs": APPROVE_SPECS})
    data = res.json()
    assert "ok" in data
    assert "decision" in data
    assert "wall_elapsed_ms" in data
    assert "gate_version" in data
    assert "max_workers" in data
    assert "axis_count" in data


def test_evaluate_decision_fields():
    res = _eval({"mutation_id": "t_fields", "trust_mode": "standard", "axis_specs": APPROVE_SPECS})
    dec = res.json()["decision"]
    assert "approved" in dec
    assert "decision" in dec
    assert "mutation_id" in dec
    assert "trust_mode" in dec
    assert "reason_codes" in dec
    assert "failed_rules" in dec
    assert "axis_results" in dec
    assert "decision_id" in dec
    assert "human_override" in dec


def test_evaluate_axis_results_count():
    res = _eval({"mutation_id": "t_count", "trust_mode": "standard", "axis_specs": APPROVE_SPECS})
    data = res.json()
    assert data["axis_count"] == len(APPROVE_SPECS)
    assert len(data["decision"]["axis_results"]) == len(APPROVE_SPECS)


def test_evaluate_axis_results_sorted():
    """Results must be sorted by (axis, rule_id) — deterministic merge invariant."""
    res = _eval({"mutation_id": "t_sort", "trust_mode": "standard", "axis_specs": APPROVE_SPECS})
    results = res.json()["decision"]["axis_results"]
    keys = [(r["axis"], r["rule_id"]) for r in results]
    assert keys == sorted(keys)


def test_evaluate_timing_annotations():
    """Per-axis duration_ms must be present and non-negative."""
    res = _eval({"mutation_id": "t_timing", "trust_mode": "standard", "axis_specs": APPROVE_SPECS})
    for ar in res.json()["decision"]["axis_results"]:
        assert "duration_ms" in ar
        assert ar["duration_ms"] >= 0


def test_evaluate_decision_digest_format():
    res = _eval({"mutation_id": "t_digest", "trust_mode": "standard", "axis_specs": APPROVE_SPECS})
    did = res.json()["decision"]["decision_id"]
    assert isinstance(did, str)
    assert did.startswith("sha256:")


def test_evaluate_decision_digest_determinism():
    """Same inputs → same decision_id (deterministic merge)."""
    payload = {"mutation_id": "det_001", "trust_mode": "standard", "axis_specs": APPROVE_SPECS}
    d1 = _eval(payload).json()["decision"]["decision_id"]
    d2 = _eval(payload).json()["decision"]["decision_id"]
    assert d1 == d2


def test_evaluate_wall_elapsed_positive():
    res = _eval({"mutation_id": "t_wall", "trust_mode": "standard", "axis_specs": APPROVE_SPECS})
    assert res.json()["wall_elapsed_ms"] >= 0


def test_evaluate_trust_mode_reflected():
    res = _eval({"mutation_id": "t_trust", "trust_mode": "elevated", "axis_specs": APPROVE_SPECS})
    assert res.json()["decision"]["trust_mode"] == "elevated"


def test_evaluate_reason_codes_empty_on_approve():
    res = _eval({"mutation_id": "t_codes", "trust_mode": "standard", "axis_specs": APPROVE_SPECS})
    assert res.json()["decision"]["reason_codes"] == []


def test_evaluate_reason_codes_nonempty_on_reject():
    res = _eval({"mutation_id": "t_rcodes", "trust_mode": "elevated", "axis_specs": REJECT_SPECS})
    assert len(res.json()["decision"]["reason_codes"]) > 0


def test_evaluate_mixed_axes_rejection():
    """One failing axis rejects the whole gate."""
    specs = [
        {"axis": "entropy",      "rule_id": "budget_ok"},
        {"axis": "constitution", "rule_id": "tier_ok"},
        {"axis": "entropy",      "rule_id": "budget_exceeded"},  # fail
    ]
    res = _eval({"mutation_id": "t_mixed", "trust_mode": "standard", "axis_specs": specs})
    assert res.json()["decision"]["approved"] is False


def test_evaluate_single_axis():
    res = _eval({
        "mutation_id": "t_single",
        "trust_mode": "standard",
        "axis_specs": [{"axis": "entropy", "rule_id": "budget_ok"}],
    })
    assert res.status_code == 200
    assert res.json()["axis_count"] == 1


def test_evaluate_gate_version_present():
    res = _eval({"mutation_id": "t_ver", "trust_mode": "standard", "axis_specs": APPROVE_SPECS})
    assert res.json()["gate_version"].startswith("v")


def test_evaluate_unknown_probe_defaults_pass():
    """Unknown axis/rule_id → probe_not_found_default_pass → ok=True."""
    specs = [{"axis": "custom_axis", "rule_id": "nonexistent_rule"}]
    res = _eval({"mutation_id": "t_unknown", "trust_mode": "standard", "axis_specs": specs})
    assert res.status_code == 200
    ar = res.json()["decision"]["axis_results"][0]
    assert ar["ok"] is True
    assert "probe_not_found" in ar["reason"]


# ─────────────────────────────────────────────────────────────────────────────
# /api/governance/parallel-gate/evaluate  — human override
# ─────────────────────────────────────────────────────────────────────────────

def test_evaluate_human_override_reflected():
    res = _eval({
        "mutation_id": "t_override",
        "trust_mode": "elevated",
        "human_override": True,
        "axis_specs": APPROVE_SPECS,
    })
    assert res.json()["decision"]["human_override"] is True


# ─────────────────────────────────────────────────────────────────────────────
# /api/governance/parallel-gate/evaluate  — validation errors
# ─────────────────────────────────────────────────────────────────────────────

def test_evaluate_empty_axis_specs_rejected():
    res = _eval({"mutation_id": "t_empty", "trust_mode": "standard", "axis_specs": []})
    assert res.status_code == 422


def test_evaluate_too_many_axes_rejected():
    specs = [{"axis": "entropy", "rule_id": "budget_ok"}] * 21
    res = _eval({"mutation_id": "t_over", "trust_mode": "standard", "axis_specs": specs})
    assert res.status_code == 422


def test_evaluate_missing_mutation_id_rejected():
    res = client.post("/api/governance/parallel-gate/evaluate", json={
        "trust_mode": "standard",
        "axis_specs": APPROVE_SPECS,
    })
    assert res.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Preset scenario smoke tests
# ─────────────────────────────────────────────────────────────────────────────

def test_preset_deep_audit_scenario():
    """11-axis deep audit — all passing probes → approved."""
    specs = [
        {"axis": "entropy",      "rule_id": "budget_ok"},
        {"axis": "entropy",      "rule_id": "source_clean"},
        {"axis": "constitution", "rule_id": "tier_ok"},
        {"axis": "constitution", "rule_id": "hash_valid"},
        {"axis": "founders_law", "rule_id": "invariant_ok"},
        {"axis": "lineage",      "rule_id": "chain_intact"},
        {"axis": "lineage",      "rule_id": "digest_match"},
        {"axis": "sandbox",      "rule_id": "preflight_ok"},
        {"axis": "sandbox",      "rule_id": "isolation_ok"},
        {"axis": "replay",       "rule_id": "baseline_match"},
        {"axis": "replay",       "rule_id": "determinism_ok"},
    ]
    res = _eval({"mutation_id": "t_deep_audit", "trust_mode": "standard", "axis_specs": specs})
    assert res.status_code == 200
    assert res.json()["decision"]["approved"] is True
    assert res.json()["axis_count"] == 11


def test_preset_elevated_mixed_scenario():
    """Mixed pass/fail → rejected."""
    specs = [
        {"axis": "entropy",      "rule_id": "budget_ok"},
        {"axis": "entropy",      "rule_id": "nondeterministic"},
        {"axis": "constitution", "rule_id": "tier_ok"},
        {"axis": "constitution", "rule_id": "hash_mismatch"},
        {"axis": "founders_law", "rule_id": "invariant_ok"},
        {"axis": "lineage",      "rule_id": "chain_intact"},
        {"axis": "sandbox",      "rule_id": "preflight_ok"},
        {"axis": "replay",       "rule_id": "determinism_ok"},
    ]
    res = _eval({"mutation_id": "t_elev_mix", "trust_mode": "elevated", "axis_specs": specs})
    assert res.json()["decision"]["approved"] is False
