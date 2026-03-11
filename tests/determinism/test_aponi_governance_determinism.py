# SPDX-License-Identifier: Apache-2.0

# ADAAD-LANE: determinism-replay

import json
from unittest.mock import patch
from runtime.governance.event_taxonomy import (
    EVENT_TYPE_CONSTITUTION_ESCALATION,
    EVENT_TYPE_AGM_STEP_01,
    EVENT_TYPE_BUDGET_MODE_CHANGED,
    EVENT_TYPE_OPERATOR_OVERRIDE,
    EVENT_TYPE_REPLAY_DIVERGENCE,
    EVENT_TYPE_REPLAY_FAILURE,
    normalize_agm_step,
    normalize_event_type,
    validate_event_type_for_agm_step,
)
from runtime.governance.policy_artifact import GovernanceModelMetadata, GovernancePolicy, GovernanceThresholds
from ui import aponi_dashboard
from ui.aponi_dashboard import AponiDashboard, _skill_capability_matrix
def _handler_class():
    dashboard = AponiDashboard(host="127.0.0.1", port=0)
    return dashboard._build_handler()
def _test_policy() -> GovernancePolicy:
    return GovernancePolicy(
        schema_version="governance_policy_v1",
        model=GovernanceModelMetadata(name="governance_health", version="v1.0.0"),
        determinism_window=200,
        mutation_rate_window_sec=3600,
        thresholds=GovernanceThresholds(determinism_pass=0.98, determinism_warn=0.90),
        fingerprint="sha256:testpolicy",
    )
def test_governance_health_model_is_formalized_and_deterministic() -> None:
    handler = _handler_class()
    with patch("ui.aponi_dashboard.GOVERNANCE_POLICY", _test_policy()):
        with patch.object(handler, "_rolling_determinism_score", return_value={"rolling_score": 0.99}):
            with patch.object(
                handler,
                "_mutation_rate_state",
                return_value={"ok": True, "max_mutations_per_hour": 60.0, "rate_per_hour": 6.0},
            ):
                with patch("ui.aponi_dashboard.metrics.tail", return_value=[]):
                    snapshot = handler._intelligence_snapshot()

    assert snapshot["governance_health"] == "PASS"
    assert snapshot["model_version"] == "v1.0.0"
    assert snapshot["policy_fingerprint"] == "sha256:testpolicy"
    assert snapshot["model_inputs"]["threshold_pass"] == 0.98
    assert snapshot["model_inputs"]["threshold_warn"] == 0.90
def test_replay_diff_returns_semantic_drift_with_stable_ordering() -> None:
    epoch = {
        "bundles": [{"id": "b-1"}],
        "initial_state": {
            "traits.error_handler": "off",
            "config.max_mutations": 60,
            "constitution.policy_hash": "abc",
            "runtime.checkpoint.last": "cp-1",
            "zeta": "legacy",
        },
        "final_state": {
            "config.max_mutations": 30,
            "traits.error_handler": "on",
            "constitution.policy_hash": "def",
            "runtime.checkpoint.last": "cp-2",
            "alpha": "new-value",
        },
    }
    with patch("ui.aponi_dashboard.ReplayEngine") as replay_mock:
        replay_mock.return_value.reconstruct_epoch.return_value = epoch
        handler = _handler_class()
        payload = handler._replay_diff("epoch-1")

    assert payload["ok"] is True
    assert payload["changed_keys"] == [
        "config.max_mutations",
        "constitution.policy_hash",
        "runtime.checkpoint.last",
        "traits.error_handler",
    ]
    assert payload["added_keys"] == ["alpha"]
    assert payload["removed_keys"] == ["zeta"]
    assert list(payload["semantic_drift"]["per_key"].keys()) == [
        "alpha",
        "config.max_mutations",
        "constitution.policy_hash",
        "runtime.checkpoint.last",
        "traits.error_handler",
        "zeta",
    ]
    assert payload["semantic_drift"]["class_counts"] == {
        "config_drift": 1,
        "governance_drift": 1,
        "trait_drift": 1,
        "runtime_artifact_drift": 1,
        "uncategorized_drift": 2,
    }
def test_risk_instability_uses_weighted_deterministic_formula() -> None:
    handler = _handler_class()
    risk_summary = {
        "escalation_frequency": 0.2,
        "override_frequency": 0.0,
        "replay_failure_rate": 0.1,
        "aggression_trend_variance": 0.0,
        "determinism_drift_index": 0.05,
    }
    timeline = [
        {"risk_tier": "high"},
        {"risk_tier": "critical"},
        {"risk_tier": "low"},
        {"risk_tier": "unknown"},
    ]
    with patch.object(handler, "_risk_summary", return_value=risk_summary):
        with patch.object(handler, "_evolution_timeline", return_value=timeline):
            with patch.object(handler, "_semantic_drift_weighted_density", return_value={"density": 0.75, "window": 4, "considered": 4}):
                payload = handler._risk_instability()

    # drift density = 3/4 = 0.75
    # instability = 0.35*0.75 + 0.25*0.1 + 0.20*0.2 + 0.20*0.05 = 0.3375
    assert payload["instability_index"] == 0.3375
    assert payload["instability_velocity"] == 0.0
    assert payload["instability_acceleration"] == 0.0
    assert payload["inputs"]["timeline_window"] == 4
    assert payload["inputs"]["semantic_drift_density"] == 0.75
def test_queue_control_command_appends_deterministic_entry(tmp_path, monkeypatch) -> None:
    queue_path = tmp_path / "aponi_queue.jsonl"
    monkeypatch.setattr("ui.aponi_dashboard.CONTROL_QUEUE_PATH", queue_path)
    from ui.aponi_dashboard import _queue_control_command

    entry = _queue_control_command(
        {
            "type": "run_task",
            "agent_id": "triage_agent",
            "governance_profile": "strict",
            "mode": "builder",
            "skill_profile": "triage-basic",
            "knowledge_domain": "release_notes",
            "capabilities": ["wikipedia"],
            "task": "summarize release risk",
            "ability": "summarize",
        }
    )

    assert entry["queue_index"] == 1
    assert entry["command_id"].startswith("cmd-000001-")
    assert entry["previous_digest"] == ""
    lines = queue_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
def test_control_policy_summary_and_templates_are_deterministic(tmp_path, monkeypatch) -> None:
    sources_path = tmp_path / "free_sources.json"
    sources_path.write_text(json.dumps({"wikipedia": {"provider": "Wikimedia"}}), encoding="utf-8")
    profiles_path = tmp_path / "profiles.json"
    profiles_path.write_text(
        json.dumps(
            {
                "triage-basic": {
                    "knowledge_domains": ["release_notes"],
                    "abilities": ["summarize"],
                    "allowed_capabilities": ["wikipedia"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("ui.aponi_dashboard.FREE_CAPABILITY_SOURCES_PATH", sources_path)
    monkeypatch.setattr("ui.aponi_dashboard.SKILL_PROFILES_PATH", profiles_path)

    from ui.aponi_dashboard import _control_intent_templates, _control_policy_summary

    summary = _control_policy_summary()
    templates = _control_intent_templates()

    assert summary["max_capabilities_per_intent"] >= 1
    assert summary["skill_profiles"] == ["triage-basic"]
    assert templates["triage-basic"]["run_task"]["ability"] == "summarize"
    assert templates["triage-basic"]["create_agent"]["knowledge_domain"] == "release_notes"
