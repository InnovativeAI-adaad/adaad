# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.mutation_executor import MutationExecutor
from runtime.evolution.goal_graph import GoalGraph
from runtime.evolution.runtime import EvolutionRuntime
from runtime.governance.foundation import SeededDeterminismProvider


pytestmark = pytest.mark.regression_standard

def test_goal_graph_valid_payload_loads_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = GoalGraph(())

    def _read(_path: Path) -> str:
        return json.dumps({"goals": []})

    monkeypatch.setattr("app.mutation_executor.MutationExecutor._read_goal_graph_raw", staticmethod(_read))
    monkeypatch.setattr("app.mutation_executor.GoalGraph.load", lambda _path: expected)

    executor = MutationExecutor(Path("/tmp"))

    assert executor.goal_graph is expected


def test_goal_graph_corrupt_payload_in_strict_mode_fails_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.mutation_executor.MutationExecutor._read_goal_graph_raw", staticmethod(lambda _path: "{not-json"))
    runtime = EvolutionRuntime(provider=SeededDeterminismProvider(seed="goal-graph-test"))
    runtime.set_replay_mode("strict")

    with pytest.raises(RuntimeError, match="goal_graph_initialization_failed:parse_error"):
        MutationExecutor(Path("/tmp"), evolution_runtime=runtime)


def test_goal_graph_corrupt_payload_allows_fallback_only_in_explicit_non_strict_dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.mutation_executor.MutationExecutor._read_goal_graph_raw", staticmethod(lambda _path: "{not-json"))
    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.setenv("CRYOVANT_DEV_MODE", "1")
    monkeypatch.delenv("ADAAD_REPLAY_MODE", raising=False)

    executor = MutationExecutor(Path("/tmp"))

    assert executor.goal_graph.compute_goal_score({}) == 0.0
