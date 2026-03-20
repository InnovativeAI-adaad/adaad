# SPDX-License-Identifier: Apache-2.0
"""Phase 79 — Multi-Generation Lineage Graph constitutional tests.

MULTIGEN-0, MULTIGEN-ACYC-0, MULTIGEN-DETERM-0, MULTIGEN-REPLAY-0, MULTIGEN-ISOLATE-0
"""
from __future__ import annotations
import pathlib
import pytest
from runtime.evolution.multi_gen_lineage import (
    GenerationNode, GenerationEdge, MultiGenLineageGraph, produce_lineage_evidence,
)
from runtime.evolution.lineage_v2 import LineageLedgerV2


def _node(epoch_id, phase=77, generation=0, parent_ids=frozenset(), seed_id=None, outcome="success"):
    return GenerationNode(
        epoch_id=epoch_id, phase=phase, version="9.13.0", outcome=outcome,
        ledger_hash="sha256:abc", generation=generation,
        parent_ids=frozenset(parent_ids), seed_id=seed_id,
    )


class TestGenerationNode:
    def test_root_node_has_no_parents(self):
        n = _node("ep-001")
        assert n.is_root() is True
        assert len(n.parent_ids) == 0

    def test_child_node_has_parent(self):
        n = _node("ep-002", parent_ids={"ep-001"}, generation=1)
        assert n.is_root() is False
        assert "ep-001" in n.parent_ids

    def test_node_digest_is_deterministic(self):
        n = _node("ep-det")
        assert n.node_digest == n.node_digest
        # Same params → same digest
        n2 = _node("ep-det")
        assert n.node_digest == n2.node_digest

    def test_different_nodes_have_different_digests(self):
        assert _node("ep-001").node_digest != _node("ep-002").node_digest

    def test_seed_driven_flag(self):
        assert _node("ep-s", seed_id="seed-001").is_seed_driven()
        assert not _node("ep-n").is_seed_driven()


class TestMultiGenLineageGraph:
    """MULTIGEN-0, MULTIGEN-ACYC-0, MULTIGEN-DETERM-0, MULTIGEN-ISOLATE-0"""

    def test_empty_graph(self):
        g = MultiGenLineageGraph()
        assert len(g.nodes()) == 0
        assert g.max_generation() == 0
        assert g.roots() == []

    def test_register_single_root(self):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001"))
        assert len(g.nodes()) == 1
        assert g.roots()[0].epoch_id == "ep-001"

    def test_register_parent_child(self):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001"))
        g.register_node(_node("ep-002", parent_ids={"ep-001"}, generation=1))
        assert len(g.nodes()) == 2
        assert len(g.children("ep-001")) == 1
        assert g.children("ep-001")[0].epoch_id == "ep-002"

    def test_register_is_idempotent(self):
        g = MultiGenLineageGraph()
        n = _node("ep-001")
        g.register_node(n)
        g.register_node(n)  # second register — no-op
        assert len(g.nodes()) == 1

    def test_ancestor_path_linear_chain(self):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001", generation=0))
        g.register_node(_node("ep-002", generation=1, parent_ids={"ep-001"}))
        g.register_node(_node("ep-003", generation=2, parent_ids={"ep-002"}))
        path = g.ancestor_path("ep-003")
        assert [n.epoch_id for n in path] == ["ep-001", "ep-002", "ep-003"]

    def test_ancestor_path_unknown_epoch(self):
        g = MultiGenLineageGraph()
        assert g.ancestor_path("nonexistent") == []

    def test_descendant_set(self):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001"))
        g.register_node(_node("ep-002", parent_ids={"ep-001"}, generation=1))
        g.register_node(_node("ep-003", parent_ids={"ep-001"}, generation=1))
        g.register_node(_node("ep-004", parent_ids={"ep-002"}, generation=2))
        desc = g.descendant_set("ep-001")
        assert desc == frozenset({"ep-002", "ep-003", "ep-004"})

    def test_leaves(self):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001"))
        g.register_node(_node("ep-002", parent_ids={"ep-001"}, generation=1))
        leaves = g.leaves()
        assert len(leaves) == 1
        assert leaves[0].epoch_id == "ep-002"

    def test_max_generation(self):
        g = MultiGenLineageGraph()
        for i in range(5):
            pids = {f"ep-{i-1:03d}"} if i > 0 else frozenset()
            g.register_node(_node(f"ep-{i:03d}", generation=i, parent_ids=pids))
        assert g.max_generation() == 4

    def test_graph_digest_is_deterministic(self):
        """MULTIGEN-DETERM-0: same nodes → same digest."""
        g1, g2 = MultiGenLineageGraph(), MultiGenLineageGraph()
        for g in (g1, g2):
            g.register_node(_node("ep-001"))
            g.register_node(_node("ep-002", parent_ids={"ep-001"}, generation=1))
        assert g1.graph_digest() == g2.graph_digest()

    def test_graph_digest_changes_on_new_node(self):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001"))
        d1 = g.graph_digest()
        g.register_node(_node("ep-002", parent_ids={"ep-001"}, generation=1))
        d2 = g.graph_digest()
        assert d1 != d2

    def test_instances_are_isolated(self):
        """MULTIGEN-ISOLATE-0: no shared module state between instances."""
        g1, g2 = MultiGenLineageGraph(), MultiGenLineageGraph()
        g1.register_node(_node("ep-only-g1"))
        assert g2.node("ep-only-g1") is None

    def test_seed_driven_nodes(self):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001"))
        g.register_node(_node("ep-seed", seed_id="seed-phase77-001", generation=1, parent_ids={"ep-001"}))
        seeds = g.seed_driven_nodes()
        assert len(seeds) == 1
        assert seeds[0].epoch_id == "ep-seed"

    def test_generation_summary(self):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001", generation=0))
        g.register_node(_node("ep-002", generation=1, parent_ids={"ep-001"}))
        g.register_node(_node("ep-003", generation=1, parent_ids={"ep-001"}))
        summary = g.generation_summary()
        assert summary == {0: 1, 1: 2}

    def test_to_dict_structure(self):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001"))
        d = g.to_dict()
        assert d["node_count"] == 1
        assert "graph_digest" in d
        assert "nodes" in d
        assert d["nodes"][0]["epoch_id"] == "ep-001"


