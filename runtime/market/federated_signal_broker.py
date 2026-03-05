# SPDX-License-Identifier: Apache-2.0
"""FederatedSignalBroker — ADAAD-14 Track A×D convergence.

Bridges the live-market pipeline (FeedRegistry / MarketSignalReading) with the
autonomous federation layer (GossipProtocol / PeerRegistry) so that every node
shares its composite market reading with all alive peers and can aggregate a
cluster-wide signal in real time.

Architecture
------------
::

    FederatedSignalBroker
         ├── publish_local_reading()  — push local composite to all alive peers
         ├── receive_peer_reading()   — validate + accept inbound peer reading
         ├── cluster_composite()      — confidence-weighted aggregate across all nodes
         └── pending_inbound()        — drain buffered peer readings

    FederationMarketGossip
         └── wrap / unwrap MarketSignalReading ↔ GossipEvent

Invariants
----------
- Market signals are advisory only; they influence fitness scoring but cannot
  approve or reject mutations.
- Peer readings with confidence == 0 are discarded (stale source guard).
- Cluster composite falls back to local reading when no peers are alive.
- All gossip events carry sha256 lineage digests (inherited from GossipProtocol).
- Authority invariant: FederatedSignalBroker never calls GovernanceGate.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from runtime.market.feed_registry import FeedRegistry, MarketSignalReading
from runtime.governance.federation.peer_discovery import GossipProtocol, PeerRegistry

log = logging.getLogger(__name__)

_MARKET_GOSSIP_EVENT_TYPE = "market_signal_broadcast.v1"
_MAX_PEER_READING_AGE_S = 60.0  # discard peer readings older than 60 s


# ---------------------------------------------------------------------------
# Gossip serialisation helpers
# ---------------------------------------------------------------------------

class FederationMarketGossip:
    """Serialise / deserialise MarketSignalReading ↔ gossip event payload."""

    @staticmethod
    def to_payload(reading: MarketSignalReading, node_id: str) -> Dict:
        return {
            "node_id": node_id,
            "adapter_id": reading.adapter_id,
            "signal_type": reading.signal_type,
            "value": reading.value,
            "confidence": reading.confidence,
            "sampled_at": reading.sampled_at,
            "lineage_digest": reading.lineage_digest,
            "source_uri": reading.source_uri,
            "stale": reading.stale,
        }

    @staticmethod
    def from_payload(payload: Dict) -> Optional["PeerReading"]:
        try:
            return PeerReading(
                node_id=payload["node_id"],
                signal_type=payload.get("signal_type", "composite"),
                value=float(payload["value"]),
                confidence=float(payload["confidence"]),
                sampled_at=float(payload["sampled_at"]),
                lineage_digest=payload.get("lineage_digest", ""),
                stale=bool(payload.get("stale", False)),
            )
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("FederationMarketGossip: malformed peer reading payload — %s", exc)
            return None


# ---------------------------------------------------------------------------
# PeerReading dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PeerReading:
    """Validated market reading received from a federation peer."""

    node_id: str
    signal_type: str
    value: float       # normalised [0.0, 1.0]
    confidence: float  # data quality / freshness [0.0, 1.0]
    sampled_at: float  # epoch timestamp (peer-local clock)
    lineage_digest: str
    stale: bool = False

    def age_seconds(self, now: Optional[float] = None) -> float:
        return (now or time.time()) - self.sampled_at

    def is_fresh(self, max_age: float = _MAX_PEER_READING_AGE_S, now: Optional[float] = None) -> bool:
        return (not self.stale) and self.age_seconds(now) < max_age and self.confidence > 0.0

    def fitness_contribution(self) -> float:
        return round(self.value * self.confidence, 6)


# ---------------------------------------------------------------------------
# FederatedSignalBroker
# ---------------------------------------------------------------------------

class FederatedSignalBroker:
    """Publish local market readings to federation peers and aggregate cluster-wide signal.

    Parameters
    ----------
    node_id:
        This node's identifier (must match PeerRegistry registration).
    feed_registry:
        Local FeedRegistry providing composite readings.
    peer_registry:
        PeerRegistry used to enumerate alive peers.
    gossip:
        GossipProtocol used to broadcast and receive events.
    """

    def __init__(
        self,
        *,
        node_id: str,
        feed_registry: FeedRegistry,
        peer_registry: PeerRegistry,
        gossip: GossipProtocol,
    ) -> None:
        self._node_id = node_id
        self._feed_registry = feed_registry
        self._peer_registry = peer_registry
        self._gossip = gossip
        self._peer_readings: Dict[str, PeerReading] = {}  # node_id → latest reading

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish_local_reading(self) -> Optional[MarketSignalReading]:
        """Fetch local composite reading and gossip it to all alive peers.

        Returns the local reading on success, None if local FeedRegistry fails.
        """
        try:
            reading = self._feed_registry.composite_reading()
        except Exception as exc:
            log.warning("FederatedSignalBroker: local FeedRegistry error — %s", exc)
            return None

        if reading.stale:
            log.debug("FederatedSignalBroker: local reading is stale — skipping broadcast")
            return reading

        payload = FederationMarketGossip.to_payload(reading, self._node_id)
        try:
            self._gossip.broadcast({"event_type": _MARKET_GOSSIP_EVENT_TYPE, "market": payload})
            log.debug(
                "FederatedSignalBroker: broadcast market reading value=%.4f confidence=%.4f peers=%d",
                reading.value,
                reading.confidence,
                len(self._peer_registry.alive_peers()),
            )
        except Exception as exc:
            log.warning("FederatedSignalBroker: gossip broadcast error — %s", exc)

        return reading

    # ------------------------------------------------------------------
    # Receive
    # ------------------------------------------------------------------

    def ingest_pending_gossip(self) -> List[PeerReading]:
        """Drain GossipProtocol inbound queue and absorb market_signal_broadcast events.

        Returns list of newly accepted peer readings.
        """
        accepted: List[PeerReading] = []
        for event in self._gossip.pending_events():
            if event.event_type != _MARKET_GOSSIP_EVENT_TYPE:
                continue
            market_payload = event.payload.get("market")
            if not market_payload:
                continue
            peer_reading = FederationMarketGossip.from_payload(market_payload)
            if peer_reading is None:
                continue
            if peer_reading.node_id == self._node_id:
                continue  # discard echoes
            if not peer_reading.is_fresh():
                log.debug(
                    "FederatedSignalBroker: stale peer reading from %s — discarded",
                    peer_reading.node_id,
                )
                continue
            self._peer_readings[peer_reading.node_id] = peer_reading
            accepted.append(peer_reading)
        return accepted

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------

    def cluster_composite(self, *, now: Optional[float] = None) -> float:
        """Return confidence-weighted composite market signal across the cluster.

        Falls back to local reading when no fresh peer readings exist.
        """
        now = now or time.time()

        # Evict stale peer readings
        self._peer_readings = {
            nid: r for nid, r in self._peer_readings.items() if r.is_fresh(now=now)
        }

        # Gather local reading
        try:
            local = self._feed_registry.composite_reading()
            local_value = local.value if not local.stale else 0.5
            local_conf = local.confidence if not local.stale else 0.0
        except Exception:
            local_value, local_conf = 0.5, 0.0

        contributions: List[tuple] = [(local_value, local_conf)]
        for r in self._peer_readings.values():
            contributions.append((r.value, r.confidence))

        total_conf = sum(c for _, c in contributions)
        if total_conf == 0.0:
            return 0.5  # neutral fallback

        weighted = sum(v * c for v, c in contributions)
        composite = round(weighted / total_conf, 6)
        log.debug(
            "FederatedSignalBroker: cluster_composite=%.4f nodes=%d",
            composite,
            len(contributions),
        )
        return composite

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def alive_peer_count(self) -> int:
        return len(self._peer_registry.alive_peers())

    def peer_reading_summary(self, *, now: Optional[float] = None) -> List[Dict]:
        now = now or time.time()
        return [
            {
                "node_id": r.node_id,
                "value": r.value,
                "confidence": r.confidence,
                "age_seconds": round(r.age_seconds(now), 2),
                "fresh": r.is_fresh(now=now),
            }
            for r in self._peer_readings.values()
        ]
