# ADAAD PR Procession Plan — 2026-03

> [!IMPORTANT]
> **Canonical source (PR sequence control):** This document is the controlling source for Phase 5 PR IDs, dependency order, milestone/CI tier flags, and per-PR acceptance gates. `docs/governance/ARCHITECT_SPEC_v3.0.0.md` must mirror this section exactly.

**Authority chain:** `CONSTITUTION.md > ARCHITECTURE_CONTRACT.md > ROADMAP.md > this document`  
**Baseline branch:** `feat/adaad-v066-core-optimizations` (3 commits ahead of `main`)  
**Baseline state:** Phase 3 shipped (v2.1.0) · Phase 4 PR-PHASE4-01 merged · v0.66 branch ready  
**Authored:** 2026-03-06

---

## Execution Sequence

```
PR-v0.66          →  PR-PHASE4-02  →  PR-PHASE4-03  →  PR-PHASE4-04
                  →  PR-PHASE4-05  →  PR-PHASE4-06  →  v2.2.0 tag
                  →  PR-PHASE5-01  →  PR-PHASE5-02  →  PR-PHASE5-03
                  →  v3.0.0 tag   →  PR-PHASE6-01
```

Dependencies are serial within each phase; phases are serial end-to-end.

---

## Tier 0 — Immediate (branch ready, open now)

### PR-v0.66 · Fast-Path Primitives + Aponi Intelligence Panels

| Field | Value |
|---|---|
| Branch | `feat/adaad-v066-core-optimizations` |
| Base | `main` |
| CI tier | `critical` |
| Risk | LOW — zero changes to existing governance/ledger paths |
| Blocks | PR-PHASE4-03, PR-PHASE4-04, PR-PHASE4-05, PR-PHASE4-06 |

**Scope:**
- 5 new runtime modules: `MutationRouteOptimizer`, `EntropyFastGate`, `CheckpointChain`, `FastPathScorer`, `ParallelGovernanceGate`
- 6 new REST endpoints in `server.py`
- 2 self-mounting Aponi UI panels: `fast_path_panel.js`, `parallel_gate_panel.js`
- 1 CI job: `fast-path-innovations`
- 163 tests, 4,824 insertions, 17 files

**Status:** Branch pushed. User opens PR at:
`https://github.com/InnovativeAI-adaad/ADAAD/compare/main...feat/adaad-v066-core-optimizations`

---

## Tier 1 — Phase 4 Completion (v2.2.0)

Phase 4 target: replace heuristic scoring with AST-aware semantic analysis and wire all v0.66 fast-path modules into the live evolution pipeline.

`SemanticDiffEngine` exists at `runtime/evolution/semantic_diff.py` (PR-PHASE4-01, merged) but is **not yet wired** into `EvolutionLoop`, `MutationFitnessEvaluator`, or `GovernanceGate`. All v0.66 modules are **API-exposed only** — not yet called from the pipeline. This tier closes both gaps.

---

### PR-PHASE4-02 · Wire SemanticDiffEngine into Scoring Pipeline

| Field | Value |
|---|---|
| Branch | `feat/phase4-semantic-scoring` |
| CI tier | `critical` |
| Depends on | PR-v0.66 merged |
| Blocks | PR-PHASE4-03 |

**Scope:**
- `runtime/evolution/scoring_algorithm.py` — replace regex heuristics with `SemanticDiffEngine.score_diff()` for `risk_score` and `complexity_score`
  - New formula: `risk = (ast_depth_delta × 0.3) + (cyclomatic_delta × 0.4) + (import_surface_delta × 0.3)`
  - Old formula: retired, hash-pinned in `scoring_algorithm_version` field for replay continuity
