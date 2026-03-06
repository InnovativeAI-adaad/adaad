<p align="center">
  <img src="docs/assets/adaad-banner.svg" width="900" alt="ADAAD — Autonomous Development & Adaptation Architecture"/>
</p>

<p align="center">
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml/badge.svg"/>
  </a>
  <img alt="Version" src="https://img.shields.io/badge/version-2.0.0-00d4ff?style=flat-square&labelColor=060d14"/>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-7b61ff?style=flat-square&labelColor=060d14"/>
  <img alt="License" src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square&labelColor=060d14"/>
  <img alt="Android" src="https://img.shields.io/badge/android-pydroid3-f59e0b?style=flat-square&labelColor=060d14"/>
</p>

<p align="center">
  <b>Self-improving software. Governed at every step.</b><br/>
  ADAAD proposes, tests, scores, and evolves code mutations — with deterministic replay, constitutional gating, and a full audit trail. Nothing executes without proof.
</p>

---

## What it does

ADAAD is an **autonomous mutation engine**: it generates, evaluates, and applies code improvements using AI agents, then verifies every decision can be replayed exactly. A human-readable governance constitution controls what's allowed. Every mutation either passes that constitution — or halts completely.

<p align="center">
  <img src="docs/assets/adaad-flow.svg" width="860" alt="ADAAD mutation pipeline"/>
</p>

**The pipeline never advances past a failed step.** Replay divergence, policy rejection, or missing evidence all halt the cycle — no exceptions, no workarounds.

---

## Three AI agents. One governed loop.

<p align="center">
  <img src="docs/assets/adaad-agents.svg" width="680" alt="ADAAD agent personas"/>
</p>

Each epoch, ADAAD asks all three agents to propose mutations. Their proposals compete in a genetic-algorithm population: scored, crossed-over, and ranked. The fittest survive. Weights self-calibrate across epochs.

---

## Start in 60 seconds

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
python onboard.py
```

That's it. `onboard.py` handles environment setup, workspace initialization, schema validation, and a governed dry-run — then shows you exactly where to go next.

> **Requirements:** Python 3.11+ · pip · git

---

## What onboarding does

```
onboard.py
  │
  ├─ 1. Check Python 3.11+
  ├─ 2. Create .venv + install deps
  ├─ 3. Set ADAAD_ENV=dev (safe default)
  ├─ 4. Initialize workspace (nexus_setup.py)
  ├─ 5. Validate governance schemas
  ├─ 6. Run governed dry-run
  │      python -m app.main --dry-run --replay audit
  └─ 7. Print your personalized next steps
```

Every step is idempotent. Run it again at any time — it picks up where it left off.

---

## What you'll see

After `python onboard.py`:

```
✔ Python 3.12.3
✔ Virtual environment ready
✔ Dependencies installed
✔ ADAAD_ENV=dev
✔ Workspace initialized
✔ Governance schemas valid
✔ Dry-run complete — no files modified

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ADAAD is ready.

  Run the dashboard:   python server.py
  Run an epoch:        python -m app.main --verbose
  Explore the docs:    docs/README.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## How the evolution loop works

```python
from runtime.autonomy.ai_mutation_proposer import CodebaseContext
from runtime.evolution.evolution_loop import EvolutionLoop
import os

loop = EvolutionLoop(
    api_key=os.environ["ADAAD_CLAUDE_API_KEY"],
    generations=3,
)

context = CodebaseContext(
    file_summaries={"runtime/autonomy/mutation_scaffold.py": "Scoring engine."},
    recent_failures=[],
    current_epoch_id="epoch-001",
)

result = loop.run_epoch(context)

print(f"Proposals:    {result.total_candidates}")
print(f"Accepted:     {result.accepted_count}")
print(f"Next agent:   {result.recommended_next_agent}")
print(f"Accuracy:     {result.weight_accuracy:.1%}")
print(f"Duration:     {result.duration_seconds:.1f}s")
```

---

## Platform capabilities

