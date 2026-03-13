# ADAAD Architect Spec — v8.0.0
## Constitutional Autonomous Software Evolution — Phases 57–65

**Status:** NON-CANONICAL FORWARD DRAFT (DO NOT USE AS ACTIVE GOVERNANCE SOURCE)  
**Date:** 2026-03-13  
**Author:** ArchitectAgent · InnovativeAI-adaad/ADAAD  
**Supersedes:** ARCHITECT_SPEC_v3.1.0.md (for Phases 57–65)  
**Version span:** v8.0.0 (Phase 57) → v9.0.0 (Phase 65)

> **HUMAN-0 applies at every constitutional gate. No implementation PR opens without prior human sign-off.**

---

## 1. Document Scope and Authority

This document is a forward-looking constitutional draft for ADAAD Phases 57–65. It is not the active canonical governance specification. The canonical governance spec remains `docs/governance/ARCHITECT_SPEC_v3.1.0.md` until a governance-controlled cutover explicitly updates manifest + validators in the same change set. This draft defines:

- All new architectural components (organs)
- All new invariants and governance rules
- All constitutional gates requiring human sign-off
- All acceptance criteria, test suites, and dependency chains
- The Constitutional Evolution Loop (CEL) unified lifecycle

This spec is machine-readable, audit-ready, and deterministic. No ambiguity is permitted.

---

## 2. The Organism — Eight Evolutionary Layers

ADAAD v8 is structured as a living organism. Each phase unlocks a new organ. The organism cannot function without any one organ — the sequence is load-bearing, not cosmetic.

| Phase | Layer | Organ | Version | Key Unlock |
|-------|-------|-------|---------|------------|
| 57 | Keystone | Brainstem (Proposals) | v8.0.0 | LLM proposals default-on; perception↔proposal bridge active |
| 58 | Perception | Code Intelligence | v8.1.0 | ADAAD knows where it is fragile, slow, and complex |
| 59 | Identity | Capability Graph v2 | v8.2.0 | ADAAD thinks in behaviors, not files |
| 60 | Motor | AST Mutation Substrate | v8.3.0 | ADAAD produces real code diffs governed by constitution |
| 61 | Evolution | Lineage Engine | v8.4.0 | Multi-step refactors; valley crossing; epistasis protection |
| 62 | Intelligence | Multi-Horizon Fitness | v8.5.0 | Long-term architecture fitness; anti-myopia |
| 63 | Judgment | GovernanceGate v2 + Exception Tokens | v8.6.0 | Temporary complexity exceptions for multi-step evolution |
| 64 | Selfhood | Constitutional Evolution Loop (CEL) | v8.7.0 | Unified governed loop; EpochEvidence; replay-verifiable |
| 65 | Emergence | First Autonomous Capability Evolution | v9.0.0 | First end-to-end governed code improvement without human authorship |

**Metaphor mapping (operationally precise):**

- DNA = MutationCandidate + ASTDiffPatch (Phase 60)
- Perception = CodeIntelModel + extractors (Phase 58)
- Identity = CapabilityGraph v2 with contracts (Phase 59)
- Motor = AST mutation pipeline + SandboxTournament (Phase 60)
- Evolution = LineageEngine + compatibility graph (Phase 61)
- Intelligence = Multi-horizon fitness signals (Phase 62)
- Immune system = GovernanceGate v2 + Exception Tokens (Phase 63)
- Memory = EpochMemoryStore + MutationHistory + EvidenceBundle (Phase 64)
- Metabolism = Epoch lifecycle (existing EvolutionLoop)

---

## 3. Phase 57 — Keystone (ProposalEngine Auto-Provisioning)

### 3.1 Purpose

Phase 57 activates ProposalEngine auto-provisioning. It is the synapse between perception and action. Every phase after it inherits this connection.

**Before Phase 57:** ADAAD produces all the machinery but uses it in disconnected fragments.

**After Phase 57:**
- ProposalEngine is default-on when `ADAAD_ANTHROPIC_API_KEY` is present
- Phase 1e in `EvolutionLoop.run_epoch()` fires every epoch with live strategy context
- LLM generates proposals informed by `governance_debt_score`, `lineage_health`, `bandit_confidence`, `epoch_count` — all existing Phase 14–15 signals
- All proposals enter the same governed pipeline: PopulationManager → MutationRouteOptimizer → GovernanceGate — no bypass

### 3.2 Constitutional Invariants

| ID | Statement | Class | Enforcement |
|----|-----------|-------|-------------|
| PROP-AUTO-0 | ProposalEngine MUST NOT activate unless `ADAAD_ANTHROPIC_API_KEY` is present and validated | Hard | startup check; fail-closed |
| PROP-AUTO-1 | All LLM-generated proposals MUST enter the governed pipeline (PopulationManager → GovernanceGate); no bypass path exists | Hard | pipeline wiring; gate audit |
| PROP-AUTO-2 | strategy_id in every proposal MUST be validated against STRATEGY_TAXONOMY before any LLM call | Hard | pre-call validation |
| PROP-AUTO-3 | ProposalEngine context fields MUST include `governance_debt_score`, `lineage_health`, `bandit_confidence`, `epoch_count` at minimum | Hard | context builder |
| PROP-AUTO-4 | ProposalEngine failure (API error, timeout, malformed response) MUST be fail-closed: epoch proceeds without LLM proposals, not with corrupted ones | Hard | error handler |
| PROP-AUTO-5 | LLM call count per epoch MUST be bounded (default: 3); bound configurable via governance YAML; exceeding bound is a hard block | Hard | call counter |

### 3.3 Gate

**SPEC-57 gate:** `HUMAN-0` — ADAAD_Phase57_Spec.docx reviewed and approved; PROP-AUTO-0..5 accepted.

**Acceptance criteria:** T57-AP-01..12 pass; 0 regressions against 3,960 baseline tests.

**Version:** v8.0.0

---

## 4. Phase 58 — Perception (Code Intelligence Layer)

### 4.1 Purpose

ADAAD gains a self-model. It stops mutating blindly. For the first time the system knows where it is fragile, slow, and complex — and can direct ProposalEngine to those targets.

### 4.2 New Module: `runtime/mutation/code_intel/`

**Inputs:** Repo tree, EpochMemoryStore, sandbox profiling data

**Outputs:** Updated `CodeIntelModel`, `model_hash`

