# SPDX-License-Identifier: Apache-2.0
"""Tests for Autonomous Multi-Node Federation — ADAAD-13 PR-13-02."""
from __future__ import annotations
import time
from datetime import datetime, timezone

import pytest
pytestmark = pytest.mark.regression_standard

class TestPeerRegistry:
    def _registry(self, self_id="node-1", endpoint="http://localhost:8001"):
        from runtime.governance.federation.peer_discovery import PeerRegistry
        return PeerRegistry(self_id=self_id, self_endpoint=endpoint)

    def test_register_peer(self):
        r = self._registry()
        r.register("node-2", "http://localhost:8002")
        peers = r.all_peers()
        assert any(p.peer_id == "node-2" for p in peers)

    def test_self_not_in_all_peers(self):
        r = self._registry()
        assert all(p.peer_id != "node-1" for p in r.all_peers())

    def test_heartbeat_updates_liveness(self):
        r = self._registry()
        r.register("node-3", "http://localhost:8003")
        ok = r.heartbeat("node-3")
        assert ok is True

    def test_stale_peer_detected_after_ttl(self):
        from runtime.governance.federation.peer_discovery import PeerRegistry
        r = PeerRegistry(self_id="n1", self_endpoint="http://x:1", peer_ttl_s=0.01)
        r.register("n2", "http://y:2")
        time.sleep(0.05)
        assert len(r.stale_peers()) == 1

    def test_alive_peers_within_ttl(self):
        r = self._registry()
        r.register("node-4", "http://localhost:8004")
        assert len(r.alive_peers()) == 1

    def test_deregister_removes_peer(self):
        r = self._registry()
        r.register("node-5", "http://localhost:8005")
        r.deregister("node-5")
        assert not any(p.peer_id == "node-5" for p in r.all_peers())

    def test_partition_detected_when_majority_stale(self):
        from runtime.governance.federation.peer_discovery import PeerRegistry
        r = PeerRegistry(self_id="n0", self_endpoint="http://x:0", peer_ttl_s=0.01)
        r.register("n1", "http://x:1"); r.register("n2", "http://x:2")
        time.sleep(0.05)
        assert r.is_partitioned(partition_threshold=0.5)

    def test_no_partition_when_all_alive(self):
        r = self._registry()
        r.register("n2", "http://x:2"); r.register("n3", "http://x:3")
        assert not r.is_partitioned()

    def test_idempotent_registration(self):
        r = self._registry()
        r.register("n2", "http://x:2")
        r.register("n2", "http://x:2-updated")
        assert len(r.all_peers()) == 1
        assert r.all_peers()[0].endpoint == "http://x:2-updated"


class TestGossipProtocol:
    def _setup(self):
        from runtime.governance.federation.peer_discovery import PeerRegistry, GossipProtocol
        r = PeerRegistry(self_id="node-g1", self_endpoint="http://g1:8080")
        g = GossipProtocol(registry=r)
        return r, g

    def _valid_raw_event(self, *, event_id: str = "e1", origin_peer_id: str = "n2", event_type: str = "test", payload=None):
        from runtime.governance.federation.peer_discovery import GossipEvent
        emitted_at = time.time()
        digest = GossipEvent.compute_lineage_digest(
            event_id=event_id,
            origin_peer_id=origin_peer_id,
            event_type=event_type,
            emitted_at=emitted_at,
        )
        return {
            "event_id": event_id,
            "origin_peer_id": origin_peer_id,
            "event_type": event_type,
            "payload": payload if payload is not None else {},
            "emitted_at": emitted_at,
            "lineage_digest": digest,
        }

    def test_receive_valid_event_enqueued(self):
        _, g = self._setup()
        raw = self._valid_raw_event()
        result = g.receive(raw)
        events = g.pending_events()
        assert result is not None
        assert len(events) == 1 and events[0].event_id == "e1"

    def test_receive_rejects_non_dict_payload(self):
        _, g = self._setup()
        raw = self._valid_raw_event(payload=["not", "a", "dict"])
        result = g.receive(raw)
        assert result is None
        assert g.pending_events() == []

    def test_receive_rejects_missing_or_bad_digest(self):
        _, g = self._setup()

        bad_digest = self._valid_raw_event()
        bad_digest["lineage_digest"] = "sha256:" + "0" * 64
        assert g.receive(bad_digest) is None

        missing_digest = self._valid_raw_event()
        del missing_digest["lineage_digest"]
        assert g.receive(missing_digest) is None

        assert g.pending_events() == []

    def test_receive_malformed_event_rejected(self):
        _, g = self._setup()
        result = g.receive({"bad_field": "value"})
        assert result is None

    def test_pending_events_drains_queue(self):
        _, g = self._setup()
        g.receive(self._valid_raw_event(event_id="e2", origin_peer_id="n3", event_type="sync"))
        g.pending_events()
        assert g.pending_events() == []

    def test_broadcast_with_no_alive_peers_returns_empty(self):
        _, g = self._setup()
        results = g.broadcast("test_event.v1", {"data": "x"})
        assert results == {}

    def test_gossip_event_build_has_sha256_digest(self):
        from runtime.governance.federation.peer_discovery import GossipEvent
        ev = GossipEvent.build(origin_peer_id="n1", event_type="test", payload={})
        assert ev.lineage_digest.startswith("sha256:")

    def test_journal_callback_exception_does_not_break_broadcast_flow(self):
        from runtime.governance.federation.peer_discovery import PeerRegistry, GossipProtocol

        def _boom(_event_type, _payload):
            raise RuntimeError("journal write failed")

        registry = PeerRegistry(self_id="node-g1", self_endpoint="http://g1:8080")
        gossip = GossipProtocol(registry=registry, journal_fn=_boom)

        results = gossip.broadcast("test_event.v1", {"data": "x"})

        assert results == {}

    def test_journal_callback_exception_emits_warning_log(self, caplog):
        from runtime.governance.federation.peer_discovery import PeerRegistry, GossipProtocol

        def _boom(_event_type, _payload):
            raise ValueError("journal offline")

        caplog.set_level("WARNING")
        registry = PeerRegistry(self_id="node-g1", self_endpoint="http://g1:8080")
        gossip = GossipProtocol(registry=registry, journal_fn=_boom)

        gossip.broadcast("test_event.v1", {"data": "x"})

        assert "GossipProtocol: journal callback failed for event_type=federation_gossip.v1 error=journal offline" in caplog.text


