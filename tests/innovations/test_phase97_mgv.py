# SPDX-License-Identifier: Apache-2.0
"""T97-MGV-01..30 — Phase 97 INNOV-12 Mutation Genealogy Visualization acceptance tests.

Invariants under test:
  MGV-0        — _load() never raises; corrupt lines silently skipped
  MGV-DETERM-0 — PropertyInheritanceVector.digest is deterministic (no RNG/datetime/uuid4)
  MGV-PERSIST-0 — _persist() uses Path.open (not builtins.open); append-only
"""
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import pytest

from runtime.innovations30.mutation_genealogy import (
    MutationGenealogyAnalyzer,
    PropertyInheritanceVector,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def empty_analyzer(tmp_path):
    return MutationGenealogyAnalyzer(tmp_path / "genealogy.jsonl")


@pytest.fixture()
def parent_scores():
    return {"correctness": 0.60, "efficiency": 0.50, "governance": 0.70}


@pytest.fixture()
def child_scores():
    return {"correctness": 0.75, "efficiency": 0.65, "governance": 0.80, "fitness_delta": 0.10}


# ---------------------------------------------------------------------------
# MGV-0 — fail-open load (T97-MGV-01..03)
# ---------------------------------------------------------------------------

def test_mgv_01_load_empty_file(tmp_path):
    """MGV-0: empty ledger loads without error."""
    path = tmp_path / "genealogy.jsonl"
    path.write_text("")
    a = MutationGenealogyAnalyzer(path)
    assert a._vectors == []


def test_mgv_02_load_corrupt_line(tmp_path):
    """MGV-0: corrupt JSON line is silently skipped."""
    path = tmp_path / "genealogy.jsonl"
    path.write_text("NOT_JSON\n")
    a = MutationGenealogyAnalyzer(path)
    assert a._vectors == []


def test_mgv_03_load_missing_file(tmp_path):
    """MGV-0: missing ledger file is not an error."""
    a = MutationGenealogyAnalyzer(tmp_path / "nonexistent.jsonl")
    assert a._vectors == []


# ---------------------------------------------------------------------------
# MGV-DETERM-0 — digest determinism (T97-MGV-04..08)
# ---------------------------------------------------------------------------

def test_mgv_04_persist_uses_path_open(tmp_path, parent_scores, child_scores):
    """MGV-PERSIST-0: _persist uses Path.open, not builtins.open — mock target verified."""
    a = MutationGenealogyAnalyzer(tmp_path / "genealogy.jsonl")
    with patch("runtime.innovations30.mutation_genealogy.Path.open",
               mock_open()) as mocked:
        v = PropertyInheritanceVector(
            parent_epoch="ep-A", child_epoch="ep-B",
            correctness_delta=0.10, efficiency_delta=0.05,
            governance_delta=0.08, fitness_delta=0.03,
        )
        a._persist(v)
        mocked.assert_called_once()


def test_mgv_05_digest_deterministic_same_inputs():
    """MGV-DETERM-0: identical inputs produce identical digest."""
    v1 = PropertyInheritanceVector("ep-A", "ep-B", 0.10, 0.05, 0.08, 0.03)
    v2 = PropertyInheritanceVector("ep-A", "ep-B", 0.10, 0.05, 0.08, 0.03)
    assert v1.digest == v2.digest


def test_mgv_06_digest_differs_on_different_epochs():
    """MGV-DETERM-0: differing parent epochs produce differing digests."""
    v1 = PropertyInheritanceVector("ep-A", "ep-B", 0.10, 0.05, 0.08, 0.03)
    v2 = PropertyInheritanceVector("ep-X", "ep-B", 0.10, 0.05, 0.08, 0.03)
    assert v1.digest != v2.digest


def test_mgv_07_digest_prefix():
    """MGV-DETERM-0: digest always prefixed sha256:."""
    v = PropertyInheritanceVector("ep-A", "ep-B", 0.10, 0.05, 0.08, 0.03)
    assert v.digest.startswith("sha256:")


def test_mgv_08_digest_length():
    """MGV-DETERM-0: digest suffix is 16 hex chars."""
    v = PropertyInheritanceVector("ep-A", "ep-B", 0.10, 0.05, 0.08, 0.03)
    assert len(v.digest) == len("sha256:") + 16


# ---------------------------------------------------------------------------
# productive_lineages — improvement threshold boundary (T97-MGV-09..14)
# ---------------------------------------------------------------------------

def test_mgv_09_productive_lineage_above_threshold(tmp_path, parent_scores, child_scores):
    """Epoch with mean improvement >= 0.05 is productive."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-B", parent_scores, child_scores)
    assert "ep-A" in a.productive_lineages()


def test_mgv_10_productive_lineage_below_threshold(tmp_path):
    """Epoch with mean improvement < 0.05 is not productive."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-B",
                          {"correctness": 0.9, "efficiency": 0.9, "governance": 0.9},
                          {"correctness": 0.9, "efficiency": 0.9, "governance": 0.9, "fitness_delta": 0.0})
    assert "ep-A" not in a.productive_lineages()


def test_mgv_11_productive_custom_threshold(tmp_path, parent_scores, child_scores):
    """Custom threshold is respected."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-B", parent_scores, child_scores)
    assert "ep-A" in a.productive_lineages(min_improvement=0.01)


def test_mgv_12_productive_empty_analyzer(tmp_path):
    """Empty analyzer returns empty productive list."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    assert a.productive_lineages() == []


