# ADAAD ![Stable](https://img.shields.io/badge/Status-Stable-2ea043)

> Deterministic, policy-governed autonomous code evolution.
> ADAAD enforces constitutional mutation gates, deterministic replay checks, and fail-closed execution behavior.
> It is built for governed staging and audit workflows.

ADAAD is a governance layer for autonomous code mutation. It exists to ensure autonomy remains reproducible, auditable, and constrained by constitutional policy.

<p align="center">
  <img src="docs/assets/adaad-banner.svg" width="850" alt="ADAAD governed autonomy banner">
</p>

<p align="center">
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/InnovativeAI-adaad/ADAAD/actions/workflows/ci.yml/badge.svg"></a>
  <a href="QUICKSTART.md"><img alt="Quick Start" src="https://img.shields.io/badge/Quick_Start-5%20Minutes-success"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10+-blue.svg">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Apache%202.0-blue.svg"></a>
  <img alt="Governance" src="https://img.shields.io/badge/Governance-Fail--Closed-critical">
</p>

<p align="center">
  <img alt="Replay" src="https://img.shields.io/badge/Replay-Deterministic-0ea5e9?style=for-the-badge">
  <img alt="Evidence" src="https://img.shields.io/badge/Evidence-Ledger_Anchored-22c55e?style=for-the-badge">
  <img alt="Policy" src="https://img.shields.io/badge/Policy-Constitutional-f97316?style=for-the-badge">
  <img alt="Release" src="https://img.shields.io/badge/Releases-Governance_Gated-a855f7?style=for-the-badge">
</p>

<p align="center">
  <a href="QUICKSTART.md"><strong>Get Started →</strong></a> ·
  <a href="docs/README.md"><strong>Documentation</strong></a> ·
  <a href="examples/single-agent-loop/README.md"><strong>Examples</strong></a> ·
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/issues"><strong>Issues</strong></a>
</p>

<p align="center">
  <img src="docs/assets/governance-flow.svg" width="680" alt="ADAAD governance flow: Propose, Simulate, Replay Verify, Policy Gate, Execute, Evidence Attach, Archive">
</p>

## ✨ Platform Highlights

| Capability | Why it matters |
| --- | --- |
| 🔁 Deterministic replay verification | Re-runs produce auditable, reproducible governance decisions. |
| 🛡️ Fail-closed constitutional gating | Mutations halt automatically when policy/replay/evidence constraints fail. |
| 🧾 Ledger-anchored evidence | Every governed step can be traced to durable artifacts for audit and review. |
| 🚦 Release evidence gates | Public-readiness milestones require objective evidence completion before release. |

## 🎬 Operator Journey (at a glance)

```text
Discover candidate → Simulate safely → Replay-verify outcomes → Enforce constitutional policy
        ↓                    ↓                     ↓                              ↓
    Evidence capture → Lineage append → Governance decision → Stage for governed review
```

<details>
<summary><strong>Open fast-path links</strong></summary>

- ⚡ First run in minutes: [QUICKSTART.md](QUICKSTART.md)
- 🧪 End-to-end sample: [examples/single-agent-loop/README.md](examples/single-agent-loop/README.md)
- 📚 Canonical docs hub: [docs/README.md](docs/README.md)
- 🛡️ Security + disclosure: [docs/SECURITY.md](docs/SECURITY.md)

</details>


## Why ADAAD Exists

Unconstrained autonomous mutation introduces systemic risk.

> ⚖️ Autonomy without governance becomes non-deterministic risk.  
> **ADAAD scales controlled, replay-verifiable evolution.**

<p align="center">
  <img alt="Deterministic" src="https://img.shields.io/badge/Deterministic-Replay_Enforced-0ea5e9">
  <img alt="Governed" src="https://img.shields.io/badge/Governed-Constitutional-f97316">
  <img alt="Auditable" src="https://img.shields.io/badge/Auditable-Ledger_Anchored-22c55e">
</p>

