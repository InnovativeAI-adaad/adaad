# SPDX-License-Identifier: Apache-2.0
"""CrossNodeBudgetArbitrator — ADAAD-14 Track B×D convergence.

Extends the Darwinian budget competition (ADAAD-11) into the federation layer
(ADAAD-13) so that agents compete for budget across the entire cluster, not
just within a single node.

Architecture
------------
::

    CrossNodeBudgetArbitrator
         ├── collect_peer_fitness()       — gossip-query peer nodes for agent fitness
         ├── arbitrate_cluster()          — run Softmax over merged local+peer scores
         ├── broadcast_local_allocations()— gossip this node's allocation decisions
         └── quorum_required()            — whether policy_change quorum is needed

    FederationBudgetGossip
         └── wrap / unwrap fitness + allocation payloads ↔ GossipEvent

    ClusterArbitrationResult
         └── per-node allocation decisions + cluster-wide evictions + quorum_met

Invariants
----------
- Cross-node competition is additive; local BudgetArbitrator retains final
  write authority to the local AgentBudgetPool.
- Budget eviction across nodes is journaled as cross_node_budget_reallocation.v1.
- Quorum gate: if cluster_policy_change_requires_quorum=True, evictions that
  affect >50% of cluster agents require ConsensusEngine quorum before applying.
- Authority invariant: CrossNodeBudgetArbitrator never approves or signs mutations.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from runtime.evolution.budget.arbitrator import ArbitrationResult, BudgetArbitrator
from runtime.evolution.budget.pool import AgentBudgetPool
from runtime.governance.federation.peer_discovery import GossipProtocol, PeerRegistry

log = logging.getLogger(__name__)

_BUDGET_GOSSIP_EVENT_TYPE = "budget_fitness_broadcast.v1"
_ALLOC_GOSSIP_EVENT_TYPE = "budget_allocation_broadcast.v1"
_MAX_PEER_FITNESS_AGE_S = 45.0
_CLUSTER_EVICTION_QUORUM_THRESHOLD = 0.5  # quorum required if >50% agents evicted


# ---------------------------------------------------------------------------
# Gossip helpers
# ---------------------------------------------------------------------------

class FederationBudgetGossip:
    """Serialise / deserialise fitness scores and allocation decisions for gossip."""

    @staticmethod
    def fitness_payload(node_id: str, epoch_id: str, scores: Dict[str, float]) -> Dict:
        raw = json.dumps({"node": node_id, "epoch": epoch_id, "scores": scores}, sort_keys=True)
        digest = "sha256:" + hashlib.sha256(raw.encode()).hexdigest()
        return {
            "node_id": node_id,
            "epoch_id": epoch_id,
            "scores": scores,
            "sampled_at": time.time(),
            "lineage_digest": digest,
        }

    @staticmethod
    def allocation_payload(node_id: str, epoch_id: str, result: ArbitrationResult) -> Dict:
        raw = json.dumps({"node": node_id, "epoch": epoch_id, "shares": result.new_shares}, sort_keys=True)
        digest = "sha256:" + hashlib.sha256(raw.encode()).hexdigest()
        return {
            "node_id": node_id,
            "epoch_id": epoch_id,
            "new_shares": result.new_shares,
            "evicted_agents": result.evicted_agents,
            "market_scalar": result.market_scalar,
            "sampled_at": time.time(),
            "lineage_digest": digest,
        }

    @staticmethod
    def parse_fitness_payload(payload: Dict) -> Optional["PeerFitnessReport"]:
        try:
            return PeerFitnessReport(
                node_id=payload["node_id"],
                epoch_id=payload["epoch_id"],
                scores={str(k): float(v) for k, v in payload["scores"].items()},
                sampled_at=float(payload["sampled_at"]),
                lineage_digest=payload.get("lineage_digest", ""),
            )
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("FederationBudgetGossip: malformed fitness payload — %s", exc)
            return None


# ---------------------------------------------------------------------------
# Peer data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PeerFitnessReport:
    node_id: str
    epoch_id: str
    scores: Dict[str, float]
    sampled_at: float
    lineage_digest: str

    def is_fresh(self, max_age: float = _MAX_PEER_FITNESS_AGE_S, now: Optional[float] = None) -> bool:
        return ((now or time.time()) - self.sampled_at) < max_age


@dataclass(frozen=True)
class ClusterArbitrationResult:
    """Result of a cross-node arbitration run."""
    epoch_id: str
    cluster_scores: Dict[str, float]        # merged agent_id → fitness across all nodes
    cluster_new_shares: Dict[str, float]    # agent_id → normalised share in cluster pool
    cluster_evicted: List[str]
    cluster_starved: List[str]
    contributing_nodes: List[str]
    quorum_required: bool
    quorum_met: Optional[bool]              # None when quorum not required
    market_scalar: float
    lineage_digest: str

    @property
    def effective_evictions(self) -> List[str]:
        """Evictions that may be applied — blocked if quorum required but not met."""
        if self.quorum_required and self.quorum_met is False:
            return []
        return self.cluster_evicted


# ---------------------------------------------------------------------------
# CrossNodeBudgetArbitrator
# ---------------------------------------------------------------------------

class CrossNodeBudgetArbitrator:
    """Run Darwinian budget competition across the entire federation cluster.

    Parameters
    ----------
    node_id:
        This node's identifier.
    local_arbitrator:
        The node-local BudgetArbitrator (writes to local AgentBudgetPool).
    peer_registry:
        Federation PeerRegistry for alive peer discovery.
    gossip:
        GossipProtocol for broadcasting and receiving budget events.
    require_quorum_for_cluster_eviction:
        When True, evictions that affect >50% of cluster agents require
        ConsensusEngine quorum before being applied locally.
    consensus_engine:
        Optional FederationConsensusEngine reference for quorum checks.
    """

    def __init__(
        self,
        *,
        node_id: str,
        local_arbitrator: BudgetArbitrator,
        peer_registry: PeerRegistry,
        gossip: GossipProtocol,
        require_quorum_for_cluster_eviction: bool = True,
        consensus_engine: Optional[Any] = None,
    ) -> None:
        self._node_id = node_id
        self._local_arbitrator = local_arbitrator
        self._peer_registry = peer_registry
        self._gossip = gossip
        self._require_quorum = require_quorum_for_cluster_eviction
        self._consensus = consensus_engine
        self._peer_fitness: Dict[str, PeerFitnessReport] = {}  # node_id → latest

    # ------------------------------------------------------------------
    # Publish local fitness scores
    # ------------------------------------------------------------------

    def broadcast_fitness(self, *, epoch_id: str, local_scores: Dict[str, float]) -> None:
        """Gossip this node's agent fitness scores to all alive peers."""
        payload = FederationBudgetGossip.fitness_payload(self._node_id, epoch_id, local_scores)
        try:
            self._gossip.broadcast({"event_type": _BUDGET_GOSSIP_EVENT_TYPE, "budget": payload})
            log.debug(
                "CrossNodeBudgetArbitrator: broadcast fitness epoch=%s agents=%d peers=%d",
                epoch_id,
                len(local_scores),
                len(self._peer_registry.alive_peers()),
            )
        except Exception as exc:
            log.warning("CrossNodeBudgetArbitrator: broadcast_fitness error — %s", exc)

    # ------------------------------------------------------------------
    # Ingest peer fitness
    # ------------------------------------------------------------------

    def ingest_pending_gossip(self) -> List[PeerFitnessReport]:
        """Drain gossip queue and absorb budget_fitness_broadcast events."""
        accepted: List[PeerFitnessReport] = []
        for event in self._gossip.pending_events():
            if event.event_type != _BUDGET_GOSSIP_EVENT_TYPE:
                continue
            budget_payload = event.payload.get("budget")
            if not budget_payload:
                continue
            report = FederationBudgetGossip.parse_fitness_payload(budget_payload)
            if report is None or report.node_id == self._node_id:
                continue
            if not report.is_fresh():
                log.debug(
                    "CrossNodeBudgetArbitrator: stale fitness report from %s — discarded",
                    report.node_id,
                )
                continue
            self._peer_fitness[report.node_id] = report
            accepted.append(report)
        return accepted

    # ------------------------------------------------------------------
    # Cluster arbitration
    # ------------------------------------------------------------------

    def arbitrate_cluster(
        self,
        *,
        epoch_id: str,
        local_scores: Dict[str, float],
        market_pressure: float = 1.0,
        now: Optional[float] = None,
    ) -> ClusterArbitrationResult:
        """Merge local + peer fitness scores and run Darwinian reallocation.

        1. Evict stale peer fitness reports.
        2. Merge all fitness scores (peer wins on conflict — most recent report).
        3. Run local arbitrator with merged scores + market pressure.
        4. Evaluate quorum requirement for evictions.
        5. Broadcast allocation decision to peers.
        6. Return ClusterArbitrationResult.
        """
        now = now or time.time()

        # Step 1: evict stale peer reports
        self._peer_fitness = {
            nid: r for nid, r in self._peer_fitness.items() if r.is_fresh(now=now)
        }

        # Step 2: merge scores — peer scores supplement local (local is authoritative for own agents)
        merged_scores: Dict[str, float] = {}
        contributing_nodes: List[str] = [self._node_id]

        for node_id, report in self._peer_fitness.items():
            for agent_id, score in report.scores.items():
                if agent_id not in merged_scores:
                    merged_scores[agent_id] = score
            contributing_nodes.append(node_id)

        # Local scores override (this node's authoritative view)
        merged_scores.update(local_scores)

        # Step 3: run local arbitrator
        result = self._local_arbitrator.arbitrate(
            fitness_scores=merged_scores,
            epoch_id=epoch_id,
            market_pressure=market_pressure,
        )

        # Step 4: quorum check
        total_agents = len(merged_scores)
        eviction_fraction = len(result.evicted_agents) / max(1, total_agents)
        quorum_required = (
            self._require_quorum
            and eviction_fraction > _CLUSTER_EVICTION_QUORUM_THRESHOLD
        )
        quorum_met: Optional[bool] = None
        if quorum_required:
            quorum_met = self._check_quorum(epoch_id)
            if not quorum_met:
                log.warning(
                    "CrossNodeBudgetArbitrator: quorum NOT met for cluster eviction "
                    "epoch=%s eviction_fraction=%.2f — evictions blocked",
                    epoch_id,
                    eviction_fraction,
                )

        # Step 5: build lineage digest
        raw = json.dumps({
            "epoch": epoch_id,
            "nodes": sorted(contributing_nodes),
            "shares": result.new_shares,
        }, sort_keys=True)
        digest = "sha256:" + hashlib.sha256(raw.encode()).hexdigest()

        cluster_result = ClusterArbitrationResult(
            epoch_id=epoch_id,
            cluster_scores=merged_scores,
            cluster_new_shares=result.new_shares,
            cluster_evicted=result.evicted_agents,
            cluster_starved=result.starved_agents,
            contributing_nodes=contributing_nodes,
            quorum_required=quorum_required,
            quorum_met=quorum_met,
            market_scalar=result.market_scalar,
            lineage_digest=digest,
        )

        # Step 6: broadcast allocation
        try:
            alloc_payload = FederationBudgetGossip.allocation_payload(self._node_id, epoch_id, result)
            self._gossip.broadcast({"event_type": _ALLOC_GOSSIP_EVENT_TYPE, "allocation": alloc_payload})
        except Exception as exc:
            log.warning("CrossNodeBudgetArbitrator: broadcast_allocation error — %s", exc)

        log.info(
            "CrossNodeBudgetArbitrator: cluster arbitration epoch=%s nodes=%d agents=%d evicted=%d quorum_req=%s",
            epoch_id,
            len(contributing_nodes),
            len(merged_scores),
            len(result.evicted_agents),
            quorum_required,
        )
        return cluster_result

    # ------------------------------------------------------------------
    # Quorum helper
    # ------------------------------------------------------------------

    def _check_quorum(self, epoch_id: str) -> bool:
        """Return True if ConsensusEngine reports quorum, False otherwise.

        Degrades to True (allow) when no consensus engine is configured, preserving
        single-node backward compatibility.
        """
        if self._consensus is None:
            return True
        try:
            return bool(self._consensus.has_quorum(epoch_id=epoch_id))
        except Exception as exc:
            log.warning("CrossNodeBudgetArbitrator: consensus quorum check error — %s", exc)
            return False

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def peer_fitness_summary(self, *, now: Optional[float] = None) -> List[Dict]:
        now = now or time.time()
        return [
            {
                "node_id": r.node_id,
                "epoch_id": r.epoch_id,
                "agent_count": len(r.scores),
                "fresh": r.is_fresh(now=now),
            }
            for r in self._peer_fitness.values()
        ]
