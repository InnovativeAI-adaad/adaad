# ADAAD ![Stable](https://img.shields.io/badge/Status-Stable-2ea043)

> Deterministic, policy-governed autonomous code evolution.
> ADAAD enforces constitutional mutation gates, deterministic replay checks, and fail-closed execution behavior.
> It is built for governed staging and audit workflows.

> **Doc metadata:** Audience: Operator / Contributor / Auditor · Last validated release: `v1.0.0`

> ✅ **Do this:** Read `docs/FOUNDATIONS.md` first, then execute setup from `QUICKSTART.md`.
>
> ⚠️ **Caveat:** Unattended production autonomy is disabled by scope and policy.
>
> 🚫 **Out of scope:** ADAAD does not train models, replace CI/CD, or bypass governance gates.

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

## Table of Contents

- [What ADAAD enforces](#what-adaad-enforces)
- [Foundations (single source of truth)](#foundations-single-source-of-truth)
- [Governance mode matrix](#governance-mode-matrix)
- [Mutation stage contract](#mutation-stage-contract)
- [Architecture at a glance](#architecture-at-a-glance)
- [Determinism and replay boundaries](#determinism-and-replay-boundaries)
- [Canonical import ownership](#canonical-import-ownership)
- [Adapter policy](#adapter-policy)
- [Aponi dashboard isolation](#aponi-dashboard-isolation)
- [Versioning policy](#versioning-policy)
- [What this system will never do](#what-this-system-will-never-do)
- [Quick start](#quick-start)
- [Security](#security)
- [Documentation map](#documentation-map)
- [License](#license)

## What ADAAD enforces

ADAAD enforces policy-first autonomous mutation control:

- Governance gates evaluate mutation eligibility.
- Replay checks enforce deterministic decision equivalence.
- Divergence fails closed before mutation execution.
- Ledger and lineage evidence are auditable and append-only.

## Foundations (single source of truth)

Governance posture, determinism contract, replay guarantees, and mutation philosophy are maintained in one authoritative document:

- [`docs/FOUNDATIONS.md`](docs/FOUNDATIONS.md)

Use this to prevent drift across README surfaces.

## Governance mode matrix

| Mode    | Mutation  | Replay   | Promotion  | Use Case           |
| ------- | --------- | -------- | ---------- | ------------------ |
| dry-run | Simulated | Optional | Disabled   | Local validation   |
| audit   | Blocked   | Required | Disabled   | Governance check   |
| strict  | Allowed   | Required | Controlled | Staged evolution   |
| staging | Allowed   | Required | Enabled    | Pre-release gating |

Exactly one mode must be active at runtime.

## Mutation stage contract

| Stage         | Enforced  | Failure Behavior | Evidence Emitted |
| ------------- | --------- | ---------------- | ---------------- |
| AST Parse     | Required  | Reject           | parse_validation_event |
| Import Root   | Required  | Reject           | import_boundary_violation |
| Sandbox       | Required  | Fail Closed      | sandbox_integrity_event |
| Fitness       | Threshold | Reject           | fitness_rejection_event |
| Certification | Required  | Block Promotion  | promotion_block_event |

## Architecture at a glance

```text
app.main
 ├── Orchestrator
 │    ├── Invariants
 │    ├── Cryovant
 │    ├── Replay
 │    ├── MutationEngine
 │    └── GovernanceGate
 └── Aponi Dashboard
```

<p align="center">
  <img src="docs/assets/architecture-simple.svg" width="760" alt="ADAAD simplified architecture diagram">
</p>

## Determinism and replay boundaries

Deterministic Inputs:
- Time
- Randomness
- External providers

Replay Guarantees:
- Stage replay
- Evidence bundle replay
- Attestation replay

Replay boundary:

```text
Mutation → Sandbox → Metrics → Evidence → Ledger → Replay
```

## Canonical import ownership

Use `runtime.*` as authoritative governance and replay implementation paths.

- Foundation primitives: `runtime.governance.foundation.*`
- Evolution governance paths: `runtime.evolution.*`
- Replay/governor integrations: `runtime.governance.*` + `runtime.evolution.*`
- Determinism provider: `runtime.governance.foundation.determinism`

> CI fails builds on non-canonical runtime imports.

`governance.*` exists as compatibility-only re-export surface. It is not a second implementation root.

## Adapter policy

Adapters MUST:
- Contain no business logic
- Contain no mutation logic
- Forward only to `runtime.*`

Adapters are compatibility-only surfaces.
They are not stable API and may change without notice.

## Aponi dashboard isolation ![Experimental](https://img.shields.io/badge/Aponi-Experimental-orange)

Aponi consumes read-only governance surfaces.
It does not mutate governance state.

Operator value:
- Governance health visibility
- Replay divergence forensics
- Risk and policy simulation views

## Versioning policy

- **MAJOR** – Governance invariant changes
- **MINOR** – New gates, non-breaking
- **PATCH** – Documentation and internal fixes

## What this system will never do

- Run unattended in production
- Bypass governance gates
- Self-modify runtime governance layer outside policy controls

## Quick start

Use [`QUICKSTART.md`](QUICKSTART.md) for setup, validation, and reset workflows.

Fast path:

```bash
./quickstart.sh
python -m app.main --dry-run --replay audit --verbose
```

## Security

Security disclosure and key-handling guidance:

- [`docs/SECURITY.md`](docs/SECURITY.md)

Do not open public issues for vulnerabilities.

## Documentation map

- Foundations: [`docs/FOUNDATIONS.md`](docs/FOUNDATIONS.md)
- Constitution: [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md)
- Quick start: [`QUICKSTART.md`](QUICKSTART.md)
- Architecture boundaries: [`docs/ARCHITECTURE_CONTRACT.md`](docs/ARCHITECTURE_CONTRACT.md)
- Full index: [`docs/manifest.txt`](docs/manifest.txt)

## License

Apache 2.0. See [`LICENSE`](LICENSE).
