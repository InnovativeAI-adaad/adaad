# SPDX-License-Identifier: Apache-2.0
"""Tests for ProposalTransportAdapter — Phase 5 transport wire-up."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard
from typing import Any, Dict, List
from unittest.mock import MagicMock, call

from runtime.governance.federation.proposal_transport_adapter import (
    ProposalTransportAdapter,
    FlushResult,
    ReceiveResult,
    _ENVELOPE_TYPE,
    _ENVELOPE_SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_proposal(
    proposal_id: str = "prop-001",
    source_epoch_id: str = "epoch-1",
    destination_repo: str = "repo-b",
    payload: Dict = None,
) -> MagicMock:
    p = MagicMock()
    p.proposal_id = proposal_id
    p.source_epoch_id = source_epoch_id
    p.destination_repo = destination_repo
    p.to_dict.return_value = payload or {
        "proposal_id": proposal_id,
        "source_repo": "repo-a",
        "source_epoch_id": source_epoch_id,
        "destination_repo": destination_repo,
    }
    return p


def _make_broker(
    pending: List = None,
    has_mark_sent: bool = True,
) -> MagicMock:
    broker = MagicMock()
    broker.pending_outbound.return_value = list(pending or [])
    if not has_mark_sent:
        del broker.mark_proposal_sent
    return broker


def _make_transport(inbound_envelopes: List = None) -> MagicMock:
    transport = MagicMock()
    transport.receive_handshake.return_value = list(inbound_envelopes or [])
    return transport


def _make_envelope(
    proposal_id: str = "prop-001",
    source_repo: str = "repo-a",
    envelope_type: str = _ENVELOPE_TYPE,
) -> Dict:
    return {
        "envelope_type": envelope_type,
        "schema_version": _ENVELOPE_SCHEMA_VERSION,
        "sender_peer_id": "repo-a-peer",
        "payload": {
            "proposal_id": proposal_id,
            "source_repo": source_repo,
            "source_epoch_id": "epoch-1",
        },
    }


def _make_adapter(
    local_peer_id: str = "local-node",
    audit_events: List = None,
) -> ProposalTransportAdapter:
    if audit_events is None:
        audit_events = []

    def _ledger(event_type, payload):
        audit_events.append({"event_type": event_type, "payload": payload})

    return ProposalTransportAdapter(
        local_peer_id=local_peer_id,
        ledger_append_event=_ledger,
    )


# ---------------------------------------------------------------------------
# FlushResult / ReceiveResult
# ---------------------------------------------------------------------------
class TestResultDataclasses:
    def test_flush_result_to_dict(self):
        r = FlushResult(sent=3, failed=1, errors=["err"])
        d = r.to_dict()
        assert d == {"sent": 3, "failed": 1, "errors": ["err"]}

    def test_receive_result_to_dict(self):
        r = ReceiveResult(received=5, delivered=4, skipped=1, errors=["bad"])
        d = r.to_dict()
        assert d == {"received": 5, "delivered": 4, "skipped": 1, "errors": ["bad"]}

    def test_flush_result_defaults(self):
        r = FlushResult()
        assert r.sent == 0 and r.failed == 0 and r.errors == []

    def test_receive_result_defaults(self):
        r = ReceiveResult()
        assert r.received == 0 and r.delivered == 0 and r.skipped == 0 and r.errors == []


# ---------------------------------------------------------------------------
# flush_outbound
# ---------------------------------------------------------------------------
class TestFlushOutbound:
    def test_no_pending_returns_zero_sent(self):
        adapter = _make_adapter()
        broker = _make_broker(pending=[])
        transport = _make_transport()

        result = adapter.flush_outbound(broker=broker, transport=transport)

        assert result.sent == 0
        assert result.failed == 0
        transport.send_handshake.assert_not_called()

    def test_sends_single_proposal(self):
        proposal = _make_proposal("prop-001", destination_repo="repo-b")
        broker = _make_broker(pending=[proposal])
        transport = _make_transport()
        adapter = _make_adapter()

        result = adapter.flush_outbound(broker=broker, transport=transport)

        assert result.sent == 1
        assert result.failed == 0
        transport.send_handshake.assert_called_once()

    def test_sends_multiple_proposals(self):
        proposals = [_make_proposal(f"prop-{i}") for i in range(3)]
        broker = _make_broker(pending=proposals)
        transport = _make_transport()
        adapter = _make_adapter()

        result = adapter.flush_outbound(broker=broker, transport=transport)

        assert result.sent == 3
        assert transport.send_handshake.call_count == 3

    def test_envelope_structure_is_correct(self):
        proposal = _make_proposal("prop-001", destination_repo="repo-b")
        broker = _make_broker(pending=[proposal])
        transport = _make_transport()
        adapter = _make_adapter(local_peer_id="my-node")

        adapter.flush_outbound(broker=broker, transport=transport)

        sent_envelope = transport.send_handshake.call_args.kwargs["envelope"]
        assert sent_envelope["envelope_type"] == _ENVELOPE_TYPE
        assert sent_envelope["schema_version"] == _ENVELOPE_SCHEMA_VERSION
        assert sent_envelope["sender_peer_id"] == "my-node"
        assert "payload" in sent_envelope

    def test_target_peer_id_uses_destination_repo(self):
        proposal = _make_proposal("prop-001", destination_repo="repo-dest")
        broker = _make_broker(pending=[proposal])
        transport = _make_transport()
        adapter = _make_adapter()

        adapter.flush_outbound(broker=broker, transport=transport)

        assert transport.send_handshake.call_args.kwargs["target_peer_id"] == "repo-dest"

    def test_mark_sent_called_on_broker(self):
        proposal = _make_proposal("prop-001")
        broker = _make_broker(pending=[proposal])
        transport = _make_transport()
        adapter = _make_adapter()

        adapter.flush_outbound(broker=broker, transport=transport)

        broker.mark_proposal_sent.assert_called_once_with("prop-001")

    def test_mark_sent_absent_does_not_raise(self):
        proposal = _make_proposal("prop-001")
        broker = _make_broker(pending=[proposal], has_mark_sent=False)
        transport = _make_transport()
        adapter = _make_adapter()

        result = adapter.flush_outbound(broker=broker, transport=transport)
        assert result.sent == 1

    def test_transport_send_failure_counts_failed(self):
        proposal = _make_proposal("prop-001")
        broker = _make_broker(pending=[proposal])
        transport = _make_transport()
        transport.send_handshake.side_effect = IOError("network_error")
        adapter = _make_adapter()

        result = adapter.flush_outbound(broker=broker, transport=transport)

        assert result.sent == 0
        assert result.failed == 1
        assert "network_error" in result.errors[0]

    def test_partial_send_failure_continues(self):
        proposals = [_make_proposal(f"prop-{i}") for i in range(3)]
        broker = _make_broker(pending=proposals)
        transport = _make_transport()
        transport.send_handshake.side_effect = [None, IOError("fail"), None]
        adapter = _make_adapter()

        result = adapter.flush_outbound(broker=broker, transport=transport)

        assert result.sent == 2
        assert result.failed == 1

    def test_audit_event_emitted_on_success(self):
        proposal = _make_proposal("prop-001")
        broker = _make_broker(pending=[proposal])
        transport = _make_transport()
        audit_events: List = []
        adapter = _make_adapter(audit_events=audit_events)

        adapter.flush_outbound(broker=broker, transport=transport)

        assert any(e["event_type"] == "federation_transport_proposal_sent" for e in audit_events)

    def test_audit_event_emitted_on_failure(self):
        proposal = _make_proposal("prop-001")
        broker = _make_broker(pending=[proposal])
        transport = _make_transport()
        transport.send_handshake.side_effect = IOError("err")
        audit_events: List = []
        adapter = _make_adapter(audit_events=audit_events)

        adapter.flush_outbound(broker=broker, transport=transport)

        assert any(e["event_type"] == "federation_transport_send_failed" for e in audit_events)

    def test_audit_failure_does_not_block_flush(self):
        proposal = _make_proposal("prop-001")
        broker = _make_broker(pending=[proposal])
        transport = _make_transport()

        def _bad_ledger(evt, payload):
            raise IOError("disk_full")

        adapter = ProposalTransportAdapter(
            local_peer_id="node",
            ledger_append_event=_bad_ledger,
        )
        result = adapter.flush_outbound(broker=broker, transport=transport)
        assert result.sent == 1


# ---------------------------------------------------------------------------
# receive_inbound
# ---------------------------------------------------------------------------
class TestReceiveInbound:
    def test_no_envelopes_returns_zero_delivered(self):
        broker = _make_broker()
        transport = _make_transport(inbound_envelopes=[])
        adapter = _make_adapter()

        result = adapter.receive_inbound(broker=broker, transport=transport)

        assert result.received == 0
        assert result.delivered == 0

    def test_delivers_valid_envelope(self):
        envelope = _make_envelope("prop-001")
        broker = _make_broker()
        transport = _make_transport(inbound_envelopes=[envelope])
        adapter = _make_adapter()

        result = adapter.receive_inbound(broker=broker, transport=transport)

        assert result.received == 1
        assert result.delivered == 1
        broker.receive_proposal.assert_called_once()

    def test_delivers_multiple_envelopes(self):
        envelopes = [_make_envelope(f"prop-{i}") for i in range(4)]
        broker = _make_broker()
        transport = _make_transport(inbound_envelopes=envelopes)
        adapter = _make_adapter()

        result = adapter.receive_inbound(broker=broker, transport=transport)

        assert result.received == 4
        assert result.delivered == 4
        assert broker.receive_proposal.call_count == 4

    def test_malformed_envelope_type_is_skipped(self):
        bad_envelope = {"envelope_type": "wrong_type", "payload": {}}
        broker = _make_broker()
        transport = _make_transport(inbound_envelopes=[bad_envelope])
        adapter = _make_adapter()

        result = adapter.receive_inbound(broker=broker, transport=transport)

        assert result.received == 1
        assert result.delivered == 0
        assert result.skipped == 1

    def test_envelope_without_payload_is_skipped(self):
        bad_envelope = {"envelope_type": _ENVELOPE_TYPE}
        broker = _make_broker()
        transport = _make_transport(inbound_envelopes=[bad_envelope])
        adapter = _make_adapter()

        result = adapter.receive_inbound(broker=broker, transport=transport)

        assert result.skipped == 1

    def test_non_dict_envelope_is_skipped(self):
        broker = _make_broker()
        transport = _make_transport(inbound_envelopes=["not a dict"])
        adapter = _make_adapter()

        result = adapter.receive_inbound(broker=broker, transport=transport)

        assert result.skipped == 1

    def test_partial_malformed_still_delivers_valid(self):
        good = _make_envelope("prop-good")
        bad = {"envelope_type": "wrong", "payload": {}}
        broker = _make_broker()
        transport = _make_transport(inbound_envelopes=[good, bad])
        adapter = _make_adapter()

        result = adapter.receive_inbound(broker=broker, transport=transport)

        assert result.received == 2
        assert result.delivered == 1
        assert result.skipped == 1

    def test_transport_receive_error_returns_empty_result(self):
        broker = _make_broker()
        transport = _make_transport()
        transport.receive_handshake.side_effect = IOError("network_down")
        adapter = _make_adapter()

        result = adapter.receive_inbound(broker=broker, transport=transport)

        assert result.received == 0
        assert "network_down" in result.errors[0]

    def test_broker_receive_error_counts_skipped(self):
        envelope = _make_envelope("prop-001")
        broker = _make_broker()
        broker.receive_proposal.side_effect = RuntimeError("broker_error")
        transport = _make_transport(inbound_envelopes=[envelope])
        adapter = _make_adapter()

        result = adapter.receive_inbound(broker=broker, transport=transport)

        assert result.skipped == 1
        assert result.delivered == 0

    def test_audit_event_emitted_on_delivery(self):
        envelope = _make_envelope("prop-001")
        broker = _make_broker()
        transport = _make_transport(inbound_envelopes=[envelope])
        audit_events: List = []
        adapter = _make_adapter(audit_events=audit_events)

        adapter.receive_inbound(broker=broker, transport=transport)

        assert any(
            e["event_type"] == "federation_transport_proposal_received"
            for e in audit_events
        )

    def test_audit_event_emitted_on_malformed(self):
        bad_envelope = {"envelope_type": "bad"}
        broker = _make_broker()
        transport = _make_transport(inbound_envelopes=[bad_envelope])
        audit_events: List = []
        adapter = _make_adapter(audit_events=audit_events)

        adapter.receive_inbound(broker=broker, transport=transport)

        assert any(
            e["event_type"] == "federation_transport_envelope_malformed"
            for e in audit_events
        )

    def test_receive_handshake_called_with_local_peer_id(self):
        broker = _make_broker()
        transport = _make_transport()
        adapter = _make_adapter(local_peer_id="my-peer-42")

        adapter.receive_inbound(broker=broker, transport=transport)

        transport.receive_handshake.assert_called_once_with(local_peer_id="my-peer-42")
