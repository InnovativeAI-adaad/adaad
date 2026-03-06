# Architecture Summary

![Status: Stable](https://img.shields.io/badge/Status-Stable-2ea043)
![Governance: Fail-Closed](https://img.shields.io/badge/Governance-Fail--Closed-critical)

> One-page, deterministic architecture orientation for governance-first ADAAD operation.

**Last reviewed:** 2026-03-06 · v2.0.0

A one-page overview of ADAAD's governance-first architecture for autonomous code evolution.

## Components

- **Trust Layer (Cryovant):** environment trust and ancestry validation.
- **Governance Layer (Constitution + policy engine):** mutation legality and gate evaluation.
- **Execution Layer (Dream / Beast / Architect):** proposal, scoring, and controlled execution.
- **Evidence Layer:** lineage, replay attestations, and release evidence bundles.
- **AI Mutation Layer (v2.0.0):** `AIMutationProposer` (Claude API, 3 personas), `EvolutionLoop` (5-phase orchestrator), `WeightAdaptor` (momentum descent), `FitnessLandscape` (plateau detection), `PopulationManager` (BLX-alpha GA).
- **Canonical spec:** `docs/governance/ARCHITECT_SPEC_v3.0.0.md`
- **Historical baseline (superseded):** `docs/governance/ARCHITECT_SPEC_v2.0.0.md`

## Boundaries

- Mutation execution is gated by governance decisions.
- Replay contract validates deterministic inputs/outputs before execution.
- Evidence artifacts are append-only and integrity-checked.

## Trust Zones

- **Policy zone:** constitution, governance rules, lock artifacts.
- **Execution zone:** mutation simulation/execution under runtime constraints.
- **Evidence zone:** attestation bundles, lineage chain, release proof artifacts.

## Mutation lifecycle

Propose → Simulate → Replay Verify → Policy Gate → Execute → Evidence Attach → Archive.

## Evidence flow

- Mutation proposal generates governed intent artifacts.
- Policy engine emits decisions and required constraints.
- Replay verifies deterministic conformance.
- Execution emits lineage/evidence for auditing.
- Release process validates evidence matrix before state transition approval.
