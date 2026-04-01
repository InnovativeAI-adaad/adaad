# ADAAD v10 System Architecture

**Status:** Forward design — target state after INNOV-30 ships (v9.48.0)  
**Authority:** HUMAN-0 — Dustin L. Reid  
**Base version:** v9.32.0 (Phase 99 complete)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ADAAD v9.48.0+                               │
│                   Constitutional Mutation Engine                     │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  AUTONOMY   │  │INTELLIGENCE │  │ GOVERNANCE  │
   │    LOOP     │  │    LAYER    │  │    LAYER    │
   │             │  │             │  │             │
   │ CEL 17-step │  │ Strategy    │  │ GovernGate  │
   │ Dream State │  │ Taxonomy    │  │ v2 + CJS    │
   │ BEAST/DREAM │  │ Critique    │  │ Invariants  │
   │   modes     │  │ Signal Buf  │  │ (80+)       │
   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
          │                │                 │
          └────────────────┼─────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │       INNOVATIONS LAYER         │
          │   (runtime/innovations30/)      │
          │                                 │
          │  Constitutional Intelligence:   │
          │   InvariantDiscovery            │
          │   TensionResolver               │
          │   GraduatedPromotion            │
          │   ConstitutionalJury ✅          │
          │   ConstitutionalStressTest      │
          │   ConstitutionalEntropyBudget   │
          │   MirrorTest                    │
          │                                 │
          │  Agent Economy:                 │
          │   ReputationStaking             │
          │   EmergentRoles                 │
          │   AgentPostmortem               │
          │                                 │
          │  Temporal Intelligence:         │
          │   TemporalRegret                │
          │   DreamState ✅                  │
          │   MorphogeneticMemory ✅         │
          │   InstitutionalTransfer         │
          │   TemporalGovernance            │
          │                                 │
          │  Real-World Grounding:          │
          │   MarketFitness                 │
          │   HardwareAdaptive              │
          │   RegulatoryCompliance          │
          │   SemanticVersionEnforcer       │
          │   BlastRadiusModel              │
          │                                 │
          │  Governance Infrastructure:     │
          │   GovernanceArchaeology         │
          │   GovernanceBankruptcy          │
          │                                 │
          │  Identity:                      │
          │   SelfAwarenessInvariant        │
          │   CuriosityEngine               │
          │   MirrorTest                    │
          └────────────────┬────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │         RUNTIME CORE            │
          │                                 │
          │  AST Mutation Substrate         │
          │  Fitness Engine v2              │
          │  Lineage Engine                 │
          │  Capability Graph v2            │
          │  Code Intel Model               │
          │  Proposal Engine                │
          │  Sandbox/Container Isolation    │
          └────────────────┬────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │        PERSISTENCE LAYER        │
          │                                 │
          │  Identity Ledger (JSONL)        │
          │  Reputation Stakes (JSONL)      │
          │  Governance Archaeology (JSONL) │
          │  Dream State Ledger (JSONL)     │
          │  Morphogenetic Memory (JSONL)   │
          │  Mirror Test Records (JSONL)    │
          │  Agent Wallets (JSON)           │
          └────────────────┬────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │            UI LAYER             │
          │                                 │
          │  Aponi (Oracle) — governance    │
          │  Dork (Whaledic) — mutation     │
          │  ADAAD_STATE_BUS (L1 shared)    │
          │  Groq SSE streaming primary     │
          │  Ollama local secondary         │
          │  DorkEngine deterministic fbk   │
          └─────────────────────────────────┘
