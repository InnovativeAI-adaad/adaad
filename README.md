<div align="center">

<!-- ADAAD_VERSION_HERO:START -->
<img src="docs/assets/readme/adaad-version-hero.svg" width="100%" alt="ADAAD v9.27.0 — 94 Phases Complete — LIVE"/>
<!-- ADAAD_VERSION_HERO:END -->

<img src="docs/assets/adaad-hero.svg" width="100%" alt="ADAAD — Autonomous Development & Adaptation Architecture"/>

<br/>

[![Version](https://img.shields.io/badge/ADAAD-v9.27.0-000?style=for-the-badge&labelColor=0d1117&color=00d4ff)](https://github.com/InnovativeAI-adaad/ADAAD/releases)&nbsp;[![Phases](https://img.shields.io/badge/93_Phases-Complete-000?style=for-the-badge&labelColor=0d1117&color=00ff88)](ROADMAP.md)&nbsp;[![Self‑Evolution](https://img.shields.io/badge/◈_Self--Evolution-LIVE_·_Phase_93-000?style=for-the-badge&labelColor=0d1117&color=ff4466)](ROADMAP.md)&nbsp;[![License](https://img.shields.io/badge/License-Apache_2.0-000?style=for-the-badge&labelColor=0d1117&color=a855f7)](LICENSE)

[![CI](https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml/badge.svg)](https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml)&nbsp;![Tests](https://img.shields.io/badge/5%2C680_Tests-Passing-00ff88?style=flat-square&labelColor=0d1117)&nbsp;![Innovations](https://img.shields.io/badge/9_Innovations-Shipped_·_22_Roadmap-00d4ff?style=flat-square&labelColor=0d1117)&nbsp;![Invariants](https://img.shields.io/badge/21_Hard--Class-Invariants-ff4466?style=flat-square&labelColor=0d1117)

<br/>

**[⚡ Quickstart](QUICKSTART.md)** &nbsp;·&nbsp; **[📜 Constitution](docs/CONSTITUTION.md)** &nbsp;·&nbsp; **[🗺 Roadmap](ROADMAP.md)** &nbsp;·&nbsp; **[📖 Thesis](docs/thesis/ADAAD_THESIS.md)** &nbsp;·&nbsp; **[🏛 Trust Center](TRUST_CENTER.md)** &nbsp;·&nbsp; **[📱 Android](INSTALL_ANDROID.md)** &nbsp;·&nbsp; **[📋 Changelog](CHANGELOG.md)**

</div>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

<div align="center">

## AI that governs its own evolution — with you in control.

**ADAAD proposes changes to itself, red-team tests them, scores them against constitutional rules,<br/>runs them in a zero-write shadow harness, and requires your sign-off before anything critical ships.**

</div>

<br/>

## The problem every AI developer hits eventually

AI tools are getting good at writing code. That's not the problem.

The problem is **what happens after.** Every AI-generated change lands in your lap. You review it, you approve it, you own it. That's fine at ten changes a day. It breaks at a hundred. At scale — real autonomous agents running real evolution loops — you become the bottleneck, and the system only stays safe because you're willing to be exhausted.

There's a deeper issue too: the AI has no memory of prior decisions. No record of why the last change shipped or failed. No constitutional rules it's genuinely bound by. No proof you can hand to an auditor, a regulator, or an acquirer that says *here is every decision this system has ever made and why.*

**These are not edge cases. They are the core governance problem of autonomous AI development.** And no current tool addresses them structurally — they all just put you back in the loop and call it safety.

ADAAD is built to solve this at the architectural level.

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## What ADAAD actually does

ADAAD is a **constitutionally governed evolution runtime** for AI systems. It manages how an AI system proposes, evaluates, and applies changes to itself — under a framework of rules that cannot be bypassed, with a ledger of decisions that cannot be altered, and with your authority over anything critical wired in at the architecture level.

Here's the sequence every proposed change goes through:

**1. Proposal** — A mutation is proposed by an AI agent (Claude-powered). It specifies what changes and why.

**2. Adversarial red-team** — A dedicated Red Team Agent tries to break the proposal. It finds the code paths the proposing agent didn't cover and generates up to five targeted adversarial cases against them. If the proposal fails, it's returned to the proposer. It does not advance. *(INNOV-08 — the first system to do this as a constitutional gate.)*

**3. Constitutional scoring** — The proposal is measured against 21 runtime-enforced constitutional rules. These aren't guidelines. If a rule is violated, the epoch halts.

**4. Shadow execution** — The mutation runs in a zero-write shadow harness against real traffic patterns. Divergence, error rate, and latency are all measured. Regression on any signal blocks promotion. *(INNOV-07)*

**5. Governance gate** — A final constitutional gate evaluates the full evidence package. Nothing passes here that hasn't cleared every prior step.

**6. Your sign-off** — For Tier 0 changes, your GPG key is required. The system is architecturally incapable of promoting critical mutations without it. This is not a setting. It is wired into the code.

**7. Ledger commit** — Every decision — pass, fail, returned, blocked — is SHA-256 hash-chained into an append-only ledger. One altered entry breaks every subsequent hash. You cannot rewrite history.

**8. Cryptographic proof** — The full lineage of the mutation is Merkle-rooted into the Cryptographic Evolution Proof DAG, linking it to every causal ancestor. Independently verifiable. No system access required. *(INNOV-06)*

<table>
<tr>
<td align="center" width="33%">
<img src="docs/assets/readme/story-01.svg" width="100%" alt="Status quo"/>
<sub><b>Every other tool.</b> You are the sole safety layer, every session, forever. The system has no memory of what it decided last time.</sub>
</td>
<td align="center" width="33%">
<img src="docs/assets/readme/story-02.svg" width="100%" alt="ADAAD"/>
<sub><b>ADAAD.</b> The governance gate is the path — not a guardrail on top. Every step is ordered, evidenced, and hash-chained.</sub>
</td>
<td align="center" width="33%">
<img src="docs/assets/readme/story-03.svg" width="100%" alt="Proof"/>
<sub><b>Proof.</b> Every decision is sealed in a tamper-evident ledger with a cryptographic lineage DAG. Replayable from any point in history.</sub>
</td>
</tr>
</table>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## What you control vs. what the system handles

<br/>

| **What only you can do** | **What ADAAD handles autonomously** |
|---|---|
| GPG-sign Tier 0 changes | Generate mutation proposals via Claude |
| Approve seed promotions | Red-team challenge every proposal before scoring |
| Set constitutional rules | Shadow-execute mutations in zero-write harness |
| Tag version ceremonies | Score against 21 constitutional rules |
| Ratify new invariants | Hash-chain every decision into the ledger |
| Patent and IP decisions | Build cryptographic evolution proof DAGs |
| GA sign-off | Mine failure patterns and propose new invariants |

Your role is setting the rules and signing what matters. The system handles everything else.

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Architecture

<img src="docs/assets/adaad-architecture.svg" width="100%" alt="ADAAD Architecture"/>

ADAAD runs a **16-step Constitutional Evolution Loop (CEL)** on every proposed change. Each step is ordered, gated, and evidenced. There is no skip path. The CEL-ORDER-0 invariant enforces this at runtime — steps that execute out of sequence abort the epoch.

Three AI agents — **Architect** (structural reasoning), **Dream** (mutation generation), and **Beast** (performance pressure) — each apply constitutional rules at different steps. No single agent can approve a change. The governance gate is the only path forward.

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Proven milestones — not roadmap promises

These events happened. The evidence is hash-chained in the ledger.

### ⛓ March 13, 2026 — First autonomous self-evolution (Phase 65)

<img src="docs/assets/adaad-phase65-banner.svg" width="100%" alt="Phase 65"/>

ADAAD identified its own highest-priority capability gap, generated a mutation, ran a sandboxed fitness tournament, scored it against constitutional rules, applied it, and sealed the proof in the ledger. Zero human intervention in the execution path. Full human control of the constitutional framework.

<img src="docs/assets/adaad-phase65-chain.svg" width="100%" alt="Phase 65 hash chain"/>

---

### 🌱 March 20, 2026 — First governed seed epoch (Phase 77)

A capability seed flowed through all 7 governed stages — proposal, human review, CEL injection, constitutional loop, ledger-anchored outcome — producing a cryptographic proof linking every step back to its origin. ADAAD can now propose, evaluate, and record its own capability evolutions under human-supervised constitutional governance. The loop is closed.

---

### ◈ March 22, 2026 — CEL goes live in production (Phase 89)

The Constitutional Evolution Loop is no longer a test harness. Real Claude-generated proposals are flowing through all 16 constitutional steps in production.

---

### 🧭 March 23, 2026 — Cryptographic Evolution Proof DAG (Phase 90 · INNOV-06)

Every mutation in ADAAD's history is now cryptographically bound to all its causal ancestors via Merkle root. Lineage is independently verifiable without system access. You can prove to any third party exactly how any capability evolved — useful for auditors, regulators, and patent counsel.

---

### 🛡 March 24, 2026 — Live Shadow Mutation Execution (Phase 91 · INNOV-07)

Before any mutation is scored and gated, it runs in a zero-write shadow harness against real traffic patterns. The shadow run produces a `ShadowFitnessReport` — divergence rate, error delta, and P99 latency — that gates promotion independently of the main fitness score. A mutation must survive shadow execution *and* the governance gate to advance.

---

### ⚔ March 27, 2026 — Adversarial Red Team as a Constitutional Gate (Phase 92 · INNOV-08)

Every mutation proposal is now challenged by a dedicated Red Team Agent before governance scoring. The Red Team finds code paths the proposing agent didn't cover and fires targeted adversarial cases against them. Proposals that fail are returned. The Red Team is constitutionally incapable of approving anything — its only outputs are PASS or RETURNED. First governed AI evolution system to use adversarial peer-review as a constitutional gate.

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Why you can trust the claims

Every property below is mechanically enforced at runtime. Not policy. Not documentation. Enforced.

**Tamper-evident ledger** — Every event is SHA-256 hash-chained. Alter one entry and every subsequent hash breaks. History cannot be rewritten, and any attempt is immediately detectable.

**Deterministic replay** — Any prior epoch can be re-run from its original inputs and produce byte-identical results. No `datetime.now()`, no `random.random()` in constitutional paths. Enforced by invariant.

**Constitutional gate** — 21 runtime-enforced rules in `constitution.yaml v0.9.0`. If a mutation violates a rule, the epoch halts. There is no configuration option that changes this.

**Adversarial red-team gate** — Every mutation is challenged before fitness scoring (INNOV-08). The agent cannot approve mutations — structural enforcement in code, not policy.

**Shadow execution gate** — Every mutation runs in a zero-write harness (INNOV-07) before live promotion. Write or egress detection is a hard block.

**Cryptographic lineage** — Full evolutionary history is Merkle-rooted in a proof DAG (INNOV-06). Independently verifiable by any third party.

**Human authority is structural** — Your signing key is required for Tier 0 changes. The system cannot bypass this. It is not a configuration option.

**27 Hard-class invariants** — Runtime rules that cannot be disabled, configured around, or violated without the epoch aborting. 27 hard stops, all enforced.

→ [Read the Constitution](docs/CONSTITUTION.md) · [Trust Center](TRUST_CENTER.md) · [Security Invariants Matrix](docs/governance/SECURITY_INVARIANTS_MATRIX.md)

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## 9 shipped world-first innovations

Not prototypes. Each shipped with a full constitutional test suite, human governor sign-off, and a hash-chained evidence artifact.

| # | Innovation | Phase | What it does |
|---|---|---|---|
| INNOV-01 | Constitutional Self-Amendment (CSAP) | 87 | ADAAD can propose amendments to its own rules — subject to unconditional human ratification |
| INNOV-02 | Adversarial Constitutional Stress (ACSE) | 87 | A dedicated agent stress-tests the constitution by attempting to violate every rule |
| INNOV-03 | Temporal Invariant Forecasting (TIFE) | 87 | The system predicts which invariants are likely to be violated in future epochs before they fail |
| INNOV-04 | Semantic Drift Detection (SCDD) | 88 | Detects when the system's constitutional behaviour is drifting from its historical baseline |
| INNOV-05 | Autonomous Organ Emergence (AOEP) | 89 | ADAAD can propose entirely new architectural organs to address capability gaps — requires human ratification |
| INNOV-06 | Cryptographic Evolution Proof DAG (CEPD) | 90 | Full lineage Merkle-rooted and independently verifiable. Legal-grade provenance. |
| INNOV-07 | Live Shadow Mutation Execution (LSME) | 91 | Mutations run in a zero-write shadow harness against real traffic before promotion |
| INNOV-08 | Adversarial Fitness Red Team (AFRT) | 92 | A Red Team Agent challenges every proposal with targeted adversarial cases before governance scoring |
| INNOV-09 | Aesthetic Fitness Signal (AFIT) | 93 | Code readability scored as a constitutionally-bounded fitness dimension — first system to treat aesthetics as a governed signal |
| INNOV-10 | Morphogenetic Memory (MMEM) | 94 | Hash-chained HUMAN-0-gated IdentityLedger encodes the system self-model — consulted pre-proposal to detect identity drift |

20 further innovations are roadmapped. Full specifications: [ADAAD_30_INNOVATIONS.md](ADAAD_30_INNOVATIONS.md)

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Quick start

```bash
pip install adaad

# Start the governance server and Aponi dashboard
python -m adaad.server
# → http://localhost:8000/ui

# Run a governed evolution epoch
python -c "
from runtime.evolution.evolution_loop import EvolutionLoop
loop = EvolutionLoop()
result = loop.run_epoch(context=loop.build_context())
print(f'Epoch complete · {result.mutations_applied} applied · {result.epoch_evidence_hash[:16]}')
"
```

→ [Full quickstart](QUICKSTART.md) · [Android setup](INSTALL_ANDROID.md)

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Runs anywhere — including a $200 Android phone

ADAAD runs on any hardware that runs Python. Constitutional governance should not depend on cloud infrastructure. If your "governed" system only stays safe with cloud KMS and Kubernetes, those safety properties are on loan from your provider. ADAAD's are yours.

| Platform | Method |
|---|---|
| Linux / macOS | `pip install adaad` |
| Windows | `pip install adaad` (WSL2 for sandbox) |
| Android (Termux) | [TERMUX_SETUP.md](TERMUX_SETUP.md) |
| Android (Pydroid 3) | [INSTALL_ANDROID.md](INSTALL_ANDROID.md) |
| Docker | `docker pull ghcr.io/innovativeai-adaad/adaad` |

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

## Enterprise and commercial use

ADAAD ships a complete commercial documentation suite alongside the open-source core.

| Resource | What it is |
|---|---|
| [Pricing Model](docs/commercial/PRICING_MODEL.md) | Seat-based, usage-based, and hybrid SKUs |
| [Procurement Fast-Lane](docs/commercial/procurement_fastlane/DAY0_PROCUREMENT_FASTLANE_CHECKLIST.md) | Day-0 checklist, DPA/MSA fallback clauses, security Q&A — designed for 5-day close |
| [SLO / SLA Sheet](docs/commercial/procurement_fastlane/SLA_SLO_SHEET.md) | Reliability targets and support tier commitments |
| [Compliance Pack](docs/compliance/) | Data handling, access control matrix, incident response |
| [Trust Center](TRUST_CENTER.md) | Security posture and governance assurance artifacts |
| [Certification Program](docs/training/CERTIFICATION_PROGRAM.md) | Operator · Governance Engineer · Enterprise Administrator |
| [Partner Program](docs/commercial/PARTNER_PROGRAM.md) | Integrator and consultancy onboarding |
| [Data Room Index](docs/strategy/DATA_ROOM_INDEX.md) | Due-diligence artifact map |
| [ROI Model](docs/commercial/ROI_MODEL.md) | Value quantification framework for governance automation |

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

Yes. Phase 65 (March 13, 2026) was the first epoch where ADAAD identified a capability gap, generated a mutation, ran it through all fitness and governance layers, and applied it with zero human intervention in the execution path.

Phase 89 (March 22, 2026) activated the live LLM proposal pipeline. Real Claude-generated proposals are flowing through the full 16-step Constitutional Evolution Loop in production.

Human oversight is structural, not optional. Dustin L. Reid holds the governor role. Any Tier 0 mutation requires his GPG-signed approval. That is not configurable.
</details>

<details>
<summary><b>What makes this different from just running tests in CI?</b></summary>
<br/>

CI tests whether known code passes known assertions. ADAAD governs whether changes to the codebase itself are constitutionally valid, adversarially stress-tested, fitness-improving, and deterministically replayable.

You can delete your CI history. You cannot alter ADAAD's ledger.

ADAAD actively challenges its own proposals via adversarial red-team agents (INNOV-08) and runs them through zero-write shadow execution (INNOV-07) before they reach production. No CI system does this. No CI system has constitutional rules it's bound by. No CI system produces a cryptographic proof of its evolutionary lineage.
</details>

<details>
<summary><b>How does the adversarial Red Team work?</b></summary>
<br/>

Every mutation proposal is handed to the `AdversarialRedTeamAgent` before fitness scoring. The Red Team queries a CodeIntel model for code paths the proposing agent didn't cover, then generates up to five targeted adversarial cases against those paths. Each case runs in a read-only sandbox.

If any case falsifies the proposal, it's returned to the proposer with a `RedTeamFindingsReport` — not scored, not promoted. The Red Team Agent is constitutionally incapable of approving a mutation (AFRT-0). Its only outputs are PASS or RETURNED. This is enforced structurally in code, not policy.

Shipped in Phase 92 (INNOV-08) as the first dedicated adversarial reasoning layer in any governed AI evolution loop.
</details>

<details>
<summary><b>What is the Seed Lifecycle Pipeline?</b></summary>
<br/>

ADAAD generates scored proposals for its own capability improvements. Strong proposals enter a promotion queue, get reviewed by the human governor, and — when approved — flow through the Constitutional Evolution Loop as a governed epoch.

The full provenance chain from proposal to outcome is cryptographically linked via the Cryptographic Evolution Proof DAG (INNOV-06). ADAAD can propose and evaluate its own evolution. The human decides what ships.
</details>

<details>
<summary><b>What are the 9 shipped innovations?</b></summary>
<br/>

INNOV-01 through INNOV-09 shipped across v9.18.0–v9.26.0 (Phases 87–93): Constitutional Self-Amendment (CSAP), Adversarial Constitutional Stress (ACSE), Temporal Invariant Forecasting (TIFE), Semantic Drift Detection (SCDD), Autonomous Organ Emergence (AOEP), Cryptographic Evolution Proof DAG (CEPD), Live Shadow Mutation Execution (LSME), Adversarial Fitness Red Team (AFRT), and Aesthetic Fitness Signal (AFIT).

22 further innovations are roadmapped. Full specifications: [ADAAD_30_INNOVATIONS.md](ADAAD_30_INNOVATIONS.md)
</details>

<details>
<summary><b>Why does it run on a $200 Android phone?</b></summary>
<br/>

Because constitutional governance should not require enterprise infrastructure. ADAAD's safety properties come from SHA-256 hash chains and the Python runtime — not from cloud KMS, Kubernetes, or any third-party service. If those go away, so do your safety guarantees. ADAAD's guarantees are local, deterministic, and yours.
</details>

<details>
<summary><b>How do I evaluate ADAAD for enterprise procurement?</b></summary>
<br/>

Start with the [Trust Center](TRUST_CENTER.md) for a buyer-facing security and governance overview. The [Procurement Fast-Lane package](docs/commercial/procurement_fastlane/DAY0_PROCUREMENT_FASTLANE_CHECKLIST.md) is designed to complete security and legal review within 5 business days. A [Certification Program](docs/training/CERTIFICATION_PROGRAM.md) is available for operators, governance engineers, and enterprise administrators.

For due diligence data room access, see the [Data Room Index](docs/strategy/DATA_ROOM_INDEX.md).
</details>

<img src="docs/assets/adaad-section-divider.svg" width="100%" alt=""/>

<div align="center">

**Built by [Innovative AI LLC](https://github.com/InnovativeAI-adaad) · Governor: Dustin L. Reid**

*The next wave of AI isn't AI that writes your code.*
*It's AI that governs itself while writing your code —*
*and can prove it.*

<br/>

**[⚡ Get Started](QUICKSTART.md)** &nbsp;·&nbsp; **[📜 Constitution](docs/CONSTITUTION.md)** &nbsp;·&nbsp; **[📖 Thesis](docs/thesis/ADAAD_THESIS.md)** &nbsp;·&nbsp; **[🗺 Roadmap](ROADMAP.md)** &nbsp;·&nbsp; **[🏛 Trust Center](TRUST_CENTER.md)**

</div>
