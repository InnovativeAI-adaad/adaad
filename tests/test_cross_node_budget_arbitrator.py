# SPDX-License-Identifier: Apache-2.0
"""Tests for CrossNodeBudgetArbitrator — ADAAD-14 PR-14-02.

Coverage
--------
- TestPeerFitnessReport        (3 tests) — freshness, staleness, parse
- TestClusterArbitrationResult (3 tests) — effective_evictions, quorum gating
- TestCrossNodeBudgetBroadcast (4 tests) — broadcast fitness, broadcast error, gossip payload
- TestCrossNodeBudgetIngest    (5 tests) — absorb peer fitness, echo filter, stale discard, malformed
- TestCrossNodeArbitrateCluster(7 tests) — merge scores, quorum gate, eviction block, lineage digest
"""
from __future__ import annotations

import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, call

from runtime.evolution.budget.arbitrator import ArbitrationResult, BudgetArbitrator
from runtime.evolution.budget.pool import AgentBudgetPool
from runtime.evolution.budget.cross_node_arbitrator import (
    ClusterArbitrationResult,
    CrossNodeBudgetArbitrator,
    FederationBudgetGossip,
    PeerFitnessReport,
    _BUDGET_GOSSIP_EVENT_TYPE,
    _MAX_PEER_FITNESS_AGE_S,
)
from runtime.governance.federation.peer_discovery import GossipEvent, PeerRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pool(agents=("agent-1", "agent-2", "agent-3")) -> AgentBudgetPool:
    shares = {a: 1.0 / len(agents) for a in agents}
    return AgentBudgetPool(total_budget=1000.0, initial_shares=shares)


def _arbitrator(pool: Optional[AgentBudgetPool] = None) -> BudgetArbitrator:
    return BudgetArbitrator(pool=pool or _pool(), temperature=1.0, eviction_starvation_count=2)


def _peer_fitness_report(node_id="node-B", epoch_id="epoch-1",
                          scores=None, age=0.0) -> PeerFitnessReport:
    return PeerFitnessReport(
        node_id=node_id,
        epoch_id=epoch_id,
        scores=scores or {"agent-X": 0.7, "agent-Y": 0.3},
        sampled_at=time.time() - age,
        lineage_digest="sha256:abc",
    )


def _gossip_event(node_id="node-B", epoch_id="epoch-1", scores=None,
                   age=0.0, event_type=_BUDGET_GOSSIP_EVENT_TYPE) -> GossipEvent:
    scores = scores or {"agent-X": 0.7, "agent-Y": 0.3}
    payload = FederationBudgetGossip.fitness_payload(node_id, epoch_id, scores)
    payload["sampled_at"] = time.time() - age
    return GossipEvent(
        event_id=f"g-{node_id}",
        origin_peer_id=node_id,
        event_type=event_type,
        payload={"budget": payload},
        emitted_at=time.time() - age,
        lineage_digest="sha256:evtdig",
    )


def _make_arbitrator(node_id="node-A", pool_agents=("agent-1", "agent-2", "agent-3"),
                      gossip_events=None, peer_alive=True, consensus_quorum=True,
                      require_quorum=True):
    pool = _pool(pool_agents)
    local_arb = _arbitrator(pool)

    peer_registry = MagicMock()
    alive = [PeerRecord("node-B", "http://10.0.0.2:8080", time.time(), time.time())] if peer_alive else []
    peer_registry.alive_peers.return_value = alive

    gossip = MagicMock()
    gossip.pending_events.return_value = gossip_events or []

    consensus = MagicMock()
    consensus.has_quorum.return_value = consensus_quorum

    arb = CrossNodeBudgetArbitrator(
        node_id=node_id,
        local_arbitrator=local_arb,
        peer_registry=peer_registry,
        gossip=gossip,
        require_quorum_for_cluster_eviction=require_quorum,
        consensus_engine=consensus,
    )
    return arb, pool, gossip, consensus


# ---------------------------------------------------------------------------
# TestPeerFitnessReport
# ---------------------------------------------------------------------------

class TestPeerFitnessReport(unittest.TestCase):

    def test_fresh_report(self):
        r = _peer_fitness_report(age=10.0)
        self.assertTrue(r.is_fresh())

    def test_stale_by_age(self):
        r = _peer_fitness_report(age=_MAX_PEER_FITNESS_AGE_S + 5)
        self.assertFalse(r.is_fresh())

    def test_parse_fitness_payload_roundtrip(self):
        payload = FederationBudgetGossip.fitness_payload("node-Z", "epoch-99", {"a-1": 0.9})
        report = FederationBudgetGossip.parse_fitness_payload(payload)
        self.assertIsNotNone(report)
        self.assertEqual(report.node_id, "node-Z")
        self.assertAlmostEqual(report.scores["a-1"], 0.9)


