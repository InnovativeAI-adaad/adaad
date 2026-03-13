"""
tests/test_lineage_engine_phase61.py
=====================================
Phase 61 — Lineage Engine — T61-LIN-01..12

Coverage
--------
T61-LIN-01  LineageNode creation, immutability, enums
T61-LIN-02  LineageNode.record_outcome + survival_score (LINEAGE-STAB-0)
T61-LIN-03  LineageNode cooling trigger (< 2/5 passes in 5 epochs)
T61-LIN-04  LineageNode serialisation roundtrip + node_hash determinism
T61-LIN-05  CompatibilityMatrix co-occurrence recording
T61-LIN-06  CompatibilityMatrix epistasis detection (EPISTASIS-0)
T61-LIN-07  CompatibilityMatrix cooling advance + expiry
T61-LIN-08  NicheRegistry pool management + top candidate
T61-LIN-09  NicheRegistry cross-niche breeding (C(5,2)=10 hybrids)
T61-LIN-10  LineageEngine register + lineage chain + generation depth
T61-LIN-11  LineageEngine outcome recording + LINEAGE-STAB-0 integration
T61-LIN-12  LineageEngine epoch lifecycle + summary + engine_hash stability
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.evolution.lineage import (
    LineageEngine, LineageNode, EpochOutcome, MutationNiche,
    CompatibilityMatrix, CoOccurrenceRecord, EPISTASIS_COOLING_EPOCHS,
    NicheRegistry, NichePool, HybridCandidate, EpochLineageSummary,
)

_TS = "2026-03-13T00:00:00Z"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(
    patch_hash: str = "aabbcc",
    niche: MutationNiche = MutationNiche.PERFORMANCE,
    parent_id=None,
    generation: int = 0,
) -> LineageNode:
    return LineageNode.create(
        patch_hash=patch_hash,
        niche=niche,
        created_at=_TS,
        parent_id=parent_id,
        generation=generation,
    )


def _engine() -> LineageEngine:
    return LineageEngine()


# ===========================================================================
# T61-LIN-01  LineageNode creation and immutability
# ===========================================================================

class TestT61Lin01NodeCreation:

    def test_basic_creation(self):
        n = _node()
        assert n.niche == MutationNiche.PERFORMANCE
        assert n.generation == 0
        assert n.parent_id is None

    def test_all_niches_valid(self):
        for niche in MutationNiche:
            n = _node(patch_hash=niche.value, niche=niche)
            assert n.niche == niche

    def test_node_is_frozen(self):
        n = _node()
        with pytest.raises((AttributeError, TypeError)):
            n.generation = 99  # type: ignore

    def test_node_id_is_64_hex(self):
        n = _node()
        assert len(n.node_id) == 64
        int(n.node_id, 16)

    def test_node_hash_is_64_hex(self):
        n = _node()
        assert len(n.node_hash) == 64
        int(n.node_hash, 16)

    def test_new_node_has_empty_outcomes(self):
        n = _node()
        assert n.epoch_outcomes == ()
        assert n.fitness_scores == ()
        assert n.in_cooling is False

    def test_parent_generation_propagated(self):
        parent = _node(patch_hash="parent")
        child = _node(patch_hash="child", parent_id=parent.node_id, generation=1)
        assert child.generation == 1
        assert child.parent_id == parent.node_id


# ===========================================================================
# T61-LIN-02  record_outcome + survival_score (LINEAGE-STAB-0)
# ===========================================================================

class TestT61Lin02RecordOutcome:

    def test_record_outcome_returns_new_node(self):
        n = _node()
        n2 = n.record_outcome(EpochOutcome.PASSED, 0.8)
        assert n is not n2
        assert len(n2.epoch_outcomes) == 1
        assert n2.epoch_outcomes[0] == EpochOutcome.PASSED

    def test_fitness_clamped(self):
        n = _node()
        n2 = n.record_outcome(EpochOutcome.PASSED, 2.5)  # > 1.0
        assert n2.fitness_scores[0] == 1.0
        n3 = n.record_outcome(EpochOutcome.PASSED, -0.5)  # < 0.0
        assert n3.fitness_scores[0] == 0.0

    def test_survival_score_all_pass(self):
        n = _node()
        for _ in range(5):
            n = n.record_outcome(EpochOutcome.PASSED, 0.9)
        assert n.survival_score() == 1.0
        assert n.is_stable()

    def test_survival_score_2_of_5_passes(self):
        n = _node()
        outcomes = [EpochOutcome.PASSED, EpochOutcome.REJECTED,
                    EpochOutcome.REJECTED, EpochOutcome.REJECTED,
                    EpochOutcome.PASSED]
        for o in outcomes:
            n = n.record_outcome(o, 0.5)
        assert abs(n.survival_score() - 0.4) < 1e-6
        assert n.is_stable()  # exactly 2/5 → threshold met

    def test_survival_score_1_of_5_fails(self):
        n = _node()
        for o in [EpochOutcome.REJECTED] * 4 + [EpochOutcome.PASSED]:
            n = n.record_outcome(o, 0.1)
        assert n.survival_score() < 0.4
        assert not n.is_stable()

    def test_survival_uses_only_last_5(self):
        n = _node()
        # First 10 epochs all pass
        for _ in range(10):
            n = n.record_outcome(EpochOutcome.PASSED, 0.9)
        # Last 5 all fail
        for _ in range(5):
            n = n.record_outcome(EpochOutcome.REJECTED, 0.1)
        assert n.survival_score() == 0.0

    def test_epochs_evaluated(self):
        n = _node()
        for _ in range(7):
            n = n.record_outcome(EpochOutcome.PASSED, 0.8)
        assert n.epochs_evaluated() == 7


# ===========================================================================
# T61-LIN-03  Cooling trigger (LINEAGE-STAB-0)
# ===========================================================================

class TestT61Lin03CoolingTrigger:

    def test_no_cooling_before_5_epochs(self):
        n = _node()
        for _ in range(4):
            n = n.record_outcome(EpochOutcome.REJECTED, 0.1)
        assert not n.in_cooling

    def test_cooling_triggered_after_5_all_fail(self):
        n = _node()
        for _ in range(5):
            n = n.record_outcome(EpochOutcome.REJECTED, 0.0)
        assert n.in_cooling

    def test_cooling_not_triggered_2_of_5_pass(self):
        n = _node()
        for o in [EpochOutcome.PASSED, EpochOutcome.REJECTED,
                  EpochOutcome.REJECTED, EpochOutcome.REJECTED, EpochOutcome.PASSED]:
            n = n.record_outcome(o, 0.5)
        assert not n.in_cooling

    def test_last_outcome(self):
        n = _node()
        n = n.record_outcome(EpochOutcome.COOLING, 0.0)
        assert n.last_outcome() == EpochOutcome.COOLING


# ===========================================================================
# T61-LIN-04  Serialisation + node_hash determinism
# ===========================================================================

class TestT61Lin04Serialisation:

    def test_to_dict_has_required_keys(self):
        n = _node()
        d = n.to_dict()
        for key in ("node_id", "patch_hash", "niche", "generation",
                    "epoch_outcomes", "fitness_scores", "in_cooling",
                    "node_hash", "survival_score", "is_stable"):
            assert key in d

    def test_from_dict_roundtrip(self):
        n = _node(niche=MutationNiche.SAFETY)
        n = n.record_outcome(EpochOutcome.PASSED, 0.7)
        restored = LineageNode.from_dict(n.to_dict())
        assert restored.node_id == n.node_id
        assert restored.node_hash == n.node_hash
        assert restored.survival_score() == n.survival_score()

    def test_node_hash_deterministic(self):
        n1 = _node(patch_hash="x")
        n2 = _node(patch_hash="x")
        assert n1.node_hash == n2.node_hash

    def test_different_patch_hash_different_node_hash(self):
        n1 = _node(patch_hash="aaa")
        n2 = _node(patch_hash="bbb")
        assert n1.node_hash != n2.node_hash


# ===========================================================================
# T61-LIN-05  CompatibilityMatrix co-occurrence recording
# ===========================================================================

class TestT61Lin05CompatMatrix:

    def test_record_co_occurrence(self):
        m = CompatibilityMatrix()
        rec = m.record("p1", "p2", "E01", True, True, True)
        assert rec.joint_passed is True
        assert not rec.epistatic

    def test_co_occurrence_count(self):
        m = CompatibilityMatrix()
        m.record("p1", "p2", "E01", True, True, True)
        m.record("p1", "p2", "E02", True, True, True)
        assert m.co_occurrence_count("p1", "p2") == 2

    def test_canonical_pair_order(self):
        m = CompatibilityMatrix()
        rec = m.record("zzz", "aaa", "E01", True, True, True)
        # should be stored as (aaa, zzz) lexicographically
        assert rec.patch_a < rec.patch_b

    def test_matrix_hash_is_64_hex(self):
        m = CompatibilityMatrix()
        h = m.matrix_hash()
        assert len(h) == 64
        int(h, 16)


# ===========================================================================
# T61-LIN-06  Epistasis detection (EPISTASIS-0)
# ===========================================================================

class TestT61Lin06Epistasis:

    def test_epistasis_flagged_when_joint_fails(self):
        m = CompatibilityMatrix()
        rec = m.record("p1", "p2", "E01",
                       a_passed_alone=True, b_passed_alone=True, joint_passed=False)
        assert rec.epistatic
        assert m.is_epistatic_pair("p1", "p2")

    def test_no_epistasis_when_joint_passes(self):
        m = CompatibilityMatrix()
        rec = m.record("p1", "p2", "E01",
                       a_passed_alone=True, b_passed_alone=True, joint_passed=True)
        assert not rec.epistatic
        assert not m.is_epistatic_pair("p1", "p2")

    def test_no_epistasis_when_a_fails_alone(self):
        m = CompatibilityMatrix()
        rec = m.record("p1", "p2", "E01",
                       a_passed_alone=False, b_passed_alone=True, joint_passed=False)
        assert not rec.epistatic

    def test_epistasis_count(self):
        m = CompatibilityMatrix()
        m.record("p1", "p2", "E01", True, True, False)
        m.record("p3", "p4", "E01", True, True, False)
        assert m.epistasis_count() == 2

    def test_epistasis_cooling_duration(self):
        m = CompatibilityMatrix()
        m.record("p1", "p2", "E01", True, True, False)
        assert m.is_epistatic_pair("p1", "p2")
        for _ in range(EPISTASIS_COOLING_EPOCHS):
            m.advance_epoch()
        assert not m.is_epistatic_pair("p1", "p2")


# ===========================================================================
# T61-LIN-07  CompatibilityMatrix cooling advance
# ===========================================================================

class TestT61Lin07CoolingAdvance:

    def test_advance_decrements_counter(self):
        m = CompatibilityMatrix()
        m.record("p1", "p2", "E01", True, True, False)
        m.advance_epoch()
        remaining = m._cooling_counters.get(frozenset(["p1", "p2"]), 0)
        assert remaining == EPISTASIS_COOLING_EPOCHS - 1

    def test_pair_unblocked_after_full_cooling(self):
        m = CompatibilityMatrix()
        m.record("p1", "p2", "E01", True, True, False)
        for _ in range(EPISTASIS_COOLING_EPOCHS):
            m.advance_epoch()
        assert not m.is_epistatic_pair("p1", "p2")
        assert frozenset(["p1", "p2"]) not in m._cooling_counters

    def test_to_dict_serialisable(self):
        m = CompatibilityMatrix()
        m.record("p1", "p2", "E01", True, True, False)
        d = m.to_dict()
        assert json.dumps(d)


# ===========================================================================
# T61-LIN-08  NicheRegistry pool management
# ===========================================================================

class TestT61Lin08NicheRegistry:

    def test_register_adds_to_pool(self):
        r = NicheRegistry()
        n = _node(niche=MutationNiche.SAFETY)
        r.register(n)
        assert r.pool(MutationNiche.SAFETY).size() == 1

    def test_wrong_niche_raises(self):
        pool = NichePool(niche=MutationNiche.SAFETY)
        n = _node(niche=MutationNiche.PERFORMANCE)
        with pytest.raises(ValueError):
            pool.add(n)

    def test_top_candidate_sorted_by_survival(self):
        r = NicheRegistry()
        n_low = _node(patch_hash="low", niche=MutationNiche.PERFORMANCE)
        # Give high_survival node 5 passes
        n_high = _node(patch_hash="high", niche=MutationNiche.PERFORMANCE)
        for _ in range(5):
            n_high = n_high.record_outcome(EpochOutcome.PASSED, 1.0)
        r.register(n_low)
        r.register(n_high)
        top = r.top_candidate(MutationNiche.PERFORMANCE)
        assert top.patch_hash == "high"

    def test_total_candidates(self):
        r = NicheRegistry()
        for i, niche in enumerate(MutationNiche):
            r.register(_node(patch_hash=str(i), niche=niche))
        assert r.total_candidates() == 5

    def test_registry_hash_deterministic(self):
        r1 = NicheRegistry()
        r2 = NicheRegistry()
        n = _node()
        r1.register(n)
        r2.register(n)
        assert r1.registry_hash() == r2.registry_hash()


# ===========================================================================
# T61-LIN-09  Cross-niche breeding
# ===========================================================================

class TestT61Lin09CrossNiche:

    def test_breed_returns_hybrid(self):
        r = NicheRegistry()
        r.register(_node(patch_hash="perf", niche=MutationNiche.PERFORMANCE))
        r.register(_node(patch_hash="safe", niche=MutationNiche.SAFETY))
        h = r.breed(MutationNiche.PERFORMANCE, MutationNiche.SAFETY)
        assert h is not None
        assert isinstance(h, HybridCandidate)
        assert h.niche_a == MutationNiche.PERFORMANCE
        assert h.niche_b == MutationNiche.SAFETY

    def test_breed_returns_none_when_empty_pool(self):
        r = NicheRegistry()
        r.register(_node(patch_hash="perf", niche=MutationNiche.PERFORMANCE))
        # SAFETY pool is empty
        h = r.breed(MutationNiche.PERFORMANCE, MutationNiche.SAFETY)
        assert h is None

    def test_same_niche_breed_raises(self):
        r = NicheRegistry()
        with pytest.raises(ValueError):
            r.breed(MutationNiche.SAFETY, MutationNiche.SAFETY)

    def test_all_possible_hybrids_count(self):
        r = NicheRegistry()
        for i, niche in enumerate(MutationNiche):
            r.register(_node(patch_hash=str(i), niche=niche))
        hybrids = r.all_possible_hybrids()
        assert len(hybrids) == 10  # C(5,2)

    def test_hybrid_id_deterministic(self):
        r = NicheRegistry()
        n_p = _node(patch_hash="perf", niche=MutationNiche.PERFORMANCE)
        n_s = _node(patch_hash="safe", niche=MutationNiche.SAFETY)
        r.register(n_p)
        r.register(n_s)
        h1 = r.breed(MutationNiche.PERFORMANCE, MutationNiche.SAFETY)
        h2 = r.breed(MutationNiche.PERFORMANCE, MutationNiche.SAFETY)
        assert h1.hybrid_id == h2.hybrid_id

    def test_hybrid_to_dict_serialisable(self):
        r = NicheRegistry()
        r.register(_node(patch_hash="p", niche=MutationNiche.PERFORMANCE))
        r.register(_node(patch_hash="s", niche=MutationNiche.SAFETY))
        h = r.breed(MutationNiche.PERFORMANCE, MutationNiche.SAFETY)
        assert json.dumps(h.to_dict())


# ===========================================================================
# T61-LIN-10  LineageEngine register + chain + generation depth
# ===========================================================================

class TestT61Lin10EngineRegister:

    def test_register_root_node(self):
        e = _engine()
        n = e.register("h1", MutationNiche.PERFORMANCE, _TS)
        assert n.generation == 0
        assert e.total_nodes() == 1

    def test_register_child_increments_generation(self):
        e = _engine()
        parent = e.register("p1", MutationNiche.PERFORMANCE, _TS)
        child = e.register("c1", MutationNiche.SAFETY, _TS, parent_id=parent.node_id)
        assert child.generation == 1
        assert child.parent_id == parent.node_id

    def test_lineage_chain_root_only(self):
        e = _engine()
        n = e.register("p1", MutationNiche.PERFORMANCE, _TS)
        chain = e.lineage_chain(n.node_id)
        assert len(chain) == 1
        assert chain[0].node_id == n.node_id

    def test_lineage_chain_depth_3(self):
        e = _engine()
        n0 = e.register("g0", MutationNiche.PERFORMANCE, _TS)
        n1 = e.register("g1", MutationNiche.PERFORMANCE, _TS, parent_id=n0.node_id)
        n2 = e.register("g2", MutationNiche.PERFORMANCE, _TS, parent_id=n1.node_id)
        chain = e.lineage_chain(n2.node_id)
        assert len(chain) == 3
        assert chain[0].node_id == n0.node_id
        assert chain[2].node_id == n2.node_id

    def test_node_by_patch_hash(self):
        e = _engine()
        n = e.register("unique_hash", MutationNiche.ARCHITECTURE, _TS)
        found = e.node_by_patch("unique_hash")
        assert found is not None
        assert found.node_id == n.node_id

    def test_unknown_node_returns_none(self):
        e = _engine()
        assert e.node("nonexistent") is None


# ===========================================================================
# T61-LIN-11  Engine outcome recording + LINEAGE-STAB-0
# ===========================================================================

class TestT61Lin11EngineOutcomes:

    def test_record_outcome_updates_node(self):
        e = _engine()
        n = e.register("p1", MutationNiche.PERFORMANCE, _TS)
        updated = e.record_outcome(n.node_id, EpochOutcome.PASSED, 0.9)
        assert updated.epochs_evaluated() == 1
        assert updated.epoch_outcomes[0] == EpochOutcome.PASSED

    def test_record_outcome_unknown_node_raises(self):
        e = _engine()
        with pytest.raises(KeyError):
            e.record_outcome("nonexistent", EpochOutcome.PASSED, 0.5)

    def test_cooling_reflected_in_engine(self):
        e = _engine()
        n = e.register("p1", MutationNiche.PERFORMANCE, _TS)
        for _ in range(5):
            e.record_outcome(n.node_id, EpochOutcome.REJECTED, 0.0)
        node = e.node(n.node_id)
        assert node.in_cooling

    def test_epistasis_via_engine(self):
        e = _engine()
        rec = e.record_co_occurrence("ph_a", "ph_b", "E01",
                                      True, True, False)
        assert rec.epistatic
        assert e.is_epistatic_pair("ph_a", "ph_b")


# ===========================================================================
# T61-LIN-12  Epoch lifecycle + summary + engine_hash stability
# ===========================================================================

class TestT61Lin12EpochLifecycle:

    def test_end_epoch_returns_summary(self):
        e = _engine()
        e.register("p1", MutationNiche.PERFORMANCE, _TS)
        summary = e.end_epoch("E01")
        assert isinstance(summary, EpochLineageSummary)
        assert summary.epoch_id == "E01"
        assert summary.nodes_registered == 1

    def test_epoch_clears_registered_count(self):
        e = _engine()
        e.register("p1", MutationNiche.PERFORMANCE, _TS)
        e.end_epoch("E01")
        # New epoch — no new registrations
        summary2 = e.end_epoch("E02")
        assert summary2.nodes_registered == 0

    def test_engine_hash_deterministic(self):
        e1 = _engine()
        e2 = _engine()
        e1.register("p1", MutationNiche.PERFORMANCE, _TS)
        e2.register("p1", MutationNiche.PERFORMANCE, _TS)
        assert e1.engine_hash() == e2.engine_hash()

    def test_engine_hash_changes_on_mutation(self):
        e = _engine()
        h1 = e.engine_hash()
        e.register("p1", MutationNiche.PERFORMANCE, _TS)
        h2 = e.engine_hash()
        assert h1 != h2

    def test_summary_to_dict_serialisable(self):
        e = _engine()
        e.register("p1", MutationNiche.PERFORMANCE, _TS)
        summary = e.end_epoch("E01")
        assert json.dumps(summary.to_dict())

    def test_epistasis_cooling_advances_on_end_epoch(self):
        e = _engine()
        e.record_co_occurrence("ph_a", "ph_b", "E01", True, True, False)
        assert e.is_epistatic_pair("ph_a", "ph_b")
        for _ in range(EPISTASIS_COOLING_EPOCHS):
            e.end_epoch(f"E0{_+2}")
        assert not e.is_epistatic_pair("ph_a", "ph_b")

    def test_to_dict_serialisable(self):
        e = _engine()
        e.register("p1", MutationNiche.PERFORMANCE, _TS)
        assert json.dumps(e.to_dict())
