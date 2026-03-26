# ADAAD Trust Center

This Trust Center provides a buyer-facing overview of ADAAD governance, security, replay integrity, and operational assurance artifacts.

## What ADAAD Is

ADAAD is a governed automation environment designed for deterministic, fail-closed mutation and governance workflows with auditable replay and evidence-linked controls.

## Core Assurance Themes

- **Fail-closed governance:** gate failures block progression by design.
- **Deterministic replay:** replay divergence is treated as a blocking integrity signal.
- **Append-only evidence:** governance and lineage records are designed for auditability.
- **Documented recovery:** formal runbooks describe incident triage and recovery sequencing.

## Buyer-Facing Compliance Documentation

- [Data Handling](docs/compliance/DATA_HANDLING.md)
- [Retention and Deletion](docs/compliance/RETENTION_AND_DELETION.md)
- [Access Control Matrix](docs/compliance/ACCESS_CONTROL_MATRIX.md)
- [Incident Response](docs/compliance/INCIDENT_RESPONSE.md)
- [Control Mapping](docs/compliance/CONTROL_MAPPING.md)

## Technical Evidence Sources

- [Security Invariants Matrix](docs/governance/SECURITY_INVARIANTS_MATRIX.md)
- [Fail-Closed Recovery Runbook](docs/governance/fail_closed_recovery_runbook.md)
- Validation scripts:
  - `scripts/verify_mutation_ledger.py`
  - `tools/verify_replay_bundle.py`
  - `tools/verify_replay_attestation_bundle.py`
  - `scripts/validate_release_evidence.py`

## Security & Governance Posture (Summary)

- Security and governance controls are backed by code-level validators and test gates.
- Merge-capable automation is conditioned on passing multi-tier gate checks and evidence completeness.
- Human sign-off is preserved for constitutionally protected amendment flows.

## Requesting Additional Assurance Artifacts

For deeper due-diligence requests (e.g., architecture contracts, CI gating policy, governance lifecycle events), see:

- `docs/CONSTITUTION.md`
- `docs/ARCHITECTURE_CONTRACT.md`
- `docs/governance/ci-gating.md`
- `docs/comms/claims_evidence_matrix.md`
