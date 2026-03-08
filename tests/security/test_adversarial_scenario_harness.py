# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

from runtime.analysis.adversarial_scenario_harness import run_manifest


def test_adversarial_manifest_matches_threat_model_narratives() -> None:
    report = run_manifest(Path("tests/security/fixtures/adversarial_governance_scenarios.json"))

    by_id = {row["scenario_id"]: row for row in report["results"]}

    assert report["scenario_count"] == 5
    assert report["failed_count"] == 0
    assert report["complete"] is True

    assert by_id["RTN-001"]["actual_verdict"] == "block"
    assert by_id["RTN-001"]["evidence"]["critical_audit_event"] is True

    assert by_id["RTN-002"]["evidence"]["dev_token_rejected_in_prod"] is True

    assert by_id["RTN-003"]["evidence"]["runtime_error"] == "strict_replay_requires_deterministic_provider"

    assert by_id["RTN-004"]["evidence"]["status"] == "REJECTED"
    assert by_id["RTN-004"]["evidence"]["token_ok"] is False

    assert by_id["RTN-005"]["evidence"]["tier_after_short_gap"] == "governance"
    assert by_id["RTN-005"]["evidence"]["tier_after_window"] == "none"


def test_summary_contains_operator_facing_fields() -> None:
    report = run_manifest(Path("tests/security/fixtures/adversarial_governance_scenarios.json"))

    required_fields = {"scenario_id", "expected_verdict", "actual_verdict", "evidence_pointers", "passed"}
    for row in report["results"]:
        assert required_fields <= set(row.keys())
        assert row["evidence_pointers"]
