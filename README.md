# ADAAD

<p align="center">
  <img src="docs/assets/adaad-banner.svg" width="860" alt="ADAAD — governed autonomy platform">
</p>

<p align="center">
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml/badge.svg">
  </a>
  <img alt="Version" src="https://img.shields.io/badge/version-1.8.0-2ea043?style=flat-square">
  <img alt="Governance" src="https://img.shields.io/badge/governance-fail--closed-dc2626?style=flat-square">
  <img alt="Replay" src="https://img.shields.io/badge/replay-deterministic-0ea5e9?style=flat-square">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-3b82f6?style=flat-square">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-6b7280?style=flat-square"></a>
</p>

<p align="center">
  <strong>Deterministic · Constitutional · Ledger-Anchored · Production-Grade</strong>
</p>

---

> **ADAAD is a governance platform for autonomous code mutation.**
> Every proposal is simulated, replay-verified, constitutionally gated, and evidence-bound before a single line executes.

---

## How It Works

```
Propose → Simulate → Replay-Verify → Gate → Execute → Attach Evidence → Archive
```

If replay diverges, policy fails, or evidence cannot be attached — **mutation halts. No exceptions.**

<p align="center">
  <img src="docs/assets/governance-flow.svg" width="680" alt="ADAAD governance flow">
</p>

---

## Platform

| Capability | Delivery |
|---|---|
| 🔁 **Deterministic replay** | Re-runs produce byte-identical, auditable governance decisions |
| 🛡️ **Fail-closed constitutional gating** | Mutations halt on any policy, replay, or evidence failure |
| 🧾 **Ledger-anchored evidence** | Every governed step traces to durable, verifiable artifacts |
| 👥 **Reviewer reputation engine** | Epoch-scoped calibration of reviewer panel size and signal weight |
| 🧪 **Policy simulation mode** | Replay historical epochs under hypothetical constraints — zero live side-effects |
| 🔒 **Fail-closed boot hardening** | Rejects unknown `ADAAD_ENV`, dev-mode in strict envs, missing signing keys |
| 🐳 **Container isolation backend** | cgroup v2 enforced sandboxes — pool-managed, health-probed, lifecycle-audited |
| 🏆 **Darwinian budget competition** | Softmax fitness-weighted reallocation; starvation detection; quorum-gated eviction |
| 🌐 **Autonomous multi-node federation** | Raft-inspired consensus, HTTP gossip, constitutional quorum gate across nodes |
| 📡 **Federated market signals** | Live VolatilityIndex / ResourcePrice / DemandSignal gossiped cluster-wide |
| 🎛️ **Market-driven container profiles** | Signal composite selects CONSTRAINED / STANDARD / BURST resource tiers dynamically |

---

## Milestones

| Milestone | Version | Capability | Status |
|---|---|---|---|
| ADAAD-6 | v1.0 | Stable Release — HMAC remediation, 11 constitutional rules, MCP co-pilot | ✅ |
| ADAAD-7 | v1.1 | Reviewer Reputation & Calibration Loop | ✅ |
| ADAAD-8 | v1.2 | Policy Simulation Mode — DSL, epoch replay, governance profile export | ✅ |
| ADAAD-9 | v1.3 | Aponi IDE — proposal editor, constitutional linter, evidence viewer, replay inspector | ✅ |
| ADAAD-10 | v1.4 | Live Market Signal Adapters — FeedRegistry, 3 concrete adapters, webhook | ✅ |
| ADAAD-11 | v1.5 | Darwinian Agent Budget Competition — pool, arbitrator, competition ledger | ✅ |
| ADAAD-12 | v1.6 | Real Container-Level Isolation Backend — orchestrator, health probes, profiles | ✅ |
| ADAAD-13 | v1.7 | Fully Autonomous Multi-Node Federation — Raft consensus, gossip, node supervisor | ✅ |
| ADAAD-14 | **v1.8** | Cross-Track Convergence — market × federation × container × Darwinian unified | ✅ |

---

