# CHANGELOG

Generated deterministically from merged governance metadata.

## [9.24.0] — 2026-03-23 — Phase 91 INNOV-07 · Live Shadow Mutation Execution (LSME)

### World-First: Constitutionally-Governed Shadow Execution Against Live Traffic

ADAAD now executes proposed mutations in a zero-write, read-only shadow against its
own live production request traffic before governance approval — the first governed
autonomous evolution system to use live traffic as a fitness signal while maintaining
all constitutional guarantees through an enforced zero-write shadow contract.

**New module:** `runtime/evolution/lsme_engine.py`

- `ShadowContract` — constitutional zero-write contract; `is_zero_write()` enforces
  LSME-0: all three fields (write, egress, db) MUST be False before any shadow runs
- `ShadowBudget` — resource bounds: wall-clock ms, CPU ms, memory MB, max requests
- `TrafficRequest` / `BaselineResponse` / `ShadowResponse` — request/response data types
- `ShadowFitnessReport` — complete evidence artifact: divergence_rate, error_delta,
  P99 latency delta, invariant_failures, shadow_responses; hash-chained; ledger-ready
- `evaluate_lsme_gate_0()` — pre-execution gate: contract checks (1-3), AST write/egress
  scan (4-5), budget advisory (6); only LSME_BUDGET_EXCEEDED is non-blocking
- `evaluate_lsme_gate_1()` — post-execution gate: divergence rate, error regression,
  P99 latency regression, invariant failures, trace archival (LSME-1)

**Invariants introduced:**
- `LSME-0`: Shadow execution MUST be zero-write. Write or egress detection (AST or
  runtime) is a hard block and HUMAN-0 alert. LSME_BUDGET_EXCEEDED is the only
  non-blocking failure — mutation proceeds on synthetic fitness only.
- `LSME-1`: ShadowFitnessReport MUST be committed to the evidence ledger BEFORE any
  divergence comparison begins. trace_committed=False → LSME_SHADOW_ABORTED always.

**Failure modes:** `LSME_WRITE_DETECTED`, `LSME_EGRESS_DETECTED`, `LSME_BUDGET_EXCEEDED`,
`LSME_ERROR_REGRESSION`, `LSME_LATENCY_REGRESSION`, `LSME_TRACE_INCOMPLETE`,
`LSME_CONTRACT_VIOLATION`, `LSME_INVARIANT_FAILURE`, `LSME_DIVERGENCE_EXCEEDED`

**Tests:** `tests/test_phase91_lsme.py` — T91-LSME-01..20 (20/20 PASS)

---

### 🏁 Phase 87 Innovation Sequence — COMPLETE

All 7 innovations from the HUMAN-0 ratified Phase 87 Innovation Architecture Plan
have been implemented, tested, and shipped:

| ID | Name | Abbr | Version | Tests | Invariants |
|----|------|------|---------|-------|------------|
| INNOV-01 | Constitutional Self-Amendment Protocol | CSAP | v9.18.0 | 20/20 | CSAP-0, CSAP-1 |
| INNOV-02 | Adversarial Constitutional Stress Engine | ACSE | v9.19.0 | 20/20 | ACSE-0, ACSE-1 |
| INNOV-03 | Temporal Invariant Forecasting Engine | TIFE | v9.20.0 | 20/20 | TIFE-0 |
| INNOV-04 | Semantic Constitutional Drift Detector | SCDD | v9.21.0 | 40/40 | SCDD-0 |
| INNOV-05 | Autonomous Organ Emergence Protocol | AOEP | v9.22.0 | 20/20 | AOEP-0 |
| INNOV-06 | Cryptographic Evolution Proof DAG | CEPD | v9.23.0 | 20/20 | CEPD-0, CEPD-1 |
| INNOV-07 | Live Shadow Mutation Execution | LSME | v9.24.0 | 20/20 | LSME-0, LSME-1 |

**Total new tests (this sequence):** 160  
**New Hard-class invariants:** CSAP-0, CSAP-1, ACSE-0, ACSE-1, TIFE-0, SCDD-0, AOEP-0, CEPD-0, CEPD-1, LSME-0, LSME-1

---

## [9.23.0] — 2026-03-23 — Phase 90 INNOV-06 · Cryptographic Evolution Proof DAG (CEPD)

### World-First: Cryptographic DAG Proof of Evolutionary Lineage

ADAAD now produces an unbreakable, tamper-evident proof of evolutionary lineage from
genesis to current state — the first autonomous evolution system to generate a
cryptographic DAG linking every mutation to ALL of its causal ancestors via Merkle
root.  CryptographicProofBundle is independently verifiable by third parties without
system access, and is structured for legal admissibility (FINDING-66-003).

**New module:** `runtime/evolution/cepd_engine.py`

- `CEPDDagNode` — DAG node: mutation_id, epoch_id, parent_node_ids, ancestor_merkle_root,
  payload_hash, HMAC/Ed25519 signature, cepd_version
- `CryptographicProofBundle` — self-contained proof: dag_node + complete ancestor_set +
  merkle_root + lineage_depth + genesis_traceable + bundle_hash; primary patent artifact
- `CEPDDagStore` — append-only in-memory DAG; genesis pre-seeded; BFS genesis traceability
- `compute_ancestor_merkle_root()` — deterministic SHA-256 Merkle over sorted ancestor IDs
- `verify_merkle_determinism()` — CEPD-0 self-check; two independent computations
- `evaluate_cepd_gate_0()` — 5-check DAG integrity gate; fail-closed; appends node on pass
- `verify_proof_bundle()` — independent verifier surface (no system access required)
- `sign_node()` / `verify_signature()` — HMAC-SHA256 (offline) or Ed25519 (PyNaCl)

