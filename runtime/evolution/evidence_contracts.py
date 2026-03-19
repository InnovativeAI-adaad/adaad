# SPDX-License-Identifier: Apache-2.0
"""Shared deterministic contracts for evidence collection and normalization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from runtime import ROOT_DIR
from runtime.governance.deterministic_filesystem import read_file_deterministic

NORMALIZED_EVIDENCE_SCHEMA_VERSION = "normalized_evidence_item.v1"
DEFAULT_NORMALIZED_EVIDENCE_SCHEMA_PATH = ROOT_DIR / "schemas" / "normalized_evidence_item.v1.json"
_REQUIRED_METADATA_FIELDS = (
    "source_id",
    "epoch_id",
    "canonical_digest",
    "schema_version",
    "deterministic_flags",
)


class EvidenceContractsError(RuntimeError):
    """Raised when evidence normalization contracts are violated."""


class EvidenceCollector(Protocol):
    """Contract for deterministic evidence collectors."""

    def collect(self, *args: Any, **kwargs: Any) -> Sequence["NormalizedEvidenceItem"]:
        """Collect and return normalized deterministic evidence items."""


@dataclass(frozen=True)
class NormalizedEvidenceItem:
    """Deterministic evidence envelope used before bundle assembly."""

    source_id: str
    epoch_id: str
    canonical_digest: str
    schema_version: str
    deterministic_flags: tuple[str, ...]
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "epoch_id": self.epoch_id,
            "canonical_digest": self.canonical_digest,
            "schema_version": self.schema_version,
            "deterministic_flags": list(self.deterministic_flags),
            "payload": self.payload,
        }



def _json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"



def _validate_schema_subset(instance: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and _json_type_name(instance) != expected_type:
        return [f"{path}:expected_{expected_type}:got_{_json_type_name(instance)}"]

    if expected_type == "object":
        if not isinstance(instance, dict):
            return [f"{path}:not_object"]
        required = schema.get("required") or []
        for key in required:
            if key not in instance:
                errors.append(f"{path}.{key}:missing_required")
        properties = schema.get("properties") or {}
        for key, value in instance.items():
            if key in properties:
                errors.extend(_validate_schema_subset(value, properties[key], f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            extra_keys = sorted(set(instance.keys()) - set(properties.keys()))
            for key in extra_keys:
                errors.append(f"{path}.{key}:additional_property")

    if expected_type == "array":
        if not isinstance(instance, list):
            return [f"{path}:not_array"]
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, value in enumerate(instance):
                errors.extend(_validate_schema_subset(value, item_schema, f"{path}[{idx}]"))

    return errors



def load_normalized_item_schema(schema_path: Path = DEFAULT_NORMALIZED_EVIDENCE_SCHEMA_PATH) -> dict[str, Any]:
    if not schema_path.exists():
        raise EvidenceContractsError(f"missing_schema:{schema_path}")
    try:
        return json.loads(read_file_deterministic(schema_path))
    except json.JSONDecodeError as exc:
        raise EvidenceContractsError(f"invalid_schema_json:{schema_path}:{exc.msg}") from exc



def validate_normalized_item(item: NormalizedEvidenceItem, *, schema_path: Path = DEFAULT_NORMALIZED_EVIDENCE_SCHEMA_PATH) -> list[str]:
    return validate_normalized_payload(item.as_dict(), schema_path=schema_path)


def validate_normalized_payload(payload: Mapping[str, Any], *, schema_path: Path = DEFAULT_NORMALIZED_EVIDENCE_SCHEMA_PATH) -> list[str]:
    schema = load_normalized_item_schema(schema_path)
    candidate = dict(payload)
    errors = _validate_schema_subset(candidate, schema)
    metadata_keys = set(candidate.keys()) - {"payload"}
    missing = sorted(set(_REQUIRED_METADATA_FIELDS) - metadata_keys)
    for key in missing:
        errors.append(f"$.{key}:missing_required")
    extras = sorted(metadata_keys - set(_REQUIRED_METADATA_FIELDS))
    for key in extras:
        errors.append(f"$.{key}:unexpected_metadata")
    return errors


__all__ = [
    "DEFAULT_NORMALIZED_EVIDENCE_SCHEMA_PATH",
    "NORMALIZED_EVIDENCE_SCHEMA_VERSION",
    "EvidenceCollector",
    "EvidenceContractsError",
    "NormalizedEvidenceItem",
    "load_normalized_item_schema",
    "validate_normalized_item",
    "validate_normalized_payload",
]
