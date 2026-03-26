# ADAAD Buyer FAQ

## Security

### Q: How is this fail-closed rather than best-effort?
ADAAD governance patterns explicitly define fail-closed behavior for strict replay, runtime profile mismatches, and critical gate failures.

References:
- Strict replay invariants and fail-closed boot posture: [`docs/governance/STRICT_REPLAY_INVARIANTS.md`](../governance/STRICT_REPLAY_INVARIANTS.md)
- CI gate policy with mandatory baseline and escalated suites: [`docs/governance/ci-gating.md`](../governance/ci-gating.md)

### Q: How do we verify replay/attestation artifacts independently?
Use the deterministic offline verifier for replay attestation bundles.

Reference:
- [`tools/verify_replay_attestation_bundle.py`](../../tools/verify_replay_attestation_bundle.py)

---

## Governance

### Q: What makes governance auditable?
Governance lifecycle events are contract-defined and include required event types, payload fields, ordering semantics, digest linkage, and idempotency behavior.

Reference:
- PR lifecycle ledger event contract: [`docs/governance/ledger_event_contract.md`](../governance/ledger_event_contract.md)

### Q: How do we prove release claims are evidence-backed?
ADAAD uses an authoritative claims-evidence matrix and a validator that can fail readiness when required claims are incomplete.

References:
- Claims matrix: [`docs/comms/claims_evidence_matrix.md`](../comms/claims_evidence_matrix.md)
- Validator: [`scripts/validate_release_evidence.py`](../../scripts/validate_release_evidence.py)

---

## Vendor lock-in

### Q: Are control points opaque or proprietary-only?
Key controls are documented as repository artifacts (Markdown specs + Python scripts), which improves portability and reviewability.

Examples:
- Determinism contract: [`docs/governance/DETERMINISM_CONTRACT_SPEC.md`](../governance/DETERMINISM_CONTRACT_SPEC.md)
- Strict replay invariants: [`docs/governance/STRICT_REPLAY_INVARIANTS.md`](../governance/STRICT_REPLAY_INVARIANTS.md)
- CI gating policy: [`docs/governance/ci-gating.md`](../governance/ci-gating.md)

### Q: Can we run checks in our own CI pipeline?
Yes. Core controls are CLI/script addressable (schema validation, replay checks, evidence validation, deterministic linting).

Examples:
- Schema validation: [`scripts/validate_governance_schemas.py`](../../scripts/validate_governance_schemas.py)
- Architecture snapshot validation: [`scripts/validate_architecture_snapshot.py`](../../scripts/validate_architecture_snapshot.py)
- Determinism lint: [`tools/lint_determinism.py`](../../tools/lint_determinism.py)

---

## Deployment

### Q: Do we need a specific runtime posture for high-assurance operation?
Yes. Strict replay and governance-critical flows require deterministic provider posture and hermetic runtime constraints.

References:
- Determinism provider + replay mode contract: [`docs/governance/DETERMINISM_CONTRACT_SPEC.md`](../governance/DETERMINISM_CONTRACT_SPEC.md)
- Hermetic runtime profile/boot expectations: [`docs/governance/STRICT_REPLAY_INVARIANTS.md`](../governance/STRICT_REPLAY_INVARIANTS.md)

### Q: How does this fit an enterprise release process?
ADAAD maps governance controls to tiered CI gates, evidence completeness checks, and replay verification steps that can be embedded in release workflows.

References:
- CI gating map and required checks: [`docs/governance/ci-gating.md`](../governance/ci-gating.md)
- Critical artifact verification: [`scripts/verify_critical_artifacts.py`](../../scripts/verify_critical_artifacts.py)