**Invariants introduced:**
- `CEPD-0`: Every DAG node MUST carry an ancestor_merkle_root that is deterministically
  reproducible from its causal ancestor set alone (CEPD_MERKLE_NONDETERMINISTIC → rejected).
- `CEPD-1`: Every DAG node MUST be traceable to the genesis node by following parent edges
  (CEPD_GENESIS_UNTRACEABLE is a constitutional integrity failure; HUMAN-0 alert required).

**Failure modes:** `CEPD_ANCESTOR_INCOMPLETE`, `CEPD_SIGNATURE_INVALID`,
`CEPD_MERKLE_NONDETERMINISTIC`, `CEPD_GENESIS_UNTRACEABLE`, `CEPD_DEPTH_EXCEEDED`,
`CEPD_NODE_INCOMPLETE`, `CEPD_NODE_REJECTED`

**Tests:** `tests/test_phase90_cepd.py` — T90-CEPD-01..20 (20/20 PASS)

**Next:** INNOV-07 LSME (v9.24.0) — Live Shadow Mutation Execution

---

## [9.22.0] — 2026-03-23 — Phase 89 INNOV-05 · Autonomous Organ Emergence Protocol (AOEP)

### World-First: Constitutionally-Governed Autonomous Architectural Self-Extension

ADAAD can now autonomously identify behavioral gaps in its capability surface and
propose entirely new organs — new architectural subsystems — to address those gaps.
All proposals require HUMAN-0 ratification; no organ constitutionally exists until
the ratification event is appended to governance_events.jsonl.

**New module:** `runtime/evolution/aoep_protocol.py`

- `CapabilityGapSignal` — detected capability gap: sustained_epochs, affected mutation
  classes, candidate_organ_purpose, deterministic gap_id + gap_hash
- `FailurePatternSummary` — recurring failure patterns attributed to a structural gap
- `OrganManifestEntry` — single organ in the current organ manifest (capability surface)
- `OrganProposal` — formal proposal for a new organ; always status PENDING_HUMAN_0 on
  GATE-0 pass; human_0_required is unconditionally True
- `Human0RatificationPayload` — HUMAN-0 sign-off bundle: proposal_id, ratification_hash,
  operator_id, timestamp, human_0_signature, predecessor_hash
- `RatificationRecord` — hash-chained ledger-ready record of GATE-1 outcome
- `AOEPCooldownTracker` — per-gap re-evaluation cooldown (AOEP_REEVAL_COOLDOWN_EPOCHS=5)
- `evaluate_aoep_gate_0()` — 5-check gap qualification gate; fail-closed
- `evaluate_aoep_gate_1()` — HUMAN-0 ratification gate; AOEP-0 non-bypassable

**Invariant introduced:**
- `AOEP-0`: Every OrganProposal MUST be submitted to HUMAN-0 before implementation.
  AOEP-GATE-1 has NO automated bypass — empty human_0_signature ALWAYS produces
  AOEP_HUMAN_0_BLOCKED; the organ does not constitutionally exist until ratification
  event is appended to governance_events.jsonl.

**Failure modes:** `AOEP_GAP_UNQUALIFIED`, `AOEP_GAP_ADDRESSABLE`, `AOEP_HUMAN_0_BLOCKED`,
`AOEP_PROPOSAL_INCOMPLETE`, `AOEP_MANIFEST_CONFLICT`, `AOEP_INSUFFICIENT_MEMORY`,
`AOEP_INSUFFICIENT_PATTERNS`, `AOEP_SIGNATURE_MISSING`, `AOEP_RATIFICATION_HASH_MISMATCH`

**Tests:** `tests/test_phase89_aoep.py` — T89-AOEP-01..20 (20/20 PASS)

**Next:** INNOV-06 CEPD (v9.23.0) — Cryptographic Evolution Proof DAG

---

## [9.21.0] — 2026-03-23 — Phase 87 INNOV-04 · Semantic Constitutional Drift Detector (SCDD)

### World-First: Semantic Drift Detection for Constitutional Invariants

ADAAD now detects when constitutional invariants have drifted semantically — when the
same rule text begins governing a different behavioral surface due to system substrate
evolution — the first autonomous evolution system to distinguish rule text stability
from behavioral coverage drift across epochs.

**New module:** `runtime/evolution/scdd_engine.py`

- `BehavioralSurfaceSnapshot` — per-epoch empirical statistics of how a rule fires:
  evaluations, blocks, block_rate, mean_fitness_delta_blocked, touched_mutation_classes
- `SemanticInvariantFingerprint` — deterministic fingerprint composed of statement_hash
  + surface_hash + composite_hash; basis for cross-epoch drift comparison
- `DriftVector` — per-invariant drift measurement: coverage_delta (40%), precision_delta
  (30%), class_surface_delta (30%); statement change adds 0.10 bonus; clamped to [0, 1]
- `ConstitutionalDriftReport` — full output; hash-chained; produced on ALL outcomes
  (STABLE, REVIEW_REQUIRED, BLOCKED); contains all DriftVectors + max_drift_score
- `SCDDEvaluationInput` — input bundle: baseline fingerprints, current fingerprints,
  rule statements, predecessor_hash
- `compute_semantic_fingerprint()` — deterministic; SHA-256(statement) + SHA-256(surface
  JSON) → SHA-256(statement_hash + surface_hash); replay-verified
- `compute_drift_vector()` — weighted composite of coverage, precision, class-surface
  delta + statement change bonus; `_classify_drift()` maps score → DriftClass
