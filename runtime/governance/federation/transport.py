# SPDX-License-Identifier: Apache-2.0
"""Federation transport contract and deterministic local transport implementation."""

from __future__ import annotations

import base64
import binascii
import hmac
from hashlib import sha256
import json
import re
from typing import Any, Protocol

from runtime import ROOT_DIR
from runtime.governance.deterministic_filesystem import read_file_deterministic

_TRANSPORT_SCHEMA = "federation_transport_contract.v1.json"
_CANONICAL_MESSAGE_SCHEMAS = {
    "policy_exchange": "federation_policy_exchange.v1.json",
    "federation_vote": "federation_vote.v1.json",
    "replay_proof_bundle": "federation_replay_proof_bundle.v1.json",
}


class FederationTransportContractError(ValueError):
    """Raised when a transport handshake envelope violates the contract."""


class FederationTransport(Protocol):
    def send_handshake(self, *, target_peer_id: str, envelope: dict[str, Any]) -> None:
        """Send one validated handshake envelope to a target peer."""

    def receive_handshake(self, *, local_peer_id: str) -> list[dict[str, Any]]:
        """Receive queued handshake envelopes for a local peer deterministically."""


class LocalFederationTransport:
    """In-memory deterministic transport used for replay-safe tests and local wiring."""

    def __init__(self) -> None:
        self._mailbox: dict[str, list[dict[str, Any]]] = {}

    def send_handshake(self, *, target_peer_id: str, envelope: dict[str, Any]) -> None:
        validated = validate_federation_transport_envelope(envelope)
        if validated["target_peer_id"] != target_peer_id:
            raise FederationTransportContractError("$.target_peer_id:target_mismatch")
        self._mailbox.setdefault(target_peer_id, []).append(validated)

    def receive_handshake(self, *, local_peer_id: str) -> list[dict[str, Any]]:
        queued = self._mailbox.get(local_peer_id, [])
        ordered = sorted(
            queued,
            key=lambda row: (str(row.get("source_peer_id", "")), str(row.get("envelope_id", ""))),
        )
        self._mailbox[local_peer_id] = []
        return ordered


def _transport_schema() -> dict[str, Any]:
    path = ROOT_DIR / "schemas" / _TRANSPORT_SCHEMA
    return json.loads(read_file_deterministic(path))


def _is_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _validate(schema: dict[str, Any], payload: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _is_type(payload, expected_type):
        return [f"{path}:expected_{expected_type}"]

    if "const" in schema and payload != schema["const"]:
        errors.append(f"{path}:const_mismatch")

    enum = schema.get("enum")
    if isinstance(enum, list) and payload not in enum:
        errors.append(f"{path}:enum_mismatch")

    if isinstance(payload, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(payload) < minimum:
            errors.append(f"{path}:min_length")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.match(pattern, payload) is None:
            errors.append(f"{path}:pattern_mismatch")

    if isinstance(payload, int):
        minimum = schema.get("minimum")
        if isinstance(minimum, int) and payload < minimum:
            errors.append(f"{path}:minimum")

    if isinstance(payload, dict):
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        for key in required:
            if isinstance(key, str) and key not in payload:
                errors.append(f"{path}.{key}:missing_required")

        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        additional = schema.get("additionalProperties", True)
        for key, value in payload.items():
            if key in properties and isinstance(properties[key], dict):
                errors.extend(_validate(properties[key], value, f"{path}.{key}"))
            elif additional is False:
                errors.append(f"{path}.{key}:additional_property")
            elif isinstance(additional, dict):
                errors.extend(_validate(additional, value, f"{path}.{key}"))

    return errors


def validate_federation_transport_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    errors = _validate(_transport_schema(), envelope)
    if errors:
        raise FederationTransportContractError(";".join(sorted(errors)))
    return dict(envelope)


def _message_schema(schema_name: str) -> dict[str, Any]:
    path = ROOT_DIR / "schemas" / schema_name
    return json.loads(read_file_deterministic(path))


def canonicalize_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _message_payload_for_digest(message: dict[str, Any]) -> dict[str, Any]:
    message_type = message.get("message_type")
    payload = message.get("payload")
    if not isinstance(message_type, str) or not isinstance(payload, dict):
        raise FederationTransportContractError("$.message:invalid_shape")
    return {
        "message_type": message_type,
        "payload": payload,
    }


def compute_message_digest(message: dict[str, Any]) -> str:
    encoded = canonicalize_json(_message_payload_for_digest(message)).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def verify_message_digest(message: dict[str, Any]) -> None:
    digest = message.get("digest")
    if not isinstance(digest, str):
        raise FederationTransportContractError("$.digest:missing")
    expected = compute_message_digest(message)
    if not hmac.compare_digest(digest, expected):
        raise FederationTransportContractError("$.digest:mismatch")


def verify_message_signature(message: dict[str, Any]) -> None:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ModuleNotFoundError as exc:
        raise FederationTransportContractError("$.signature:verification_backend_missing") from exc

    signature = message.get("signature")
    if not isinstance(signature, dict):
        raise FederationTransportContractError("$.signature:expected_object")
    if signature.get("algorithm") != "ed25519":
        raise FederationTransportContractError("$.signature.algorithm:unsupported")

    public_key_b64 = signature.get("public_key")
    signature_b64 = signature.get("value")
    if not isinstance(public_key_b64, str) or not isinstance(signature_b64, str):
        raise FederationTransportContractError("$.signature:missing_material")

    try:
        public_key_raw = base64.b64decode(public_key_b64, validate=True)
        signature_raw = base64.b64decode(signature_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise FederationTransportContractError("$.signature:invalid_base64") from exc

    try:
        verifier = Ed25519PublicKey.from_public_bytes(public_key_raw)
        verifier.verify(signature_raw, compute_message_digest(message).encode("utf-8"))
    except (TypeError, ValueError, InvalidSignature) as exc:
        raise FederationTransportContractError("$.signature:invalid") from exc


def validate_canonical_federation_message(message: dict[str, Any]) -> dict[str, Any]:
    message_type = message.get("message_type")
    schema_name = _CANONICAL_MESSAGE_SCHEMAS.get(message_type)
    if schema_name is None:
        raise FederationTransportContractError("$.message_type:unsupported")

    errors = _validate(_message_schema(schema_name), message)
    if errors:
        raise FederationTransportContractError(";".join(sorted(errors)))

    verify_message_digest(message)
    verify_message_signature(message)
    return dict(message)


__all__ = [
    "FederationTransport",
    "FederationTransportContractError",
    "LocalFederationTransport",
    "canonicalize_json",
    "compute_message_digest",
    "validate_canonical_federation_message",
    "validate_federation_transport_envelope",
    "verify_message_digest",
    "verify_message_signature",
]
