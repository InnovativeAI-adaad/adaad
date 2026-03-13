<p align="center">
  <img src="docs/assets/adaad-hero.svg" width="960" alt="ADAAD — Autonomous Device-Anchored Adaptive Development"/>
</p>

<p align="center">
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml"><img src="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <img src="https://img.shields.io/badge/version-9.1.0-00d4ff?style=flat-square" alt="Version"/>
  <img src="https://img.shields.io/badge/tests-4%2C441%20passing-00ff88?style=flat-square" alt="Tests"/>
  <img src="https://img.shields.io/badge/constitution-v0.9.0%20%E2%80%94%2023%20rules-f5c842?style=flat-square" alt="Constitution"/>
  <img src="https://img.shields.io/badge/license-Apache%202.0-lightgrey?style=flat-square" alt="License"/>
  <img src="https://img.shields.io/badge/platform-Android%20%7C%20Linux%20%7C%20macOS-9966ff?style=flat-square" alt="Platform"/>
  <img src="https://img.shields.io/badge/self--evolution-active-ff4466?style=flat-square" alt="Self-Evolution Active"/>
</p>

<p align="center">
  <a href="QUICKSTART.md"><strong>Get Started in 5 Minutes →</strong></a>
  &nbsp;·&nbsp;
  <a href="docs/CONSTITUTION.md"><strong>The 23 Rules</strong></a>
  &nbsp;·&nbsp;
  <a href="examples/single-agent-loop/README.md"><strong>Live Example</strong></a>
  &nbsp;·&nbsp;
  <a href="ROADMAP.md"><strong>Roadmap</strong></a>
</p>

---

## The One-Paragraph Case

Every AI code tool today does the same thing: **suggest, you apply.** No memory of what worked. No fitness score. No audit trail. No rollback. No constitutional constraint on what it can touch. You are always the last line of defense.

**ADAAD is different in kind, not degree.** It is a production-grade autonomous code evolution engine that improves your codebase epoch by epoch — every mutation cryptographically signed, hash-chained into a tamper-evident ledger, deterministically replayable, and subject to a 23-rule constitutional gate before a single byte changes. It runs a 14-step governed evolution loop. It scores proposals against 7 fitness signals. It runs on a $200 Android phone.

> *It has already evolved itself. That happened. The hash is in the ledger.*

---

## What Makes This Different

| Every Other AI Code Tool | ADAAD |
|:---|:---|
| Suggest → human applies | Propose → evaluate → gate → apply **atomically** |
| No memory between sessions | Full lineage ledger, epoch by epoch |
| No audit trail | SHA-256 hash-chained evolution ledger, tamper-evident |
| Safety is optional, bolt-on | `GovernanceGate` is the **only** approval surface — no bypass exists |
| Can't prove what it did | Every decision is deterministically replayable |
| Server-only, enterprise-priced | Runs on a $200 Android phone — Apache 2.0, free |
| Human is the safety layer | Constitutional governance **is** the safety layer |

---

## Architecture

<p align="center">
  <img src="docs/assets/adaad-architecture.svg" width="900" alt="ADAAD System Architecture"/>
</p>

Three LLM-backed agents (**Architect**, **Dream**, **Beast**) compete via bandit selection. Every winning proposal traverses a 14-step Constitutional Evolution Loop before a single byte changes. The `GovernanceGate` is the sole approval surface — it cannot be bypassed, ever.

---

## The Constitutional Evolution Loop (CEL)

All 14 steps execute in strict sequence. One failure → clean halt. Zero silent errors. This is architectural invariant **CEL-ORDER-0**.

```
[1]  MODEL-DRIFT-CHECK    Determinism guard — blocks if determinism_verified=False
[2]  LINEAGE-SNAPSHOT     Capture capability_graph_before hash
[3]  FITNESS-BASELINE     Record pre-epoch 7-signal composite score
[4]  PROPOSAL-GENERATE    LLM-backed mutation proposals from Architect/Dream/Beast
[5]  AST-SCAN             StaticSafetyScanner — 4 hard rules (GovernanceGateV2 preflight)
[6]  SANDBOX-EXECUTE      Ephemeral clone execution — respects SANDBOX_ONLY
[7]  REPLAY-VERIFY        Hash match — any divergence = auto-rollback (SANDBOX-DIV-0)
[8]  FITNESS-SCORE        7 signals scored and bounded — determinism veto is unconditional
[9]  GOVERNANCE-GATE-V2   5 diff-aware AST rules (Phase 63)
[10] GOVERNANCE-GATE      18 base constitutional rules — all must pass (GATE-V2-EXISTING-0)
[11] LINEAGE-REGISTER     Register survivors in lineage chain
[12] PROMOTION-DECISION   CapabilityGraph + PromotionEvent — skipped in SANDBOX_ONLY
[13] EPOCH-EVIDENCE       SHA-256 hash-chained ledger entry written
[14] STATE-ADVANCE        Epoch counter advanced — emit epoch_complete.v1
```