- `evaluate_scdd_gate_0()` — 7-check gate; fail-closed; full report on all outcomes

**Invariant introduced:**
- `SCDD-0`: SCDD MUST run every N epochs; any invariant with semantic drift score ≥
  SCDD_CRITICAL_THRESHOLD (0.75) MUST produce SCDD_BLOCKED outcome, blocking further
  mutation progress until the drifted invariant is reviewed through CSAP.

**Failure modes covered:** `SCDD_CRITICAL_DRIFT_FOUND`, `SCDD_FINGERPRINT_NONDETERMINISTIC`,
`SCDD_BASELINE_MISSING`, `SCDD_EMPTY_INVARIANT_SET`, `SCDD_SURFACE_HASH_CONFLICT`

**Drift classification thresholds:** STABLE < 0.30 ≤ MINOR < 0.55 ≤ MAJOR < 0.75 ≤ CRITICAL

**Tests:** `tests/test_phase87_innov04_scdd.py` — T87-SCDD-01..20 (20/20 PASS)

**Next:** INNOV-05 AOEP (v9.22.0) — Autonomous Organ Emergence Protocol

---

## [9.20.0] — 2026-03-23 — Phase 87 INNOV-03 · Temporal Invariant Forecasting Engine (TIFE)

### World-First: Multi-Epoch Constitutional Pre-Validation

ADAAD now evaluates proposed mutations against simulated *future* system states before
governance approval — the first autonomous evolution system to implement multi-epoch
constitutional pre-validation.  Governance transforms from reactive to predictive.

**New module:** `runtime/evolution/tife_engine.py`

- `TIFEMutationInput` — mutation projection enriched with capability deltas, governance debt, trajectory flags
- `VisionProjection` — trajectory forecast baseline (dead-end paths, debt trajectory, capability deltas)
- `CapabilityGraphSnapshot` — CapabilityGraphV2 projection; `non_redundant_ids()` for regression detection
- `InvariantEvaluationReport` — per-epoch invariant status, projected debt, ISI contribution
- `TemporalViabilityReport` — full output; hash-chained; specifies first_violation_epoch on BLOCKED
- `evaluate_tife_gate_0()` — 5-check temporal viability gate; fail-closed; report on both outcomes
- `analyse_isi_trend()` — rolling ISI health signal for AnalysisAgent; degrading/stable/improving + alert

**Invariant introduced:**
- `TIFE-0`: Every mutation MUST pass TIFE-GATE-0 (ISI ≥ 0.85, no debt breach, no dead-end,
  no capability regression) before GovernanceGate v2.  Failed mutations enter `temporal_hold`;
  TemporalViabilityReport specifies the remediation epoch.

**Failure modes covered:** `TIFE_ISI_BELOW_THRESHOLD`, `TIFE_DEBT_HORIZON_BREACH`,
`TIFE_TRAJECTORY_DEAD_END`, `TIFE_CAPABILITY_REGRESSION`, `TIFE_SIMULATION_NONDETERMINISTIC`

**Tests:** `tests/test_phase87_innov03_tife.py` — T87-TIFE-01..20 (20/20 PASS)

**Next:** INNOV-04 SCDD (v9.21.0) — Semantic Constitutional Drift Detector

---

## [9.19.0] — 2026-03-23 — Phase 87 INNOV-02 · Adversarial Constitutional Stress Engine (ACSE)

### World-First: Governed Constitutional Adversarial Red-Teaming

ADAAD now red-teams its own mutation proposals and constitutional amendments before they
advance to GovernanceGate v2.  ACSE is the immune system's attack function — the system
stress-tests itself constitutionally before anything merges.

**New module:** `runtime/evolution/acse_engine.py`

- `MutationCandidate` — minimal projection of a mutation fed to ACSE; decoupled from full mutation model
- `AdversarialBudget` — resource envelope: wall-clock ms, LLM call quota, max vector count
- `AdversarialTestVector` — single deterministic adversarial probe; class, verdict, violation detail, seed audit
- `AdversarialEvidenceBundle` — full output package; hash-chained; mandatory GovernanceGate v2 input
- `derive_adversarial_seed()` — `SHA-256(lineage_digest + epoch_id)`; determinism-verified on every run
- `_generate_invariant_probe_vectors()` — ≥ 5 canonical vectors per touched invariant class (ACSE-0)
- `_generate_boundary_stress_vectors()` — one probe per claimed fitness threshold at 1% boundary delta
- `_generate_replay_interference_vectors()` — 3 isolation-context replay probes
- `evaluate_acse_gate_0()` — 8-check gate; fail-closed; full `AdversarialEvidenceBundle` on all outcomes
- `acse_csap_gate1_check()` — **hardened CSAP-GATE-1 check 3**: advisory → hard FAIL; `ACSE_CLEAR` bundle required

**Invariants introduced:**
- `ACSE-0`: ACSE MUST produce ≥ 5 deterministic adversarial test vectors per invariant class touched
  before any mutation proceeds to GovernanceGate v2
- `ACSE-1`: `AdversarialEvidenceBundle` MUST be hash-chained and archived before mutation state advances

**Failure modes covered:** `ACSE_BOUNDARY_BREACH`, `ACSE_VIOLATION_FOUND`, `ACSE_BUDGET_EXCEEDED`,
`ACSE_SEED_NONDETERMINISTIC`, `ACSE_COUNTER_EVIDENCE_UNSIGNED`

**CSAP integration:** CSAP-GATE-1 check 3 hardened from advisory to hard FAIL.  Any amendment
without `ACSE_CLEAR` bundle is now unconditionally rejected.