```

---

## Module Inventory (v9.48.0 Target)

### runtime/innovations30/ — 30 innovation modules

| Module | Innovation | Status |
|---|---|---|
| `invariant_discovery.py` | INNOV-01 CSAP | ✅ Shipped |
| `constitutional_tension.py` | INNOV-02 ACSE | ✅ Shipped |
| `graduated_invariants.py` | INNOV-03 TIFE | ✅ Shipped |
| `intent_preservation.py` | INNOV-04 SCDD | ✅ Shipped |
| `temporal_regret.py` | INNOV-05 AOEP | ✅ Shipped |
| `counterfactual_fitness.py` | INNOV-06 CEPD | ✅ Shipped |
| `epistemic_decay.py` | INNOV-07 LSME | ✅ Shipped |
| `red_team_agent.py` | INNOV-08 AFRT | ✅ Shipped |
| `aesthetic_fitness.py` | INNOV-09 AFIT | ✅ Shipped |
| `morphogenetic_memory.py` | INNOV-10 MMEM | ✅ Shipped |
| `dream_state.py` | INNOV-11 DSTE | ✅ Shipped |
| `mutation_genealogy.py` | INNOV-12 MGV | ✅ Shipped |
| `knowledge_transfer.py` | INNOV-13 | 📋 Phase 98 |
| `constitutional_jury.py` | INNOV-14 CJS | ✅ Shipped v9.32.0 |
| `reputation_staking.py` | INNOV-15 | 📋 Phase 100 |
| `emergent_roles.py` | INNOV-16 | 📋 Phase 101 |
| `agent_postmortem.py` | INNOV-17 | 📋 Phase 102 |
| `temporal_governance.py` | INNOV-18 | 📋 Phase 103 |
| `governance_archaeology.py` | INNOV-19 | 📋 Phase 104 |
| `constitutional_stress_test.py` | INNOV-20 | 📋 Phase 105 |
| `governance_bankruptcy.py` | INNOV-21 | 📋 Phase 106 |
| `market_fitness.py` | INNOV-22 | 📋 Phase 107 |
| `regulatory_compliance.py` | INNOV-23 | 📋 Phase 108 |
| `semantic_version_enforcer.py` | INNOV-24 | 📋 Phase 109 |
| `hardware_adaptive_fitness.py` | INNOV-25 | 📋 Phase 110 |
| `constitutional_entropy_budget.py` | INNOV-26 | 📋 Phase 111 |
| `blast_radius_model.py` | INNOV-27 | 📋 Phase 112 |
| `self_awareness_invariant.py` | INNOV-28 | 📋 Phase 113 |
| `curiosity_engine.py` | INNOV-29 | 📋 Phase 114 |
| `mirror_test.py` | INNOV-30 | 📋 Phase 115 |

---

## Data Flow — Mutation Lifecycle at v9.48.0

```
PROPOSAL SUBMISSION
      │
      ▼
[ReputationStaking.stake()] ←── MIN_STAKE check, MAX_STAKE_FRACTION cap
      │
      ▼
[EmergentRoles.route()] ←────── Match proposal type to specialized agents
      │
      ▼
[BlastRadiusModel.estimate()] ← Formal reversal cost estimation
      │
      ▼
[GovernanceGate v2 — Tier 0]
      │  AST safety, import boundary, complexity
      ▼
[GovernanceGate v2 — Tier 1]
      │  Full constitutional invariant check (80+)
      ▼
[ConstitutionalJury.deliberate()] ←── HIGH_STAKES_PATHS trigger
      │  3 jurors, 2-of-3 quorum, dissent ledgered
      ▼
[RegulatoryCompliance.check()] ←── EU AI Act, NIST AI RMF gates
      │
      ▼
[TemporalGovernanceWindow.evaluate()] ← Health-state-adjusted severity
      │
      ▼
[FitnessEngine v2 — evaluation]
      │  Constitutional, structural, diversity, architectural scores
      │  + MarketConditionedFitness signal injection
      │  + HardwareAdaptiveFitness weight adjustment
      │  + AestheticFitness score
      ▼
[SemanticVersionEnforcer.verify()] ← Semver contract validation
      │
      ▼