---

## The 23 Constitutional Rules

<table>
<tr>
<td valign="top" width="33%">

**🔴 Blocking — 9 Rules**
Unconditionally reject any violating mutation.

- `single_file_scope`
- `ast_validity`
- `no_banned_tokens`
- `signature_required`
- `lineage_continuity`
- `resource_bounds`
- `federation_dual_gate`
- `federation_hmac_required`
- `soulbound_privacy_invariant`

</td>
<td valign="top" width="33%">

**🟡 Warning — 5 Rules**
Flag and continue — blocking in PRODUCTION.

- `max_complexity_delta`
- `test_coverage_maintained`
- `max_mutation_rate`
- `import_smoke_test`
- `entropy_budget_limit`

</td>
<td valign="top" width="33%">

**🔵 Advisory — 9 Rules**
Informational — captured in audit trails.

- `deployment_authority_tier`
- `revenue_credit_floor`
- `reviewer_calibration`
- `bandit_arm_integrity_invariant`
- `market_signal_integrity_invariant`
- `+5 GovernanceGateV2 AST rules`

</td>
</tr>
</table>

---

## 8 Permanent Architectural Invariants

These cannot be overridden by any mutation, configuration, or runtime flag — enforced at the **code level**, not policy level.

| ID | Rule |
|:---|:---|
| `GOV-SOLE-0` | `GovernanceGate` is the sole mutation approval surface — no bypass exists |
| `DET-ALL-0` | All governance decisions are deterministic |
| `SIM-BLOCK-0` | `simulation=True` blocks all live side-effects |
| `SANDBOX-DIV-0` | AST hash must match post-apply — any divergence = automatic rollback |
| `PATCH-SIZE-0` | Max 40 delta AST nodes, max 2 files per patch |
| `TIER0-SELF-0` | Tier-0 bound modules cannot self-mutate |
| `LINEAGE-STAB-0` | Lineage stable iff ≥ 2/5 last epochs passed |
| `CEL-ORDER-0` | All 14 CEL steps execute in strict sequence — no skipping allowed |

---

## Quick Start

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.server.txt

# Always validate first
PYTHONPATH=. python -m pytest tests/test_boot_preflight.py -q

# Full test suite — 4,441 tests
PYTHONPATH=. python -m pytest tests/ -q

# Dry-run governed evolution — no writes, no risk
ADAAD_CEL_ENABLED=true ADAAD_SANDBOX_ONLY=true ADAAD_ENV=dev python app/main.py
```

**Android (Pydroid3 / Termux):**
```bash
pip install -r requirements.phone.txt
CRYOVANT_DEV_MODE=1 ADAAD_ENV=dev python app/main.py --host 0.0.0.0 --port 8000
```

> See [QUICKSTART.md](QUICKSTART.md) for the full walkthrough · [INSTALL_ANDROID.md](INSTALL_ANDROID.md) for phone setup

---

## Fitness Engine — 7 Signals

Every mutation proposal is scored across 7 independent signals before `GovernanceGate` sees it. Determinism divergence is an **unconditional veto** (`FIT-DIV-0`) — not a scored signal.

| Signal | Weight Bound | Notes |
|:---|:---:|:---|
| Test coverage delta + failure reduction | [0.05, 0.70] | Rewards mutations that improve pass rates |
| Cyclomatic complexity delta | [0.05, 0.70] | Penalizes complexity increases |
| Performance benchmark delta | [0.05, 0.70] | Measures runtime impact |
| Governance compliance (10-epoch rolling) | [0.05, 0.70] | Historical track record of mutation type |
| Architectural fitness — coupling & centrality | [0.05, 0.70] | Rewards improved dependency structure |
| Determinism — replay divergence | [0.05, 0.70] | **HARD FLOOR: zero divergence required** |
| Net node additions (deletion rewarded) | [0.05, 0.70] | Rewards codebase shrinkage |

**AdaptiveWeights:** EMA momentum descent (LR=0.05) adjusts weights from post-merge telemetry. `NonStationarityDetector` (Page-Hinkley) switches to Thompson Sampling after ≥30 epochs of non-stationary reward.

---

## Mutation Tier System

| Tier | Paths | Authority | Review Model |
|:---|:---|:---:|:---|
| **Tier 0 — Production** | `runtime/`, `security/`, `app/main.py` | ❌ Never auto | Human required before any merge |
| **Tier 1 — Stable** | `tests/`, `docs/`, most agents | ✅ Auto + audit trail | Human reviews logs within 24h |
| **Tier 2 — Sandbox** | `app/agents/test_subject/` | ✅ Fully autonomous | Zero blast radius to other tiers |

---

## Three AI Mutation Agents

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ARCHITECT     │    │     DREAM       │    │     BEAST       │
│                 │    │                 │    │                 │
│  Methodical     │    │  Creative       │    │  Aggressive     │
│  Conservative   │    │  Exploratory    │    │  Max throughput │
│  Structured     │    │  Novel paths    │    │  Filtered hard  │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         └─────────────────────┼─────────────────────┘
                               ▼
              ┌─────────────────────────────┐
              │     BANDIT SELECTOR         │
              │  UCB1 + Thompson Sampling   │
              │  BLX-alpha crossover        │
              │  Up to 12 candidates/epoch  │
              └────────────┬────────────────┘
                           ▼
              ┌─────────────────────────────┐
              │     GOVERNANCE GATE         │
              │   23 constitutional rules   │
              │  Non-bypassable · GOV-SOLE-0│
              └─────────────────────────────┘
```

