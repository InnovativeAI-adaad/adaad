# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.replay import ReplayEngine, ReplayVersionValidator


def test_replay_version_validator_audit_ignores_ephemeral_field_mismatches() -> None:
    validator = ReplayVersionValidator()
    bundle = {
        "scoring_algorithm_version": "v1.1.0",
        "governor_version": "3.0.0",
        "replay_scoring_algorithm_version": "v1.2.0",
        "nonce": "one",
        "generated_at": "2026-01-01T00:00:00Z",
        "run_id": "run-a",
    }

    report = validator.validate(bundle, mode="audit")

    assert report["ok"] is True
    assert report["decision"] == "allow_with_divergence"
    assert "scoring_algorithm_version" in report["mismatches"]
    assert "nonce" not in report["normalized_bundle"]


def test_replay_version_validator_migration_missing_module_reports_gap() -> None:
    validator = ReplayVersionValidator()
    bundle = {
        "scoring_algorithm_version": "v9.9.9",
        "governor_version": "3.0.0",
        "replay_scoring_algorithm_version": "v1.1.0",
    }

    report = validator.validate(bundle, mode="migration")

    assert report["ok"] is True
    assert report["decision"] == "allow_with_migration_report"
    assert report["migration"]["missing_historical_module"] is True


def test_replay_engine_exposes_version_validate() -> None:
    engine = ReplayEngine()
    report = engine.version_validate({"scoring_algorithm_version": "v1", "governor_version": "3"}, mode="strict")
    assert report["mode"] == "strict"