def test_mgv_13_productive_multiple_children(tmp_path, parent_scores, child_scores):
    """Mean is computed across all children."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-B", parent_scores, child_scores)
    a.record_inheritance("ep-A", "ep-C", parent_scores, child_scores)
    assert "ep-A" in a.productive_lineages()


def test_mgv_14_productive_returns_list(tmp_path):
    """productive_lineages always returns a list."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    result = a.productive_lineages()
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# dead_end_epochs — child-never-parent set logic (T97-MGV-15..19)
# ---------------------------------------------------------------------------

def test_mgv_15_dead_end_single(tmp_path, parent_scores, child_scores):
    """ep-B is a dead end: child but never parent."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-B", parent_scores, child_scores)
    assert "ep-B" in a.dead_end_epochs()


def test_mgv_16_dead_end_not_parent(tmp_path, parent_scores, child_scores):
    """ep-A is not a dead end: it is a parent."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-B", parent_scores, child_scores)
    assert "ep-A" not in a.dead_end_epochs()


def test_mgv_17_dead_end_chain(tmp_path, parent_scores, child_scores):
    """ep-B graduates out of dead-end once it produces ep-C."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-B", parent_scores, child_scores)
    a.record_inheritance("ep-B", "ep-C", parent_scores, child_scores)
    assert "ep-B" not in a.dead_end_epochs()
    assert "ep-C" in a.dead_end_epochs()


def test_mgv_18_dead_end_empty(tmp_path):
    """Empty analyzer returns empty dead-end list."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    assert a.dead_end_epochs() == []


def test_mgv_19_dead_end_returns_list(tmp_path):
    """dead_end_epochs always returns a list."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    assert isinstance(a.dead_end_epochs(), list)


# ---------------------------------------------------------------------------
# evolutionary_direction — cumulative delta accumulation (T97-MGV-20..25)
# ---------------------------------------------------------------------------

def test_mgv_20_evolutionary_direction_basic(tmp_path, parent_scores, child_scores):
    """evolutionary_direction returns dict with expected keys."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-B", parent_scores, child_scores)
    direction = a.evolutionary_direction("ep-B")
    assert set(direction.keys()) == {"correctness", "efficiency", "governance", "fitness"}


def test_mgv_21_evolutionary_direction_unknown_epoch(tmp_path):
    """Unknown epoch returns empty dict."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    assert a.evolutionary_direction("ep-UNKNOWN") == {}


def test_mgv_22_evolutionary_direction_values_rounded(tmp_path, parent_scores, child_scores):
    """Values in direction dict are rounded to 4 decimal places."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-B", parent_scores, child_scores)
    for val in a.evolutionary_direction("ep-B").values():
        assert val == round(val, 4)


def test_mgv_23_evolutionary_direction_accumulates(tmp_path, parent_scores, child_scores):
    """Multiple parents to same child accumulate."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-C", parent_scores, child_scores)
    a.record_inheritance("ep-B", "ep-C", parent_scores, child_scores)
    direction = a.evolutionary_direction("ep-C")
    assert direction["correctness"] != 0


def test_mgv_24_evolutionary_direction_correctness_delta(tmp_path):
    """Correctness delta computed correctly."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    a.record_inheritance("ep-A", "ep-B",
                          {"correctness": 0.5, "efficiency": 0.5, "governance": 0.5},
                          {"correctness": 0.8, "efficiency": 0.5, "governance": 0.5, "fitness_delta": 0.0})
    direction = a.evolutionary_direction("ep-B")
    assert direction["correctness"] == pytest.approx(0.3, abs=1e-4)


def test_mgv_25_evolutionary_direction_returns_dict(tmp_path, parent_scores, child_scores):
    """evolutionary_direction always returns dict."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    assert isinstance(a.evolutionary_direction("ep-ANY"), dict)


# ---------------------------------------------------------------------------
# net_improvement and is_dead_end (T97-MGV-26..30)
# ---------------------------------------------------------------------------

def test_mgv_26_net_improvement_average():
    """net_improvement is mean of four deltas."""
    v = PropertyInheritanceVector("ep-A", "ep-B", 0.4, 0.2, 0.2, 0.0)
    assert v.net_improvement == pytest.approx(0.2, abs=1e-6)


def test_mgv_27_is_dead_end_below_threshold():
    """is_dead_end is True when net_improvement < -0.05."""
    v = PropertyInheritanceVector("ep-A", "ep-B", -0.3, -0.3, -0.3, -0.3)
    assert v.is_dead_end is True


def test_mgv_28_is_dead_end_above_threshold():
    """is_dead_end is False when net_improvement >= -0.05."""
    v = PropertyInheritanceVector("ep-A", "ep-B", 0.1, 0.1, 0.1, 0.1)
    assert v.is_dead_end is False


def test_mgv_29_record_inheritance_returns_vector(tmp_path, parent_scores, child_scores):
    """record_inheritance returns PropertyInheritanceVector instance."""
    a = MutationGenealogyAnalyzer(tmp_path / "g.jsonl")
    result = a.record_inheritance("ep-A", "ep-B", parent_scores, child_scores)
    assert isinstance(result, PropertyInheritanceVector)


def test_mgv_30_persistence_roundtrip(tmp_path, parent_scores, child_scores):
    """Persisted vectors survive a fresh analyzer load from same path."""
    path = tmp_path / "g.jsonl"
    a1 = MutationGenealogyAnalyzer(path)
    a1.record_inheritance("ep-A", "ep-B", parent_scores, child_scores)
    a2 = MutationGenealogyAnalyzer(path)
    assert len(a2._vectors) == 1
    assert a2._vectors[0].parent_epoch == "ep-A"
    assert a2._vectors[0].child_epoch == "ep-B"
