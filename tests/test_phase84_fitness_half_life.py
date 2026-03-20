# SPDX-License-Identifier: Apache-2.0
"""Phase 84 — Temporal Fitness Half-Life Tests.

Tests ID: T84-TFHL-NN

Invariants under test:
  TFHL-0          Decay re-evaluation is read-only on historical records.
  TFHL-DET-0      Identical inputs → identical vectors, scores, digests.
  TFHL-DECAY-0    Decay model: adjusted = recorded × exp(-k × drift).
  TFHL-ALERT-0    FitnessDecayEvent emitted when adjusted < threshold.
  TFHL-ADVISORY-0 Module never imports or invokes GovernanceGate.
  TFHL-IMM-0      CodebaseStateVector is immutable.
"""

from __future__ import annotations

import json
import math
import pathlib
import tempfile
from typing import Any, Dict

import pytest

from runtime.evolution.codebase_state_vector import (
    CodebaseStateVector,
    FileSnapshot,
    _source_digest,
    _count_nodes,
    _cyclomatic,
)
from runtime.evolution.fitness_decay_scorer import (
    FitnessDecayScorer,
    FitnessDecayResult,
    FitnessRecord,
    DECAY_ALERT_THRESHOLD,
    DECAY_RATE_CONSTANT,
    HALF_LIFE_EPOCHS_DEFAULT,
    _adjusted_score,
    _decay_factor,
)
from runtime.evolution.lineage_v2 import LineageLedgerV2

pytestmark = pytest.mark.phase84

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SRC_A = "x = 1\ndef f():\n    return x\n"
SRC_B = "import os\nx = 1\ndef f():\n    if x:\n        return x\n    return None\n"
SRC_C = "x = 2\ndef f():\n    return x * 2\n"  # similar to A, slight drift


def _vec(sources: Dict[str, str]) -> CodebaseStateVector:
    return CodebaseStateVector.from_sources(sources)


def _ledger(tmp: pathlib.Path) -> LineageLedgerV2:
    return LineageLedgerV2(ledger_path=tmp / "ledger.jsonl")


def _record(score=0.85, sources=None) -> FitnessRecord:
    v = _vec(sources or {"main.py": SRC_A})
    return FitnessRecord.create("cand-1", "epoch-1", score, v)


# ===========================================================================
# CodebaseStateVector — construction and determinism
# ===========================================================================


def test_T84_TFHL_01_vector_deterministic():
    """T84-TFHL-01: TFHL-DET-0 — identical sources → identical vector_id."""
    v1 = _vec({"f.py": SRC_A})
    v2 = _vec({"f.py": SRC_A})
    assert v1.vector_id == v2.vector_id
    assert v1.region_digest == v2.region_digest


def test_T84_TFHL_02_different_source_different_vector():
    """T84-TFHL-02: TFHL-DET-0 — different source → different vector_id."""
    v1 = _vec({"f.py": SRC_A})
    v2 = _vec({"f.py": SRC_B})
    assert v1.vector_id != v2.vector_id


def test_T84_TFHL_03_vector_immutable():
    """T84-TFHL-03: TFHL-IMM-0 — CodebaseStateVector is frozen: direct setattr raises."""
    from dataclasses import FrozenInstanceError
    v = _vec({"f.py": SRC_A})
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        v.vector_id = "hacked"


def test_T84_TFHL_04_empty_sources_valid():
    """T84-TFHL-04: Empty source dict → valid zero vector."""
    v = _vec({})
    assert v.file_count == 0
    assert v.total_nodes == 0


def test_T84_TFHL_05_file_snapshots_sorted_by_path():
    """T84-TFHL-05: TFHL-DET-0 — file_snapshots sorted by path."""
    v = _vec({"z.py": SRC_A, "a.py": SRC_B, "m.py": SRC_C})
    paths = [s.path for s in v.file_snapshots]
    assert paths == sorted(paths)


