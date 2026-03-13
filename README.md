<p align="center">
  <img src="docs/assets/adaad-banner.svg" width="900" alt="ADAAD — Autonomous Device-Anchored Adaptive Development"/>
</p>

<p align="center">
  <b>ADAAD — Autonomous Device-Anchored Adaptive Development</b><br/>
  <i>Your codebase. Under constitutional law. Evolving itself.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-9.0.0-blue?style=for-the-badge" alt="Version"/>
  <img src="https://img.shields.io/badge/Tests-4441%20Passing-brightgreen?style=for-the-badge" alt="Tests"/>
  <img src="https://img.shields.io/badge/Constitution-v0.9.0%20%E2%80%94%2023%20Rules-orange?style=for-the-badge" alt="Constitution"/>
  <img src="https://img.shields.io/badge/License-Apache%202.0-lightgrey?style=for-the-badge" alt="License"/>
  <img src="https://img.shields.io/badge/Runs%20On-Android%20%7C%20Linux%20%7C%20macOS-9C27B0?style=for-the-badge" alt="Platform"/>
  <img src="https://img.shields.io/badge/Self--Evolution-Active-red?style=for-the-badge" alt="Self-Evolution"/>
</p>

---

## The One-Paragraph Case

Every AI code tool today does the same thing: it suggests, you apply. No memory of what worked last time. No fitness score. No audit trail. No rollback. No constitutional constraint on what it can touch. You're always starting from scratch, and you're always the last line of defense.

**ADAAD is different in kind, not degree.** It is a production-grade autonomous code evolution engine that rewrites your codebase epoch by epoch — with every mutation cryptographically signed, hash-chained into an append-only ledger, deterministically replayable, and subject to a 23-rule constitutional gate before a single byte can change. It runs a 14-step governed evolution loop. It scores its own proposals against 7 fitness signals. It maintains full lineage across 5 evolutionary niches. It runs on your phone.

It has already evolved itself. That happened. It's evidenced. The hash is in the ledger.

> *"ADAAD is not a code generator. It is an autonomous software organism that governs its own evolution."*
> — Dustin L. Reid, Sole Architect, InnovativeAI LLC

---

## What Makes This Different

| Every other AI code tool | ADAAD |
|---|---|
| Suggests code, human applies | Proposes → evaluates → gates → applies atomically |
| No memory between sessions | Full lineage ledger, epoch by epoch |
| No audit trail | SHA-256 hash-chained evolution ledger, tamper-evident |
| Safety is optional, bolt-on | GovernanceGate is the **only** mutation approval surface — no bypass exists |
| Can't prove what it did | Every decision is deterministically replayable |
| Server only, enterprise-priced | Runs on a $200 Android phone, Apache 2.0 licensed |
| Human is the safety layer | Constitutional governance **is** the safety layer — humans reserved for decisions that require humans |

The gap ADAAD fills is not "can AI write code" — that's solved. The gap is: **can AI improve code in a governed, auditable, continuous, deterministic, and constitutionally constrained loop?** Before ADAAD, no.

---

## Quick Start

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
pip install -r requirements.dev.txt

# Validate your environment before anything else
PYTHONPATH=. python -m pytest tests/test_boot_preflight.py -q

# Run the full test suite (4,441 tests)
PYTHONPATH=. python -m pytest tests/ -q

