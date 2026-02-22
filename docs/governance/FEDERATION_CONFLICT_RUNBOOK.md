# Federation Conflict Runbook (v0.70.0 file-exchange mode)

## Scope

This runbook covers deterministic, file-based federation manifest exchange for air-gapped deployments.
Network transport is explicitly out of scope for v0.70.0.

## Split-brain detection

- Confirm `ADAAD_FEDERATION_ENABLED=true` only where federation coordination is intended.
- Load manifests from `runtime/governance/federation/manifests/`.
- Exclude stale manifests older than `ADAAD_FEDERATION_MANIFEST_TTL` seconds.
- Verify canonical JSON + HMAC signature for each manifest before classification.
- Classify peer compatibility as:
  - `full`: matching governance trust mode and law version.
  - `downlevel`: matching trust mode with compatible law-version family.
  - `incompatible`: trust mode mismatch or incompatible law family.

## Peer eviction procedure

1. Mark a peer as non-participating when manifests are stale, invalidly signed, or classified `incompatible`.
2. Record eviction rationale in governance operations evidence.
3. Do not delete historical evidence; use append-only lineage events.
4. Re-check peer eligibility only after a fresh, valid manifest is observed.

## Reconciliation workflow

1. Acquire an intent lock with `mutation_lock_{intent_id}.lock`.
2. If lock acquisition fails, treat as contention and retry after operator review.
3. Re-run manifest compatibility checks using current manifests only.
4. Apply governance precedence policy deterministically (`local`, `federated`, or `both`).
5. Release lock and persist reconciliation outcome in lineage records.

## Operational invariants

- Federation is opt-in; default behavior remains air-gapped (`ADAAD_FEDERATION_ENABLED=false`).
- Lock and manifest TTLs are bounded and deterministic.
- Signed manifest payloads are canonicalized for reproducible verification.
