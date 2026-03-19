# SPDX-License-Identifier: Apache-2.0
"""Deterministic replay manifest v1 canonicalization, signing, and persistence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from runtime import ROOT_DIR
from runtime.evolution.replay_attestation import sign_replay_payload_digest, verify_replay_payload_digest_signature
from runtime.governance.deterministic_filesystem import read_file_deterministic
from runtime.governance.foundation import canonical_json, sha256_prefixed_digest

REPLAY_MANIFEST_SCHEMA_PATH = ROOT_DIR / "schemas" / "replay_manifest.v1.json"
REPLAY_MANIFESTS_DIR = ROOT_DIR / "adaad" / "replay" / "manifests"
DEFAULT_REPLAY_MANIFEST_ALGORITHM = "hmac-sha256"
DEFAULT_REPLAY_MANIFEST_KEY_ID = "proof-key"


def _validate_schema_subset(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")

    if expected_type == "object":
        if not isinstance(instance, dict):
            return [f"{path}:type_error:expected_object"]
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}.{key}:missing_required")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, subschema in properties.items():
                if key in instance and isinstance(subschema, dict):
                    errors.extend(_validate_schema_subset(instance[key], subschema, f"{path}.{key}"))
        additional = schema.get("additionalProperties", True)
        if additional is False and isinstance(properties, dict):
            allowed = set(properties)
            for key in instance:
                if key not in allowed:
                    errors.append(f"{path}.{key}:unexpected_property")

    elif expected_type == "array":
        if not isinstance(instance, list):
            return [f"{path}:type_error:expected_array"]
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(instance):
                errors.extend(_validate_schema_subset(item, item_schema, f"{path}[{idx}]"))

    elif expected_type == "string":
        if not isinstance(instance, str):
            errors.append(f"{path}:type_error:expected_string")

    elif expected_type == "boolean":
        if not isinstance(instance, bool):
            errors.append(f"{path}:type_error:expected_boolean")

    elif expected_type == "integer":
        if not isinstance(instance, int) or isinstance(instance, bool):
            errors.append(f"{path}:type_error:expected_integer")

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and instance not in enum_values:
        errors.append(f"{path}:enum_error")

    pattern = schema.get("pattern")
    if isinstance(pattern, str) and isinstance(instance, str) and re.match(pattern, instance) is None:
        errors.append(f"{path}:pattern_mismatch")

    return errors


def _normalize_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized = {str(item).strip() for item in values if str(item).strip()}
    return sorted(normalized)


def _normalized_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    normalized = {
        "epoch_id": str(result.get("epoch_id") or ""),
        "decision": str(result.get("decision") or ""),
        "passed": bool(result.get("passed")),
        "replay_score": float(result.get("replay_score", 0.0)),
        "baseline_source": str(result.get("baseline_source") or ""),
        "digest_match": bool(result.get("digest_match")),
        "trusted": bool(result.get("trusted")),
    }
    indicators: list[str] = []
    cause_buckets = result.get("cause_buckets")
    if isinstance(cause_buckets, dict):
        for key in sorted(cause_buckets):
            if bool(cause_buckets.get(key)):
                indicators.append(f"cause:{key}")
    if bool(result.get("federation_drift_detected")):
        indicators.append("federation_drift_detected")
    if indicators:
        normalized["indicators"] = indicators
    return normalized


def _normalize_lineage_chain(results: Any) -> list[dict[str, Any]]:
    if not isinstance(results, list):
        return []
    entries = [_normalized_result(item) for item in results]
    entries = [item for item in entries if item]
    return sorted(entries, key=canonical_json)


def build_replay_manifest_v1(
    *,
    replay_started_at: str,
    replay_finished_at: str,
    preflight: Mapping[str, Any],
    halted: bool,
    algorithm: str = DEFAULT_REPLAY_MANIFEST_ALGORITHM,
    key_id: str = DEFAULT_REPLAY_MANIFEST_KEY_ID,
) -> dict[str, Any]:
    results = preflight.get("results")
    lineage_chain = _normalize_lineage_chain(results)
    evidence_items_consumed = _normalize_string_list([item.get("epoch_id") for item in lineage_chain if item.get("epoch_id")])

    divergence_indicators = _normalize_string_list(
        [
            *("result_divergence" for item in lineage_chain if not bool(item.get("passed"))),
            *("federation_drift_detected" for _ in [0] if bool(preflight.get("federation_drift_detected"))),
        ]
    )

    divergence_class = "none" if not divergence_indicators else ("federation_drift" if "federation_drift_detected" in divergence_indicators else "state_divergence")

    unsigned_manifest = {
        "replay_started_at": str(replay_started_at),
        "replay_finished_at": str(replay_finished_at),
        "evidence_items_consumed": evidence_items_consumed,
        "lineage_chain": lineage_chain,
        "reconstructed_state_hash": sha256_prefixed_digest(
            {
                "mode": str(preflight.get("mode") or ""),
                "verify_target": str(preflight.get("verify_target") or ""),
                "decision": str(preflight.get("decision") or ""),
                "lineage_chain": lineage_chain,
            }
        ),
        "divergence": {
            "class": divergence_class,
            "indicators": divergence_indicators,
            "halted": bool(halted),
        },
        "algorithm": algorithm,
        "key_id": key_id,
    }

    signed_digest = sha256_prefixed_digest(unsigned_manifest)
    signature = sign_replay_payload_digest(algorithm=algorithm, key_id=key_id, signed_digest=signed_digest)
    manifest = {**unsigned_manifest, "signature": signature}

    errors = validate_replay_manifest_schema(manifest)
    if errors:
        raise ValueError(f"replay_manifest_schema_validation_failed:{';'.join(errors)}")

    return manifest


def canonical_replay_manifest_bytes(manifest: Mapping[str, Any]) -> bytes:
    return (canonical_json(dict(manifest)) + "\n").encode("utf-8")


def replay_manifest_filename(manifest: Mapping[str, Any]) -> str:
    filename_digest = sha256_prefixed_digest(
        {
            "replay_started_at": manifest.get("replay_started_at"),
            "replay_finished_at": manifest.get("replay_finished_at"),
            "evidence_items_consumed": manifest.get("evidence_items_consumed", []),
            "lineage_chain": manifest.get("lineage_chain", []),
            "reconstructed_state_hash": manifest.get("reconstructed_state_hash"),
            "divergence": manifest.get("divergence", {}),
            "algorithm": manifest.get("algorithm"),
            "key_id": manifest.get("key_id"),
        }
    )
    return f"replay_manifest.v1.{filename_digest.split(':', 1)[1]}.json"


def write_replay_manifest_v1(manifest: Mapping[str, Any], *, manifests_dir: Path | None = None) -> Path:
    target_dir = manifests_dir or REPLAY_MANIFESTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / replay_manifest_filename(manifest)
    path.write_bytes(canonical_replay_manifest_bytes(manifest))
    return path


def verify_replay_manifest_signature(manifest: Mapping[str, Any]) -> bool:
    unsigned_manifest = {
        "replay_started_at": manifest.get("replay_started_at"),
        "replay_finished_at": manifest.get("replay_finished_at"),
        "evidence_items_consumed": manifest.get("evidence_items_consumed", []),
        "lineage_chain": manifest.get("lineage_chain", []),
        "reconstructed_state_hash": manifest.get("reconstructed_state_hash"),
        "divergence": manifest.get("divergence", {}),
        "algorithm": manifest.get("algorithm"),
        "key_id": manifest.get("key_id"),
    }
    signed_digest = sha256_prefixed_digest(unsigned_manifest)
    return verify_replay_payload_digest_signature(
        algorithm=str(manifest.get("algorithm") or ""),
        key_id=str(manifest.get("key_id") or ""),
        signed_digest=signed_digest,
        signature=str(manifest.get("signature") or ""),
    )


def validate_replay_manifest_schema(manifest: Mapping[str, Any]) -> list[str]:
    schema = json.loads(read_file_deterministic(REPLAY_MANIFEST_SCHEMA_PATH))
    return _validate_schema_subset(dict(manifest), schema)


__all__ = [
    "REPLAY_MANIFEST_SCHEMA_PATH",
    "REPLAY_MANIFESTS_DIR",
    "DEFAULT_REPLAY_MANIFEST_ALGORITHM",
    "DEFAULT_REPLAY_MANIFEST_KEY_ID",
    "build_replay_manifest_v1",
    "canonical_replay_manifest_bytes",
    "replay_manifest_filename",
    "write_replay_manifest_v1",
    "verify_replay_manifest_signature",
    "validate_replay_manifest_schema",
]
