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
