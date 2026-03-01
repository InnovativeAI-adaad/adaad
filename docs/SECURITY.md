# Security

## Security model summary

Cryovant is designed around a least-privilege, auditable security model:

- Private key material is stored locally under `security/keys/` with owner-only filesystem permissions.
- Secrets are never committed to source control or included in release artifacts.
- Security-relevant lineage events are append-only and recorded for post-incident review.
- Evidence used for governance and release communications is traceable to versioned repository artifacts.
- All security-relevant events must be replay-verifiable and ledger-anchored.

## Reporting process

If you identify a potential vulnerability, follow this coordinated disclosure process:

1. Do **not** open a public issue with exploit details.
2. Share a private report with maintainers including:
   - Impacted component(s)
   - Reproduction steps or proof-of-concept
   - Severity assessment and potential blast radius
3. Allow maintainers time to triage, remediate, and coordinate disclosure timing.
4. After remediation, publish an advisory summary with affected versions and mitigations.

## Key handling overview

Use the following baseline controls for local key material:

- [ ] Ensure `security/keys/` exists before first use (`mkdir -p security/keys`).
- [ ] Enforce strict directory permissions (`chmod 700 security/keys`).
- [ ] Keep private keys outside version control.
- [ ] Rotate or revoke keys immediately if compromise is suspected.

## Audit artifacts and evidence locations

Security and release evidence is expected in the following locations:

- Lineage ledger: `security/ledger/lineage.jsonl`
- Metrics mirror: `reports/metrics.jsonl`
- Claims/evidence matrix: `docs/comms/claims_evidence_matrix.md`
- Release evidence validation helper: `scripts/validate_release_evidence.py`

---

Related docs: [Repository README](../README.md) · [Documentation index](README.md)


## Weak-Point Hardening Policy

For safety-critical changes, treat the following as required controls:

- Normalize and validate mutation/orchestration inputs before policy decisions.
- Prefer deterministic transformations (stable ordering, explicit filtering).
- Apply fail-closed behavior when evidence or policy signals are absent.
- Favor minimal-allocation optimizations only when they preserve behavior and replay invariants.

Each hardening change should include a rationale and explicit invariants in code
or adjacent documentation to support auditability.


## Threat model weak-point matrix

| Weak point | Mitigation | Validation vector | Evidence path |
| --- | --- | --- | --- |
| Duplicate/whitespace task input noise | Deterministic task normalization before orchestration decisions | `tests/test_orchestration_contracts.py` task normalization tests | `reports/metrics.jsonl` + replay manifests |
| Malformed/non-string task entries | Ignore malformed labels and preserve fail-closed semantics | `tests/test_orchestration_contracts.py` non-string normalization test | Mutation orchestration status envelopes |
| Null/non-iterable task payloads | Fail closed early with `invalid_tasks_payload` and `safe_boot=True` | `tests/test_orchestration_contracts.py` invalid payload tests | Mutation orchestration status envelopes |
| License drift in release artifacts | MIT baseline + SPDX/license checks in scripts | `python scripts/validate_license_compliance.py` | Release evidence checklist + CI logs |


## Mutation input fuzzing policy

For orchestration input safety, fuzzing and edge-case tests must remain
deterministic and replay-compatible:

- Use seeded or static fixtures for malformed payload classes.
- Validate that malformed input cannot bypass fail-closed transition rules.
- Record expected envelope outcomes (`status`, `reason`, `safe_boot`/`run_cycle`) in tests.
- Verify blocked transitions use isolated payload dictionaries so post-call mutation cannot alter later decisions.

## Fail-closed enforcement points

Core fail-closed transition guards in orchestration are:

- `mutation_enabled=False` => `run_cycle=False`
- `fail_closed=True` => `run_cycle=False`
- `governance_gate_passed=False` => `run_cycle=False`
- `exit_after_boot=True` => mutation cycle skipped explicitly

These controls are verified in orchestration contract tests and should remain
stable across releases.