| | Capability | What it means |
|---|---|---|
| 🔁 | **Deterministic replay** | Every decision re-runs byte-identical. Divergence halts the pipeline. |
| 🛡️ | **Constitutional gating** | 11 governance axes evaluated per mutation. One failure = full halt. |
| 🧾 | **Ledger-anchored evidence** | Every governed step is signed, hashed, and durably attached. |
| 🤖 | **AI mutation proposals** | Three Claude-powered agents produce diverse, scored candidates each epoch. |
| 📈 | **Self-calibrating weights** | Scoring weights adapt via momentum gradient descent across epochs. |
| 🧬 | **Genetic population evolution** | BLX-alpha crossover, elitism, diversity enforcement per generation. |
| 🗺️ | **Fitness landscape memory** | Win/loss rates tracked per mutation type. Plateau triggers exploration mode. |
| 👥 | **Reviewer reputation** | Epoch-scoped calibration of reviewer panel size and signal weight. |
| 🧪 | **Policy simulation** | Replay historical epochs under hypothetical constraints — zero side-effects. |
| 🐳 | **Container isolation** | cgroup v2 sandboxes — pool-managed, health-probed, lifecycle-audited. |
| 🏆 | **Darwinian budgets** | Softmax fitness-weighted resource reallocation across competing agents. |
| 🌐 | **Multi-node federation** | Raft-inspired consensus, HTTP gossip, constitutional quorum gating. |

---

## Who is this for?

```
I want to...                                  Start here
─────────────────────────────────────────────────────────
Try it in 60 seconds                          python onboard.py
Understand the architecture                   docs/EVOLUTION_ARCHITECTURE.md
Contribute code                               CONTRIBUTING.md
Review the governance model                   docs/CONSTITUTION.md
Audit a release                               docs/RELEASE_EVIDENCE_MATRIX.md
Check security posture                        docs/SECURITY.md
Run on Android / Pydroid3                     docs/ENVIRONMENT_VARIABLES.md
Deploy to production                          docs/release/release_checklist.md
```

---

## Configuration (the four essentials)

| Variable | What it does | Default |
|---|---|---|
| `ADAAD_ENV` | Environment mode. Unknown values halt at boot. | — (required) |
| `ADAAD_CLAUDE_API_KEY` | Anthropic API key for AI mutation proposals. | — (for AI mode) |
| `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY` | HMAC key. Required in strict environments. | — (required in prod) |
| `CRYOVANT_DEV_MODE` | Enables dev-only overrides. Rejected in strict envs. | `0` |

Full reference: [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)

---

## The authority invariant

> **One authority. No exceptions.**

`GovernanceGate` is the only surface that can approve, sign, or execute a mutation. Market adapters, budget arbitrators, container profilers, and federation consensus all influence fitness scores and resource allocation — but **none of them can approve a mutation**. That authority belongs exclusively to the constitutional evaluation inside `GovernanceGate`.

This is architecturally enforced, not just documented.

---

## Milestones

| Version | Capability |
|---|---|
| **v2.0** | AI mutation engine — Claude API, 3 agent personas, GA evolution, adaptive weights |
| v1.8 | Cross-track convergence — market × federation × container × Darwinian unified |
| v1.7 | Fully autonomous multi-node federation — Raft consensus, gossip, node supervisor |
| v1.6 | Real container-level isolation — cgroup v2, orchestrator, health probes |
| v1.5 | Darwinian agent budget competition — pool, arbitrator, ledger |
| v1.4 | Live market signal adapters — FeedRegistry, 3 adapters, webhook |
| v1.3 | Aponi IDE — proposal editor, linter, evidence viewer, replay inspector |
| v1.0 | Stable release — HMAC, 11 constitutional rules, MCP co-pilot |

---

## Non-goals

ADAAD does not: replace human judgment · guarantee semantic correctness · remove required oversight · operate without an audit trail.

---

<p align="center">
  <a href="docs/CONSTITUTION.md">Constitution</a> ·
  <a href="docs/EVOLUTION_ARCHITECTURE.md">Architecture</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="docs/SECURITY.md">Security</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

<p align="center">
  <sub>MIT License · <a href="LICENSE">LICENSE</a></sub>
</p>
