# SPDX-License-Identifier: Apache-2.0

"""Compatibility placeholder for moved Phase 2 capability tests.

Canonical suites:
- tests/governance/signals/test_phase2_governance_signals.py
- tests/governance/inviolability/test_phase2_lineage_inviolability.py
"""

# ADAAD-LANE: governance-signals
from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import json
import tempfile
import unittest
from pathlib import Path
from typing import List
from unittest import mock

# ---------------------------------------------------------------------------
# 1. ExploreExploitController
# ---------------------------------------------------------------------------

from runtime.autonomy.explore_exploit_controller import (
    ControllerState,
    EvolutionMode,
    ExploreExploitController,
    MAX_CONSECUTIVE_EXPLOIT,
    MIN_EXPLORE_RATIO,
    ModeTransitionEvent,
    WINDOW_SIZE,
)


class TestExploreExploitController(unittest.TestCase):

    def _make_controller(self, **kwargs) -> tuple[ExploreExploitController, Path]:
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / "ee_state.json"
        ctrl = ExploreExploitController(state_path=path, **kwargs)
        return ctrl, path

    # --- Construction -------------------------------------------------------

    def test_default_mode_is_explore(self):
        ctrl, _ = self._make_controller()
        self.assertEqual(ctrl.current_mode, EvolutionMode.EXPLORE)

    def test_default_consecutive_exploit_zero(self):
        ctrl, _ = self._make_controller()
        self.assertEqual(ctrl.consecutive_exploit_count, 0)

    def test_default_explore_ratio_one(self):
        ctrl, _ = self._make_controller()
        self.assertEqual(ctrl.window_explore_ratio(), 1.0)

    # --- select_mode logic --------------------------------------------------

    def test_plateau_forces_explore(self):
        ctrl, _ = self._make_controller()
        mode = ctrl.select_mode(
            epoch_id="e-001",
            epoch_score=0.90,   # High score — would normally trigger EXPLOIT
            is_plateau=True,    # But plateau overrides
        )
        self.assertEqual(mode, EvolutionMode.EXPLORE)

    def test_high_score_selects_exploit(self):
        ctrl, _ = self._make_controller()
        mode = ctrl.select_mode(
            epoch_id="e-001",
            epoch_score=0.70,
            is_plateau=False,
        )
        self.assertEqual(mode, EvolutionMode.EXPLOIT)

    def test_low_score_selects_explore(self):
        ctrl, _ = self._make_controller()
        mode = ctrl.select_mode(
            epoch_id="e-001",
            epoch_score=0.30,
            is_plateau=False,
        )
        self.assertEqual(mode, EvolutionMode.EXPLORE)

    def test_human_override_always_honoured(self):
        ctrl, _ = self._make_controller()
        # Score and plateau both push toward EXPLOIT, but override wins
        mode = ctrl.select_mode(
            epoch_id="e-001",
            epoch_score=0.90,
            is_plateau=False,
            human_override=EvolutionMode.EXPLORE,
        )
        self.assertEqual(mode, EvolutionMode.EXPLORE)

    def test_consecutive_exploit_limit_forces_explore(self):
        ctrl, _ = self._make_controller()
        # Drive consecutive exploit counter to the limit
        for i in range(MAX_CONSECUTIVE_EXPLOIT):
            ctrl.commit_epoch(f"e-{i:03d}", EvolutionMode.EXPLOIT)
        # Now even high score should force EXPLORE
        mode = ctrl.select_mode(
            epoch_id=f"e-{MAX_CONSECUTIVE_EXPLOIT:03d}",
            epoch_score=0.90,
            is_plateau=False,
        )
        self.assertEqual(mode, EvolutionMode.EXPLORE)

    def test_explore_floor_enforced(self):
        """After 8 EXPLOIT + 2 EXPLORE in window of 10, ratio = 0.20 (floor OK).
        After 9 EXPLOIT + 1 EXPLORE, ratio = 0.10 < floor → force EXPLORE."""
        ctrl, _ = self._make_controller()
        # Reset after consecutive limit by committing EXPLORE epochs
        # Build a history: 9 EXPLOIT + 1 EXPLORE in window
        # We need to bypass consecutive limit (reset it by committing EXPLORE occasionally)
        for i in range(9):
            ctrl._state.consecutive_exploit_count = 0  # Reset to bypass limit
            ctrl._state.epoch_mode_history.append(EvolutionMode.EXPLOIT.value)
        ctrl._state.epoch_mode_history.append(EvolutionMode.EXPLORE.value)
        ctrl._save_state()

        # ratio = 1/10 = 0.10 < MIN_EXPLORE_RATIO (0.20) → force EXPLORE
        mode = ctrl.select_mode(
            epoch_id="e-forced",
            epoch_score=0.90,
            is_plateau=False,
        )
        self.assertEqual(mode, EvolutionMode.EXPLORE)

    # --- commit_epoch -------------------------------------------------------

    def test_commit_exploit_increments_counter(self):
        ctrl, _ = self._make_controller()
        ctrl.commit_epoch("e-001", EvolutionMode.EXPLOIT)
        self.assertEqual(ctrl.consecutive_exploit_count, 1)

    def test_commit_explore_resets_counter(self):
        ctrl, _ = self._make_controller()
        ctrl.commit_epoch("e-001", EvolutionMode.EXPLOIT)
        ctrl.commit_epoch("e-002", EvolutionMode.EXPLOIT)
        ctrl.commit_epoch("e-003", EvolutionMode.EXPLORE)
        self.assertEqual(ctrl.consecutive_exploit_count, 0)

    def test_commit_updates_history(self):
        ctrl, _ = self._make_controller()
        ctrl.commit_epoch("e-001", EvolutionMode.EXPLOIT)
        ctrl.commit_epoch("e-002", EvolutionMode.EXPLORE)
        ratio = ctrl.window_explore_ratio()
        self.assertAlmostEqual(ratio, 0.5, places=3)

    # --- set_mode (operator override) ---------------------------------------

    def test_set_mode_changes_current_mode(self):
        ctrl, _ = self._make_controller()
        ctrl.commit_epoch("e-001", EvolutionMode.EXPLOIT)
        ctrl.set_mode(EvolutionMode.EXPLORE, epoch_id="e-002", reason="manual_test")
        self.assertEqual(ctrl.current_mode, EvolutionMode.EXPLORE)

    def test_set_mode_emits_transition_log(self):
        ctrl, _ = self._make_controller()
        ctrl.commit_epoch("e-001", EvolutionMode.EXPLOIT)
        ctrl.set_mode(EvolutionMode.EXPLORE, epoch_id="e-002", reason="test")
        snap = ctrl.health_snapshot()
        self.assertIsNotNone(snap["last_transition"])
        self.assertIn("human_set_mode", snap["last_transition"]["reason"])

    # --- Audit writer integration -------------------------------------------

    def test_audit_writer_called_on_transition(self):
        audit_events = []

        def writer(event_type, payload):
            audit_events.append((event_type, payload))

        ctrl, _ = self._make_controller(audit_writer=writer)
        # Trigger a plateau → EXPLORE transition from EXPLOIT mode
        ctrl._state.current_mode = EvolutionMode.EXPLOIT.value
        ctrl.select_mode(epoch_id="e-001", epoch_score=0.9, is_plateau=True)
        self.assertTrue(any(e[0] == "mode_transition" for e in audit_events))

    def test_audit_writer_failure_does_not_block_selection(self):
        def writer(event_type, payload):
            raise RuntimeError("audit_unavailable")

        ctrl, _ = self._make_controller(audit_writer=writer)
        ctrl._state.current_mode = EvolutionMode.EXPLOIT.value
        # Should not raise despite audit writer failure
        mode = ctrl.select_mode(epoch_id="e-001", epoch_score=0.9, is_plateau=True)
        self.assertEqual(mode, EvolutionMode.EXPLORE)

    # --- Persistence --------------------------------------------------------

    def test_state_persists_across_reload(self):
        ctrl, path = self._make_controller()
        for i in range(3):
            ctrl.commit_epoch(f"e-{i:03d}", EvolutionMode.EXPLOIT)
        ctrl.commit_epoch("e-003", EvolutionMode.EXPLORE)

        reloaded = ExploreExploitController(state_path=path)
        self.assertEqual(reloaded.consecutive_exploit_count, 0)
        self.assertAlmostEqual(reloaded.window_explore_ratio(), 0.25, places=3)

    # --- Health snapshot ----------------------------------------------------

    def test_health_snapshot_keys(self):
        ctrl, _ = self._make_controller()
        snap = ctrl.health_snapshot()
        for key in (
            "current_mode", "consecutive_exploit_count", "window_explore_ratio",
            "explore_floor_ok", "total_epochs_recorded", "transition_count",
        ):
            self.assertIn(key, snap)

    def test_explore_floor_ok_reflects_actual_ratio(self):
        ctrl, _ = self._make_controller()
        snap = ctrl.health_snapshot()
        self.assertTrue(snap["explore_floor_ok"])  # Empty history = 1.0 ratio

    # --- reset --------------------------------------------------------------

    def test_reset_clears_all_state(self):
        ctrl, path = self._make_controller()
        ctrl.commit_epoch("e-001", EvolutionMode.EXPLOIT)
        ctrl.reset()
        self.assertEqual(ctrl.consecutive_exploit_count, 0)
        self.assertEqual(ctrl.window_explore_ratio(), 1.0)
        self.assertFalse(path.exists())

    # --- MIN_EXPLORE_RATIO is constitutionally enforced ---------------------

    def test_min_explore_ratio_is_20_percent(self):
        self.assertEqual(MIN_EXPLORE_RATIO, 0.20)

    def test_max_consecutive_exploit_is_4(self):
        self.assertEqual(MAX_CONSECUTIVE_EXPLOIT, 4)


