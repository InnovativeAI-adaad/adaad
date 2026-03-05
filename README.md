# ADAAD

<p align="center">
  <img src="docs/assets/adaad-banner.svg" width="860" alt="ADAAD — governed autonomy platform banner">
</p>

<p align="center">
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml/badge.svg">
  </a>
  <img alt="Status" src="https://img.shields.io/badge/Status-Stable-2ea043">
  <img alt="Version" src="https://img.shields.io/badge/Version-v1.1-2ea043">
  <img alt="Governance" src="https://img.shields.io/badge/Governance-Fail--Closed-critical">
  <img alt="Replay" src="https://img.shields.io/badge/Replay-Deterministic-0ea5e9">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-blue.svg">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-green.svg"></a>
</p>

<p align="center">
  <img alt="Replay" src="https://img.shields.io/badge/Replay-Deterministic-0ea5e9?style=for-the-badge">
  <img alt="Evidence" src="https://img.shields.io/badge/Evidence-Ledger_Anchored-22c55e?style=for-the-badge">
  <img alt="Policy" src="https://img.shields.io/badge/Policy-Constitutional-f97316?style=for-the-badge">
  <img alt="Release" src="https://img.shields.io/badge/Releases-Governance_Gated-a855f7?style=for-the-badge">
</p>

<p align="center">
  <a href="QUICKSTART.md"><strong>Quick Start →</strong></a> ·
  <a href="docs/README.md"><strong>Documentation</strong></a> ·
  <a href="examples/single-agent-loop/README.md"><strong>Examples</strong></a> ·
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/issues"><strong>Issues</strong></a>
</p>

> **Deterministic, policy-governed autonomous code evolution.**
> ADAAD enforces constitutional mutation gates, deterministic replay verification, and fail-closed execution across every governed workflow.

**Last reviewed:** 2026-03-05 · **Constitution:** v0.3.0 · **Version:** 1.4.0 · **Milestones:** ADAAD-7 ✅ · ADAAD-8 ✅ · ADAAD-9 ✅ · ADAAD-10 ✅ · ADAAD-10 ✅ · ADAAD-11 🔵

> ℹ️ Visual conventions follow [docs/DOCS_VISUAL_STYLE_GUIDE.md](docs/DOCS_VISUAL_STYLE_GUIDE.md).

---

## What ADAAD Is

ADAAD is a governance layer for autonomous code mutation. It makes autonomy **reproducible**, **auditable**, and **constitutionally constrained** — not just fast.

```
Propose → Simulate → Replay-Verify → Policy Gate → Execute → Attach Evidence → Archive
```

Every step is ledger-anchored. Every decision is deterministic. Every failure is closed, not deferred.

<p align="center">
  <img src="docs/assets/governance-flow.svg" width="700" alt="ADAAD governance flow: propose, simulate, replay verify, policy gate, execute, evidence attach, archive">
</p>

---

## Platform Highlights

| Capability | What it delivers |
|---|---|
| 🔁 **Deterministic replay** | Re-runs produce byte-identical, auditable governance decisions |
| 🛡️ **Fail-closed constitutional gating** | Mutations halt automatically on policy, replay, or evidence failure |
| 🧾 **Ledger-anchored evidence** | Every governed step traces to durable, verifiable artifacts |
| 🚦 **Release evidence gates** | Milestone tags require objective evidence before any release |
| 👥 **Reviewer reputation engine** | Calibrates reviewer panel size by epoch-scoped reputation score |
| 🧪 **Policy simulation mode** | Replay historical epochs under hypothetical constraints — zero live governance side effects |
| 📦 **Governance profile export** | Deterministic simulation artifacts with schema-enforced `simulation: true` and SHA-256 digest |
| 🔒 **Fail-closed boot hardening** | Boot rejects unknown `ADAAD_ENV`, dev-mode in strict envs, missing signing keys |
| 🛡️ **Federation key pinning** | Messages accepted only from registered key IDs; caller-supplied substitution rejected |
| 🧹 **Sandbox injection hardening** | Preflight blocks shell metacharacters, IFS bypass, `eval`/`exec`/`source`, null-byte injection |
| 🧠 **Versioned memory subsystem** | Append-only state versions with confidence metadata and non-destructive rollback pointers |

