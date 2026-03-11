# SPDX-License-Identifier: Apache-2.0

# ADAAD-LANE: constitutional-inviolability

"""
Phase 2 capability test suite — comprehensive coverage for:

  1. ExploreExploitController  (runtime/autonomy/explore_exploit_controller.py)
  2. HumanApprovalGate         (runtime/governance/human_approval_gate.py)
  3. LineageDAG                (runtime/evolution/lineage_dag.py)
  4. PhaseTransitionGate       (runtime/governance/phase_transition_gate.py)

Test categories per module:
  - Construction and default state
  - Core operation correctness
  - Constitutional invariants (floors, ceilings, fail-closed)
  - Persistence and reload
  - Audit trail completeness
  - Edge cases and error paths
  - Determinism (identical inputs → identical outputs)
"""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from typing import List
from unittest import mock
from runtime.autonomy.explore_exploit_controller import (
    ControllerState,
    EvolutionMode,
    ExploreExploitController,
    MAX_CONSECUTIVE_EXPLOIT,
    MIN_EXPLORE_RATIO,
    ModeTransitionEvent,
    WINDOW_SIZE,
)
from runtime.governance.human_approval_gate import (
    ApprovalDecision,
    ApprovalReason,
    ApprovalRequest,
    ApprovalStatus,
    HumanApprovalGate,
)
from runtime.evolution.lineage_dag import (
    BranchComparison,
    GenerationSummary,
    LineageDAG,
    LineageDAGIntegrityError,
    LineageDAGNodeError,
    LineageNode,
    MAX_GENERATION_DEPTH,
)
from runtime.timeutils import now_iso
def _make_node(
    node_id: str,
    parent_id=None,
    generation=0,
    agent="architect",
    epoch="e-001",
    score=0.5,
    mutation_type="structural",
    approved=False,
    promoted=False,
) -> LineageNode:
    return LineageNode(
        node_id=node_id,
        parent_id=parent_id,
        generation=generation,
        agent_origin=agent,
        epoch_id=epoch,
        fitness_score=score,
        mutation_type=mutation_type,
        human_approved=approved,
        promoted=promoted,
        created_at=now_iso(),
    )