**Tests:** `tests/test_phase87_innov02_acse.py` — T87-ACSE-01..20 (20/20 PASS)

**Next:** INNOV-03 TIFE (v9.20.0) — Temporal Invariant Forecasting Engine

---

## [9.18.0] — 2026-03-23 — Phase 87 INNOV-01 · Constitutional Self-Amendment Protocol (CSAP)

### World-First: Governed Constitutional Self-Amendment

ADAAD can now propose, validate, and cryptographically ratify amendments to its own
constitutional invariant set under a two-gate supermajority protocol.

**New module:** `runtime/evolution/csap_protocol.py`

- `ConstitutionalAmendmentProposal` — machine-readable proposal dataclass; `content_hash()` deterministic
- `InvariantParser` — structural parser enforcing modal-verb grammar; deterministic; no IO
- `InvariantsMatrix` — full invariant registry; `apply_amendment()` returns new matrix (immutable); original never mutated
- `ConstitutionalAmendmentQueue` — append-only persisted proposal queue (CSAP-GATE-1 check 1)
- `ConstitutionalAmendmentLedger` — append-only ledger; `verify_chain()` predecessor-hash audit; CSAP-1 enforced
- `evaluate_csap_gate_0()` — six deterministic eligibility checks; fail-closed
- `evaluate_csap_gate_1()` — six ratification checks; fitness regression delta gate; ACSE advisory hook
- `ConstitutionalSelfAmendmentProtocol` — orchestrator; CSAP-1 ledger-before-matrix ordering enforced

**Invariants introduced:**
- `CSAP-0`: Hard-class amendment MUST NOT proceed without HUMAN-0 co-signature — enforced in CSAP-GATE-0 check 6
- `CSAP-1`: Ledger MUST be written before InvariantsMatrix is mutated — enforced in orchestrator `evaluate()`

**Failure modes covered:** `AMENDMENT_INELIGIBLE`, `RATIFICATION_DENIED`, `AMENDMENT_CONFLICT`,
`AMENDMENT_REPLAY_BROKEN`, `INVARIANT_PARSER_REJECT`

**Tests:** `tests/test_phase87_innov01_csap.py` — T87-CSAP-01..20 (20/20 PASS)

**Next:** INNOV-02 ACSE (v9.19.0) — when ACSE ships, CSAP-GATE-1 check 3 hardens from advisory to hard FAIL.

---

## [9.17.1] — 2026-03-23 — Phase 87 · Innovation Architecture Plan — HUMAN-0 Ratified

### Governance — Phase 87 Innovation Architecture Plan

Seven world-first autonomous improvement features ratified by HUMAN-0 (Dustin L. Reid).
No implementation code in this PR — plan document and governance ledger event only.

**Document:** `docs/governance/PHASE_87_INNOVATION_ARCHITECTURE_PLAN.md`  
**Document SHA-256:** `sha256:780af05e3b610f3bd864be5a906fe7c840e563fc346c3a70baec1b6360cbdb2b`  
**Governance ledger event:** `HUMAN_0_RATIFICATION · PHASE-87-PLAN · record_hash sha256:09832b5aff5b587fa7a70ba1fb1c65b79dfc44ee30163a37782172784e3b3ef1`

**Features ratified (implementation sequence v9.18.0 → v9.24.0):**

| ID | Name | Abbr | Target |
|----|------|------|--------|
| INNOV-01 | Constitutional Self-Amendment Protocol | CSAP | v9.18.0 |
| INNOV-02 | Adversarial Constitutional Stress Engine | ACSE | v9.19.0 |
| INNOV-03 | Temporal Invariant Forecasting Engine | TIFE | v9.20.0 |
| INNOV-04 | Semantic Constitutional Drift Detector | SCDD | v9.21.0 |
| INNOV-05 | Autonomous Organ Emergence Protocol | AOEP | v9.22.0 |
| INNOV-06 | Cryptographic Evolution Proof DAG | CEPD | v9.23.0 |
| INNOV-07 | Live Shadow Mutation Execution | LSME | v9.24.0 |

**New Hard-class invariants registered (pending InvariantsMatrix update in INNOV-01 PR):**
`CSAP-0`, `CSAP-1`, `ACSE-0`, `ACSE-1`, `TIFE-0`, `SCDD-0`, `AOEP-0`, `CEPD-0`, `CEPD-1`, `LSME-0`, `LSME-1`

**Open finding:** FINDING-66-003 (patent filing) addressed by CEPD (INNOV-06) via `CryptographicProofBundle`.

**Invariant:** All seven implementations MUST proceed in ID order. No phase may begin until all prior phases are RELEASED and tagged.

---

## [9.17.0] — 2026-03-21 — Phase 86 · Evolution Engine Integration + CompoundEvolutionTracker

### Phase 86 Track A — CEL Evolution Engine Wiring

- `runtime/evolution/constitutional_evolution_loop.py` — 14-step CEL extended to 15 steps:
  - **Step 8 FITNESS-SCORE**: stub (`0.65 if sandbox_ok`) replaced with real pipeline —
    `FitnessOrchestrator.score()` (5-component composite) + `FitnessDecayScorer.evaluate()`
    (temporal half-life discount) + `CausalFitnessAttributor.attribute()` (per-op Shapley).
    `STEP8-LEDGER-FIRST-0`: `fitness_event_digest` written before `fitness_summary` committed.
  - **Step 9 PARETO-SELECT** (new): `ParetoCompetitionOrchestrator.run_epoch()` replaces
    scalar `score > 0.5` threshold in place since Phase 64. `CEL-PARETO-0`: frontier digest
    ledger-first before Step 10.
  - **Post-epoch SELF-DISCOVERY hook**: `ConstitutionalSelfDiscoveryLoop` fires every
    `SELF_DISC_FREQUENCY` (5) completed epochs. `CEL-SELF-DISC-NONBLOCK-0`: exception-safe,
    never blocks. `SELF-DISC-HUMAN-0`: candidates advisory only; HUMAN-0 required for
    any promotion to `CONSTITUTION.md`.
  - `_UNSET` sentinel distinguishes lazy-import from explicit `None` injection.
  - `self._epoch_seq` tracks completed epochs; blocked epochs do not increment.
