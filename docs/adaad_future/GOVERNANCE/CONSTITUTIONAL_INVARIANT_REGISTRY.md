# Constitutional Invariant Registry

**Status:** Canonical — updated through v9.32.0 (Phase 99)  
**Current Hard-class count:** 46  
**Target at v9.48.0:** 80+  
**Authority:** HUMAN-0 — Dustin L. Reid

---

## Hard-Class Invariant Index

A Hard-class invariant is an unconditional constraint. Violation raises an exception that aborts the current operation. No bypass path exists except explicit HUMAN-0 authorization with ledgered evidence.

### Format

```
INVARIANT-ID    Module      Class    Phase   Description
```

---

## Category I — Constitutional Evolution Loop (CEL)

| ID | Module | Phase | Description |
|---|---|---|---|
| `CEL-ORDER-0` | constitutional_evolution_loop | 64 | Steps execute in defined order only |
| `CEL-EVIDENCE-0` | constitutional_evolution_loop | 64 | Epoch hash chain required before evidence accepted |
| `CEL-BLOCK-0` | constitutional_evolution_loop | 64 | Blocked mutations halt epoch immediately |
| `CEL-DRYRUN-0` | constitutional_evolution_loop | 64 | Dry-run mode restricted to sandbox execution |
| `CEL-REPLAY-0` | constitutional_evolution_loop | 64 | No datetime.now() calls during replay |
| `CEL-GATE-0` | constitutional_evolution_loop | 64 | GovernanceGate v2 is sole promotion authority |

## Category II — AST Mutation Substrate

| ID | Module | Phase | Description |
|---|---|---|---|
| `AST-SAFE-0` | governance_gate_v2 | 63 | No dynamic execution (exec/eval/__import__) |
| `AST-IMPORT-0` | governance_gate_v2 | 63 | Import boundary violations block mutation |
| `AST-COMPLEX-0` | governance_gate_v2 | 63 | Cyclomatic complexity ceiling enforced |
| `SEMANTIC-INT-0` | governance_gate_v2 | 63 | Semantic integrity score must exceed floor |

## Category III — Exception/Governance Tokens

| ID | Module | Phase | Description |
|---|---|---|---|
| `EXCEP-SCOPE-0` | governance_gate_v2 | 63 | Exception token scope validated before use |
| `EXCEP-HUMAN-0` | governance_gate_v2 | 63 | HUMAN-0 signature required for Hard-class exceptions |
| `EXCEP-TTL-0` | governance_gate_v2 | 63 | Exception tokens expire after TTL epochs |
| `EXCEP-REVOKE-0` | governance_gate_v2 | 63 | Revoked tokens are permanently blocked |

## Category IV — Fitness Engine

| ID | Module | Phase | Description |
|---|---|---|---|
| `FIT-BOUND-0` | fitness_engine_v2 | 62 | Fitness score bounded [0.0, 1.0] always |
| `FIT-DET-0` | fitness_engine_v2 | 62 | Identical inputs produce identical fitness scores |
| `FIT-DIV-0` | fitness_engine_v2 | 62 | Diversity contribution cannot be negative |
| `FIT-ARCH-0` | fitness_engine_v2 | 62 | Architectural score included in every evaluation |

## Category V — Lineage and Replay

| ID | Module | Phase | Description |
|---|---|---|---|
| `LINEAGE-CACHE-0` | lineage_engine | 61 | Verify-integrity cache invalidation on append |
| `REPLAY-0` | replay_attestation | 77 | Identical inputs produce identical replay outputs |

## Category VI — Cross-Epoch Dream State

| ID | Module | Phase | Description |
|---|---|---|---|
| `DSTE-0` | dream_state | 96 | Dream ledger committed before candidates returned |
| `DSTE-1` | dream_state | 96 | Deterministic seeded RNG from epoch_id + seed |
| `DSTE-2` | dream_state | 96 | Novelty filter applied before ceiling cap |
| `DSTE-3` | dream_state | 96 | Quorum gate (≥3 source epochs) before dream fires |
| `DSTE-4` | dream_state | 96 | DreamCandidate genesis_digest deterministic |
| `DSTE-5` | dream_state | 96 | DreamStateReport structurally cannot be APPROVED |
| `DSTE-6` | dream_state | 96 | Post-execution ceiling cap enforced |

## Category VII — Morphogenetic Memory

| ID | Module | Phase | Description |
|---|---|---|---|
| `MMEM-0` | morphogenetic_memory | 94 | Memory enrichment persists before return |
| `MMEM-CHAIN-0` | morphogenetic_memory | 94 | Memory chain hash verified on every read |
| `MMEM-READONLY-0` | morphogenetic_memory | 94 | Memory snapshots immutable after creation |
| `MMEM-WIRE-0` | morphogenetic_memory | 94 | Evolution loop must wire memory enrichment |
| `MMEM-LEDGER-0` | morphogenetic_memory | 94 | Ledger persists before enrichment returns |
| `MMEM-DETERM-0` | morphogenetic_memory | 94 | Memory digest deterministic from contents |

## Category VIII — Mutation Genealogy Visualization

