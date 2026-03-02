#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <input_policy_json> <output_signed_json>" >&2
  exit 2
fi

INPUT_PATH="$1"
OUTPUT_PATH="$2"

: "${ADAAD_POLICY_SIGNER_KEY_ID:=policy-signer-prod-1}"
: "${ADAAD_POLICY_ARTIFACT_SIGNING_KEY:?ADAAD_POLICY_ARTIFACT_SIGNING_KEY must be set}"

ADAAD_ARTIFACT_SIGNER_KEY_ID="${ADAAD_POLICY_SIGNER_KEY_ID}" \
ADAAD_ARTIFACT_SIGNER_ALGORITHM="hmac-sha256" \
ADAAD_POLICY_ARTIFACT_SIGNING_KEY="${ADAAD_POLICY_ARTIFACT_SIGNING_KEY}" \
"$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/sign_artifact.sh" \
  policy_artifact "${INPUT_PATH}" "${OUTPUT_PATH}"