## Quick Start

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git && cd ADAAD
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.server.txt
python nexus_setup.py && ./quickstart.sh
```

Governed dry-run:

```bash
python -m app.main --dry-run --replay audit --verbose
```

→ Full guide: [QUICKSTART.md](QUICKSTART.md)

---

## Start Here

| Role | Entry point |
|---|---|
| 🧪 First-time evaluator | [QUICKSTART.md](QUICKSTART.md) |
| 👩‍💻 Contributor | [CONTRIBUTING.md](CONTRIBUTING.md) · [Architecture Contract](docs/ARCHITECTURE_CONTRACT.md) |
| 🔐 Security reviewer | [SECURITY.md](docs/SECURITY.md) · [Invariants Matrix](docs/governance/SECURITY_INVARIANTS_MATRIX.md) |
| 🧾 Auditor | [Release Checklist](docs/release/release_checklist.md) · [Evidence Matrix](docs/RELEASE_EVIDENCE_MATRIX.md) |

---

## Authority Invariant

> **GovernanceGate is the sole mutation-approval authority across every surface.**

Market adapters influence fitness scores. Budget arbitrators reallocate pool shares. Container profilers select resource tiers. Federation consensus provides ordering. **None of these surfaces can approve, sign, or execute a mutation.** That authority belongs exclusively to `GovernanceGate`, and the constitutional evaluation it enforces.

This invariant is architecturally enforced, not just documented.

---

## Key Configuration

| Variable | Purpose |
|---|---|
| `ADAAD_ENV` | **Required.** `dev` · `test` · `staging` · `production`. Unknown values cause `SystemExit` at boot. |
| `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY` | **Required in strict envs.** HMAC key for session tokens. |
| `ADAAD_SANDBOX_CONTAINER_ROLLOUT` | `true` activates `ContainerOrchestrator` as default execution backend. |
| `CRYOVANT_DEV_MODE` | Dev-only overrides. Rejected in strict environments at boot. |

→ Full reference: [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)

---

## Reference

**Governance** — [Constitution](docs/CONSTITUTION.md) · [Determinism Contract](docs/DETERMINISM.md) · [Architecture Contract](docs/ARCHITECTURE_CONTRACT.md) · [Threat Model](docs/THREAT_MODEL.md)

**Security** — [SECURITY.md](docs/SECURITY.md) · [Federation Key Registry](docs/governance/FEDERATION_KEY_REGISTRY.md) · [Security Invariants Matrix](docs/governance/SECURITY_INVARIANTS_MATRIX.md)

**Releases** — [Evidence Matrix](docs/RELEASE_EVIDENCE_MATRIX.md) · [Release Checklist](docs/release/release_checklist.md) · [Changelog](CHANGELOG.md) · [Milestone Roadmap](MILESTONE_ROADMAP_ADAAD6-9.md)

**Docs Hub** — [docs/README.md](docs/README.md) · [Examples](examples/single-agent-loop/README.md)

---

## Non-Goals

ADAAD does not: generate model intelligence · replace CI pipelines · remove required human oversight · guarantee semantic correctness beyond governed constraints.

---

<p align="center">
  <img alt="Deterministic" src="https://img.shields.io/badge/Deterministic-Replay_Enforced-0ea5e9?style=for-the-badge">
  <img alt="Governed" src="https://img.shields.io/badge/Governed-Constitutional-f97316?style=for-the-badge">
  <img alt="Auditable" src="https://img.shields.io/badge/Auditable-Ledger_Anchored-22c55e?style=for-the-badge">
  <img alt="Converged" src="https://img.shields.io/badge/v1.8-Cross--Track_Converged-a855f7?style=for-the-badge">
</p>

<p align="center">MIT License · <a href="LICENSE">LICENSE</a> · <a href="LICENSES.md">LICENSES.md</a></p>

---

## AI Mutation Capability Expansion — v2.0

> **Released:** 2026-03-06 | **Branch:** `feature/ai-mutation-capability-expansion-v2`

This release delivers the full **AI mutation engine** — connecting ADAAD to the Claude API for the first time and establishing a production-ready, self-improving evolution loop.

### What's New

| Module | Type | Capability |
|---|---|---|
| `runtime/autonomy/mutation_scaffold.py` | **UPGRADED** | `ScoringWeights`, `PopulationState`, lineage fields, adaptive threshold, elitism bonus |
| `runtime/autonomy/ai_mutation_proposer.py` | **NEW** | Claude API integration — Architect / Dream / Beast agent personas |
| `runtime/autonomy/weight_adaptor.py` | **NEW** | Momentum-based self-calibrating weight learner |
| `runtime/autonomy/fitness_landscape.py` | **NEW** | Persistent win/loss tracker, plateau detection, agent recommendation |
| `runtime/evolution/population_manager.py` | **NEW** | GA-style population evolution with BLX-alpha crossover |
| `runtime/evolution/evolution_loop.py` | **NEW** | Full epoch orchestrator: propose → score → evolve → adapt → record |
| `adaad/core/health.py` | **FIXED** | `gate_ok` flag added to health payload (PR #12) |

### Evolution Epoch Lifecycle

```
FitnessLandscape → AI Propose (3 agents) → PopulationManager.seed()
    → evolve_generation() × N → WeightAdaptor.adapt() → FitnessLandscape.record()
    → EpochResult (epoch_id, accepted_count, weight_accuracy, recommended_next_agent)
```

### Agent Personas

| Agent | Strategy | Mutation Type | Risk Profile |
|---|---|---|---|
| **Architect** | Structural cohesion, interface contracts | `structural` | Low-medium |
| **Dream** | High-novelty, exploratory, cross-domain | `experimental` | High |
| **Beast** | Conservative micro-optimisations, coverage | `performance`/`coverage` | Very low |

### Adaptive Scoring

- **Adaptive threshold:** scales down during exploration epochs (`diversity_pressure > 0`)
- **Elitism bonus:** `+0.05` score for children of elite-roster parents
- **Momentum weight adaptation:** `LR=0.05`, `momentum=0.85` — stable convergence
- **Plateau detection:** `< 20%` win rate across all tracked types → Dream dispatched

### Test Coverage

```
44 new tests — 44 passed (100%)
0 regressions in existing test suite
```

### Quick Start (Evolution Loop)

```python
import os
from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.evolution.evolution_loop import EvolutionLoop

loop = EvolutionLoop(api_key=os.environ["ADAAD_CLAUDE_API_KEY"], generations=3)
context = CodebaseContext(
    file_summaries={"runtime/autonomy/mutation_scaffold.py": "Scoring helpers."},
    recent_failures=[],
    current_epoch_id="epoch-001",
)
result = loop.run_epoch(context)
print(f"Accepted: {result.accepted_count}/{result.total_candidates}")
print(f"Next agent: {result.recommended_next_agent}")
print(f"Weight accuracy: {result.weight_accuracy:.2%}")
```