class TestFederationConsensusEngine:
    def _engine(self, node_id="node-1", peers=None):
        from runtime.governance.federation.consensus import FederationConsensusEngine
        return FederationConsensusEngine(node_id=node_id, peer_ids=peers or ["node-2","node-3"])

    def test_initial_role_is_follower(self):
        eng = self._engine()
        from runtime.governance.federation.consensus import NodeRole
        assert eng.role == NodeRole.FOLLOWER

    def test_start_election_transitions_to_candidate(self):
        eng = self._engine()
        from runtime.governance.federation.consensus import NodeRole
        eng.start_election()
        assert eng.role == NodeRole.CANDIDATE

    def test_election_won_on_majority_votes(self):
        eng = self._engine(peers=["n2","n3"])  # 3 total; need >1.5 = 2 votes
        from runtime.governance.federation.consensus import NodeRole
        eid = eng.start_election()  # self-vote = 1
        won = eng.receive_vote(eid, granted=True)  # vote 2 → majority (2/3 > 0.51)
        assert won is True
        assert eng.role == NodeRole.LEADER

    def test_append_entry_requires_leader(self):
        eng = self._engine()
        result = eng.append_entry("proposal", {"key": "val"})
        assert result is None  # not leader

    def test_leader_can_append_entry(self):
        eng = self._engine(peers=["n2"])  # 2 total; 1 self-vote = 50%, need >51% so 2 votes
        eid = eng.start_election()
        eng.receive_vote(eid, granted=True)  # now leader (2/2 = 100%)
        from runtime.governance.federation.consensus import NodeRole
        assert eng.role == NodeRole.LEADER
        entry = eng.append_entry("proposal", {"mutation": "x"})
        assert entry is not None
        assert entry.lineage_digest.startswith("sha256:")

    def test_commit_entry_updates_commit_index(self):
        eng = self._engine(peers=["n2"])
        eid = eng.start_election()
        eng.receive_vote(eid, granted=True)
        eng.append_entry("proposal", {})
        ok = eng.commit_entry(0)
        assert ok is True
        assert eng.commit_index == 0

    def test_quorum_required_for_policy_change(self):
        eng = self._engine()
        assert eng.quorum_required_for("policy_change") is True
        assert eng.quorum_required_for("proposal") is False

    def test_heartbeat_receive_resets_to_follower(self):
        eng = self._engine()
        from runtime.governance.federation.consensus import NodeRole
        eng.start_election()
        eng.receive_heartbeat(leader_id="node-2", leader_term=5)
        assert eng.role == NodeRole.FOLLOWER
        assert eng.leader_id == "node-2"

    def test_request_vote_granted_for_higher_term(self):
        eng = self._engine()
        result = eng.request_vote(candidate_id="node-2", candidate_term=10)
        assert result["vote_granted"] is True

    def test_request_vote_denied_for_stale_term(self):
        eng = self._engine()
        eng._state.current_term = 5
        result = eng.request_vote(candidate_id="node-2", candidate_term=3)
        assert result["vote_granted"] is False

    def test_journal_fail_open_emits_status_and_does_not_raise(self, caplog):
        from runtime.governance.federation.consensus import FederationConsensusEngine, JournalFailureMode
        caplog.set_level("ERROR")

        def _boom(_event_type, _payload):
            raise RuntimeError("journal unavailable")

        eng = FederationConsensusEngine(
            node_id="node-1",
            peer_ids=["node-2", "node-3"],
            journal_fn=_boom,
            journal_failure_mode=JournalFailureMode.FAIL_OPEN,
        )

        eng.start_election()

        status = eng.last_journal_status
        assert status is not None
        assert status.ok is False
        assert status.event_type == "federation_election_started.v1"
        assert status.exception_class == "RuntimeError"
        assert status.exception_message == "journal unavailable"
        assert status.fail_closed_triggered is False
        assert "federation_journal_write_failed" in caplog.text
        assert "exception_class=RuntimeError" in caplog.text
        assert "exception_message=journal unavailable" in caplog.text

    def test_journal_fail_closed_raises_for_critical_event(self):
        from runtime.governance.federation.consensus import FederationConsensusEngine, JournalFailureMode

        def _boom(_event_type, _payload):
            raise ValueError("write failed")

        eng = FederationConsensusEngine(
            node_id="node-1",
            peer_ids=["node-2", "node-3"],
            journal_fn=_boom,
            journal_failure_mode=JournalFailureMode.FAIL_CLOSED_CRITICAL,
        )

        with pytest.raises(ValueError, match="write failed"):
            eng.start_election()

        status = eng.last_journal_status
        assert status is not None
        assert status.ok is False
        assert status.fail_closed_triggered is True

    def test_log_entry_build_is_deterministic_for_identical_inputs(self):
        from runtime.governance.federation.consensus import LogEntry

        payload = {"z": 1, "nested": {"b": 2, "a": [3, 1]}}
        first = LogEntry.build(term=3, index=7, entry_type="proposal", payload=payload)
        second = LogEntry.build(term=3, index=7, entry_type="proposal", payload=payload)

        assert first.lineage_digest == second.lineage_digest

    def test_log_entry_digest_changes_when_payload_changes(self):
        from runtime.governance.federation.consensus import LogEntry

        base = LogEntry.build(term=3, index=7, entry_type="proposal", payload={"value": 1})
        mutated = LogEntry.build(term=3, index=7, entry_type="proposal", payload={"value": 2})

        assert base.lineage_digest != mutated.lineage_digest

    def test_log_entry_digest_is_stable_across_repeated_runs(self):
        from runtime.governance.federation.consensus import LogEntry

        payload = {"nested": {"y": [2, 1], "x": "v"}, "flag": True}
        digests = {
            LogEntry.build(term=11, index=4, entry_type="policy_change", payload=payload).lineage_digest
            for _ in range(25)
        }

        assert len(digests) == 1

    def test_commit_entry_rejects_tampered_digest(self):
        eng = self._engine(peers=["n2"])
        eid = eng.start_election()
        eng.receive_vote(eid, granted=True)
        entry = eng.append_entry("proposal", {"mutation": "x"})
        assert entry is not None

        eng._state.log[0] = type(entry)(
            term=entry.term,
            index=entry.index,
            entry_type=entry.entry_type,
            payload=entry.payload,
            lineage_digest="sha256:" + "0" * 64,
            committed=False,
        )

        assert eng.commit_entry(0) is False