def test_T84_TFHL_06_vector_roundtrip():
    """T84-TFHL-06: CodebaseStateVector to_dict/from_dict round-trip."""
    v = _vec({"f.py": SRC_A, "g.py": SRC_B})
    v2 = CodebaseStateVector.from_dict(v.to_dict())
    assert v.vector_id == v2.vector_id
    assert v.region_digest == v2.region_digest
    assert v.total_nodes == v2.total_nodes


def test_T84_TFHL_07_source_digest_deterministic():
    """T84-TFHL-07: TFHL-DET-0 — _source_digest identical for same source."""
    assert _source_digest(SRC_A) == _source_digest(SRC_A)
    assert _source_digest(SRC_A) != _source_digest(SRC_B)


# ===========================================================================
# drift_from
# ===========================================================================


def test_T84_TFHL_08_zero_drift_identical_vectors():
    """T84-TFHL-08: drift_from returns 0.0 for identical vectors."""
    v = _vec({"f.py": SRC_A})
    assert v.drift_from(v) == 0.0


def test_T84_TFHL_09_positive_drift_for_changed_source():
    """T84-TFHL-09: drift_from > 0 when source changes."""
    v1 = _vec({"f.py": SRC_A})
    v2 = _vec({"f.py": SRC_B})
    assert v1.drift_from(v2) > 0.0


def test_T84_TFHL_10_drift_bounded_0_1():
    """T84-TFHL-10: drift_from is always in [0.0, 1.0]."""
    v1 = _vec({"f.py": SRC_A})
    v2 = _vec({"g.py": SRC_B})  # completely different files
    drift = v1.drift_from(v2)
    assert 0.0 <= drift <= 1.0


def test_T84_TFHL_11_drift_deterministic():
    """T84-TFHL-11: TFHL-DET-0 — drift_from is deterministic."""
    v1 = _vec({"f.py": SRC_A})
    v2 = _vec({"f.py": SRC_B})
    assert v1.drift_from(v2) == v1.drift_from(v2)


def test_T84_TFHL_12_slight_change_small_drift():
    """T84-TFHL-12: Minor source change → small drift, not maximum."""
    v1 = _vec({"f.py": SRC_A})
    v2 = _vec({"f.py": SRC_C})  # SRC_C is a slight variation of SRC_A
    drift = v1.drift_from(v2)
    assert 0.0 < drift < 1.0


# ===========================================================================
# Decay model — TFHL-DECAY-0
# ===========================================================================


def test_T84_TFHL_13_decay_factor_zero_drift():
    """T84-TFHL-13: TFHL-DECAY-0 — drift=0 → decay_factor=1.0 (no decay)."""
    assert _decay_factor(0.0) == pytest.approx(1.0)


def test_T84_TFHL_14_decay_factor_full_drift():
    """T84-TFHL-14: TFHL-DECAY-0 — drift=1.0 → decay_factor=exp(-k)."""
    k = DECAY_RATE_CONSTANT
    expected = math.exp(-k)
    assert _decay_factor(1.0) == pytest.approx(expected, abs=1e-9)


def test_T84_TFHL_15_adjusted_score_no_decay():
    """T84-TFHL-15: TFHL-DECAY-0 — zero drift → adjusted = recorded."""
    assert _adjusted_score(0.85, 0.0) == pytest.approx(0.85)


def test_T84_TFHL_16_adjusted_score_decays_with_drift():
    """T84-TFHL-16: TFHL-DECAY-0 — positive drift reduces adjusted score."""
    assert _adjusted_score(0.9, 0.5) < 0.9


def test_T84_TFHL_17_adjusted_score_bounded():
    """T84-TFHL-17: TFHL-DECAY-0 — adjusted_score clamped to [0.0, 1.0]."""
    assert 0.0 <= _adjusted_score(1.0, 1.0) <= 1.0
    assert 0.0 <= _adjusted_score(0.0, 0.5) <= 1.0


def test_T84_TFHL_18_adjusted_score_deterministic():
    """T84-TFHL-18: TFHL-DET-0 — identical inputs → identical adjusted score."""
    s1 = _adjusted_score(0.8, 0.3)
    s2 = _adjusted_score(0.8, 0.3)
    assert s1 == s2


# ===========================================================================
# FitnessRecord
# ===========================================================================


