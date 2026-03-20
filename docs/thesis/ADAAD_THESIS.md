# ADAAD: Constitutionally Governed Autonomous Code Evolution

## A Technical Thesis on Architecture, Invariants, and Demonstrated Capability

**Author:** Dustin L. Reid — Governor, Innovative AI LLC  
**Version:** v9.14.0 — March 20, 2026  
**Phase:** 79 complete — Multi-Generation Lineage Graph  
**Status:** Living document — updated with each major phase

---

## Abstract

ADAAD (Autonomous Development & Adaptation Architecture) is a constitutionally governed runtime that enables a software system to propose, evaluate, sandbox, and apply mutations to its own codebase — without bypassing any layer of human oversight or cryptographic accountability.

The central thesis: **autonomous software evolution and rigorous human governance are not in tension. They are complementary requirements that reinforce each other.** ADAAD demonstrates this by making every autonomous decision traceable, every mutation replayable, and every governance gate structurally inviolable.

As of v9.14.0, ADAAD has:
- Completed 79 governed evolution phases
- Executed its first fully autonomous self-evolution (Phase 65 — March 13, 2026)
- Demonstrated SEED-LIFECYCLE-COMPLETE-0 in live execution (Phase 77 — March 20, 2026)
- Accumulated 12,441+ SHA-256 hash-chained ledger entries
- Passed 4,748+ tests across constitutional, determinism, and integration tiers
- Implemented a Multi-Generation Lineage Graph for cross-epoch ancestry tracking
- Deployed on hardware as constrained as a $200 Android phone

---

## Part I: The Problem

### 1.1 The Current State of AI-Assisted Code Evolution

Every AI coding tool in production today — regardless of vendor or capability — shares the same fundamental architecture:

```
Human intent → AI suggestion → Human review → Human apply
```

The human is in the critical path as the **sole safety layer** at every step. This is intentional and often appropriate at small scale. It fails systematically at the following inflection points:

1. **Volume**: when mutation frequency exceeds human review bandwidth, the review becomes a rubber-stamp
2. **Complexity**: when mutations interact across module boundaries too complex for single-reviewer comprehension
3. **History**: when no tamper-evident record of why a mutation was applied survives the session
4. **Accountability**: when there is no cryptographic proof that a mutation was evaluated by any criteria at all

These are not hypothetical failure modes. They are the current production reality for every AI-augmented engineering team operating at scale.

### 1.2 What Is Missing

The gap is not intelligence — current LLMs are capable of generating high-quality mutations. The gap is **governance infrastructure**: the set of structural constraints, evidence mechanisms, and constitutional invariants that make autonomous mutation safe, auditable, and reversible.

Specifically, what is missing from every existing tool:
- A tamper-evident, cryptographically hash-chained record of every mutation decision
- A constitutional gate that is structurally impossible to bypass, not merely configurable
- Deterministic replay capability for any prior mutation decision
- A fitness scoring system that evaluates mutations against the actual codebase, not just a prompt
- A sandbox isolation layer that prevents execution side-effects from reaching production state
- A human oversight surface that provides real-time visibility without requiring intervention in every decision

ADAAD provides all of these. Together, they constitute what we call **constitutionally governed autonomy**.

---

## Part II: The Architecture

### 2.1 Core Architectural Principle

ADAAD is not an AI that writes code and hopes for the best. It is a **governed runtime** that enforces constitutional constraints on every mutation before, during, and after execution.

The architecture is built on three non-negotiable properties:

1. **Ledger-first**: every decision is written to a hash-chained ledger before it executes
2. **Gate-sole**: the GovernanceGate is the only path through which a mutation can be promoted
3. **Replay-proof**: any prior epoch can be deterministically replayed from its original inputs

These are not design goals. They are constitutional invariants: `AUDIT-0`, `GOV-SOLE-0`, and `REPLAY-0`. Violating any of them is a constitutional error that halts the system.

### 2.2 The Four Architectural Layers