# ---------------------------------------------------------------------------
# TestClusterArbitrationResult
# ---------------------------------------------------------------------------

class TestClusterArbitrationResult(unittest.TestCase):

    def _result(self, evicted, quorum_required, quorum_met) -> ClusterArbitrationResult:
        return ClusterArbitrationResult(
            epoch_id="ep-1", cluster_scores={}, cluster_new_shares={},
            cluster_evicted=evicted, cluster_starved=[],
            contributing_nodes=["node-A"], quorum_required=quorum_required,
            quorum_met=quorum_met, market_scalar=1.0, lineage_digest="sha256:x",
        )

    def test_effective_evictions_no_quorum_required(self):
        r = self._result(["agent-X"], quorum_required=False, quorum_met=None)
        self.assertEqual(r.effective_evictions, ["agent-X"])

    def test_effective_evictions_quorum_met(self):
        r = self._result(["agent-X"], quorum_required=True, quorum_met=True)
        self.assertEqual(r.effective_evictions, ["agent-X"])

    def test_effective_evictions_quorum_not_met_blocks(self):
        r = self._result(["agent-X"], quorum_required=True, quorum_met=False)
        self.assertEqual(r.effective_evictions, [])


# ---------------------------------------------------------------------------
# TestCrossNodeBudgetBroadcast
# ---------------------------------------------------------------------------

class TestCrossNodeBudgetBroadcast(unittest.TestCase):

    def test_broadcast_fitness_calls_gossip(self):
        arb, pool, gossip, _ = _make_arbitrator()
        arb.broadcast_fitness(epoch_id="ep-1", local_scores={"agent-1": 0.8})
        gossip.broadcast.assert_called_once()
        call_payload = gossip.broadcast.call_args[0][0]
        self.assertEqual(call_payload["event_type"], _BUDGET_GOSSIP_EVENT_TYPE)
        self.assertAlmostEqual(call_payload["budget"]["scores"]["agent-1"], 0.8)

    def test_broadcast_fitness_gossip_error_does_not_raise(self):
        arb, pool, gossip, _ = _make_arbitrator()
        gossip.broadcast.side_effect = RuntimeError("network down")
        arb.broadcast_fitness(epoch_id="ep-1", local_scores={"agent-1": 0.9})
        # Should not raise

    def test_broadcast_fitness_payload_contains_lineage_digest(self):
        arb, pool, gossip, _ = _make_arbitrator()
        arb.broadcast_fitness(epoch_id="ep-2", local_scores={"agent-2": 0.6})
        call_payload = gossip.broadcast.call_args[0][0]
        self.assertTrue(call_payload["budget"]["lineage_digest"].startswith("sha256:"))

    def test_broadcast_fitness_payload_contains_epoch_id(self):
        arb, pool, gossip, _ = _make_arbitrator()
        arb.broadcast_fitness(epoch_id="ep-specific", local_scores={})
        call_payload = gossip.broadcast.call_args[0][0]
        self.assertEqual(call_payload["budget"]["epoch_id"], "ep-specific")


# ---------------------------------------------------------------------------
# TestCrossNodeBudgetIngest
# ---------------------------------------------------------------------------

class TestCrossNodeBudgetIngest(unittest.TestCase):

    def test_ingest_valid_peer_report(self):
        evt = _gossip_event("node-B", scores={"agent-X": 0.7})
        arb, pool, gossip, _ = _make_arbitrator(gossip_events=[evt])
        accepted = arb.ingest_pending_gossip()
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].node_id, "node-B")

    def test_ingest_filters_own_node(self):
        evt = _gossip_event("node-A")  # same as broker node_id
        arb, pool, gossip, _ = _make_arbitrator(node_id="node-A", gossip_events=[evt])
        accepted = arb.ingest_pending_gossip()
        self.assertEqual(len(accepted), 0)

    def test_ingest_discards_stale_report(self):
        evt = _gossip_event("node-B", age=_MAX_PEER_FITNESS_AGE_S + 10)
        arb, pool, gossip, _ = _make_arbitrator(gossip_events=[evt])
        accepted = arb.ingest_pending_gossip()
        self.assertEqual(len(accepted), 0)

    def test_ingest_ignores_non_budget_events(self):
        evt = _gossip_event("node-B", event_type="market_signal_broadcast.v1")
        arb, pool, gossip, _ = _make_arbitrator(gossip_events=[evt])
        accepted = arb.ingest_pending_gossip()
        self.assertEqual(len(accepted), 0)

    def test_ingest_malformed_payload_discarded(self):
        bad_event = GossipEvent(
            event_id="bad-1", origin_peer_id="node-X",
            event_type=_BUDGET_GOSSIP_EVENT_TYPE,
            payload={"budget": {"broken": True}},
            emitted_at=time.time(), lineage_digest="sha256:bad",
        )
        arb, pool, gossip, _ = _make_arbitrator(gossip_events=[bad_event])
        accepted = arb.ingest_pending_gossip()
        self.assertEqual(len(accepted), 0)