class TestLineageDAG(unittest.TestCase):

    def _make_dag(self, **kwargs) -> LineageDAG:
        tmpdir = tempfile.mkdtemp()
        return LineageDAG(dag_path=Path(tmpdir) / "dag.jsonl", **kwargs)

    # --- add_node -----------------------------------------------------------

    def test_add_root_node_succeeds(self):
        dag = self._make_dag()
        digest = dag.add_node(_make_node("n-000"))
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)  # SHA-256 hex

    def test_add_child_node_succeeds(self):
        dag = self._make_dag()
        dag.add_node(_make_node("n-000"))
        dag.add_node(_make_node("n-001", parent_id="n-000", generation=1, score=0.7))
        self.assertEqual(dag.max_generation(), 1)

    def test_duplicate_node_id_raises(self):
        dag = self._make_dag()
        dag.add_node(_make_node("n-000"))
        with self.assertRaises(LineageDAGNodeError):
            dag.add_node(_make_node("n-000"))

    def test_missing_parent_raises(self):
        dag = self._make_dag()
        with self.assertRaises(LineageDAGNodeError):
            dag.add_node(_make_node("n-001", parent_id="n-missing", generation=1))

    def test_wrong_generation_raises(self):
        dag = self._make_dag()
        dag.add_node(_make_node("n-000"))
        with self.assertRaises(LineageDAGNodeError):
            dag.add_node(_make_node("n-001", parent_id="n-000", generation=5))

    def test_promoted_without_approval_raises(self):
        dag = self._make_dag()
        with self.assertRaises(LineageDAGNodeError):
            dag.add_node(_make_node("n-000", approved=False, promoted=True))

    def test_generation_exceeding_max_raises(self):
        dag = self._make_dag()
        # Build a chain up to MAX_GENERATION_DEPTH
        dag.add_node(_make_node("n-000"))
        parent = "n-000"
        for gen in range(1, MAX_GENERATION_DEPTH + 1):
            nid = f"n-{gen:03d}"
            dag.add_node(_make_node(nid, parent_id=parent, generation=gen))
            parent = nid
        # One more should raise
        with self.assertRaises(LineageDAGNodeError):
            dag.add_node(_make_node(
                f"n-{MAX_GENERATION_DEPTH + 1:03d}",
                parent_id=parent,
                generation=MAX_GENERATION_DEPTH + 1,
            ))

    # --- promote_node -------------------------------------------------------

    def test_promote_node_sets_flags(self):
        dag = self._make_dag()
        dag.add_node(_make_node("n-000"))
        promoted = dag.promote_node("n-000", operator_id="dreezy66")
        self.assertTrue(promoted.human_approved)
        self.assertTrue(promoted.promoted)

    def test_promote_nonexistent_node_raises(self):
        dag = self._make_dag()
        with self.assertRaises(LineageDAGNodeError):
            dag.promote_node("n-missing", operator_id="op")

    def test_get_node_after_promote_reflects_promotion(self):
        dag = self._make_dag()
        dag.add_node(_make_node("n-000"))
        dag.promote_node("n-000", operator_id="dreezy66")
        node = dag.get_node("n-000")
        self.assertTrue(node.promoted)

    # --- get_lineage_chain --------------------------------------------------

    def test_root_chain_is_single_node(self):
        dag = self._make_dag()
        dag.add_node(_make_node("n-000"))
        chain = dag.get_lineage_chain("n-000")
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0].node_id, "n-000")

    def test_chain_ordered_oldest_first(self):
        dag = self._make_dag()
        dag.add_node(_make_node("root"))
        dag.add_node(_make_node("child", parent_id="root", generation=1))
        dag.add_node(_make_node("grandchild", parent_id="child", generation=2))
        chain = dag.get_lineage_chain("grandchild")
        self.assertEqual([n.node_id for n in chain], ["root", "child", "grandchild"])

    def test_chain_missing_node_raises(self):
        dag = self._make_dag()
        with self.assertRaises(LineageDAGNodeError):
            dag.get_lineage_chain("n-missing")

    # --- compare_branches ---------------------------------------------------

    def test_branch_comparison_fitness_delta(self):
        dag = self._make_dag()
        dag.add_node(_make_node("root"))
        dag.add_node(_make_node("branch-a", parent_id="root", generation=1, score=0.80))
        dag.add_node(_make_node("branch-b", parent_id="root", generation=1, score=0.40))
        result = dag.compare_branches("branch-a", "branch-b")
        self.assertAlmostEqual(result.fitness_delta, 0.40, places=3)
        self.assertEqual(result.common_ancestor_id, "root")

    def test_branch_comparison_generation_distance(self):
        dag = self._make_dag()
        dag.add_node(_make_node("root"))
        dag.add_node(_make_node("g1", parent_id="root", generation=1))
        dag.add_node(_make_node("g2", parent_id="g1", generation=2))
        result = dag.compare_branches("root", "g2")
        self.assertEqual(result.generation_distance, 2)

    # --- generation_summary -------------------------------------------------

    def test_generation_summary_counts(self):
        dag = self._make_dag()
        dag.add_node(_make_node("root"))
        dag.add_node(_make_node("g1a", parent_id="root", generation=1, score=0.6))
        dag.add_node(_make_node("g1b", parent_id="root", generation=1, score=0.8))
        summaries = dag.generation_summary()
        self.assertEqual(len(summaries), 2)
        g1 = summaries[1]
        self.assertEqual(g1.generation, 1)
        self.assertEqual(g1.node_count, 2)
        self.assertAlmostEqual(g1.avg_fitness, 0.7, places=3)

    def test_generation_summary_top_node(self):
        dag = self._make_dag()
        dag.add_node(_make_node("root"))
        dag.add_node(_make_node("g1a", parent_id="root", generation=1, score=0.6))
        dag.add_node(_make_node("g1b", parent_id="root", generation=1, score=0.9))
        g1 = dag.generation_summary()[1]
        self.assertEqual(g1.top_node_id, "g1b")
        self.assertAlmostEqual(g1.top_fitness, 0.9, places=3)

    # --- integrity_check ----------------------------------------------------

    def test_integrity_check_passes_on_clean_dag(self):
        dag = self._make_dag()
        dag.add_node(_make_node("root"))
        dag.add_node(_make_node("child", parent_id="root", generation=1))
        self.assertTrue(dag.integrity_check())

    def test_integrity_check_fails_on_tampered_file(self):
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / "dag.jsonl"
        dag = LineageDAG(dag_path=path)
        dag.add_node(_make_node("root"))
        # Tamper with the stored digest
        lines = path.read_text().splitlines()
        record = json.loads(lines[0])
        record["chain_digest"] = "0" * 64
        path.write_text(json.dumps(record) + "\n")
        dag2 = LineageDAG(dag_path=path)
        self.assertFalse(dag2.integrity_check())

    # --- Persistence --------------------------------------------------------

    def test_dag_reloads_from_disk(self):
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / "dag.jsonl"
        dag = LineageDAG(dag_path=path)
        dag.add_node(_make_node("root"))
        dag.add_node(_make_node("child", parent_id="root", generation=1, score=0.75))
        dag.promote_node("child", operator_id="op")

        dag2 = LineageDAG(dag_path=path)
        node = dag2.get_node("child")
        self.assertIsNotNone(node)
        self.assertTrue(node.promoted)
        self.assertAlmostEqual(node.fitness_score, 0.75, places=3)

    # --- health_snapshot ----------------------------------------------------

    def test_health_snapshot_keys(self):
        dag = self._make_dag()
        dag.add_node(_make_node("root"))
        snap = dag.health_snapshot()
        for key in (
            "total_nodes", "max_generation", "approved_count", "promoted_count",
            "approval_rate", "promotion_rate", "chain_digest", "integrity_ok",
        ):
            self.assertIn(key, snap)

    def test_health_snapshot_integrity_ok_true(self):
        dag = self._make_dag()
        dag.add_node(_make_node("root"))
        snap = dag.health_snapshot()
        self.assertTrue(snap["integrity_ok"])

    # --- Audit writer -------------------------------------------------------

    def test_audit_writer_called_on_add_node(self):
        events = []

        def writer(et, payload):
            events.append(et)

        dag = self._make_dag(audit_writer=writer)
        dag.add_node(_make_node("root"))
        self.assertIn("lineage_node_added", events)

    def test_audit_writer_called_on_promote(self):
        events = []

        def writer(et, payload):
            events.append(et)

        dag = self._make_dag(audit_writer=writer)
        dag.add_node(_make_node("root"))
        dag.promote_node("root", operator_id="op")
        self.assertIn("lineage_node_promoted", events)
from runtime.governance.phase_transition_gate import (
    AutonomyLevel,
    GateCriteria,
    GateResult,
    PHASE_GATE_CRITERIA,
    PhaseTransitionGate,
    TransitionEvidence,
)
def _make_passing_evidence(target_phase: int) -> TransitionEvidence:
    """Build TransitionEvidence that satisfies all criteria for a target phase."""
    c = PHASE_GATE_CRITERIA[target_phase]
    return TransitionEvidence(
        approved_mutation_count=c.min_approved_mutations,
        mutation_pass_rate=c.min_mutation_pass_rate,
        lineage_completeness=c.min_lineage_completeness,
        audit_chain_intact=True,
        consecutive_clean_epochs=c.min_consecutive_clean_epochs,
    )
def _make_failing_evidence() -> TransitionEvidence:
    return TransitionEvidence(
        approved_mutation_count=0,
        mutation_pass_rate=0.0,
        lineage_completeness=0.0,
        audit_chain_intact=False,
        consecutive_clean_epochs=0,
    )
from runtime.evolution.evolution_loop import EvolutionLoop, EpochResult
if __name__ == "__main__":
    unittest.main()
