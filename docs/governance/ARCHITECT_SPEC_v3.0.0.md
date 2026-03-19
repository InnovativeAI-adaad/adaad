# ArchitectAgent Constitutional Specification — v3.0.0

![Governance: Fail-Closed](https://img.shields.io/badge/Governance-Fail--Closed-critical)
![ArchitectAgent: Canonical](https://img.shields.io/badge/ArchitectAgent-Canonical-a855f7)
![Version: 9.12.1](https://img.shields.io/badge/version-9.12.1-00d4ff)
![Phase: 5 — Multi-Repo Federation](https://img.shields.io/badge/Phase_5-Multi--Repo_Federation-f59e0b)

> **Authority:** ArchitectAgent · ADAAD Constitutional Governance
> **Scope:** Phase 5 — Multi-Repo Federation and all subsystems active in v3.0.0
> **Effective:** 2026-03-06
> **Supersedes:** `ARCHITECT_SPEC_v2.0.0.md` (v2.0.0–v2.3.0 coverage)
> **Status:** CANONICAL — machine-interpretable, audit-ready, replay-verifiable


> [!IMPORTANT]
> **Canonical source (PR sequence control):** `docs/governance/ADAAD_PR_PROCESSION_2026-03.md` is the controlling source for Phase 5 PR IDs, dependency chain, milestone/CI tier flags, and per-PR acceptance gates. This document mirrors that sequence exactly.

---

## Preamble

This document is the authoritative architectural and constitutional specification for ADAAD v3.0.0. It extends v2.0.0 governance with the complete Phase 5 constitutional model for Multi-Repo Federation: the new dual-gate invariant, cross-repo mutation lifecycle, `FederatedSignalBroker` upgrade blueprint, `LineageLedgerV2` federation extension, federated evidence matrix, and all new failure modes.

All agents — MutationAgent, IntegrationAgent, AnalysisAgent, EvolutionAgent, and any future agent operating across any federated repository — must comply with every rule enumerated here. Rules inherited from v2.0.0 remain in force unless explicitly superseded by this document.

---

## 1. Constitutional Governance Model — Phase 5 Extensions

### 1.1 The Dual-Gate Invariant (New — Non-Negotiable)

```
INVARIANT PHASE5-GATE-0: A federated mutation MUST receive GovernanceGate approval
in BOTH the source repository AND the destination repository before any change is
applied in either repository.

Source approval alone is insufficient.
Destination approval alone is insufficient.
Concurrent approval is not required, but sequential approval is mandatory.
Approval in one gate does NOT bind the other gate.

Violation of this invariant is a constitutional fault.
Both pipelines halt immediately on detection.
The dual-gate result is recorded in both evidence ledgers.
```

**Rationale:** Single-repo ADAAD ensures one GovernanceGate controls one codebase. Federation introduces the possibility that a mutation accepted in repo A could propagate damage to repo B whose constitution was never consulted. The dual-gate invariant closes this surface completely.

### 1.2 The Federation Authority Chain

```
SOURCE REPO                        DESTINATION REPO
──────────────────                 ──────────────────────────────
EvolutionLoop                      FederatedMutationReceiver
    │                                     │
    ▼                                     ▼
AIMutationProposer                 [Duplicate all Phase 2–4 stages]
    │                                     │
    ▼                                     ▼
GovernanceGate (Source)    →→→    GovernanceGate (Destination)
    │                                     │
    ▼                                     ▼
EvidenceLedger (Source)           EvidenceLedger (Destination)
    │                                     │
    └─────────────┬───────────────────────┘
                  ▼
         FederatedEvidenceMatrix
         (cross-repo determinism proof)
```

**Advisory boundary:** `FederatedSignalBroker` is the ONLY component permitted to carry mutation proposals between repos. It is a governed conduit — not an authority. It cannot approve, sign, or execute. It can only transport.

### 1.3 Updated Authority Table

| Component | Authority Class | Phase 5 Change |
|---|---|---|
| `GovernanceGate` | **Sole authority** — approves/rejects mutations | **Extended**: dual-gate evaluation required for federated mutations |
| `FederatedSignalBroker` | Advisory → **Governed conduit** | **Upgraded**: may transport mutation proposals; still cannot approve |
| `LineageLedgerV2` | Evidence storage | **Extended**: `federation_origin` field added |
| `FederatedMutationReceiver` | **New** — destination-side intake | New in Phase 5: receives proposals, feeds destination GovernanceGate |
| `FederatedEvidenceMatrix` | **New** — cross-repo proof bundle | New in Phase 5: dual-ledger determinism verification |
| `FederationConsensusEngine` | Coordination advisory | Unchanged: Raft-style election for leader node; advisory only |
| `AIMutationProposer` | Advisory | Unchanged: generates proposals, never approves |

### 1.4 The Sixteen Constitutional Rules (v2.0.0 + Phase 5 Additions)

Rules 1–14 are inherited from `ARCHITECT_SPEC_v2.0.0.md` without modification.

| # | Rule ID | Severity | Gate Behavior |
|---|---------|----------|---------------|
| 1–14 | *(inherited)* | *(unchanged)* | *(unchanged)* |
| 15 | `federated_dual_gate_required` | **BLOCKING** | Halt if destination gate approval absent before cross-repo apply |
| 16 | `federation_origin_declared` | **BLOCKING** | Halt if `federation_origin` field absent from any federated mutation's lineage record |

**Fail-closed rule (inherited):** Any gate producing an unrecognized result is treated as FAIL. The pipeline halts.

---

## 2. Phase 5 Mutation Lifecycle — Cross-Repo Evolution

### 2.1 Complete Federated Epoch Flow

```
SOURCE REPO EPOCH
─────────────────────────────────────────────────────────────────────
[1] STRATEGY SELECTION         — BanditSelector, FitnessLandscape
[1.5] ENTROPY PREFLIGHT        — EntropyFastGate (Phase 4)
[2] PROPOSAL GENERATION        — AIMutationProposer (Architect/Beast/Dream)
[2.5] ROUTE OPTIMIZATION       — MutationRouteOptimizer (Phase 4)
[3] POPULATION SELECTION       — PopulationManager, BLX-alpha GA
[3.5] SEMANTIC SCORING         — SemanticDiffEngine + LineageLedgerV2 proximity
[4] SOURCE GOVERNANCE GATE     — GovernanceGate.approve_mutation()
    │   PASS: mutation signed, epoch continues
    │   FAIL: halt, emit FEDERATED_SOURCE_GATE_REJECT to source ledger
    ▼
[5] FEDERATION DISPATCH        — FederatedSignalBroker.dispatch_mutation_proposal()
    │   Payload: signed mutation bundle + source epoch chain + source gate certificate
    │   Transport: federation_handshake_envelope.v1.json schema
    │   Invariant: source gate certificate MUST be present in payload
    ▼
DESTINATION REPO INTAKE
─────────────────────────────────────────────────────────────────────
[6] FEDERATED MUTATION RECEIVER — FederatedMutationReceiver.receive()
    │   Validates: federation_handshake_envelope schema
    │   Validates: source gate certificate signature against trusted key registry
    │   Validates: federation_origin field present in lineage metadata
    │   FAIL: emit FEDERATION_INTAKE_REJECT, halt, notify source
    ▼
[7] DESTINATION REPLAY PROOF   — ReplayEngine.verify_source_epoch()
    │   Replays source epoch with supplied inputs; confirms deterministic match
    │   DIVERGE: emit FEDERATION_REPLAY_DIVERGENCE, halt both pipelines
    ▼
[8] DESTINATION GOVERNANCE GATE — GovernanceGate.approve_mutation()
    │   Full evaluation (v3.0.0): rules 1–16 applied to destination codebase context
    │   PASS: mutation applied to destination repo
    │   FAIL: emit FEDERATED_DESTINATION_GATE_REJECT to destination ledger
    │          Notify source ledger via FEDERATION_DESTINATION_REJECT_ECHO
    ▼
[9] FEDERATED EVIDENCE MATRIX   — FederatedEvidenceMatrix.assemble()
    │   Collects: source ledger entry + destination ledger entry
    │   Computes: cross-repo determinism proof (SHA-256 of canonical bundle)
    │   Emits:    federated_evidence_matrix_complete event to both ledgers
    ▼
[10] CHECKPOINT ANCHOR          — CheckpointChain.append() in both repos
     Federation epoch finalized. Both chains extended. Cycle restarts.
```

### 2.2 Lifecycle Phase Definitions

#### Phase 5 — Step 5: Federation Dispatch

| Field | Value |
|---|---|
| **Purpose** | Transport signed mutation proposal from source to destination without conveying authority |
| **Inputs** | Signed mutation bundle; source epoch chain digest; source GovernanceGate certificate |
| **Checks** | Source gate certificate present; payload conforms to `federation_handshake_envelope.v1.json`; trusted key registry validates signature |
| **Pass Condition** | Envelope validated; dispatch queued to FederatedMutationReceiver |
| **Fail Condition** | Any validation failure → `FEDERATION_DISPATCH_VALIDATION_FAIL` |
| **Failure Modes** | `FEDERATION_DISPATCH_SCHEMA_VIOLATION`, `FEDERATION_DISPATCH_UNSIGNED_PAYLOAD`, `FEDERATION_DISPATCH_UNTRUSTED_KEY` |
| **Dependencies** | GovernanceGate (source), `federation_handshake_envelope.v1.json` schema, `federation_trusted_keys.json` |
| **Notes for Other Agents** | MutationAgent must never call FederatedSignalBroker dispatch directly. Only EvolutionLoop may trigger dispatch, and only after source gate PASS. |

#### Phase 5 — Step 6: Federated Mutation Receiver

| Field | Value |
|---|---|
| **Purpose** | Destination-side intake: validate inbound federated proposals before they enter destination pipeline |
| **Inputs** | `FederationHandshakeEnvelope`; source gate certificate; `federation_origin` metadata |
| **Checks** | Schema validation; source gate cert signature; `federation_origin` present; proposal not already applied (deduplication via mutation_id) |
| **Pass Condition** | All checks pass → proposal queued for destination replay proof |
| **Fail Condition** | Any check fails → `FEDERATION_INTAKE_REJECT`; source notified |
| **Failure Modes** | `FEDERATION_INTAKE_SCHEMA_INVALID`, `FEDERATION_INTAKE_CERT_UNVERIFIABLE`, `FEDERATION_INTAKE_MISSING_ORIGIN`, `FEDERATION_INTAKE_DUPLICATE_MUTATION` |
| **Dependencies** | `federation_trusted_keys.json`, `LineageLedgerV2`, `FederationProtocol` |
| **Notes for Other Agents** | IntegrationAgent: destination CI must run full test suite on the received mutation before GovernanceGate evaluation. |

#### Phase 5 — Step 7: Destination Replay Proof

| Field | Value |
|---|---|
| **Purpose** | Verify that source epoch is deterministically reproducible before trusting its outcome |
| **Inputs** | Source epoch seed; source scoring inputs; source gate inputs; claimed source gate certificate |
| **Checks** | Replay produces byte-identical gate certificate; no divergence in fitness scores > 0.001 tolerance |
| **Pass Condition** | Replay matches → proceed to destination gate |
| **Fail Condition** | Any divergence → `FEDERATION_REPLAY_DIVERGENCE`; both pipelines halt |
| **Failure Modes** | `FEDERATION_REPLAY_DIVERGENCE`, `FEDERATION_REPLAY_MISSING_SEED`, `FEDERATION_REPLAY_TIMEOUT` |
| **Dependencies** | `ReplayEngine`, `DeterministicProvider`, `GovernanceGate` |
| **Notes for Other Agents** | This is the hardest invariant to satisfy. AnalysisAgent: divergence here almost always indicates a non-deterministic dependency in the source pipeline — escalate immediately. |

#### Phase 5 — Step 8: Destination Governance Gate

| Field | Value |
|---|---|
| **Purpose** | Independent constitutional evaluation of the federated mutation against the destination codebase |
| **Inputs** | Federated mutation bundle; destination codebase AST snapshot; destination fitness state; replay proof |
| **Checks** | Versioned constitutional rule set evaluated against destination context; federation-specific rules confirmed per this spec version |
| **Pass Condition** | All BLOCKING rules pass → mutation applied to destination |
| **Fail Condition** | Any BLOCKING rule fails → `FEDERATED_DESTINATION_GATE_REJECT`; source ledger echo emitted |
| **Failure Modes** | `FEDERATED_DESTINATION_GATE_REJECT`, `FEDERATION_DESTINATION_GATE_TIMEOUT`, `FEDERATION_DESTINATION_REPLAY_PROOF_ABSENT` |
| **Dependencies** | `GovernanceGate`, destination `EvidenceLedger`, `FederatedEvidenceMatrix` |
| **Notes for Other Agents** | Source gate approval does NOT weaken or bias destination gate evaluation. Every rule is applied fresh. |

#### Phase 5 — Step 9: Federated Evidence Matrix

| Field | Value |
|---|---|
| **Purpose** | Produce a tamper-proof, cross-repo determinism proof binding both ledger entries |
| **Inputs** | Source ledger entry hash; destination ledger entry hash; epoch chain digests from both repos; gate certificates from both repos |
| **Checks** | Both ledger entry hashes confirmed before matrix assembly; canonical JSON deterministic |
| **Pass Condition** | Matrix assembled; `federated_evidence_matrix_complete` event emitted to both ledgers |
| **Fail Condition** | Missing ledger hash → `FEDERATION_EVIDENCE_MATRIX_INCOMPLETE`; both pipelines enter `EVIDENCE_HOLD` state |
| **Failure Modes** | `FEDERATION_EVIDENCE_MATRIX_INCOMPLETE`, `FEDERATION_EVIDENCE_HASH_MISMATCH`, `FEDERATION_EVIDENCE_LEDGER_WRITE_FAIL` |
| **Dependencies** | Both `EvidenceLedger` instances, `CheckpointChain` (both repos) |
| **Notes for Other Agents** | A release may not be tagged if any federated epoch has an incomplete evidence matrix. |

---

## 3. Subsystem Blueprints — Phase 5 New and Modified Components

### 3.1 FederatedSignalBroker — Upgrade from Advisory to Governed Conduit

**Current state (v2.3.0):** Read-only market signal aggregation. Cannot propose, approve, or apply mutations. `Authority invariant: FederatedSignalBroker never calls GovernanceGate.`

**Phase 5 upgrade:**

| Field | Specification |
|---|---|
| **Purpose** | Transport signed mutation proposals from source to destination pipelines; remain strictly non-approving |
| **New surface** | `dispatch_mutation_proposal(bundle: SignedMutationBundle) → DispatchReceipt` |
| **New surface** | `receive_dispatch_receipt(receipt: DispatchReceipt) → None` (source-side confirmation) |
| **Retained invariant** | `FederatedSignalBroker NEVER calls GovernanceGate` — this invariant is carried forward unchanged |
| **Retained invariant** | Market signals remain advisory; they influence fitness scoring but cannot approve mutations |
| **New invariant** | Every dispatch call emits `federation_dispatch_initiated` event to source ledger before network transport |
| **New invariant** | If transport fails, `FEDERATION_DISPATCH_TRANSPORT_FAIL` is emitted; source pipeline halts (fail-closed) |
| **Schema** | All outbound payloads validated against `federation_handshake_envelope.v1.json` before dispatch |
| **Key validation** | Outbound envelope signed with key from `governance/federation_trusted_keys.json` |
| **No new authority** | The upgrade adds transport capability only. Approval authority remains exclusively with `GovernanceGate`. |

**Retained class invariants from v2.3.0:**
- Peer readings with confidence == 0 are discarded (stale source guard)
- Cluster composite falls back to local reading when no peers are alive
- All gossip events carry SHA-256 lineage digests

### 3.2 LineageLedgerV2 — federation_origin Field Extension

**Current state (v2.3.0):** Append-only, SHA-256 hash-chained ledger. `semantic_proximity_score()` added in Phase 4.

**Phase 5 extension:**

| Field | Specification |
|---|---|
| **Purpose** | Carry cross-repo provenance for every federated mutation without breaking single-repo replay |
| **New field** | `federation_origin: Optional[FederationOrigin]` — present only for federated mutations; `None` for local mutations |
| **FederationOrigin schema** | `source_repo_id: str`, `source_epoch_id: str`, `source_gate_certificate_digest: str`, `source_ledger_entry_hash: str`, `dispatch_timestamp_utc: str` |
| **Backward compatibility** | `federation_origin: None` is the default; all existing single-repo ledger reads are unaffected |
| **Constitutional rule enforcement** | Rule 16 (`federation_origin_declared`): if a mutation arrives via federated path and `federation_origin` is `None`, the GovernanceGate BLOCKS immediately |
| **Serialization** | `federation_origin` is included in canonical JSON hash computation when present; excluded when `None` |
| **Replay invariant** | Replaying a federated entry with `federation_origin` present must produce the same hash as the original; the field is part of the deterministic state |
| **Failure mode** | `LINEAGE_FEDERATION_ORIGIN_MISSING` — emitted when federated mutation lacks origin field |

### 3.3 FederatedMutationReceiver — New Component

| Field | Specification |
|---|---|
| **Purpose** | Destination-side intake gate for inbound federated mutation proposals |
| **Location** | `runtime/governance/federation/mutation_receiver.py` |
| **Inputs** | `FederationHandshakeEnvelope` (validated against schema); source gate certificate |
| **Checks** | Schema validation; key registry signature verification; `federation_origin` present; mutation_id deduplication |
| **Outputs** | `ReceivedProposal` dataclass → feeds destination EvolutionLoop at Phase 7 |
| **Deduplication** | Maintains an in-memory (epoch-scoped) set of received `mutation_id` values; duplicate arrivals emit `FEDERATION_INTAKE_DUPLICATE_MUTATION` and are silently discarded (fail-silent on duplicate only) |
| **Authority** | None. FederatedMutationReceiver cannot approve mutations. It validates envelopes and queues proposals. |
| **Failure behavior** | Fail-closed. Any validation failure halts intake and notifies source via `FEDERATION_INTAKE_REJECT` |
| **Dependencies** | `FederationProtocol`, `federation_trusted_keys.json`, `LineageLedgerV2` |
| **Notes for Other Agents** | MutationAgent must not construct `FederationHandshakeEnvelope` objects directly. Only `FederatedSignalBroker.dispatch_mutation_proposal()` produces valid envelopes. |

### 3.4 FederatedEvidenceMatrix — New Component

| Field | Specification |
|---|---|
| **Purpose** | Produce a cryptographically bound, cross-repo proof that both GovernanceGates evaluated and decided on the same mutation |
| **Location** | `runtime/governance/federation/evidence_matrix.py` |
| **Inputs** | Source ledger entry hash; destination ledger entry hash; source epoch chain digest; destination epoch chain digest; both gate certificates |
| **Matrix structure** | `mutation_id`, `source_ledger_hash`, `destination_ledger_hash`, `source_epoch_digest`, `destination_epoch_digest`, `source_gate_cert_digest`, `destination_gate_cert_digest`, `matrix_digest` (SHA-256 of canonical JSON of all prior fields) |
| **Determinism** | Canonical JSON (sorted keys, no whitespace) used for all digests. Identical inputs → identical `matrix_digest`. |
| **Storage** | Appended to `security/ledger/federated_evidence_matrix.jsonl` (new file, append-only) |
| **Ledger echo** | `federated_evidence_matrix_complete` event emitted to both source and destination `EvidenceLedger` with `matrix_digest` |
| **Release gate** | A version may not be tagged if `federated_evidence_matrix.jsonl` contains any entry with `status: INCOMPLETE` |
| **Failure mode** | `FEDERATION_EVIDENCE_MATRIX_INCOMPLETE` — emitted when either ledger hash is absent at assembly time |
| **Replay** | `FederatedEvidenceMatrix` must be fully replayable: given identical input hashes, produces identical `matrix_digest` |

### 3.5 GovernanceGate — Phase 5 Extensions

**No new authority model.** `GovernanceGate` remains the sole approval authority. Phase 5 adds two behaviors:

| Extension | Specification |
|---|---|
| **Rule 15 evaluation** | `federated_dual_gate_required`: present in all federated mutation evaluations. Checks that `federation_origin` field is populated AND that the source gate certificate digest in `federation_origin` is present and verifiable before proceeding to other rules |
| **Destination reject echo** | When destination gate REJECTs a federated mutation, it emits `FEDERATION_DESTINATION_REJECT_ECHO` event containing the mutation_id and rejection reason. Source pipeline writes this echo to its own ledger. |
| **Replay proof requirement** | Destination gate evaluation is constitutionally blocked until Step 7 (replay proof) passes. `FEDERATION_DESTINATION_REPLAY_PROOF_ABSENT` halts evaluation if proof is missing. |

---

## 4. Security Invariants — Phase 5 Additions

The following invariants extend `SECURITY_INVARIANTS_MATRIX.md`. They are incorporated by reference and must be added to that document in PR-PHASE5-01.

### 4.1 Federation Mutation Propagation Invariants

| # | Invariant ID | Statement |
|---|---|---|
| F-01 | `no_cross_repo_approval_delegation` | Source GovernanceGate approval NEVER delegates or implies destination approval. Every gate evaluation is fully independent. |
| F-02 | `federation_transport_signed_only` | FederatedSignalBroker may only dispatch payloads signed by a key present in `governance/federation_trusted_keys.json`. Unsigned or unverifiable payloads are never dispatched. |
| F-03 | `destination_gate_context_isolation` | Destination GovernanceGate evaluates mutations against destination codebase AST, not source. Cross-contamination of scoring contexts is a constitutional fault. |
| F-04 | `federation_replay_divergence_halts_both` | A replay divergence detected at Step 7 halts BOTH source and destination pipelines. Neither may continue until the divergence is manually resolved and the incident is recorded in both ledgers. |
| F-05 | `no_retroactive_federation_evidence` | `federated_evidence_matrix.jsonl` entries may not be modified or backdated after the epoch completes. Violation is detected via hash chain verification. |
| F-06 | `federated_mutation_rate_bounded` | The rate of federated mutations accepted per destination epoch is bounded by `MAX_FEDERATED_MUTATIONS_PER_EPOCH = 3`. This prevents federated flooding attacks. |
| F-07 | `federation_origin_immutable` | Once written to `LineageLedgerV2`, the `federation_origin` field of a ledger entry is immutable. No subsequent mutation may alter it. |

### 4.2 Phase 5 Failure Mode Registry

All failure modes are deterministic, named, non-silent, and emitted to the evidence ledger.

| Failure Mode ID | Trigger | Both Pipelines Halt? |
|---|---|---|
| `FEDERATED_SOURCE_GATE_REJECT` | Source GovernanceGate REJECTs federated proposal | Source halts; destination not notified |
| `FEDERATION_DISPATCH_SCHEMA_VIOLATION` | Outbound envelope fails schema validation | Source halts |
| `FEDERATION_DISPATCH_UNSIGNED_PAYLOAD` | Payload missing or unverifiable signature | Source halts |
| `FEDERATION_DISPATCH_UNTRUSTED_KEY` | Signing key absent from trusted key registry | Source halts |
| `FEDERATION_DISPATCH_TRANSPORT_FAIL` | Network/transport error during dispatch | Source halts |
| `FEDERATION_INTAKE_SCHEMA_INVALID` | Inbound envelope fails schema validation at destination | Destination halts; source notified |
| `FEDERATION_INTAKE_CERT_UNVERIFIABLE` | Source gate cert signature unverifiable | Destination halts; source notified |
| `FEDERATION_INTAKE_MISSING_ORIGIN` | `federation_origin` absent from lineage metadata | Destination halts; source notified |
| `FEDERATION_INTAKE_DUPLICATE_MUTATION` | `mutation_id` already processed this epoch | Destination discards silently; no halt |
| `FEDERATION_REPLAY_DIVERGENCE` | Step 7 replay produces non-matching result | **Both pipelines halt** |
| `FEDERATION_REPLAY_MISSING_SEED` | Source epoch seed absent from payload | Destination halts |
| `FEDERATION_REPLAY_TIMEOUT` | Replay proof computation exceeds 45s | Destination halts |
| `FEDERATED_DESTINATION_GATE_REJECT` | Destination GovernanceGate REJECTs mutation | Destination halts; source echo emitted |
| `FEDERATION_DESTINATION_REPLAY_PROOF_ABSENT` | Step 8 attempted before Step 7 passed | Destination halts |
| `FEDERATION_DESTINATION_GATE_TIMEOUT` | Destination gate evaluation exceeds 45s | Destination halts |
| `FEDERATION_EVIDENCE_MATRIX_INCOMPLETE` | Either ledger hash absent at matrix assembly | Both pipelines enter EVIDENCE_HOLD |
| `FEDERATION_EVIDENCE_HASH_MISMATCH` | Recomputed matrix_digest differs from stored | Both pipelines halt |
| `FEDERATION_EVIDENCE_LEDGER_WRITE_FAIL` | Append to federated_evidence_matrix.jsonl fails | Both pipelines halt |
| `LINEAGE_FEDERATION_ORIGIN_MISSING` | Federated mutation lacks `federation_origin` in LineageLedgerV2 | GovernanceGate blocks (Rule 16) |

---

## 5. Phase 5 PR Sequence

The following PRs are the canonical, ordered delivery sequence for Phase 5 under the **3-PR merged-scope model**. No PR may merge without evidence from the prior PR entry.

| PR ID | Milestone flag | CI tier | Blocked by |
|---|---|---|---|
| PR-PHASE5-01 | phase-5 / v3.0.0 | critical | v2.2.0 tag |
| PR-PHASE5-02 | phase-5 / v3.0.0 | critical | PR-PHASE5-01 merged |
| PR-PHASE5-03 | phase-5 / v3.0.0-release-gate | critical | PR-PHASE5-02 merged |

### PR-PHASE5-01: Federation Mutation Propagation

| Field | Value |
|---|---|
| **Purpose** | Upgrade federated propagation from signal ingestion to governed mutation propagation with dual decision references |
| **Files modified** | `runtime/market/federated_signal_broker.py`, `runtime/governance/federation/peer_discovery.py`, ledger schema/event contracts |
| **Acceptance gates** | (1) Dual approval required before commit (`federated_mutation_dual_approval`) (2) `federated_mutation_accepted.v1` includes both decision IDs (3) Federation transport + governance suites pass without regressions |
| **Constitutional gate** | Tier 1 + Tier 2 (critical, federation path) |
| **Blocked by** | v2.2.0 tagged |

### PR-PHASE5-02: Cross-Repo Lineage

| Field | Value |
|---|---|
| **Purpose** | Extend `LineageLedgerV2` with `federation_origin` and preserve deterministic replay/hash behavior |
| **Files modified** | `runtime/evolution/lineage_v2.py`, `security/ledger/lineage_v2.py`, lineage endpoint + tests |
| **Acceptance gates** | (1) Deterministic serialization/hash for `federation_origin=None` and populated values (2) Existing lineage integrity tests pass unchanged (3) Governance blocks missing federation origin metadata |
| **Constitutional gate** | Tier 1 + Tier 2 (critical, lineage/replay path) |
| **Blocked by** | PR-PHASE5-01 merged |

### PR-PHASE5-03: Federated Evidence Matrix + v3.0.0 Gate

| Field | Value |
|---|---|
| **Purpose** | Finalize federated evidence/release gate and complete v3.0.0 milestone controls |
| **Files modified** | `docs/comms/claims_evidence_matrix.md`, federation evidence/replay wiring, CI workflows, constitution rule updates |
| **Merged scope note** | Includes scope previously split as `PR-PHASE5-04` (broker replay-proof hardening) and `PR-PHASE5-05` (federated evidence matrix + full E2E CI) |
| **Acceptance gates** | (1) `federated-determinism` CI job passes with zero matrix digest divergences (2) `validate_release_evidence.py --require-complete` passes (3) v3.0.0 release gate blocks until federated evidence completeness + dual-approval invariants are satisfied |
| **Constitutional gate** | Tier 1 + Tier 2 + Tier 3 (milestone release gate) |
| **Blocked by** | PR-PHASE5-02 merged |

### Phase 5 sequence changelog note

- **2026-03-06:** Sequence normalized from historical 5-PR decomposition to canonical 3-PR merged-scope model. Scope formerly documented as `PR-PHASE5-04` and `PR-PHASE5-05` is now folded into `PR-PHASE5-03` to remove spec/procession drift and concentrate v3.0.0 acceptance gating.

---

## 6. Determinism Contract — Phase 5 Extensions

The `DETERMINISM_CONTRACT_SPEC.md` is extended by the following invariants, to be added in PR-PHASE5-01:

| Invariant ID | Statement |
|---|---|
| `DC-P5-01` | `FederatedEvidenceMatrix.assemble()` produces identical `matrix_digest` for identical input hashes on any machine, any clock |
| `DC-P5-02` | `LineageLedgerV2` hash computation is identical whether `federation_origin` is `None` or populated, provided the same canonical JSON rules apply |
| `DC-P5-03` | `GovernanceGate` Rule 15 and Rule 16 evaluation produces identical PASS/FAIL for identical mutation payloads regardless of evaluation order or wall-clock time |
| `DC-P5-04` | Source epoch replay (Step 7) must be byte-identical to original evaluation; any tolerance > 0 in fitness scores constitutes a divergence |
| `DC-P5-05` | `FederationHandshakeEnvelope` canonical JSON is stable: identical logical inputs always serialize to identical bytes |

---

## 7. Measurement Targets — Phase 5

| Metric | Target | Enforcement |
|---|---|---|
| Cross-repo epoch duration (Steps 5–10) | < 90 seconds end-to-end | `federated-epoch-determinism` CI job |
| Federation replay divergence rate | 0 divergences per 100 federated epochs | `DC-P5-04` |
| `federated_evidence_matrix.jsonl` INCOMPLETE entries at release | 0 | Release gate in `governance_strict_release_gate.yml` |
| Dual-gate acceptance rate | Source: 20–60%; Destination: ≥ source rate (destination may reject more) | `EpochTelemetry` |
| `FEDERATION_EVIDENCE_HASH_MISMATCH` events | 0 in production | Alert runbook |
| `federation_origin` missing on federated mutations | 0 | Rule 16 enforcement |

---

## 8. Backward Compatibility Guarantees

The following guarantees apply to all consumers of ADAAD v2.x who upgrade to v3.0.0:

1. **Single-repo pipelines are unaffected.** All v2.3.0 behavior is preserved. Federation is opt-in via `FederatedSignalBroker.dispatch_mutation_proposal()`. A pipeline that never calls this method operates identically to v2.3.0.
2. **`LineageLedgerV2` single-repo entries hash identically to v2.3.0 entries.** `federation_origin=None` is excluded from hash computation.
3. **For v3.0.0, GovernanceGate rules 1–14 are evaluated identically.** Rules 15 and 16 are only evaluated when a federated mutation is detected (i.e., `federation_origin` is non-None in the proposal metadata).
4. **All existing MCP tools, `EpochTelemetry`, and `BanditSelector` interfaces are unchanged.**
5. **`CheckpointChain` is extended, not replaced.** Existing checkpoint files remain valid.

---

## 9. What Phase 5 Will Not Build

Constitutional clarity requires explicit exclusions:

- **No cross-repo GovernanceGate fusion.** Source and destination gates are permanently independent. A shared "federation gate" that approves for both repos is constitutionally prohibited.
- **No implicit propagation.** A mutation accepted in the source repo is never automatically queued for any destination repo. Every dispatch is an explicit, audited action.
- **No federated approval delegation.** A node cannot grant another node the right to approve on its behalf.
- **No unauthenticated federation.** There is no "trust all" mode. `federation_trusted_keys.json` is always consulted.
- **No retroactive evidence.** `federated_evidence_matrix.jsonl` cannot be amended after epoch close.

---

## 10. Governance Sign-Off Record

| Field | Value |
|---|---|
| **Issuing agent** | ArchitectAgent |
| **Specification version** | v3.0.0 |
| **Issued date** | 2026-03-06 |
| **Supersedes** | `ARCHITECT_SPEC_v2.0.0.md` |
| **Status** | CANONICAL — effective immediately |
| **Next spec version** | v3.1.0 (Phase 6 — Autonomous Roadmap Self-Amendment) |
| **Human sign-off required before Phase 5 PRs begin** | Yes — PR-PHASE5-01 must be reviewed by a maintainer before any implementation PR is opened |

---

*No agent may override, defer, or selectively apply the rules in this specification. Constitutional faults halt the pipeline. The specification is the law.*