**Components:**

| File | Responsibility |
|------|----------------|
| `model.py` | `FunctionGraph`, `HotspotMap`, `MutationHistory`, `CodeIntelModel` dataclasses |
| `extractors/static_graph.py` | `ast.walk()`-based function graph extraction; deterministic traversal; cyclomatic complexity via existing SemanticDiffEngine algorithm |
| `extractors/runtime_hotspots.py` | Consumes profiling dict from Phase 60 sandbox benchmark harness; updates HotspotMap |
| `targets.py` | `TargetDiscovery`: `hotspot_targets()`, `fragility_targets()`; returns sorted `EvolutionTarget` list |

**Determinism invariants (non-negotiable):**

- All timestamp fields use `RuntimeDeterminismProvider.now_utc()` — never `datetime.now()`
- `model_hash = sha256(json.dumps(model.__dict__, sort_keys=True, default=str))`
- `MutationHistory` bridge: `EpochMemoryStore` (existing Phase 52) provides signal via adapter; no EpochMemoryStore changes required

### 4.3 ProposalEngine Context Enrichment

At epoch start, `CapabilityTargetDiscovery` (Phase 59) maps function-level targets → capability-level targets → ProposalEngine context:

```
_engine_context = {
    # existing Phase 14-15 fields (unchanged)
    'mutation_score': ..., 'governance_debt_score': ...,
    # new Phase 58 fields
    'capability_target': target.capability_name,
    'hotspot_functions': [f.function_name for f in target.functions],
    'fragility_signals': {fn: success_rate ...},
}
```

### 4.4 Constitutional Invariants

| ID | Statement | Class | Enforcement |
|----|-----------|-------|-------------|
| INTEL-DET-0 | `model_hash` MUST be identical for identical `CodeIntelModel` state across process restarts | Hard | determinism test suite |
| INTEL-TS-0 | All `CodeIntelModel` timestamps MUST use `RuntimeDeterminismProvider.now_utc()` | Hard | static analysis + tests |
| INTEL-ISO-0 | `CodeIntelModel` MUST NOT write to governance or ledger paths — advisory only | Hard | module boundary audit |

### 4.5 Acceptance Criteria

Tests T58-INTEL-01..12:
- FunctionGraph construction from real ADAAD source files
- HotspotMap update from profiling data
- MutationHistory bridge from EpochMemoryStore entries
- `model_hash` determinism: same model → same hash across process restarts
- TargetDiscovery produces sorted, de-duplicated targets
- All timestamps use `RuntimeDeterminismProvider` (mock provider in tests)

**Blocks on:** Phase 57 at main  
**Human gate:** None (implementation gate only)

---

## 5. Phase 59 — Identity (Capability Graph v2)

### 5.1 Purpose

ADAAD stops thinking in files and functions. It now reasons about capabilities — the behaviors it provides. The existing `runtime/capability_graph.py` is promoted from a score registry to a full Capability Layer.

### 5.2 CapabilityNode v2 — New Fields

| Field | Type | Constraint |
|-------|------|------------|
| `contract` | `CapabilityContract` | inputs (dict), outputs (dict), invariants (list[str]), determinism_required (bool) |
| `version` | str | semantic version; bumped on any contract or binding change |
| `governance_tags` | list[str] | includes `'tier_0_adjacent'`, `'requires_human_review'`, `'non_mutable'` |
| `telemetry` | `CapabilityTelemetry` | latency_ms, success_rate, error_rate; updated by FitnessEngine v2 |
| `bound_modules` | list[str] | Tier-1 file paths that implement this capability |
| `dependency_set` | frozenset[str] | names of dependent CapabilityNodes; missing deps raise ValueError at load time |

### 5.3 CapabilityTargetDiscovery

| Method | Input Signals | Output / Logic |
|--------|---------------|----------------|
| `hotspot_targets(n=5)` | HotspotMap.top(10) | CapabilityTarget per top-n hotspot functions, mapped to capability via binding_map. Priority = runtime_percent |
| `fragility_targets(threshold=0.3)` | MutationHistory.success_rate per function | CapabilityTarget for capabilities whose bound functions have mutation success rate < threshold. Priority = 1 - success_rate |
| `architectural_targets()` | FunctionGraph coupling/centrality; LineageDAG stability | Returns empty list until Phase 62 active |
| `discover(K=5)` | All three target lists | Merges, de-duplicates by capability_name (max priority wins), sorts descending. Returns top-K |
| `_map_function_to_capability(fn_name)` | capability_binding_map: Dict[str, list[str]] | Reverse lookup; built once at epoch start from CapabilityGraph bound_modules |

### 5.4 First 10 Capabilities (Constitutional Registry)

| Capability | Tier | ADAAD Anchor Module | Primary Contract Invariant |
|------------|------|---------------------|---------------------------|
| ConstitutionEnforcement | 0 — immutable | `runtime/governance/gate.py` | No mutation may bypass or weaken governance evaluation |
| DeterministicReplay | 0 — immutable | `runtime/evolution/replay_verifier.py` | Identical inputs + seed → identical outputs; zero replay divergence |
| LedgerEvidence | 0 — immutable | `runtime/evolution/evidence_bundle.py` | All ledger entries are hash-chained; no retroactive modification |
| GovernanceGate | 0 — immutable | `runtime/governance/gate.py` | Sole promotion authority; no bypass path |
| MutationProposal | 1 — governed-mutable | `runtime/evolution/proposal_engine.py` | Proposals must pass strategy_id validation before any LLM call |
| SandboxExecution | 1 — governed-mutable | `runtime/sandbox/executor.py` | Execution is deterministic; no external network; ephemeral isolation |
| FitnessEvaluation | 1 — governed-mutable | `runtime/evolution/fitness_v2.py` | Scores are advisory only; bounded [0.0, 1.0]; deterministic given inputs |
| StrategySelection | 1 — governed-mutable | `runtime/intelligence/strategy.py` | strategy_id constrained to STRATEGY_TAXONOMY; unknown IDs blocked |
| CodeIntelligence | 1 — governed-mutable | `runtime/mutation/code_intel/` (Phase 58) | Model is advisory only; does not write to governance or ledger paths |
| EpochMemory | 1 — governed-mutable | `runtime/autonomy/epoch_memory_store.py` | Store is append-only within rolling window; SHA-256 hash-chained |

### 5.5 Constitutional Invariants

