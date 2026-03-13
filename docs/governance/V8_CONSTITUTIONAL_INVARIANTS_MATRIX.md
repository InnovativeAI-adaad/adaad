# ADAAD v8 Constitutional Invariants Matrix
## Phases 57–65 — Machine-Readable Invariant Registry

**Version:** v8.0.0  
**Date:** 2026-03-13  
**Authority:** ArchitectAgent  
**Status:** CONSTITUTIONAL DRAFT — HUMAN-0 applies at all gates

---

## Invariant Format

Each invariant entry is structured for deterministic evaluation:

```
ID:          Unique identifier (PHASE-CATEGORY-INDEX)
Statement:   Exact, unambiguous condition
Class:       Hard | Class-B-Eligible
Phase:       Originating phase
Gate:        Constitutional gate association (if any)
Failure:     Enumerated, non-silent failure state
Enforcement: Mechanism that evaluates this invariant
```

---

## Phase 57 — Proposal Auto-Provisioning

### PROP-AUTO-0
- **Statement:** ProposalEngine MUST NOT activate unless `ADAAD_ANTHROPIC_API_KEY` is present and validated against the Anthropic endpoint before the first epoch begins
- **Class:** Hard
- **Failure:** `PROP_ENGINE_ACTIVATION_BLOCKED` — epoch proceeds without LLM proposals; event logged to evidence ledger
- **Enforcement:** Startup check in EvolutionLoop.run_epoch() Phase 1e entry guard

### PROP-AUTO-1
- **Statement:** All LLM-generated proposals MUST enter the governed pipeline (PopulationManager → MutationRouteOptimizer → GovernanceGate); no bypass path exists at any layer
- **Class:** Hard
- **Failure:** `BYPASS_PATH_DETECTED` — constitutional violation; epoch halted; incident written to ledger
- **Enforcement:** Pipeline wiring audit; gate decision log cross-reference

### PROP-AUTO-2
- **Statement:** `strategy_id` in every proposal MUST be validated against `STRATEGY_TAXONOMY` before any LLM call; invalid strategy_id blocks the call
- **Class:** Hard
- **Failure:** `INVALID_STRATEGY_ID` — proposal dropped; validation error logged; no LLM call made
- **Enforcement:** Pre-call validation in ProposalAdapter

### PROP-AUTO-3
- **Statement:** ProposalEngine context MUST include `governance_debt_score`, `lineage_health`, `bandit_confidence`, `epoch_count` at minimum before any prompt assembly
- **Class:** Hard
- **Failure:** `CONTEXT_INCOMPLETE` — epoch aborts LLM path; fallback to non-LLM proposals
- **Enforcement:** Context builder pre-flight check

### PROP-AUTO-4
- **Statement:** ProposalEngine failure (API error, timeout, malformed response, network error) MUST be fail-closed: epoch proceeds without LLM proposals; no corrupted or partial proposals enter the pipeline
- **Class:** Hard
- **Failure:** `PROPOSAL_ENGINE_FAIL_CLOSED` — epoch continues on non-LLM path; failure recorded in EpochEvidence
- **Enforcement:** Exception handler wrapping all LLM calls; no partial result propagation

### PROP-AUTO-5
- **Statement:** LLM call count per epoch MUST be bounded; default bound is 3; bound is configurable only via governance YAML with ArchitectAgent approval; exceeding the bound is a hard block (not a soft limit)
- **Class:** Hard
- **Failure:** `LLM_CALL_BOUND_EXCEEDED` — additional calls blocked; event logged; remaining proposals generated non-LLM
- **Enforcement:** Call counter in ProposalEngine with hard ceiling

---

## Phase 58 — Code Intelligence

### INTEL-DET-0
- **Statement:** `CodeIntelModel.model_hash` MUST be identical for identical `CodeIntelModel` state across process restarts, reimports, and execution environments; hash is `sha256(json.dumps(model.__dict__, sort_keys=True, default=str))`
- **Class:** Hard
- **Failure:** `MODEL_HASH_NONDETERMINISTIC` — epoch aborted; determinism violation logged to ledger
- **Enforcement:** Determinism test suite; T58-INTEL-04