```
┌──────────────────────────────────────────────────────────────────────┐
│  GOVERNANCE LAYER                                                    │
│  docs/CONSTITUTION.md — 23 invariants — supreme law                 │
│  GovernanceGate · LineageLedgerV2 · HUMAN-0 · Amendment pipeline    │
├──────────────────────────────────────────────────────────────────────┤
│  EVOLUTION LAYER                                                     │
│  14-step Constitutional Evolution Loop (CEL)                        │
│  CapabilitySeed · ProposalEngine · FitnessPipeline · Sandbox        │
│  SeedLifecyclePipeline (Phases 71–77)                               │
├──────────────────────────────────────────────────────────────────────┤
│  RUNTIME LAYER                                                       │
│  Deterministic replay · SHA-256 hash chain · cgroup v2 sandbox      │
│  Ed25519/HMAC event signing · Multi-gen lineage graph               │
├──────────────────────────────────────────────────────────────────────┤
│  OPERATOR LAYER                                                      │
│  Aponi Dashboard · ADAADchat GitHub App · DEVADAAD agent            │
│  GPG-signed Tier 0 gates · Governor sign-off protocol               │
└──────────────────────────────────────────────────────────────────────┘
```

Each layer enforces its own set of invariants and cannot be bypassed by the layer above or below.

### 2.3 The Constitutional Evolution Loop

The CEL is the mutation path. It is a 14-step ordered sequence. Every step either passes with evidence or the epoch fails closed. There is no skip path, no partial completion, no emergency bypass.

```
Step 01  TARGET_DISCOVERY      CodeIntelModel identifies highest-priority gap
Step 02  CAPABILITY_MAP        CapabilityDiscovery maps the target to code paths
Step 03  PROPOSAL_GENERATE     ProposalEngine generates AST mutation candidate
Step 04  STATIC_SCAN           StaticSafetyScanner validates AST safety rules
Step 05  SANDBOX_PREFLIGHT     Preflight checks before execution
Step 06  SANDBOX_TOURNAMENT    Candidate runs in ephemeral cgroup v2 container
Step 07  FITNESS_SCORE         FitnessEngineV2 scores against 7 signals
Step 08  REPLAY_VERIFY         Deterministic replay confirms identical output
Step 09  GOVERNANCE_GATE       All 23 constitutional invariants evaluated ◄ HUMAN-0
Step 10  APPLY_MUTATION        Atomic patch applied to codebase
Step 11  POST_APPLY_VERIFY     Post-apply invariant check
Step 12  PROMOTION_DECISION    Mutation promoted or rejected
Step 13  EVIDENCE_BUNDLE       Immutable evidence artifact produced
Step 14  STATE_ADVANCE         Ledger sealed, epoch state advanced
```

`CEL-ORDER-0`: these steps execute in strict sequence. Reordering or skipping is a constitutional violation.

### 2.4 The Governance Gate

The GovernanceGate is not a feature. It is the path itself. `GOV-SOLE-0` states: the GovernanceGate is the only surface through which a mutation can be promoted. There is no alternate code path. There is no configuration that bypasses it. There is no exception handling that skips it.

Every mutation that passes the gate gets a signed, hash-chained evidence record in `LineageLedgerV2` before execution. Every mutation that fails the gate gets an equally detailed rejection record. Both are immutable.

### 2.5 The Seed Lifecycle Pipeline

Phases 71–77 implemented a complete pipeline for ADAAD to propose its own capability evolutions through a governed, human-reviewed process.

```
CapabilitySeed          A scored capability improvement proposal
      ↓
SeedPromotionQueue      SEED-PROMO-0: only expansion_score ≥ 0.85 admitted
      ↓
Human Review Gate       SEED-REVIEW-HUMAN-0: operator sign-off required
      ↓                 No system process may self-approve
ProposalRequest         SEED-PROP-DETERM-0: deterministic proposal generation
      ↓                 SEED-PROP-LEDGER-0: ledger write before return
CEL Injection           SEED-CEL-AUDIT-0: injection event ledger-recorded
      ↓
LiveWiredCEL            14-step governed epoch — all CEL invariants enforced
      ↓
SeedCELOutcomeEvent     SEED-OUTCOME-AUDIT-0: hash-linked to full chain
```

**SEED-LIFECYCLE-COMPLETE-0** — the full provenance chain from seed inception to CEL outcome is cryptographically hash-linked and deterministically replayable — was demonstrated live on March 20, 2026.

This means ADAAD can now propose, route, and evaluate its own capability improvements through a constitutional process that maintains human oversight at every gate.

---

## Part III: Constitutional Invariants

### 3.1 The 23 Rules

The ADAAD Constitution (`docs/CONSTITUTION.md`) defines 23 invariants. These are not guidelines or best practices. They are runtime-enforced constitutional rules. Any code path that violates an invariant is a constitutional error.

The invariants are organized into tiers:

**Tier 0 — Governance Integrity (inviolable)**

| Invariant | Rule |
|---|---|
| `HUMAN-0` | No Tier 0 mutation is ever applied without governor GPG sign-off |
| `AUDIT-0` | Every ledger event is SHA-256 hash-chained; retroactive modification is structurally impossible |
| `GOV-SOLE-0` | The GovernanceGate is the only promotion path — not a guardrail, the path itself |
| `REPLAY-0` | Any epoch can be deterministically replayed from its original inputs |
| `GATE-0` | GovernanceGate is sole mutation promotion authority; no bypass exists |

**Tier 1 — Evolution Integrity**

| Invariant | Rule |
|---|---|
| `CEL-ORDER-0` | 14 CEL steps execute in strict sequence; reordering or skipping is a constitutional violation |
| `CEL-EVIDENCE-0` | Every epoch produces an immutable evidence bundle before state advance |
| `MUTATION-TARGET` | Mutations target identified capability gaps, not arbitrary code paths |
| `SANDBOX-0` | All agent execution is preflight-gated in cgroup v2 isolation |
| `SANDBOX-DIV-0` | Sandbox divergence halts the epoch; no partial execution advances |

**Tier 2 — Seed Lifecycle Integrity**

| Invariant | Rule |
|---|---|
| `SEED-PROMO-0` | Only seeds with expansion_score ≥ 0.85 may enter the promotion queue |
| `SEED-REVIEW-HUMAN-0` | No system process may self-approve a seed; operator_id is required |
| `SEED-LIFECYCLE-COMPLETE-0` | End-to-end seed epoch produces outcome linked to full upstream chain |
| `SEED-OUTCOME-AUDIT-0` | SeedCELOutcomeEvent written to ledger before bus emission |
| `SEED-CEL-AUDIT-0` | CEL injection event recorded before context is returned |

**Tier 3 — Signing and Lineage Integrity**

| Invariant | Rule |
|---|---|
| `EVENT-SIGN-ABSTRACT-0` | EventSigner and EventVerifier are abstract; direct instantiation is a runtime error |
| `LEDGER-SIGN-0` | Production ledger events carry a SignatureBundle from the active EventSigner |
| `MULTIGEN-0` | Every lineage graph node is anchored to a verified ledger entry |
| `MULTIGEN-DETERM-0` | Identical ledger contents produce identical graph_digest |
| `MULTIGEN-REPLAY-0` | The lineage graph is fully reconstructable from the ledger alone |
| `WEBHOOK-SHIM-DELEG-0` | The webhook handler shim delegates 100% to app.github_app |
| `DOC-SYNC-VERSION-0` | README version markers always match the VERSION file |
| `JOURNAL-CACHE-0` | Journal warm-cache advances atomically post-append |

### 3.2 Why Invariants Instead of Policies

Policies can be changed. Invariants are constitutional. The distinction matters enormously in practice.

A policy-based system: "Thou shalt not bypass the governance gate — unless the deployment is urgent, the engineer has approval, or the configuration flag is set."

An invariant-based system: there is no code path that bypasses the governance gate. The configuration flag does not exist. The approval mechanism does not exist. The bypass is structurally absent.

ADAAD uses invariants because the failure modes of policy-based safety are too dangerous in autonomous systems. Policies require vigilance to maintain. Invariants require violation to break.

---

## Part IV: Proven Capabilities

### 4.1 First Autonomous Self-Evolution — Phase 65 (March 13, 2026)

**What happened:** ADAAD identified its own highest-priority capability gap, generated a mutation proposal via ProposalEngine, ran it through a sandboxed tournament, scored it against 7 fitness signals, evaluated it against all 23 constitutional invariants via GovernanceGate, applied the mutation, hash-chained the evidence, and sealed the record in LineageLedgerV2.

**Zero human intervention in the execution path.** Full human oversight of the constitutional framework (Dustin L. Reid holds the governor role and the constitutional framework was designed and ratified by him).

**Evidence:** The Phase 65 epoch evidence record is sealed in the immutable lineage ledger. The hash cannot be altered. The record cannot be deleted. The execution cannot be un-done.

**Significance:** Phase 65 demonstrates that the governance architecture is not merely theoretical. A real autonomous evolution cycle executed against ADAAD's own runtime, passed through all constitutional gates, and produced a verifiable, tamper-evident evidence record. This is the first time any governed autonomous code evolution system has produced such evidence in production.