- `runtime/evolution/mutation_fitness_evaluator.py` — call `enrich_code_diff_with_semantic()` on every `MutationCandidate` before scoring
- `runtime/evolution/evolution_loop.py` — pass `python_content` through to evaluator for semantic enrichment
- Backward compat: `SemanticDiffEngine` falls back to `0.5/0.5` on `None` or `SyntaxError` — no scoring regression on incomplete proposals
- Algorithm version bumped: `semantic_diff_v1.0` baked into scoring payload for replay verification

**Acceptance criteria:**
- `scoring_algorithm_version: "semantic_diff_v1.0"` in all scored payloads
- Identical AST inputs → identical scores across two independent runs (determinism CI job gates this in PR-PHASE4-06)
- All existing scoring tests continue to pass

---

### PR-PHASE4-03 · MutationRouteOptimizer — Pipeline Pre-Scoring Gate

| Field | Value |
|---|---|
| Branch | `feat/phase4-route-gate` |
| CI tier | `critical` |
| Depends on | PR-v0.66 merged |
| Blocks | PR-PHASE4-06 |

**Scope:**
- `runtime/evolution/evolution_loop.py` — insert `MutationRouteOptimizer.route()` call at **Phase 2.5** (after seed, before evolve)
  - `TRIVIAL` tier: skip `evolve_generation()` deep scoring, use `FastPathScorer` directly — estimated 60–80% pipeline time reduction for low-complexity mutations
  - `STANDARD` tier: full pipeline (no change)
  - `ELEVATED` tier: full pipeline + flag for human-review annotation in `EpochResult`
- `EpochResult` extended: `elevated_mutation_ids: list[str]`, `trivial_fast_pathed: int`
- Route decisions appended to ledger via `journal.append_tx("mutation_route_decision", payload)` — auditable
- `MutationCandidate` gains `route_tier: str` field (set at routing time, passed through to scoring)

**Acceptance criteria:**
- TRIVIAL mutations produce structurally identical `MutationScore` to full pipeline (via `FastPathScorer`)
- Route decision digest present in every scored payload
- `EpochResult.trivial_fast_pathed` increments correctly in simulation mode

---

### PR-PHASE4-04 · EntropyFastGate — Pre-Proposal Entropy Preflight

| Field | Value |
|---|---|
| Branch | `feat/phase4-entropy-preflight` |
| CI tier | `critical` |
| Depends on | PR-v0.66 merged |
| Blocks | PR-PHASE4-06 |

**Scope:**
- `runtime/evolution/evolution_loop.py` — insert `EntropyFastGate.evaluate()` call at **Phase 1.5** (after proposals collected, before population seed)
  - `DENY` verdict: proposal quarantined, `journal.append_tx("entropy_gate_quarantine", ...)` emitted, proposal excluded from `all_proposals`
  - `WARN` verdict: proposal flagged, proceeds with `entropy_flagged: True` in candidate metadata
  - `ALLOW` verdict: no action
- Entropy estimation: derive `estimated_bits` from `len(proposal.python_content)` hash variance + nondeterministic source scan (grep for `random`, `uuid`, `time.time` in proposal content)
- `EpochResult` extended: `entropy_quarantined: int`, `entropy_warned: int`
- Strict mode on by default for `PRODUCTION` tier; permissive for `SANDBOX`

**Acceptance criteria:**
- Proposals containing `import random` without governance annotation → `WARN` or `DENY` (per mode)
- Zero entropy-flagged proposals reach `GovernanceGate` in strict mode
- Quarantine events appear in ledger journal

---

### PR-PHASE4-05 · CheckpointChain — Epoch Transition Anchoring

| Field | Value |
|---|---|
| Branch | `feat/phase4-checkpoint-anchor` |
| CI tier | `standard` |
| Depends on | PR-v0.66 merged |

**Scope:**
- `runtime/evolution/evolution_loop.py` — at end of `run_epoch()`, append `EpochResult` digest to the running `CheckpointChain`
  - Chain state persisted to `data/checkpoint_chain.jsonl` (append-only)
  - `EpochResult` extended: `checkpoint_digest: str` — the `chain_digest` of the new link