### INTEL-TS-0
- **Statement:** All timestamp fields in `CodeIntelModel` and its sub-dataclasses MUST use `RuntimeDeterminismProvider.now_utc()`; `datetime.now()`, `datetime.utcnow()`, `time.time()` are prohibited
- **Class:** Hard
- **Failure:** `NONDETERMINISTIC_TIMESTAMP` — StaticSafetyScanner NonDeterminismRule catches at scan time; hard reject
- **Enforcement:** Static analysis + T58-INTEL-06 (mock provider verification)

### INTEL-ISO-0
- **Statement:** `CodeIntelModel` and all sub-components of `runtime/mutation/code_intel/` MUST NOT write to governance paths, ledger paths, or any path governed by GovernanceGate; CodeIntelModel is advisory-only
- **Class:** Hard
- **Failure:** `INTEL_MODULE_BOUNDARY_VIOLATION` — constitutional violation; epoch halted; incident written to ledger
- **Enforcement:** Module boundary audit at PR review; integration test isolation checks

---

## Phase 59 — Capability Graph v2

### CAP-VERS-0
- **Statement:** Every CapabilityNode version bump (contract change, binding change, or governance_tag change) MUST produce a corresponding ledger entry before the epoch closes
- **Class:** Hard
- **Failure:** `CAPABILITY_VERSION_UNLEDGERED` — epoch evidence incomplete; capability rollback triggered; constitutional violation
- **Enforcement:** CapabilityEvolutionEngine post-update hook; EvidenceBundleBuilder validation

### CAP-DEP-0
- **Statement:** If `CapabilityNode.dependency_set` references a capability name not present in `CapabilityGraph.nodes`, a `ValueError` MUST be raised at load time; no silent missing dependency
- **Class:** Hard
- **Failure:** `CAPABILITY_DEPENDENCY_MISSING` — ValueError raised at graph load; startup aborted until resolved
- **Enforcement:** CapabilityGraph.__init__ validation loop

### CAP-TIER0-0
- **Statement:** Tier-0 capabilities (ConstitutionEnforcement, DeterministicReplay, LedgerEvidence, GovernanceGate) MUST carry `governance_tags: ['non_mutable']`; GovernanceGate MUST block any mutation whose `target_file` is in these capabilities' `bound_modules`
- **Class:** Hard
- **Failure:** `TIER0_MUTATION_ATTEMPT` — hard block before any LLM call; TIER0-SELF-0 incident recorded
- **Enforcement:** ProposalAdapter pre-check + GovernanceGate Tier-0 boundary rule

---

## Phase 60 — AST Mutation Substrate

### SANDBOX-DIV-0
- **Statement:** Post-apply test results MUST match sandbox test results exactly (same seed, same input); any divergence between sandbox outcome and post-apply outcome = automatic rejection + incident ledger entry + rollback
- **Class:** Hard
- **Failure:** `SANDBOX_DIVERGENCE_DETECTED` — mutation rolled back; incident written to ledger; alert emitted; GovernanceGate marks run as failed
- **Enforcement:** replay_verifier.py called post-apply for every approved mutation

### TIER0-SELF-0
- **Statement:** No `ASTDiffPatch` may specify a `target_file` that resolves to a Tier-0 module root or any file within a Tier-0 module's path; this check occurs before any LLM call in ProposalAdapter
- **Class:** Hard
- **Failure:** `TIER0_TARGET_BLOCKED` — proposal dropped; no LLM call made; event logged
- **Enforcement:** ProposalAdapter target_file pre-check against Tier-0 path registry

### PATCH-SIZE-0
- **Statement:** Any `ASTDiffPatch` with `node_count_delta > 40` OR `files_touched > 2` MUST be hard-rejected; no Exception Token available for patch size violations
- **Class:** Hard (no Class B path)
- **Failure:** `PATCH_SIZE_EXCEEDED` — proposal dropped at StaticSafetyScanner PatchSizeRule; no pipeline entry
- **Enforcement:** StaticSafetyScanner PatchSizeRule; thresholds in `config/governance/static_rules.yaml`

---

## Phase 61 — Lineage Engine

