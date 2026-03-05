# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import base64

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from runtime.governance.federation.transport import FederationTransportContractError, compute_message_digest, verify_message_signature


def _build_signed_message(private_key: Ed25519PrivateKey, *, key_id: str = "federation-root-1") -> dict[str, object]:
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
        "key_id": key_id,
        "signature": base64.b64encode(private_key.sign(digest.encode("utf-8"))).decode("ascii"),
    }
    return message


def _raise_untrusted(key_id: str) -> str:
    raise FederationTransportContractError(f"federation_key_id_untrusted:{key_id}")


def test_trusted_key_id_valid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = Ed25519PrivateKey.generate()
    trusted_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    monkeypatch.setattr("runtime.governance.federation.transport.get_trusted_public_key", lambda _key_id: trusted_pem)

    verify_message_signature(_build_signed_message(private_key))


def test_untrusted_key_id_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr("runtime.governance.federation.transport.get_trusted_public_key", _raise_untrusted)

    with pytest.raises(FederationTransportContractError, match="federation_key_id_untrusted:federation-root-1"):
        verify_message_signature(_build_signed_message(private_key))


def test_missing_key_id_rejected() -> None:
    private_key = Ed25519PrivateKey.generate()
    message = _build_signed_message(private_key)
    message["signature"] = {"algorithm": "ed25519", "signature": message["signature"]["signature"]}

    with pytest.raises(FederationTransportContractError, match=r"\$\.signature.key_id:missing"):
        verify_message_signature(message)


def test_caller_supplied_public_key_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    trusted_private = Ed25519PrivateKey.generate()
    attacker_private = Ed25519PrivateKey.generate()

    trusted_pem = trusted_private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    monkeypatch.setattr("runtime.governance.federation.transport.get_trusted_public_key", lambda _key_id: trusted_pem)

    message = _build_signed_message(trusted_private)
    attacker_pem = attacker_private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    message["signature"]["public_key"] = attacker_pem

    verify_message_signature(message)