- `runtime/evolution/checkpoint_chain.py` — add `load_chain()` / `append_epoch()` helpers for persistent chain I/O
- Boot-time chain verification: at `EvolutionLoop.__init__`, load and verify the existing chain; halt if integrity fails (fail-closed)
- Chain integrity check exposed via `/api/fast-path/checkpoint-chain/verify` already (PR-v0.66) — now backed by real epoch data

**Acceptance criteria:**
- `checkpoint_digest` present in every `EpochResult`
- `verify_checkpoint_chain(load_chain())` passes after N sequential epochs
- Any manual edit to `checkpoint_chain.jsonl` → boot-time halt

---

### PR-PHASE4-06 · ParallelGovernanceGate — Concurrent Axis Evaluation

| Field | Value |
|---|---|
| Branch | `feat/phase4-parallel-gate-wire` |
| CI tier | `critical` |
| Depends on | PR-v0.66 merged, PR-PHASE4-02 merged |
| Blocks | v2.2.0 tag |

**Scope:**
- `runtime/governance/gate.py` — `GovernanceGate.approve_mutation()` gains a `parallel: bool = False` option
  - When `parallel=True`: delegate to `ParallelGovernanceGate.approve_mutation_parallel()` with the same axis specs
  - Default remains serial for backward compatibility; `PRODUCTION` tier enables parallel by constitution amendment (advisory rule `parallel_gate_eligible`)
- Build axis spec list from existing `GovernanceGate` rule set — each rule maps to a `ParallelAxisSpec` probe
- `GateDecision.gate_mode: str` field added (`"serial"` | `"parallel"`) for replay evidence
- Constitution v0.4.0: adds `parallel_gate_eligible` advisory rule

**Acceptance criteria:**
- Serial and parallel gate produce identical `decision_id` for identical inputs (determinism proof)
- All existing governance gate tests pass unchanged
- `gate_mode` present in every ledger `governance_gate_decision.v1` event

---

### PR-PHASE4-07 · Lineage Confidence Scoring + Determinism CI Job

| Field | Value |
|---|---|
| Branch | `feat/phase4-lineage-confidence` |
| CI tier | `critical` |
| Depends on | PR-PHASE4-02 merged |
| Blocks | v2.2.0 tag |

**Scope (lineage confidence):**
- `runtime/evolution/lineage_v2.py` — `LineageLedgerV2.semantic_proximity_score(mutation_id, candidate_content)` — computes cosine similarity between `SemanticDiffEngine` AST metrics of a candidate and the rolling mean of the last N accepted mutations
  - Returns `proximity_bonus: float ∈ [0, 0.15]` for mutations close to accepted ancestors
  - Returns `exploration_bonus: float ∈ [0, 0.10]` for semantically novel mutations (low similarity)
- `runtime/evolution/scoring_algorithm.py` — apply lineage bonus to final fitness score: `fitness = base_fitness + proximity_bonus + exploration_bonus`
- `EpochResult` extended: `mean_lineage_proximity: float`

**Scope (determinism CI job):**
- `.github/workflows/ci.yml` — new job `semantic-diff-determinism`
  - Runs two independent invocations of `SemanticDiffEngine.score_diff()` on 10 fixed AST fixtures
  - Asserts digest equality across both runs
  - Fails the gate if any score diverges
  - Added to `ci-gating-summary` needs list

**Acceptance criteria:**
- `proximity_bonus` and `exploration_bonus` present in scoring payload
- `semantic-diff-determinism` CI job green on every push
- CHANGELOG entry for Phase 4 GA

---

### v2.2.0 Release Tag Gate

Required before tagging `v2.2.0`:
1. PR-PHASE4-02 through PR-PHASE4-07 merged and CI green
2. `CHANGELOG.md` Phase 4 section complete with all evidence links
3. `ROADMAP.md` Phase 4 status updated to `✅ shipped`
4. `docs/comms/claims_evidence_matrix.md` Phase 4 row complete
5. Governance + Runtime sign-off