def test_T84_TFHL_19_fitness_record_roundtrip():
    """T84-TFHL-19: FitnessRecord to_dict/from_dict round-trip."""
    r = _record(score=0.75)
    r2 = FitnessRecord.from_dict(r.to_dict())
    assert r.record_id == r2.record_id
    assert r.recorded_score == r2.recorded_score


def test_T84_TFHL_20_record_id_deterministic():
    """T84-TFHL-20: TFHL-DET-0 — same candidate_id + epoch_id → same record_id."""
    v = _vec({"f.py": SRC_A})
    r1 = FitnessRecord.create("cand-x", "epoch-y", 0.8, v)
    r2 = FitnessRecord.create("cand-x", "epoch-y", 0.8, v)
    assert r1.record_id == r2.record_id


# ===========================================================================
# FitnessDecayScorer
# ===========================================================================


def test_T84_TFHL_21_no_decay_on_identical_vectors():
    """T84-TFHL-21: No drift → adjusted_score ≈ recorded_score."""
    record = _record(score=0.85)
    current = _vec({"main.py": SRC_A})
    scorer = FitnessDecayScorer()
    result = scorer.evaluate(record, current)
    assert result.adjusted_score == pytest.approx(0.85, abs=1e-6)
    assert result.alert_triggered is False


def test_T84_TFHL_22_alert_triggered_on_high_drift():
    """T84-TFHL-22: TFHL-ALERT-0 — high drift triggers alert."""
    record = _record(score=0.85, sources={"main.py": SRC_A})
    current = _vec({"completely_different.py": SRC_B})
    scorer = FitnessDecayScorer(alert_threshold=DECAY_ALERT_THRESHOLD)
    result = scorer.evaluate(record, current)
    assert result.alert_triggered is True
    assert result.adjusted_score < DECAY_ALERT_THRESHOLD


def test_T84_TFHL_23_decay_event_written_to_ledger():
    """T84-TFHL-23: TFHL-ALERT-0 — FitnessDecayEvent written to ledger on alert."""
    with tempfile.TemporaryDirectory() as td:
        ledger = _ledger(pathlib.Path(td))
        record = _record(score=0.85, sources={"main.py": SRC_A})
        current = _vec({"other.py": SRC_B})
        scorer = FitnessDecayScorer(ledger=ledger)
        result = scorer.evaluate(record, current)
        if result.alert_triggered:
            lines = ledger.ledger_path.read_text().strip().splitlines()
            events = [json.loads(l) for l in lines]
            assert any(e["type"] == "FitnessDecayEvent" for e in events)


def test_T84_TFHL_24_no_ledger_no_crash():
    """T84-TFHL-24: TFHL-0 — scorer works fine without ledger injected."""
    record = _record(score=0.85, sources={"main.py": SRC_A})
    current = _vec({"other.py": SRC_B})
    scorer = FitnessDecayScorer()  # no ledger
    result = scorer.evaluate(record, current)
    assert isinstance(result, FitnessDecayResult)


def test_T84_TFHL_25_batch_sorted_by_adjusted_score():
    """T84-TFHL-25: TFHL-DET-0 — batch results sorted ascending by adjusted_score."""
    current = _vec({"other.py": SRC_B})
    records = [
        FitnessRecord.create("c1", "e1", 0.9, _vec({"a.py": SRC_A})),
        FitnessRecord.create("c2", "e2", 0.5, _vec({"a.py": SRC_A})),
        FitnessRecord.create("c3", "e3", 0.7, _vec({"a.py": SRC_A})),
    ]
    scorer = FitnessDecayScorer()
    results = scorer.evaluate_batch(records, current)
    scores = [r.adjusted_score for r in results]
    assert scores == sorted(scores)


def test_T84_TFHL_26_advisory_no_gate_import():
    """T84-TFHL-26: TFHL-ADVISORY-0 — fitness_decay_scorer never imports GovernanceGate."""
    import runtime.evolution.fitness_decay_scorer as m
    src = open(m.__file__).read()
    assert "GovernanceGate(" not in src
    assert "from runtime.governance.gate" not in src
    assert "import GovernanceGate" not in src
