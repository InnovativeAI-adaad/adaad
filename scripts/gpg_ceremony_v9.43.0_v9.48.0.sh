#!/bin/bash
# ============================================================
# ADAAD GPG Tag Ceremony — v9.43.0 through v9.48.0 Backfill
# ============================================================
# EXECUTION TARGET : ADAADell (Founder Workstation ONLY)
# SIGNING KEY      : 4C95E2F99A775335B1CF3DAF247B015A1CCD95F6
# AUTHORIZED BY    : HUMAN-0 — Dustin L. Reid — Phase 116
# EVIDENCE REF     : ILA-116-2026-04-04-001
# ============================================================
set -euo pipefail

GPG_KEY="4C95E2F99A775335B1CF3DAF247B015A1CCD95F6"
REMOTE="origin"

echo "========================================"
echo " ADAAD GPG Ceremony — 6 Tag Backfill"
echo " Key: ${GPG_KEY}"
echo "========================================"

# Verify GPG key is available
gpg --list-secret-keys "${GPG_KEY}" > /dev/null 2>&1 || {
    echo "ERROR: GPG key ${GPG_KEY} not found. Run on ADAADell only."
    exit 1
}

# Pull latest to ensure SHAs are resolvable
git fetch --tags origin
git pull --ff-only origin main

declare -A TAG_MESSAGES=(
    ["v9.43.0"]="Phase 110 — INNOV-25 Hardware-Adaptive Fitness (HAF) | 3 invariants: HAF-0 HAF-DETERM-0 HAF-AUDIT-0 | cumulative: 113"
    ["v9.44.0"]="Phase 111 — INNOV-26 Constitutional Entropy Budget (CEB) | 3 invariants: CEB-0 CEB-DETERM-0 CEB-AUDIT-0 | cumulative: 116"
    ["v9.45.0"]="Phase 112 — INNOV-27 Mutation Blast Radius Modeling (BLAST) | 3 invariants: BLAST-0 BLAST-SLA-0 BLAST-AUDIT-0 | cumulative: 116"
    ["v9.46.0"]="Phase 113 — INNOV-28 Self-Awareness Invariant (SELF-AWARE) | 3 invariants: SELF-AWARE-0 SELF-AWARE-DETERM-0 SELF-AWARE-AUDIT-0 | cumulative: 119"
    ["v9.47.0"]="Phase 114 — INNOV-29 Curiosity-Driven Exploration (CURIOSITY) | 3 invariants: CURIOSITY-0 CURIOSITY-STOP-0 CURIOSITY-AUDIT-0 | cumulative: 122"
    ["v9.48.0"]="Phase 115 — INNOV-30 The Mirror Test (MIRROR) | 3 invariants: MIRROR-0 MIRROR-DETERM-0 MIRROR-AUDIT-0 | cumulative: 125 | PIPELINE COMPLETE"
)

SIGNED=0
for TAG in v9.43.0 v9.44.0 v9.45.0 v9.46.0 v9.47.0 v9.48.0; do
    MSG="${TAG_MESSAGES[$TAG]}"
    # Resolve the commit SHA for this tag (tag must exist as lightweight tag or be on main)
    SHA=$(git rev-list -n1 "${TAG}" 2>/dev/null || git rev-parse HEAD)
    echo ""
    echo "Signing ${TAG} @ ${SHA:0:7} ..."
    echo "  ${MSG}"
    git tag -s "${TAG}" "${SHA}" \
        -m "chore(tag): ${TAG} — ${MSG}" \
        --local-user="${GPG_KEY}" \
        --force
    git tag -v "${TAG}" 2>&1 | grep -E "Good signature|gpg:" | head -2
    SIGNED=$((SIGNED+1))
done

echo ""
echo "========================================"
echo " ${SIGNED}/6 tags signed."
echo " Verify all before push:"
echo "   git tag -v v9.43.0 v9.44.0 v9.45.0 v9.46.0 v9.47.0 v9.48.0"
echo ""
echo " Push with:"
echo "   git push origin v9.43.0 v9.44.0 v9.45.0 v9.46.0 v9.47.0 v9.48.0 --force"
echo "========================================"
