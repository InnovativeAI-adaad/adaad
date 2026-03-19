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

## Replay traversal normalization (AEO ledger + index)

Replay graph traversal now uses `runtime/evolution/replay_graph_engine.py` to normalize nodes and edges from both AEO ledger events and AEO index documents before replay application.

Deterministic invariants:

- canonical stable topological order with lexical tie-breakers,
- strict lineage continuity checks (`mutation_id`, `parent_mutation_id`, `ancestor_chain`),
- fail-closed event hash and signature verification,
- pure in-memory traversal event emission only (no side effects).