- `tests/test_phase86_cel_fitness_wiring.py` — T86-FIT-01..24 (24 tests)
- `tests/test_phase86_pareto_select_step.py` — T86-PAR-01..15 (15 tests)
- `tests/test_phase86_self_discovery_hook.py` — T86-DISC-01..10 (10 tests)

**Invariants introduced:** `STEP8-LEDGER-FIRST-0`, `STEP8-DETERM-0`, `CEL-PARETO-0`,
`CEL-PARETO-DETERM-0`, `CEL-SELF-DISC-0`, `CEL-SELF-DISC-NONBLOCK-0`, `SELF-DISC-HUMAN-0`

### Phase 86 Track B — CompoundEvolutionTracker

- `runtime/evolution/compound_evolution.py` — `CompoundEvolutionTracker`:
  - `track_epoch(epoch_id, pareto_result, lineage_graph, attributions)` → `CompoundEvolutionRecord`
  - Synthesises `ParetoCompetitionResult` + `MultiGenLineageGraph` + `CausalAttributionReport`
  - Generation-discounted fitness aggregation (`GENERATION_DISCOUNT_FACTOR = 0.8`)
  - `COMP-GOV-WRITE-0`: `ledger.append_raw()` called before record returned
- `CompoundEvolutionRecord`, `AncestorContribution` — frozen dataclasses with round-trip serialisation
- `tests/test_phase86_compound_evolution.py` — T86-COMP-01..24 (24 tests)

**Invariants introduced:** `COMP-TRACK-0`, `COMP-ANCESTRY-0`, `COMP-GOV-WRITE-0`, `COMP-CAUSAL-0`

## [9.16.0] — 2026-03-20 — Phases 81–84 · Evolution Engine Core

### Phase 78 (merge) — Journal Warm-Cache + Autonomous Doc Sync

- `security/ledger/journal.py` — `JOURNAL-CACHE-0` warm-path tail cache absorbed into main; `JournalPaths` dataclass + full path-resolution infrastructure
- `scripts/verify_doc_sync.py` — upgraded to full argparse/dataclass/JSON-output implementation with `DOC-SYNC-DETERM-0` determinism guarantee
- `docs/ADAADCHAT_SETUP.md` — GitHub App wiring guide for ADAADchat operators
- `.env.example` — canonical environment variable reference
- `tests/governance/test_journal_warm_cache.py`, `test_phase78_doc_sync.py` — phase78 constitutional test suites absorbed

### Phase 81 — Constitutional Self-Discovery Loop

- `runtime/evolution/constitutional_self_discovery.py` — `ConstitutionalSelfDiscoveryLoop`: coordinates failure mining → invariant candidacy → ratification gate
- `runtime/evolution/failure_pattern_miner.py` — `FailurePatternMiner`: mines ledger for recurring failure signatures, produces `FailurePattern` candidates
- `runtime/evolution/invariant_candidate_proposer.py` — `InvariantCandidateProposer`: lifts failure patterns to `InvariantCandidate` proposals with constitutional metadata
- `runtime/evolution/invariant_ratification_gate.py` — `InvariantRatificationGate`: GovernanceGate-gated ratification; only constitutionally-consistent invariants advance
- `tests/test_phase81_constitutional_self_discovery.py` — constitutional test suite
- `artifacts/governance/phase81/track_a_sign_off.json` — governance sign-off artifact
- `pytest.ini` — `phase81` mark registered

**Invariants introduced:**
- `SELF-DISC-0`: ADAAD can propose new constitutional invariants from its own failure history
- `RATIFY-GOV-0`: No invariant candidate advances without GovernanceGate ratification
- `MINE-DETERM-0`: identical ledger state → identical failure pattern candidates

### Phase 82 — Pareto Population Evolution

- `runtime/evolution/pareto_frontier.py` — `ParetoFrontier`: multi-objective non-dominated set maintenance; `dominates()`, `frontier_digest()`
- `runtime/evolution/pareto_competition.py` — `ParetoCompetitionOrchestrator`: population-level multi-objective competitive selection
- `runtime/seed_competition.py` — extended with Pareto-aware ranking surface
- `tests/test_phase82_pareto_evolution.py` — constitutional test suite
- `artifacts/governance/phase82/track_a_sign_off.json` — governance sign-off artifact

**Invariants introduced:**
- `PARETO-0`: Evolution selection is non-dominated — no candidate advances if dominated on all objectives
- `PARETO-DETERM-0`: identical population → identical frontier; ties broken lexicographically
- `PARETO-GOV-0`: Pareto selection result written to ledger before any promotion

### Phase 83 — Causal Fitness Attribution Engine

- `runtime/evolution/causal_fitness_attributor.py` — `CausalFitnessAttributor`: Shapley-value approximation for per-operation fitness contribution
- `runtime/evolution/mutation_ablator.py` — `MutationAblator`: ablation harness; removes operations and re-evaluates fitness delta
- `tests/test_phase83_causal_fitness_attribution.py` — constitutional test suite
- `artifacts/governance/phase83/track_a_sign_off.json` — governance sign-off artifact