---

## Tier 2 — Phase 5: Multi-Repo Federation (v3.0.0)

### Canonical Phase 5 sequence model

**Policy decision:** Phase 5 uses the **3-PR merged-scope model**. The previous 5-PR split is retired.

| PR ID | Milestone flag | CI tier | Depends on |
|---|---|---|---|
| PR-PHASE5-01 | Phase 5 / v3.0.0 | critical | v2.2.0 tagged |
| PR-PHASE5-02 | Phase 5 / v3.0.0 | critical | PR-PHASE5-01 merged |
| PR-PHASE5-03 | Phase 5 / v3.0.0 (milestone release gate) | critical | PR-PHASE5-02 merged |

### PR-PHASE5-01 · Federation Mutation Propagation

| Field | Value |
|---|---|
| Branch | `feat/phase5-federated-propagation` |
| CI tier | `critical` |
| Milestone flag | `phase-5` |
| Depends on | v2.2.0 tagged |

**Scope:**
- `runtime/market/federated_signal_broker.py` — extend from read-only signal ingestion to **governed mutation propagation**: accepted mutations in source repo emit `federated_mutation_proposal.v1` gossip events to alive peers
- `runtime/governance/federation/peer_discovery.py` — `PeerRegistry` gains `accept_mutation_proposal()` endpoint: validates `federation_origin` chain, routes to local `GovernanceGate` for independent approval
- Authority invariant: **both** source and destination `GovernanceGate` must independently approve before propagation commits
- New ledger event: `federated_mutation_accepted.v1` carrying dual `decision_id` references

**Acceptance gates:**
1. Source and destination approvals are both required before commit (`federated_mutation_dual_approval`).
2. `federated_mutation_accepted.v1` ledger entries include both decision IDs.
3. Federation transport/governance tests pass with no regression in existing governance suites.

---

### PR-PHASE5-02 · Cross-Repo Lineage

| Field | Value |
|---|---|
| Branch | `feat/phase5-cross-repo-lineage` |
| CI tier | `critical` |
| Milestone flag | `phase-5` |
| Depends on | PR-PHASE5-01 merged |

**Scope:**
- `runtime/evolution/lineage_v2.py` — `LineageLedgerV2` gains `federation_origin: str | None` field
- Cross-repo lineage entries carry source repo identity + epoch chain digest
- `SemanticDiffEngine` proximity scoring works across federation origin (semantic proximity is repo-agnostic)
- Federated mutations appear in `GET /api/audit/epochs/{epoch_id}/lineage` response with `federation_origin` annotation

**Acceptance gates:**
1. `LineageLedgerV2` serialization and hashing are deterministic for both `federation_origin=None` and populated origins.
2. Existing lineage integrity tests pass unchanged; federated lineage tests pass.
3. Governance blocks missing federation origin metadata by invariant.

---

### PR-PHASE5-03 · Federated Evidence Matrix + v3.0.0 Gate

| Field | Value |
|---|---|
| Branch | `feat/phase5-evidence-matrix` |
| CI tier | `critical` |
| Milestone flag | `phase-5` + `v3.0.0-release-gate` |
| Depends on | PR-PHASE5-02 merged |

**Scope:**
- `docs/comms/claims_evidence_matrix.md` — Phase 5 row with cross-repo determinism verification requirements
- CI job `federated-determinism`: verifies zero divergences in simulated two-node federation epoch
- `CONSTITUTION.md` v0.5.0: adds `federated_mutation_dual_approval` as BLOCKING rule

**Merged scope note:** This PR absorbs the previously split scopes of `PR-PHASE5-04` and `PR-PHASE5-05` (signal broker replay-proof hardening + federated evidence matrix wiring and CI).

**Acceptance gates:**
1. `federated-determinism` CI job is green with zero matrix digest divergences.
2. Evidence matrix entries are complete and deterministic (`--require-complete` passes).
3. v3.0.0 release gate is blocked unless federated evidence and dual-approval invariants are satisfied.