---

## Codebase at a Glance

| Metric | Value |
|:---|:---|
| Version | **9.1.0** (Phase 66 — Foundation Hardening) |
| Runtime Python files | 329 |
| Test files | 267 |
| Total test LOC | ~37,000 |
| Passing tests | **4,441** |
| Constitutional rules | **23** (v0.9.0) |
| Development phases completed | **66** |
| Android support | Full — Termux + Pydroid3 |
| First autonomous self-evolution | ✅ Phase 65 — March 13, 2026 |

---

## Phase 65 — First Autonomous Self-Evolution

On March 13, 2026, ADAAD executed its first **fully autonomous, governed self-improvement cycle** with zero human intervention in the execution path and full human oversight of the governance framework.

```
[1]  CodeIntelModel       → identified highest-priority improvement target
[2]  CapabilityDiscovery  → mapped to cap:runtime.evolution.cel_wiring.live_mode
[3]  ProposalEngine       → generated LLM-backed mutation proposal
[4]  StaticSafetyScanner  → cleared all 4 AST safety rules
[5]  SandboxTournament    → evaluated in ephemeral container
[6]  FitnessEngineV2      → scored all 7 signals — composite exceeded baseline
[7]  GovernanceGateV2     → approved (Class A)
[8]  GovernanceGate       → confirmed all 18 base constitutional rules
[9]  Patch Application    → applied atomically — 0 replay divergences
[10] CapabilityGraph      → updated — CapabilityChange written to ledger
[11] EpochEvidence        → hash-chained into evolution ledger
[12] Human Oversight      → acknowledged the full audit trail
```

---

## Project Structure

```
ADAAD/
├── app/                   # Orchestrator, agents, mutation cycle, FastAPI server
├── runtime/               # Core engine — governance, evolution, fitness, federation
│   ├── evolution/         # CEL, lineage ledger, fitness engine, replay attestation
│   ├── governance/        # Constitutional gate, 23 rules, federation, rate limiting
│   ├── autonomy/          # Bandit selector, weight adaptor, non-stationarity
│   └── sandbox/           # Ephemeral container execution, preflight checks
├── security/              # Cryovant auth, key management, session governance
├── tests/                 # 267 test files, 4,441 passing tests
├── docs/                  # Architecture docs, constitution, governance specs
│   └── assets/            # SVG diagrams and visual assets
├── governance/            # Constitutional rules, federation keys, attestations
├── schemas/               # JSON schemas for all governance artifacts
├── tools/                 # Linters, audit tools, import boundary enforcement
├── scripts/               # CI/CD, retention enforcement, signing scripts
├── ui/                    # Aponi dashboard (Python + HTML)
├── android/               # Android build, F-Droid, Play Store assets
├── _inbox/                # Working documents, proposals, media (non-canonical)
├── QUICKSTART.md          # 5-minute setup guide
├── AGENTS.md              # Build agent protocol spec (ADAAD / DEVADAAD)
└── ROADMAP.md             # Full phase roadmap through Q2 2027
```

---

## What ADAAD Is Not

- ❌ Not a general-purpose LLM coding assistant
- ❌ Not an unattended production auto-merge system
- ❌ Not a CI/CD replacement
- ❌ Not a self-improving model training framework

---

## License & Trademarks

- **Source code:** [Apache License 2.0](LICENSE)
- **Brand assets** (`brand/` directory): Proprietary — see [BRAND_LICENSE.md](BRAND_LICENSE.md)
- **Trademarks:** "InnovativeAI", "ADAAD", "Aponi", and "Cryovant" are trademarks of InnovativeAI LLC

Built by **Dustin L. Reid**, InnovativeAI LLC — Blackwell, Oklahoma.

---

<p align="center">
  <a href="QUICKSTART.md">Get Started</a> ·
  <a href="docs/CONSTITUTION.md">Constitution</a> ·
  <a href="ROADMAP.md">Roadmap</a> ·
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/issues">Issues</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <sub>ADAAD v9.1.0 · Apache 2.0 · InnovativeAI LLC · github.com/InnovativeAI-adaad/ADAAD</sub>
</p>