| ID | Statement | Class | Enforcement |
|----|-----------|-------|-------------|
| CAP-VERS-0 | Every CapabilityNode version bump MUST produce a ledger entry | Hard | CapabilityEvolutionEngine |
| CAP-DEP-0 | Missing dependency_set entries MUST raise ValueError at load time | Hard | load-time validation |
| CAP-TIER0-0 | Tier-0 capabilities MUST carry `governance_tags: ['non_mutable']`; GovernanceGate blocks any mutation targeting their bound_modules | Hard | gate pre-check |

### 5.6 Gate

**CAP-REGISTRY gate:** `HUMAN-0` — First 10 capability contracts reviewed; bound_modules correct; governance_tags verified.

**Acceptance criteria:** T59-CAP-01..10; first 10 capabilities in registry with contracts validated.

**Blocks on:** Phase 58 at main

---

## 6. Phase 60 — Motor (AST Mutation Substrate + Sandbox)

### 6.1 Purpose

ADAAD gains the ability to produce real, governed, AST-level code modifications. Two components are delivered together because the sandbox is required to validate the AST substrate safely.

### 6.2 ASTDiffPatch — The DNA

**New dataclass:**

| Field | Type | Constraint |
|-------|------|------------|
| `before_source` | str \| None | Source before mutation |
| `after_source` | str | Source after mutation |
| `before_ast_hash` | sha256 | `sha256(ast.dump(ast.parse(before_source)))` — formatting-invariant |
| `after_ast_hash` | sha256 | `sha256(ast.dump(ast.parse(after_source)))` — formatting-invariant |
| `mutation_kind` | enum | `insert_function \| modify_logic \| refactor_block \| optimize_loop \| delete_dead_code` |
| `target_file` | str | Tier-1 path only; Tier-0 paths hard-blocked |
| `node_count_delta` | int | Bounded by PatchSizeRule |
| `files_touched` | int | Bounded by PatchSizeRule |

`MutationCandidate` gains: `ast_patch: ASTDiffPatch | None = None` (keyword-optional; all existing constructors unchanged)

**TIER0-SELF-0 enforced:** `target_file` pre-checked against Tier-0 path list before any LLM call in ProposalAdapter.

### 6.3 StaticSafetyScanner

**Module:** `runtime/mutation/static_scanner.py` — runs before SandboxTournament; fail-closed

| Rule | Statement | Class | Enforcement |
|------|-----------|-------|-------------|
| ImportBoundaryRule | AST import visitor; blocks any import targeting Tier-0 roots | Hard | pre-sandbox |
| NonDeterminismRule | Detects `random`, `time.time()`, `datetime.now()`, `uuid.uuid4()` without determinism provider | Hard | pre-sandbox |
| ComplexityCeilingRule | cyclomatic delta > 2 → Class A rejection; delta > 8 → hard rejection | Class B eligible for delta ≤ 8 | pre-sandbox |
| PatchSizeRule | node_count_delta > 40 OR files_touched > 2 → hard rejection | Hard | pre-sandbox |

All thresholds in `config/governance/static_rules.yaml` — configurable, governed.

### 6.4 SandboxTournament

**Module:** `runtime/mutation/sandbox_tournament.py`

**Ephemeral clone:** `runtime/sandbox/ephemeral_clone.py` — tmpfs copy of repo; patch applied atomically; tests run; torn down. No git operations.

**LibCST:** Introduced at Phase 60 for Tier-1 patch application (preserves comments, formatting, whitespace).

**Benchmark harness:** `timeit` wrappers injected around HotspotMap-identified functions; provides performance delta signal to FitnessEngine v2.

**Feature flag:** `MUTATION_SANDBOX_ONLY=true` — no real repo writes during Phase 60 stabilisation.

**Post-approval replay check:** `replay_verifier.py` (existing) confirms post-apply test results match sandbox results exactly (SANDBOX-DIV-0).

### 6.5 Constitutional Invariants

| ID | Statement | Class | Enforcement |
|----|-----------|-------|-------------|
| SANDBOX-DIV-0 | Post-apply test results MUST match sandbox results exactly (same seed). Any divergence = automatic rejection + incident ledger entry | Hard | replay_verifier.py |
| TIER0-SELF-0 | No ASTDiffPatch may target a Tier-0 file path; pre-check occurs before any LLM call | Hard | ProposalAdapter pre-check |
| PATCH-SIZE-0 | node_count_delta > 40 OR files_touched > 2 → hard rejection; no exception token available | Hard | StaticSafetyScanner |

### 6.6 Acceptance Criteria

Tests T60-AST-01..15: MUTATION_SANDBOX_ONLY tests pass; SANDBOX-DIV-0 verified.

**Blocks on:** Phase 59 at main  
**Human gate:** None

---

## 7. Phase 61 — Evolution (Lineage Engine)

### 7.1 Purpose

Individual mutation approval stalls evolutionary systems. Phase 61 introduces lineage tracking — the ability to evaluate mutation sequences over time, not just single candidates.

### 7.2 Lineage Architecture

**Module:** `runtime/evolution/lineage_dag.py` — extended with mutation compatibility tracking

**Compatibility matrix:** After each epoch, co-occurring mutations (A applied before B) are recorded. If A+B causes test regression that A alone and B alone do not, epistasis is flagged.

**LineageSurvival scoring:** A lineage survives if it passes governance in at least 2 of any 5 consecutive epochs. Failed lineages enter cooling (1-epoch suspension). Governed by LINEAGE-STAB-0.

**Mutation niches (speciation):** 5 independent bandit instances within StrategyBrain v2: performance, architecture, safety, simplicity, experimental. Cross-niche breeding: top candidate from two niches combined into a hybrid candidate.

**Lineage evidence record:** `EpochEvidence.capability_changes` carries `from_version` and `to_version` per capability — multi-epoch lineage reconstructable from ledger alone.

### 7.3 Multi-Step Refactor Protocol (Valley-Crossing)

Valley-crossing requires temporarily worsening metrics before improving them. Without a protocol, GovernanceGate blocks step 1.

