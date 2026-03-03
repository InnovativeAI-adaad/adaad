# ADAAD v1.1-GA Closure Tracker (Execution Control Surface)

This tracker converts the ADAAD-7 execution plan into auditable release controls. It is designed for governance sign-off and strict replay verification.

Primary execution plan: [`ADAAD_7_EXECUTION_PLAN.md`](../../ADAAD_7_EXECUTION_PLAN.md)
Release evidence matrix: [`docs/RELEASE_EVIDENCE_MATRIX.md`](../RELEASE_EVIDENCE_MATRIX.md)

## Phase 1 Control Gate (must be 100% complete)

| Control ID | Requirement | Acceptance criteria | Evidence artifact(s) | Status |
|---|---|---|---|---|
| GA-1.1 | Auth contract enforcement merged and verified | `GateCertifier.passed` path is token-backed (`token_ok`) and CI is green on release SHA | Merge commit SHA + CI run URL + auth contract diff | ⬜ |
| GA-1.2 | `verify_session()` call-site audit complete | No runtime/app usage outside approved test-only contexts | Call-site audit report + reviewer sign-off note | ⬜ |
| GA-1.3 | CI hardening merged | `secret_scan.yml` exists and branch protection blocks on secret scan | Workflow file + protection screenshot/export | ⬜ |
| GA-1.4 | Evidence matrix aligned to strict gate | Every strict gate claim maps to test + artifact path + owner | Updated matrix commit + governance approval | ⬜ |
| GA-1.5 | Deterministic governance gate refactor complete | Gate decisions are pure/replay-safe; nondeterministic sources removed | Module diff + deterministic replay proof | ⬜ |
| GA-1.6 | Mutation risk scorer suite expanded | 25+ deterministic cases passing in hermetic and CI environments | Test report + fixture index + pass logs | ⬜ |

## Supporting controls promoted from watch-items

| Control ID | Requirement | Acceptance criteria | Evidence artifact(s) | Status |
|---|---|---|---|---|
| GA-KR.1 | Key rotation enforcement audit | Rotation freshness policy and escalation are evidenced in release package | Audit memo + attestation output | ⬜ |
| GA-RP.1 | Replay-proof trust-root hardening scope | Third-party verifier trust-root plan is documented and approved | Scope document + schema impact note | ⬜ |
| GA-SB.1 | Sandbox timeout and backend fail-closed parity | Mutation execution fails closed deterministically across backends | Cross-backend test evidence + runbook note | ⬜ |

## Sign-off protocol

- Governance Lead signs only when all `GA-1.x` controls are complete.
- Security Lead signs when `GA-1.1`, `GA-1.2`, `GA-1.3`, and `GA-KR.1` are complete.
- Runtime/Codex sign-off required for `GA-1.5`, `GA-1.6`, and `GA-SB.1`.
- Release tag `v1.1-GA` is blocked until all mandatory controls are checked.

## Evidence packaging notes

- Prefer immutable artifact pointers (commit SHA + CI run ID + signed report hash).
- For replay evidence, include digest outputs from strict mode and bundle verifier output.
- For checklist portability, mirror final evidence links in release notes and audit memo.
