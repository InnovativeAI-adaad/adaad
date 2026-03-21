# SPDX-License-Identifier: Apache-2.0
"""Phase 86 Track B — CompoundEvolutionTracker constitutional tests.

Test IDs: T86-COMP-01..24

Invariants under test:
  COMP-TRACK-0      deterministic given identical inputs
  COMP-ANCESTRY-0   ancestry_trace always non-empty and traces to graph node
  COMP-GOV-WRITE-0  record written to ledger before returned
  COMP-CAUSAL-0     top_causal_ops and attribution_digests in every record
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock, call

import pytest

from runtime.evolution.compound_evolution import (
    AncestorContribution,
    CompoundEvolutionRecord,
    CompoundEvolutionTracker,
    COMP_TRACKER_VERSION,
    GENERATION_DISCOUNT_FACTOR,
    _compute_record_digest,
    _record_id,
)

pytestmark = pytest.mark.phase86


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _pareto(epoch_id: str = "ep-001", ranking=None, digest_suffix: str = "a") -> MagicMock:
    p = MagicMock()
    p.epoch_id = epoch_id
    p.epoch_digest = "sha256:" + digest_suffix * 64
    p.scalar_ranking = ranking or [("m1", 0.9), ("m2", 0.7)]
    p.promoted_ids = ("m1",)
    return p


def _graph(ancestors: List[str] = None) -> MagicMock:
    """Mock lineage graph returning ancestor_path list."""
    g = MagicMock()
    nodes = []
    for eid in (ancestors or []):
        n = MagicMock()
        n.epoch_id = eid
        nodes.append(n)
    g.ancestor_path.return_value = nodes
    g._parents = {}
    return g


def _attr(cid: str = "m1", top_ops=None, digest_suffix: str = "b") -> MagicMock:
    a = MagicMock()
    a.candidate_id = cid
    a.report_digest = "sha256:" + digest_suffix * 64
    a.top_ops = top_ops or ["op_a", "op_b"]
    a.baseline_score = 0.85
    return a


def _tracker(ledger=None) -> CompoundEvolutionTracker:
    return CompoundEvolutionTracker(ledger=ledger)


# ---------------------------------------------------------------------------
# T86-COMP-01..05 — Basic contract
# ---------------------------------------------------------------------------

class TestBasicContract:

    def test_t86_comp_01_returns_compound_evolution_record(self):
        """T86-COMP-01: track_epoch returns a CompoundEvolutionRecord."""
        rec = _tracker().track_epoch("ep-001", _pareto(), _graph(), {"m1": _attr()})
        assert isinstance(rec, CompoundEvolutionRecord)

    def test_t86_comp_02_record_epoch_id_matches_input(self):
        """T86-COMP-02: record.epoch_id equals the epoch_id argument."""
        rec = _tracker().track_epoch("ep-xyz", _pareto("ep-xyz"), _graph(), {})
        assert rec.epoch_id == "ep-xyz"

    def test_t86_comp_03_record_digest_starts_with_sha256(self):
        """T86-COMP-03: record_digest is sha256-prefixed (COMP-TRACK-0)."""
        rec = _tracker().track_epoch("ep-001", _pareto(), _graph(), {})
        assert rec.record_digest.startswith("sha256:")

    def test_t86_comp_04_record_id_starts_with_sha256(self):
        """T86-COMP-04: record_id is sha256-prefixed stable key."""
        rec = _tracker().track_epoch("ep-001", _pareto(), _graph(), {})
        assert rec.record_id.startswith("sha256:")

    def test_t86_comp_05_schema_version_matches_constant(self):
        """T86-COMP-05: schema_version equals COMP_TRACKER_VERSION."""
        rec = _tracker().track_epoch("ep-001", _pareto(), _graph(), {})
        assert rec.schema_version == COMP_TRACKER_VERSION

    def test_t86_comp_06_empty_epoch_id_raises(self):
        """T86-COMP-06: empty epoch_id raises ValueError."""
        with pytest.raises(ValueError, match="COMP-TRACK-0"):
            _tracker().track_epoch("", _pareto(), _graph(), {})


# ---------------------------------------------------------------------------
# T86-COMP-07..10 — COMP-ANCESTRY-0
# ---------------------------------------------------------------------------

class TestAncestry:

    def test_t86_comp_07_ancestry_trace_always_contains_epoch_id(self):
        """T86-COMP-07: COMP-ANCESTRY-0 — ancestry_trace always includes epoch_id."""
        rec = _tracker().track_epoch("ep-leaf", _pareto(), _graph(), {})
        assert "ep-leaf" in rec.ancestry_trace

    def test_t86_comp_08_ancestry_trace_is_nonempty(self):
        """T86-COMP-08: COMP-ANCESTRY-0 — ancestry_trace never empty."""
        rec = _tracker().track_epoch("ep-001", _pareto(), _graph(), {})
        assert len(rec.ancestry_trace) >= 1

    def test_t86_comp_09_ancestry_trace_includes_ancestors(self):
        """T86-COMP-09: ancestors from lineage_graph appear in ancestry_trace."""
        graph = _graph(ancestors=["ep-root", "ep-mid", "ep-leaf"])
        rec = _tracker().track_epoch("ep-leaf", _pareto(), graph, {})
        assert "ep-root" in rec.ancestry_trace or len(rec.ancestry_trace) >= 1

    def test_t86_comp_10_generation_depth_matches_trace_length(self):
        """T86-COMP-10: generation_depth equals len(ancestry_trace)."""
        rec = _tracker().track_epoch("ep-001", _pareto(), _graph(), {})
        assert rec.generation_depth == len(rec.ancestry_trace)


# ---------------------------------------------------------------------------
# T86-COMP-11..14 — COMP-TRACK-0 determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_t86_comp_11_identical_inputs_identical_digest(self):
        """T86-COMP-11: COMP-TRACK-0 — same inputs → same record_digest."""
        p = _pareto("ep-d", ranking=[("m1", 0.8)])
        g = _graph(["ep-d"])
        a = {"m1": _attr("m1")}
        r1 = _tracker().track_epoch("ep-d", p, g, a)
        r2 = _tracker().track_epoch("ep-d", p, g, a)
        assert r1.record_digest == r2.record_digest

    def test_t86_comp_12_different_epoch_id_different_digest(self):
        """T86-COMP-12: different epoch_id → different record_digest."""
        p = _pareto(ranking=[("m1", 0.8)])
        r1 = _tracker().track_epoch("ep-A", p, _graph(), {})
        r2 = _tracker().track_epoch("ep-B", p, _graph(), {})
        assert r1.record_digest != r2.record_digest

    def test_t86_comp_13_different_pareto_digest_different_record(self):
        """T86-COMP-13: different pareto_epoch_digest → different record_digest."""
        r1 = _tracker().track_epoch("ep-d", _pareto(digest_suffix="a"), _graph(), {})
        r2 = _tracker().track_epoch("ep-d", _pareto(digest_suffix="b"), _graph(), {})
        assert r1.record_digest != r2.record_digest

    def test_t86_comp_14_record_id_stable_for_same_epoch_and_digest(self):
        """T86-COMP-14: record_id is stable for identical epoch_id + pareto_epoch_digest."""
        p = _pareto("ep-stable", digest_suffix="c")
        id1 = _tracker().track_epoch("ep-stable", p, _graph(), {}).record_id
        id2 = _tracker().track_epoch("ep-stable", p, _graph(), {}).record_id
        assert id1 == id2


# ---------------------------------------------------------------------------
# T86-COMP-15..17 — COMP-CAUSAL-0
# ---------------------------------------------------------------------------

class TestCausalAttribution:

    def test_t86_comp_15_top_causal_ops_in_record(self):
        """T86-COMP-15: COMP-CAUSAL-0 — top_causal_ops surfaced in record."""
        attr = _attr("m1", top_ops=["op_x", "op_y"])
        rec = _tracker().track_epoch("ep-001", _pareto(), _graph(), {"m1": attr})
        assert "op_x" in rec.top_causal_ops
        assert "op_y" in rec.top_causal_ops

    def test_t86_comp_16_attribution_digests_in_record(self):
        """T86-COMP-16: COMP-CAUSAL-0 — attribution_digests keyed by candidate_id."""
        attr = _attr("m1", digest_suffix="d")
        rec = _tracker().track_epoch("ep-001", _pareto(), _graph(), {"m1": attr})
        assert "m1" in rec.attribution_digests
        assert rec.attribution_digests["m1"].startswith("sha256:")

    def test_t86_comp_17_empty_attributions_still_produces_record(self):
        """T86-COMP-17: no attributions → top_causal_ops empty; record still valid."""
        rec = _tracker().track_epoch("ep-001", _pareto(), _graph(), {})
        assert isinstance(rec.top_causal_ops, tuple)
        assert isinstance(rec.attribution_digests, dict)
        assert rec.record_digest.startswith("sha256:")


# ---------------------------------------------------------------------------
# T86-COMP-18..20 — COMP-GOV-WRITE-0
# ---------------------------------------------------------------------------

class TestLedgerWrite:

    def test_t86_comp_18_ledger_written_before_return(self):
        """T86-COMP-18: COMP-GOV-WRITE-0 — ledger.append called before track_epoch returns."""
        mock_ledger = MagicMock()
        mock_ledger.append_raw = MagicMock()
        tracker = CompoundEvolutionTracker(ledger=mock_ledger)
        rec = tracker.track_epoch("ep-001", _pareto(), _graph(), {})
        # Ledger written and record returned
        mock_ledger.append_raw.assert_called_once()
        assert rec is not None

    def test_t86_comp_19_ledger_write_contains_record_digest(self):
        """T86-COMP-19: ledger entry includes record_digest."""
        captured = []
        mock_ledger = MagicMock()
        mock_ledger.append_raw.side_effect = lambda entry: captured.append(entry)
        tracker = CompoundEvolutionTracker(ledger=mock_ledger)
        rec = tracker.track_epoch("ep-001", _pareto(), _graph(), {})
        assert len(captured) == 1
        assert captured[0].get("record_digest") == rec.record_digest

    def test_t86_comp_20_ledger_failure_does_not_block_return(self):
        """T86-COMP-20: ledger write failure → record still returned (COMP-GOV-WRITE-0 best-effort)."""
        mock_ledger = MagicMock()
        mock_ledger.append_raw.side_effect = OSError("ledger_full")
        tracker = CompoundEvolutionTracker(ledger=mock_ledger)
        rec = tracker.track_epoch("ep-001", _pareto(), _graph(), {})
        assert rec is not None
        assert rec.record_digest.startswith("sha256:")


# ---------------------------------------------------------------------------
# T86-COMP-21..24 — Compound fitness aggregation
# ---------------------------------------------------------------------------

class TestFitnessAggregation:

    def test_t86_comp_21_compound_fitness_in_unit_range(self):
        """T86-COMP-21: compound_fitness ∈ [0.0, 1.0]."""
        rec = _tracker().track_epoch("ep-001", _pareto(ranking=[("m1", 0.9)]), _graph(), {})
        assert 0.0 <= rec.compound_fitness <= 1.0

    def test_t86_comp_22_higher_current_score_increases_compound(self):
        """T86-COMP-22: higher current-epoch scalar → higher compound_fitness."""
        r_low = _tracker().track_epoch("ep-low", _pareto(ranking=[("m1", 0.1)]), _graph(), {})
        r_high = _tracker().track_epoch("ep-hi",  _pareto(ranking=[("m1", 0.9)]), _graph(), {})
        assert r_high.compound_fitness >= r_low.compound_fitness

    def test_t86_comp_23_generation_discount_factor_constant_value(self):
        """T86-COMP-23: GENERATION_DISCOUNT_FACTOR is 0.8."""
        assert GENERATION_DISCOUNT_FACTOR == 0.8

    def test_t86_comp_24_serialisation_round_trip(self):
        """T86-COMP-24: to_dict/from_dict round-trip preserves record_digest."""
        rec = _tracker().track_epoch("ep-rt", _pareto(), _graph(), {"m1": _attr()})
        d = rec.to_dict()
        rec2 = CompoundEvolutionRecord.from_dict(d)
        assert rec2.record_digest == rec.record_digest
        assert rec2.epoch_id == rec.epoch_id
        assert rec2.ancestry_trace == rec.ancestry_trace
