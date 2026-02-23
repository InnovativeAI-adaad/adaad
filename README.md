# ADAAD

> **Deterministic, policy-governed autonomous code evolution.**

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
  <a href="QUICKSTART.md"><strong>Get Started →</strong></a> ·
  <a href="docs/README.md"><strong>Documentation</strong></a> ·
  <a href="examples/single-agent-loop/README.md"><strong>Examples</strong></a> ·
  <a href="https://github.com/InnovativeAI-adaad/ADAAD/issues"><strong>Issues</strong></a>
</p>

<p align="center">
  <img src="docs/assets/governance-flow.svg" width="680" alt="ADAAD governance flow: Propose, Simulate, Replay Verify, Policy Gate, Execute, Evidence Attach, Archive">
</p>

## Why ADAAD Exists

Unconstrained autonomous code mutation creates risk.

ADAAD exists to ensure that autonomy remains:
- Deterministic
- Governed
- Auditable
- Replay-verifiable
- Fail-closed

Autonomy without governance scales chaos.
ADAAD scales controlled evolution.

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

## Strategic Documentation Path

- Canonical docs home: [docs/README.md](docs/README.md)
- Determinism contract: [docs/DETERMINISM.md](docs/DETERMINISM.md)
- Architecture contract: [docs/ARCHITECTURE_CONTRACT.md](docs/ARCHITECTURE_CONTRACT.md)
- One-page architecture summary: [docs/ARCHITECTURE_SUMMARY.md](docs/ARCHITECTURE_SUMMARY.md)
- Threat model: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)
- Governance maturity model: [docs/GOVERNANCE_MATURITY_MODEL.md](docs/GOVERNANCE_MATURITY_MODEL.md)
- Release evidence and checklist: [docs/RELEASE_EVIDENCE_MATRIX.md](docs/RELEASE_EVIDENCE_MATRIX.md), [docs/releases/RELEASE_AUDIT_CHECKLIST.md](docs/releases/RELEASE_AUDIT_CHECKLIST.md)

## Project Status

| Aspect | Status |
|---|---|
| Recommended for | Governed audit workflows, replay verification, staged mutation review |
| Not ready for | Unattended production autonomy |
| Maturity | Stable / v1.0 |
| Replay mode | Audit and strict governance-ready |
| Mutation execution | Fail-closed and policy-gated |