# Watch a full governed evolution loop — no writes, no risk
ADAAD_CEL_ENABLED=true ADAAD_SANDBOX_ONLY=true python app/main.py
```

```python
# Check whether the Constitutional Evolution Loop is active
from runtime.evolution.cel_wiring import is_cel_enabled
print(is_cel_enabled())  # True when ADAAD_CEL_ENABLED=true
```

**Android (Pydroid3 / Termux):**
```bash
pip install -r requirements.phone.txt
CRYOVANT_DEV_MODE=1 python app/main.py --host 0.0.0.0 --port 8000
```

---

## How It Works

ADAAD runs a 14-step **ConstitutionalEvolutionLoop** (CEL). Every step executes in strict sequence — `CEL-ORDER-0` is an architectural invariant. No skipping. No shortcuts. One failure → clean halt. Zero silent errors.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ConstitutionalEvolutionLoop                          │
│                                                                         │
│  Step  1   MODEL-DRIFT-CHECK    CodeIntelModel determinism guard        │
│  Step  2   LINEAGE-SNAPSHOT     LineageEngine state hash                │
│  Step  3   FITNESS-BASELINE     FitnessEngineV2 — 7-signal baseline     │
│  Step  4   PROPOSAL-GENERATE    ProposalEngine → LLM-backed mutation    │
│  Step  5   AST-SCAN             StaticSafetyScanner — 4 hard rules      │
│  Step  6   SANDBOX-EXECUTE      Ephemeral clone execution               │
│  Step  7   REPLAY-VERIFY        Hash match — one divergence = rejection │
│  Step  8   FITNESS-SCORE        7 signals scored, all bounded           │
│  Step  9   GOVERNANCE-GATE-V2   5 diff-aware AST rules                  │
│  Step 10   GOVERNANCE-GATE      18 base constitutional rules            │
│  Step 11   LINEAGE-REGISTER     LineageEngine.register()                │
│  Step 12   PROMOTION-DECISION   CapabilityGraph + PromotionEvent        │
│  Step 13   EPOCH-EVIDENCE-WRITE Hash-chained ledger entry               │
│  Step 14   STATE-ADVANCE        Epoch counter + journal event           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Constitutional Governance

ADAAD's governance is not a safety filter bolted on the outside — **it is the execution substrate**. `GovernanceGate` is the only surface that can approve a mutation. There is no side channel. No override. No exception token that bypasses constitutional evaluation. This is written into the architecture, not just policy.

**`GOV-SOLE-0`: GovernanceGate is the sole mutation approval surface. Full stop.**

```
23 Constitutional Rules  (canonical source: runtime/governance/constitution.yaml)
│
├── GovernanceGate — 18 base rules (v0.9.0)
│   ├── Core Determinism       all decisions deterministic, replay-verifiable
│   ├── Mutation Safety        AST validity, banned tokens, patch size ceiling
│   ├── Lineage Integrity      every mutation traceable to its ancestors
│   ├── Capability Boundary    Tier-0 modules cannot self-mutate
│   └── Human Approval         HUMAN-0 gate — Tier-0 mutations require human sign-off
│
└── GovernanceGateV2 — 5 diff-aware rules
    ├── AST-SAFE-0      diff-aware syntax safety
    ├── AST-IMPORT-0    import boundary enforcement
    ├── AST-COMPLEX-0   cyclomatic complexity ceiling
    ├── SANDBOX-DIV-0   post-apply hash — divergence = auto-rollback
    └── SEMANTIC-INT-0  semantic contract integrity
```

**Eight permanent architectural invariants** — these cannot be overridden by any mutation, ever:

| Invariant | Rule |
|---|---|
| `GOV-SOLE-0` | GovernanceGate is the sole mutation approval surface |
| `DET-ALL-0` | All governance decisions are deterministic |
| `SIM-BLOCK-0` | `simulation=True` blocks all live side-effects |
| `SANDBOX-DIV-0` | AST hash must match post-apply; divergence = rollback |
| `PATCH-SIZE-0` | Max 40 delta AST nodes, max 2 files per patch |
| `TIER0-SELF-0` | Tier-0 bound modules cannot self-mutate |
| `LINEAGE-STAB-0` | Lineage stable iff ≥ 2/5 last epochs passed |
| `CEL-ORDER-0` | All 14 CEL steps execute in strict sequence; no skipping |

---

## What ADAAD Has Already Done

ADAAD executed its first fully autonomous, governed self-improvement in v9.0.0. Here is exactly what happened — every step cryptographically evidenced:

1. **CodeIntelModel** identified the highest-priority improvement target in the live codebase
2. **CapabilityTargetDiscovery** mapped it to `cap:runtime.evolution.cel_wiring.live_mode`
3. **ProposalEngine** generated an LLM-backed mutation proposal
4. **StaticSafetyScanner** cleared all four AST safety rules
5. **SandboxTournament** evaluated candidates in an ephemeral container
6. **FitnessEngineV2** scored all 7 signals — composite exceeded baseline
7. **GovernanceGateV2** approved the proposal (Class A)
8. **GovernanceGate** confirmed all 18 base constitutional rules passed
9. Patch applied atomically — replay verifier confirmed **0 divergences**
10. **CapabilityGraph** updated — `CapabilityChange` written to the capability ledger
11. **EpochEvidence** hash-chained into the evolution ledger
12. Human acknowledged the full audit trail

The cryptographic evidence bundle: `artifacts/governance/phase65/`
The hash chain: `data/checkpoint_chain.jsonl`
Replay it yourself: `python tools/verify_replay_attestation_bundle.py`

---

## The Fitness Engine — 7 Signals

Every mutation proposal is scored across 7 independent signals before GovernanceGate sees it. All weights are bounded. Determinism divergence is not a scored signal — it is an unconditional veto (`FIT-DIV-0`).

| Signal | Weight Bound |
|---|---|
| Test coverage delta + failure reduction | `[0.05, 0.70]` |
| Cyclomatic complexity delta | `[0.05, 0.70]` |
| Performance benchmark delta | `[0.05, 0.70]` |
| Governance compliance (10-epoch rolling window) | `[0.05, 0.70]` |
| Architectural fitness — coupling and centrality | `[0.05, 0.70]` |
| **Determinism — replay divergence must be 0** | `[0.05, 0.70]` — **hard floor** |
| Net node additions (deletion is rewarded) | `[0.05, 0.70]` |

Up to 12 candidates compete per epoch under BLX-alpha crossover and UCB1/Thompson bandit selection. The best-scoring proposal that clears all 23 constitutional rules gets applied. The rest are quarantined with full evidence.

---

## Autonomous on Any Device

Most AI systems require a cloud backend, an enterprise contract, and an ops team. ADAAD runs on a $200 Android phone — the full governance pipeline, the full evolution loop, the full cryptographic ledger. Zero compiled dependencies. Zero cloud required. Free.

The production FastAPI server, the Aponi governance dashboard, the telemetry pipeline, the replay verifier — all of it runs on the same hardware you carry in your pocket. The governance model does not degrade on constrained hardware; it is the same 23-rule constitution.

---

## Repository Structure

```
runtime/
├── governance/                     Constitutional gate — 23 rules, policy artifacts
├── evolution/
│   ├── cel_wiring.py               CEL activation — is_cel_enabled(), build_cel()
│   ├── constitutional_evolution_loop.py  14-step LiveWiredCEL
│   ├── proposal_engine.py          LLM-augmented mutation proposals
│   ├── fitness_v2.py               FitnessEngineV2 — 7 bounded signals
│   ├── lineage_v2.py               LineageLedgerV2 — SHA-256 hash-chained
│   └── replay_attestation.py       HMAC-signed replay proofs
├── mutation/
│   ├── code_intel/                 CodeIntelModel — FunctionGraph, HotspotMap
│   └── ast_substrate/              ASTDiffPatch, StaticSafetyScanner, SandboxTournament
├── capability_graph.py             CapabilityGraph + CapabilityChange ledger
└── tools/mutation_guard.py         DNA mutation executor — upsert, auto-vivify, checksum

