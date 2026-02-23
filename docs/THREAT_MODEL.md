# Threat Model

This document defines the core threat assumptions for ADAAD's governance-first mutation runtime.

## Scope

Covered surfaces:
- Governance policy and constitution enforcement
- Replay and deterministic verification contracts
- Mutation lineage and evidence artifacts
- Runtime execution boundaries
- Build/release supply chain inputs

## Primary threats

- **Governance bypass attempts:** executing or merging mutations without required governance gates.
- **Replay poisoning:** tampering with replay inputs or attestation bundles to force false pass.
- **Mutation divergence injection:** introducing non-deterministic or unauthorized state transitions.
- **Constitution tampering:** modifying governance constraints outside approved controls.
- **Runtime state manipulation:** changing execution environment to alter policy/replay outcomes.
- **Supply chain compromise:** dependency or artifact compromise impacting deterministic trust.

## Mitigations

- Fail-closed policy gating for mutation execution.
- Replay contract verification with hash-bound artifacts.
- Lineage and evidence integrity validation.
- Controlled runtime profile and deterministic boundary checks.
- Constitution/policy artifact validation and governance audit trail.
- Release evidence checklist and CI governance gate enforcement.

## Residual risks and assumptions

- Determinism guarantees are bounded by declared replay contract surfaces.
- Organization-level branch protections and CI controls must remain enabled.
- External trust anchors and third-party signing ecosystems require operational hardening discipline.