### 4.2 First Governed Seed Epoch Run — Phase 77 Track B (March 20, 2026)

**What happened:** A `CapabilitySeed` with `expansion_score = 0.900 ≥ 0.850` was constructed, governed-promoted through the SeedPromotionQueue, approved by the human governor (`DUSTIN-L-REID-DUSTADAAD`), converted into a `ProposalRequest` (cycle_id: `seed-cycle-166597d6cdb61ab6`), injected into the CEL epoch context, run through all 14 `LiveWiredCEL` steps, and had its outcome recorded as a `SeedCELOutcomeEvent` hash-linked to the full upstream chain.

**Evidence artifact:** `artifacts/governance/phase77/seed_epoch_run_evidence.json`  
**run_digest:** `sha256:b3a41c40b99177dc51d5cfdd43d826c27aa7bf718f93fd936f7a5658869590ab`  
**Outcome:** success

**Significance:** `SEED-LIFECYCLE-COMPLETE-0` is now demonstrably satisfied. ADAAD can propose, route, evaluate, and record the outcomes of its own capability evolutions through a constitutional process. The organism is closing its own feedback loop under human governance.

### 4.3 Deterministic Replay

Every ADAAD epoch can be deterministically replayed from its original inputs. Given the same epoch state and the same random seed, the system produces byte-identical output. This is not a testing convenience — it is a constitutional requirement (`REPLAY-0`) and the foundation of the audit system.

Replay capability means: any claim about what ADAAD decided, at any point in its history, can be independently verified. There is no "trust us" in ADAAD's governance model.

### 4.4 SHA-256 Hash-Chained Immutable Ledger

`LineageLedgerV2` maintains 12,441+ entries as of v9.14.0. Every entry is:
- SHA-256 hashed with the previous entry's hash as input
- Append-only (no mutation mechanism exists)
- Deterministically verifiable by replaying the hash chain from genesis

An attacker with write access to the ledger file could add entries but cannot substitute or delete existing entries without breaking the hash chain at the point of modification. `verify_integrity()` will detect the break.

### 4.5 Android Deployment

ADAAD runs on Android 10+ devices with as little as 2GB RAM. This is not a demo mode. The full governance runtime — CEL, ledger, sandbox, and Aponi dashboard — operates in Termux or Pydroid 3 without binary dependencies unavailable on Android.

This matters because it demonstrates that constitutional governance does not require cloud infrastructure. The governance model is portable. The invariants are not tied to AWS or Kubernetes. They are tied to the code.

---

## Part V: The Operator Model

### 5.1 HUMAN-0 — The Inviolable Governor Gate

`HUMAN-0` is the most important invariant in the system. It states: no Tier 0 mutation is ever applied without the governor's GPG-signed commit.

This is not a process rule. It is a constitutional invariant. The governor (Dustin L. Reid) holds the only key that can satisfy `HUMAN-0`. No agent, no automation, no emergency procedure can produce a GPG-signed commit on his behalf without his private key.

**HUMAN-0 is what distinguishes constitutionally governed autonomy from ungoverned automation.** The system can evolve at scale. The human retains decisive authority over constitutional changes and Tier 0 mutations.

### 5.2 The Tier System

ADAAD divides its codebase into three tiers with different governance requirements:

| Tier | Paths | Gate | Autonomous execution |
|---|---|---|---|
| **Tier 0** | `runtime/`, `security/`, orchestrator core | Governor GPG sign-off — `HUMAN-0` | Never |
| **Tier 1** | `tests/`, `docs/`, most agents | GovernanceGate approval | After gate passage |
| **Tier 2** | `experiments/`, `sandbox/` | Sandbox-only | Sandboxed only |

The tier assignment is based on blast radius. A mutation to `runtime/governance/gate_certifier.py` (Tier 0) could compromise the entire governance surface. A mutation to `tests/test_fitness_deterministic.py` (Tier 1) cannot.

### 5.3 The DEVADAAD Agent Role

DEVADAAD is the AI execution agent that operates within the constitutional framework. It can:
- Read and modify Tier 1 and Tier 2 paths
- Open branches, write commits, push to remote
- Run test suites and interpret results
- Generate mutation proposals for GovernanceGate review
- Author documentation, release notes, procession docs

It cannot:
- GPG-sign commits or tags (`HUMAN-0`)
- Merge to main without governor sign-off (`HUMAN-0`)
- Modify constitutional invariants (`HUMAN-0`)
- Execute autonomous mutations on Tier 0 paths (`HUMAN-0`)

