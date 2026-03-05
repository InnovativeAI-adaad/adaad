# SPDX-License-Identifier: Apache-2.0
"""Tests for FederatedSignalBroker — ADAAD-14 PR-14-01.

Coverage
--------
- TestFederatedSignalBrokerPublish   (4 tests) — local reading broadcast, stale guard, FeedRegistry error
- TestFederatedSignalBrokerIngest    (6 tests) — peer reading absorption, echo filter, stale filter, malformed discard
- TestFederatedSignalBrokerAggregate (6 tests) — cluster composite weighting, eviction, fallback, single-node
- TestPeerReading                    (4 tests) — freshness, age, fitness_contribution, stale flag
"""
from __future__ import annotations

import time
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from runtime.market.feed_registry import MarketSignalReading
from runtime.market.federated_signal_broker import (
    FederatedSignalBroker,
    FederationMarketGossip,
    PeerReading,
    _MARKET_GOSSIP_EVENT_TYPE,
    _MAX_PEER_READING_AGE_S,
)
from runtime.governance.federation.peer_discovery import GossipEvent, PeerRecord


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

def _reading(value: float = 0.7, confidence: float = 0.9, stale: bool = False, node_id: str = "node-A") -> MarketSignalReading:
    import hashlib, json
    raw = json.dumps({"v": value, "t": time.time()}, sort_keys=True)
    digest = "sha256:" + hashlib.sha256(raw.encode()).hexdigest()
    return MarketSignalReading(
        adapter_id="test-adapter",
        signal_type="composite",
        value=value,
        confidence=confidence,
        sampled_at=time.time(),
        lineage_digest=digest,
        source_uri="test://",
        stale=stale,
    )


def _peer_reading(node_id: str = "node-B", value: float = 0.6, confidence: float = 0.8,
                   age: float = 0.0, stale: bool = False) -> PeerReading:
    return PeerReading(
        node_id=node_id,
        signal_type="composite",
        value=value,
        confidence=confidence,
        sampled_at=time.time() - age,
        lineage_digest="sha256:abc123",
        stale=stale,
    )


def _gossip_event(node_id: str, value: float = 0.6, confidence: float = 0.8,
                   event_type: str = _MARKET_GOSSIP_EVENT_TYPE, age: float = 0.0) -> GossipEvent:
    payload = {
        "market": {
            "node_id": node_id,
            "signal_type": "composite",
            "value": value,
            "confidence": confidence,
            "sampled_at": time.time() - age,
            "lineage_digest": "sha256:def456",
            "source_uri": "test://",
            "stale": False,
        }
    }
    return GossipEvent(
        event_id=f"gossip-{node_id}",
        origin_peer_id=node_id,
        event_type=event_type,
        payload=payload,
        emitted_at=time.time() - age,
        lineage_digest="sha256:evtdigest",
    )


def _make_broker(local_value: float = 0.7, local_confidence: float = 0.9,
                  local_stale: bool = False, node_id: str = "node-A",
                  gossip_events: Optional[List] = None):
    feed_registry = MagicMock()
    feed_registry.composite_reading.return_value = _reading(local_value, local_confidence, local_stale)

    peer_registry = MagicMock()
    peer_registry.alive_peers.return_value = [
        PeerRecord("node-B", "http://10.0.0.2:8080", time.time(), time.time())
    ]

    gossip = MagicMock()
    gossip.pending_events.return_value = gossip_events or []

    broker = FederatedSignalBroker(
        node_id=node_id,
        feed_registry=feed_registry,
        peer_registry=peer_registry,
        gossip=gossip,
    )
    return broker, feed_registry, peer_registry, gossip


# ---------------------------------------------------------------------------
# TestPeerReading
# ---------------------------------------------------------------------------

class TestPeerReading(unittest.TestCase):

    def test_fresh_reading(self):
        r = _peer_reading(age=5.0)
        self.assertTrue(r.is_fresh())

    def test_stale_by_age(self):
        r = _peer_reading(age=_MAX_PEER_READING_AGE_S + 1)
        self.assertFalse(r.is_fresh())

    def test_stale_flag(self):
        r = _peer_reading(stale=True)
        self.assertFalse(r.is_fresh())

    def test_fitness_contribution(self):
        r = _peer_reading(value=0.8, confidence=0.5)
        self.assertAlmostEqual(r.fitness_contribution(), 0.4, places=5)

    def test_zero_confidence_not_fresh(self):
        r = _peer_reading(confidence=0.0)
        self.assertFalse(r.is_fresh())