### LINEAGE-STAB-0
- **Statement:** A lineage MUST pass GovernanceGate in at least 2 of any 5 consecutive epochs to remain active; lineages that fail this criterion enter a 1-epoch cooling suspension; cooling is mandatory, not advisory
- **Class:** Hard
- **Failure:** `LINEAGE_COOLING_TRIGGERED` — lineage suspended for 1 epoch; event recorded in EpochEvidence governance_events; no proposals from cooling lineage during suspension
- **Enforcement:** LineageEngine post-epoch stability evaluator

### EPISTASIS-0
- **Statement:** Any mutation pair (A, B) where the combination A+B causes test regression that neither A alone nor B alone causes MUST be flagged as epistatic and blocked from co-application in the same epoch or lineage window
- **Class:** Hard
- **Failure:** `EPISTASIS_DETECTED` — both mutations held; epistasis record written to compatibility matrix; alert in governance_events
- **Enforcement:** Compatibility matrix recorder + LineageEngine co-application pre-check

---

## Phase 62 — Multi-Horizon Fitness Engine v2

### FIT-BOUND-0
- **Statement:** All individual fitness signal weights MUST be bounded to [0.05, 0.70]; composite score MUST be bounded to [0.0, 1.0]; any weight outside these bounds is a constitutional violation
- **Class:** Hard
- **Failure:** `FITNESS_WEIGHT_OUT_OF_BOUNDS` — epoch scoring halted; default weights restored; violation recorded
- **Enforcement:** Weight validation in FitnessEngine v2 initialiser and at every weight update

### FIT-DET-0
- **Statement:** Composite fitness score MUST be deterministic given identical sandbox results, CodeIntelModel state, and arithmetic inputs; non-determinism in scoring is a constitutional violation
- **Class:** Hard
- **Failure:** `FITNESS_NONDETERMINISM` — epoch aborted; determinism violation recorded in ledger
- **Enforcement:** T62-FIT-01..10 determinism test suite; parallel scoring cross-check

### FIT-DIV-0
- **Statement:** If `replay_verifier.py` reports any divergence for a mutation, that mutation's determinism fitness = 0.0 and the mutation MUST be rejected regardless of all other signal scores; this override cannot be excepted by any Exception Token
- **Class:** Hard (no Class B path)
- **Failure:** `REPLAY_DIVERGENCE_TOTAL_REJECTION` — mutation rejected; SANDBOX-DIV-0 incident recorded
- **Enforcement:** FitnessEngine v2 determinism signal integration; replay_verifier.py post-sandbox hook

### FIT-ARCH-0
- **Statement:** Architectural fitness signal MUST return exactly 0.5 (neutral) until Phase 62 is fully activated (feature flag `PHASE62_ARCH_SIGNAL=true`); a neutral score MUST NOT block any mutation that would otherwise pass
- **Class:** Hard
- **Failure:** `ARCH_SIGNAL_PREMATURE_BLOCK` — constitutional violation; epoch invalidated if architectural signal blocks pre-Phase-62 mutations
- **Enforcement:** Phase activation flag check in FitnessEngine v2 architectural signal path

---

## Phase 63 — GovernanceGate v2 + Exception Tokens

### AST-SAFE-0
- **Statement:** No mutation may produce an AST with syntax errors, `exec()`, `eval()`, or bare `os.system()` / `subprocess.call()` / `subprocess.run()` without a determinism wrapper; violation = hard reject
- **Class:** Hard (no Class B path)
- **Failure:** `AST_SAFETY_VIOLATION` — hard reject; no pipeline progression; event in GovernanceDecision rule_traces
- **Enforcement:** ASTNormalizer.validate_ast() in GovernanceGate v2

### AST-IMPORT-0
- **Statement:** No new imports from Tier-0 module roots are permitted in any mutation; import surface delta MUST be ≤ 0 for Tier-0-adjacent files; violation = hard reject
- **Class:** Hard (no Class B path)
- **Failure:** `IMPORT_BOUNDARY_VIOLATION` — hard reject; event in governance_events
- **Enforcement:** StaticSafetyScanner ImportBoundaryRule + RuntimeImportGuard

