# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import base64

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from runtime.governance.federation.transport import (
    FederationTransportContractError,
    compute_message_digest,
    validate_canonical_federation_message,
)


def _signed_policy_exchange_message() -> dict[str, object]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    message: dict[str, object] = {
        "schema_id": "https://adaad.local/schemas/federation_policy_exchange.v1.json",
        "message_type": "policy_exchange",
        "payload": {
            "exchange_id": "ex-1",
            "source_peer_id": "node-a",
            "target_peer_id": "node-b",
            "policy_version": "2.1.0",
            "manifest_digest": "sha256:" + ("a" * 64),
            "sent_at_epoch": 100,
        },
    }
    digest = compute_message_digest(message)
    message["digest"] = digest
    message["signature"] = {
        "algorithm": "ed25519",
        "key_id": "node-a-key",
        "public_key": base64.b64encode(public_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)).decode("ascii"),
        "value": base64.b64encode(private_key.sign(digest.encode("utf-8"))).decode("ascii"),
    }
    return message


def test_valid_signature_and_digest_pass_validation() -> None:
    message = _signed_policy_exchange_message()

    validated = validate_canonical_federation_message(message)

    assert validated["digest"] == message["digest"]


def test_digest_mismatch_is_rejected_fail_closed() -> None:
    message = _signed_policy_exchange_message()
    message["payload"]["policy_version"] = "2.2.0"

    try:
        validate_canonical_federation_message(message)
    except FederationTransportContractError as exc:
        assert "$.digest:mismatch" in str(exc)
    else:
        raise AssertionError("expected digest mismatch rejection")


def test_invalid_signature_is_rejected_fail_closed() -> None:
    message = _signed_policy_exchange_message()
    signature = dict(message["signature"])
    signature["value"] = base64.b64encode(b"\x00" * 64).decode("ascii")
    message["signature"] = signature

    try:
        validate_canonical_federation_message(message)
    except FederationTransportContractError as exc:
        assert "$.signature:invalid" in str(exc)
    else:
        raise AssertionError("expected signature rejection")