**Invariants introduced:**
- `CAUSAL-ATTR-0`: Every fitness score traceable to per-operation causal contributions
- `ABLATE-DETERM-0`: ablation runs are deterministic and ledger-recorded
- `SHAPLEY-BOUND-0`: approximation error bounded; exact Shapley computed when coalition count ≤ threshold

### Phase 84 — Temporal Fitness Half-Life

- `runtime/evolution/codebase_state_vector.py` — `CodebaseStateVector`: fingerprints codebase structural state for temporal comparison
- `runtime/evolution/fitness_decay_scorer.py` — `FitnessDecayScorer`: applies exponential half-life decay to historical fitness scores by codebase drift distance
- `tests/test_phase84_fitness_half_life.py` — constitutional test suite
- `artifacts/governance/phase84/track_a_sign_off.json` — governance sign-off artifact

**Invariants introduced:**
- `DECAY-0`: Historical fitness scores discounted by codebase structural drift — stale scores do not gate current promotions
- `HALFLIFE-DETERM-0`: identical `CodebaseStateVector` pair → identical decay coefficient
- `DECAY-LEDGER-0`: decay coefficients written to ledger at scoring time

### Metrics at v9.16.0
- Tests: 4,800+ passing (+28 est.)
- Phases complete: 84
- Constitutional invariants: 36 (+9)
- Evolution engine: Pareto multi-objective + causal attribution + temporal decay — all operational

---

## [9.15.0] — 2026-03-20 — Phase 80 Complete (Multi-Generation Compound Evolution)

### Phase 80 — Multi-Seed Competitive Epoch

#### Track A — Multi-Seed Competition Infrastructure (#PR-80-01)

- `runtime/seed_competition.py` — `SeedCompetitionOrchestrator` (new): population-level competitive epoch runner
  - `SeedCandidate` (frozen dataclass): candidate_id + fitness_context + metadata
  - `CompetitionResult` (frozen dataclass): epoch_id, winner_id, ranked_ids, fitness_scores, gate_verdict, competition_digest
  - `_rank_candidates()`: deterministic fitness ranking, tie-break by lexicographic candidate_id
  - `_competition_digest()`: SHA-256 of canonical sorted inputs (SEED-RANK-0)
- `runtime/evolution/lineage_v2.py` — `SeedCompetitionEpochEvent` (frozen dataclass) + `append_competition_epoch()` on `LineageLedgerV2`
- `runtime/fitness_pipeline.py` — `rank_seeds_by_fitness()`: multi-seed ranking surface using FitnessOrchestrator
- `tests/test_phase80_seed_competition.py` — 24 constitutional tests T80-COMP-01..24 (24/24 pass)
- `artifacts/governance/phase80/track_a_sign_off.json` — governance sign-off artifact
- `pytest.ini` — phase80 mark registered

**Invariants introduced:**
- `SEED-COMP-0`: No seed promoted without competitive ranking of all candidates in epoch window
- `SEED-RANK-0`: Fitness ranking deterministic — equal inputs → identical rank orderings; ties lexicographic
- `COMP-GOV-0`: GovernanceGate evaluates all candidates before any single candidate advances
- `COMP-LEDGER-0`: `SeedCompetitionEpochEvent` written to `LineageLedgerV2` before any promotion

#### Track B — GA Unblock Sprint (#PR-80-02)

- `android/fdroid/com.innovativeai.adaad.yml` — v9.14.0 build entry (versionCode 91400); `CurrentVersion` → 9.14.0
- `docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md` — § 2.3 updated: v1.1-GA canonical declaration (closes FINDING-H04-GA-VERSIONING pending Gate 4); phase80 node added to automation contract
- `docs/IP_PATENT_FILING_ARTIFACT.md` — Phase 80 Track B transmittal checklist + H-03 filing instructions appended

**HUMAN-0 gate actions (non-delegable — not included in this release):**
- Gate 3: F-Droid MR submission (Dustin)
- Gate 4: GPG v1.1-GA sign-off commit (Dustin)
- C-02: GPG tag ceremony v9.7.0–v9.10.0 (Dustin)
- H-03: Patent counsel engagement + provisional filing (Dustin)

### Metrics at v9.15.0
- Tests: 4,772+ passing (+24)
- Phases complete: 80
- Constitutional invariants: 27 (+4)
- Seed competition: population-level competitive epoch now operational

## [9.14.0] — 2026-03-20 — Phases 78 + 79 + Thesis

### Phase 78 — Production Signing Infrastructure + Aponi GitHub Feed + Doc Autosync

- **M78-01 Journal warm-cache** (`JOURNAL-CACHE-0`): 9 constitutional tests confirming O(n) append performance, tamper detection, and cross-instance isolation
- **M78-02 Autonomous Doc Sync** (`DOC-SYNC-VERSION-0`): `.github/workflows/docs-autosync.yml` triggers on VERSION/CHANGELOG/ROADMAP push; `scripts/verify_doc_sync.py` exits 1 on any version drift
- **Ed25519/HMAC production signers** (`LEDGER-SIGN-0`): `HMACEnvSigner` (ADAAD_LEDGER_HMAC_SECRET), `Ed25519FileSigner` (ADAAD_SIGNING_KEY_PATH), `build_signer_from_env()` priority factory. 21 tests
- **Aponi GitHub Feed Panel**: `data-view="github"` nav, `loadGithubFeed()` async, event-type-keyed CSS classes (push/pr/ci/slash/install/rejected), governance bridge fallback. 16 tests
- Total: 46 new tests