# ---------------------------------------------------------------------------
# TestFederatedSignalBrokerPublish
# ---------------------------------------------------------------------------

class TestFederatedSignalBrokerPublish(unittest.TestCase):

    def test_publish_broadcasts_to_gossip(self):
        broker, feed, peers, gossip = _make_broker(local_value=0.75)
        result = broker.publish_local_reading()
        self.assertIsNotNone(result)
        gossip.broadcast.assert_called_once()
        call_payload = gossip.broadcast.call_args[0][0]
        self.assertEqual(call_payload["event_type"], _MARKET_GOSSIP_EVENT_TYPE)
        self.assertAlmostEqual(call_payload["market"]["value"], 0.75, places=4)

    def test_publish_stale_reading_skips_broadcast(self):
        broker, feed, peers, gossip = _make_broker(local_stale=True)
        result = broker.publish_local_reading()
        self.assertIsNotNone(result)  # stale reading still returned
        gossip.broadcast.assert_not_called()

    def test_publish_feed_registry_error_returns_none(self):
        broker, feed, peers, gossip = _make_broker()
        feed.composite_reading.side_effect = RuntimeError("feed down")
        result = broker.publish_local_reading()
        self.assertIsNone(result)
        gossip.broadcast.assert_not_called()

    def test_publish_gossip_error_still_returns_reading(self):
        broker, feed, peers, gossip = _make_broker()
        gossip.broadcast.side_effect = RuntimeError("network error")
        result = broker.publish_local_reading()
        self.assertIsNotNone(result)  # graceful degradation


# ---------------------------------------------------------------------------
# TestFederatedSignalBrokerIngest
# ---------------------------------------------------------------------------

class TestFederatedSignalBrokerIngest(unittest.TestCase):

    def test_ingest_valid_peer_reading(self):
        evt = _gossip_event("node-B", value=0.65, confidence=0.85)
        broker, *_ = _make_broker(gossip_events=[evt])
        accepted = broker.ingest_pending_gossip()
        self.assertEqual(len(accepted), 1)
        self.assertAlmostEqual(accepted[0].value, 0.65, places=4)

    def test_ingest_filters_echo_from_self(self):
        evt = _gossip_event("node-A", value=0.7)  # same node_id as broker
        broker, *_ = _make_broker(node_id="node-A", gossip_events=[evt])
        accepted = broker.ingest_pending_gossip()
        self.assertEqual(len(accepted), 0)

    def test_ingest_discards_stale_peer_reading(self):
        evt = _gossip_event("node-B", age=_MAX_PEER_READING_AGE_S + 5)
        broker, *_ = _make_broker(gossip_events=[evt])
        accepted = broker.ingest_pending_gossip()
        self.assertEqual(len(accepted), 0)

    def test_ingest_ignores_non_market_events(self):
        evt = _gossip_event("node-B", event_type="federation_gossip.v1")
        broker, *_ = _make_broker(gossip_events=[evt])
        accepted = broker.ingest_pending_gossip()
        self.assertEqual(len(accepted), 0)

    def test_ingest_malformed_payload_discarded(self):
        bad_event = GossipEvent(
            event_id="bad-1", origin_peer_id="node-X", event_type=_MARKET_GOSSIP_EVENT_TYPE,
            payload={"market": {"broken": True}}, emitted_at=time.time(), lineage_digest="sha256:bad",
        )
        broker, *_ = _make_broker(gossip_events=[bad_event])
        accepted = broker.ingest_pending_gossip()
        self.assertEqual(len(accepted), 0)

    def test_ingest_multiple_peers(self):
        events = [
            _gossip_event("node-B", value=0.6, confidence=0.8),
            _gossip_event("node-C", value=0.7, confidence=0.9),
        ]
        broker, *_ = _make_broker(gossip_events=events)
        accepted = broker.ingest_pending_gossip()
        self.assertEqual(len(accepted), 2)
        node_ids = {r.node_id for r in accepted}
        self.assertEqual(node_ids, {"node-B", "node-C"})


