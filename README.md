<p align="center">
  <img src="docs/assets/adaad-banner.svg" width="900" alt="ADAAD — Autonomous Device-Anchored Adaptive Development"/>
</p>

<p align="center">
  <b>ADAAD — Autonomous Device-Anchored Adaptive Development</b><br/>
  <i>The world's first constitutional AI mutation engine: governed, deterministic, self-evolving.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-9.0.0-blue?style=for-the-badge" alt="Version"/>
  <img src="https://img.shields.io/badge/Phase-65%20Complete-success?style=for-the-badge" alt="Phase"/>
  <img src="https://img.shields.io/badge/Tests-3960%2B%20Passing-brightgreen?style=for-the-badge" alt="Tests"/>
  <img src="https://img.shields.io/badge/Constitution-v0.7.0-orange?style=for-the-badge" alt="Constitution"/>
  <img src="https://img.shields.io/badge/Python-3.12%2B-yellow?style=for-the-badge" alt="Python"/>
  <img src="https://img.shields.io/badge/License-Apache%202.0-lightgrey?style=for-the-badge" alt="License"/>
  <img src="https://img.shields.io/badge/Self--Evolution-Phase%2065%20Active-9C27B0?style=for-the-badge" alt="Emergence"/>
</p>

---

## What is ADAAD?

**ADAAD** is a production-grade autonomous code evolution engine built by **InnovativeAI LLC** (Blackwell, Oklahoma). It does not generate code the way a chatbot does. It *evolves* a living codebase — epoch by epoch — under a constitutional governance model that makes every mutation deterministic, auditable, and human-co-signed where the stakes demand it.

> *"ADAAD is not a code generator. It is an autonomous software organism that governs its own evolution."*
> — Dustin L. Reid, Sole Architect

**The core proposition:** code that rewrites itself, under constitutional law, provably better every epoch.

**As of v9.0.0 (Phase 65 — Emergence):** ADAAD has executed its first fully governed, self-directed capability evolution. Every step from codebase perception to governance approval to atomic patch application is cryptographically hash-chained in the evolution ledger and replay-verifiable.

---

## System State

<!-- ADAAD_VERSION_INFOBOX:START -->

| Field | Value |
|---|---|
| **Current version** | `9.0.0` |
| **Phase** | 65 complete — Emergence: First Autonomous Capability Evolution |
| **Released** | 2026-03-13 |
| **Release branch** | `main` |
| **Tests passing** | 3,960+ |
| **Constitution** | v0.9.0 (23 rules: 18 base + 5 Phase 63 GovernanceGateV2; see `runtime/governance/constitution.yaml`) |
| **Canonical governance spec** | `docs/governance/ARCHITECT_SPEC_v8.0.0.md` |
| **All 9 Organs** | Active and production-wired |
| **CEL mode** | `ADAAD_CEL_ENABLED=true` activates live ConstitutionalEvolutionLoop |
| **Next phase** | 66 — direction to be proposed by ArchitectAgent + human-approved |

<!-- ADAAD_VERSION_INFOBOX:END -->

---

