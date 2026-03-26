# Data Handling

## Purpose

This document summarizes what data ADAAD stores, what data it transmits, and how controls are enforced in fail-closed governance flows.

## Data Classification

| Class | Examples | Primary storage surface | Transmission surface |
| --- | --- | --- | --- |
| Governance events | `GovernanceDecisionEvent`, `merge_attestation.v1`, replay attestations | Runtime ledger/event stores under governed runtime paths | Internal APIs and controlled federation channels |
| Replay artifacts | Replay manifests, replay digests, replay proof metadata | Replay/lineage artifact directories and evidence bundles | CI artifacts, controlled operator retrieval |
| Security/auth metadata | Token verification outcomes, signature validation outcomes, key IDs | Security audit logs and ledger events | In-process verification flows; no plaintext secret export |
| Operational telemetry | Determinism telemetry, fail-closed reasons, gate outcomes | Telemetry/event sinks and governance reports | Metrics endpoints for authorized operators |
| Documentation/evidence metadata | Claims-evidence matrix links, runbook references | `docs/` repository content | Git-based collaboration + release packaging |

## Stored Data (High-Level)

1. **Append-only governance and lineage records** used for determinism, replay, and integrity verification.
2. **Replay validation artifacts** (digests, manifests, and attestation metadata).
3. **Security decision evidence** (auth/signature pass/fail outcomes, fail-closed reasoning).
4. **Governance gate outputs** from validation scripts and CI checks.

## Transmitted Data (High-Level)

1. **Federation messages** constrained by trusted key registry and signature validation.
2. **Operator/API responses** from read-only governance status endpoints.
3. **CI/release evidence summaries** produced by validation tooling.

## Explicit Non-Goals / Guardrails

- No policy path permits bypassing signature, replay, or governance gates.
- Unknown/malformed governance/security states are treated as fail-closed.
- Controls rely on deterministic, reproducible evidence rather than mutable operator memory.

## Technical Evidence

- Security invariants and fail-closed authentication/replay constraints: `docs/governance/SECURITY_INVARIANTS_MATRIX.md`.
- Fail-closed triage/recovery procedures and post-incident validation: `docs/governance/fail_closed_recovery_runbook.md`.
- Ledger integrity + replay verification utilities: `scripts/verify_mutation_ledger.py`, `tools/verify_replay_bundle.py`, `tools/verify_replay_attestation_bundle.py`, `scripts/validate_evidence_subsystem_determinism.py`.