---

## Start Here

<details open>
<summary><strong>Choose your role</strong></summary>

| Role | Entry point | Goal |
|---|---|---|
| 🧪 First-time evaluator | [QUICKSTART.md](QUICKSTART.md) | Governed run in under 5 minutes |
| 👩‍💻 Contributor | [CONTRIBUTING.md](CONTRIBUTING.md) + [docs/ARCHITECTURE_CONTRACT.md](docs/ARCHITECTURE_CONTRACT.md) | Change code without breaking governance invariants |
| 🔐 Security reviewer | [docs/SECURITY.md](docs/SECURITY.md) + [docs/governance/SECURITY_INVARIANTS_MATRIX.md](docs/governance/SECURITY_INVARIANTS_MATRIX.md) | Validate auth, signing, and fail-closed controls |
| 🧾 Auditor / release owner | [docs/release/release_checklist.md](docs/release/release_checklist.md) + [docs/RELEASE_EVIDENCE_MATRIX.md](docs/RELEASE_EVIDENCE_MATRIX.md) | Verify go/no-go readiness and evidence completeness |

</details>

<details>
<summary><strong>Fast-path links</strong></summary>

- ⚡ First run: [QUICKSTART.md](QUICKSTART.md)
- 🧪 End-to-end sample: [examples/single-agent-loop/README.md](examples/single-agent-loop/README.md)
- 📚 Docs hub: [docs/README.md](docs/README.md)
- 🧱 Build strategy: [docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md](docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md)
- 🛡️ Security: [docs/SECURITY.md](docs/SECURITY.md)

</details>

---

## Operator Promises

- **Clear fail-closed behavior** over silent success.
- **Replay-verifiable decisions** over opaque automation.
- **Evidence-first workflows** — no "it works on my machine."
- **Explicit contracts** (architecture, determinism, auth) for safer collaboration.

---

## Why ADAAD Exists

> ⚖️ Autonomy without governance becomes non-deterministic risk.
> **ADAAD scales controlled, replay-verifiable evolution.**

| Without Governance | With ADAAD |
|---|---|
| Non-deterministic mutation | Deterministic replay validation |
| Unbounded autonomy | Constitutional policy gating |
| Opaque changes | Ledger-anchored evidence |
| Silent drift | Fail-closed enforcement |

ADAAD treats mutation as a **governed, evidence-bound lifecycle** — not a blind rewrite.


---

## ADAAD-8 · Policy Simulation Mode

> v1.2.0 · Merged 2026-03-05

The policy simulation mode allows operators to express hypothetical governance constraints, replay them against historical epochs, and measure tradeoffs before any live policy is amended.

**Foundational insight:** ADAAD already possesses everything simulation needs — an append-only ledger, a constitutional evaluation engine, and epoch-level fitness scores. The simulation layer is a governed evaluation skin over existing infrastructure, not a parallel execution engine.

### Isolation invariant

`SimulationPolicy.simulation = True` is checked at the `GovernanceGate` boundary before any state-affecting operation. No simulated constraint can reach a live governance surface. Zero ledger writes, zero constitution state transitions, zero mutation executor calls.

### Simulation API

| Endpoint | Description |
|---|---|
| `POST /simulation/run` | Run a DSL policy block against epoch range |
| `GET /simulation/results/{run_id}` | Retrieve a completed simulation run |

### DSL constraint types (10 core, v1.3-locked)

| Constraint | Example |
|---|---|
| Approval threshold | `require_approvals(tier=PRODUCTION, count=3)` |
| Risk ceiling | `max_risk_score(threshold=0.4)` |
| Mutation rate ceiling | `max_mutations_per_epoch(count=10)` |
| Complexity delta ceiling | `max_complexity_delta(delta=0.15)` |
| Tier lockdown | `freeze_tier(tier=PRODUCTION)` |
| Rule assertion | `require_rule(rule_id=lineage_continuity, severity=BLOCKING)` |
| Coverage floor | `min_test_coverage(threshold=0.80)` |
| Entropy cap | `max_entropy_per_epoch(ceiling=0.30)` |
| Reviewer escalation | `escalate_reviewers_on_risk(threshold=0.6, count=2)` |
| Lineage depth | `require_lineage_depth(min=3)` |