GATE DECISION: PROMOTE / BLOCK / DEFER
      │
      ├─── BLOCK ──→ [ReputationStaking.settle(outcome='failed')]
      │                  stake burned, agent wallet decremented
      │              [AgentPostmortem.record()]
      │                  failure interview, feeds InvariantDiscovery
      │
      └─── PROMOTE ─→ [ReputationStaking.settle(outcome='passed')]
                          stake * GOVERNANCE_PASS_MULTIPLIER returned
                      [LineageEngine.record()]
                      [MorphogeneticMemory.enrich()]
                      [MutationGenealogyAnalyzer.record()]
                      [GovernanceArchaeology.append()]
                      DEPLOY TO PRODUCTION
```

---

## Constitutional Invariant Architecture

### Hard-Class Invariants (46 current, 80+ target)

Naming convention: `MODULE-KEYWORD-N`  
Examples: `CJS-0`, `DSTE-0`, `MMEM-0`, `MGV-0`

All Hard-class invariants must be:
- Documented in `GOVERNANCE/CONSTITUTIONAL_INVARIANT_REGISTRY.md`
- Tested with at least one positive and one negative test
- Incorporated into `GovernanceGateV2` evaluation path
- Reported in phase governance artifacts

### Invariant Categories

| Category | Current count | Target |
|---|---|---|
| Core runtime (CEL, AST, sandbox) | ~15 | 20 |
| Constitutional intelligence | ~8 | 15 |
| Agent economy | 0 | 8 |
| Temporal intelligence | ~7 | 12 |
| Real-world grounding | 0 | 10 |
| Governance infrastructure | ~5 | 10 |
| Identity/self-awareness | 0 | 5 |
| **Total** | **~46** | **80+** |

---

## LLM Provider Architecture (No Paid APIs)

```
Request
   │
   ▼
[Groq Free Tier] ────────────────────────────────→ Response
   │  llama-3.3-70b-versatile
   │  SSE streaming
   │  14,400 req/day limit
   │  FAILURE or RATE_LIMIT
   ▼
[Ollama Local] ──────────────────────────────────→ Response  
   │  localhost:11434
   │  Zero cost, zero network
   │  FAILURE or UNAVAILABLE
   ▼
[DorkEngine Deterministic] ──────────────────────→ Response
   Constitutional rule engine
   Always available
   Deterministic output from constitutional rules
   No external dependency
```

**Invariants:**
- `DORK-FREE-0`: No paid API dependency in primary or secondary path
- `BRIDGE-FREE-0`: State bus relay requires no external authentication

---

## Persistence and Auditability

All ADAAD data persists in append-only JSONL files. No database. No external dependency.

| File | Content | Innovation |
|---|---|---|
| `data/reputation_stakes.jsonl` | Stake records per proposal | INNOV-15 |
| `data/agent_wallets.json` | Agent balance snapshots | INNOV-15 |
| `data/emergent_roles.json` | Discovered role assignments | INNOV-16 |
| `data/postmortem_interviews.jsonl` | Agent failure interviews | INNOV-17 |
| `data/governance_windows.jsonl` | Window evaluation history | INNOV-18 |
| `data/mutation_archaeology.jsonl` | Full decision timelines | INNOV-19 |
| `data/constitutional_gaps.jsonl` | Stress test findings | INNOV-20 |
| `data/bankruptcy_declarations.jsonl` | Bankruptcy events | INNOV-21 |
| `data/external_signals.jsonl` | Market signal history | INNOV-22 |
| `data/compliance_verdicts.jsonl` | Regulatory verdicts | INNOV-23 |
| `data/semver_verdicts.jsonl` | Version promise verdicts | INNOV-24 |
| `data/blast_radius_reports.jsonl` | Blast radius estimates | INNOV-27 |
| `data/mirror_test_records.jsonl` | Mirror test results | INNOV-30 |
| `data/reputation_stakes.jsonl` | All stake events | INNOV-15 |

**Archaeology guarantee:** Every entry in every JSONL file carries a SHA-256 digest linking it to its predecessors. Any tampering is detectable.

---

*Architecture authority: ADAAD LEAD · InnovativeAI LLC · 2026-04-01*
