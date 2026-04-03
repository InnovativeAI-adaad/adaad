<div align="center">

<!-- ADAAD_VERSION_HERO:START -->
<img src="docs/assets/readme/adaad-hero-animated.svg" width="100%" alt="ADAAD v9.40.0 — 107 Phases Complete — LIVE"/>
<!-- ADAAD_VERSION_HERO:END -->

**[⚡ Quickstart](#quickstart)** &nbsp;·&nbsp; **[📜 Constitution](docs/CONSTITUTION.md)** &nbsp;·&nbsp; **[🗺 Roadmap](ROADMAP.md)** &nbsp;·&nbsp; **[📖 Thesis](docs/thesis/ADAAD_THESIS.md)** &nbsp;·&nbsp; **[🏛 Trust Center](TRUST_CENTER.md)** &nbsp;·&nbsp; **[📱 Android](INSTALL_ANDROID.md)** &nbsp;·&nbsp; **[📋 Changelog](CHANGELOG.md)**

</div>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## What ADAAD is

**ADAAD is a constitutionally governed autonomous code evolution runtime.**

It proposes mutations to its own source code, red-team tests them, scores them against constitutional rules, runs them in a zero-write shadow harness, checks them against a formally encoded self-model, and requires your cryptographic sign-off before anything critical ships — with every decision sealed in a tamper-evident hash-chained ledger.

The governance stack is not a policy layer. It is the only promotion path. There is no bypass. That is the point.

**Who it's for:** AI teams, research labs, and enterprises that need to run autonomous AI evolution with auditable, deterministic, human-governed provenance — and need to prove it to auditors, regulators, or acquirers.

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Core guarantees

These are not documentation claims. They are runtime-enforced invariants. Violating them aborts the epoch.

| Guarantee | Enforcement | Invariant |
|:---|:---|:---:|
| Every epoch produces a verifiable evidence hash | SHA-256 hash-chained append-only ledger | `CEL-EVIDENCE-0` |
| Mutations are byte-identical replayable from original inputs | No `datetime.now()` / `random()` in constitutional paths | `CEL-REPLAY-0` |
| Step ordering cannot be bypassed or skipped | Runtime sequence check — out-of-order aborts | `CEL-ORDER-0` |
| Governance gate is the sole promotion path | `GovernanceGateV2` is wired as the only path | `GOV-SOLE-0` |
| Shadow harness writes nothing to production | Zero-write enforcement + egress detection | `LSME-0` |
| Red Team cannot approve its own challenges | Structural constraint — PASS or RETURNED only | `AFRT-0` |
| Identity check never blocks an epoch | Fail-open with fallback score injection | `MMEM-0` |
| Critical mutations require GPG-signed human key | Architecturally enforced — not a config option | `HUMAN-0` |
| Import boundaries block unauthorized dependencies | Static enforcement — violations block merge | `AST-IMPORT-0` |
| All 99 Hard-class invariants enforced at runtime | Epoch aborts on violation — no silent failures | 99 invariants |

→ [Full invariants matrix](docs/governance/V8_CONSTITUTIONAL_INVARIANTS_MATRIX.md) · [Constitution](docs/CONSTITUTION.md)

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## The mutation pipeline

<img src="docs/assets/readme/adaad-pipeline-animated.svg" width="100%" alt="ADAAD Mutation Pipeline — 9 governed steps"/>

Every proposed change traverses all 9 gates in strict order. `CEL-ORDER-0` enforces this at runtime. There is no skip path, no override flag, no configuration that changes this.

<details>
<summary><b>Step-by-step breakdown</b></summary>
<br/>

**Phase 0d — Identity Check (INNOV-10)**
`IdentityContextInjector` consults the `IdentityLedger` — a hash-chained, HUMAN-0-attested self-model containing 8 founding `IdentityStatement`s. Injects `identity_consistency_score` into `CodebaseContext` before any proposal is generated. Proposals contradicting the system's self-model are flagged at the root. Never blocks epoch (`MMEM-0`).

**Phase 1 — Proposal**
Claude-powered agents (Architect · Dream · Beast) generate `MutationCandidate`s. Identity score is in context. Bandit selector routes to the highest-performing agent based on prior epoch outcomes.

**Phase 2–3 — Adversarial Red Team (INNOV-08)**
`AdversarialRedTeamAgent` queries `CodeIntelModel` for uncovered code paths, generates up to 5 targeted adversarial cases, and runs each in a read-only sandbox. `AFRT-0`: the agent cannot approve — structural constraint, not policy. Output: PASS or RETURNED.

**Phase 4 — Constitutional Scoring**
`FitnessEngineV2` scores against 7 fitness signals plus `identity_consistency` (8th). All 27 runtime-enforced constitutional rules checked. Rule violation halts epoch immediately.

**Phase 5 — Live Shadow Execution (INNOV-07)**
Zero-write shadow harness runs mutation against real traffic patterns. `ShadowFitnessReport`: divergence rate · error delta · P99 latency. Regression on any signal = hard block. Independent of fitness score.

**Phase 6 — Governance Gate**
`GovernanceGateV2` evaluates the full evidence package — fitness scores, shadow report, red-team verdict, identity score, determinism check, lineage validity. All prior gates must pass. Verdict: APPROVED · RETURNED · BLOCKED.

**Phase 7 — Human Sign-off (Tier 0)**
For critical mutations, GPG-signed approval from the governor (`HUMAN-0: Dustin L. Reid`) is required. The system is architecturally incapable of promoting Tier 0 mutations without it. Not a setting.

**Phase 8 — Ledger Commit**
Every decision — pass, fail, return, block — is SHA-256 hash-chained into the append-only `ScoringLedger`. One altered entry breaks every subsequent hash. History cannot be rewritten. Any attempt is immediately detectable.

**Phase 9 — Cryptographic Proof DAG (INNOV-06)**
Full mutation lineage Merkle-rooted. Every causal ancestor cryptographically linked. Independently verifiable without system access. Legal-grade provenance for auditors, regulators, patent counsel.

</details>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Architecture

<img src="docs/assets/adaad-architecture.svg" width="100%" alt="ADAAD Architecture"/>

ADAAD runs a **16-step Constitutional Evolution Loop (CEL)** on every proposed change. Three AI agents — **Architect** (structural reasoning), **Dream** (mutation generation), and **Beast** (performance pressure) — apply constitutional rules at different steps. No single agent can approve a change.

<details>
<summary><b>Module map and boundary contracts</b></summary>
<br/>

**Runtime layer** — `runtime/`
| Module | Role |
|:---|:---|
| `evolution/evolution_loop.py` | Orchestrates the 16-phase epoch. Phase 0d MMEM wire lives here. |
| `evolution/constitutional_evolution_loop.py` | 16-step CEL dispatch. Calls GovernanceGate, AFRT, LSME. |
| `evolution/fitness_v2.py` | `FitnessEngineV2` — 8-signal scoring including identity. |
| `memory/identity_ledger.py` | Hash-chained HUMAN-0-gated `IdentityLedger`. MMEM-0/CHAIN-0/LEDGER-0. |
| `memory/identity_context_injector.py` | Phase 0d wiring. Never raises. |
| `lineage/lineage_ledger_v2.py` | Second-gen lineage store with MMEM co-commit surface. |
| `capability_graph.py` | Tracks module capability contracts. No `__import__` — enforced. |

**Governance layer** — `security/`
| Module | Role |
|:---|:---|
| `security/ledger/governance_events.jsonl` | Hash-chained HUMAN-0 sign-off events. |
| `security/ledger/scoring.jsonl` | All epoch governance decisions. Append-only. |
| `config/constitution.yaml` | 27 runtime-enforced constitutional rules v0.9.0. |

**Import boundary contract**
All module-to-module imports must cross defined seams. Violations are caught by `scripts/check_spdx_headers.py` and `AST-IMPORT-0` CI gate. Adding a direct cross-layer import without updating the boundary contract blocks the PR.

Every file must carry `# SPDX-License-Identifier: Apache-2.0`. Missing headers are a merge blocker.

</details>

<details>
<summary><b>Agent roles — Architect · Dream · Beast</b></summary>
<br/>

**Architect** — Structural reasoning. Long-term maintainability, clean architecture, reducing technical debt. Proposes mutations that improve code organization without sacrificing fitness.

**Dream** — Creative mutation generation. Experimental approaches, novel capability surfaces, capability gap identification. Higher exploration rate.

**Beast** — Performance pressure. Throughput, efficiency, bottleneck elimination. Penalizes complexity that doesn't buy fitness.

All three are Claude-powered and selected per epoch by the `AgentBanditSelector` (INNOV multi-armed bandit) based on prior win/loss ratios. No single agent controls the outcome. The governance gate is the only promotion authority.

</details>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Proven milestones — not roadmap promises

These events happened. The evidence is hash-chained in the ledger.

<!-- AUTO-UPDATED: phase progress regenerates on every merge to main -->
<img src="docs/assets/readme/adaad-phase-progress.svg" width="100%" alt="ADAAD Phase Progress"/>

<br/>

<details open>
<summary><b>⛓ March 13, 2026 — First autonomous self-evolution (Phase 65)</b></summary>
<br/>

<img src="docs/assets/adaad-phase65-banner.svg" width="100%" alt="Phase 65"/>

ADAAD identified its own highest-priority capability gap, generated a mutation, ran a sandboxed fitness tournament, scored it against constitutional rules, applied it, and sealed the proof in the ledger. Zero human intervention in the execution path. Full human control of the constitutional framework.

<img src="docs/assets/adaad-phase65-chain.svg" width="100%" alt="Phase 65 hash chain"/>
</details>

<details>
<summary><b>🌱 March 20, 2026 — First governed seed epoch (Phase 77)</b></summary>
<br/>

A capability seed flowed through all 7 governed stages — proposal, human review, CEL injection, constitutional loop, ledger-anchored outcome — producing a cryptographic proof linking every step back to its origin. The loop is closed.
</details>

<details>
<summary><b>◈ March 22, 2026 — CEL live in production (Phase 89)</b></summary>
<br/>

Real Claude-generated proposals flowing through all 16 constitutional steps in production. Not a test harness.
</details>

<details>
<summary><b>🧭 March 23, 2026 — Cryptographic Evolution Proof DAG (Phase 90 · INNOV-06)</b></summary>
<br/>

Every mutation cryptographically bound to all causal ancestors via Merkle root. Independently verifiable without system access. Legal-grade provenance for auditors, regulators, and patent counsel.
</details>

<details>
<summary><b>🛡 March 24, 2026 — Live Shadow Mutation Execution (Phase 91 · INNOV-07)</b></summary>
<br/>

Zero-write shadow harness against real traffic. `ShadowFitnessReport`: divergence rate · error delta · P99 latency. Must survive shadow execution *and* governance gate to advance.
</details>

<details>
<summary><b>⚔ March 27, 2026 — Adversarial Red Team as a Constitutional Gate (Phase 92 · INNOV-08)</b></summary>
<br/>

Every proposal challenged by `AdversarialRedTeamAgent` before governance scoring. Finds uncovered code paths, fires targeted adversarial cases. `AFRT-0`: cannot approve — PASS or RETURNED only. Structurally enforced.
</details>

<details>
<summary><b>🎨 March 27, 2026 — Aesthetic Fitness Signal (Phase 93 · INNOV-09)</b></summary>
<br/>

Code readability scored across 5 AST axes (function length · name entropy · nesting depth · comment density · cyclomatic complexity) as a constitutionally-bounded, weighted fitness signal. `AFIT-WEIGHT-0`: weight bounded [0.05, 0.30]. Technical debt is now measurable and governed.
</details>

<details>
<summary><b>🧬 March 28, 2026 — Morphogenetic Memory (Phase 94 · INNOV-10)</b></summary>
<br/>

`IdentityLedger` — 8 founding `IdentityStatement`s (IS-001..IS-008), hash-chained, HUMAN-0-attested. `IdentityContextInjector` fires Phase 0d before proposals are generated. Injects `identity_consistency_score`. Proposals contradicting the system's self-model flagged before they're written. First system to ask: *is this mutation consistent with what this system believes itself to be?*
</details>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Why you can trust the claims

Every property below is mechanically enforced at runtime.

**⛓ Tamper-evident ledger** — Every event is SHA-256 hash-chained. Alter one entry and every subsequent hash breaks. History cannot be rewritten.

**♻️ Deterministic replay** — Any prior epoch can be re-run from its original inputs and produce byte-identical results. No `datetime.now()`, no `random.random()` in constitutional paths. `CEL-REPLAY-0`.

**📜 Constitutional gate** — 27 runtime-enforced rules. Rule violation halts epoch. No config option changes this.

**⚔️ Adversarial red-team gate** — Every mutation challenged before scoring. Cannot approve. `AFRT-0`.

**🛡 Shadow execution gate** — Zero-write harness before live promotion. `LSME-0`.

**🔬 Identity gate** — Self-model consulted before proposals are generated. `MMEM-0`.

**🗺 Cryptographic lineage** — Merkle-rooted proof DAG. Independently verifiable. `CEPD-0`.

**🔑 Human authority is structural** — GPG key required for Tier 0. Not configurable. `HUMAN-0`.

**🚧 99 Hard-class invariants** — Cannot be disabled, configured around, or violated without epoch abort.

→ [Read the Constitution](docs/CONSTITUTION.md) · [Trust Center](TRUST_CENTER.md) · [Security Invariants Matrix](docs/governance/V8_CONSTITUTIONAL_INVARIANTS_MATRIX.md)

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## 22 shipped world-first innovations

<img src="docs/assets/readme/adaad-innovations-animated.svg" width="100%" alt="22 World-First Innovations — Shipped"/>

<details>
<summary><b>Full innovation index</b></summary>
<br/>

| # | Innovation | Phase | Core claim |
|:---:|:---|:---:|:---|
| INNOV-01 | Constitutional Self-Amendment (CSAP) | 87 | ADAAD proposes amendments to its own rules — unconditional human ratification required |
| INNOV-02 | Adversarial Constitutional Stress (ACSE) | 87 | Dedicated agent attempts to violate every constitutional rule to stress-test governance |
| INNOV-03 | Temporal Invariant Forecasting (TIFE) | 87 | Predicts which invariants will likely be violated in future epochs before they fail |
| INNOV-04 | Semantic Drift Detection (SCDD) | 88 | Detects when constitutional behaviour drifts from its historical baseline |
| INNOV-05 | Autonomous Organ Emergence (AOEP) | 89 | Proposes entirely new architectural organs to close capability gaps — human ratification required |
| INNOV-06 | Cryptographic Evolution Proof DAG (CEPD) | 90 | Full lineage Merkle-rooted · independently verifiable · legal-grade provenance |
| INNOV-07 | Live Shadow Mutation Execution (LSME) | 91 | Zero-write shadow harness · real traffic · hard block on regression |
| INNOV-08 | Adversarial Fitness Red Team (AFRT) | 92 | Red Team gate before scoring · cannot approve · PASS or RETURNED only |
| INNOV-09 | Aesthetic Fitness Signal (AFIT) | 93 | Code readability as a constitutionally-bounded, weighted fitness dimension |
| INNOV-10 | Morphogenetic Memory (MMEM) | 94 | Hash-chained self-model consulted pre-proposal · detects identity drift at root |

8 further innovations are roadmapped. Full specifications: [ADAAD_30_INNOVATIONS.md](ADAAD_30_INNOVATIONS.md)

</details>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## What you control vs. what the system handles

| **What only you can do** | **What ADAAD handles autonomously** |
|:---|:---|
| 🔑 GPG-sign Tier 0 changes | Generate mutation proposals via Claude |
| 🌱 Approve seed promotions | Red-team challenge every proposal before scoring |
| 📜 Set constitutional rules | Shadow-execute mutations in zero-write harness |
| 🏷 Tag version ceremonies | Score against 27 constitutional rules |
| ⚙️ Ratify new Hard-class invariants | Hash-chain every decision into the ledger |
| 🧬 Amend `IdentityLedger` statements | Consult self-model before every proposal (MMEM) |
| 📋 Patent and IP decisions | Build cryptographic evolution proof DAGs |
| ✅ GA sign-off | Mine failure patterns and propose new invariants |

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

<a name="quickstart"></a>
## Quickstart

### One command

```bash
git clone https://github.com/InnovativeAI-adaad/adaad.git
cd adaad
python onboard.py
```

`onboard.py` sets up your environment, validates governance schemas, and runs a governed dry-run. Safe to re-run any time.

**What success looks like:**
```
  ✔ Python 3.12.x
  ✔ Virtual environment created (.venv)
  ✔ Dependencies installed
  ✔ Governance schemas valid
  ✔ Dry-run complete  (fail-closed behaviour confirmed)

  Run the dashboard   python server.py
  Run an epoch        python -m app.main --verbose
  Strict replay       python -m app.main --replay strict --verbose
```

### Deterministic environment (reproducible evidence hashes)

```bash
# Create venv with pinned Python
python3.12 -m venv .venv && source .venv/bin/activate

# Install editable + dev extras
pip install -e .[dev]

# Set deterministic env — required for byte-identical replay
export ADAAD_SEED=42
export PYTHONHASHSEED=0

# Validate workspace and run epoch
python nexus_setup.py --validate-only
python -m app.main --replay audit --verbose
```

**If your evidence hash differs from expected:**
1. Confirm `python --version` matches — minor version matters
2. Confirm `PYTHONHASHSEED=0` is set in your shell
3. Confirm deps were installed with `--no-deps` (no transitive upgrades)
4. Run `scripts/check_replay_keyring_secrets.py` for environment diff
5. Run `git status` — any local changes will diverge the hash

<details>
<summary><b>Platform-specific setup</b></summary>
<br/>

| Platform | Method |
|:---|:---|
| Linux / macOS | `pip install adaad` or clone above |
| Windows | `pip install adaad` (WSL2 for sandbox) |
| Android (Termux) | [TERMUX_SETUP.md](TERMUX_SETUP.md) |
| Android (Pydroid 3) | [INSTALL_ANDROID.md](INSTALL_ANDROID.md) |
| Docker | `docker pull ghcr.io/innovativeai-adaad/adaad` |

*Constitutional governance should not depend on cloud infrastructure. ADAAD's safety properties come from SHA-256 hash chains and the Python runtime — not from cloud KMS, Kubernetes, or any third-party service.*

</details>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Replay and audit

Every governance decision ADAAD makes is replayable and verifiable from first principles.

### Verify an epoch

```bash
# Run an epoch with audit output
python -m app.main --replay audit --verbose

# Output includes:
#   epoch_id        : unique identifier
#   evidence_hash   : sha256 of the full epoch evidence package
#   mutations_applied
#   governance_decisions: [APPROVED|RETURNED|BLOCKED] per candidate
```

### Replay a specific epoch

```bash
# Strict replay — must produce byte-identical evidence hash
python -m app.main --replay strict --epoch-id <epoch_id> --verbose

# If replay diverges, it is a blocking integrity signal.
# Check: same Python version, same PYTHONHASHSEED, same deps.
```

### Inspect mutation lineage

```bash
# Verify the hash chain of the scoring ledger
python -c "
from runtime.lineage.lineage_ledger_v2 import LineageLedgerV2
ledger = LineageLedgerV2()
print('Chain valid:', ledger.verify_chain())
print('Events:', len(ledger.events()))
"
```

### Verify the IdentityLedger chain

```bash
python -c "
from runtime.memory.identity_ledger import IdentityLedger
ledger = IdentityLedger.load_genesis()
print('Chain valid:', ledger.verify_chain())
print('Statements:', len(ledger))
for s in ledger.statements():
    print(f'  {s.statement_id}: {s.statement[:60]}...')
"
```

### Confirm no unauthorized imports

```bash
python scripts/check_spdx_headers.py
# All files must carry: # SPDX-License-Identifier: Apache-2.0
# Violations are printed and cause CI failure.
```

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Governance in 60 seconds

ADAAD evolves through numbered phases. Each phase ships a specific capability, registers findings, resolves them with evidence, and chains a governance ledger entry before merge.

### Recent phases

| Phase | Innovation | Invariants added | Status |
|:---:|:---|:---:|:---:|
| 92 | Adversarial Fitness Red Team (AFRT) | AFRT-0 · GATE-0 · INTEL-0 · LEDGER-0 · CASES-0 · DETERM-0 | ✅ Shipped |
| 93 | Aesthetic Fitness Signal (AFIT) | AFIT-0 · DETERM-0 · BOUND-0 · WEIGHT-0 | ✅ Shipped |
| 94 | Morphogenetic Memory (MMEM) | MMEM-0 · CHAIN-0 · READONLY-0 · WIRE-0 · LEDGER-0 · DETERM-0 | ✅ Shipped |
| 95 | Oracle×Dork Alignment (UI) | — | ✅ Shipped |
| 96 | Cross-Epoch Dream State Engine (DSTE) · INNOV-11 | DSTE-0..6 | ✅ Shipped |
| 97 | TBD · INNOV-12 | — | 🗺 Planned |

### Governance event chain

Every HUMAN-0 sign-off is recorded in `security/ledger/governance_events.jsonl` as a hash-chained event. Chain verification:

```bash
python -c "
import json, hashlib
events = [json.loads(l) for l in open('security/ledger/governance_events.jsonl')]
print(f'Governance events: {len(events)}')
print(f'Latest: {events[-1][\"event_id\"]}')
print(f'Latest hash: {events[-1][\"event_hash\"][:32]}...')
"
```

<details>
<summary><b>How a phase ships (contributor reference)</b></summary>
<br/>

1. ArchitectAgent produces a specification for the phase
2. MutationAgent implements on a `feature/phase<N>-*` branch
3. TIER 0 invariant checks pass + `pytest` green + no regressions
4. HUMAN-0 signs off verbally (`Approved. All signed: Dustin L. Reid`)
5. `--no-ff` merge to main (lineage preserved — mandatory)
6. CHANGELOG entry + VERSION bump + semantic GPG-signed tag
7. Agent state updated + governance ledger event chained
8. Push

</details>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## For contributors

<details>
<summary><b>Required reading before opening any PR</b></summary>
<br/>

- [CONTRIBUTING.md](CONTRIBUTING.md) — development setup, PR flow, required checks
- [docs/CONSTITUTION.md](docs/CONSTITUTION.md) — 27 constitutional rules, governance philosophy
- [docs/governance/V8_CONSTITUTIONAL_INVARIANTS_MATRIX.md](docs/governance/V8_CONSTITUTIONAL_INVARIANTS_MATRIX.md) — all Hard-class invariants

</details>

<details>
<summary><b>Local checks before every PR</b></summary>
<br/>

```bash
# 1. Tests — all must pass
pytest --tb=short -q

# 2. SPDX headers — all source files
python scripts/check_spdx_headers.py

# 3. Import boundaries
python scripts/check_dependency_baseline.py

# 4. License check
python scripts/check_licenses.py

# 5. Replay integrity
python -m app.main --replay audit --verbose

# 6. Workspace validation
python nexus_setup.py --validate-only
```

</details>

<details>
<summary><b>PR evidence requirements</b></summary>
<br/>

Every governance-impacting PR must include in its description:
- **Branch name**: `feature/phase<N>-<descriptor>` or `fix/phase<N>-<descriptor>`
- **Test count**: number of new tests added
- **Invariants**: any new Hard-class invariants introduced
- **Evidence hash**: from a local epoch run
- **HUMAN-0 sign-off**: governor approval before merge

PRs without evidence artifacts are returned, not merged.

</details>

<details>
<summary><b>How to propose a new innovation</b></summary>
<br/>

1. Open a discussion with the `[INNOV-PROPOSAL]` label
2. Include: problem statement, proposed mechanism, invariants required, test coverage plan
3. ArchitectAgent reviews and produces a formal specification
4. HUMAN-0 ratifies the specification
5. Phase number is assigned and added to the procession
6. Implementation proceeds on a feature branch per the governance flow above

</details>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Security and trust center

**SPDX enforcement** — Every source file must carry `# SPDX-License-Identifier: Apache-2.0`. Missing headers block merge via CI.

**Import boundary enforcement** — Module seams are defined and enforced. Cross-layer imports without boundary contract updates block merge via `AST-IMPORT-0`.

**Replay divergence** — Any divergence from expected evidence hash is treated as a blocking integrity signal. Not a warning. A block.

**Key management** — HUMAN-0 GPG key (`4C95E2F99A775335B1CF3DAF247B015A1CCD95F6`) signs all release tags and Tier 0 governance events. Key is not stored in this repository.

**IdentityLedger attestation** — ILA-94-2026-03-28-001 attests the genesis seed terminal hash `3f5706...`. External auditors can verify independently.

**Report security issues** via the issue template `SECURITY.md`. Do not open public issues for vulnerability reports.

→ [Full Trust Center](TRUST_CENTER.md) · [Compliance Pack](docs/compliance/)

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Live system stats

<!-- AUTO-UPDATED: stats card regenerates on every merge to main -->
<img src="docs/assets/readme/adaad-stats-card.svg" width="100%" alt="ADAAD Live Stats"/>

<div align="center">

![GitHub commit activity](https://img.shields.io/github/commit-activity/m/InnovativeAI-adaad/adaad?style=flat-square&labelColor=0d1117&color=00d4ff&label=Commits%2Fmonth)&nbsp;![GitHub last commit](https://img.shields.io/github/last-commit/InnovativeAI-adaad/adaad?style=flat-square&labelColor=0d1117&color=00ff88&label=Last%20commit)&nbsp;![GitHub repo size](https://img.shields.io/github/repo-size/InnovativeAI-adaad/adaad?style=flat-square&labelColor=0d1117&color=a855f7&label=Repo%20size)&nbsp;![GitHub issues](https://img.shields.io/github/issues/InnovativeAI-adaad/adaad?style=flat-square&labelColor=0d1117&color=ff4466&label=Open%20issues)

</div>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Mythic identity

The ADAAD system uses named operational roles. These are runtime roles, not marketing.

| Name | Role |
|:---|:---|
| **Architect** | Structural mutation agent. Prioritizes maintainability and constitutional alignment. |
| **Dream** | Exploratory mutation agent. Novel approaches, capability gap identification. |
| **Beast** | Performance mutation agent. Throughput, efficiency, bottleneck pressure. |
| **Cryovant** | Identity and device-anchoring layer. Session tokens, audit signatures, trust anchoring. |
| **Aponi** | Governance dashboard. Audit UI, mutation lineage viewer, live epoch status. |
| **HUMAN-0** | The governor role. Dustin L. Reid. Holds GPG key. Ratifies constitutional changes. |

*ADAAD names clarify runtime roles and UX flows. They are not APIs and not marketing personas.*

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Enterprise and commercial use

<details>
<summary><b>Commercial documentation suite</b></summary>
<br/>

| Resource | What it is |
|:---|:---|
| [Pricing Model](docs/commercial/PRICING_MODEL.md) | Seat-based, usage-based, and hybrid SKUs |
| [Procurement Fast-Lane](docs/commercial/procurement_fastlane/DAY0_PROCUREMENT_FASTLANE_CHECKLIST.md) | Day-0 checklist, DPA/MSA fallback clauses, security Q&A — designed for 5-day close |
| [SLO / SLA Sheet](docs/commercial/procurement_fastlane/SLA_SLO_SHEET.md) | Reliability targets and support tier commitments |
| [Compliance Pack](docs/compliance/) | Data handling, access control matrix, incident response |
| [Trust Center](TRUST_CENTER.md) | Security posture and governance assurance artifacts |
| [Certification Program](docs/training/CERTIFICATION_PROGRAM.md) | Operator · Governance Engineer · Enterprise Administrator |
| [Partner Program](docs/commercial/PARTNER_PROGRAM.md) | Integrator and consultancy onboarding |
| [Data Room Index](docs/strategy/DATA_ROOM_INDEX.md) | Due-diligence artifact map |
| [ROI Model](docs/commercial/ROI_MODEL.md) | Value quantification framework for governance automation |

</details>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## What ADAAD is not

- ❌ **Not a code assistant** — it doesn't autocomplete your code or answer questions
- ❌ **Not CI/CD** — it governs the mutation process, not the build pipeline
- ❌ **Not fully autonomous** — your sign-off is constitutionally required for critical changes
- ❌ **Not a security scanner** — it enforces mutation governance, not vulnerability detection
- ❌ **Not magic** — every decision is logged, hash-chained, replayable, and explainable

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## FAQ

<details>
<summary><b>Is this actually running autonomously?</b></summary>
<br/>

Yes. Phase 65 (March 13, 2026) was the first epoch where ADAAD identified a capability gap, generated a mutation, ran it through all fitness and governance layers, and applied it with zero human intervention in the execution path. Phase 89 activated live LLM proposals in production.

Human oversight is structural, not optional. Dustin L. Reid holds the governor role. Any Tier 0 mutation requires his GPG-signed approval. That is not configurable.
</details>

<details>
<summary><b>What makes this different from just running tests in CI?</b></summary>
<br/>

CI tests whether known code passes known assertions. ADAAD governs whether *changes to the codebase itself* are constitutionally valid, adversarially stress-tested, fitness-improving, and deterministically replayable.

You can delete your CI history. You cannot alter ADAAD's ledger.

ADAAD actively challenges its own proposals via adversarial red-team agents, checks them against its encoded self-model, and runs them through zero-write shadow execution before they reach production. No CI system does this. No CI system has constitutional rules it's bound by. No CI system produces a cryptographic proof of its evolutionary lineage.
</details>

<details>
<summary><b>How does the adversarial Red Team work?</b></summary>
<br/>

Every mutation proposal is handed to `AdversarialRedTeamAgent` before fitness scoring. It queries `CodeIntelModel` for code paths the proposing agent didn't cover, then generates up to five targeted adversarial cases. Each runs in a read-only sandbox.

If any case falsifies the proposal, it's returned with a `RedTeamFindingsReport`. `AFRT-0`: the agent cannot approve — structurally enforced in code, not policy. Its only outputs are PASS or RETURNED.
</details>

<details>
<summary><b>What is Morphogenetic Memory?</b></summary>
<br/>

MMEM (INNOV-10, Phase 94) is a formally encoded architectural self-model: a hash-chained, HUMAN-0-gated, append-only `IdentityLedger` containing founding `IdentityStatement`s that define what ADAAD believes itself to be.

Before every epoch's proposals are generated (Phase 0d), the `IdentityContextInjector` consults the ledger and injects `identity_consistency_score` into `CodebaseContext`. This score is available to all downstream stages.

It answers the question no prior gate could ask: *is this mutation consistent with what this system believes itself to be?*
</details>

<details>
<summary><b>What are the 10 shipped innovations?</b></summary>
<br/>

INNOV-01 through INNOV-22 shipped across v9.18.0–v9.40.0 (Phases 87–107): Constitutional Self-Amendment (CSAP), Adversarial Constitutional Stress (ACSE), Temporal Invariant Forecasting (TIFE), Semantic Drift Detection (SCDD), Autonomous Organ Emergence (AOEP), Cryptographic Evolution Proof DAG (CEPD), Live Shadow Mutation Execution (LSME), Adversarial Fitness Red Team (AFRT), Aesthetic Fitness Signal (AFIT), Morphogenetic Memory (MMEM), and Agent Post-Mortem Interviews (APM), and Temporal Governance Windows (TGOV), and Governance Archaeology Mode (GAM).

8 further innovations are roadmapped. Full specifications: [ADAAD_30_INNOVATIONS.md](ADAAD_30_INNOVATIONS.md)
</details>

<details>
<summary><b>Why does it run on a $200 Android phone?</b></summary>
<br/>

Constitutional governance should not require enterprise infrastructure. ADAAD's safety properties come from SHA-256 hash chains and the Python runtime — not cloud KMS, Kubernetes, or any third-party service. If those go away, so do your safety guarantees. ADAAD's guarantees are local, deterministic, and yours.
</details>

<details>
<summary><b>How do I evaluate ADAAD for enterprise procurement?</b></summary>
<br/>

Start with the [Trust Center](TRUST_CENTER.md). The [Procurement Fast-Lane package](docs/commercial/procurement_fastlane/DAY0_PROCUREMENT_FASTLANE_CHECKLIST.md) is designed to complete security and legal review within 5 business days. A [Certification Program](docs/training/CERTIFICATION_PROGRAM.md) is available for operators, governance engineers, and enterprise administrators.
</details>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Roadmap

**Short term** — Phase 105 (INNOV-20), Aponi panel for jury deliberation (CJS), AEO endpoint provisioning.

**Mid term** — FitnessEngineV2 8th signal integration (identity_consistency), MMEM amendment protocol, device-anchored mobile runtime, reproducible packaging.

**Long term** — Cross-device federation with deterministic consensus, GA v1.1 readiness, Phase 114 milestone (30-innovation pipeline completion).

→ [Full roadmap](ROADMAP.md) · [30 Innovations specification](ADAAD_30_INNOVATIONS.md)

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

<div align="center">

<img src="docs/assets/readme/adaad-collage.png" width="90%" alt="ADAAD — Auditable · Deterministic · Automated"/>

<br/><br/>

**Built by [Innovative AI LLC](https://github.com/InnovativeAI-adaad) · Governor: Dustin L. Reid · Blackwell, Oklahoma**

*The next wave of AI isn't AI that writes your code.*
*It's AI that governs itself while writing your code —*
*and can prove it.*

<br/>

**[⚡ Get Started](#quickstart)** &nbsp;·&nbsp; **[📜 Constitution](docs/CONSTITUTION.md)** &nbsp;·&nbsp; **[📖 Thesis](docs/thesis/ADAAD_THESIS.md)** &nbsp;·&nbsp; **[🗺 Roadmap](ROADMAP.md)** &nbsp;·&nbsp; **[🏛 Trust Center](TRUST_CENTER.md)**

<br/>

*Build without limits. Govern without compromise.*

</div>