### GovernanceProfile export

Simulation runs export as self-contained `GovernanceProfile` artifacts. `simulation: true` is schema-enforced in every export. Determinism guarantee: identical ledger slice + identical `SimulationPolicy` + identical epoch-scoped scoring versions → identical `profile_digest`.

---

## Governed Mutation Lifecycle

1. **Propose** — submit candidate mutation through governed intake.
2. **Simulate** — evaluate in a policy-bounded, sandboxed runtime.
3. **Replay-verify** — confirm expected state transition is deterministic.
4. **Gate** — enforce constitutional and governance rules.
5. **Execute** — proceed only when all required controls pass.
6. **Attach evidence** — bind artifacts and lineage to the ledger.
7. **Archive** — preserve decisions for audit and reproducibility.

> 🚫 If replay diverges, policy fails, or evidence cannot be attached — **mutation halts**. No exceptions. No silent fallback.

---

## Current Architecture State

### API surface

| Endpoint | Description |
|---|---|
| `GET /api/health` | Runtime health + version |
| `GET /api/mutations` | Mutation registry |
| `GET /api/epochs` | Epoch index |
| `GET /api/constitution/status` | Constitution version + active rules |
| `GET /api/system/intelligence` | System intelligence telemetry |
| `POST /api/mutations/proposals` | Governed proposal intake |
| `GET /api/audit/epochs/{epoch_id}/replay-proof` | Replay proof bundle |
| `GET /api/audit/epochs/{epoch_id}/lineage` | Mutation lineage chain |
| `GET /api/audit/bundles/{bundle_id}` | Forensic bundle |
| `GET /governance/reviewer-calibration` | Reviewer reputation + tier calibration *(ADAAD-7)* |
| `GET /api/lint/preview` | Deterministic lint preflight |
| `WS /ws/events` | Real-time governance event stream |

### Aponi dashboard

Aponi provides governance-first authoring and forensic analysis. **Authoring and analysis only** — it does not grant execution authority.

<p align="center">
  <img src="docs/assets/brand/aponi-context.svg" width="760" alt="Aponi context: UI authoring feeds governed execution without bypassing constitutional gates">
</p>

- Proposals submit through governed intake (`POST /api/mutations/proposals`).
- `authority_level` is clamped server-side by constitutional validation.
- Queue admission ≠ deployment approval — constitutional, replay, and review gates remain in effect.

---

## ADAAD-7 · Reviewer Reputation & Calibration

> Constitution v0.3.0 · Merged 2026-03-05

The reviewer reputation engine calibrates **how many reviewers** a mutation requires. Reviewer authority and voting are never modified.

| Dimension | Weight | Signal |
|---|---|---|
| Override rate | 0.30 | How often reviewer decisions are overridden |
| Long-term mutation impact | 0.30 | Quality of mutations reviewers approved |
| Latency | 0.20 | Responsiveness within SLA |
| Governance alignment | 0.20 | Adherence to constitutional expectations |

**Architectural invariants:**
- Constitutional floor: minimum 1 human reviewer — enforced across all tiers, all scores.
- Epoch weight snapshot: weights snapshotted per epoch; replay binds to epoch-scoped snapshot.
- Score version binding: `scoring_algorithm_version` recorded in every ledger event.

---

## Environment Configuration

| Variable | Purpose |
|---|---|
| `ADAAD_ENV` | **Required.** `dev`, `test`, `staging`, `production`, `prod`. Unknown values cause `SystemExit` at boot. |
| `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY` | **Required in strict envs.** HMAC key for governance session tokens. |
| `CRYOVANT_DEV_MODE` | Enable dev-only overrides. Rejected in strict environments at boot. |
| `ADAAD_DISPATCH_LATENCY_BUDGET_MS` | Dispatcher latency budget |
| `ADAAD_DISPATCH_LATENCY_MODE` | `static` or `adaptive` |
| `ADAAD_DETERMINISTIC_LOCK` | Freeze deterministic runtime behavior |
| `ADAAD_CONSTITUTION_STRICT` | Strict constitution enforcement mode |

