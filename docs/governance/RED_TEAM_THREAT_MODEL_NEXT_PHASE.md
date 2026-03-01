# Red-Team Threat Model — Next Phase Plan

## Objectives

1. Validate security boundary hardening for signature and token paths.
2. Probe determinism drift under governance/critical tiers.
3. Verify fail-closed behavior for certification and recovery transitions.

## Scenarios

1. **Legacy signature misuse**
   - Attempt `cryovant-static-*` payload signatures in prod-like mode.
   - Expected: rejection + critical audit event.

2. **Dev token leakage**
   - Attempt to use `CRYOVANT_DEV_TOKEN` while `ADAAD_ENV=prod`.
   - Expected: rejection.

3. **Determinism bypass**
   - Start governance/critical workflows with non-deterministic provider.
   - Expected: runtime rejection.

4. **Certification partial-check bypass**
   - Inject forbidden token primitives while keeping AST/import clean.
   - Expected: certification reject due to `token_ok=false`.

5. **Recovery churn**
   - Alternate violation/no-violation windows to verify de-escalation timing.
   - Expected: no premature de-escalation.

## Deliverables

- threat scenario test scripts
- expected/observed behavior matrix
- mitigation recommendations and residual-risk assessment