This is the correct boundary. The agent is powerful within the constitutional framework. The human retains decisive authority outside it.

### 5.4 Aponi — The Governance Console

Aponi is the real-time human oversight dashboard. It provides:
- Live epoch feed with mutation status and fitness scores
- Seed lifecycle tracker (phases 71–79)
- Lineage ledger health metrics
- GovernanceGate decision history
- CI/CD signal board
- GitHub App event feed (Phase 78)

Aponi does not execute. It observes, surfaces, and alerts. The human uses it to understand what the autonomous system is doing and decide when to intervene.

---

## Part VI: Current Live State — v9.14.0

### 6.1 What Is Live

| Component | Status | Phase | Invariants |
|---|---|---|---|
| Constitutional Evolution Loop (14 steps) | ✅ LIVE | 65 | `CEL-ORDER-0`, `CEL-EVIDENCE-0` |
| LineageLedgerV2 (12,441+ entries) | ✅ LIVE | all | `AUDIT-0`, `REPLAY-0` |
| GovernanceGate | ✅ LIVE | all | `GOV-SOLE-0`, `GATE-0` |
| Seed Lifecycle Pipeline (Phases 71–77) | ✅ LIVE | 71–77 | `SEED-LIFECYCLE-COMPLETE-0` |
| Deterministic Replay | ✅ LIVE | all | `REPLAY-0` |
| Sandbox Isolation (cgroup v2) | ✅ LIVE | 49+ | `SANDBOX-0` |
| ADAADchat GitHub App (governed webhooks) | ✅ LIVE | 77 | `GITHUB-APP-GOV-0` |
| Ed25519/HMAC Event Signing infrastructure | ✅ LIVE | 78 | `LEDGER-SIGN-0` (interface) |
| Aponi GitHub Feed Panel | ✅ LIVE | 78 | — |
| Journal Warm-Cache (11.6× speedup) | ✅ LIVE | 78 | `JOURNAL-CACHE-0` |
| Autonomous Doc Sync CI | ✅ LIVE | 78 | `DOC-SYNC-VERSION-0` |
| Multi-Generation Lineage Graph | ✅ LIVE | 79 | `MULTIGEN-0`–`MULTIGEN-REPLAY-0` |
| KMS/HSM production key wiring | 🟡 PLANNED | 80 | `LEDGER-SIGN-0` (production) |
| Compound Evolution Tracker | 🟡 PLANNED | 80 | Phase 6 horizon |

### 6.2 Metrics at v9.14.0

| Metric | Value |
|---|---|
| Passing tests | **4,748+** |
| Evidence ledger entries | **12,441+** |
| Constitutional invariants | **23** |
| CEL steps | **14** |
| Phases complete | **79** |
| First self-evolution | ✅ Phase 65 — March 13, 2026 |
| First seed epoch run | ✅ Phase 77 — March 20, 2026 |
| Lines of governed runtime | ~47,000 |
| Mutation tier coverage | Tier 0/1/2 fully enforced |
| Android compatibility | ✅ Android 10+ |

### 6.3 What ADAAD Is Not

- Not a code assistant. It doesn't autocomplete.
- Not CI/CD. It governs mutations, not builds.
- Not fully autonomous. `HUMAN-0` is constitutional and inviolable.
- Not a security scanner. It enforces mutation constraints, not vulnerability detection.
- Not magic. Every decision is logged, replayable, and explainable.

---

## Part VII: Evolution Trajectory

### 7.1 Phase 80 Target — KMS/HSM Production Key Wiring

The `EventSigner` abstract interface is live. `Ed25519FileSigner`, `HMACEnvSigner`, and `build_signer_from_env()` are implemented (Phase 78). Phase 80 wires the production KMS backend to `LineageLedgerV2.append_event()` so every ledger entry carries a `SignatureBundle` from the active signer.

When complete: an attacker with write access to the ledger file, and without access to the signing key, cannot substitute ledger entries without producing an invalid signature bundle detectable by `verify_integrity()`. This closes the last gap between hash-chain integrity (current) and cryptographic non-repudiation (Phase 80).

### 7.2 Phase 80+ — Compound Evolution

The Multi-Generation Lineage Graph (Phase 79) provides the foundation for **compound evolution**: epochs that explicitly build on the mutations of prior epochs, creating multi-generation capability improvement chains.