app/main.py                         Deterministic orchestrator entrypoint
artifacts/governance/               Cryptographic evidence bundles — human-signed
data/checkpoint_chain.jsonl         Append-only hash-chained evolution ledger
tests/                              4,441 tests
docs/
├── CONSTITUTION.md                 Constitutional rules, amendment log, invariants
├── governance/ARCHITECT_SPEC_v8.0.0.md   Authoritative architecture specification
└── ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md  Roadmap and hardening agenda
```

---

## Defensibility

ADAAD's strategic moat is not a product feature — it is a tightly-integrated architecture that cannot be reproduced by assembling off-the-shelf components.

**Evidence infrastructure.** Every mutation in ADAAD history is cryptographically evidenced. SHA-256 hash-chained ledger, replay attestation bundles, governance sign-off artifacts, EpochEvidence records. In regulated industries — fintech, healthcare, defense — this evidence infrastructure is worth more than the mutation engine itself.

**Compliance positioning.** As AI code generation becomes ubiquitous, regulatory pressure on software audit trails will increase. ADAAD is years ahead of the compliance curve. The answer to "why did this change happen, who approved it, and can you prove it?" is a cryptographic proof chain with deterministic replay.

**Earned autonomy, not assumed.** The architecture enforces that autonomy cannot be granted — it must be earned through demonstrated, evidenced stability. Each expansion of what ADAAD can do is matched by a deepening of what it cannot do without consent. This is the correct model for deploying AI autonomy in high-stakes environments.

---

## Governance Audit Trail

All human sign-offs are cryptographically recorded. The governance ledger is append-only and tamper-evident.

| Gate | Status | Evidence |
|---|---|---|
| Capability Registry v2 | ✅ SIGNED | `artifacts/governance/phase59/` |
| GovernanceGateV2 rules | ✅ SIGNED | `artifacts/governance/phase63/` |
| CEL dry-run | ✅ SIGNED | `artifacts/governance/phase64/` |
| Mutation target selection | ✅ SIGNED | `artifacts/governance/phase65/` |
| v9.0.0 release audit | ✅ SIGNED | `artifacts/governance/phase65/v9_release_audit_report.json` |
| Replay verification | ✅ SIGNED | `artifacts/governance/phase65/v9_replay_verification.json` |

```bash
# Replay the evidence chain yourself
python tools/verify_replay_attestation_bundle.py

# Audit approval/rejection rates and agent performance
python tools/adaad_audit.py
```

---

## Who Built This

**InnovativeAI LLC** — Blackwell, Oklahoma.
**Dustin L. Reid** — Sole Architect.

Built with zero outside funding. Every phase of this architecture was designed, implemented, tested, and governed by one person. The build history — with each release adding a precisely scoped capability to a tightly governed architecture — is itself a defensibility asset.

ADAAD demonstrates that **autonomous capability and constitutional governance are synergistic, not adversarial.** The faster and more capable the mutation engine becomes, the more essential the governance layer is — and the more valuable the architecture becomes.

---

<p align="center">
  <i>v9.0.0 — Apache 2.0 — InnovativeAI LLC — Blackwell, Oklahoma</i><br/>
  <a href="https://github.com/InnovativeAI-adaad/ADAAD">github.com/InnovativeAI-adaad/ADAAD</a>
</p>