class TestMultiGenFromLedger:
    """MULTIGEN-REPLAY-0: graph fully reconstructable from ledger."""

    def test_from_empty_ledger(self, tmp_path):
        l = LineageLedgerV2(ledger_path=tmp_path / "e.jsonl")
        g = MultiGenLineageGraph.from_ledger(l)
        assert len(g.nodes()) == 0

    def test_from_ledger_with_epoch_events(self, tmp_path):
        l = LineageLedgerV2(ledger_path=tmp_path / "l.jsonl")
        l.append_event("EpochComplete", {"epoch_id": "ep-001", "outcome": "success", "phase": 77})
        l.append_event("EpochComplete", {"epoch_id": "ep-002", "outcome": "success", "phase": 78,
                                          "parent_epoch_id": "ep-001"})
        g = MultiGenLineageGraph.from_ledger(l)
        assert len(g.nodes()) == 2
        ep2 = g.node("ep-002")
        assert ep2 is not None
        assert "ep-001" in ep2.parent_ids

    def test_from_ledger_seed_epoch(self, tmp_path):
        l = LineageLedgerV2(ledger_path=tmp_path / "seed.jsonl")
        l.append_event("SeedCELOutcomeEvent", {
            "epoch_id": "phase77-ep-001", "seed_id": "seed-gov-001",
            "outcome_status": "success", "cycle_id": "cyc-001",
        })
        g = MultiGenLineageGraph.from_ledger(l)
        nodes = g.nodes()
        assert len(nodes) == 1
        assert nodes[0].seed_id == "seed-gov-001"
        assert nodes[0].is_seed_driven()

    def test_ledger_replay_produces_identical_graph(self, tmp_path):
        """MULTIGEN-REPLAY-0 + MULTIGEN-DETERM-0: replaying same ledger gives same digest."""
        p = tmp_path / "replay.jsonl"
        l = LineageLedgerV2(ledger_path=p)
        for i in range(5):
            l.append_event("EpochComplete", {
                "epoch_id": f"ep-{i:03d}", "outcome": "success", "phase": 77 + i,
                **({"parent_epoch_id": f"ep-{i-1:03d}"} if i > 0 else {}),
            })
        g1 = MultiGenLineageGraph.from_ledger(l)
        g2 = MultiGenLineageGraph.from_ledger(LineageLedgerV2(ledger_path=p))
        assert g1.graph_digest() == g2.graph_digest()


class TestEvidenceArtifact:
    def test_produce_evidence_returns_dict(self):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001"))
        ev = produce_lineage_evidence(g)
        assert ev["schema"] == "MultiGenLineageEvidence/1.0"
        assert "graph" in ev

    def test_produce_evidence_writes_artifact(self, tmp_path):
        g = MultiGenLineageGraph()
        g.register_node(_node("ep-001"))
        path = tmp_path / "phase79" / "lineage_evidence.json"
        produce_lineage_evidence(g, artifact_path=path)
        assert path.exists()
        import json
        data = json.loads(path.read_text())
        assert data["graph"]["node_count"] == 1
