# Control Mapping

## Purpose

This document maps ADAAD's existing invariants, gate stack controls, and verification scripts to common control families used in buyer security/compliance reviews.

## Control Family Mapping

| Control family | ADAAD implementation signal | Primary evidence |
| --- | --- | --- |
| Access Control (AC) | Token/signature verification invariants, strict-env dev override restrictions, governance gate authority boundary | `docs/governance/SECURITY_INVARIANTS_MATRIX.md`, `security/cryovant.py` |
| Audit & Accountability (AU) | Append-only governance/lineage evidence, reason-coded fail-closed outcomes, metrics/events | `docs/governance/fail_closed_recovery_runbook.md`, ledger/replay verification scripts |
| Configuration Management (CM) | Determinism/import boundary linting, architecture snapshot checks, schema validation | `tools/lint_determinism.py`, `tools/lint_import_paths.py`, `scripts/validate_architecture_snapshot.py`, `scripts/validate_governance_schemas.py` |
| Incident Response (IR) | Fail-closed recovery triage flow, strict replay re-validation, post-recovery checklist | `docs/governance/fail_closed_recovery_runbook.md`, replay validators |
| Integrity / System & Info Integrity (SI) | Replay divergence fail-closed behavior, hash-chain integrity checks, strict replay invariants | `docs/governance/SECURITY_INVARIANTS_MATRIX.md`, `scripts/verify_mutation_ledger.py`, `tools/verify_replay_bundle.py` |
| Risk & Governance (GV/RM) | Tiered gate taxonomy, evidence completeness requirements, merge attestation requirement | `AGENTS.md`, `scripts/validate_release_evidence.py`, PR lifecycle schemas/scripts |
| Contingency / Resilience (CP) | Recovery runbook for divergence/integrity incidents, documented rehearsal narratives | `docs/governance/fail_closed_recovery_runbook.md` |

## Invariants to Control Families

| Invariant / gate concept | Control family linkage |
| --- | --- |
| Fail-closed replay divergence enforcement | SI, IR |
| Strict environment signing key requirement | AC, SI |
| Trusted federation key registry enforcement | AC, SI |
| Append-only ledger integrity checks | AU, SI |
| Tiered gate stack with merge-blocking semantics | GV/RM, SI |
| Human sign-off invariants for amendment paths | GV/RM, AC |

## Validation Script Mapping

| Script/tool | Primary control intent |
| --- | --- |
| `scripts/validate_governance_schemas.py` | CM — schema integrity and policy structure correctness |
| `scripts/validate_architecture_snapshot.py` | CM — architecture drift detection |
| `tools/lint_determinism.py` | SI/CM — deterministic execution guarantees |
| `tools/lint_import_paths.py` | CM/AC — boundary enforcement |
| `scripts/verify_mutation_ledger.py` | AU/SI — append-only integrity verification |
| `tools/verify_replay_bundle.py` | SI/IR — replay evidence integrity |
| `tools/verify_replay_attestation_bundle.py` | SI/AU — attestation bundle verification |
| `scripts/validate_release_evidence.py --require-complete` | GV/RM, AU — evidence completeness gate |

## Notes for Buyer Reviews

- This mapping intentionally references currently enforced controls rather than future roadmap commitments.
- Control families may map to multiple ADAAD artifacts; reviewers should validate both docs and executable validators.
