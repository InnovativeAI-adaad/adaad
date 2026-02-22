# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from runtime.governance.federation import (
    FederationTransportContractError,
    LocalFederationTransport,
    validate_federation_transport_envelope,
)


def _envelope() -> dict[str, object]:
    return {
        "schema_id": "https://adaad.local/schemas/federation_transport_contract.v1.json",
        "protocol": "adaad.federation.transport",
        "protocol_version": "1.0",
        "envelope_id": "env-1",
        "source_peer_id": "node-a",
        "target_peer_id": "node-b",
        "sent_at_epoch": 1,
        "handshake": {
            "peer_id": "node-a",
            "policy_version": "2.1.0",
            "manifest_digest": "sha256:abc123",
            "decision": "accept",
        },
    }


def test_transport_contract_accepts_valid_envelope() -> None:
    envelope = _envelope()

    validated = validate_federation_transport_envelope(envelope)

    assert validated["schema_id"] == envelope["schema_id"]


def test_transport_contract_rejects_invalid_envelope() -> None:
    envelope = _envelope()
    envelope["handshake"] = {"peer_id": "node-a", "policy_version": "2.1.0", "manifest_digest": "invalid", "decision": "accept"}

    try:
        validate_federation_transport_envelope(envelope)
    except FederationTransportContractError as exc:
        assert "pattern_mismatch" in str(exc)
    else:
        raise AssertionError("expected FederationTransportContractError")


def test_local_transport_rejects_target_peer_mismatch() -> None:
    transport = LocalFederationTransport()

    try:
        transport.send_handshake(target_peer_id="node-z", envelope=_envelope())
    except FederationTransportContractError as exc:
        assert "target_mismatch" in str(exc)
    else:
        raise AssertionError("expected FederationTransportContractError")