At compound evolution maturity, ADAAD can:
- Identify which prior mutations are preconditions for a proposed evolution
- Score the compound improvement potential of a mutation against the full ancestry chain
- Produce evidence that maps the current state of the codebase to its full governance history

This is the Phase 6 target from the 18-month horizon: **Autonomy Level L4 — Governed Compound Evolution**.

### 7.3 v1.1-GA Readiness

| Gate | Status |
|---|---|
| Gate 1 — CI Quality | ✅ Cleared |
| Gate 2 — Governance Documentation | ⏳ H-04 GA versioning decision (Dustin) |
| Gate 3 — F-Droid Distribution | ⏳ MR submission (Dustin) |
| Gate 4 — Founder GPG Sign-off | ⏳ HUMAN-0 (Dustin) |
| Gate 5 — Phase Roadmap Completeness | ✅ Cleared through Phase 79 |

Three gate items require Dustin's direct action. No agent can satisfy them. They are HUMAN-0 gated by design.

---

## Part VIII: Why This Matters

### 8.1 The Governance Thesis

The dominant fear about autonomous AI systems acting on codebases is not that they will be incompetent. It is that they will be competent but ungoverned — making changes that are locally optimal but globally dangerous, without audit trails, without reversibility, without accountability.

ADAAD's answer is not to limit capability. It is to make governance structural.

**Constitutional invariants, not configuration.** There is no flag to disable the governance gate. There is no emergency bypass. There is no "trusted operator" exception. The gate is the path.

**Evidence, not promises.** Every mutation is ledger-recorded before execution. The record is tamper-evident. The replay is deterministic. Claims about what ADAAD decided are verifiable, not testimonial.

**Human authority at the right level.** HUMAN-0 preserves decisive human authority over constitutional changes and Tier 0 mutations. It does not require human review of every Tier 1 mutation — that would defeat the purpose of automation. The human governs the constitutional framework; the framework governs the execution.

### 8.2 The Portability Thesis

Governance should not require enterprise infrastructure. ADAAD runs on a $200 Android phone. The governance model — hash-chained ledger, constitutional invariants, deterministic replay — is implemented in pure Python with no infrastructure dependencies.

This is a deliberate design choice. An autonomous system that only operates safely when connected to AWS KMS and a Kubernetes cluster is not actually safe. It is dependent on infrastructure availability for its safety properties. The moment that infrastructure is unavailable, the safety properties are undefined.

ADAAD's safety properties are computational, not infrastructural. They derive from the mathematical properties of SHA-256 hash chains and the structural properties of the Python runtime — both available on a $200 phone.

### 8.3 The Evidence Thesis

ADAAD does not claim to be safe. It produces evidence that it is safe.

The distinction: claims require trust. Evidence requires verification.

Every autonomous mutation decision is recorded in an immutable, hash-chained ledger before execution. Every claim about what ADAAD decided can be independently verified by replaying the epoch from its original inputs. The hash chain cannot be altered without detection. The replay is deterministic.

This is a fundamental shift in how AI system governance works. Instead of auditing outputs and inferring governance quality, ADAAD allows direct inspection of the decision-making process itself — at any point in time, for any epoch, with byte-level reproducibility.

---

## Appendix A: Constitutional Invariant Reference

Full invariant table with module locations and test coverage:

