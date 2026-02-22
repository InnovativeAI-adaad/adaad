# Governance Schema Versioning and Migration Policy

## Scope
This policy governs JSON schemas under `schemas/` that define governance artifacts.

## Dialect and `$id` conventions
- **Single dialect**: all governance schemas MUST use JSON Schema draft 2020-12:
  - `$schema`: `https://json-schema.org/draft/2020-12/schema`
- **Canonical URL-style IDs**: each schema MUST use:
  - `$id`: `https://adaad.local/schemas/<filename>`
- Mixed-draft governance schemas are not permitted in the same major line.

## Versioning rules
- Schema filenames follow `<name>.v<major>.json`.
- Backward-compatible changes are patch/minor changes to content with unchanged filename and `schema_version` const.
- Breaking changes require a new major filename (`.v2.json`, `.v3.json`, ...).
- Existing major versions remain immutable once released, except for correctness fixes that do not broaden accepted payloads.

## Migration policy
- New major schemas MUST ship with:
  - A migration note describing source and target major versions.
  - Deterministic migration logic (no network calls, no time-dependent defaults).
  - Validation coverage in tests for both source and target schemas where applicable.
- Runtime validators MUST continue fail-closed behavior for unknown or malformed payloads.

## Validation gate
- All governance schemas are validated through a single helper path:
  - `runtime/governance/schema_validator.py`
- CI/local check entrypoint:
  - `python scripts/validate_governance_schemas.py`

## Regression prevention
- Any schema change MUST run:
  1. `python scripts/validate_governance_schemas.py`
  2. Relevant test targets covering schema consumers and validators.
- Pull requests that introduce mixed drafts or non-canonical `$id` values must be rejected.


## Release gate semantics migration (strict governance release workflow)
- Releases are now gated by `.github/workflows/governance_strict_release_gate.yml` for governance/public-readiness tag flows.
- Migration impact: release candidates must pass determinism lint, entropy discipline checks, governance strict-mode validation (including rule activation assertions), strict replay validation, and constitution fingerprint stability checks before gate completion.
- Operational expectation: any non-success state in a required strict-release job is release-blocking until resolved; there is no permissive skip path for these checks.

## Checkpoint governance event migration notes
- New schema contracts:
  - `schemas/checkpoint_event.v1.json` for `checkpoint_created` governance payloads emitted alongside legacy checkpoint materialization.
  - `schemas/checkpoint_chain_event.v1.json` for `checkpoint_chain_verified` and `checkpoint_chain_violated` verifier outcomes.
- Versioning:
  - Both contracts are introduced at `schema_version: "1.0"` and follow the same major-version compatibility rules defined above.
- Compatibility transition:
  - `EpochCheckpointEvent` remains append-compatible as the canonical replay/checkpoint material source for existing readers.
  - During migration, checkpoint producers emit both `EpochCheckpointEvent` and schema-bound governance event records (`checkpoint_created`) to preserve legacy replay consumers.
  - Verifier consumers should transition to governance chain events while retaining support for `verify_checkpoint_chain` return structure (`passed/errors`) until all downstream contracts consume `checkpoint_chain_*` records.
  - Historical ledgers are immutable; no backfill mutation is permitted. Consumers may compute read-time projections that join legacy `EpochCheckpointEvent` entries with new governance event payloads.