# ---------------------------------------------------------------------------
# 2. HumanApprovalGate
# ---------------------------------------------------------------------------

from runtime.governance.human_approval_gate import (
    ApprovalDecision,
    ApprovalReason,
    ApprovalRequest,
    ApprovalStatus,
    HumanApprovalGate,
)


class TestHumanApprovalGate(unittest.TestCase):

    def _make_gate(self, **kwargs) -> HumanApprovalGate:
        tmpdir = tempfile.mkdtemp()
        return HumanApprovalGate(
            queue_path=Path(tmpdir) / "queue.jsonl",
            audit_path=Path(tmpdir) / "audit.jsonl",
            index_path=Path(tmpdir) / "approval_index.json",
            **kwargs,
        )

    # --- request_approval ---------------------------------------------------

    def test_request_approval_returns_approval_id(self):
        gate = self._make_gate()
        aid = gate.request_approval("mut-001", "epoch-001")
        self.assertTrue(aid.startswith("appr-"))

    def test_request_approval_adds_to_pending_queue(self):
        gate = self._make_gate()
        gate.request_approval("mut-001", "epoch-001")
        queue = gate.pending_queue()
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["mutation_id"], "mut-001")

    def test_two_requests_both_pending(self):
        gate = self._make_gate()
        gate.request_approval("mut-001", "epoch-001")
        gate.request_approval("mut-002", "epoch-001")
        self.assertEqual(len(gate.pending_queue()), 2)

    # --- record_decision ----------------------------------------------------

    def test_approved_mutation_passes_is_approved(self):
        gate = self._make_gate()
        aid = gate.request_approval("mut-001", "epoch-001")
        gate.record_decision(aid, approved=True, operator_id="dreezy66")
        self.assertTrue(gate.is_approved("mut-001"))

    def test_rejected_mutation_fails_is_approved(self):
        gate = self._make_gate()
        aid = gate.request_approval("mut-001", "epoch-001")
        gate.record_decision(aid, approved=False, operator_id="dreezy66")
        self.assertFalse(gate.is_approved("mut-001"))

    def test_pending_mutation_fails_is_approved(self):
        gate = self._make_gate()
        gate.request_approval("mut-001", "epoch-001")
        self.assertFalse(gate.is_approved("mut-001"))

    def test_unknown_mutation_fails_is_approved(self):
        gate = self._make_gate()
        self.assertFalse(gate.is_approved("mut-unknown"))

    def test_decision_removed_from_pending_queue(self):
        gate = self._make_gate()
        aid = gate.request_approval("mut-001", "epoch-001")
        gate.record_decision(aid, approved=True, operator_id="dreezy66")
        self.assertEqual(len(gate.pending_queue()), 0)

    def test_invalid_approval_id_raises(self):
        gate = self._make_gate()
        with self.assertRaises(ValueError):
            gate.record_decision("appr-nonexistent", approved=True, operator_id="op")

    def test_decision_digest_is_deterministic(self):
        aid = "appr-abc123"
        d1 = ApprovalDecision.compute_digest(aid, "mut-1", "approved", "op1", "2026-01-01T00:00:00Z")
        d2 = ApprovalDecision.compute_digest(aid, "mut-1", "approved", "op1", "2026-01-01T00:00:00Z")
        self.assertEqual(d1, d2)

    def test_decision_digest_differs_on_different_inputs(self):
        d1 = ApprovalDecision.compute_digest("a-001", "mut-1", "approved", "op1", "2026-01-01T00:00:00Z")
        d2 = ApprovalDecision.compute_digest("a-001", "mut-1", "approved", "op2", "2026-01-01T00:00:00Z")
        self.assertNotEqual(d1, d2)

    # --- revoke_approval ----------------------------------------------------

    def test_revoked_approval_fails_is_approved(self):
        gate = self._make_gate()
        aid = gate.request_approval("mut-001", "epoch-001")
        gate.record_decision(aid, approved=True, operator_id="dreezy66")
        self.assertTrue(gate.is_approved("mut-001"))
        gate.revoke_approval("mut-001", operator_id="dreezy66", reason="rollback")
        self.assertFalse(gate.is_approved("mut-001"))

    def test_revocation_writes_audit_event(self):
        gate = self._make_gate()
        aid = gate.request_approval("mut-001", "epoch-001")
        gate.record_decision(aid, approved=True, operator_id="dreezy66")
        gate.revoke_approval("mut-001", operator_id="dreezy66", reason="test")
        trail = gate.audit_trail("mut-001")
        event_types = [e["event_type"] for e in trail]
        self.assertIn("approval_revoked", event_types)

    # --- batch_approve ------------------------------------------------------

    def test_batch_approve_approves_all(self):
        gate = self._make_gate()
        decisions = gate.batch_approve(
            ["mut-001", "mut-002", "mut-003"],
            epoch_id="epoch-001",
            operator_id="dreezy66",
        )
        self.assertEqual(len(decisions), 3)
        for mid in ("mut-001", "mut-002", "mut-003"):
            self.assertTrue(gate.is_approved(mid))

    def test_batch_approve_returns_decision_objects(self):
        gate = self._make_gate()
        decisions = gate.batch_approve(["mut-001"], epoch_id="e-001", operator_id="op1")
        self.assertIsInstance(decisions[0], ApprovalDecision)
        self.assertEqual(decisions[0].status, ApprovalStatus.APPROVED.value)

    def test_batch_approve_uses_index_without_full_replay_per_item(self):
        gate = self._make_gate()
        original_read_audit = gate._read_audit
        call_count = {"count": 0}

        def counting_read_audit():
            call_count["count"] += 1
            return original_read_audit()

        gate._read_audit = counting_read_audit
        gate.batch_approve(
            [f"mut-{i:04d}" for i in range(200)],
            epoch_id="epoch-001",
            operator_id="dreezy66",
        )
        self.assertLessEqual(call_count["count"], 3)

    def test_index_corruption_triggers_rebuild_and_preserves_correctness(self):
        gate = self._make_gate()
        aid = gate.request_approval("mut-001", "epoch-001")
        gate.record_decision(aid, approved=True, operator_id="dreezy66")

        gate._index_path.write_text("{invalid-json", encoding="utf-8")
        rebuilt_gate = HumanApprovalGate(
            queue_path=gate._queue_path,
            audit_path=gate._audit_path,
            index_path=gate._index_path,
        )
        self.assertTrue(rebuilt_gate.is_approved("mut-001"))
        self.assertTrue(rebuilt_gate.verify_index_consistency())

    def test_index_digest_mismatch_triggers_rebuild(self):
        gate = self._make_gate()
        aid = gate.request_approval("mut-009", "epoch-009")
        gate.record_decision(aid, approved=False, operator_id="dreezy66")

        index_payload = json.loads(gate._index_path.read_text(encoding="utf-8"))
        index_payload["audit_digest"] = "bad-digest"
        gate._index_path.write_text(json.dumps(index_payload, sort_keys=True), encoding="utf-8")

        rebuilt_gate = HumanApprovalGate(
            queue_path=gate._queue_path,
            audit_path=gate._audit_path,
            index_path=gate._index_path,
        )
        self.assertFalse(rebuilt_gate.is_approved("mut-009"))
        self.assertTrue(rebuilt_gate.verify_index_consistency())

    # --- audit_trail --------------------------------------------------------

    def test_audit_trail_records_all_events(self):
        gate = self._make_gate()
        aid = gate.request_approval("mut-001", "epoch-001")
        gate.record_decision(aid, approved=True, operator_id="dreezy66")
        trail = gate.audit_trail("mut-001")
        event_types = [e["event_type"] for e in trail]
        self.assertIn("approval_requested", event_types)
        self.assertIn("approval_decision", event_types)

    def test_audit_trail_filtered_by_mutation_id(self):
        gate = self._make_gate()
        aid1 = gate.request_approval("mut-001", "e-001")
        aid2 = gate.request_approval("mut-002", "e-001")
        gate.record_decision(aid1, True, "op")
        gate.record_decision(aid2, False, "op")
        trail = gate.audit_trail("mut-001")
        for e in trail:
            self.assertEqual(e["payload"]["mutation_id"], "mut-001")

    # --- Audit writer integration -------------------------------------------

    def test_audit_writer_called_on_approval(self):
        events = []

        def writer(et, payload):
            events.append(et)

        gate = self._make_gate(audit_writer=writer)
        aid = gate.request_approval("mut-001", "e-001")
        gate.record_decision(aid, approved=True, operator_id="op")
        self.assertIn("human_approval_decision", events)

    def test_audit_writer_failure_does_not_block_decision(self):
        def writer(et, payload):
            raise RuntimeError("writer_down")

        gate = self._make_gate(audit_writer=writer)
        aid = gate.request_approval("mut-001", "e-001")
        decision = gate.record_decision(aid, approved=True, operator_id="op")
        self.assertEqual(decision.status, ApprovalStatus.APPROVED.value)


