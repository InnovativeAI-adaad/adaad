# SPDX-License-Identifier: Apache-2.0
"""Phase 6 acceptance tests for M6-04 (T6-04-01..10)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.federation.mutation_broker import (
    FederationAuditFailureMode,
    FederationMutationBroker,
    FederationMutationBrokerError,
)


def _make_broker(
    audit_events: list[tuple[str, dict[str, Any]]],
    *,
    audit_writer: Callable[[str, dict[str, Any]], None] | None = None,
    audit_failure_mode: FederationAuditFailureMode = FederationAuditFailureMode.FAIL_CLOSED_CRITICAL,
) -> FederationMutationBroker:
    writer = audit_writer or (lambda event, payload: audit_events.append((event, payload)))
    return FederationMutationBroker(
        local_repo="source-node",
        governance_gate=object(),
        lineage_chain_digest_fn=lambda: "sha256:" + "a" * 64,
        audit_writer=writer,
        audit_failure_mode=audit_failure_mode,
    )


def _write_hmac_key(tmp_path: Path) -> str:
    key_path = tmp_path / "federation_hmac.key"
    key_path.write_text("k" * 64, encoding="utf-8")
    return str(key_path)


def _propagate(
    *,
    broker: FederationMutationBroker,
    destination_nodes: list[dict[str, Any]],
    hmac_key_path: str,
    gate_evaluator: Callable[..., dict[str, Any]],
    mutation_writer: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None] | None = None,
    authority_level: str = "governor-review",
    replay_lineage_consistent: bool = True,
    source_gate_decision_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return broker.propagate_amendment(
        proposal_id="proposal-001",
        source_node="source-node",
        destination_nodes=destination_nodes,
        mutation_payload={"mutation_id": "roadmap-001", "lineage_chain": {}},
        source_gate_decision_payload=source_gate_decision_payload or {"approved": True, "decision_id": "src-1"},
        propagation_timestamp="2026-03-06T10:00:00Z",
        evidence_bundle_hash="sha256:" + "b" * 64,
        federation_hmac_key_path=hmac_key_path,
        authority_level=authority_level,
        replay_lineage_consistent=replay_lineage_consistent,
        destination_gate_evaluator=gate_evaluator,
        destination_mutation_writer=mutation_writer,
    )


# T6-04-01

def test_t6_04_01_all_gates_pass_destination_gets_proposed(tmp_path: Path) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    broker = _make_broker(events)
    destinations = [{"node_id": "peer-b"}, {"node_id": "peer-a"}]
    hmac_key_path = _write_hmac_key(tmp_path)

    payload = _propagate(
        broker=broker,
        destination_nodes=destinations,
        hmac_key_path=hmac_key_path,
        gate_evaluator=lambda *_args, **_kwargs: {"approved": True, "decision": "approved", "decision_id": "dest-1"},
    )

    assert payload["destination_nodes"] == ["peer-a", "peer-b"]
    assert all(node.get("applied_mutations") for node in destinations)
    assert events[-1][0] == "federated_amendment_propagated"


# T6-04-02

def test_t6_04_02_source_approval_does_not_bind_destination(tmp_path: Path) -> None:
    broker = _make_broker([])
    with pytest.raises(FederationMutationBrokerError, match="destination_gate_rejected"):
        _propagate(
            broker=broker,
            destination_nodes=[{"node_id": "peer-a"}],
            hmac_key_path=_write_hmac_key(tmp_path),
            source_gate_decision_payload={"approved": True, "decision_id": "source-approved"},
            gate_evaluator=lambda *_args, **_kwargs: {
                "approved": False,
                "decision": "destination-must-re-evaluate",
                "decision_id": "dest-reject-1",
            },
        )


# T6-04-03

def test_t6_04_03_divergence_blocks_and_keeps_peers_unchanged(tmp_path: Path) -> None:
    broker = _make_broker([])
    destinations = [{"node_id": "peer-a", "divergence_count": 1}]

    def divergence_gate(destination: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        if destination.get("divergence_count", 0) > 0:
            return {
                "approved": False,
                "decision": "PHASE6_FEDERATED_AMENDMENT_DIVERGENCE_BLOCKED",
                "decision_id": "dest-divergence",
            }
        return {"approved": True, "decision": "approved", "decision_id": "dest-ok"}

    with pytest.raises(FederationMutationBrokerError, match="PHASE6_FEDERATED_AMENDMENT_DIVERGENCE_BLOCKED"):
        _propagate(
            broker=broker,
            destination_nodes=destinations,
            hmac_key_path=_write_hmac_key(tmp_path),
            gate_evaluator=divergence_gate,
        )

    assert destinations[0].get("applied_mutations") is None


# T6-04-04

def test_t6_04_04_partial_failure_rolls_back_every_peer(tmp_path: Path) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    broker = _make_broker(events)
    destinations = [{"node_id": "peer-a"}, {"node_id": "peer-b"}]

    def fail_second_write(node: dict[str, Any], mutation_payload: dict[str, Any], gate_payload: dict[str, Any]) -> None:
        if node["node_id"] == "peer-b":
            raise RuntimeError("simulated write failure")
        broker._default_destination_mutation_writer(node, mutation_payload, gate_payload)

    with pytest.raises(FederationMutationBrokerError, match="federated_propagation_rolled_back"):
        _propagate(
            broker=broker,
            destination_nodes=destinations,
            hmac_key_path=_write_hmac_key(tmp_path),
            gate_evaluator=lambda *_args, **_kwargs: {"approved": True, "decision": "approved", "decision_id": "dest-1"},
            mutation_writer=fail_second_write,
        )

    assert all(node.get("applied_mutations") is None for node in destinations)
    assert events[-1][0] == "federated_amendment_rollback"


# T6-04-05

def test_t6_04_05_federation_origin_is_in_lineage_chain(tmp_path: Path) -> None:
    broker = _make_broker([])
    destination = {"node_id": "peer-a"}

    def writer_with_lineage(node: dict[str, Any], mutation_payload: dict[str, Any], gate_payload: dict[str, Any]) -> None:
        mutation_payload["lineage_chain"]["federation_origin"] = "source-node"
        broker._default_destination_mutation_writer(node, mutation_payload, gate_payload)

    _propagate(
        broker=broker,
        destination_nodes=[destination],
        hmac_key_path=_write_hmac_key(tmp_path),
        gate_evaluator=lambda *_args, **_kwargs: {"approved": True, "decision": "approved", "decision_id": "dest-1"},
        mutation_writer=writer_with_lineage,
    )

    applied = destination["applied_mutations"][0]["mutation"]
    assert applied["lineage_chain"]["federation_origin"] == "source-node"


# T6-04-06

def test_t6_04_06_missing_hmac_key_raises_federation_key_error(tmp_path: Path) -> None:
    broker = _make_broker([])
    validation_calls: list[str] = []

    def validate_hook(path: str) -> None:
        validation_calls.append(path)
        raise FederationMutationBrokerError("federation_hmac_required")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(broker, "_validate_federation_hmac_key_path", validate_hook)
        with pytest.raises(FederationMutationBrokerError, match="federation_hmac_required"):
            _propagate(
                broker=broker,
                destination_nodes=[{"node_id": "peer-a"}],
                hmac_key_path=str(tmp_path / "missing.key"),
                gate_evaluator=lambda *_args, **_kwargs: {"approved": True, "decision": "approved", "decision_id": "dest-1"},
            )

    assert validation_calls == [str(tmp_path / "missing.key")]


# T6-04-07

def test_t6_04_07_authority_violation_rejected(tmp_path: Path) -> None:
    broker = _make_broker([])
    with pytest.raises(FederationMutationBrokerError, match="PHASE6_FEDERATED_AUTHORITY_VIOLATION"):
        _propagate(
            broker=broker,
            destination_nodes=[{"node_id": "peer-a"}],
            hmac_key_path=_write_hmac_key(tmp_path),
            gate_evaluator=lambda *_args, **_kwargs: {"approved": True, "decision": "approved", "decision_id": "dest-1"},
            authority_level="agent-review",
        )


# T6-04-08

def test_t6_04_08_replay_hash_mismatch_halts_propagation(tmp_path: Path) -> None:
    broker = _make_broker([])
    destination = {"node_id": "peer-a"}
    with pytest.raises(FederationMutationBrokerError, match="PHASE6_FEDERATED_REPLAY_LINEAGE_INCONSISTENT"):
        _propagate(
            broker=broker,
            destination_nodes=[destination],
            hmac_key_path=_write_hmac_key(tmp_path),
            gate_evaluator=lambda *_args, **_kwargs: {"approved": True, "decision": "approved", "decision_id": "dest-1"},
            replay_lineage_consistent=False,
        )

    assert destination.get("applied_mutations") is None


# T6-04-09

def test_t6_04_09_ledger_event_emitted_for_source_and_all_peers(tmp_path: Path) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    broker = _make_broker(events)

    payload = _propagate(
        broker=broker,
        destination_nodes=[{"node_id": "peer-a"}, {"node_id": "peer-b"}],
        hmac_key_path=_write_hmac_key(tmp_path),
        gate_evaluator=lambda *_args, **_kwargs: {"approved": True, "decision": "approved", "decision_id": "dest-1"},
    )

    assert events[-1][0] == "federated_amendment_propagated"
    assert events[-1][1] == payload
    assert set(payload) == {
        "proposal_id",
        "source_node",
        "destination_nodes",
        "propagation_timestamp",
        "evidence_bundle_hash",
    }


# T6-04-10

def test_t6_04_10_pending_peer_blocks_storm_invariant(tmp_path: Path) -> None:
    broker = _make_broker([])

    def pending_storm_gate(destination: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        if destination.get("pending", False):
            return {
                "approved": False,
                "decision": "PHASE6_FEDERATED_AMENDMENT_STORM_BLOCKED",
                "decision_id": "dest-pending",
            }
        return {"approved": True, "decision": "approved", "decision_id": "dest-ok"}

    with pytest.raises(FederationMutationBrokerError, match="PHASE6_FEDERATED_AMENDMENT_STORM_BLOCKED"):
        _propagate(
            broker=broker,
            destination_nodes=[{"node_id": "peer-a", "pending": True}],
            hmac_key_path=_write_hmac_key(tmp_path),
            gate_evaluator=pending_storm_gate,
        )


def test_t6_04_11_propagation_audit_failure_is_surfaced_fail_closed(tmp_path: Path) -> None:
    def fail_on_propagate(event: str, _payload: dict[str, Any]) -> None:
        if event == "federated_amendment_propagated":
            raise RuntimeError("audit down")

    broker = _make_broker([], audit_writer=fail_on_propagate)

    with pytest.raises(FederationMutationBrokerError, match="audit_persistence_failed:federated_amendment_propagated"):
        _propagate(
            broker=broker,
            destination_nodes=[{"node_id": "peer-a"}],
            hmac_key_path=_write_hmac_key(tmp_path),
            gate_evaluator=lambda *_args, **_kwargs: {"approved": True, "decision": "approved", "decision_id": "dest-1"},
        )

    status = broker.last_audit_status
    assert status is not None
    assert status.ok is False
    assert status.reason == "audit_persistence_failed"
    assert status.error_type == "RuntimeError"


def test_t6_04_12_rollback_remains_deterministic_when_rollback_audit_fails_fail_open(tmp_path: Path) -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    def fail_on_rollback(event: str, payload: dict[str, Any]) -> None:
        if event == "federated_amendment_rollback":
            raise RuntimeError("rollback audit unavailable")
        events.append((event, payload))

    broker = _make_broker(
        events,
        audit_writer=fail_on_rollback,
        audit_failure_mode=FederationAuditFailureMode.FAIL_OPEN,
    )
    destinations = [{"node_id": "peer-a"}, {"node_id": "peer-b"}]

    def fail_second_write(node: dict[str, Any], mutation_payload: dict[str, Any], gate_payload: dict[str, Any]) -> None:
        if node["node_id"] == "peer-b":
            raise RuntimeError("simulated write failure")
        broker._default_destination_mutation_writer(node, mutation_payload, gate_payload)

    with pytest.raises(FederationMutationBrokerError, match="federated_propagation_rolled_back"):
        _propagate(
            broker=broker,
            destination_nodes=destinations,
            hmac_key_path=_write_hmac_key(tmp_path),
            gate_evaluator=lambda *_args, **_kwargs: {"approved": True, "decision": "approved", "decision_id": "dest-1"},
            mutation_writer=fail_second_write,
        )

    assert all(node.get("applied_mutations") is None for node in destinations)
    status = broker.last_audit_status
    assert status is not None
    assert status.ok is False
    assert status.reason == "audit_persistence_failed"
    assert status.error_type == "RuntimeError"