# ---------------------------------------------------------------------------
# TestCrossNodeArbitrateCluster
# ---------------------------------------------------------------------------

class TestCrossNodeArbitrateCluster(unittest.TestCase):

    def test_single_node_cluster_produces_result(self):
        arb, pool, gossip, _ = _make_arbitrator()
        result = arb.arbitrate_cluster(
            epoch_id="ep-1",
            local_scores={"agent-1": 0.9, "agent-2": 0.5, "agent-3": 0.3},
        )
        self.assertIsInstance(result, ClusterArbitrationResult)
        self.assertIn("node-A", result.contributing_nodes)

    def test_peer_scores_merged_into_cluster(self):
        arb, pool, gossip, _ = _make_arbitrator()
        # Inject peer fitness directly
        arb._peer_fitness["node-B"] = _peer_fitness_report(
            "node-B", scores={"agent-peer-1": 0.8, "agent-peer-2": 0.2}
        )
        result = arb.arbitrate_cluster(
            epoch_id="ep-2",
            local_scores={"agent-1": 0.7},
        )
        self.assertIn("node-B", result.contributing_nodes)
        self.assertIn("agent-peer-1", result.cluster_scores)

    def test_local_scores_override_peer_on_conflict(self):
        arb, pool, gossip, _ = _make_arbitrator()
        arb._peer_fitness["node-B"] = _peer_fitness_report(
            "node-B", scores={"agent-1": 0.1}  # peer says 0.1
        )
        result = arb.arbitrate_cluster(
            epoch_id="ep-3",
            local_scores={"agent-1": 0.9},  # local says 0.9 — should win
        )
        self.assertAlmostEqual(result.cluster_scores["agent-1"], 0.9)

    def test_stale_peer_fitness_evicted_before_merge(self):
        arb, pool, gossip, _ = _make_arbitrator()
        arb._peer_fitness["node-B"] = _peer_fitness_report(
            "node-B", age=_MAX_PEER_FITNESS_AGE_S + 10
        )
        result = arb.arbitrate_cluster(
            epoch_id="ep-4",
            local_scores={"agent-1": 0.8},
        )
        self.assertNotIn("node-B", result.contributing_nodes)

    def test_lineage_digest_starts_with_sha256(self):
        arb, pool, gossip, _ = _make_arbitrator()
        result = arb.arbitrate_cluster(
            epoch_id="ep-5",
            local_scores={"agent-1": 0.7},
        )
        self.assertTrue(result.lineage_digest.startswith("sha256:"))

    def test_quorum_not_required_when_few_evictions(self):
        # With 3 agents and starvation_count=2, won't evict in single run
        arb, pool, gossip, _ = _make_arbitrator(require_quorum=True)
        result = arb.arbitrate_cluster(
            epoch_id="ep-6",
            local_scores={"agent-1": 0.9, "agent-2": 0.8, "agent-3": 0.7},
        )
        self.assertFalse(result.quorum_required)

    def test_allocation_broadcast_called_after_arbitration(self):
        arb, pool, gossip, _ = _make_arbitrator()
        arb.arbitrate_cluster(
            epoch_id="ep-7",
            local_scores={"agent-1": 0.9},
        )
        # broadcast called at least once (may also call for fitness)
        self.assertTrue(gossip.broadcast.called)

    def test_peer_fitness_summary_introspection(self):
        arb, pool, gossip, _ = _make_arbitrator()
        arb._peer_fitness["node-B"] = _peer_fitness_report("node-B")
        summary = arb.peer_fitness_summary()
        self.assertEqual(len(summary), 1)
        self.assertTrue(summary[0]["fresh"])


if __name__ == "__main__":
    unittest.main()