1. **Lineage simulation:** Before any Class B mutation is proposed, the system simulates the next 3 epochs with the mutation applied. If net fitness improves, the mutation is Class B eligible.
2. **Exception Token requested:** CapabilityGovernanceGate grants ExceptionToken (Phase 63) scoped to the capability, rule AST-COMPLEX-0, and a 3-epoch window.
3. **Human gate:** HUMAN-0 required — human co-signs the exception via HumanApprovalGate (existing module). Exception token includes `human_approval_ref`.
4. **Execution:** Class B mutation applied; lineage tracked; exception auto-revokes after 3 epochs or on instability trigger.

### 7.4 Constitutional Invariants

| ID | Statement | Class | Enforcement |
|----|-----------|-------|-------------|
| LINEAGE-STAB-0 | A lineage must pass governance in ≥ 2 of any 5 consecutive epochs to remain active; failed lineages enter 1-epoch cooling | Hard | LineageEngine post-epoch |
| EPISTASIS-0 | Any mutation combination that produces test regression when A+B but not A alone or B alone MUST be flagged as epistatic and blocked from co-application | Hard | compatibility matrix |

### 7.5 Acceptance Criteria

Tests T61-LIN-01..12: Epistasis detection test cases; lineage survival scoring; cooling period enforcement.

**Blocks on:** Phase 60 at main  
**Human gate:** None

---

## 8. Phase 62 — Intelligence (Multi-Horizon Fitness Engine v2)

### 8.1 Purpose

Phase 62 replaces synthetic scoring with real, multi-horizon fitness signals. Directly solves the Local Fitness Trap: without long-horizon signals, the system optimises performance at the cost of architecture.

### 8.2 Signal Architecture

| Signal | Weight | Horizon | ADAAD Source |
|--------|--------|---------|--------------|
| Test fitness (coverage delta, failure reduction) | 30% | Short / per-epoch | SandboxTournament test harness; existing coverage hooks in HardenedSandboxExecutor |
| Complexity fitness (cyclomatic delta) | 20% | Short | SemanticDiffEngine.diff() cyclomatic_delta (existing; Phase 4) |
| Performance fitness (benchmark delta) | 15% | Short | Benchmark harness (Phase 60) + HotspotMap (Phase 58) |
| Governance compliance (rolling pass rate) | 15% | Medium / 10-epoch window | EpochMemoryStore stats (Phase 52) + GovernanceGate decision ledger |
| Architectural fitness (coupling, centrality) | 12% | Long / 20-epoch window | FunctionGraph centrality (Phase 58) + LineageDAG coupling (Phase 61). Returns 0.5 (neutral) until Phase 62 active |
| Determinism fitness (replay divergence = 0) | 8% | Hard floor / per-epoch | replay_verifier.py (existing); SANDBOX-DIV-0. Any divergence = total rejection regardless of other scores |
| Code pressure (deletion bonus) | −5% on net additions | Short | ASTDiffPatch.node_count_delta; negative fitness per net positive node count — prevents bloat |

### 8.3 Constitutional Invariants

| ID | Statement | Class | Enforcement |
|----|-----------|-------|-------------|
| FIT-BOUND-0 | All signal weights bounded to [0.05, 0.70]; composite score bounded to [0.0, 1.0] | Hard | weight validation |
| FIT-DET-0 | Composite score MUST be deterministic given identical inputs | Hard | determinism test suite |
| FIT-DIV-0 | Determinism fitness = 0 on any replay divergence; this overrides all other signals; mutation is total rejection | Hard | replay_verifier.py integration |
| FIT-ARCH-0 | Architectural fitness signal returns 0.5 (neutral) until Phase 62 is fully active; it MUST NOT block mutations before activation | Hard | phase activation flag |

### 8.4 Acceptance Criteria

Tests T62-FIT-01..10: All 7 signal sources active; composite score deterministic; bounded weights verified.

**Blocks on:** Phase 61 at main  
**Human gate:** None

---

## 9. Phase 63 — Judgment (GovernanceGate v2 + Exception Tokens)

### 9.1 Purpose

GovernanceGate v2 extends the existing 16-rule gate with diff-aware rules and introduces Exception Tokens — time-bounded, capability-scoped constitutional relief that allows evolutionary valley-crossing without compromising governance integrity.

### 9.2 GovernanceGate v2 — Five New Rules

All existing 16 rules are unchanged and continue to evaluate first.

| Rule ID | Statement | Class B Eligible | Enforcement |
|---------|-----------|------------------|-------------|
| AST-SAFE-0 | No mutation may produce AST with syntax errors, exec/eval, or bare os.system/subprocess without determinism wrapper | No | ASTNormalizer.validate_ast(); hard reject |
| AST-IMPORT-0 | No new imports from Tier-0 module roots. Import surface delta ≤ 0 for Tier-0-adjacent files | No | StaticSafetyScanner ImportBoundaryRule + RuntimeImportGuard |
| AST-COMPLEX-0 | Modified function: cyclomatic_after ≤ cyclomatic_before + 2. Class B exception available with lineage projection + human gate | Yes (max +8, 3-epoch window) | StaticSafetyScanner pre-sandbox; GovernanceGate v2 post-sandbox |
| SANDBOX-DIV-0 | Post-apply test results must match sandbox results exactly (same seed). Any divergence = automatic rejection + incident ledger entry | No | replay_verifier.py post-apply |
| SEMANTIC-INT-0 | No mutation may remove a try/except block or error guard without introducing a compensating handler in the same or callee scope | No | GovernanceGate v2 AST visitor; pattern match on node deletion vs insertion |

### 9.3 Exception Token Schema

| Field | Type | Constraint | Purpose |
|-------|------|------------|---------|
| `token_id` | sha256 hex | `sha256(epoch_id + capability_name + rule_id + scope_hash)` | Deterministic, non-guessable token identity |
| `capability_name` | str | Must be in CapabilityGraph.nodes; Tier-0 capabilities ineligible | Scopes exception to a single capability — no blanket exceptions |
| `rule_id` | str | Must be `AST-COMPLEX-0` only (Phase 63 scope) | Only complexity ceiling can be excepted |
| `granted_at_epoch` | str | Epoch ID of grant; recorded in EpochEvidence.exception_tokens_used | Audit trail |
| `expires_at_epoch` | int | Max 3 epochs from grant; non-renewable without new human gate | Prevents permanent governance bypass |
| `lineage_projection` | list[float] | Fitness projections for epochs +1, +2, +3 from lineage simulation | Exception only granted if projection shows net improvement |
| `human_approval_ref` | str \| None | Required for Tier-1 capabilities; human gate ref from HumanApprovalGate | HUMAN-0 preserved |
| `revocation_trigger` | str | auto-revoke conditions: lineage diverges, target capability changes, test failure rate > threshold | Exception auto-revokes on instability |

