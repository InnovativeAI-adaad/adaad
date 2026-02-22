# SPDX-License-Identifier: Apache-2.0
"""Federation transport contract and deterministic local transport implementation."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from runtime import ROOT_DIR
from runtime.governance.deterministic_filesystem import read_file_deterministic

_TRANSPORT_SCHEMA = "federation_transport_contract.v1.json"


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


def _schema() -> dict[str, Any]:
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
    errors = _validate(_schema(), envelope)
    if errors:
        raise FederationTransportContractError(";".join(sorted(errors)))
    return dict(envelope)


__all__ = [
    "FederationTransport",
    "FederationTransportContractError",
    "LocalFederationTransport",
    "validate_federation_transport_envelope",
]