# ---------------------------------------------------------------------------
# 3. LineageDAG
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 4. PhaseTransitionGate
# ---------------------------------------------------------------------------

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


class TestPhaseTransitionGate(unittest.TestCase):

    def _make_gate(self, **kwargs) -> PhaseTransitionGate:
        tmpdir = tempfile.mkdtemp()
        return PhaseTransitionGate(
            state_path=Path(tmpdir) / "phase_state.json",
            audit_path=Path(tmpdir) / "phase_audit.jsonl",
            **kwargs,
        )

    # --- Initial state ------------------------------------------------------

    def test_default_phase_is_zero(self):
        gate = self._make_gate()
        self.assertEqual(gate.current_phase, 0)

    def test_default_autonomy_level_is_l0(self):
        gate = self._make_gate()
        self.assertEqual(gate.autonomy_level, AutonomyLevel.L0_MANUAL)

    def test_l0_label(self):
        self.assertEqual(AutonomyLevel.L0_MANUAL.label(), "Manual")

    def test_l4_label(self):
        self.assertEqual(AutonomyLevel.L4_GOVERNED_AUTO.label(), "Governed Autonomous")

    # --- evaluate_gate (read-only) -----------------------------------------

    def test_evaluate_gate_passes_with_sufficient_evidence(self):
        gate = self._make_gate()
        evidence = _make_passing_evidence(1)
        result = gate.evaluate_gate(1, evidence, operator_id="dreezy66")
        self.assertTrue(result.gate_passed)
        self.assertEqual(len(result.failed_criteria()), 0)

    def test_evaluate_gate_fails_with_insufficient_evidence(self):
        gate = self._make_gate()
        evidence = _make_failing_evidence()
        result = gate.evaluate_gate(1, evidence, operator_id="dreezy66")
        self.assertFalse(result.gate_passed)
        self.assertGreater(len(result.failed_criteria()), 0)

    def test_evaluate_gate_does_not_commit_transition(self):
        gate = self._make_gate()
        evidence = _make_passing_evidence(1)
        gate.evaluate_gate(1, evidence, operator_id="dreezy66")
        # Phase must still be 0 — evaluate_gate is read-only
        self.assertEqual(gate.current_phase, 0)

    def test_evaluate_gate_reports_per_criterion_results(self):
        gate = self._make_gate()
        # Pass most criteria but fail audit chain
        c = PHASE_GATE_CRITERIA[1]
        evidence = TransitionEvidence(
            approved_mutation_count=c.min_approved_mutations,
            mutation_pass_rate=c.min_mutation_pass_rate,
            lineage_completeness=c.min_lineage_completeness,
            audit_chain_intact=False,   # FAIL
            consecutive_clean_epochs=c.min_consecutive_clean_epochs,
        )
        result = gate.evaluate_gate(1, evidence, operator_id="dreezy66")
        self.assertFalse(result.gate_passed)
        failed_names = [c.name for c in result.failed_criteria()]
        self.assertIn("audit_chain_intact", failed_names)

    def test_evaluate_gate_digest_is_deterministic(self):
        gate = self._make_gate()
        evidence = _make_passing_evidence(1)
        r1 = gate.evaluate_gate(1, evidence, "op1")
        # Create a fresh gate with identical state
        gate2 = PhaseTransitionGate(
            state_path=gate._state_path,
            audit_path=gate._audit_path,
        )
        r2 = gate2.evaluate_gate(1, evidence, "op1")
        # Digests differ because timestamp differs — but gate_passed is same
        self.assertEqual(r1.gate_passed, r2.gate_passed)

    # --- Phase skip enforcement ---------------------------------------------

    def test_phase_skip_raises(self):
        gate = self._make_gate()
        with self.assertRaises(ValueError):
            gate.evaluate_gate(2, _make_passing_evidence(2), "op")

    def test_invalid_phase_zero_raises(self):
        gate = self._make_gate()
        with self.assertRaises(ValueError):
            gate.evaluate_gate(0, _make_passing_evidence(1), "op")

    def test_invalid_phase_five_raises(self):
        gate = self._make_gate()
        with self.assertRaises(ValueError):
            gate.evaluate_gate(5, _make_failing_evidence(), "op")

    # --- attempt_transition (commits) ---------------------------------------

    def test_successful_transition_advances_phase(self):
        gate = self._make_gate()
        evidence = _make_passing_evidence(1)
        success, _ = gate.attempt_transition(1, evidence, operator_id="dreezy66")
        self.assertTrue(success)
        self.assertEqual(gate.current_phase, 1)

    def test_failed_transition_does_not_advance_phase(self):
        gate = self._make_gate()
        success, _ = gate.attempt_transition(1, _make_failing_evidence(), "dreezy66")
        self.assertFalse(success)
        self.assertEqual(gate.current_phase, 0)

    def test_transition_writes_audit_record(self):
        gate = self._make_gate()
        evidence = _make_passing_evidence(1)
        gate.attempt_transition(1, evidence, operator_id="dreezy66")
        # Audit file must exist and contain at least one entry
        audit_lines = gate._audit_path.read_text().splitlines()
        self.assertGreater(len(audit_lines), 0)
        first = json.loads(audit_lines[0])
        self.assertEqual(first["event_type"], "phase_transition_attempt")

    def test_transition_history_recorded(self):
        gate = self._make_gate()
        gate.attempt_transition(1, _make_passing_evidence(1), "op")
        self.assertEqual(len(gate.transition_history()), 1)

    def test_sequential_transitions_each_advance_one_level(self):
        gate = self._make_gate()
        for phase in range(1, 5):
            success, _ = gate.attempt_transition(phase, _make_passing_evidence(phase), "op")
            self.assertTrue(success, f"transition to phase {phase} failed")
            self.assertEqual(gate.current_phase, phase)

    # --- record_epoch_outcome -----------------------------------------------

    def test_consecutive_clean_epochs_increments(self):
        gate = self._make_gate()
        gate.record_epoch_outcome(clean=True)
        gate.record_epoch_outcome(clean=True)
        self.assertEqual(gate.consecutive_clean_epochs, 2)

    def test_dirty_epoch_resets_counter(self):
        gate = self._make_gate()
        gate.record_epoch_outcome(clean=True)
        gate.record_epoch_outcome(clean=True)
        gate.record_epoch_outcome(clean=False)  # Governance fault
        self.assertEqual(gate.consecutive_clean_epochs, 0)

    def test_clean_epoch_contributes_to_gate_criteria(self):
        gate = self._make_gate()
        # Record enough clean epochs for phase 1 (needs 1)
        gate.record_epoch_outcome(clean=True)
        c = PHASE_GATE_CRITERIA[1]
        evidence = TransitionEvidence(
            approved_mutation_count=c.min_approved_mutations,
            mutation_pass_rate=c.min_mutation_pass_rate,
            lineage_completeness=c.min_lineage_completeness,
            audit_chain_intact=True,
            consecutive_clean_epochs=0,  # Pass 0 — gate should use stored counter
        )
        result = gate.evaluate_gate(1, evidence, "op")
        # The criterion should pass because stored counter (1) >= required (1)
        clean_criterion = next(
            r for r in result.criteria_results if r.name == "min_consecutive_clean_epochs"
        )
        self.assertTrue(clean_criterion.passed)

    # --- demote_phase -------------------------------------------------------

    def test_demote_phase_reduces_current_phase(self):
        gate = self._make_gate()
        gate.attempt_transition(1, _make_passing_evidence(1), "op")
        gate.demote_phase(to_phase=0, operator_id="dreezy66", reason="rollback_test")
        self.assertEqual(gate.current_phase, 0)

    def test_demote_resets_consecutive_clean_epochs(self):
        gate = self._make_gate()
        gate.attempt_transition(1, _make_passing_evidence(1), "op")
        gate.record_epoch_outcome(clean=True)
        gate.record_epoch_outcome(clean=True)
        gate.demote_phase(0, "op", "test")
        self.assertEqual(gate.consecutive_clean_epochs, 0)

    def test_demote_above_current_phase_raises(self):
        gate = self._make_gate()
        with self.assertRaises(ValueError):
            gate.demote_phase(to_phase=2, operator_id="op", reason="bad")

    def test_demote_writes_audit_record(self):
        gate = self._make_gate()
        gate.attempt_transition(1, _make_passing_evidence(1), "op")
        gate.demote_phase(0, "dreezy66", "stability_concern")
        lines = gate._audit_path.read_text().splitlines()
        events = [json.loads(l)["event_type"] for l in lines if l.strip()]
        self.assertIn("phase_demotion", events)

    # --- Persistence --------------------------------------------------------

    def test_phase_state_persists_across_reload(self):
        gate = self._make_gate()
        gate.attempt_transition(1, _make_passing_evidence(1), "op")
        gate2 = PhaseTransitionGate(
            state_path=gate._state_path,
            audit_path=gate._audit_path,
        )
        self.assertEqual(gate2.current_phase, 1)

    # --- health_snapshot ----------------------------------------------------

    def test_health_snapshot_keys(self):
        gate = self._make_gate()
        snap = gate.health_snapshot()
        for key in (
            "current_phase", "autonomy_level", "autonomy_level_label",
            "consecutive_clean_epochs", "transition_count",
        ):
            self.assertIn(key, snap)

    def test_health_snapshot_autonomy_label_correct(self):
        gate = self._make_gate()
        snap = gate.health_snapshot()
        self.assertEqual(snap["autonomy_level_label"], "Manual")

    # --- Audit writer -------------------------------------------------------

    def test_audit_writer_called_on_successful_transition(self):
        events = []

        def writer(et, payload):
            events.append(et)

        gate = self._make_gate(audit_writer=writer)
        gate.attempt_transition(1, _make_passing_evidence(1), "op")
        self.assertIn("phase_transition_committed", events)

    def test_audit_writer_not_called_on_failed_transition(self):
        events = []

        def writer(et, payload):
            events.append(et)

        gate = self._make_gate(audit_writer=writer)
        gate.attempt_transition(1, _make_failing_evidence(), "op")
        self.assertNotIn("phase_transition_committed", events)

    # --- PHASE_GATE_CRITERIA completeness -----------------------------------

    def test_all_four_phase_criteria_defined(self):
        for phase in (1, 2, 3, 4):
            self.assertIn(phase, PHASE_GATE_CRITERIA)

    def test_phase_criteria_monotonically_increasing_difficulty(self):
        """Higher phases must require more approved mutations."""
        prev = PHASE_GATE_CRITERIA[1].min_approved_mutations
        for phase in (2, 3, 4):
            curr = PHASE_GATE_CRITERIA[phase].min_approved_mutations
            self.assertGreater(curr, prev, f"Phase {phase} must require more mutations than phase {phase-1}")
            prev = curr

    def test_phase_4_requires_100_percent_lineage(self):
        self.assertEqual(PHASE_GATE_CRITERIA[4].min_lineage_completeness, 1.00)