class TestFederationNodeSupervisor:
    def _setup(self):
        from runtime.governance.federation.peer_discovery import PeerRegistry, GossipProtocol
        from runtime.governance.federation.consensus import FederationConsensusEngine
        from runtime.governance.federation.node_supervisor import FederationNodeSupervisor
        r = PeerRegistry(self_id="n1", self_endpoint="http://n1:8080")
        eng = FederationConsensusEngine(node_id="n1", peer_ids=[])
        g = GossipProtocol(registry=r)
        journal = []
        sup = FederationNodeSupervisor(registry=r, consensus=eng, gossip=g,
                                        journal_fn=lambda ev, p: journal.append((ev,p)))
        return sup, r, eng, journal

    def test_tick_returns_healthy_with_no_peers(self):
        sup, _, _, _ = self._setup()
        status = sup.tick()
        from runtime.governance.federation.node_supervisor import NodeSupervisorState
        assert status.state == NodeSupervisorState.HEALTHY

    def test_tick_safe_mode_on_partition(self):
        from runtime.governance.federation.peer_discovery import PeerRegistry, GossipProtocol
        from runtime.governance.federation.consensus import FederationConsensusEngine
        from runtime.governance.federation.node_supervisor import FederationNodeSupervisor, NodeSupervisorState
        r = PeerRegistry(self_id="n1", self_endpoint="http://n1:8080", peer_ttl_s=0.01)
        r.register("n2", "http://n2:8080"); r.register("n3", "http://n3:8080")
        time.sleep(0.05)
        eng = FederationConsensusEngine(node_id="n1", peer_ids=["n2","n3"])
        g = GossipProtocol(registry=r)
        sup = FederationNodeSupervisor(registry=r, consensus=eng, gossip=g)
        status = sup.tick()
        assert status.safe_mode_active is True

    def test_partition_journals_event(self):
        from runtime.governance.federation.peer_discovery import PeerRegistry, GossipProtocol
        from runtime.governance.federation.consensus import FederationConsensusEngine
        from runtime.governance.federation.node_supervisor import FederationNodeSupervisor
        r = PeerRegistry(self_id="n1", self_endpoint="http://n1:8080", peer_ttl_s=0.01)
        r.register("n2","http://n2:8080")
        time.sleep(0.05)
        eng = FederationConsensusEngine(node_id="n1", peer_ids=["n2"])
        g = GossipProtocol(registry=r)
        journal=[]
        sup = FederationNodeSupervisor(registry=r, consensus=eng, gossip=g,
                                        journal_fn=lambda ev,p: journal.append((ev,p)))
        sup.tick()
        assert any("partition" in ev for ev,_ in journal)


    def test_rejoin_cadence_uses_provider_time(self):
        from runtime.governance.federation.consensus import FederationConsensusEngine
        from runtime.governance.federation.node_supervisor import FederationNodeSupervisor, NodeSupervisorState

        class _Registry:
            def alive_peers(self):
                return []

            def stale_peers(self):
                return [object()]

            def is_partitioned(self, partition_threshold=0.5):
                _ = partition_threshold
                return True

        class _Gossip:
            def __init__(self):
                self.events = []

            def broadcast(self, event_type, payload):
                self.events.append((event_type, payload))

        class _Provider:
            deterministic = True

            def __init__(self, values):
                self._values = list(values)

            def now_utc(self):
                ts = self._values.pop(0)
                return datetime.fromtimestamp(ts, tz=timezone.utc)

        provider = _Provider([100.0, 101.0, 102.0, 103.0, 111.0, 112.0])
        gossip = _Gossip()
        supervisor = FederationNodeSupervisor(
            registry=_Registry(),
            consensus=FederationConsensusEngine(node_id="n1", peer_ids=[]),
            gossip=gossip,
            rejoin_interval_s=10.0,
            provider=provider,
        )

        supervisor.tick()
        supervisor.tick()
        supervisor.tick()

        rejoin_events = [event for event in gossip.events if event[0] == "federation_rejoin_request.v1"]
        assert len(rejoin_events) == 2
        assert rejoin_events[0][1]["requested_at"] == 101.0
        assert rejoin_events[1][1]["requested_at"] == 111.0
        assert supervisor._state == NodeSupervisorState.REJOINING

    def test_rejoin_behavior_is_stable_across_repeated_runs(self):
        from runtime.governance.federation.consensus import FederationConsensusEngine
        from runtime.governance.federation.node_supervisor import FederationNodeSupervisor

        class _Registry:
            def alive_peers(self):
                return []

            def stale_peers(self):
                return [object()]

            def is_partitioned(self, partition_threshold=0.5):
                _ = partition_threshold
                return True

        class _Gossip:
            def __init__(self):
                self.events = []

            def broadcast(self, event_type, payload):
                self.events.append((event_type, payload))

        class _Provider:
            deterministic = True

            def __init__(self, values):
                self._values = list(values)

            def now_utc(self):
                ts = self._values.pop(0)
                return datetime.fromtimestamp(ts, tz=timezone.utc)

        def _run_once():
            provider = _Provider([200.0, 201.0, 202.0, 203.0, 211.0, 212.0])
            gossip = _Gossip()
            journal = []
            supervisor = FederationNodeSupervisor(
                registry=_Registry(),
                consensus=FederationConsensusEngine(node_id="n1", peer_ids=[]),
                gossip=gossip,
                rejoin_interval_s=10.0,
                provider=provider,
                journal_fn=lambda event_type, payload: journal.append((event_type, payload)),
            )
            supervisor.tick()
            supervisor.tick()
            supervisor.tick()
            return gossip.events, journal

        first_events, first_journal = _run_once()
        second_events, second_journal = _run_once()

        assert first_events == second_events
        assert first_journal == second_journal
        assert first_journal[0][1]["detected_at"] == 200.0
        assert first_events[0][1]["requested_at"] == 201.0
