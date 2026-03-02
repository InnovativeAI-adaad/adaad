#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <artifact_type> <input_json> <output_signed_json>" >&2
  exit 2
fi

ARTIFACT_TYPE="$1"
INPUT_PATH="$2"
OUTPUT_PATH="$3"

: "${ADAAD_ARTIFACT_SIGNER_ALGORITHM:=hmac-sha256}"
: "${ADAAD_ARTIFACT_SIGNER_KEY_ID:=}"

PYTHONPATH=. python - "$ARTIFACT_TYPE" "$INPUT_PATH" "$OUTPUT_PATH" <<'PY'
import json
import os
import sys
from pathlib import Path
from typing import Any

from runtime.governance.policy_artifact import (
    GovernanceKeyRotationMetadata,
    GovernancePolicyArtifactEnvelope,
    GovernanceSignerMetadata,
    policy_artifact_digest,
)
from security import cryovant


def _load_rotation_metadata() -> dict[str, Any]:
    rotation_path = os.getenv("ADAAD_ARTIFACT_ROTATION_METADATA", "").strip()
    if not rotation_path:
        return {}
    raw = Path(rotation_path)
    if not raw.exists():
        raise ValueError(f"rotation_metadata_missing:{rotation_path}")
    metadata = json.loads(raw.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("rotation_metadata_invalid")
    return metadata


def _ordered_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized = [str(item).strip() for item in value if str(item).strip()]
    return sorted(dict.fromkeys(normalized))


def _choose_key_id(metadata: dict[str, Any], requested_key_id: str) -> str:
    if requested_key_id:
        return requested_key_id
    active = str(metadata.get("active_key_id") or "").strip()
    if active:
        return active
    trusted = _ordered_ids(metadata.get("trusted_key_ids"))
    if trusted:
        return trusted[0]
    return "policy-signer-prod-1"


artifact_type = sys.argv[1]
src = Path(sys.argv[2])
out = Path(sys.argv[3])
artifact = json.loads(src.read_text(encoding="utf-8"))

metadata = _load_rotation_metadata()
algorithm = os.getenv("ADAAD_ARTIFACT_SIGNER_ALGORITHM", "hmac-sha256").strip() or "hmac-sha256"
requested_key_id = os.getenv("ADAAD_ARTIFACT_SIGNER_KEY_ID", "").strip()
key_id = _choose_key_id(metadata, requested_key_id)
trusted_key_ids = _ordered_ids(metadata.get("trusted_key_ids"))
if trusted_key_ids and key_id not in trusted_key_ids:
    raise ValueError("selected_key_not_in_trusted_set")

artifact["signer"] = {
    "key_id": key_id,
    "algorithm": algorithm,
    "trusted_key_ids": trusted_key_ids,
}

if metadata:
    artifact["key_rotation"] = {
        "active_key_id": str(metadata.get("active_key_id") or key_id),
        "overlap_key_ids": _ordered_ids(metadata.get("overlap_key_ids")),
        "overlap_until_epoch": int(metadata.get("overlap_until_epoch", artifact.get("effective_epoch", 0))),
    }

if artifact_type not in {"policy_artifact", "generic_json"}:
    raise ValueError(f"unsupported_artifact_type:{artifact_type}")

envelope = GovernancePolicyArtifactEnvelope(
    schema_version=str(artifact["schema_version"]),
    payload=dict(artifact["payload"]),
    signer=GovernanceSignerMetadata(
        key_id=key_id,
        algorithm=algorithm,
        trusted_key_ids=tuple(trusted_key_ids),
    ),
    signature="",
    previous_artifact_hash=str(artifact["previous_artifact_hash"]),
    effective_epoch=int(artifact["effective_epoch"]),
    key_rotation=(
        GovernanceKeyRotationMetadata(
            active_key_id=str(artifact["key_rotation"]["active_key_id"]),
            overlap_key_ids=tuple(_ordered_ids(artifact["key_rotation"]["overlap_key_ids"])),
            overlap_until_epoch=int(artifact["key_rotation"]["overlap_until_epoch"]),
        )
        if isinstance(artifact.get("key_rotation"), dict)
        else None
    ),
)

artifact["signature"] = cryovant.sign_artifact_hmac_digest(
    artifact_type="policy_artifact" if artifact_type == "policy_artifact" else "replay_proof",
    key_id=key_id,
    signed_digest=policy_artifact_digest(envelope),
)
out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
print(out)
PY
