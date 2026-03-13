# SPDX-License-Identifier: Apache-2.0
"""FederationNodeSupervisor — heartbeat, partition detection, autonomous rejoin. ADAAD-13 Track D."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

from runtime.governance.foundation import RuntimeDeterminismProvider, default_provider

log = logging.getLogger(__name__)


class NodeSupervisorState(str, Enum):
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"   # some peers stale but quorum maintained
    PARTITIONED = "partitioned"  # majority of peers stale — safe mode
    REJOINING = "rejoining"


@dataclass(frozen=True)
class SupervisorStatus:
    state: NodeSupervisorState
    alive_peers: int
    stale_peers: int
    is_leader: bool
    term: int
    safe_mode_active: bool


class FederationNodeSupervisor:
    """Monitors federation health; enforces safe mode on partition; triggers autonomous rejoin.

    In safe mode (partitioned):
    - No new mutations are approved at the cross-node level.
    - Local mutations continue with degraded-federation label.
    - Rejoin is attempted automatically when peers become reachable.
    """

    def __init__(
        self,
        *,
        registry: Any,         # PeerRegistry
        consensus: Any,        # FederationConsensusEngine
        gossip: Any,           # GossipProtocol
        partition_threshold: float = 0.5,
        rejoin_interval_s: float = 10.0,
        journal_fn: Optional[Callable] = None,
        provider: RuntimeDeterminismProvider | None = None,
    ) -> None:
        self._registry = registry
        self._consensus = consensus
        self._gossip = gossip
        self._partition_threshold = partition_threshold
        self._rejoin_interval_s = rejoin_interval_s
        self._journal_fn = journal_fn
        self._provider: RuntimeDeterminismProvider = provider or default_provider()
        self._state = NodeSupervisorState.HEALTHY
        self._last_rejoin_attempt = 0.0

    def _now_timestamp(self) -> float:
        return self._provider.now_utc().timestamp()

    def tick(self) -> SupervisorStatus:
        """Run one supervision cycle. Call periodically (e.g. every heartbeat interval)."""
        alive = len(self._registry.alive_peers())
        stale = len(self._registry.stale_peers())
        partitioned = self._registry.is_partitioned(partition_threshold=self._partition_threshold)

        if partitioned:
            if self._state != NodeSupervisorState.PARTITIONED:
                self._state = NodeSupervisorState.PARTITIONED
                self._on_partition_detected()
            self._maybe_rejoin()
        elif stale > 0:
            self._state = NodeSupervisorState.DEGRADED
        else:
            self._state = NodeSupervisorState.HEALTHY

        # Leader sends periodic heartbeats
        if self._consensus.role.value == "leader":
            self._gossip.broadcast("federation_heartbeat.v1", {
                "leader_id": self._consensus.node_id,
                "term": self._consensus.term,
                "commit_index": self._consensus.commit_index,
            })

        return SupervisorStatus(
            state=self._state,
            alive_peers=alive,
            stale_peers=stale,
            is_leader=self._consensus.role.value == "leader",
            term=self._consensus.term,
            safe_mode_active=partitioned,
        )

    def _on_partition_detected(self) -> None:
        log.warning("FederationNodeSupervisor: partition detected — safe mode active")
        self._journal("federation_partition_detected.v1", {
            "node_id": self._consensus.node_id,
            "alive_peers": len(self._registry.alive_peers()),
            "stale_peers": len(self._registry.stale_peers()),
            "detected_at": self._now_timestamp(),
        })

    def _maybe_rejoin(self) -> None:
        now = self._now_timestamp()
        if (now - self._last_rejoin_attempt) < self._rejoin_interval_s:
            return
        self._last_rejoin_attempt = now
        self._state = NodeSupervisorState.REJOINING
        self._gossip.broadcast("federation_rejoin_request.v1", {
            "node_id": self._consensus.node_id,
            "term": self._consensus.term,
            "requested_at": now,
        })
        log.info("FederationNodeSupervisor: rejoin broadcast sent")

    def _journal(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._journal_fn:
            try: self._journal_fn(event_type, payload)
            except Exception: pass

__all__ = ["FederationNodeSupervisor", "NodeSupervisorState", "SupervisorStatus"]
