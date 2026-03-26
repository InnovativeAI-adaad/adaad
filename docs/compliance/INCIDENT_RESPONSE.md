# Incident Response

## Purpose

This runbook-style policy summarizes incident response steps for fail-closed governance incidents, replay divergence, and ledger integrity alarms.

## Incident Categories

| Category | Typical indicator | Immediate posture |
| --- | --- | --- |
| Replay divergence | Strict replay mismatch / divergence digest | Fail-closed, pause mutation execution |
| Ledger integrity alert | Hash-chain verification failure | Treat as potential tampering until disproven |
| Governance gate regression | Tier 0/1/2/3/M gate failure | Block progression, capture evidence, remediate |
| Auth/signature violation | Token/signature verification failure | Deny request, record reason code, investigate |

## Standard Response Workflow

1. **Detect and classify** the incident using governance decision records and validator outputs.
2. **Contain impact** by pausing mutation execution and preserving current evidence state.
3. **Verify integrity** via ledger/replay validation scripts.
4. **Perform human review** for divergent/tampered artifacts.
5. **Recover** only through approved governance controls.
6. **Re-validate** with strict replay and evidence completeness checks before resuming normal operation.
7. **Document closure** in incident notes/runbooks with objective artifact references.

## Minimum Validation Commands During Triage

```bash
python scripts/verify_mutation_ledger.py
python tools/verify_replay_bundle.py
python tools/verify_replay_attestation_bundle.py
python scripts/validate_release_evidence.py --require-complete
```

## Escalation Triggers

Escalate immediately when any of the following occurs:

- Ledger integrity check fails.
- Strict replay remains divergent after first remediation attempt.
- Required governance evidence is missing/incomplete.
- Constitutional invariants appear violated.

## Authoritative References

- Operational recovery sequence: `docs/governance/fail_closed_recovery_runbook.md`.
- Security and fail-closed invariant definitions: `docs/governance/SECURITY_INVARIANTS_MATRIX.md`.
- Replay and ledger validation toolchain:
  - `scripts/verify_mutation_ledger.py`
  - `tools/verify_replay_bundle.py`
  - `tools/verify_replay_attestation_bundle.py`