| Without Governance | With ADAAD |
|---|---|
| Non-deterministic mutation | Deterministic replay validation |
| Unbounded autonomy | Constitutional policy gating |
| Opaque changes | Ledger-anchored evidence |
| Silent drift | Fail-closed enforcement |

ADAAD treats mutation as a governed, evidence-bound lifecycle—not a blind rewrite.

---

ADAAD ensures autonomy remains:
- Deterministic
- Governed
- Auditable
- Replay-verifiable
- Fail-closed

## Fail-Closed by Design

If replay diverges, policy fails, or evidence cannot be attached, mutation execution halts.

No mutation executes without governance validation.

## What ADAAD Does

ADAAD orchestrates a governed mutation lifecycle:

1. Propose candidate mutation.
2. Simulate in policy-bounded runtime.
3. Replay-verify expected state transition.
4. Enforce constitutional and governance gates.
5. Execute only when all required controls pass.
6. Attach evidence and lineage artifacts.
7. Archive decisions for audit and reproducibility.

## Trust Guarantees

ADAAD enforces:

- Deterministic replay validation
- Fail-closed mutation execution
- Policy-bound runtime enforcement
- Lineage and mutation traceability
- Constitution-level governance constraints

All governance decisions are reproducible across runs.

## Non-Goals

ADAAD does not:
- Generate model intelligence
- Replace CI pipelines
- Remove human oversight where required
- Guarantee semantic correctness beyond governed constraints

## Quick Start

- Follow [QUICKSTART.md](QUICKSTART.md) for environment setup and validation.
- Run `./quickstart.sh` to execute baseline checks.
- Run `python -m app.main --dry-run --replay audit --verbose` for a governed dry-run.

## Dependency Baseline (Production)

- `requirements.server.txt` is the source of truth for production/runtime dependency versions.
- `archives/backend/requirements.txt` mirrors the same pinned `fastapi`, `uvicorn`, and `anthropic` versions to preserve archive reproducibility against the active runtime baseline.
- Run `python scripts/check_dependency_baseline.py` to enforce this mirror invariant before merge/release (works from any current working directory and fails if tracked packages are unpinned or divergent).

## Strategic Documentation Path

- Canonical docs home: [docs/README.md](docs/README.md)

### Governance and Determinism
- [Determinism contract](docs/DETERMINISM.md)
- [Architecture contract](docs/ARCHITECTURE_CONTRACT.md)
- [One-page architecture summary](docs/ARCHITECTURE_SUMMARY.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Governance maturity model](docs/GOVERNANCE_MATURITY_MODEL.md)

### Release and Compliance
- [Release evidence matrix](docs/RELEASE_EVIDENCE_MATRIX.md)
- [Release audit checklist](docs/releases/RELEASE_AUDIT_CHECKLIST.md)

## Project Status

| Aspect | Status |
|---|---|
| Recommended for | Governed audit workflows, replay verification, staged mutation review |
| Not ready for | Unattended production autonomy |
| Maturity | Stable / v1.0 |
| Replay mode | Audit and strict governance-ready |
| Mutation execution | Fail-closed and policy-gated |


## Start here next

See role-based paths in [docs/README.md](docs/README.md).


## Governance & Determinism Guarantees (Current State)

ADAAD currently guarantees:

- Deterministic constitutional envelope hashing
- Replay-stable governance evaluation
- Canonicalized Aponi integration port
- Configurable and ledger-visible dispatcher latency
- YAML hermetic fallback for constitution loading

ADAAD does **not** yet implement:

- Live market signal adapters
- True Darwinian agent budget competition
- Real container-level isolation backend
- Fully autonomous multi-node federation

### Environment Configuration

| Variable | Purpose |
| --- | --- |
| `ADAAD_DISPATCH_LATENCY_BUDGET_MS` | Dispatcher latency budget |
| `ADAAD_DISPATCH_LATENCY_MODE` | Dispatcher latency mode (`static`/`adaptive`) |
| `ADAAD_DETERMINISTIC_LOCK` | Freeze deterministic runtime behavior |
| `ADAAD_CONSTITUTION_STRICT` | Strict constitution enforcement mode |
