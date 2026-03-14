<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/adaad-hero.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/adaad-hero.svg">
  <img src="docs/assets/adaad-hero.svg" width="100%" alt="ADAAD — Autonomous Device-Anchored Adaptive Development"/>
</picture>

<br/><br/>

[![Version](https://img.shields.io/badge/ADAAD-v9.1.0-000?style=for-the-badge&labelColor=0d1117&color=00d4ff)](https://github.com/InnovativeAI-adaad/ADAAD/releases)&nbsp;[![Self-Evolution](https://img.shields.io/badge/◈_Self--Evolution-ACTIVE-000?style=for-the-badge&labelColor=0d1117&color=ff4466)](ROADMAP.md)&nbsp;[![Constitution](https://img.shields.io/badge/Constitution-v0.9.0_—_23_Rules-000?style=for-the-badge&labelColor=0d1117&color=f5c842)](docs/CONSTITUTION.md)&nbsp;[![License](https://img.shields.io/badge/License-Apache_2.0-000?style=for-the-badge&labelColor=0d1117&color=a855f7)](LICENSE)

<br/>

[![CI](https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml/badge.svg)](https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml)&nbsp;![Tests](https://img.shields.io/badge/4%2C441_Tests-Passing-00ff88?style=flat-square&labelColor=0d1117)&nbsp;![Phases](https://img.shields.io/badge/66_Phases-Complete-00d4ff?style=flat-square&labelColor=0d1117)&nbsp;![GovernanceGate](https://img.shields.io/badge/GovernanceGate-Non--Bypassable-f5c842?style=flat-square&labelColor=0d1117)&nbsp;![Determinism](https://img.shields.io/badge/Replay-Zero_Divergence-00ff88?style=flat-square&labelColor=0d1117)&nbsp;![Platform](https://img.shields.io/badge/Android_%7C_Linux_%7C_macOS-Supported-9966ff?style=flat-square&labelColor=0d1117)

<br/>

![Evolved](https://img.shields.io/badge/⛓_First_Autonomous_Evolution-March_13%2C_2026_—_Hash_In_Ledger-ff4466?style=flat-square&labelColor=100005)&nbsp;&nbsp;![Phone](https://img.shields.io/badge/📱_Runs_On-A_$200_Android_Phone-00ff88?style=flat-square&labelColor=001500)&nbsp;&nbsp;![Replay](https://img.shields.io/badge/🔐_Every_Decision-Deterministically_Replayable-00d4ff?style=flat-square&labelColor=001520)

<br/><br/>

**[⚡ 5-Minute Quickstart](QUICKSTART.md)** &nbsp;·&nbsp; **[📜 The 23 Rules](docs/CONSTITUTION.md)** &nbsp;·&nbsp; **[🗺 Full Roadmap](ROADMAP.md)** &nbsp;·&nbsp; **[🤖 Agent Spec](AGENTS.md)** &nbsp;·&nbsp; **[📱 Android Setup](INSTALL_ANDROID.md)** &nbsp;·&nbsp; **[🔬 Examples](examples/)** &nbsp;·&nbsp; **[📊 Aponi Dashboard](ui/)**

</div>

<br/>

---

## In One Sentence

> **ADAAD is a production-grade code evolution engine that improves your codebase epoch by epoch — every mutation cryptographically signed, hash-chained into a tamper-evident ledger, deterministically replayable, and subject to 23 constitutional rules before a single byte changes.**

*It has already evolved itself. The hash is in the ledger.*

---

## Why This Exists

Every AI code tool does the same thing: **suggest → you apply.**

No memory of what worked. No fitness score. No audit trail. No rollback. No constitutional constraint on what it can touch. **You are always the last line of defense.**

ADAAD inverts this. The `GovernanceGate` is the last line of defense — not you. You set the constitution. The system enforces it, epoch by epoch, with cryptographic proof at every step.

> [!IMPORTANT]
> **Different in kind, not degree.** ADAAD does not assist. It does not suggest. It proposes, evaluates, gates, and applies. It runs a 14-step governed loop. It scores mutations against 7 fitness signals. It produces a hash-chained evidence ledger you can replay byte-for-byte. It runs on a $200 Android phone. Apache 2.0. Free forever.

---

## ADAAD vs. Everything Else

<table>
<thead>
<tr>
<th align="left">Capability</th>
<th align="center">Copilot / Cursor</th>
<th align="center">Devin / SWE-agent</th>
<th align="center">ADAAD</th>
</tr>
</thead>
<tbody>
<tr>
<td>Mutation model</td>
<td align="center">Suggest → human applies</td>
<td align="center">Autonomous PR creation</td>
<td align="center">✅ Propose → Gate → Apply <strong>atomically</strong></td>
</tr>
<tr>
<td>Safety architecture</td>
<td align="center">Human reviews</td>
<td align="center">Human reviews</td>
<td align="center">✅ <code>GovernanceGate</code> — constitutional, non-bypassable</td>
</tr>
<tr>
<td>Audit trail</td>
<td align="center">Git history only</td>
<td align="center">PR descriptions</td>
<td align="center">✅ SHA-256 hash-chained evidence ledger, tamper-evident</td>
</tr>
<tr>
<td>Replay proof</td>
<td align="center">❌</td>
<td align="center">❌</td>
<td align="center">✅ <code>replay_verifier.py</code> — byte-identical, zero-divergence enforced</td>
</tr>
<tr>
<td>Fitness scoring</td>
<td align="center">❌</td>
<td align="center">❌</td>
<td align="center">✅ 7-signal engine — adaptive weights from post-merge telemetry</td>
</tr>
<tr>
<td>Self-evolution</td>
<td align="center">❌</td>
<td align="center">Partial</td>
<td align="center">✅ Phase 65 — proven, hash in ledger, March 13 2026</td>
</tr>
<tr>
<td>Runs on $200 phone</td>
<td align="center">❌</td>
<td align="center">❌</td>
<td align="center">✅ Full Android support — Termux + Pydroid3</td>
</tr>
<tr>
<td>Pricing</td>
<td align="center">$10–19/mo</td>
<td align="center">$500+/mo</td>
<td align="center">✅ Apache 2.0 — free forever</td>
</tr>
<tr>
<td>Cross-repo mutation</td>
<td align="center">❌</td>
<td align="center">Limited</td>
<td align="center">✅ Federation — HMAC-gated, dual-gate governed</td>
</tr>
<tr>
<td>Memory between runs</td>
<td align="center">❌</td>
<td align="center">Limited</td>
<td align="center">✅ Full lineage ledger — epoch by epoch, SHA-256 hash-chained</td>
</tr>
</tbody>
</table>

---

## Live System Status

<div align="center">

| System | Status | Invariant | Phase Introduced |
|:---:|:---:|:---:|:---:|
| 🟢 GovernanceGate | **ACTIVE** | `GOV-SOLE-0` | Phase 1 |
| 🟢 Constitutional Evolution Loop | **14-STEP** | `CEL-ORDER-0` | Phase 64 |
| 🟢 Evidence Ledger | **HASH-CHAINED** | `CEL-EVIDENCE-0` | Phase 1 |
| 🟢 FitnessEngine v2 | **7 SIGNALS** | `FIT-BOUND-0` | Phase 62 |
| 🟢 SandboxTournament | **OPERATIONAL** | `SANDBOX-DIV-0` | Phase 60 |
| 🟢 Deterministic Replay | **ZERO DIVERGENCE** | `DET-ALL-0` | Phase 1 |
| 🟢 AdaptiveWeights | **EMA LIVE** | `FIT-DIV-0` | Phase 3 |
| 🟢 Federation | **HMAC-GATED** | `federation_dual_gate` | Phase 5 |
| 🟢 CodeIntelModel | **SCANNING** | `INTEL-DET-0` | Phase 58 |
| 🟢 Autonomous Self-Evolution | **PHASE 65 PROVEN** | `MUTATION-TARGET` | Phase 65 |

</div>

---

## Architecture

<div align="center">
<img src="docs/assets/adaad-architecture.svg" width="100%" alt="ADAAD System Architecture"/>
</div>

<br/>

Three LLM-backed agents — **Architect**, **Dream**, **Beast** — compete for epoch selection via UCB1 bandit algorithm. Every winning proposal traverses the full **14-step Constitutional Evolution Loop** before a single byte changes. The `GovernanceGate` is the sole approval surface. Invariant `GOV-SOLE-0`: it cannot be bypassed. Ever. Not by configuration. Not by flag. Not by runtime override.

<div align="center">
<img src="docs/assets/adaad-flow.svg" width="100%" alt="ADAAD Mutation Flow"/>
</div>

---

## The Constitutional Evolution Loop

All 14 steps execute in strict sequence. One failure → clean halt. Zero silent errors. Architectural invariant: **`CEL-ORDER-0`**.

<div align="center">

| Step | Name | Type | Failure Mode |
|:---:|:---|:---:|:---|
| `01` | `MODEL-DRIFT-CHECK` | Guard | Blocks epoch if determinism stale |
| `02` | `LINEAGE-SNAPSHOT` | Capture | Records `capability_graph_before` hash |
| `03` | `FITNESS-BASELINE` | Measure | Pre-epoch 7-signal composite score |
| `04` | `PROPOSAL-GENERATE` | Generate | LLM mutations — Architect / Dream / Beast agents |
| `05` | `AST-SCAN` | Preflight | StaticSafetyScanner — 4 hard AST rules |
| `06` | `SANDBOX-EXECUTE` | Test | Ephemeral clone — respects `SANDBOX_ONLY` |
| `07` | `REPLAY-VERIFY` | Verify | Hash match — any divergence = auto-rollback |
| `08` | `FITNESS-SCORE` | Score | 7 signals — determinism divergence = unconditional veto |
| `09` | `GOVERNANCE-GATE-V2` | Gate | 5 diff-aware AST rules (Phase 63) |
| `10` | `GOVERNANCE-GATE` | Gate | **23 constitutional rules — ALL must pass** |
| `11` | `LINEAGE-REGISTER` | Register | Survivors chained into lineage record |
| `12` | `PROMOTION-DECISION` | Promote | `CapabilityGraph` + `PromotionEvent` — skipped in `SANDBOX_ONLY` |
| `13` | `EPOCH-EVIDENCE` | Seal | SHA-256 hash-chained ledger entry written |
| `14` | `STATE-ADVANCE` | Advance | Epoch counter advanced — emit `epoch_complete.v1` |

</div>

```
SANDBOX_ONLY=true  ──────────────►  Full 14 steps execute
                                     Proposals evaluated
                                     Fitness scored
                                     Gate checked
                                     ─── NO patch applied ─── zero risk
                                     Perfect for first run
```

---

## Three Competing Mutation Agents

<div align="center">
<img src="docs/assets/adaad-agents.svg" width="100%" alt="ADAAD Agent Competition"/>
</div>

<br/>

<table>
<tr>
<td align="center" width="33%">

### 🏛 ARCHITECT

**Methodical · Conservative · Structural**

Low entropy delta proposals. High governance compliance history. Favors complexity reduction and test improvements. The safe bet.

*Best epoch role:* Stabilization runs, post-incident hardening, Tier-0 adjacent patches.

</td>
<td align="center" width="33%">

### 💭 DREAM

**Creative · Exploratory · Novel**

High novelty score proposals. Explores non-obvious mutation pathways. Higher variance — rewarded when it works, filtered when it doesn't.

*Best epoch role:* Capability expansion, architectural refactors, discovery epochs.

</td>
<td align="center" width="33%">

### ⚡ BEAST

**Aggressive · High-throughput · Hard-filtered**

Volume + velocity. Generates the most candidates per epoch. GovernanceGate filters heavily — but the best Beast proposals are often the highest composite-scoring.

*Best epoch role:* Test suite improvement, documentation mutation, low-risk high-breadth epochs.

</td>
</tr>
</table>

<br/>

All three compete via **UCB1 multi-armed bandit** (switches to Thompson Sampling after ≥30 epochs of non-stationary reward). Up to **12 candidates per epoch** via BLX-alpha genetic crossover. The GovernanceGate decides. The bandit learns from the outcome.

---

## The 23 Constitutional Rules

<details>
<summary><strong>🔴 9 Blocking Rules — Unconditional rejection. No exceptions. No overrides.</strong></summary>

<br/>

A single blocking violation halts the epoch immediately. The patch is discarded. No partial application. No retry without a clean re-proposal.

| Rule | What It Enforces |
|:---|:---|
| `single_file_scope` | Mutations confined to a single target file — no scope creep |
| `ast_validity` | Resulting AST must parse cleanly — no syntax errors of any kind |
| `no_banned_tokens` | No `exec`, `eval`, `os.system`, subprocess shell equivalents |
| `signature_required` | Every mutation must carry a valid cryptographic signature |
| `lineage_continuity` | Mutation must chain to an existing, valid lineage record |
| `resource_bounds` | Memory and compute bounds enforced per mutation tier |
| `federation_dual_gate` | Cross-repo mutations require `GovernanceGate` approval in both source and destination |
| `federation_hmac_required` | HMAC key validation required for all federation channel operations |
| `soulbound_privacy_invariant` | No identity-linked data exported outside governed channels |

</details>

<details>
<summary><strong>🟡 5 Warning Rules — Flag and continue in Tier 1/2. Blocking in PRODUCTION (Tier 0).</strong></summary>

<br/>

| Rule | Threshold |
|:---|:---|
| `max_complexity_delta` | Cyclomatic complexity delta ≤ +2 |
| `test_coverage_maintained` | Coverage must not decrease — delta ≥ 0 |
| `max_mutation_rate` | Epoch mutation density within anti-flood rate bounds |
| `import_smoke_test` | All new imports must resolve at import time |
| `entropy_budget_limit` | Proposal entropy within deterministic bounds |

</details>

<details>
<summary><strong>🔵 9 Advisory Rules — Informational. Captured in all audit trails and evidence bundles.</strong></summary>

<br/>

| Rule | What It Tracks |
|:---|:---|
| `deployment_authority_tier` | Tier-based deployment authority verification |
| `revenue_credit_floor` | Credit floor enforcement for contributor attribution |
| `reviewer_calibration` | Historical reviewer calibration score tracking |
| `bandit_arm_integrity_invariant` | UCB1 / Thompson Sampling internal state consistency |
| `market_signal_integrity_invariant` | Market signal provenance and freshness |
| `gate_v2_complexity` | GovernanceGateV2 AST complexity diff (Phase 63) |
| `gate_v2_import_surface` | GovernanceGateV2 import surface delta (Phase 63) |
| `gate_v2_error_guard` | GovernanceGateV2 error guard preservation (Phase 63) |
| `gate_v2_semantic_scope` | GovernanceGateV2 semantic scope adherence (Phase 63) |

</details>

---

## 8 Permanent Architectural Invariants

Enforced at the **code level**, not the policy level. No mutation, no configuration, no runtime flag, no environment variable can override these. They are structural — not advisory.

```yaml
# ─── ADAAD ARCHITECTURAL INVARIANTS  ·  v9.1.0  ────────────────────────────────
#     Source of truth: docs/CONSTITUTION.md
#     Enforcement: code-level  ·  Override: structurally impossible
#     Audit: every invariant violation produces a blocking ledger entry
# ─────────────────────────────────────────────────────────────────────────────────

GOV-SOLE-0:      GovernanceGate is the sole mutation approval surface.
                 No bypass path exists. No config flag. No env override.
                 Invariant: code-level.

DET-ALL-0:       All governance decisions are deterministic.
                 Identical inputs → identical byte-identical output, always.
                 Divergence = automatic epoch halt.

SIM-BLOCK-0:     simulation=True blocks ALL live side-effects.
                 Zero bleed to production. Structural, not advisory.

SANDBOX-DIV-0:   AST hash must match post-apply.
                 Any divergence = automatic rollback + blocking ledger entry.
                 Not a threshold. Zero divergence. Always.

PATCH-SIZE-0:    Maximum 40 delta AST nodes.
                 Maximum 2 files per patch. Hard ceiling.

TIER0-SELF-0:    Tier-0 bound modules cannot self-mutate.
                 Ever. Under any condition. Regardless of GovernanceGate outcome.

LINEAGE-STAB-0:  Lineage stable iff ≥ 2/5 last epochs passed fitness + gate.
                 Unstable lineage = promotion blocked, regardless of current score.

CEL-ORDER-0:     All 14 CEL steps execute in strict declared sequence.
                 No step may be skipped. No step may be reordered.
                 Single failure = clean halt. Zero silent errors.
```

---

## Fitness Engine — 7 Signals

Every mutation proposal is scored across 7 independent signals before the `GovernanceGate` evaluates it. **Determinism divergence is an unconditional veto (`FIT-DIV-0`)** — it does not participate in scoring and cannot be overridden by weight adjustments under any circumstances.

<div align="center">

| Signal | Weight Range | Veto Condition |
|:---|:---:|:---|
| 🧪 **Test delta** — coverage increase + failure reduction | `[0.05, 0.70]` | — |
| 🌀 **Complexity delta** — cyclomatic change | `[0.05, 0.70]` | — |
| ⚡ **Performance delta** — runtime benchmark | `[0.05, 0.70]` | — |
| 📊 **Governance compliance** — 10-epoch rolling track record | `[0.05, 0.70]` | — |
| 🏗 **Architectural fitness** — coupling + module centrality | `[0.05, 0.70]` | — |
| 🔒 **Determinism** — replay divergence measurement | `[0.05, 0.70]` | **ANY divergence = unconditional epoch halt** |
| 🧹 **Node economy** — net AST additions (deletions rewarded) | `[0.05, 0.70]` | — |

</div>

**`AdaptiveWeights` (Phase 3):** EMA momentum descent (LR=0.05) adjusts signal weights from post-merge telemetry. Weights are bounded `[0.05, 0.70]` — no signal dominates, no signal becomes irrelevant. `NonStationarityDetector` (Page-Hinkley test) switches to Thompson Sampling automatically after ≥30 epochs of detected reward non-stationarity.

```
Each epoch:
  score = Σ (signal_value[i] × adaptive_weight[i])   for i in 7 signals
  if determinism_divergence > 0:  → VETO (unconditional, cannot be overridden)
  if score < baseline:            → REJECT
  if gate_v2 FAIL:                → REJECT
  if gate_base FAIL:              → REJECT
  → APPROVED — proceed to PROMOTION-DECISION
```

---

## Mutation Tier System

<div align="center">

| Tier | Scope | Autonomous Authority | Review Required |
|:---|:---|:---:|:---|
| 🔴 **Tier 0 — Production** | `runtime/`, `security/`, `app/main.py`, governance | ❌ **Never autonomous** | Human required before any merge |
| 🟡 **Tier 1 — Stable** | `tests/`, `docs/`, most agents, schemas | ✅ Auto + full audit trail | Human reviews ledger within 24h |
| 🟢 **Tier 2 — Sandbox** | `app/agents/test_subject/` only | ✅ Fully autonomous | Zero blast radius to other tiers |

</div>

`TIER0-SELF-0` is a permanent architectural invariant. Tier-0 modules cannot be mutation targets under any conditions — not via configuration, not via exception token, not via governance override. The invariant is structural.

---

## Federation — Cross-Repo Governed Evolution

ADAAD mutations can propagate across repositories via the **FederationMutationBroker** (Phase 5). Every federated mutation requires:

1. `GovernanceGate` approval in the **source** repository
2. `GovernanceGate` approval in the **destination** repository
3. HMAC key validation on the federation channel (`federation_hmac_required` — blocking rule)
4. `FederatedEvidenceMatrix` — zero cross-repo divergence count before promotion

```
Source Repo                    Federation Channel              Destination Repo
─────────────                  ──────────────────              ────────────────
ProposalEngine                 HMAC-validated                  ProposalTransport
     ↓                         encrypted tunnel                      ↓
GovernanceGate ─────────────────────────────────────────► GovernanceGate
     ↓                                                           ↓
EvidenceMatrix ◄──────── cross-repo divergence check ──────► EvidenceMatrix
     ↓                   divergence_count must == 0              ↓
EvolutionLedger                                           EvolutionLedger
```

Constitutional invariant: `federation_dual_gate` — a blocking rule. Cross-repo mutations that bypass either gate are structurally impossible.

---

## The Aponi Dashboard

**Aponi** is the ADAAD observability and governance console — a Python + HTML dashboard that surfaces the live state of the evolution loop.

```
┌─────────────────────────────────────────────────────────┐
│  APONI  ·  Governance Console  ·  ADAAD v9.1.0          │
│─────────────────────────────────────────────────────────│
│  Evolution Loop    ● ACTIVE     Epoch 847               │
│  GovernanceGate    ● ENFORCING  23 rules / 0 bypasses   │
│  Evidence Ledger   ● LIVE       12,441 entries          │
│  Active Agents     ● 3/3        Architect Dream Beast   │
│  Current Phase     ● SANDBOX    TIER-1 target           │
│─────────────────────────────────────────────────────────│
│  Last Epoch Result:  APPROVED  ·  Class A  ·  +2 tests  │
│  Fitness Composite:  0.74      ·  above baseline: ✓     │
│  Replay Hash:        a3f8e9... ·  divergences: 0        │
└─────────────────────────────────────────────────────────┘
```

The Aponi dashboard is where HUMAN-0 gates are exercised. For Phase 65, the Aponi console displayed the full 12-step audit trail — the human acknowledgement hash was committed from this interface.

Start Aponi: `PYTHONPATH=. python -m ui.aponi --port 8080`

---

## Security — Cryovant

**Cryovant** is the ADAAD authentication, key management, and session governance layer.

> [!WARNING]
> `ADAAD_ENV` must be explicitly set before boot. Unset → `assert_env_mode_set()` fails closed with `adaad_env_unset:critical`. This is the **first boot invariant** — it fires before governance key validation.

```bash
# Required env declarations
export ADAAD_ENV=dev          # dev | staging | production
export CRYOVANT_DEV_MODE=1    # bypass governance keys in dev (no production use)

# Production: governance signing key required
export GOVERNANCE_SIGNING_KEY="$(cat /path/to/key.pem)"
```

Key principles:
- `SIM-BLOCK-0` — `simulation=True` blocks all live side-effects at the structural level
- All mutations cryptographically signed before `GovernanceGate` evaluation
- HMAC keys required for all federation operations
- Boot preflight validates environment before any mutation activity begins

---

## ⛓ Phase 65 — First Autonomous Self-Evolution

<div align="center">
<img src="docs/assets/adaad-phase65-banner.svg" width="100%" alt="Phase 65 — First Autonomous Self-Evolution"/>
</div>

<br/>

*March 13, 2026. Zero human intervention in the execution path. Full human oversight of the constitutional framework. Every step cryptographically evidenced.*

<details>
<summary><strong>View full Phase 65 evidence ledger entry</strong></summary>

<br/>

```json
{
  "event":   "EPOCH_COMPLETE",
  "phase":   65,
  "version": "9.0.0",
  "date":    "2026-03-13",
  "ledger":  "artifacts/governance/phase65/",

  "constitutional_invariants_enforced": [
    "MUTATION-TARGET", "AUDIT-0",   "REPLAY-0",
    "CEL-ORDER-0",     "CEL-EVIDENCE-0", "SANDBOX-DIV-0",
    "GATE-V2-EXISTING-0"
  ],

  "execution_trace": {
    "01_TARGET_DISCOVERY":   "✓ CodeIntelModel → highest-priority Tier-1 capability identified",
    "02_CAPABILITY_MAP":     "✓ CapabilityDiscovery → cap:runtime.evolution.cel_wiring.live_mode",
    "03_PROPOSAL_GENERATE":  "✓ ProposalEngine → AST-level mutation — proposal_hash recorded",
    "04_STATIC_SCAN":        "✓ StaticSafetyScanner → all 4 AST safety rules PASS",
    "05_SANDBOX_TOURNAMENT": "✓ SandboxTournament → top candidate ID in ephemeral container",
    "06_FITNESS_SCORE":      "✓ FitnessEngineV2 → 7/7 signals above baseline — composite PASS",
    "07_GOVERNANCE_GATE_V2": "✓ GovernanceGateV2 → APPROVED (Class A — no exception token)",
    "08_GOVERNANCE_GATE":    "✓ GovernanceGate → CONFIRMED — all 23 constitutional rules pass",
    "09_PATCH_APPLY":        "✓ ASTDiffPatch → applied atomically — replay_verifier: 0 divergences",
    "10_CAPABILITY_UPDATE":  "✓ CapabilityGraph → target node bumped, CapabilityChange to ledger",
    "11_EPOCH_EVIDENCE":     "✓ EpochEvidence → SHA-256 hash-chained into evolution ledger",
    "12_HUMAN_OVERSIGHT":    "✓ Full audit trail reviewed in Aponi — acknowledgement hash committed"
  },

  "proof": {
    "replay_divergences":   0,
    "governance_bypasses":  0,
    "retroactive_evidence": false,
    "silent_failures":      0
  }
}
```

</details>

---

## Quick Start

<table>
<tr>
<td width="50%">

**Server / Desktop / CI**

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.server.txt

# Boot preflight — always run first
PYTHONPATH=. python -m pytest tests/test_boot_preflight.py -q

# Full 4,441-test suite
PYTHONPATH=. python -m pytest tests/ -q

# Safe dry-run — zero writes, full CEL
ADAAD_CEL_ENABLED=true \
ADAAD_SANDBOX_ONLY=true \
ADAAD_ENV=dev \
python app/main.py
```

</td>
<td width="50%">

**Android — Termux / Pydroid3**

```bash
pip install -r requirements.phone.txt

# Dev mode — explore without governance keys
CRYOVANT_DEV_MODE=1 \
ADAAD_ENV=dev \
python app/main.py --host 0.0.0.0 --port 8000
```

**Aponi Dashboard**

```bash
# Governance console on any device
PYTHONPATH=. python -m ui.aponi --port 8080
# Open: http://localhost:8080
```

</td>
</tr>
</table>

> [!TIP]
> **Always start with `ADAAD_SANDBOX_ONLY=true`.** The full 14-step CEL executes — proposals evaluated, fitness-scored, gate-checked — but no patch is applied. Zero risk. Complete observability. Identical audit trail.

> [!NOTE]
> Full guides: **[QUICKSTART.md](QUICKSTART.md)** · **[INSTALL_ANDROID.md](INSTALL_ANDROID.md)** · **[PHONE_SETUP.md](PHONE_SETUP.md)** · **[TERMUX_SETUP.md](TERMUX_SETUP.md)**

---

## DEVADAAD — The Governed Build Agent

ADAAD ships with a first-class build agent protocol. Use `ADAAD` or `DEVADAAD` as trigger tokens when working with Claude (or any LLM following [AGENTS.md](AGENTS.md)):

| Trigger | Effect |
|:---|:---|
| `ADAAD` | Execute governed build workflow — stages work for human review, **no merge** |
| `DEVADAAD` | Build + operator-authorized merge — all `ADAAD` constraints apply |
| `ADAAD status` | Orientation report — no build action |
| `ADAAD preflight` | Preflight checks only — no new code |
| `ADAAD audit` | Surface all open findings from `.adaad_agent_state.json` |
| `ADAAD verify` | Full verify stack against current state — no new code |

> [!CAUTION]
> `DEVADAAD` grants merge authority. First word of prompt must be `DEVADAAD` exactly. All governance constraints apply in full — `GovernanceGate`, `HUMAN-0` gates, GPG-signed squash merges. The only additional capability over `ADAAD` is merge execution.

---

## Phase Timeline — 66 Phases Complete

<details>
<summary><strong>View complete phase history (v1.0 → v9.1.0)</strong></summary>

<br/>

| Phase Range | Theme | Key Deliverables | Version |
|:---|:---|:---|:---:|
| **1–2** | Foundation | `GovernanceGate`, Evidence Ledger, SHA-256 hash-chaining, deterministic replay | v1.0 |
| **3–4** | Adaptive Intelligence | `AdaptiveWeights` EMA descent, `SemanticDiffEngine` AST analysis | v2.x |
| **5–6** | Federation & Autonomy | Multi-repo federation, HMAC gating, roadmap self-amendment | v3.x |
| **7–8** | Governance Calibration | Reviewer reputation, governance health dashboard, telemetry unification | v3.2–3.3 |
| **9–20** | Core Hardening | Admission control, rate limiting, entropy baselines, audit gap closure | v4.x |
| **21–30** | Evidence & Lineage | Gate decision ledger, lineage stability, compatibility graph | v5.x |
| **31–40** | Scale & Resilience | Bandit integrity, memory governance, Cryovant auth, Aponi dashboard | v6.x |
| **41–50** | SPA & Infrastructure | Cryovant gate middleware, defect sweep, federation hardening | v7.x–8.x |
| **51–56** | Intelligence Layer | Memory governance, learning signal isolation, `MEMORY-0` invariant | v8.x |
| **57** | Keystone | ProposalEngine auto-provisioning | v8.0 |
| **58** | Perception | CodeIntelModel — code intelligence layer | v8.1 |
| **59** | Identity | CapabilityGraph v2 + CapabilityTargetDiscovery | v8.2 |
| **60** | Motor | AST Mutation Substrate + SandboxTournament | v8.3 |
| **61** | Evolution | Lineage Engine + CompatibilityGraph | v8.4 |
| **62** | Intelligence | MultiHorizon FitnessEngine v2 | v8.5 |
| **63** | Judgment | GovernanceGate v2 + Exception Tokens | v8.6 |
| **64** | Selfhood | Constitutional Evolution Loop (CEL) + EpochEvidence | v8.7 |
| **65** | **Emergence** ⛓ | **First Autonomous Self-Evolution — March 13, 2026** | **v9.0** |
| **66** | Foundation Hardening | Audit gap closure, boot validation, API hardening | **v9.1** |

</details>

---

## Codebase at a Glance

<div align="center">

| Metric | Value |
|:---|:---|
| **Version** | `9.1.0` — Phase 66: Foundation Hardening |
| **Runtime Python files** | 329 |
| **Test files** | 267 |
| **Total test lines** | ~37,000 |
| **Passing tests** | **4,441** |
| **Constitutional rules** | **23** — Constitution v0.9.0 |
| **Architectural invariants** | **8** — code-level, non-overridable |
| **Development phases** | **66** complete |
| **Governance phases** | v0 → v0.9.0 constitution evolution |
| **Android support** | Full — Termux + Pydroid3 |
| **Federation** | Multi-repo HMAC-gated (Phase 5) |
| **First autonomous self-evolution** | ✅ Phase 65 — March 13, 2026 |
| **Self-evolution proof** | SHA-256 hash-chained, replayable |

</div>

---

## Governance Authority Chain

```
docs/CONSTITUTION.md                       ← 23 rules · v0.9.0
    └─► docs/ARCHITECTURE_CONTRACT.md      ← structural constraints
            └─► ARCHITECT_SPEC_v9.x.md     ← implementation spec
                    └─► ADAAD_PR_PROCESSION_2026-03-v2.md
                                │
                                ▼
                    ╔═══════════════════════════╗
                    ║     GovernanceGate         ║
                    ║  23 rules · GOV-SOLE-0     ║
                    ║  Non-bypassable            ║
                    ║  Every mutation            ║
                    ║  Every epoch               ║
                    ╚═══════════════════════════╝
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        Evidence Ledger   CapabilityGraph    LineageLedger
        (SHA-256 chain)   (version graph)    (stability)
```

The constitution is the root. The `GovernanceGate` is the sole enforcement surface. Nothing merges without passing through it.

---

## Project Structure

```
ADAAD/
├── app/                   # Orchestrator, agents, mutation cycle, FastAPI server
│   └── agents/            # Architect / Dream / Beast agent implementations
├── runtime/               # Core engine — the constitutional machine
│   ├── evolution/         # CEL, lineage ledger, fitness engine, replay verifier
│   ├── governance/        # GovernanceGate (23 rules), federation, rate limiting
│   ├── autonomy/          # Bandit selector, AdaptiveWeights, NonStationarityDetector
│   ├── mutation/          # AST substrate, SandboxTournament, CodeIntelModel
│   └── sandbox/           # Ephemeral container execution, preflight checks
├── security/              # Cryovant — auth, key management, session governance
├── tests/                 # 267 test files · 4,441 passing
├── docs/                  # Architecture docs, constitution, governance specs
│   └── assets/            # SVG diagrams and visual assets
├── governance/            # Constitutional rules, federation keys, attestations
├── schemas/               # JSON schemas for all governance artifacts
├── artifacts/             # Per-phase evidence artifacts (immutable after phase close)
├── tools/                 # Linters, audit tools, import boundary enforcement
├── scripts/               # CI/CD, retention enforcement, signing scripts
├── ui/                    # Aponi dashboard — governance console (Python + HTML)
├── android/               # Android build, F-Droid, Play Store assets
├── _inbox/                # Working documents, proposals (non-canonical)
├── QUICKSTART.md          # 5-minute setup guide
├── AGENTS.md              # Build agent protocol spec (ADAAD / DEVADAAD)
├── ROADMAP.md             # Full phase roadmap through Q2 2027
└── docs/CONSTITUTION.md   # The 23 rules — the root of authority
```

---

## Frequently Asked Questions

<details>
<summary><strong>Is ADAAD safe to run on a production codebase?</strong></summary>

<br/>

Start with `ADAAD_SANDBOX_ONLY=true` and `ADAAD_ENV=dev`. In sandbox mode the full 14-step CEL runs — proposals are evaluated, scored, and gate-checked — but no patch is ever applied. You get the complete audit trail without any codebase changes.

When you're ready to apply patches: use `Tier 2` (sandbox paths only) for first live runs. `Tier 0` (production runtime) requires human sign-off before any mutation. Constitutional invariant `TIER0-SELF-0` means core modules cannot be self-mutated under any conditions.

</details>

<details>
<summary><strong>What does "deterministically replayable" mean in practice?</strong></summary>

<br/>

Every governance decision is byte-identical given identical inputs. `replay_verifier.py` takes any committed mutation SHA, re-executes the full 14-step CEL with the original inputs, and verifies the output hash matches. Zero divergence is the only acceptable result — `SANDBOX-DIV-0` mandates this. Any divergence triggers automatic rollback.

This means you can audit any past epoch with complete fidelity. The ledger is not just a log — it's a replayable proof.

</details>

<details>
<summary><strong>What is a "Class A" vs "Class B" mutation?</strong></summary>

<br/>

`GovernanceGateV2` classifies mutations by AST complexity delta:

- **Class A** — cyclomatic delta ≤ +2. Approved automatically if all other rules pass.
- **Class B** — cyclomatic delta > +2. Requires an exception token **and** a `HUMAN-0` co-sign before `GovernanceGate` will approve it.

The intent: simple, bounded mutations flow freely. Complex mutations require explicit human judgment. The governance gate does not block complexity entirely — it escalates it.

</details>

<details>
<summary><strong>Can I use ADAAD without Android? Without a server?</strong></summary>

<br/>

Yes. ADAAD runs on any Python 3.10+ environment — Linux, macOS, Windows (via WSL), Android (Termux / Pydroid3), CI/CD pipelines, and bare metal. The Android support is a first-class path, not a demo — `requirements.phone.txt` keeps the dependency footprint small enough for a phone.

</details>

<details>
<summary><strong>What is the difference between ADAAD and DEVADAAD?</strong></summary>

<br/>

Both are trigger tokens for the governed build agent protocol defined in `AGENTS.md`.

- **`ADAAD`** — executes the full governed build workflow and stages work for human review. Does not merge.
- **`DEVADAAD`** — everything `ADAAD` does, plus operator-authorized merge execution. The first word of the prompt must be `DEVADAAD` exactly. All governance constraints apply identically — the only additional capability is merge.

</details>

---

## What ADAAD Is Not

> [!CAUTION]
> - ❌ **Not** a general-purpose LLM coding assistant
> - ❌ **Not** an unattended production auto-merge system
> - ❌ **Not** a CI/CD pipeline replacement
> - ❌ **Not** a self-improving model training or fine-tuning framework
> - ❌ **Not** a tool where the human is the safety layer
>
> **It is a governed code evolution engine.**
>
> Safety is structural, not advisory. The `GovernanceGate` is not a guardrail — it is the only path through. Constitution v0.9.0 defines 23 rules. Invariant `GOV-SOLE-0` makes the gate the sole approval surface. This is architectural, not configurable.

---

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full contribution contract.

All contributions flow through the same governed pipeline used for ADAAD's own evolution:
- PRs require CI green on all tiers
- Governance docs changes require GPG-signed commits
- Constitutional rule changes require explicit human governor sign-off
- Evidence artifacts are immutable after phase close

---

## License & Trademarks

- **Source code:** [Apache License 2.0](LICENSE) — free forever, no exceptions
- **Brand assets** (`brand/` directory): Proprietary — see [BRAND_LICENSE.md](BRAND_LICENSE.md)
- **Trademarks:** "InnovativeAI", "ADAAD", "Aponi", and "Cryovant" are trademarks of InnovativeAI LLC

Built by **Dustin L. Reid**, InnovativeAI LLC — Blackwell, Oklahoma.

---

<div align="center">

**[⚡ Quickstart](QUICKSTART.md)** &nbsp;·&nbsp; **[📜 Constitution](docs/CONSTITUTION.md)** &nbsp;·&nbsp; **[🗺 Roadmap](ROADMAP.md)** &nbsp;·&nbsp; **[🤖 Agent Spec](AGENTS.md)** &nbsp;·&nbsp; **[🐛 Issues](https://github.com/InnovativeAI-adaad/ADAAD/issues)** &nbsp;·&nbsp; **[🤝 Contributing](CONTRIBUTING.md)** &nbsp;·&nbsp; **[📱 Android](INSTALL_ANDROID.md)** &nbsp;·&nbsp; **[📊 Aponi](ui/)**

<br/>

![ledger](https://img.shields.io/badge/⛓_Evidence_Ledger-SHA--256_Hash--Chained-0d1117?style=flat-square&labelColor=0d1117&color=00d4ff)&nbsp;![constitution](https://img.shields.io/badge/📜_Constitution-v0.9.0_—_23_Rules_Active-0d1117?style=flat-square&labelColor=0d1117&color=f5c842)&nbsp;![evolved](https://img.shields.io/badge/◈_Self--Evolved-Phase_65_—_March_13_2026-0d1117?style=flat-square&labelColor=0d1117&color=ff4466)&nbsp;![invariants](https://img.shields.io/badge/🔒_8_Invariants-Code--Level_Non--Overridable-0d1117?style=flat-square&labelColor=0d1117&color=a855f7)

<br/>

<sub><code>ADAAD v9.1.0</code> &nbsp;·&nbsp; Apache 2.0 &nbsp;·&nbsp; InnovativeAI LLC &nbsp;·&nbsp; Blackwell, Oklahoma &nbsp;·&nbsp; <a href="https://github.com/InnovativeAI-adaad/ADAAD">github.com/InnovativeAI-adaad/ADAAD</a></sub>

</div>