**Release gate for v3.0.0:** same structure as v2.2.0 plus cross-repo determinism CI green.

---

## Tier 3 — Phase 6: Autonomous Roadmap Self-Amendment (v3.1.0, Pioneering)

### PR-PHASE6-01 · Roadmap Self-Amendment Pilot

| Field | Value |
|---|---|
| Branch | `feat/phase6-roadmap-self-amendment` |
| CI tier | `critical` |
| Depends on | v3.0.0 tagged |
| Human sign-off | **REQUIRED** — non-delegatable |

**Scope:**
- `ArchitectAgent` extended: detects when Phase N+1 prerequisites are met from telemetry, proposes a `ROADMAP.md` mutation advancing the milestone
- `ROADMAP.md` mutations governed identically to all other mutations: GovernanceGate, constitutional compliance, replay proof
- `Founders-Law` amendment required: adds `roadmap_mutation_human_signoff_required` as a new blocking invariant
- **Human governance sign-off is mandatory** — the system cannot self-promote without explicit operator approval

---

## Summary Table

| PR | Phase | CI Tier | Depends On | Est. Complexity |
|---|---|---|---|---|
| PR-v0.66 | v0.66 | critical | — | **DONE, open PR** |
| PR-PHASE4-02 | 4 | critical | PR-v0.66 | Medium |
| PR-PHASE4-03 | 4 | critical | PR-v0.66 | Medium |
| PR-PHASE4-04 | 4 | critical | PR-v0.66 | Medium |
| PR-PHASE4-05 | 4 | standard | PR-v0.66 | Low |
| PR-PHASE4-06 | 4 | critical | PR-v0.66 + PR-PHASE4-02 | Medium |
| PR-PHASE4-07 | 4 | critical | PR-PHASE4-02 | Medium |
| **v2.2.0 tag** | — | — | All PHASE4 | — |
| PR-PHASE5-01 | 5 | critical | v2.2.0 | High |
| PR-PHASE5-02 | 5 | critical | PR-PHASE5-01 | Medium |
| PR-PHASE5-03 | 5 | critical | PR-PHASE5-02 | Low |
| **v3.0.0 tag** | — | — | All PHASE5 | — |
| PR-PHASE6-01 | 6 | critical | v3.0.0 | High + human gate |

---

## Governance Invariants (Applies to All PRs)

- Every PR must carry `SPDX-License-Identifier: Apache-2.0` on all new Python files
- Every scoring formula change requires `scoring_algorithm_version` bump
- No PR may remove or downgrade existing blocking constitutional rules
- Every new ledger event type requires a schema entry in `docs/governance/ledger_event_contract.md`
- All new modules must be determinism-lint clean (`tools/lint_determinism.py`)
- Human sign-off required for: v2.2.0, v3.0.0, PR-PHASE6-01

---

*This document is governed by `CONSTITUTION.md`. Amendments require ArchitectAgent approval and a CHANGELOG entry.*

---

## Changelog Notes

- **2026-03-06 — Phase 5 sequencing normalization:** Adopted the canonical **3-PR merged-scope model** for Phase 5 across governance docs. `PR-PHASE5-04` and `PR-PHASE5-05` scope moved into `PR-PHASE5-03` to remove cross-document divergence and keep a single release-gate PR for v3.0.0.

---

## Phase 6 Completion Addendum — 2026-03-07

> **Authority:** ArchitectAgent · `ARCHITECT_SPEC_v3.1.0.md`
> **Effective:** 2026-03-07 · Added to this procession document as governing extension.

### Updated Execution Sequence (Phase 6 Completion)

```
[v3.0.0 tagged — DONE]  →  [M6-01 + M6-02 shipped — DONE]
    →  PR-PHASE6-02  →  PR-PHASE6-03  →  PR-PHASE6-04  →  v3.1.0 tag
       (M6-03)           (M6-04)          (M6-05 close)
```

