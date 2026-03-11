# SPDX-License-Identifier: Apache-2.0
"""Tests: Governance Profile Exporter — ADAAD-8 / PR-13 (Milestone)

Tests cover:
- export_profile: simulation=True always present
- export_profile: schema_version = 'governance_profile.v1'
- export_profile: simulation_policy.simulation = True
- export_profile: epoch_range derived from epoch results
- export_profile: summary fields all present and correct
- export_profile: scoring_versions metadata present
- export_profile: profile_digest is deterministic (identical inputs → identical digest)
- export_profile: different inputs produce different digests
- export_profile: raises ValueError for non-simulation run_result
- validate_profile_schema: passes for valid profile
- validate_profile_schema: raises for missing required fields
- validate_profile_schema: raises if simulation=False
- GovernanceProfile: frozen — cannot mutate fields
- GovernanceProfile: simulation=False raises at construction
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.simulation.constraint_interpreter import interpret_policy_block
from runtime.governance.simulation.epoch_simulator import EpochReplaySimulator
from runtime.governance.simulation.profile_exporter import (
    GovernanceProfile,
    GOVERNANCE_PROFILE_SCHEMA_VERSION,
    export_profile,
    validate_profile_schema,
    profile_digest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_policy():
    return interpret_policy_block("")


def _policy(dsl: str):
    return interpret_policy_block(dsl)


def _make_run_result(epoch_ids=("e1", "e2"), dsl=""):
    policy = interpret_policy_block(dsl)
    sim = EpochReplaySimulator(policy)
    epoch_data = {
        eid: {
            "epoch_id": eid,
            "mutations": [
                {"mutation_id": f"m-{eid}-1", "risk_score": 0.2, "complexity_delta": 0.05,
                 "lineage_depth": 3, "test_coverage": 0.9, "tier": "standard", "entropy": 0.1}
            ],
            "actual_mutations_advanced": 1,
            "entropy": 0.1,
            "scoring_algorithm_version": "1.0",
        }
        for eid in epoch_ids
    }
    return sim.simulate_epoch_range(list(epoch_ids), epoch_data_map=epoch_data), policy


# ---------------------------------------------------------------------------
# GovernanceProfile construction
# ---------------------------------------------------------------------------

class TestGovernanceProfileConstruction:
    def test_simulation_false_raises(self):
        with pytest.raises(ValueError):
            GovernanceProfile(
                simulation=False,
                schema_version=GOVERNANCE_PROFILE_SCHEMA_VERSION,
                generated_at="deterministic",
                epoch_range={"start": None, "end": None},
                simulation_policy={},
                summary={},
                epoch_results=[],
                scoring_versions={},
                profile_digest="sha256:" + "a" * 64,
            )

    def test_simulation_true_constructs_successfully(self):
        profile = GovernanceProfile(
            simulation=True,
            schema_version=GOVERNANCE_PROFILE_SCHEMA_VERSION,
            generated_at="deterministic",
            epoch_range={"start": None, "end": None},
            simulation_policy={"simulation": True},
            summary={"epochs_evaluated": 0},
            epoch_results=[],
            scoring_versions={},
            profile_digest="sha256:" + "a" * 64,
        )
        assert profile.simulation is True

    def test_profile_is_frozen(self):
        profile = GovernanceProfile(
            simulation=True,
            schema_version=GOVERNANCE_PROFILE_SCHEMA_VERSION,
            generated_at="deterministic",
            epoch_range={"start": None, "end": None},
            simulation_policy={"simulation": True},
            summary={},
            epoch_results=[],
            scoring_versions={},
            profile_digest="sha256:" + "a" * 64,
        )
        with pytest.raises((AttributeError, TypeError)):
            profile.simulation = False  # type: ignore


# ---------------------------------------------------------------------------
# export_profile
# ---------------------------------------------------------------------------

class TestExportProfile:
    def test_simulation_true_in_exported_profile(self):
        run, policy = _make_run_result()
        profile = export_profile(run, policy, generated_at="deterministic")
        assert profile.simulation is True

    def test_schema_version_correct(self):
        run, policy = _make_run_result()
        profile = export_profile(run, policy, generated_at="deterministic")
        assert profile.schema_version == GOVERNANCE_PROFILE_SCHEMA_VERSION

    def test_simulation_policy_simulation_true(self):
        run, policy = _make_run_result()
        profile = export_profile(run, policy, generated_at="deterministic")
        assert profile.simulation_policy["simulation"] is True

    def test_epoch_range_correct(self):
        run, policy = _make_run_result(epoch_ids=("e1", "e2"))
        profile = export_profile(run, policy, generated_at="deterministic")
        assert profile.epoch_range["start"] == "e1"
        assert profile.epoch_range["end"] == "e2"

    def test_epoch_range_none_for_empty_run(self):
        policy = _empty_policy()
        sim = EpochReplaySimulator(policy)
        run = sim.simulate_epoch_range([], epoch_data_map={})
        profile = export_profile(run, policy, generated_at="deterministic")
        assert profile.epoch_range["start"] is None
        assert profile.epoch_range["end"] is None

    def test_summary_required_fields_present(self):
        run, policy = _make_run_result()
        profile = export_profile(run, policy, generated_at="deterministic")
        assert "epochs_evaluated" in profile.summary
        assert "velocity_impact_pct" in profile.summary
        assert "mutations_gated" in profile.summary
        assert "drift_risk_delta_mean" in profile.summary
        assert "governance_health_score_mean" in profile.summary

    def test_summary_epochs_evaluated_correct(self):
        run, policy = _make_run_result(epoch_ids=("e1", "e2", "e3"))
        profile = export_profile(run, policy, generated_at="deterministic")
        assert profile.summary["epochs_evaluated"] == 3

    def test_epoch_results_count_matches(self):
        run, policy = _make_run_result(epoch_ids=("e1", "e2"))
        profile = export_profile(run, policy, generated_at="deterministic")
        assert len(profile.epoch_results) == 2

    def test_scoring_versions_present(self):
        run, policy = _make_run_result()
        profile = export_profile(run, policy, generated_at="deterministic")
        assert isinstance(profile.scoring_versions, dict)
        assert len(profile.scoring_versions) > 0

    def test_profile_digest_present_and_sha256_prefixed(self):
        run, policy = _make_run_result()
        profile = export_profile(run, policy, generated_at="deterministic")
        assert profile.profile_digest.startswith("sha256:")
        assert len(profile.profile_digest) == 7 + 64  # "sha256:" + 64 hex chars

    def test_raises_for_non_simulation_run(self):
        from runtime.governance.simulation.epoch_simulator import SimulationRunResult
        fake_run = SimulationRunResult(
            simulation=False,  # invalid
            epoch_count=0,
            total_mutations_actual=0,
            total_mutations_simulated=0,
            total_mutations_blocked=0,
            velocity_impact_pct=0.0,
            drift_risk_delta_mean=0.0,
            governance_health_score_mean=1.0,
            epoch_results=[],
            policy_digest="sha256:" + "a" * 64,
            run_digest="sha256:" + "b" * 64,
        )
        policy = _empty_policy()
        with pytest.raises(ValueError):
            export_profile(fake_run, policy)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestExportProfileDeterminism:
    def test_identical_inputs_produce_identical_profile_digest(self):
        run1, policy1 = _make_run_result(epoch_ids=("e1", "e2"), dsl="max_risk_score(threshold=0.5)")
        run2, policy2 = _make_run_result(epoch_ids=("e1", "e2"), dsl="max_risk_score(threshold=0.5)")
        p1 = export_profile(run1, policy1, generated_at="deterministic")
        p2 = export_profile(run2, policy2, generated_at="deterministic")
        assert p1.profile_digest == p2.profile_digest

    def test_different_policy_produces_different_digest(self):
        run1, p1 = _make_run_result(dsl="max_risk_score(threshold=0.3)")
        run2, p2 = _make_run_result(dsl="max_risk_score(threshold=0.7)")
        profile1 = export_profile(run1, p1, generated_at="deterministic")
        profile2 = export_profile(run2, p2, generated_at="deterministic")
        assert profile1.profile_digest != profile2.profile_digest

    def test_to_dict_is_deterministic(self):
        run, policy = _make_run_result()
        profile = export_profile(run, policy, generated_at="deterministic")
        d1 = profile.to_dict()
        d2 = profile.to_dict()
        assert d1 == d2

    def test_profile_digest_function(self):
        run, policy = _make_run_result()
        p = export_profile(run, policy, generated_at="deterministic")
        assert profile_digest(p) == p.profile_digest


# ---------------------------------------------------------------------------
# validate_profile_schema
# ---------------------------------------------------------------------------

class TestValidateProfileSchema:
    def test_valid_profile_passes(self):
        run, policy = _make_run_result()
        profile = export_profile(run, policy, generated_at="deterministic")
        assert validate_profile_schema(profile.to_dict()) is True

    def test_missing_required_field_raises(self):
        run, policy = _make_run_result()
        d = export_profile(run, policy, generated_at="deterministic").to_dict()
        del d["simulation"]
        with pytest.raises(ValueError) as exc_info:
            validate_profile_schema(d)
        assert "simulation" in str(exc_info.value)

    def test_simulation_false_raises(self):
        run, policy = _make_run_result()
        d = export_profile(run, policy, generated_at="deterministic").to_dict()
        d["simulation"] = False
        with pytest.raises(ValueError):
            validate_profile_schema(d)

    def test_wrong_schema_version_raises(self):
        run, policy = _make_run_result()
        d = export_profile(run, policy, generated_at="deterministic").to_dict()
        d["schema_version"] = "governance_profile.v0"
        with pytest.raises(ValueError):
            validate_profile_schema(d)

    def test_policy_simulation_false_raises(self):
        run, policy = _make_run_result()
        d = export_profile(run, policy, generated_at="deterministic").to_dict()
        d["simulation_policy"] = {"simulation": False}
        with pytest.raises(ValueError):
            validate_profile_schema(d)