### 9.4 Exception Token Lifecycle

1. GovernanceGate evaluates mutation: fitness below baseline but lineage simulation passes → sets `class_b_eligible=True` on `GovernanceDecision`
2. `CapabilityGovernanceGate.request_exception(decision, lineage_projection)` — builds ExceptionToken; routes to HumanApprovalGate (existing module)
3. Human co-signs via HUMAN-0 workflow; `human_approval_ref` stored in token
4. Token written to `ExceptionTokenLedger` (new append-only JSONL in `data/exception_tokens.jsonl`)
5. Mutation executes under exception; every `EpochEvidence` record during exception window includes `exception_tokens_used` list
6. Auto-revocation triggers: lineage diverges, target capability contract changes, test failure rate exceeds threshold, or epoch window expires

### 9.5 Constitutional Invariants

| ID | Statement | Class | Enforcement |
|----|-----------|-------|-------------|
| EXCEP-SCOPE-0 | Exception tokens MUST be scoped to a single capability and a single rule; no blanket exceptions; Tier-0 capabilities ineligible | Hard | token constructor |
| EXCEP-HUMAN-0 | HUMAN-0 MUST be obtained before any exception token is granted for Tier-1 capabilities | Hard | HumanApprovalGate |
| EXCEP-TTL-0 | Exception tokens expire at most 3 epochs from grant; non-renewable without new human gate | Hard | token lifecycle manager |
| EXCEP-REVOKE-0 | Auto-revocation MUST occur silently and immediately on any trigger condition; no grace period | Hard | ExceptionTokenLedger monitor |
| GATE-V2-EXISTING-0 | All 16 existing GovernanceGate rules continue to evaluate first, unchanged; new rules are additive only | Hard | gate rule execution order |

### 9.6 Gate

**GATE-V2-RULES gate:** `HUMAN-0` (constitutional amendment) — All 5 new GovernanceGate v2 rules reviewed; exception token schema accepted; AST-COMPLEX-0 thresholds approved.

**Acceptance criteria:** Tests T63-GATE-01..15; 5 new rules verified; token lifecycle tested.

**Blocks on:** Phase 62 at main

---

## 10. Phase 64 — Selfhood (Constitutional Evolution Loop)

### 10.1 Purpose

Phase 64 assembles all prior organs into the Constitutional Evolution Loop (CEL) — a single, unified, replay-verifiable epoch lifecycle. This is the moment ADAAD becomes a governed evolutionary organism rather than a mutation pipeline.

### 10.2 CEL Step Sequence (14 Steps, Strictly Ordered)

| Step | Node | Input | Output / Side-effect | ADAAD Module |
|------|------|-------|----------------------|--------------|
| 1 | Code Intelligence refresh | Repo tree; EpochMemoryStore; sandbox profiling | Updated CodeIntelModel; model_hash | Phase 58 |
| 2 | TargetDiscovery | CodeIntelModel (hotspots, fragility, mutation history) | Ranked EvolutionTarget list (function-level) | Phase 58 |
| 3 | CapabilityTargetDiscovery | EvolutionTarget list + capability→function binding map | Ranked CapabilityTarget list with reason and bound functions | Phase 59 |
| 4 | ProposalEngine (LLM) | CapabilityTarget context + CodeIntel signals + governance constraints | MutationCandidate list with ast_patch, target_file, mutation_kind | Phase 57 |
| 5 | StaticSafetyScanner | MutationCandidate.ast_patch | StaticCheckResult; hard-reject on Tier-0 target, nondeterminism, import boundary, size limit | Phase 60 |
| 6 | SandboxTournament | Passing candidates; ephemeral repo clone | Per-candidate: test results, coverage delta, benchmark delta, replay verification | Phase 60 |
| 7 | FitnessEngine v2 | Sandbox results; CodeIntelModel (architectural signals) | Multi-horizon FitnessScores; composite score; explanations | Phase 62 |
| 8 | GovernanceGate v2 | MutationEvaluation (static + sandbox + fitness) | GovernanceDecision: approved / rejected / class_b_eligible + rule_traces | Phase 63 |
| 9 | Exception Token gate | class_b_eligible decisions + lineage simulation | ExceptionToken grant or deny; time-bounded capability-scoped relief | Phase 63 |
| 10 | Patch application + replay | Approved mutations; ephemeral clone result | Atomic write to Tier-1 target; replay verifier confirms no divergence | Phase 60 (SANDBOX-DIV-0) |
| 11 | CapabilityGraph update | Approved CapabilityChange; new contract/version | Capability version bumped; telemetry updated; CAP-VERS-0 ledger entry | Phase 59 |
| 12 | EpochEvidence + Ledger write | All epoch artifacts: model_hash, targets, mutations, decisions, cap_changes | EpochEvidence record hash-chained into existing JSONL ledger via EvidenceBundleBuilder | Phase 64 |
| 13 | Strategy Brain feedback | Governance decisions; fitness deltas; rejection reasons | MutationOperatorFramework weights updated; niche bandit priors updated; MutationSkill library | Phase 61 |
| 14 | Next epoch start smarter | Updated CodeIntelModel + CapabilityGraph + Strategy Brain | Richer context for step 4 (ProposalEngine prompts better targeted) | Full loop closed |

### 10.3 EpochEvidence — The Atomic Evidence Record

Every CEL epoch produces exactly one `EpochEvidence` record. It is the cryptographic proof of what ADAAD did, what it believed, and what governance allowed.