## Architecture at a Glance — v9 Runtime

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         ADAAD v9 Runtime                                 │
│                                                                          │
│  EvolutionLoop.run_epoch()                                               │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  ADAAD_CEL_ENABLED=true ──▶ _run_cel_epoch()                     │  │
│  │                                                                   │  │
│  │  LiveWiredCEL — 14-step ConstitutionalEvolutionLoop               │  │
│  │                                                                   │  │
│  │  Step  1  MODEL-DRIFT-CHECK   CodeIntelModel determinism check    │  │
│  │  Step  2  LINEAGE-SNAPSHOT    LineageEngine state hash            │  │
│  │  Step  3  FITNESS-BASELINE    FitnessEngineV2 baseline            │  │
│  │  Step  4  PROPOSAL-GENERATE   ProposalEngine.generate() ◀── LLM  │  │
│  │  Step  5  AST-SCAN            StaticSafetyScanner (4 rules)       │  │
│  │  Step  6  SANDBOX-EXECUTE     ephemeral clone execution           │  │
│  │  Step  7  REPLAY-VERIFY       SANDBOX-DIV-0 hash check            │  │
│  │  Step  8  FITNESS-SCORE       FitnessEngineV2 (7 signals)         │  │
│  │  Step  9  GOVERNANCE-GATE-V2  5 Phase 63 rules (AST-aware)        │  │
│  │  Step 10  GOVERNANCE-GATE     18 base constitutional rules            │  │
│  │  Step 11  LINEAGE-REGISTER    LineageEngine.register()            │  │
│  │  Step 12  PROMOTION-DECISION  CapabilityGraph + PromotionEvent    │  │
│  │  Step 13  EPOCH-EVIDENCE-WRITE hash-chained ledger entry          │  │
│  │  Step 14  STATE-ADVANCE       epoch counter + journal event       │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ADAAD_CEL_ENABLED=false ──▶ _run_legacy_epoch() (prior behavior)       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## The Nine Evolutionary Organs

| Phase | Organ | Layer | Deliverable | Version |
|---|---|---|---|---|
| 57 | Brainstem | Keystone | ProposalEngine auto-provisioning, PROP-AUTO-0..5 | v8.0.0 |
| 58 | Perception | Intelligence | CodeIntelModel — FunctionGraph, HotspotMap, MutationHistory | v8.1.0 |
| 59 | Identity | Capability | CapabilityGraph v2 — 10 bootstrap caps, Tier-0 guard, CAP-VERS-0 | v8.2.0 |
| 60 | Motor | Mutation | ASTDiffPatch (DNA), StaticSafetyScanner, SandboxTournament | v8.3.0 |
| 61 | Evolution | Lineage | LineageEngine — 5 niches, epistasis, LINEAGE-STAB-0 | v8.4.0 |
| 62 | Intelligence | Fitness | FitnessEngineV2 — 7 signals, bounded weights, FIT-BOUND-0 | v8.5.0 |
| 63 | Judgment | Governance | GovernanceGateV2 + Exception Tokens, AST-SAFE-0, CEL-GATE-0 | v8.6.0 |
| 64 | Selfhood | CEL | ConstitutionalEvolutionLoop — 14 steps, EpochEvidence, CEL-ORDER-0 | v8.7.0 |
| **65** | **Emergence** | **Integration** | **First Autonomous Capability Evolution — v9.0.0** | **v9.0.0** |

---

## Constitutional Architecture

ADAAD's governance is not a safety filter bolted on the outside — it is the **execution substrate**. Every mutation flows through `GovernanceGate` and `GovernanceGateV2` before it can touch the codebase.

```
23 Constitutional Rules (active — canonical: runtime/governance/constitution.yaml)
├── GovernanceGate (18 base rules — v0.9.0)
│   ├── Core Determinism       R1–R4
│   ├── Mutation Safety        R5–R9
│   ├── Lineage Integrity      R10–R12
│   ├── Capability Boundary    R13–R14
│   ├── Human Approval         R15–R16 (HUMAN-0 gate)
│   └── Phase 23–63 additions  R17–R18 (entropy_budget_limit + market_signal_integrity)
│
└── GovernanceGateV2 (5 rules — Phase 63, diff-aware)
    ├── AST-SAFE-0     diff-aware syntax safety
    ├── AST-IMPORT-0   import boundary enforcement
    ├── AST-COMPLEX-0  cyclomatic ceiling
    ├── SANDBOX-DIV-0  post-apply hash verification
    └── SEMANTIC-INT-0 semantic contract integrity
```

**Eight Permanent Architecture Invariants:**

