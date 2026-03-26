# Evidence Orchestration Subsystem (Deterministic Contract)

## Scope

This document defines deterministic subsystem behavior for evidence bundle orchestration in ADAAD runtime/governance flows, including canonical normalization, signing secret resolution, append-only ledger + lineage invariants, and replay verification guarantees.

Primary implementation surfaces:

- `runtime/evolution/evidence_bundle.py`
- `runtime/evolution/lineage_v2.py`
- `runtime/evolution/replay.py`
- `scripts/validate_evidence_subsystem_determinism.py`
- `tests/evolution/test_evidence_subsystem_determinism.py`

---

## 1) Deterministic ordering rules

The subsystem must produce identical outputs for identical logical inputs.

1. **Canonical object serialization**
   - All bundle digest material uses canonical JSON (`sort_keys=True`) via `canonical_json`.
   - Digest identity excludes transport-only fields and is generated from deterministic core payload.

2. **Stable sequence ordering**
   - Bundle index ordering key: `(epoch_id, bundle_id, bundle_digest)`.
   - Sandbox evidence ordering key: `(epoch_id, bundle_id, entry_hash)`.
   - Replay proofs ordering key: `epoch_id`.
   - Federated verification ordering key: `(epoch_id, proposal_id)`.

3. **Epoch-range normalization**
   - Requested epoch interval resolves to known epochs and is normalized to ascending sorted order.

4. **No entropy in ordering path**
   - No random/shuffled ordering, no dependency on filesystem listing order, and no wall-clock ordering in digest-critical fields.

---

## 2) Normalization canonical form

Normalization contract for evidence bundle construction:

1. **JSON form**
   - UTF-8, deterministic key order, canonical separators.
   - Numeric/string values represented as stable Python primitives before serialization.

2. **Schema form**
   - Bundle schema version: `evidence_bundle.v1`.
   - Required deterministic roots include:
     - `schema_version`
     - `export_scope`
     - `replay_proofs`
     - `lineage_anchors`
     - `bundle_index`
     - `export_metadata`

3. **Digest form**
   - Core digest: `sha256:<hex64>` over canonicalized core bundle.
   - Bundle ID derives from digest prefix (`evidence-<16hex>`).

4. **Legacy compatibility**
   - Legacy bundle validation is only allowed where explicitly enabled and non-strict governance contexts permit it.

---

## 3) Signing secret resolution rules

The evidence signer uses strict fail-closed resolution:

1. Resolve `key_id` from `ADAAD_EVIDENCE_BUNDLE_KEY_ID` (default: `forensics-dev`).
2. Attempt key-specific env var:
   - `ADAAD_EVIDENCE_BUNDLE_KEY_<KEY_ID_NORMALIZED>`
3. Fallback to generic env var:
   - `ADAAD_EVIDENCE_BUNDLE_SIGNING_KEY`
4. If neither is present, fail closed with:
   - `missing_export_signing_secret:<key_id>`

Signature material contract:

- `signature = sha256(secret + ":" + signed_digest)`
- `signed_digest` equals deterministic bundle digest.

---

## 4) Append-only ledger + lineage graph invariants

The lineage and evidence system is append-only and hash-chained.

1. **Append-only invariant**
   - New events append to JSONL; existing lines are immutable.
   - Any overwrite divergence of persisted evidence export is rejected (`immutable_export_mismatch`).

2. **Hash-chain invariant**
   - Each lineage row includes `prev_hash` + `hash`.
   - Verification recomputes hashes deterministically and fails on mismatch.

3. **Epoch digest invariant**
   - Bundle events advance per-epoch digest chain deterministically:
     - `epoch_digest = sha256(previous_epoch_digest + bundle_digest)`.

4. **Lineage anchor invariant**
   - `lineage_anchors` include expected + incremental epoch digests and sorted bundle IDs.
   - Identical event streams must yield identical lineage anchors.

---

## 5) Replay reconstruction and verification path

Replay verification path is deterministic and fail-closed:

1. **Reconstruction source**
   - Read append-only lineage ledger in append order.
   - Extract epoch-scoped events deterministically.

2. **Replay execution**
   - Replay engine recomputes epoch digest/canonical digest and event count.

3. **Bundle-level inclusion**
   - `replay_proofs` emitted per epoch and sorted by epoch id.

4. **Verification assertion**
   - Two independent reconstructions from equivalent synthetic event streams must produce:
     - identical `export_metadata.digest`
     - identical signer signature
     - identical `lineage_anchors`
     - identical canonical bundle payload

---

## 6) CI fail-closed gate

CI includes a deterministic validator script:

- `python scripts/validate_evidence_subsystem_determinism.py`

Behavior:

- Creates two isolated synthetic runs.
- Emits deterministic mutation + governance + epoch events.
- Builds evidence bundles in each run.
- Compares digest/signature/lineage/canonical JSON.
- Returns non-zero on any divergence.

This gate is wired as fail-closed in `.github/workflows/ci.yml`.

---

## 7) Release decision bundle ID derivation (script contract)

`scripts/orchestrate_release_candidates.py` emits deterministic release decision bundle IDs.

Contract:

1. Canonicalize a material object containing:
   - `release_inputs` (raw candidate payload),
   - `release_version` (`release_version` or `version` metadata; fallback `unknown-version`),
   - `lane` (`lane` or `control_lane`; fallback `unknown-lane`).
2. Compute SHA-256 over canonical JSON (`sort_keys=True`, canonical separators).
3. Emit a human-readable ID: `release-decision-<12hex>`.

Compatibility note:

- Validators/parsers must accept digest-suffix IDs and must not require epoch-second numeric suffixes.