| Field | Type | Source | Purpose |
|-------|------|--------|---------|
| `epoch_id` | str | EvolutionLoop.run_epoch() | Unique epoch identifier; primary key in JSONL ledger |
| `model_hash` | sha256 hex | `sha256(json.dumps(CodeIntelModel, sort_keys=True))` | Proves exactly what ADAAD believed at epoch start |
| `capability_targets` | list[str] | CapabilityTargetDiscovery.discover() | Which capabilities were selected for evolution this epoch |
| `mutations_attempted` | list[mutation_id] | All candidates entering SandboxTournament | Full audit trail |
| `mutations_succeeded` | list[mutation_id] | GovernanceGate approved subset | Governance filter visible in evidence |
| `capability_changes` | list[CapabilityChange] | CapabilityEvolutionEngine.evolve() results | Per-capability: from_version, to_version, mutation_id, fitness_before, fitness_after |
| `governance_events` | list[str] | GovernanceGate v2 decision traces | Human-readable rule trace per candidate; explainability record |
| `exception_tokens_used` | list[token_id] | ExceptionTokenLedger (Phase 63) | Which Class B exceptions were active this epoch |
| `fitness_summary` | dict[str, float] | FitnessEngine v2 composite per succeeded mutation | Signal breakdown: test, complexity, performance, architectural, determinism |
| `predecessor_hash` | sha256 hex | Previous EpochEvidence.compute_hash() | Hash-chains EpochEvidence into existing JSONL ledger |
| `timestamp` | datetime (UTC) | RuntimeDeterminismProvider.now_utc() | MUST use existing RuntimeDeterminismProvider — not datetime.now() |

### 10.4 ProposalEngine Prompt Contract

| Context Field | Source | Injected Into Prompt As |
|---------------|--------|------------------------|
| `capability_name` | CapabilityTarget.capability_name | 'Target capability: {name}. Implement improvement in bound modules: {files}' |
| `capability_contract` | CapabilityNode.contract (invariants, inputs, outputs) | Hard constraint list: 'These invariants must not be weakened: {invariants}' |
| `capability_version` | CapabilityNode.version | 'Current version: {version}. Proposal must be backward-compatible or produce a minor version bump' |
| `hotspot_functions` | CapabilityTarget.functions + HotspotMap | 'Performance-critical functions: {fn}: {runtime_pct}% of runtime. Prefer mutations targeting these.' |
| `fragility_signals` | TargetDiscovery.fragility_targets() | 'Fragile functions (mutation success rate < 30%): {fn_list}. Prefer simpler mutations here.' |
| `call_graph_context` | FunctionGraph.edges for bound functions | 'Call graph: {fn} calls {callees}. Mutations must not break these call contracts.' |
| `governance_constraints` | Static rules YAML + Tier boundary | 'Constitutional constraints: no Tier-0 imports, complexity delta ≤ 2 (Class A), max 40 AST nodes, max 2 files' |
| `strategy_id` | StrategyModule (existing STRATEGY_TAXONOMY) | Routes to existing _STRATEGY_SYSTEM_PROMPTS dict — unchanged from Phase 16 |
| `mutation_history_signals` | MutationHistory.success_rate(fn) per bound fn | 'Historical mutation success rates: {fn}: {rate}. Avoid patterns that repeatedly fail.' |
| `required_output_schema` | ASTDiffPatch JSON schema | 'Return JSON: {mutation_kind, target_file, ast_patch:{before_source,after_source}, intent, risk_class}' |

### 10.5 Aponi CEL Console (Phase 64 Dashboard)

| Panel | Content |
|-------|---------|
| Diff Viewer | Side-by-side before/after source with ast_patch metadata overlay and mutation_kind annotation |
| Rule Trace | GovernanceGate v2 rule evaluation trace; per-rule pass/fail; Class A/B classification; exception token indicator |
| Fitness Breakdown | Multi-horizon signal bar chart per mutation candidate; composite score with signal weights visible |
| Lineage Tree | Visual lineage DAG with compatibility edges; stability scores; cooling-period indicators |
| Exception Token Status | Active tokens per capability; expiry countdown; lineage projection chart |
| EpochEvidence Audit | Full evidence record for any epoch; model_hash, capability targets, all decisions — hash-verifiable |
| CEL Status Panel | Which CEL step is currently executing; live progress; last epoch summary |

### 10.6 Constitutional Invariants

| ID | Statement | Class | Enforcement |
|----|-----------|-------|-------------|
| CEL-ORDER-0 | The 14 CEL steps MUST execute in strict sequence; no step may be skipped; no step may execute out of order | Hard | step sequencer |
| CEL-EVIDENCE-0 | Every CEL epoch MUST produce exactly one EpochEvidence record; epoch without evidence record is invalid | Hard | EvidenceBundleBuilder |
| CEL-HASH-0 | predecessor_hash MUST reference the previous EpochEvidence hash; broken chain is a constitutional violation | Hard | hash chain validator |
| CEL-TS-0 | All EpochEvidence timestamps MUST use RuntimeDeterminismProvider.now_utc() | Hard | evidence builder |

### 10.7 Gate

**CEL-DRY-RUN gate:** `HUMAN-0` — SANDBOX_ONLY dry-run results reviewed in Aponi; EpochEvidence ledger write verified; calibration accepted.

**Acceptance criteria:** Tests T64-CEL-01..12; full loop dry-run in SANDBOX_ONLY mode; EpochEvidence ledger write verified.

**Blocks on:** Phase 63 at main

---

## 11. Phase 65 — Emergence (First Autonomous Capability Evolution)

### 11.1 Purpose

Phase 65 is not a construction phase. It is the validation milestone that proves the entire stack delivers on its promise. All 9 organs must be active. The target is the first end-to-end governed code improvement that ADAAD produces without human authorship.

### 11.2 Acceptance Protocol (12 Steps)

1. TargetDiscovery identifies highest-priority Tier-1 capability from live CodeIntelModel and MutationHistory
2. CapabilityTargetDiscovery maps to a specific capability with bound functions and hotspot context
3. ProposalEngine generates an AST-level mutation proposal with full prompt contract context
4. StaticSafetyScanner passes all checks
5. SandboxTournament runs ephemeral competition; top candidate advances to GovernanceGate v2
6. FitnessEngine v2 scores all signals; composite score above baseline
7. GovernanceGate v2 approves as Class A (or Class B with exception token + human co-sign)
8. Patch applied atomically; replay_verifier.py confirms zero divergence (SANDBOX-DIV-0)
9. CapabilityGraph: target capability version bumped; CapabilityChange written
10. EpochEvidence hash-chained into ledger via EvidenceBundleBuilder
11. Aponi console displays full audit trail; human reviews and acknowledges
12. At least one fitness signal demonstrably improves: test coverage, complexity, performance, or architectural fitness

### 11.3 Constitutional Proof

When Phase 65 completes, ADAAD can truthfully and cryptographically prove:

> "I analysed my own structure. I identified where to improve. I proposed a change. I tested it safely. Governance approved it. I applied it. I can replay every step of that decision chain."