| ID | Invariant |
|---|---|
| GOV-SOLE-0 | `GovernanceGate` is the sole mutation approval surface |
| DET-ALL-0 | All governance decisions are deterministic |
| SIM-BLOCK-0 | `SimulationPolicy.simulation=True` blocks all live side-effects |
| SANDBOX-DIV-0 | AST hash must match after apply; divergence = auto-rollback |
| PATCH-SIZE-0 | Max 40 delta AST nodes, max 2 files per patch |
| TIER0-SELF-0 | Tier-0 bound modules cannot self-mutate |
| LINEAGE-STAB-0 | Lineage stable iff ≥ 2/5 last epochs passed |
| CEL-ORDER-0 | 14 CEL steps execute in strict sequence; no skipping |

---

## Phase 65 — Emergence: What Actually Happened

ADAAD's first governed self-improvement executed as follows:

1. **CodeIntelModel** identified the highest-priority improvement target in the live codebase
2. **CapabilityTargetDiscovery** mapped it to `cap:runtime.evolution.cel_wiring.live_mode`
3. **ProposalEngine** generated an LLM-backed mutation proposal
4. **StaticSafetyScanner** cleared all four AST safety rules
5. **SandboxTournament** evaluated candidates in an ephemeral container
6. **FitnessEngineV2** scored all 7 signals — composite exceeded baseline
7. **GovernanceGateV2** approved the proposal (Class A)
8. **GovernanceGate** confirmed all 18 base constitutional rules passed
9. Patch applied atomically — `replay_verifier` confirmed **0 divergences**
10. **CapabilityGraph** updated — `CapabilityChange` written to capability ledger
11. **EpochEvidence** hash-chained into the evolution ledger
12. Human acknowledged the full audit trail

**Every step is cryptographically evidenced.** Bundle: `artifacts/governance/phase65/`

### Activate CEL

```bash
# Live mode — routes run_epoch() through ConstitutionalEvolutionLoop
ADAAD_CEL_ENABLED=true python -m adaad

# Dry-run / sandbox mode — all steps execute but no writes occur
ADAAD_CEL_ENABLED=true ADAAD_SANDBOX_ONLY=true python -m adaad
```

---

## Fitness Engine — 7 Signals (Phase 62)

| Signal | Weight Bound | Horizon |
|---|---|---|
| Test fitness (coverage delta, failure reduction) | [0.05, 0.70] | Per-epoch |
| Complexity fitness (cyclomatic delta) | [0.05, 0.70] | Per-epoch |
| Performance fitness (benchmark delta) | [0.05, 0.70] | Per-epoch |
| Governance compliance (rolling pass rate) | [0.05, 0.70] | 10-epoch window |
| Architectural fitness (coupling, centrality) | [0.05, 0.70] | 20-epoch window |
| Determinism fitness (replay divergence = 0) | [0.05, 0.70] | Hard floor |
| Net node additions (deletion bonus) | [0.05, 0.70] | Per-epoch |

Determinism divergence = **total rejection**. No exception. `FIT-DIV-0` enforced.

---

## Quick Start

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
pip install -r requirements.txt
python -m pytest tests/ -q
python -m pytest -m autonomous_critical -q
```

```python
# Check version
from runtime import __version__
print(__version__)  # 9.0.0

# Build a CEL in sandbox mode
from runtime.evolution.cel_wiring import build_cel, is_cel_enabled
cel = build_cel(sandbox_only=True)

