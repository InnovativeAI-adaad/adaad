# Deterministic Evidence Normalization Contract

This repository now defines a shared evidence normalization contract in `runtime/evolution/evidence_contracts.py`.

## Required deterministic metadata

Every normalized evidence item must include:

- `source_id`
- `epoch_id`
- `canonical_digest`
- `schema_version`
- `deterministic_flags`

The canonical schema is `schemas/normalized_evidence_item.v1.json`.

## Fail-closed behavior

Normalization fails closed if required metadata is missing or if unexpected metadata fields are present.