| ID | Module | Phase | Description |
|---|---|---|---|
| `MGV-0` | mutation_genealogy | 97 | Genealogy analyzer fail-open on corrupt lines |
| `MGV-DETERM-0` | mutation_genealogy | 97 | PropertyInheritanceVector digest is deterministic |
| `MGV-PERSIST-0` | mutation_genealogy | 97 | Genealogy records append-only via Path.open |

## Category IX — Constitutional Jury System

| ID | Module | Phase | Description |
|---|---|---|---|
| `CJS-0` | constitutional_jury | 99 | ConstitutionalJury.deliberate() sole evaluation authority for high-stakes paths |
| `CJS-QUORUM-0` | constitutional_jury | 99 | jury_size < JURY_SIZE raises ConfigError at construction |
| `CJS-DETERM-0` | constitutional_jury | 99 | JuryDecision.decision_digest is sha256(mutation_id:verdict:approve_count:jury_size) |
| `CJS-DISSENT-0` | constitutional_jury | 99 | Dissenting verdicts ledgered before majority verdict returned |
| `CJS-PERSIST-0` | constitutional_jury | 99 | _persist() and _record_dissent() use Path.open append-only |

---

## Planned Hard-Class Invariants (Phases 100–115)

| Phase | Innovation | Planned Invariants | Count |
|---|---|---|---|
| 100 | ARS — Agent Reputation Staking | `STAKE-0`, `STAKE-DETERM-0`, `STAKE-HUMAN-0`, `STAKE-BURN-0` | 4 |
| 101 | ERS — Emergent Role Specialization | `ROLE-0`, `ROLE-DETERM-0`, `ROLE-PERSIST-0` | 3 |
| 102 | APM — Agent Post-Mortem | `APM-0`, `APM-DETERM-0`, `APM-AUDIT-0` | 3 |
| 103 | TGW — Temporal Governance Windows | `TGW-0`, `TGW-DETERM-0`, `TGW-LOG-0` | 3 |
| 104 | GAM — Governance Archaeology | `GAM-0`, `GAM-DETERM-0`, `GAM-COMPLETE-0` | 3 |
| 105 | CST — Constitutional Stress Testing | `CST-0`, `CST-DETERM-0`, `CST-GAP-0` | 3 |
| 106 | GDB — Governance Bankruptcy | `BANK-0`, `BANK-HUMAN-0`, `BANK-DETERM-0` | 3 |
| 107 | MCF — Market-Conditioned Fitness | `MCF-0`, `MCF-DETERM-0`, `MCF-AUDIT-0` | 3 |
| 108 | RCL — Regulatory Compliance | `RCL-0`, `RCL-DETERM-0`, `RCL-HUMAN-0` | 3 |
| 109 | SVP — Semantic Version Promises | `SVP-0`, `SVP-DETERM-0`, `SVP-AUDIT-0` | 3 |
| 110 | HAF — Hardware-Adaptive Fitness | `HAF-0`, `HAF-DETERM-0`, `HAF-BOUND-0` | 3 |
| 111 | CEB — Entropy Budget | `CEB-0`, `CEB-DETERM-0`, `CEB-COOL-0` | 3 |
| 112 | MBR — Blast Radius Modeling | `MBR-0`, `MBR-DETERM-0`, `MBR-SLA-0` | 3 |
| 113 | SAI — Self-Awareness Invariant | `SELF-AWARE-0`, `SAI-DETERM-0`, `SAI-AUDIT-0` | 3 |
| 114 | CDE — Curiosity-Driven Exploration | `CDE-0`, `CDE-HARD-STOP-0`, `CDE-DETERM-0` | 3 |
| 115 | TMT — The Mirror Test | `MIRROR-0`, `MIRROR-DETERM-0`, `MIRROR-CALIBRATE-0` | 3 |

**Planned additional count:** 49  
**Projected total at v9.48.0:** 46 + 49 = **95 Hard-class invariants**

---

## Invariant Naming Convention

```
<MODULE_ABBR>[-<KEYWORD>]-<N>

Examples:
  CJS-0           — first invariant of Constitutional Jury System
  DSTE-QUORUM-0   — quorum constraint in Dream State Engine
  MMEM-CHAIN-0    — chain constraint in Morphogenetic Memory
  SELF-AWARE-0    — top-level Self-Awareness Invariant
```

Rules:
1. All-caps module abbreviation prefix
2. Optional semantic keyword
3. Zero-indexed counter
4. First invariant in any module is always `-0` (the master invariant)
5. The `-0` invariant is the architectural invariant for that module — the one constraint that defines the module's purpose

---

## Invariant Lifecycle

```
DRAFT → ADVISORY → WARNING → HARD-CLASS → [RETIRED]
```

| Stage | Enforcement | Demotion trigger | Promotion trigger |
|---|---|---|---|
| `draft` | None — observation only | — | 10+ epochs observing |
| `advisory` | Logged, not blocking | False positive rate > 20% | Precision ≥ 0.85 for 20 epochs |
| `warning` | Logged prominently | False positive rate > 10% | Precision ≥ 0.95 for 50 epochs |
| `hard-class` | Blocking — exception raised | Never (requires governance amendment) | Final state |
| `retired` | Inactive | — | Re-promotion requires HUMAN-0 |

---

*Registry last updated: v9.32.0 · Phase 99 · 2026-04-01*  
*All 46 current invariants verified in test suite: tests/test_innovations30.py + runtime tests*