### AST-COMPLEX-0
- **Statement:** For any modified function, `cyclomatic_complexity_after` MUST be ≤ `cyclomatic_complexity_before + 2` for Class A approval; delta > 2 and ≤ 8 is Class B eligible with lineage projection and HUMAN-0; delta > 8 = hard reject
- **Class:** Class A (≤ +2) / Class B eligible (+3 to +8) / Hard reject (> +8)
- **Failure:** `COMPLEXITY_CEILING_EXCEEDED` (Class A) or `COMPLEXITY_CLASS_B_ELIGIBLE` (Class B) or `COMPLEXITY_HARD_REJECT` (> +8)
- **Enforcement:** StaticSafetyScanner ComplexityCeilingRule pre-sandbox; GovernanceGate v2 post-sandbox

### SEMANTIC-INT-0
- **Statement:** No mutation may remove a `try/except` block or error guard from any function without introducing a compensating handler in the same function or a directly-called callee function; violation = hard reject
- **Class:** Hard (no Class B path)
- **Failure:** `ERROR_GUARD_REMOVAL_UNCOMPENSATED` — hard reject; pattern recorded in rule_traces
- **Enforcement:** GovernanceGate v2 AST visitor; node deletion vs insertion pattern matcher

### EXCEP-SCOPE-0
- **Statement:** Exception tokens MUST be scoped to exactly one capability_name and exactly one rule_id; no blanket exceptions covering multiple capabilities or rules are permitted; Tier-0 capabilities are permanently ineligible for exception tokens
- **Class:** Hard
- **Failure:** `EXCEPTION_TOKEN_SCOPE_VIOLATION` — token rejected; exception not granted; alert to human maintainer
- **Enforcement:** ExceptionToken constructor validation

### EXCEP-HUMAN-0
- **Statement:** HUMAN-0 MUST be obtained and `human_approval_ref` recorded before any exception token is granted for Tier-1 capabilities; no automated exception token grant without human co-signature
- **Class:** Hard
- **Failure:** `EXCEPTION_TOKEN_WITHOUT_HUMAN_APPROVAL` — constitutional violation; token rejected; incident recorded
- **Enforcement:** HumanApprovalGate integration in CapabilityGovernanceGate.request_exception()

### EXCEP-TTL-0
- **Statement:** Exception tokens MUST expire at most 3 epochs from `granted_at_epoch`; tokens are non-renewable without a new human gate; expired tokens are automatically invalidated and may not be re-used
- **Class:** Hard
- **Failure:** `EXCEPTION_TOKEN_EXPIRED` — token invalidated; any mutation attempting to use it is rejected; expiry event recorded in ExceptionTokenLedger
- **Enforcement:** Token lifecycle manager; epoch counter check at every token use

### EXCEP-REVOKE-0
- **Statement:** Auto-revocation of exception tokens MUST occur immediately on any trigger condition (lineage diverges, target capability contract changes, test failure rate exceeds threshold, epoch window expires); no grace period; revocation is permanent for that token
- **Class:** Hard
- **Failure:** `EXCEPTION_TOKEN_AUTO_REVOKED` — token invalidated immediately; revocation event recorded; ongoing Class B mutation blocked
- **Enforcement:** ExceptionTokenLedger monitor; trigger condition evaluator at each epoch

### GATE-V2-EXISTING-0
- **Statement:** All 16 existing GovernanceGate rules MUST continue to evaluate first, in their current order, unchanged; the 5 new Phase 63 rules are additive only and evaluate after the existing 16; no existing rule may be weakened or removed in Phase 63
- **Class:** Hard
- **Failure:** `EXISTING_GATE_RULE_MODIFIED` — constitutional violation; epoch halted; PR blocked
- **Enforcement:** Rule count and order audit in GovernanceGate v2 integration tests

---

## Phase 64 — Constitutional Evolution Loop

### CEL-ORDER-0
- **Statement:** The 14 CEL steps MUST execute in strict sequence (Step 1 → Step 14); no step may be skipped; no step may execute out of order; a failure in any step halts the epoch at that step
- **Class:** Hard
- **Failure:** `CEL_STEP_OUT_OF_ORDER` or `CEL_STEP_SKIPPED` — epoch halted; event recorded; no EpochEvidence written for incomplete epochs
- **Enforcement:** Step sequencer with numbered guards; integration tests T64-CEL-01..12