### 11.4 Gate

**MUTATION-TARGET gate:** `HUMAN-0` — Human selects and approves first mutation target in Aponi console; mutation diff reviewed; Class A or B classification confirmed.

**V9-RELEASE gate:** `AUDIT-0`, `REPLAY-0` — Full regression 3,960+ tests, 0 failures; EpochEvidence present in ledger; replay verification passes on committed mutation.

**Version tag:** v9.0.0 tagged at Phase 65 completion.

---

## 12. Implementation Dependency Chain

Each phase requires all predecessors merged to main. Human sign-off gates are constitutional requirements — not process gates.

| Phase | Deliverable | Blocks On | Human Gate | Acceptance Criteria |
|-------|-------------|-----------|------------|---------------------|
| 57 | ProposalEngine auto-provisioning | Phase 57 spec sign-off | HUMAN-0 | T57-AP-01..12 pass; 0 regressions |
| 58 | CodeIntelModel + TargetDiscovery | Phase 57 at main | — | T58-INTEL-01..12; model_hash determinism verified |
| 59 | CapabilityGraph v2 + CapabilityTargetDiscovery | Phase 58 at main | HUMAN-0 | First 10 capabilities in registry; contracts validated; T59-CAP-01..10 |
| 60 | ASTDiffPatch + StaticScanner + SandboxTournament | Phase 59 at main | — | MUTATION_SANDBOX_ONLY tests pass; SANDBOX-DIV-0 verified; T60-AST-01..15 |
| 61 | LineageEngine + compatibility graph | Phase 60 at main | — | Epistasis detection test cases; lineage survival scoring; T61-LIN-01..12 |
| 62 | Multi-horizon FitnessEngine v2 | Phase 61 at main | — | All 7 signal sources active; composite score deterministic; T62-FIT-01..10 |
| 63 | GovernanceGate v2 + Exception Tokens | Phase 62 at main | HUMAN-0 (constitutional amendment) | 5 new rules verified; token lifecycle tested; T63-GATE-01..15 |
| 64 | CEL + EpochEvidence + Aponi console | Phase 63 at main | HUMAN-0 | Full loop dry-run in SANDBOX_ONLY mode; EpochEvidence ledger write verified; T64-CEL-01..12 |
| 65 | First autonomous capability evolution | Phase 64 at main | HUMAN-0 (mutation approval) | v9.0.0 tag; at least 1 fitness signal improved; EpochEvidence in ledger |

---

## 13. Prevention Plan — Three Critical Failure Modes

### 13.1 AST Patch Reliability (Format/Comment Drift)

**Risk:** Raw stdlib `ast` discards comments, formatting, and whitespace. If `ast_patch.after_source` diverges from what LibCST actually applies to the file, SANDBOX-DIV-0 will catch it post-apply but the system will enter a chronic rejection loop.

**Prevention:**
- stdlib `ast` at Phase 60 for validation only; LibCST for all actual source patch application
- `before_ast_hash` and `after_ast_hash` computed from `ast.dump()` not source text — formatting-invariant
- SANDBOX-DIV-0 catches any divergence post-apply; auto-rollback + governance incident record

### 13.2 Determinism Freeze (Evolutionary Stagnation)

**Risk:** If all mutation seeds derive only from static epoch context, the system can produce identical proposals epoch after epoch — especially when the codebase changes slowly. Evolution freezes.

**Prevention:**
- `seed = sha256(epoch_id + ledger_tail_hash)` — the ledger grows every epoch; tail hash changes even when codebase does not. Controlled entropy from system history.
- Detection: `EpochEvidence` records `mutations_attempted`; if this list is identical for 3+ consecutive epochs, StrategyBrain v2 enters forced exploration mode

### 13.3 Governance Lock-In on the First Real Mutation

**Risk:** Phase 65 may fail not because the system is broken, but because GovernanceGate v2 is calibrated too strictly for a first-attempt Class A mutation.

**Prevention:**
- Phase 64 dry-run in `MUTATION_SANDBOX_ONLY` mode produces a cohort of real proposals; thresholds in `static_rules.yaml` are calibrated against actual ADAAD code before any real writes
- Class B exception token path allows first mutation to proceed with temporary complexity relief if lineage simulation is positive and human co-signs
- Phase 65 explicitly requires human review of the first mutation target in Aponi console — the human can select a low-risk target and accept a conservative patch as v9.0.0

---

## 14. Constitutional Sign-Off Block

Checklist reference: `docs/governance/V8_HUMAN_GATE_READINESS.md`

All constitutional gates require human maintainer sign-off before the corresponding implementation PR opens. No gate can be bypassed. No PR can open on a successor phase until the predecessor's gate is recorded in the evidence ledger.

| Gate | Phase | Invariant | Condition for Sign-off |
|------|-------|-----------|------------------------|
| SPEC-57 | Phase 57 | HUMAN-0 | ADAAD_Phase57_Spec.docx reviewed and approved; PROP-AUTO-0..5 accepted |
| CAP-REGISTRY | Phase 59 | HUMAN-0 | First 10 capability contracts reviewed; bound_modules correct; governance_tags verified |
| GATE-V2-RULES | Phase 63 | HUMAN-0 (constitutional amendment) | All 5 new GovernanceGate v2 rules reviewed; exception token schema accepted; AST-COMPLEX-0 thresholds approved |
| CEL-DRY-RUN | Phase 64 | HUMAN-0 | SANDBOX_ONLY dry-run results reviewed in Aponi; EpochEvidence ledger write verified; calibration accepted |
| MUTATION-TARGET | Phase 65 | HUMAN-0 | Human selects and approves first mutation target in Aponi console; mutation diff reviewed; Class A or B classification confirmed |
| V9-RELEASE | Phase 65 | AUDIT-0, REPLAY-0 | Full regression 3,960+ tests, 0 failures; EpochEvidence present in ledger; replay verification passes on committed mutation |

---

## 15. New Invariants Matrix — v8.0.0

### Phase 57

