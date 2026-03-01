# Security Invariants Matrix

This matrix defines mandatory enforcement invariants for governance-critical execution.

## Mode / Tier Invariants

| Replay mode | Recovery tier | Deterministic provider | Network surface | Mutation execution |
| --- | --- | --- | --- | --- |
| `off` | `none` | Optional | Policy-configurable | Allowed when gates pass |
| `off` | `advisory` | Recommended | Policy-configurable | Allowed when gates pass |
| `off` | `conservative` | Recommended | Policy-configurable | Reduced mutation rate |
| `off` | `governance` | **Required** | Denied by recovery policy | Fail-closed if governance checks fail |
| `off` | `critical` | **Required** | Denied by recovery policy | Fail-closed / blocked |
| `strict` | any | **Required** | Denied by strict profile | Fail-closed on divergence |

Backward-compatibility alias: `audit` tier is accepted for deterministic-provider enforcement.

## Authentication / Signature Invariants

1. Governance bearer tokens must be cryptographically verifiable (`cryovant-gov-v1`).
2. `CRYOVANT_DEV_TOKEN` override is accepted only in explicit dev mode (`ADAAD_ENV=dev` and `CRYOVANT_DEV_MODE` enabled).
3. Payload-bound `cryovant-static-*` signatures are accepted only in explicit dev mode.
4. Governance certifier decisions are binding on `import_ok`, `token_ok`, `ast_ok`, and `auth_ok`.

## Audit Visibility Invariants

- Rejected legacy static signature attempts emit `cryovant_legacy_static_payload_signature_rejected`.
- Accepted dev-only static signature attempts emit `cryovant_legacy_static_payload_signature_accepted`.
- Certifier violations include explicit reason-codes for token and code-scan failures.