---

### PR-PHASE6-02 · M6-03 EvolutionLoop × RoadmapAmendmentEngine Wire

| Field | Value |
|---|---|
| Branch | `feat/phase6-m603-evolution-loop-wire` |
| CI Tier | `critical` |
| Depends on | M6-01 shipped, M6-02 shipped, v3.0.0 tagged |
| Blocks | PR-PHASE6-03 |
| Human sign-off | **REQUIRED** |

**Scope:**
- `runtime/autonomy/loop.py` — insert 6-gate prerequisite check at post-epoch-N checkpoint
- `runtime/autonomy/roadmap_amendment_engine.py` — `list_pending()` method added (storm guard)
- `EpochResult` extended: `amendment_proposed: bool`, `amendment_id: Optional[str]`
- 6 new ledger event types registered in `ledger_event_contract.md`
- `ADAAD_AMENDMENT_TRIGGER_INTERVAL` added to `docs/ENVIRONMENT_VARIABLES.md`
- `tests/autonomy/test_evolution_loop_amendment.py` — ≥10 acceptance-criteria tests

**Constitutional gates (all BLOCKING if violated):**
- `INVARIANT PHASE6-AUTH-0` (authority_level immutability)
- `INVARIANT PHASE6-STORM-0` (at most 1 pending amendment)
- `INVARIANT PHASE6-HUMAN-0` (no auto-approval path)

---

### PR-PHASE6-03 · M6-04 Federated Roadmap Propagation

| Field | Value |
|---|---|
| Branch | `feat/phase6-m604-federated-amendment` |
| CI Tier | `critical` |
| Depends on | PR-PHASE6-02 merged |
| Blocks | v3.1.0 tag |
| Human sign-off | **REQUIRED per node** |

**Scope:**
- `runtime/governance/federation/mutation_broker.py` — `propagate_amendment()` method added
- `federated_amendment_propagated` ledger event registered
- `tests/governance/federation/test_federated_amendment.py` — ≥8 tests
- All-or-nothing propagation rollback logic

**Constitutional gates (all BLOCKING if violated):**
- `INVARIANT PHASE6-FED-0` (source approval does NOT bind destination)
- `INVARIANT PHASE5-GATE-0` (dual-gate, inherited from Phase 5)
- `federation_hmac_required` constitutional rule (BLOCKING, unchanged)

---

### PR-PHASE6-04 · M6-05 Free Android Distribution — Completion Close

| Field | Value |
|---|---|
| Branch | `feat/phase6-m605-android-distribution-complete` |
| CI Tier | `standard` |
| Depends on | `android-free-release.yml` passing |
| Blocks | v3.1.0 tag |
| Human sign-off | Required (F-Droid MR submission) |

**Scope:**
- F-Droid MR submitted and URL recorded in CHANGELOG
- Track 1 (GitHub Releases): end-to-end pipeline run documented
- Track 2B (self-hosted F-Droid): `repo.xml` validation passing
- Track 3 (PWA): `standalone` display mode verified

**Constitutional gate:** `INVARIANT PHASE6-APK-0` (governance gate before every APK sign)

---

### Phase 6 Procession Summary

| PR | Milestone | CI Tier | Depends On | Human Sign-off |
|---|---|---|---|---|
| `PR-PHASE6-02` | M6-03 EvolutionLoop wire | critical | M6-01, M6-02 | **REQUIRED** |
| `PR-PHASE6-03` | M6-04 Federated propagation | critical | PR-PHASE6-02 | **REQUIRED per node** |
| `PR-PHASE6-04` | M6-05 Distribution close | standard | android CI | Required (F-Droid) |
| **v3.1.0 tag** | Phase 6 GA | — | All above | **REQUIRED** |

---

*Addendum authored by ArchitectAgent. Governed by `CONSTITUTION.md`. Effective 2026-03-07.*