# Run an epoch (dry-run, no real writes)
result = cel.run_epoch(epoch_id="my-epoch-001")
print(result.completed)            # True when all 14 steps pass
print(result.epoch_evidence_hash)  # SHA-256 of the evidence record
```

---

## Human Gate Summary — All Signed Off

| Gate | Phase | Status | Evidence |
|---|---|---|---|
| CAP-REGISTRY | 59 | ✅ SIGNED_OFF | `artifacts/governance/phase59/capability_graph_v2_signoff.json` |
| GATE-V2-RULES | 63 | ✅ SIGNED_OFF | `artifacts/governance/phase63/governance_gate_v2_signoff.json` |
| CEL-DRY-RUN | 64 | ✅ SIGNED_OFF | `artifacts/governance/phase64/cel_dry_run_signoff.json` |
| MUTATION-TARGET | 65 | ✅ SIGNED_OFF | `artifacts/governance/phase65/mutation_target_signoff.json` |
| AUDIT-0 | 65 | ✅ SIGNED_OFF | `artifacts/governance/phase65/v9_release_audit_report.json` |
| REPLAY-0 | 65 | ✅ SIGNED_OFF | `artifacts/governance/phase65/v9_replay_verification.json` |

---

## Repository Structure

```
runtime/
├── governance/              Constitutional gate (23 rules), policy artifacts
├── evolution/
│   ├── evolution_loop.py    Top-level epoch path — CEL routing (Phase 65)
│   ├── cel_wiring.py        build_cel(), is_cel_enabled(), assert_cel_enabled_or_raise()
│   ├── constitutional_evolution_loop.py  14-step LiveWiredCEL (Phase 64)
│   ├── proposal_engine.py   LLM-augmented proposals (Phase 57)
│   ├── fitness_v2.py        FitnessEngineV2 — 7 signals (Phase 62)
│   ├── lineage_v2.py        LineageLedgerV2, hash-chained (Phase 61)
│   └── replay_attestation.py HMAC-signed replay proofs
├── mutation/
│   ├── code_intel/          CodeIntelModel (Phase 58)
│   └── ast_substrate/       ASTDiffPatch, StaticSafetyScanner, SandboxTournament (Phase 60)
├── capability_graph.py      CapabilityGraph + CapabilityChange ledger (Phase 65)
├── capability/              CapabilityRegistry v2 (Phase 59)
└── tools/
    └── mutation_guard.py    DNA mutation executor — upsert, auto-vivify, checksum
artifacts/governance/
├── phase65/                 v9.0.0 evidence bundle (HUMAN-0, AUDIT-0, REPLAY-0)
├── phase64/                 CEL dry-run signoff
├── phase63/                 GovernanceGateV2 signoff
└── phase59/                 CapabilityGraph v2 signoff
tests/                       3,960+ tests — Phases 57–65 complete
docs/governance/             ARCHITECT_SPEC_v8.0.0.md, CONSTITUTION.md, V8_HUMAN_GATE_READINESS.md
```

---

## Phase Roadmap

```
Phase 57 ✅  Brainstem    ProposalEngine auto-provisioning             v8.0.0
Phase 58 ✅  Perception   Code Intelligence Model                      v8.1.0
Phase 59 ✅  Identity     Capability Graph v2                          v8.2.0
Phase 60 ✅  Motor        AST Mutation Substrate (DNA + Sandbox)       v8.3.0
Phase 61 ✅  Evolution    Lineage Engine (niches + epistasis)           v8.4.0
Phase 62 ✅  Intelligence Multi-Horizon Fitness Engine v2               v8.5.0
Phase 63 ✅  Judgment     GovernanceGate v2 + Exception Tokens          v8.6.0
Phase 64 ✅  Selfhood     Constitutional Evolution Loop (14 steps)      v8.7.0
Phase 65 ✅  Emergence    First Autonomous Capability Evolution         v9.0.0
─────────────────────────────────────────────────────────────────────────────
Phase 66 🔜  TBD          Direction: ArchitectAgent proposal + human approval
```

---

## InnovativeAI LLC

**Co-founders:** Weirdo · Dustin L. Reid (Sole Architect, ADAAD)
**Location:** Blackwell, Oklahoma
**Mission:** Build the most rigorously governed autonomous code evolution engine ever shipped.

> ADAAD demonstrates that **autonomous capability and constitutional governance are synergistic, not adversarial**. Every phase that expands what ADAAD can do is matched by a phase that deepens what it cannot do without consent. This is the architecture of trustworthy autonomy.

---

*v9.0.0 — Phase 65: Emergence complete — 2026-03-13*
