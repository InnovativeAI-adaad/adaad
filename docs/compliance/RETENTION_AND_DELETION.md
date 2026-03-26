# Retention and Deletion

## Purpose

This document defines retention expectations for ADAAD governance artifacts and deletion constraints for immutable evidence surfaces.

## Retention Model

| Data type | Retention expectation | Rationale |
| --- | --- | --- |
| Governance ledger events | Retain as append-only records | Required for replay/audit integrity and constitutional traceability |
| Replay manifests and attestation metadata | Retain with release/verification evidence | Required for deterministic replay proof and incident reconstruction |
| Validation outputs (CI/governance checks) | Retain according to release evidence requirements | Needed to demonstrate gate passage at change time |
| Operational metrics summaries | Retain per reporting lifecycle and governance needs | Supports trend analysis and post-incident reviews |
| Temporary local debugging artifacts | Remove when no longer needed | Minimize accidental persistence of transient data |

## Deletion Principles

1. **No destructive edits** to append-only governance/lineage chains.
2. **No silent purges** of evidence required for release/governance validation.
3. **Fail-closed behavior** if required integrity artifacts are missing or unreadable.
4. **Controlled archival** preferred over deletion for governed forensic artifacts.

## Practical Deletion Workflow (for non-governed transient data)

1. Confirm artifact is not referenced by release evidence or replay requirements.
2. Archive if needed for traceability.
3. Delete transient copy.
4. Re-run validation scripts to ensure no evidence contract regression.

## Verification Hooks

- Use `scripts/verify_mutation_ledger.py` for ledger integrity verification.
- Use replay bundle validators to ensure replay evidence remains intact:
  - `tools/verify_replay_bundle.py`
  - `tools/verify_replay_attestation_bundle.py`
- Use `scripts/validate_release_evidence.py --require-complete` to verify evidence completeness after lifecycle operations.

## Technical Evidence

- `docs/governance/SECURITY_INVARIANTS_MATRIX.md`
- `docs/governance/fail_closed_recovery_runbook.md`
- `scripts/verify_mutation_ledger.py`
- `tools/verify_replay_bundle.py`
- `tools/verify_replay_attestation_bundle.py`
- `scripts/validate_release_evidence.py`