# ---------------------------------------------------------------------------
# TestFederatedSignalBrokerAggregate
# ---------------------------------------------------------------------------

class TestFederatedSignalBrokerAggregate(unittest.TestCase):

    def _broker_with_peers(self, local_value, local_conf, peer_specs):
        """Build broker and inject peer readings directly."""
        broker, feed, peers, gossip = _make_broker(local_value=local_value, local_confidence=local_conf)
        for node_id, value, confidence in peer_specs:
            broker._peer_readings[node_id] = _peer_reading(node_id=node_id, value=value, confidence=confidence)
        return broker

    def test_cluster_composite_single_node_equals_local(self):
        broker, feed, peers, gossip = _make_broker(local_value=0.8, local_confidence=1.0)
        composite = broker.cluster_composite()
        self.assertAlmostEqual(composite, 0.8, places=4)

    def test_cluster_composite_weighted_average(self):
        # local: value=0.8, conf=1.0  peer: value=0.4, conf=1.0 → avg=0.6
        broker = self._broker_with_peers(0.8, 1.0, [("node-B", 0.4, 1.0)])
        composite = broker.cluster_composite()
        self.assertAlmostEqual(composite, 0.6, places=4)

    def test_cluster_composite_higher_confidence_dominates(self):
        # local: value=0.5, conf=0.1  peer: value=0.9, conf=0.9
        # weighted = (0.5*0.1 + 0.9*0.9) / (0.1+0.9) = (0.05+0.81)/1.0 = 0.86
        broker = self._broker_with_peers(0.5, 0.1, [("node-B", 0.9, 0.9)])
        composite = broker.cluster_composite()
        self.assertAlmostEqual(composite, 0.86, places=4)

    def test_cluster_composite_evicts_stale_peers(self):
        broker, feed, peers, gossip = _make_broker(local_value=0.7, local_confidence=1.0)
        # Inject stale peer reading (old timestamp)
        broker._peer_readings["node-B"] = _peer_reading(
            "node-B", value=0.1, confidence=0.9, age=_MAX_PEER_READING_AGE_S + 10
        )
        composite = broker.cluster_composite()
        # Stale peer evicted — only local reading remains
        self.assertAlmostEqual(composite, 0.7, places=4)
        self.assertNotIn("node-B", broker._peer_readings)

    def test_cluster_composite_zero_confidence_fallback(self):
        broker, feed, peers, gossip = _make_broker()
        feed.composite_reading.side_effect = RuntimeError("feed down")
        # No peer readings either — should return 0.5 neutral
        composite = broker.cluster_composite()
        self.assertAlmostEqual(composite, 0.5, places=4)

    def test_peer_reading_summary_includes_freshness(self):
        broker = self._broker_with_peers(0.7, 0.9, [("node-B", 0.6, 0.8)])
        summary = broker.peer_reading_summary()
        self.assertEqual(len(summary), 1)
        self.assertIn("fresh", summary[0])
        self.assertTrue(summary[0]["fresh"])

    def test_alive_peer_count(self):
        broker, feed, peers, gossip = _make_broker()
        self.assertEqual(broker.alive_peer_count(), 1)


# ---------------------------------------------------------------------------
# TestFederationMarketGossip
# ---------------------------------------------------------------------------

class TestFederationMarketGossip(unittest.TestCase):

    def test_round_trip(self):
        r = _reading(0.72, 0.88)
        payload = FederationMarketGossip.to_payload(r, "node-X")
        peer = FederationMarketGossip.from_payload(payload)
        self.assertIsNotNone(peer)
        self.assertAlmostEqual(peer.value, 0.72, places=4)
        self.assertAlmostEqual(peer.confidence, 0.88, places=4)
        self.assertEqual(peer.node_id, "node-X")

    def test_from_payload_malformed_returns_none(self):
        result = FederationMarketGossip.from_payload({"broken": True})
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