### Phase 79 — Multi-Generation Lineage Graph

- `runtime/evolution/multi_gen_lineage.py`: `GenerationNode` (frozen dataclass, `node_digest`), `MultiGenLineageGraph` (DAG: `register_node`, `ancestor_path`, `descendant_set`, `generation_summary`, `graph_digest`, `to_dict`, `from_ledger`)
- `MULTIGEN-0`: every node ledger-anchored; `MULTIGEN-ACYC-0`: DAG, cycles structurally impossible; `MULTIGEN-DETERM-0`: identical ledger → identical `graph_digest`; `MULTIGEN-REPLAY-0`: graph reconstructable from ledger alone; `MULTIGEN-ISOLATE-0`: no shared state
- Foundation for Phase 80 compound evolution
- 26 tests

### Thesis

- `docs/thesis/ADAAD_THESIS.md`: 500-line comprehensive technical thesis covering architecture, all 23 constitutional invariants, proven capabilities, operator model, current live state, and evolution trajectory

### Metrics at v9.14.0
- Tests: 4,748+ passing
- Phases complete: 79
- Constitutional invariants: 23
- Evidence ledger entries: 12,441+

## [9.13.0] — 2026-03-20 — Phase 77 Complete (Track A + Track B)

### Track A — Constitutional Governance Infrastructure (#PR-77-01)

- PR ID: `PR-77-01`
- Title: Close 4 constitutional stubs — ABC enforcement + webhook consolidation
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase77-track-a-abc-enforcement`, `phase77-webhook-shim-deleg-0`
- Closes: `FINDING-AUDIT-C03` remnant (dual webhook handler) + 3 `NotImplementedError` stubs
- Delivered:
  - `runtime/evolution/event_signing.py` — `EventSigner` / `EventVerifier` → proper ABC (`EVENT-SIGN-ABSTRACT-0`)
  - `runtime/innovations.py` — `GovernancePlugin.evaluate()` → proper ABC (`GPLUGIN-ABSTRACT-0`)
  - `runtime/fitness_pipeline.py` — `FitnessEvaluator` abstractmethod contract clarified
  - `runtime/integrations/github_webhook_handler.py` — replaced with governed shim delegating 100% to `app.github_app` (`WEBHOOK-SHIM-DELEG-0` / `WEBHOOK-SHIM-COMPAT-0`)
  - 26 constitutional closure tests (`tests/test_phase77_track_a_close.py`)
- Key invariants: `EVENT-SIGN-ABSTRACT-0`, `GPLUGIN-ABSTRACT-0`, `WEBHOOK-SHIM-DELEG-0`, `WEBHOOK-SHIM-COMPAT-0`

### Track B — First Seed Epoch Run (#PR-77-02)

- PR ID: `PR-77-02`
- Title: First Seed Epoch Run — SEED-LIFECYCLE-COMPLETE-0 demonstrated
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `artifacts/governance/phase77/seed_epoch_run_evidence.json`
- run_digest: `sha256:b3a41c40b99177dc51d5cfdd43d826c27aa7bf718f93fd936f7a5658869590ab`
- Milestone: **First live demonstration of end-to-end Seed Lifecycle Pipeline** (Phases 71–76)
- Delivered:
  - `scripts/run_phase77_seed_epoch.py` — reproducible 7-step pipeline executor
  - `artifacts/governance/phase77/seed_epoch_run_evidence.json` — inaugural `EpochEvidence` artifact
  - Full pipeline executed: `CapabilitySeed` → `SeedPromotionQueue` → human review → `ProposalRequest` → CEL injection → `LiveWiredCEL.run_epoch()` (14 steps) → `SeedCELOutcomeEvent`
  - 27 constitutional tests (`tests/test_phase77_track_b_seed_epoch.py`)
- Key invariants demonstrated: `SEED-LIFECYCLE-COMPLETE-0`, `SEED-PROMO-0`, `SEED-REVIEW-HUMAN-0`, `SEED-PROP-LEDGER-0`, `SEED-CEL-AUDIT-0`, `SEED-OUTCOME-AUDIT-0`, `CEL-ORDER-0`
- Total: 53 new tests | 150 passing across affected modules | 0 regressions
- Governor: Dustin L. Reid — 2026-03-20

## [9.12.1] — 2026-03-19 — Optimize: 7-Fault Sweep

- PR ID: `PR-508-OPTIMIZE-v9.12.1`
- Title: Optimize — 7-fault sweep (warm-cache regression · constitution version drift · import contracts · GitHub App wiring)
- Lane/Tier: `runtime` / `hotfix`
- Evidence refs: `optimize-warm-cache-lineage-v2`, `optimize-constitution-version-drift`, `optimize-import-contracts`, `optimize-github-app-wiring`
- Fixes:
  - `runtime/evolution/lineage_v2.py` — O(n→n²) warm-cache regression in `append_event()`; `_verified_tail_hash` now advanced post-append (C-04 contract)
  - `app/github_app.py` — governance event emission wiring completed
  - `app/main.py` — import contract alignment (5 modules)
  - Test suite: `test_lineage_v2_streaming`, `test_replay_attestation_determinism`, `test_constitution_*` — version constant sync
- Phase 78 note: Journal-level `_VERIFIED_TAIL_CACHE` (11.6× speedup, 1700ms→146ms) deferred — shared journal test-isolation pre-condition required first

## [9.12.0] — 2026-03-19 — Phase 77

- PR ID: `PR-PHASE77-01`
- Title: GitHub App Governance + Constitution Version Alignment
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase77-github-audit-bridge`, `phase77-external-event-bridge`, `phase77-constitution-version-0.9.0`
- Closes: `FINDING-AUDIT-C03` — `app/github_app.py` and `runtime/integrations/github_webhook_handler.py` governance gap
- Delivered:
  - `runtime/governance/external_event_bridge.py` — SHA-256 hash-chained JSONL audit ledger
  - `ExternalGovernanceSignal` emitted for mutation-class events (`push.main`, `pr.merged`, `ci.failure`)
  - `app/github_app._emit_governance_event` wired to bridge keyword API
  - `CONSTITUTION_VERSION` updated `"0.7.0"` → `"0.9.0"` in 3 runtime files + `constitution.yaml`
  - All 31 Phase-77 tests passing (T77-BRG-01..10, T77-SIG-01..06, T77-CHAIN-01..04, T77-WIRE-01..03, T77-CONST-01..03, T77-IDEM-01..02)
