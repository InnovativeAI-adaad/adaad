# SPDX-License-Identifier: Apache-2.0
"""PeerRegistry + GossipProtocol — ADAAD-13 Track D.

Autonomous peer discovery and HTTP gossip propagation for multi-node federation.

Architecture
------------
::

    PeerRegistry
         ├── register(peer_id, endpoint) — add/update peer
         ├── heartbeat(peer_id) — update liveness timestamp
         ├── alive_peers() — peers within TTL window
         └── stale_peers() — peers beyond TTL (partition candidates)

    GossipProtocol
         ├── broadcast(event) — send to all alive peers (best-effort, non-blocking)
         ├── receive(raw) — validate + enqueue inbound gossip
         └── pending_events() — drain inbound queue

Invariants
----------
- Peer registration is idempotent; re-registration updates endpoint only.
- Gossip events carry sha256 lineage digest for cross-node traceability.
- Partition detection fires when > partition_threshold peers become stale.
- All gossip transmissions are best-effort; failures degrade to local-only operation.
- Constitutional evaluation gate is never bypassed by gossip; gossip carries
  proposals and state sync payloads, not execution authority.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from urllib import error as urlerror, request as urlreq

log = logging.getLogger(__name__)

_GOSSIP_TIMEOUT_S = 3
_DEFAULT_PEER_TTL_S = 30
_EVENT_TYPE_GOSSIP = "federation_gossip.v1"


@dataclass
class PeerRecord:
    peer_id: str
    endpoint: str          # e.g. "http://10.0.0.2:8080"
    registered_at: float
    last_heartbeat: float
    constitution_version: str = ""
    is_self: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_alive(self, *, ttl: float = _DEFAULT_PEER_TTL_S, now: Optional[float] = None) -> bool:
        return ((now or time.time()) - self.last_heartbeat) < ttl


@dataclass(frozen=True)
class GossipEvent:
    event_id: str
    origin_peer_id: str
    event_type: str
    payload: Dict[str, Any]
    emitted_at: float
    lineage_digest: str

    @staticmethod
    def build(*, origin_peer_id: str, event_type: str, payload: Dict[str, Any]) -> "GossipEvent":
        now = time.time()
        eid = f"gossip-{uuid.uuid4().hex[:12]}"
        raw = json.dumps({"eid": eid, "origin": origin_peer_id, "type": event_type, "ts": now}, sort_keys=True)
        digest = "sha256:" + hashlib.sha256(raw.encode()).hexdigest()
        return GossipEvent(
            event_id=eid, origin_peer_id=origin_peer_id, event_type=event_type,
            payload=payload, emitted_at=now, lineage_digest=digest,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id, "origin_peer_id": self.origin_peer_id,
            "event_type": self.event_type, "payload": self.payload,
            "emitted_at": self.emitted_at, "lineage_digest": self.lineage_digest,
        }


class PeerRegistry:
    """Registry of federation peers with TTL-based liveness tracking."""

    def __init__(self, *, self_id: str, self_endpoint: str, peer_ttl_s: float = _DEFAULT_PEER_TTL_S) -> None:
        self._self_id = self_id
        self._peers: Dict[str, PeerRecord] = {}
        self._ttl = peer_ttl_s
        self.register(self_id, self_endpoint, is_self=True)

    def register(self, peer_id: str, endpoint: str, *, is_self: bool = False) -> PeerRecord:
        now = time.time()
        if peer_id in self._peers:
            self._peers[peer_id].endpoint = endpoint
            self._peers[peer_id].last_heartbeat = now
            return self._peers[peer_id]
        record = PeerRecord(peer_id=peer_id, endpoint=endpoint, registered_at=now,
                            last_heartbeat=now, is_self=is_self)
        self._peers[peer_id] = record
        return record

    def heartbeat(self, peer_id: str) -> bool:
        rec = self._peers.get(peer_id)
        if rec is None:
            return False
        rec.last_heartbeat = time.time()
        return True

    def deregister(self, peer_id: str) -> bool:
        return self._peers.pop(peer_id, None) is not None

    def alive_peers(self) -> List[PeerRecord]:
        return [p for p in self._peers.values() if not p.is_self and p.is_alive(ttl=self._ttl)]

    def stale_peers(self) -> List[PeerRecord]:
        return [p for p in self._peers.values() if not p.is_self and not p.is_alive(ttl=self._ttl)]

    def all_peers(self) -> List[PeerRecord]:
        return [p for p in self._peers.values() if not p.is_self]

    def is_partitioned(self, *, partition_threshold: float = 0.5) -> bool:
        total = len(self.all_peers())
        if total == 0:
            return False
        stale = len(self.stale_peers())
        return (stale / total) >= partition_threshold

    @property
    def self_id(self) -> str:
        return self._self_id


class GossipProtocol:
    """HTTP-based gossip broadcast with inbound event validation."""

    def __init__(self, *, registry: PeerRegistry, journal_fn: Optional[Callable] = None) -> None:
        self._registry = registry
        self._journal_fn = journal_fn
        self._inbound: List[GossipEvent] = []

    def broadcast(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, bool]:
        """Broadcast to all alive peers. Returns {peer_id: success}."""
        event = GossipEvent.build(
            origin_peer_id=self._registry.self_id,
            event_type=event_type, payload=payload,
        )
        results: Dict[str, bool] = {}
        for peer in self._registry.alive_peers():
            results[peer.peer_id] = self._send(peer.endpoint, event)
        self._journal(_EVENT_TYPE_GOSSIP, {"event_id": event.event_id, "results": results,
                                           "lineage_digest": event.lineage_digest})
        return results

    def receive(self, raw: Dict[str, Any]) -> Optional[GossipEvent]:
        """Validate and enqueue an inbound gossip event."""
        required = {"event_id", "origin_peer_id", "event_type", "payload", "emitted_at", "lineage_digest"}
        if not required.issubset(raw.keys()):
            log.warning("GossipProtocol: malformed inbound event — missing fields")
            return None
        event = GossipEvent(
            event_id=str(raw["event_id"]), origin_peer_id=str(raw["origin_peer_id"]),
            event_type=str(raw["event_type"]), payload=dict(raw.get("payload") or {}),
            emitted_at=float(raw["emitted_at"]), lineage_digest=str(raw["lineage_digest"]),
        )
        self._inbound.append(event)
        return event

    def pending_events(self) -> List[GossipEvent]:
        events, self._inbound = list(self._inbound), []
        return events

    def _send(self, endpoint: str, event: GossipEvent) -> bool:
        try:
            body = json.dumps(event.to_dict()).encode()
            req = urlreq.Request(f"{endpoint}/federation/gossip", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
            with urlreq.urlopen(req, timeout=_GOSSIP_TIMEOUT_S):
                pass
            return True
        except Exception as exc:
            log.debug("GossipProtocol: send to %s failed — %s", endpoint, exc)
            return False

    def _journal(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._journal_fn:
            try: self._journal_fn(event_type, payload)
            except Exception: pass

__all__ = ["PeerRegistry", "PeerRecord", "GossipProtocol", "GossipEvent"]
