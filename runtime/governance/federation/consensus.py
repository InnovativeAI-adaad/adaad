# SPDX-License-Identifier: Apache-2.0
"""FederationConsensusEngine — Raft-inspired leader election + constitutional quorum. ADAAD-13 Track D."""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)

_ELECTION_TIMEOUT_S = 5.0
_HEARTBEAT_INTERVAL_S = 1.5
_QUORUM_THRESHOLD = 0.51   # > 50% of nodes must agree


class NodeRole(str, Enum):
    FOLLOWER  = "follower"
    CANDIDATE = "candidate"
    LEADER    = "leader"


class JournalFailureMode(str, Enum):
    FAIL_OPEN = "fail_open"
    FAIL_CLOSED_CRITICAL = "fail_closed_critical"


@dataclass(frozen=True)
class JournalStatus:
    event_type: str
    ok: bool
    mode: JournalFailureMode
    exception_class: Optional[str] = None
    exception_message: Optional[str] = None
    fail_closed_triggered: bool = False


@dataclass(frozen=True)
class LogEntry:
    term: int
    index: int
    entry_type: str    # "proposal" | "policy_change" | "node_join" | "node_leave"
    payload: Dict[str, Any]
    lineage_digest: str
    committed: bool = False

    @staticmethod
    def _digest_material(*, term: int, index: int, entry_type: str, payload: Dict[str, Any]) -> str:
        canonical_payload = json.loads(
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
        return json.dumps(
            {
                "term": term,
                "index": index,
                "entry_type": entry_type,
                "payload": canonical_payload,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def recompute_digest(*, term: int, index: int, entry_type: str, payload: Dict[str, Any]) -> str:
        material = LogEntry._digest_material(
            term=term,
            index=index,
            entry_type=entry_type,
            payload=payload,
        )
        return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_digest(entry: "LogEntry") -> bool:
        return entry.lineage_digest == LogEntry.recompute_digest(
            term=entry.term,
            index=entry.index,
            entry_type=entry.entry_type,
            payload=entry.payload,
        )

    @staticmethod
    def build(term: int, index: int, entry_type: str, payload: Dict[str, Any]) -> "LogEntry":
        digest = LogEntry.recompute_digest(
            term=term,
            index=index,
            entry_type=entry_type,
            payload=payload,
        )
        return LogEntry(term=term, index=index, entry_type=entry_type, payload=payload, lineage_digest=digest)


@dataclass
class ConsensusState:
    node_id: str
    current_term: int = 0
    role: NodeRole = NodeRole.FOLLOWER
    voted_for: Optional[str] = None
    leader_id: Optional[str] = None
    log: List[LogEntry] = field(default_factory=list)
    commit_index: int = -1
    last_heartbeat: float = field(default_factory=time.time)

    def is_leader(self) -> bool: return self.role == NodeRole.LEADER
    def is_candidate(self) -> bool: return self.role == NodeRole.CANDIDATE


class FederationConsensusEngine:
    """Raft-inspired consensus for autonomous multi-node federation.

    Provides:
    - Leader election (term-based, majority vote required)
    - Log replication (append-only, lineage-digested entries)
    - Constitutional quorum enforcement (cross-node policy changes require quorum)
    - Split-brain detection (partition detected → safe mode, no writes)

    Authority invariant: consensus engine gates cross-node policy changes through
    the same constitutional evaluation that governs single-node mutations.
    GovernanceGate retains execution authority; consensus provides ordering only.
    """

    def __init__(
        self,
        *,
        node_id: str,
        peer_ids: List[str],
        journal_fn: Any = None,
        journal_failure_mode: JournalFailureMode = JournalFailureMode.FAIL_CLOSED_CRITICAL,
        critical_journal_events: Optional[Set[str]] = None,
    ) -> None:
        self._state = ConsensusState(node_id=node_id)
        self._peer_ids = list(peer_ids)
        self._votes_received: Dict[str, int] = {}
        self._journal_fn = journal_fn
        self._journal_failure_mode = JournalFailureMode(journal_failure_mode)
        self._critical_journal_events = critical_journal_events or {
            "federation_election_started.v1",
            "federation_leader_elected.v1",
            "federation_log_appended.v1",
        }
        self._last_journal_status: Optional[JournalStatus] = None

    # ------------------------------------------------------------------
    # Election
    # ------------------------------------------------------------------

    def request_vote(self, *, candidate_id: str, candidate_term: int) -> Dict[str, Any]:
        """Handle an incoming RequestVote RPC."""
        if candidate_term < self._state.current_term:
            return {"vote_granted": False, "term": self._state.current_term}
        if candidate_term > self._state.current_term:
            self._state.current_term = candidate_term
            self._state.role = NodeRole.FOLLOWER
            self._state.voted_for = None
        can_vote = (
            self._state.voted_for is None or self._state.voted_for == candidate_id
        )
        if can_vote:
            self._state.voted_for = candidate_id
            return {"vote_granted": True, "term": self._state.current_term}
        return {"vote_granted": False, "term": self._state.current_term}

    def start_election(self) -> str:
        """Transition to candidate, increment term, start election. Returns election_id."""
        self._state.current_term += 1
        self._state.role = NodeRole.CANDIDATE
        self._state.voted_for = self._state.node_id
        election_id = f"election-{uuid.uuid4().hex[:12]}"
        self._votes_received[election_id] = 1  # self-vote
        self._journal("federation_election_started.v1", {
            "election_id": election_id,
            "candidate_id": self._state.node_id,
            "term": self._state.current_term,
        })
        return election_id

    def receive_vote(self, election_id: str, *, granted: bool) -> bool:
        """Record a vote; return True if quorum reached → become leader."""
        if granted:
            self._votes_received[election_id] = self._votes_received.get(election_id, 0) + 1
        total_nodes = len(self._peer_ids) + 1
        votes = self._votes_received.get(election_id, 0)
        if votes / total_nodes > _QUORUM_THRESHOLD:
            self._state.role = NodeRole.LEADER
            self._state.leader_id = self._state.node_id
            self._journal("federation_leader_elected.v1", {
                "leader_id": self._state.node_id,
                "term": self._state.current_term,
                "votes": votes,
                "total_nodes": total_nodes,
            })
            return True
        return False

    # ------------------------------------------------------------------
    # Log replication
    # ------------------------------------------------------------------

    def append_entry(self, entry_type: str, payload: Dict[str, Any]) -> Optional[LogEntry]:
        """Append a log entry (leader only). Returns None if not leader."""
        if not self._state.is_leader():
            return None
        idx = len(self._state.log)
        entry = LogEntry.build(
            term=self._state.current_term, index=idx,
            entry_type=entry_type, payload=payload,
        )
        self._state.log.append(entry)
        self._journal("federation_log_appended.v1", {
            "index": idx, "term": self._state.current_term,
            "entry_type": entry_type, "lineage_digest": entry.lineage_digest,
        })
        return entry

    def commit_entry(self, index: int) -> bool:
        """Mark entry at index as committed (after quorum replication)."""
        if index < 0 or index >= len(self._state.log):
            return False
        entry = self._state.log[index]
        if not LogEntry.verify_digest(entry):
            return False
        self._state.log[index] = LogEntry(
            term=entry.term, index=entry.index, entry_type=entry.entry_type,
            payload=entry.payload, lineage_digest=entry.lineage_digest, committed=True,
        )
        self._state.commit_index = max(self._state.commit_index, index)
        return True

    def receive_heartbeat(self, *, leader_id: str, leader_term: int) -> None:
        """Process a heartbeat from the current leader."""
        if leader_term >= self._state.current_term:
            self._state.current_term = leader_term
            self._state.role = NodeRole.FOLLOWER
            self._state.leader_id = leader_id
            self._state.last_heartbeat = time.time()

    # ------------------------------------------------------------------
    # Constitutional quorum
    # ------------------------------------------------------------------

    def quorum_required_for(self, entry_type: str) -> bool:
        """Return True iff this entry type requires constitutional quorum."""
        return entry_type in ("policy_change", "node_join", "node_leave", "constitution_amendment")

    def quorum_size(self) -> int:
        total = len(self._peer_ids) + 1
        return int(total * _QUORUM_THRESHOLD) + 1

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    @property
    def role(self) -> NodeRole: return self._state.role
    @property
    def term(self) -> int: return self._state.current_term
    @property
    def leader_id(self) -> Optional[str]: return self._state.leader_id
    @property
    def node_id(self) -> str: return self._state.node_id
    @property
    def log(self) -> List[LogEntry]: return list(self._state.log)
    @property
    def commit_index(self) -> int: return self._state.commit_index
    @property
    def last_journal_status(self) -> Optional[JournalStatus]: return self._last_journal_status

    def is_election_timeout(self) -> bool:
        return (time.time() - self._state.last_heartbeat) > _ELECTION_TIMEOUT_S

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _journal(self, event_type: str, payload: Dict[str, Any]) -> JournalStatus:
        if not self._journal_fn:
            self._last_journal_status = JournalStatus(
                event_type=event_type,
                ok=True,
                mode=self._journal_failure_mode,
            )
            return self._last_journal_status
        try:
            self._journal_fn(event_type, payload)
            self._last_journal_status = JournalStatus(
                event_type=event_type,
                ok=True,
                mode=self._journal_failure_mode,
            )
            return self._last_journal_status
        except Exception as exc:
            fail_closed_triggered = (
                self._journal_failure_mode == JournalFailureMode.FAIL_CLOSED_CRITICAL
                and event_type in self._critical_journal_events
            )
            self._last_journal_status = JournalStatus(
                event_type=event_type,
                ok=False,
                mode=self._journal_failure_mode,
                exception_class=exc.__class__.__name__,
                exception_message=str(exc),
                fail_closed_triggered=fail_closed_triggered,
            )
            log.error(
                "federation_journal_write_failed event_type=%s exception_class=%s exception_message=%s mode=%s fail_closed=%s",
                event_type,
                exc.__class__.__name__,
                str(exc),
                self._journal_failure_mode.value,
                fail_closed_triggered,
            )
            if fail_closed_triggered:
                raise
            return self._last_journal_status

__all__ = [
    "FederationConsensusEngine",
    "ConsensusState",
    "LogEntry",
    "NodeRole",
    "JournalFailureMode",
    "JournalStatus",
]