| ID | Statement | Class | Phase |
|----|-----------|-------|-------|
| PROP-AUTO-0 | ProposalEngine MUST NOT activate unless API key present and validated | Hard | 57 |
| PROP-AUTO-1 | All LLM proposals MUST enter governed pipeline; no bypass | Hard | 57 |
| PROP-AUTO-2 | strategy_id MUST be validated against STRATEGY_TAXONOMY before any LLM call | Hard | 57 |
| PROP-AUTO-3 | Context MUST include governance_debt_score, lineage_health, bandit_confidence, epoch_count | Hard | 57 |
| PROP-AUTO-4 | ProposalEngine failure MUST be fail-closed | Hard | 57 |
| PROP-AUTO-5 | LLM call count per epoch MUST be bounded (default: 3) | Hard | 57 |

### Phase 58

| ID | Statement | Class | Phase |
|----|-----------|-------|-------|
| INTEL-DET-0 | model_hash MUST be identical for identical CodeIntelModel across restarts | Hard | 58 |
| INTEL-TS-0 | All CodeIntelModel timestamps MUST use RuntimeDeterminismProvider.now_utc() | Hard | 58 |
| INTEL-ISO-0 | CodeIntelModel MUST NOT write to governance or ledger paths | Hard | 58 |

### Phase 59

| ID | Statement | Class | Phase |
|----|-----------|-------|-------|
| CAP-VERS-0 | Every CapabilityNode version bump MUST produce a ledger entry | Hard | 59 |
| CAP-DEP-0 | Missing dependency_set entries MUST raise ValueError at load time | Hard | 59 |
| CAP-TIER0-0 | Tier-0 capabilities carry 'non_mutable' tag; GovernanceGate blocks all mutations to their bound_modules | Hard | 59 |

### Phase 60

| ID | Statement | Class | Phase |
|----|-----------|-------|-------|
| SANDBOX-DIV-0 | Post-apply test results MUST match sandbox results exactly | Hard | 60 |
| TIER0-SELF-0 | No ASTDiffPatch may target a Tier-0 file path | Hard | 60 |
| PATCH-SIZE-0 | node_count_delta > 40 OR files_touched > 2 → hard rejection | Hard | 60 |

### Phase 61

| ID | Statement | Class | Phase |
|----|-----------|-------|-------|
| LINEAGE-STAB-0 | Lineage must pass governance ≥ 2 of 5 consecutive epochs to remain active | Hard | 61 |
| EPISTASIS-0 | Epistatic mutation combinations MUST be flagged and blocked from co-application | Hard | 61 |

### Phase 62

| ID | Statement | Class | Phase |
|----|-----------|-------|-------|
| FIT-BOUND-0 | All signal weights bounded to [0.05, 0.70]; composite bounded to [0.0, 1.0] | Hard | 62 |
| FIT-DET-0 | Composite score MUST be deterministic given identical inputs | Hard | 62 |
| FIT-DIV-0 | Determinism fitness = 0 on any replay divergence; overrides all other signals | Hard | 62 |
| FIT-ARCH-0 | Architectural fitness signal returns 0.5 (neutral) until Phase 62 fully active | Hard | 62 |

### Phase 63

| ID | Statement | Class | Phase |
|----|-----------|-------|-------|
| AST-SAFE-0 | No mutation may produce AST with syntax errors, exec/eval, or unguarded system calls | Hard | 63 |
| AST-IMPORT-0 | No new imports from Tier-0 module roots | Hard | 63 |
| AST-COMPLEX-0 | cyclomatic_after ≤ cyclomatic_before + 2 (Class A); Class B eligible up to +8 with lineage + HUMAN-0 | Class A / B | 63 |
| SEMANTIC-INT-0 | No removal of error guard without compensating handler | Hard | 63 |
| EXCEP-SCOPE-0 | Exception tokens scoped to single capability and single rule; Tier-0 ineligible | Hard | 63 |
| EXCEP-HUMAN-0 | HUMAN-0 required before any exception token granted for Tier-1 capabilities | Hard | 63 |
| EXCEP-TTL-0 | Exception tokens expire at most 3 epochs from grant | Hard | 63 |
| EXCEP-REVOKE-0 | Auto-revocation immediate on any trigger condition; no grace period | Hard | 63 |
| GATE-V2-EXISTING-0 | All 16 existing gate rules continue to evaluate first, unchanged | Hard | 63 |

### Phase 64

| ID | Statement | Class | Phase |
|----|-----------|-------|-------|
| CEL-ORDER-0 | 14 CEL steps MUST execute in strict sequence; no skip; no out-of-order | Hard | 64 |
| CEL-EVIDENCE-0 | Every CEL epoch MUST produce exactly one EpochEvidence record | Hard | 64 |
| CEL-HASH-0 | predecessor_hash MUST reference previous EpochEvidence hash | Hard | 64 |
| CEL-TS-0 | All EpochEvidence timestamps MUST use RuntimeDeterminismProvider.now_utc() | Hard | 64 |

---

## 16. Notes for Downstream Agents

### For MutationAgent / IntegrationAgent

- **Phase 57 first:** No Phase 58+ work may begin until Phase 57 is merged to main and HUMAN-0 gate is recorded in evidence ledger.
- **Fail-closed always:** Every new module must fail closed on error — no silent fallback, no partial state propagation.
- **GovernanceGate isolation:** New modules (CodeIntelModel, StaticSafetyScanner, SandboxTournament, FitnessEngine v2) MUST NOT reference GovernanceGate directly. Gate is called only through the established gate chain.
- **Determinism non-negotiable:** All timestamps via `RuntimeDeterminismProvider.now_utc()`. All scoring advisory-only. All weights bounded to [0.05, 0.70].
- **Feature flag discipline:** `MUTATION_SANDBOX_ONLY=true` MUST be enforced throughout Phase 60 stabilisation. No real repo writes until flag cleared by human gate.
- **SANDBOX-DIV-0 on every apply:** replay_verifier.py must run post-apply for every approved mutation without exception.

### For AnalysisAgent

- `CodeIntelModel.model_hash` is the evidence key for perception state. Record it in every EpochEvidence.
- Fitness signal weights are governance-controlled. Any weight outside [0.05, 0.70] is a constitutional violation to report.
- Exception token presence in EpochEvidence is an audit event. Flag any epoch with exception_tokens_used for review.
- Lineage stagnation (identical mutations_attempted across 3+ epochs) triggers forced exploration — flag and report.

---

**END OF SPECIFICATION — ADAAD v8 Constitutional Autonomous Software Evolution — Unified Roadmap — Phases 57–65**

*ArchitectAgent · InnovativeAI-adaad/ADAAD · v8.0.0 · 2026-03-13*