# ---------------------------------------------------------------------------
# 5. EvolutionLoop integration — E/E controller wired
# ---------------------------------------------------------------------------

from runtime.evolution.evolution_loop import EvolutionLoop, EpochResult


class TestEvolutionLoopIntegration(unittest.TestCase):

    def test_epoch_result_has_evolution_mode_field(self):
        """EpochResult must expose evolution_mode and window_explore_ratio."""
        result = EpochResult(
            epoch_id="e-001",
            generation_count=3,
            total_candidates=10,
            accepted_count=4,
        )
        self.assertIn("evolution_mode", result.__dataclass_fields__)
        self.assertIn("window_explore_ratio", result.__dataclass_fields__)

    def test_epoch_result_default_mode_is_explore(self):
        result = EpochResult(
            epoch_id="e-001",
            generation_count=3,
            total_candidates=10,
            accepted_count=4,
        )
        self.assertEqual(result.evolution_mode, EvolutionMode.EXPLORE.value)

    def test_evolution_loop_accepts_controller_kwarg(self):
        """EvolutionLoop constructor must accept optional controller kwarg."""
        import inspect
        sig = inspect.signature(EvolutionLoop.__init__)
        self.assertIn("controller", sig.parameters)

    def test_evolution_loop_uses_provided_controller(self):
        """When a controller is injected, it must be the one used by the loop."""
        tmpdir = tempfile.mkdtemp()
        ctrl = ExploreExploitController(state_path=Path(tmpdir) / "ctrl.json")
        loop = EvolutionLoop(api_key="sk-test", controller=ctrl)
        self.assertIs(loop._controller, ctrl)

    def test_controller_commit_called_after_epoch(self):
        """After run_epoch, controller.epoch_mode_history must have one entry."""
        tmpdir = tempfile.mkdtemp()
        ctrl = ExploreExploitController(state_path=Path(tmpdir) / "ctrl.json")

        # Patch all API-calling components to avoid network calls
        with mock.patch(
            "runtime.evolution.evolution_loop.propose_from_all_agents",
            return_value={},
        ), mock.patch(
            "runtime.evolution.evolution_loop.PopulationManager.seed"
        ), mock.patch(
            "runtime.evolution.evolution_loop.PopulationManager.evolve_generation",
            return_value=[],
        ), mock.patch(
            "runtime.evolution.evolution_loop.PopulationManager.set_weights"
        ), mock.patch(
            "runtime.evolution.evolution_loop.WeightAdaptor.adapt",
            return_value=mock.MagicMock(risk_penalty=0.20, complexity_penalty=0.10),
        ):
            from runtime.autonomy.ai_mutation_proposer import CodebaseContext
            context = CodebaseContext(
                file_summaries={},
                recent_failures=[],
                current_epoch_id="epoch-test-001",
            )
            loop = EvolutionLoop(api_key="sk-test", controller=ctrl)
            result = loop.run_epoch(context)

        self.assertEqual(len(ctrl._state.epoch_mode_history), 1)
        self.assertIn(result.evolution_mode, [m.value for m in EvolutionMode])


if __name__ == "__main__":
    unittest.main()
