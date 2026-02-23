# Determinism Contract

ADAAD determinism ensures governance decisions and replay outcomes are reproducible for the same approved inputs.

## Replay contract

Replay compares current execution artifacts against canonical mutation and governance evidence for a target epoch.

A replay pass requires:
- identical policy-relevant inputs,
- identical governance constraints,
- deterministic runtime profile compliance,
- matching contract hashes for covered state.

## Hash boundaries

Deterministic boundaries include (at minimum):
- mutation manifest and governance payload hashes,
- replay attestation contract fields,
- lineage anchors and parent references,
- release evidence bundle integrity artifacts.

## What invalidates replay

Replay is invalidated when any covered deterministic input diverges, including:
- governance policy/constitution version drift,
- mutation manifest mismatch,
- lineage hash-chain mismatch,
- runtime profile lock mismatch,
- evidence bundle tampering.

## Mutation state inclusion/exclusion

### Included (governance-significant)
- mutation intent and manifest fields,
- policy decision artifacts,
- lineage/evidence references,
- replay attestation payloads.

### Excluded (non-governance runtime noise)
- non-deterministic telemetry fields not covered by replay contract,
- non-authoritative local environment metadata outside lock boundaries.

## Divergence detection

Divergence is detected by contract-level hash and schema validation against the recorded baseline, then surfaced as a fail-closed governance outcome.

## Formal guarantees vs non-guarantees

### Guarantees
- Replay mismatch prevents governed execution.
- Covered governance decisions are reproducible under contract constraints.
- Evidence and lineage artifacts are integrity-checked.

### Non-guarantees
- Determinism does not imply semantic perfection of a mutation.
- Determinism does not replace required human review policies.
- Determinism scope is limited to declared contract boundaries.