| Invariant | Module | Test |
|---|---|---|
| `HUMAN-0` | `runtime/governance/gate_certifier.py` | `tests/governance/` |
| `AUDIT-0` | `runtime/evolution/lineage_v2.py` | `tests/test_lineage_v2_integrity.py` |
| `GOV-SOLE-0` | `runtime/governance/gate_certifier.py` | `tests/test_gatekeeper_protocol.py` |
| `REPLAY-0` | `runtime/evolution/evolution_loop.py` | `tests/determinism/` |
| `GATE-0` | `runtime/governance/gate_certifier.py` | `tests/test_governance_surface.py` |
| `CEL-ORDER-0` | `runtime/evolution/cel_wiring.py` | `tests/test_phase78_journal_cache.py` |
| `CEL-EVIDENCE-0` | `runtime/evolution/evolution_loop.py` | `tests/test_evolution_audit_grade.py` |
| `SANDBOX-0` | `runtime/sandbox/` | `tests/sandbox/` |
| `SEED-PROMO-0` | `runtime/seed_promotion.py` | `tests/test_phase77_track_b_seed_epoch.py` |
| `SEED-REVIEW-HUMAN-0` | `runtime/seed_review.py` | `tests/test_phase77_track_b_seed_epoch.py` |
| `SEED-LIFECYCLE-COMPLETE-0` | pipeline Phases 71–77 | `tests/test_phase77_track_b_seed_epoch.py` |
| `SEED-OUTCOME-AUDIT-0` | `runtime/seed_cel_outcome.py` | `tests/test_phase76_seed_cel_outcome.py` |
| `EVENT-SIGN-ABSTRACT-0` | `runtime/evolution/event_signing.py` | `tests/test_phase77_track_a_close.py` |
| `LEDGER-SIGN-0` | `runtime/evolution/event_signing.py` | `tests/test_phase78_event_signing.py` |
| `MULTIGEN-0` | `runtime/evolution/multi_gen_lineage.py` | `tests/test_phase79_multi_gen_lineage.py` |
| `MULTIGEN-DETERM-0` | `runtime/evolution/multi_gen_lineage.py` | `tests/test_phase79_multi_gen_lineage.py` |
| `MULTIGEN-REPLAY-0` | `runtime/evolution/multi_gen_lineage.py` | `tests/test_phase79_multi_gen_lineage.py` |
| `WEBHOOK-SHIM-DELEG-0` | `runtime/integrations/github_webhook_handler.py` | `tests/test_phase77_track_a_close.py` |
| `DOC-SYNC-VERSION-0` | `scripts/verify_doc_sync.py` | `tests/test_phase78_aponi_github_feed.py` |
| `JOURNAL-CACHE-0` | `runtime/evolution/lineage_v2.py` | `tests/test_phase78_journal_cache.py` |
| `GPLUGIN-ABSTRACT-0` | `runtime/innovations.py` | `tests/test_phase77_track_a_close.py` |
| `GITHUB-APP-GOV-0` | `app/github_app.py` | `tests/test_github_app.py` |
| `SEED-CEL-AUDIT-0` | `runtime/seed_cel_injector.py` | `tests/test_phase75_seed_proposal_cel_injection.py` |

---

## Appendix B: Phase Completion Map

| Phase | Version | Title | Key Milestone |
|---|---|---|---|
| 47–51 | v7.1–v7.5 | Gap Closure + Alignment | AutonomyLoop wired, federation consensus |
| 52–56 | v7.6–v7.x | Cross-Epoch Memory | EpochMemoryStore, Aponi hardening |
| 57–64 | v8.0–v8.7 | Constitutional Sequence | Full 14-step CEL, governance surface |
| 65 | v9.0 | **First Autonomous Self-Evolution** | ⛓ **March 13, 2026 — hash sealed** |
| 66–70 | v9.1–v9.5 | Innovations Pipeline | CapabilitySeed, oracle, vision mode |
| 71–76 | v9.6–v9.11 | Seed Lifecycle Pipeline | Full pipeline: evolution → outcome |
| 77 | v9.13 | **SEED-LIFECYCLE-COMPLETE-0** | 🌱 **March 20, 2026 — first live epoch** |
| 78 | v9.14 | Production Signing + Aponi GitHub Feed | Ed25519/HMAC, doc autosync |
| 79 | v9.14 | Multi-Generation Lineage Graph | DAG ancestry tracking |
| 80 (planned) | v9.15 | KMS/HSM Production Wiring | Non-repudiable ledger events |
| 81+ (horizon) | v9.16+ | Compound Evolution | L4 governed multi-gen evolution |

---

## Appendix C: Evidence Artifacts

All evidence artifacts are committed to the repository and hash-linked to the ledger:

| Artifact | Phase | Path |
|---|---|---|
| First Seed Epoch Run | 77 | `artifacts/governance/phase77/seed_epoch_run_evidence.json` |
| Phase 65 Epoch Evidence | 65 | Sealed in `LineageLedgerV2` (immutable) |

---

*This thesis is a living document. It is updated with each major phase. The claims in this document are verifiable against the codebase, the ledger, and the test suite. Nothing in this document is testimonial.*

*For the constitutional framework that governs all claims in this document, see `docs/CONSTITUTION.md`.*

*For the evidence that backs them, see `runtime/evolution/lineage_v2.py` and the hash-chained ledger.*

**Innovative AI LLC — Dustin L. Reid, Governor**  
**v9.14.0 — March 20, 2026**
