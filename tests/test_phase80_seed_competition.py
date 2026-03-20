# SPDX-License-Identifier: Apache-2.0
"""Phase 80 — Multi-Seed Competitive Epoch Tests.

Tests ID convention: T80-COMP-NN

Invariants under test:
  SEED-COMP-0    No seed promoted without ranking all candidates first.
  SEED-RANK-0    Fitness ranking is deterministic (equal inputs → equal ordering).
  COMP-GOV-0     GovernanceGate evaluates all candidates before winner selected.
  COMP-LEDGER-0  SeedCompetitionEpochEvent written to ledger before any return.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from runtime.seed_competition import (
    CompetitionResult,
    SeedCandidate,
    SeedCompetitionOrchestrator,
    _competition_digest,
    _rank_candidates,
)
from runtime.evolution.lineage_v2 import LineageLedgerV2, SeedCompetitionEpochEvent
from runtime.fitness_pipeline import rank_seeds_by_fitness

pytestmark = pytest.mark.phase80


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(correctness: float = 1.0, efficiency: float = 0.8, **kw) -> Dict[str, Any]:
    base = {
        "epoch_id": "test-epoch",
        "mutation_tier": "low",
        "correctness_score": correctness,
        "efficiency_score": efficiency,
        "policy_compliance_score": 0.9,
        "goal_alignment_score": 0.7,
        "simulated_market_score": 0.5,
    }
    base.update(kw)
    return base


def _candidate(cid: str, correctness: float = 1.0) -> SeedCandidate:
    return SeedCandidate(
        candidate_id=cid,
        fitness_context=_ctx(correctness=correctness),
        metadata={"origin": "test"},
    )


def _always_pass(cid: str, meta: Dict) -> str:  # noqa: ARG001
    return "pass"


def _always_fail(cid: str, meta: Dict) -> str:  # noqa: ARG001
    return "fail"


def _fail_first(call_order: List[str]):
    """Gate that fails the first candidate evaluated, passes rest."""
    called: List[str] = []

    def _fn(cid: str, meta: Dict) -> str:  # noqa: ARG001
        called.append(cid)
        call_order[:] = called[:]
        return "fail" if len(called) == 1 else "pass"

    return _fn


def _make_ledger(tmp: pathlib.Path) -> LineageLedgerV2:
    return LineageLedgerV2(ledger_path=tmp / "ledger.jsonl")


def _make_orch(tmp: pathlib.Path, gate_fn=None) -> SeedCompetitionOrchestrator:
    return SeedCompetitionOrchestrator(
        ledger=_make_ledger(tmp),
        gate_fn=gate_fn or _always_pass,
        epoch_id_factory=lambda: "epoch-fixed-001",
    )


# ---------------------------------------------------------------------------
# T80-COMP-01: Basic 2-candidate epoch completes and returns winner
# ---------------------------------------------------------------------------


def test_T80_COMP_01_basic_two_candidate_epoch():
    """T80-COMP-01: Two-candidate epoch returns highest-scoring winner."""
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        orch = _make_orch(tmp)
        result = orch.run_epoch([_candidate("alpha", 1.0), _candidate("beta", 0.5)])
        assert isinstance(result, CompetitionResult)
        assert result.gate_verdict == "pass"
        assert result.winner_id == "alpha"  # higher correctness score
        assert len(result.ranked_ids) == 2


# ---------------------------------------------------------------------------
# T80-COMP-02: SEED-RANK-0 — determinism: same inputs → same ranking
# ---------------------------------------------------------------------------


def test_T80_COMP_02_ranking_determinism():
    """T80-COMP-02: SEED-RANK-0 — identical inputs produce identical rankings."""
    scores = {"alpha": 0.9, "beta": 0.7, "gamma": 0.8}
    r1 = _rank_candidates(scores)
    r2 = _rank_candidates(scores)
    assert r1 == r2
    assert r1 == ["alpha", "gamma", "beta"]


# ---------------------------------------------------------------------------
# T80-COMP-03: SEED-RANK-0 — tie-breaking is lexicographic by candidate_id
# ---------------------------------------------------------------------------


def test_T80_COMP_03_tie_breaking_lexicographic():
    """T80-COMP-03: SEED-RANK-0 — ties broken by ascending candidate_id."""
    scores = {"charlie": 0.5, "alpha": 0.5, "beta": 0.5}
    ranked = _rank_candidates(scores)
    assert ranked == ["alpha", "beta", "charlie"]


# ---------------------------------------------------------------------------
# T80-COMP-04: COMP-LEDGER-0 — ledger entry written before CompetitionResult returned
# ---------------------------------------------------------------------------


def test_T80_COMP_04_ledger_written_before_return():
    """T80-COMP-04: COMP-LEDGER-0 — ledger entry exists after run_epoch."""
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ledger = _make_ledger(tmp)
        orch = SeedCompetitionOrchestrator(
            ledger=ledger,
            gate_fn=_always_pass,
            epoch_id_factory=lambda: "epoch-ledger-test",
        )
        orch.run_epoch([_candidate("x", 1.0)])
        # Ledger file must exist and contain SeedCompetitionEpochEvent
        assert ledger.ledger_path.exists()
        entries = ledger.ledger_path.read_text().strip().splitlines()
        events = [json.loads(e) for e in entries]
        types = [e["type"] for e in events]
        assert "SeedCompetitionEpochEvent" in types


# ---------------------------------------------------------------------------
# T80-COMP-05: COMP-GOV-0 — gate is called for ALL candidates
# ---------------------------------------------------------------------------


def test_T80_COMP_05_gate_called_for_all_candidates():
    """T80-COMP-05: COMP-GOV-0 — gate evaluated for every candidate."""
    evaluated: List[str] = []

    def _tracking_gate(cid: str, meta: Dict) -> str:  # noqa: ARG001
        evaluated.append(cid)
        return "pass"

    with tempfile.TemporaryDirectory() as td:
        candidates = [_candidate("a"), _candidate("b"), _candidate("c")]
        orch = _make_orch(pathlib.Path(td), gate_fn=_tracking_gate)
        orch.run_epoch(candidates)
        # All 3 candidates must have been evaluated by gate
        assert set(evaluated) == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# T80-COMP-06: SEED-COMP-0 — empty candidates raises ValueError
# ---------------------------------------------------------------------------


def test_T80_COMP_06_empty_candidates_raises():
    """T80-COMP-06: SEED-COMP-0 — empty candidates list raises ValueError."""
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(pathlib.Path(td))
        with pytest.raises(ValueError, match="SEED-COMP-0"):
            orch.run_epoch([])


# ---------------------------------------------------------------------------
# T80-COMP-07: All candidates fail gate → ledger written, RuntimeError raised
# ---------------------------------------------------------------------------


def test_T80_COMP_07_all_fail_gate_writes_ledger_then_raises():
    """T80-COMP-07: All gate failures → COMP-LEDGER-0 honoured then RuntimeError."""
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ledger = _make_ledger(tmp)
        orch = SeedCompetitionOrchestrator(
            ledger=ledger,
            gate_fn=_always_fail,
            epoch_id_factory=lambda: "epoch-all-fail",
        )
        with pytest.raises(RuntimeError, match="COMP-GOV-0"):
            orch.run_epoch([_candidate("x"), _candidate("y")])
        # Ledger entry must still have been written (COMP-LEDGER-0)
        assert ledger.ledger_path.exists()
        events = [json.loads(l) for l in ledger.ledger_path.read_text().strip().splitlines()]
        assert any(e["type"] == "SeedCompetitionEpochEvent" for e in events)


# ---------------------------------------------------------------------------
# T80-COMP-08: digest is deterministic (SEED-RANK-0)
# ---------------------------------------------------------------------------


def test_T80_COMP_08_competition_digest_determinism():
    """T80-COMP-08: competition_digest identical for identical inputs."""
    ids = ["alpha", "beta", "gamma"]
    scores = {"alpha": 0.9, "beta": 0.7, "gamma": 0.8}
    d1 = _competition_digest(ids, scores)
    d2 = _competition_digest(ids, scores)
    assert d1 == d2
    assert len(d1) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# T80-COMP-09: digest changes when scores change
# ---------------------------------------------------------------------------


def test_T80_COMP_09_digest_differs_on_score_change():
    """T80-COMP-09: digest detects score mutation."""
    ids = ["alpha", "beta"]
    d1 = _competition_digest(ids, {"alpha": 0.9, "beta": 0.7})
    d2 = _competition_digest(ids, {"alpha": 0.9, "beta": 0.8})
    assert d1 != d2


# ---------------------------------------------------------------------------
# T80-COMP-10: winner is highest-ranked gate passer, not just highest scorer
# ---------------------------------------------------------------------------


def test_T80_COMP_10_winner_is_highest_ranked_passer():
    """T80-COMP-10: When top-scorer fails gate, next passer wins."""
    call_order: List[str] = []
    gate = _fail_first(call_order)

    with tempfile.TemporaryDirectory() as td:
        orch = SeedCompetitionOrchestrator(
            ledger=_make_ledger(pathlib.Path(td)),
            gate_fn=gate,
            epoch_id_factory=lambda: "epoch-skip-top",
        )
        # alpha scores higher, will be evaluated first, gate will fail it
        result = orch.run_epoch([_candidate("alpha", 1.0), _candidate("beta", 0.5)])
        assert result.winner_id == "beta"
        assert result.gate_verdict == "pass"


# ---------------------------------------------------------------------------
# T80-COMP-11: SeedCompetitionEpochEvent round-trip serialisation
# ---------------------------------------------------------------------------


def test_T80_COMP_11_event_roundtrip():
    """T80-COMP-11: SeedCompetitionEpochEvent to_dict / from_dict round-trip."""
    ev = SeedCompetitionEpochEvent(
        epoch_id="e-001",
        candidate_ids=["a", "b"],
        ranked_ids=["a", "b"],
        winner_id="a",
        fitness_scores={"a": 0.9, "b": 0.7},
        gate_verdict="pass",
        competition_digest="abc123",
        phase=80,
        version="9.14.0",
    )
    d = ev.to_dict()
    ev2 = SeedCompetitionEpochEvent.from_dict(d)
    assert ev == ev2


# ---------------------------------------------------------------------------
# T80-COMP-12: rank_seeds_by_fitness pipeline surface (SEED-RANK-0)
# ---------------------------------------------------------------------------


def test_T80_COMP_12_rank_seeds_by_fitness_ordering():
    """T80-COMP-12: rank_seeds_by_fitness returns descending order."""
    contexts = {
        "high": _ctx(correctness=1.0),
        "mid": _ctx(correctness=0.6),
        "low": _ctx(correctness=0.2),
    }
    ranked = rank_seeds_by_fitness(contexts)
    ids = [r[0] for r in ranked]
    assert ids[0] == "high"
    assert ids[-1] == "low"


# ---------------------------------------------------------------------------
# T80-COMP-13: rank_seeds_by_fitness determinism
# ---------------------------------------------------------------------------


def test_T80_COMP_13_rank_seeds_determinism():
    """T80-COMP-13: rank_seeds_by_fitness is deterministic over repeated calls."""
    contexts = {
        "a": _ctx(correctness=0.9),
        "b": _ctx(correctness=0.7),
        "c": _ctx(correctness=0.8),
    }
    r1 = rank_seeds_by_fitness(contexts)
    r2 = rank_seeds_by_fitness(contexts)
    assert r1 == r2


# ---------------------------------------------------------------------------
# T80-COMP-14: rank_seeds_by_fitness raises on empty input
# ---------------------------------------------------------------------------


def test_T80_COMP_14_rank_seeds_empty_raises():
    """T80-COMP-14: rank_seeds_by_fitness raises ValueError on empty input."""
    with pytest.raises(ValueError, match="SEED-RANK-0"):
        rank_seeds_by_fitness({})


# ---------------------------------------------------------------------------
# T80-COMP-15: CompetitionResult contains correct structure
# ---------------------------------------------------------------------------


def test_T80_COMP_15_competition_result_structure():
    """T80-COMP-15: CompetitionResult has all required fields."""
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(pathlib.Path(td))
        result = orch.run_epoch([_candidate("solo", 0.75)])
        assert result.epoch_id == "epoch-fixed-001"
        assert result.winner_id == "solo"
        assert isinstance(result.fitness_scores, dict)
        assert "solo" in result.fitness_scores
        assert isinstance(result.ranked_ids, list)
        assert isinstance(result.competition_digest, str)
        assert len(result.competition_digest) == 64


# ---------------------------------------------------------------------------
# T80-COMP-16: Single candidate epoch succeeds (edge case)
# ---------------------------------------------------------------------------


def test_T80_COMP_16_single_candidate_succeeds():
    """T80-COMP-16: Single candidate still enforces gate + ledger."""
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ledger = _make_ledger(tmp)
        orch = SeedCompetitionOrchestrator(
            ledger=ledger,
            gate_fn=_always_pass,
            epoch_id_factory=lambda: "epoch-solo",
        )
        result = orch.run_epoch([_candidate("only-one")])
        assert result.winner_id == "only-one"
        assert result.gate_verdict == "pass"
        # Ledger written
        assert any(
            json.loads(l)["type"] == "SeedCompetitionEpochEvent"
            for l in ledger.ledger_path.read_text().strip().splitlines()
        )


# ---------------------------------------------------------------------------
# T80-COMP-17: ledger entry contains competition_digest field
# ---------------------------------------------------------------------------


def test_T80_COMP_17_ledger_entry_has_digest():
    """T80-COMP-17: COMP-LEDGER-0 — ledger entry embeds competition_digest."""
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ledger = _make_ledger(tmp)
        orch = SeedCompetitionOrchestrator(
            ledger=ledger,
            gate_fn=_always_pass,
            epoch_id_factory=lambda: "epoch-digest-check",
        )
        result = orch.run_epoch([_candidate("a", 0.9), _candidate("b", 0.7)])
        events = [
            json.loads(l)
            for l in ledger.ledger_path.read_text().strip().splitlines()
            if json.loads(l)["type"] == "SeedCompetitionEpochEvent"
        ]
        assert events
        payload = events[-1]["payload"]
        assert payload["competition_digest"] == result.competition_digest


# ---------------------------------------------------------------------------
# T80-COMP-18: ledger entry contains phase=80
# ---------------------------------------------------------------------------


def test_T80_COMP_18_ledger_entry_phase_80():
    """T80-COMP-18: COMP-LEDGER-0 — ledger entry records phase=80."""
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ledger = _make_ledger(tmp)
        orch = SeedCompetitionOrchestrator(
            ledger=ledger,
            gate_fn=_always_pass,
            epoch_id_factory=lambda: "epoch-phase-check",
        )
        orch.run_epoch([_candidate("p")])
        events = [
            json.loads(l)
            for l in ledger.ledger_path.read_text().strip().splitlines()
            if json.loads(l)["type"] == "SeedCompetitionEpochEvent"
        ]
        assert events[-1]["payload"]["phase"] == 80


# ---------------------------------------------------------------------------
# T80-COMP-19: 5-candidate ranking order is stable across calls
# ---------------------------------------------------------------------------


def test_T80_COMP_19_five_candidate_ranking_stable():
    """T80-COMP-19: 5-candidate ranking is stable (SEED-RANK-0)."""
    scores = {"e": 0.1, "b": 0.7, "d": 0.3, "a": 0.9, "c": 0.5}
    r1 = _rank_candidates(scores)
    r2 = _rank_candidates(scores)
    r3 = _rank_candidates(scores)
    assert r1 == r2 == r3
    assert r1 == ["a", "b", "c", "d", "e"]


# ---------------------------------------------------------------------------
# T80-COMP-20: COMP-GOV-0 — gate is evaluated in ranked order
# ---------------------------------------------------------------------------


def test_T80_COMP_20_gate_evaluated_in_ranked_order():
    """T80-COMP-20: COMP-GOV-0 — gate called in descending fitness order."""
    call_order: List[str] = []

    def _tracking(cid: str, meta: Dict) -> str:  # noqa: ARG001
        call_order.append(cid)
        return "pass"

    with tempfile.TemporaryDirectory() as td:
        orch = SeedCompetitionOrchestrator(
            ledger=_make_ledger(pathlib.Path(td)),
            gate_fn=_tracking,
            epoch_id_factory=lambda: "epoch-order",
        )
        orch.run_epoch([
            _candidate("low", 0.3),
            _candidate("high", 0.9),
            _candidate("mid", 0.6),
        ])
    assert call_order == ["high", "mid", "low"]


# ---------------------------------------------------------------------------
# T80-COMP-21: SeedCompetitionEpochEvent.candidate_ids is sorted
# ---------------------------------------------------------------------------


def test_T80_COMP_21_epoch_event_candidate_ids_sorted():
    """T80-COMP-21: SeedCompetitionEpochEvent.candidate_ids are stored sorted."""
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ledger = _make_ledger(tmp)
        orch = SeedCompetitionOrchestrator(
            ledger=ledger,
            gate_fn=_always_pass,
            epoch_id_factory=lambda: "epoch-sorted",
        )
        orch.run_epoch([_candidate("z"), _candidate("a"), _candidate("m")])
        events = [
            json.loads(l)
            for l in ledger.ledger_path.read_text().strip().splitlines()
            if json.loads(l)["type"] == "SeedCompetitionEpochEvent"
        ]
        assert events[-1]["payload"]["candidate_ids"] == ["a", "m", "z"]


# ---------------------------------------------------------------------------
# T80-COMP-22: deferred gate verdict propagates to CompetitionResult
# ---------------------------------------------------------------------------


def test_T80_COMP_22_deferred_gate_verdict():
    """T80-COMP-22: Deferred gate verdict surfaces in CompetitionResult."""
    def _deferred(cid: str, meta: Dict) -> str:  # noqa: ARG001
        return "deferred"

    with tempfile.TemporaryDirectory() as td:
        orch = SeedCompetitionOrchestrator(
            ledger=_make_ledger(pathlib.Path(td)),
            gate_fn=_deferred,
            epoch_id_factory=lambda: "epoch-deferred",
        )
        result = orch.run_epoch([_candidate("d1"), _candidate("d2")])
        assert result.gate_verdict == "deferred"


# ---------------------------------------------------------------------------
# T80-COMP-23: rank_seeds_by_fitness tie-breaking is deterministic
# ---------------------------------------------------------------------------


def test_T80_COMP_23_rank_seeds_tie_breaking():
    """T80-COMP-23: rank_seeds_by_fitness ties broken by ascending candidate_id."""
    # Same context → same scores; ordering should be lexicographic by id
    ctx = _ctx(correctness=0.5)
    contexts = {"charlie": ctx, "alpha": ctx, "beta": ctx}
    # Run twice to confirm stability
    r1 = rank_seeds_by_fitness(contexts)
    r2 = rank_seeds_by_fitness(contexts)
    assert r1 == r2
    ids1 = [r[0] for r in r1]
    assert ids1 == sorted(ids1)  # lexicographic ascending for ties


# ---------------------------------------------------------------------------
# T80-COMP-24: SeedCompetitionOrchestrator default construction succeeds
# ---------------------------------------------------------------------------


def test_T80_COMP_24_default_construction():
    """T80-COMP-24: Orchestrator can be constructed with all defaults (no args)."""
    # This should not raise even without injecting deps
    orch = SeedCompetitionOrchestrator()
    assert orch is not None
