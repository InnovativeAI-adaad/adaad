# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.governance.federation.node_supervisor import (
    FederationNodeSupervisor,
    NodeSupervisorJournalError,
)


pytestmark = pytest.mark.governance_gate


class _Registry:
    def alive_peers(self) -> list[str]:
        return ["peer-a"]

    def stale_peers(self) -> list[str]:
        return ["peer-b", "peer-c"]

    def is_partitioned(self, partition_threshold: float) -> bool:
        return partition_threshold <= 0.5


class _Gossip:
    def __init__(self) -> None:
        self.broadcasts: list[tuple[str, dict[str, object]]] = []

    def broadcast(self, event_type: str, payload: dict[str, object]) -> None:
        self.broadcasts.append((event_type, payload))


def _consensus() -> SimpleNamespace:
    return SimpleNamespace(
        role=SimpleNamespace(value="leader"),
        node_id="node-a",
        term=7,
        commit_index=11,
    )


def test_partition_journal_failure_is_surfaced_fail_closed() -> None:
    supervisor = FederationNodeSupervisor(
        registry=_Registry(),
        consensus=_consensus(),
        gossip=_Gossip(),
        journal_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("journal down")),
    )

    with pytest.raises(NodeSupervisorJournalError, match="journal_persistence_failed:federation_partition_detected.v1"):
        supervisor.tick()

    status = supervisor.last_journal_status
    assert status is not None
    assert status.ok is False
    assert status.reason == "journal_persistence_failed"
    assert status.error_type == "RuntimeError"