### CEL-EVIDENCE-0
- **Statement:** Every CEL epoch that completes Step 14 MUST produce exactly one `EpochEvidence` record; an epoch without a corresponding EpochEvidence record is constitutionally invalid and must be flagged for replay
- **Class:** Hard
- **Failure:** `EPOCH_EVIDENCE_MISSING` — epoch marked invalid; replay triggered; alert to human maintainer
- **Enforcement:** EvidenceBundleBuilder post-epoch validation; ledger completeness check

### CEL-HASH-0
- **Statement:** Every `EpochEvidence.predecessor_hash` MUST equal the hash of the immediately preceding `EpochEvidence` record in the ledger; a broken chain is a constitutional violation requiring immediate halt and audit
- **Class:** Hard
- **Failure:** `EVIDENCE_CHAIN_BROKEN` — epoch halted; constitutional violation alert; no further epochs until chain is audited and resolved
- **Enforcement:** Hash chain validator in EvidenceBundleBuilder; called at every write

### CEL-TS-0
- **Statement:** All `EpochEvidence` timestamp fields MUST use `RuntimeDeterminismProvider.now_utc()`; `datetime.now()` or any non-provider timestamp in EpochEvidence is a constitutional violation
- **Class:** Hard
- **Failure:** `NONDETERMINISTIC_EVIDENCE_TIMESTAMP` — evidence record rejected; epoch marked invalid
- **Enforcement:** EvidenceBundleBuilder timestamp source validation

---

## Summary Table — All v8 Invariants

| ID | Phase | Class | Has Exception Path |
|----|-------|-------|--------------------|
| PROP-AUTO-0 | 57 | Hard | No |
| PROP-AUTO-1 | 57 | Hard | No |
| PROP-AUTO-2 | 57 | Hard | No |
| PROP-AUTO-3 | 57 | Hard | No |
| PROP-AUTO-4 | 57 | Hard | No |
| PROP-AUTO-5 | 57 | Hard | No |
| INTEL-DET-0 | 58 | Hard | No |
| INTEL-TS-0 | 58 | Hard | No |
| INTEL-ISO-0 | 58 | Hard | No |
| CAP-VERS-0 | 59 | Hard | No |
| CAP-DEP-0 | 59 | Hard | No |
| CAP-TIER0-0 | 59 | Hard | No |
| SANDBOX-DIV-0 | 60 | Hard | No |
| TIER0-SELF-0 | 60 | Hard | No |
| PATCH-SIZE-0 | 60 | Hard | No |
| LINEAGE-STAB-0 | 61 | Hard | No |
| EPISTASIS-0 | 61 | Hard | No |
| FIT-BOUND-0 | 62 | Hard | No |
| FIT-DET-0 | 62 | Hard | No |
| FIT-DIV-0 | 62 | Hard | No |
| FIT-ARCH-0 | 62 | Hard | No |
| AST-SAFE-0 | 63 | Hard | No |
| AST-IMPORT-0 | 63 | Hard | No |
| AST-COMPLEX-0 | 63 | Class A / Class B | Class B: HUMAN-0 + lineage projection required |
| SEMANTIC-INT-0 | 63 | Hard | No |
| EXCEP-SCOPE-0 | 63 | Hard | No |
| EXCEP-HUMAN-0 | 63 | Hard | No |
| EXCEP-TTL-0 | 63 | Hard | No |
| EXCEP-REVOKE-0 | 63 | Hard | No |
| GATE-V2-EXISTING-0 | 63 | Hard | No |
| CEL-ORDER-0 | 64 | Hard | No |
| CEL-EVIDENCE-0 | 64 | Hard | No |
| CEL-HASH-0 | 64 | Hard | No |
| CEL-TS-0 | 64 | Hard | No |

**Total new invariants:** 34  
**Hard (no exception):** 33  
**Class B eligible:** 1 (AST-COMPLEX-0, requires HUMAN-0)

---

*ArchitectAgent · InnovativeAI-adaad/ADAAD · v8.0.0 · 2026-03-13*
