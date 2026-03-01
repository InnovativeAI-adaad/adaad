# Governance State Machine Normalization

## Recovery Tier Transition Rules

`TierManager.auto_evaluate_and_apply(...)` normalization:

1. Escalation applies immediately when evaluated tier severity is higher than current.
2. De-escalation applies only when evaluated tier severity is lower **and** recovery window has elapsed.
3. No-op transitions are not recorded.

This prevents inert de-escalation branches and keeps transition history semantically meaningful.

## Certification Decision Normalization

`GateCertifier` pass criteria are conjunctive:

- `import_ok`
- `token_ok`
- `ast_ok`
- `auth_ok`

Any single gate failure rejects certification.

## Auth Normalization

Governance-critical paths use production-capable token verification (`verify_governance_token`) instead of deprecated session helper semantics.