- Key invariants: `GITHUB-AUDIT-0`, `GITHUB-GATE-OBS-0`, `GITHUB-SIG-CLOSED-0`, `GITHUB-DETERM-0`, `GITHUB-FAILSAFE-0`, `GITHUB-GATE-ISO-0`

## [9.11.0] — 2026-03-15 — Phase 76

- PR ID: `PR-PHASE76-01`
- Title: Seed CEL Outcome Recorder
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.10.0] — 2026-03-14 — Phase 75

- PR ID: `PR-PHASE75-01`
- Title: Seed Proposal CEL Injection
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.9.0] — 2026-03-14 — Phase 74

- PR ID: `PR-PHASE74-01`
- Title: Seed-to-Proposal Bridge
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.8.0] — 2026-03-14 — Phase 73

- PR ID: `PR-PHASE73-01`
- Title: Seed Review Decision + Governance Wire
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.7.0] — 2026-03-14 — Phase 72

- PR ID: `PR-PHASE72-01`
- Title: Seed Promotion Queue + Graduation UI
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.6.0] — 2026-03-14 — Phase 71

- PR ID: `PR-PHASE71-01`
- Title: Oracle Persistence + Seed Evolution
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.5.0] — 2026-03-14 — Phase 70

- PR ID: `PR-PHASE70-01`
- Title: WebSocket Live Epoch Feed
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.4.0] — 2026-03-14 — Phase 69

- PR ID: `PR-PHASE69-01`
- Title: Aponi Innovations UI
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.3.0] — 2026-03-14 — Phase 68

- PR ID: `PR-PHASE68-01`
- Title: Full Innovations Orchestration
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.2.0] — 2026-03-14 — Phase 67

- PR ID: `PR-PHASE67-01`
- Title: Innovations Wiring (CEL)
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.1.0] — 2026-03-14 — Phase 66

- PR ID: `PR-PHASE66-01`
- Title: Doc Alignment + Deep Dive
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.0.0] — unknown-date — Phase 65

- PR ID: `PR-PHASE65-01`
- Title: Emergence — First Autonomous Capability Evolution
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase65-preflight-determinism-import-hardening`

## [8.7.0] — unknown-date — Phase 64

- PR ID: `PR-PHASE64-01`
- Title: Phase 64
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [8.6.0] — unknown-date — Phase 63

- PR ID: `PR-PHASE63-01`
- Title: Phase 63
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [8.5.0] — unknown-date — Phase 62

- PR ID: `PR-PHASE62-01`
- Title: Phase 62
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [8.4.0] — unknown-date — Phase 61

- PR ID: `PR-PHASE61-01`
- Title: Phase 61
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase61-ci-tier-gating-enforced`, `phase61-critical-file-budget-enforced`, `phase61-legacy-path-reduction-target`, `phase61-lineage-engine-v840`, `phase61-metrics-schema-coverage-100`, `phase61-runtime-cost-and-experiment-caps`

## [8.3.0] — unknown-date — Phase 60

- PR ID: `PR-PHASE60-01`
- Title: Phase 60
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase60-ast-mutation-substrate-sandbox-v830`

## [8.2.0] — unknown-date — Phase 59

- PR ID: `PR-PHASE59-01`
- Title: Phase 59
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase59-capability-graph-v2-v820`

## [8.1.0] — unknown-date — Phase 58

- PR ID: `PR-PHASE58-01`
- Title: Phase 58
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase58-code-intelligence-layer-v810`

## [8.0.0] — unknown-date — Phase 57

- PR ID: `PR-PHASE57-01`
- Title: Phase 57
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase57-proposal-engine-autoprovisioning`

## [7.5.0] — 2026-03-12 — Phase 51

- PR ID: `PR-PHASE51-01`
- Title: Phase 51
- Lane/Tier: `governance` / `standard`
- Evidence refs: _none_

## [7.4.0] — unknown-date — Phase 50

- PR ID: `PR-PHASE50-01`
- Title: Phase 50
- Lane/Tier: `governance` / `standard`
- Evidence refs: _none_

## [7.3.0] — 2026-03-12 — Phase 49

- PR ID: `PR-PHASE49-01`
- Title: Phase 49
- Lane/Tier: `governance` / `standard`
- Evidence refs: _none_

## [7.2.0] — 2026-03-12 — Phase 48

- PR ID: `PR-PHASE48-01`
- Title: Phase 48
- Lane/Tier: `governance` / `standard`
- Evidence refs: _none_

## [7.1.0] — 2026-03-12 — Phase 47

- PR ID: `PR-PHASE47-01`
- Title: Phase 47
- Lane/Tier: `governance` / `standard`
- Evidence refs: _none_
