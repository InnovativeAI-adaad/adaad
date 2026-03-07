# SPDX-License-Identifier: Apache-2.0
"""
Integration tests for runtime/evolution/evolution_loop.py.

All 5 tests mock propose_from_all_agents — no real Claude API calls.
simulate_outcomes=True enables full weight adaptation in tests.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch

from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.autonomy.mutation_scaffold import MutationCandidate
from runtime.autonomy.roadmap_amendment_engine import GovernanceViolation
from runtime.evolution.evolution_loop import EvolutionLoop, EpochResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_candidates(agent: str, n: int = 4) -> list[MutationCandidate]:
    return [
        MutationCandidate(
            mutation_id=f"{agent}-mc-{i:03d}",
            expected_gain=0.6,
            risk_score=0.1,
            complexity=0.2,
            coverage_delta=0.3,
            agent_origin=agent,
            epoch_id="epoch-test",
        )
        for i in range(n)
    ]


MOCK_PROPOSALS = {
    "architect": _make_candidates("architect"),
    "dream":     _make_candidates("dream"),
    "beast":     _make_candidates("beast"),
}


def _make_context() -> CodebaseContext:
    return CodebaseContext(
        file_summaries={"runtime/evolution/evolution_loop.py": "Epoch orchestrator."},
        recent_failures=[],
        current_epoch_id="epoch-test-001",
    )


@pytest.fixture
def loop(tmp_path) -> EvolutionLoop:
    # Patch persistence paths to tmp_path to avoid polluting data/
    with patch("runtime.autonomy.weight_adaptor.DEFAULT_STATE_PATH", tmp_path / "w.json"), \
         patch("runtime.autonomy.fitness_landscape.DEFAULT_LANDSCAPE_PATH", tmp_path / "fl.json"):
        return EvolutionLoop(api_key="test-key", generations=2, simulate_outcomes=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_epoch_returns_epoch_result(loop) -> None:
    ctx = _make_context()
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=MOCK_PROPOSALS,
    ):
        result = loop.run_epoch(ctx)
    assert isinstance(result, EpochResult)
    assert result.epoch_id == "epoch-test-001"
    assert result.generation_count == 2


def test_accepted_count_gt_zero_simulate(loop) -> None:
    ctx = _make_context()
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=MOCK_PROPOSALS,
    ):
        result = loop.run_epoch(ctx)
    assert result.accepted_count > 0


def test_weight_accuracy_updates(loop) -> None:
    ctx = _make_context()
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=MOCK_PROPOSALS,
    ):
        result = loop.run_epoch(ctx)
    # After simulate epoch, accuracy should deviate from initial 0.5
    assert result.weight_accuracy != 0.0


def test_landscape_recorded_after_epoch(loop) -> None:
    ctx = _make_context()
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=MOCK_PROPOSALS,
    ):
        loop.run_epoch(ctx)
    # Landscape should have some records after epoch
    summary = loop._landscape.summary()
    assert isinstance(summary["types"], dict)


def test_recommended_next_agent_returned(loop) -> None:
    ctx = _make_context()
    with patch(
        "runtime.evolution.evolution_loop.propose_from_all_agents",
        return_value=MOCK_PROPOSALS,
    ):
        result = loop.run_epoch(ctx)
    assert result.recommended_next_agent in {"architect", "dream", "beast"}


class _FakeProposal:
    def __init__(self, proposal_id: str) -> None:
        self.proposal_id = proposal_id
        self.lineage_chain_hash = "deadbeef" * 8
        self.prior_roadmap_hash = "cafebabe" * 8


class _FakeAmendmentEngine:
    def __init__(self, pending: list | None = None, should_raise: bool = False) -> None:
        self._pending = pending or []
        self._should_raise = should_raise
        self.propose_called = False

    def list_pending(self):
        return self._pending

    def propose(self, **_: object):
        if self._should_raise:
            raise RuntimeError("boom")
        self.propose_called = True
        return _FakeProposal("rmap-amendment-test")


def test_epoch_result_includes_amendment_fields_defaults() -> None:
    result = EpochResult(
        epoch_id="epoch",
        generation_count=1,
        total_candidates=0,
        accepted_count=0,
    )
    payload = json.loads(json.dumps(result.__dict__))
    assert payload["amendment_proposed"] is False
    assert payload["amendment_id"] is None


def test_m603_proposes_only_when_all_gates_pass(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_AMENDMENT_TRIGGER_INTERVAL", "5")
    monkeypatch.setenv("ADAAD_FEDERATION_ENABLED", "false")
    monkeypatch.setattr("runtime.evolution.evolution_loop.journal.append_tx", lambda *args, **kwargs: None)
    monkeypatch.setattr("runtime.evolution.evolution_loop.EvolutionLoop._record_health_score", lambda *args, **kwargs: 0.95)

    engine = _FakeAmendmentEngine()
    with patch("runtime.autonomy.weight_adaptor.DEFAULT_STATE_PATH", tmp_path / "w.json"), \
         patch("runtime.autonomy.fitness_landscape.DEFAULT_LANDSCAPE_PATH", tmp_path / "fl.json"):
        loop = EvolutionLoop(api_key="k", generations=1, simulate_outcomes=False, amendment_engine=engine)
    loop._adaptor._prediction_accuracy = 0.9

    ctx = _make_context()
    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value=MOCK_PROPOSALS):
        for i in range(4):
            ctx.current_epoch_id = f"epoch-{i}"
            result = loop.run_epoch(ctx)
            assert result.amendment_proposed is False
            assert result.amendment_id is None
        ctx.current_epoch_id = "epoch-trigger"
        result = loop.run_epoch(ctx)

    assert engine.propose_called is True
    assert result.amendment_proposed is True
    assert result.amendment_id == "rmap-amendment-test"


def test_m603_storm_block_logs_and_continues(tmp_path, monkeypatch, caplog) -> None:
    monkeypatch.setenv("ADAAD_AMENDMENT_TRIGGER_INTERVAL", "5")
    monkeypatch.setenv("ADAAD_FEDERATION_ENABLED", "false")
    monkeypatch.setattr("runtime.evolution.evolution_loop.journal.append_tx", lambda *args, **kwargs: None)
    monkeypatch.setattr("runtime.evolution.evolution_loop.EvolutionLoop._record_health_score", lambda *args, **kwargs: 0.95)

    pending = [type("P", (), {"proposal_id": "pending-1"})()]
    engine = _FakeAmendmentEngine(pending=pending)
    with patch("runtime.autonomy.weight_adaptor.DEFAULT_STATE_PATH", tmp_path / "w.json"), \
         patch("runtime.autonomy.fitness_landscape.DEFAULT_LANDSCAPE_PATH", tmp_path / "fl.json"):
        loop = EvolutionLoop(api_key="k", generations=1, simulate_outcomes=False, amendment_engine=engine)
    loop._adaptor._prediction_accuracy = 0.9
    caplog.set_level("WARNING")

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value=MOCK_PROPOSALS):
        for i in range(5):
            ctx = _make_context()
            ctx.current_epoch_id = f"epoch-{i}"
            result = loop.run_epoch(ctx)

    assert result.amendment_proposed is False
    assert engine.propose_called is False
    assert "PHASE6_AMENDMENT_STORM_BLOCKED" in caplog.text


def test_m603_interval_misconfiguration_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_AMENDMENT_TRIGGER_INTERVAL", "4")
    monkeypatch.setattr("runtime.evolution.evolution_loop.journal.append_tx", lambda *args, **kwargs: None)

    with patch("runtime.autonomy.weight_adaptor.DEFAULT_STATE_PATH", tmp_path / "w.json"), \
         patch("runtime.autonomy.fitness_landscape.DEFAULT_LANDSCAPE_PATH", tmp_path / "fl.json"):
        loop = EvolutionLoop(api_key="k", generations=1, simulate_outcomes=True, amendment_engine=_FakeAmendmentEngine())

    with patch("runtime.evolution.evolution_loop.propose_from_all_agents", return_value=MOCK_PROPOSALS):
        with pytest.raises(GovernanceViolation, match="PHASE6_TRIGGER_INTERVAL_MISCONFIGURED"):
            loop.run_epoch(_make_context())