Full reference: [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)

---

## Quick Start

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git && cd ADAAD
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.server.txt
python nexus_setup.py
./quickstart.sh
```

Then run the governed dry-run:

```bash
python -m app.main --dry-run --replay audit --verbose
```

Full guide: [QUICKSTART.md](QUICKSTART.md)

---

## Phase 0 Hardening (v1.1) — Complete

| Finding | Description | Status | PR |
|---|---|---|---|
| C-01 | No boot-time env validation | ✅ Resolved | PR-HARDEN-01 |
| C-02 | Sandbox injection fragment list incomplete | ✅ Resolved | Phase 0 inline |
| C-03 | Federation caller-supplied public key | ✅ Resolved | PR-SECURITY-01 |
| H-01 | Python version inconsistency in CI | ✅ Resolved | PR-CI-01 |
| H-08 | SPDX header coverage | ✅ Resolved | PR-CI-02 |

See [docs/releases/1.1.0.md](docs/releases/1.1.0.md) for full release notes.

---

## Governance Guarantees (v1.1 + ADAAD-7)

**Currently enforced:**
- Deterministic constitutional envelope hashing
- Replay-stable governance evaluation
- Epoch-scoped reviewer reputation scoring
- Constitutional floor ≥ 1 human reviewer (architecturally enforced)
- Fail-closed boot environment validation
- Federation key pinning — untrusted `key_id` rejected at transport
- Sandbox injection hardening — IFS bypass, `eval`/`exec`/`source`, null-byte blocked
- SPDX license header coverage across all Python source files

**Not yet implemented:**
- Live market signal adapters
- True Darwinian agent budget competition
- Real container-level isolation backend
- Fully autonomous multi-node federation

---

## Project Status

| Aspect | Status |
|---|---|
| Maturity | Stable · v1.2 |
| Completed milestones | ADAAD-6 ✅ · ADAAD-7 ✅ · ADAAD-8 ✅ |
| Constitution | v0.3.0 · 14 rules active |
| Replay mode | Audit + strict governance-ready |
| Mutation execution | Fail-closed, policy-gated |
| Boot validation | Fail-closed |
| Federation trust | Key-pinned |
| Recommended for | Governed audit workflows · replay verification · staged mutation review |
| Not ready for | Unattended production autonomy |

---

## Reference Index

### Governance & Determinism
- [Constitution](docs/CONSTITUTION.md) · [Determinism contract](docs/DETERMINISM.md) · [Architecture contract](docs/ARCHITECTURE_CONTRACT.md)
- [Threat model](docs/THREAT_MODEL.md) · [Governance maturity model](docs/GOVERNANCE_MATURITY_MODEL.md)
- [Security invariants matrix](docs/governance/SECURITY_INVARIANTS_MATRIX.md)

### Release & Compliance
- [Release evidence matrix](docs/RELEASE_EVIDENCE_MATRIX.md) · [Release checklist](docs/release/release_checklist.md)
- [Release audit checklist](docs/releases/RELEASE_AUDIT_CHECKLIST.md) · [v1.1.0 release notes](docs/releases/1.1.0.md)
- [Claims-to-evidence matrix](docs/comms/claims_evidence_matrix.md)

### Security
- [Security](docs/SECURITY.md) · [Federation key registry](docs/governance/FEDERATION_KEY_REGISTRY.md)
- [Determinism contract spec](docs/governance/DETERMINISM_CONTRACT_SPEC.md)

---

## Non-Goals

ADAAD does not: generate model intelligence · replace CI pipelines · remove required human oversight · guarantee semantic correctness beyond governed constraints.

---

## Licensing

MIT License. See [LICENSE](LICENSE) and [LICENSES.md](LICENSES.md).
Run `python scripts/validate_license_compliance.py` for SPDX compliance verification.

---

<p align="center">
  <img alt="Deterministic" src="https://img.shields.io/badge/Deterministic-Replay_Enforced-0ea5e9">
  <img alt="Governed" src="https://img.shields.io/badge/Governed-Constitutional-f97316">
  <img alt="Auditable" src="https://img.shields.io/badge/Auditable-Ledger_Anchored-22c55e">
</p>
