# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.goal_graph import GoalGraph


def test_goal_graph_load_and_compute_is_deterministic() -> None:
    graph = GoalGraph.load(Path("runtime/evolution/goal_graph.json"))
    state = {
        "metrics": {
            "tests_ok": 1.0,
            "survival_score": 0.8,
            "risk_score_inverse": 0.9,
            "entropy_compliance": 1.0,
            "deterministic_replay_seed": 1.0,
        },
        "capabilities": [
            "mutation_execution",
            "test_validation",
            "impact_analysis",
            "entropy_discipline",
            "audit_logging",
        ],
    }

    first = graph.compute_goal_score(state)
    second = graph.compute_goal_score(state)

    assert first == second
    assert 0.0 <= first <= 1.0


def test_goal_graph_threshold_penalty_reduces_score() -> None:
    graph = GoalGraph.load(Path("runtime/evolution/goal_graph.json"))
    strong_state = {
        "metrics": {
            "tests_ok": 1.0,
            "survival_score": 0.8,
            "risk_score_inverse": 0.9,
            "entropy_compliance": 1.0,
            "deterministic_replay_seed": 1.0,
        },
        "capabilities": [
            "mutation_execution",
            "test_validation",
            "impact_analysis",
            "entropy_discipline",
            "audit_logging",
        ],
    }
    weak_state = {
        "metrics": {
            "tests_ok": 0.0,
            "survival_score": 0.1,
            "risk_score_inverse": 0.1,
            "entropy_compliance": 0.0,
            "deterministic_replay_seed": 0.0,
        },
        "capabilities": [],
    }

    assert graph.compute_goal_score(weak_state) < graph.compute_goal_score(strong_state)


def test_goal_graph_reload_requires_valid_signature(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    goal_path = tmp_path / "goal_graph.json"
    goal_path.write_text('{"goals": []}', encoding="utf-8")

    monkeypatch.setattr("security.cryovant.verify_payload_signature", lambda payload, signature, key_id: False)
    with pytest.raises(ValueError, match="goal_graph_signature_verification_failed"):
        GoalGraph.reload_goal_graph(goal_path, signature="sha256:" + "0" * 64)


def test_goal_graph_reload_preserves_deterministic_scoring(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    goal_path = tmp_path / "goal_graph.json"
    source = Path("runtime/evolution/goal_graph.json").read_text(encoding="utf-8")
    goal_path.write_text(source, encoding="utf-8")
    monkeypatch.setattr("security.cryovant.verify_payload_signature", lambda payload, signature, key_id: True)

    before = GoalGraph.load(goal_path)
    before_score = before.compute_goal_score(
        {
            "metrics": {"tests_ok": 1.0, "survival_score": 0.8, "risk_score_inverse": 0.9, "entropy_compliance": 1.0, "deterministic_replay_seed": 1.0},
            "capabilities": ["mutation_execution", "test_validation", "impact_analysis", "entropy_discipline", "audit_logging"],
        }
    )
    reloaded = GoalGraph.reload_goal_graph(goal_path, signature="sha256:" + "1" * 64)
    after_score = reloaded.compute_goal_score(
        {
            "metrics": {"tests_ok": 1.0, "survival_score": 0.8, "risk_score_inverse": 0.9, "entropy_compliance": 1.0, "deterministic_replay_seed": 1.0},
            "capabilities": ["mutation_execution", "test_validation", "impact_analysis", "entropy_discipline", "audit_logging"],
        }
    )

    assert before_score == after_score
