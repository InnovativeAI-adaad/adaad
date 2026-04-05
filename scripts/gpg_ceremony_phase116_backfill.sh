#!/usr/bin/env bash
# ADAAD GPG Ceremony — Phase 116 Backfill
# Target: ADAADell (Founder Workstation)

set -euo pipefail

KEY_ID="4C95E2F99A775335B1CF3DAF247B015A1CCD95F6"

declare -A TAG_PHASES=(
  ["v9.43.0"]="Phase 110"
  ["v9.44.0"]="Phase 111"
  ["v9.45.0"]="Phase 112"
  ["v9.46.0"]="Phase 113"
  ["v9.47.0"]="Phase 114"
  ["v9.48.0"]="Phase 115"
  ["v9.49.0"]="Phase 116"
)

echo "Starting GPG Ceremony backfill..."

for tag in "${!TAG_PHASES[@]}"; do
  phase="${TAG_PHASES[$tag]}"
  echo "Resolving commit for $tag ($phase)..."
  sha=$(git log --oneline --grep="$phase" -n 1 | cut -d' ' -f1)
  
  if [[ -z "$sha" ]]; then
    echo "WARNING: Could not resolve commit for $tag ($phase). Skipping."
    continue
  fi
  
  echo "Signing $tag on commit $sha..."
  git tag -s "$tag" "$sha" -u "$KEY_ID" -m "chore(tag): $tag — $phase backfill" --force
done

echo "Ceremony complete."
echo "To push: git push origin --tags --force"
