# Unified Identity Model

## Overview

ADAAD uses a unified auth validator (`security/unified_auth.py`) for API, runtime, and MCP surfaces. The model supports:

- OIDC JWT validation using issuer/audience + JWKS.
- Organization/workspace scoping claims (`org_id`, `workspace_id`).
- Service accounts backed by rotating credentials.
- RBAC action enforcement for `read`, `write`, `approve`, and `merge`.

## Token Types

### 1) OIDC bearer JWTs

Configured by environment:

- `ADAAD_AUTH_OIDC_ISSUER` — expected `iss` claim.
- `ADAAD_AUTH_OIDC_AUDIENCE` — comma-separated allowed audiences.
- JWKS source, in precedence order:
  1. `ADAAD_AUTH_JWKS_JSON`
  2. `ADAAD_AUTH_JWKS_PATH`
  3. `ADAAD_AUTH_JWKS_URL`

Validation rules:

- Signature must verify against JWKS.
- `exp` must exist and be unexpired.
- `nbf`, if present, must be valid for current time.
- `iss` and `aud` are enforced when configured.

### 2) Service accounts

Service account credentials are loaded from `ADAAD_SERVICE_ACCOUNT_CREDENTIALS`:

```json
{
  "svc-ci-2026-03": {
    "secret": "<rotated-secret>",
    "sub": "service-account:ci",
    "org_id": "org-main",
    "workspace_id": "ws-governance",
    "roles": ["write"],
    "actions": ["approve"],
    "expires_at": 1770000000
  }
}
```

Bearer format: `Authorization: Bearer <credential_id>.<secret>`.

Rotation pattern:

1. Add new credential ID alongside old credential.
2. Update callers to new ID/secret.
3. Remove old credential after rollout completes.

## RBAC action model

Built-in role expansion:

- `read` → `read`
- `write` → `read`, `write`
- `approve` → `read`, `write`, `approve`
- `merge` → `read`, `write`, `approve`, `merge`
- `admin` → all actions

Scopes (`audit:read`, `audit:write`) are also translated to action permissions to preserve compatibility with existing audit endpoints.

## Scoped tenancy claims

If an endpoint provides expected `org_id` and/or `workspace_id`, the validator rejects mismatches with:

- `org_scope_mismatch`
- `workspace_scope_mismatch`

## Normalized auth context

All consumers receive a shared context shape:

- `scheme`
- `subject`
- `org_id`
- `workspace_id`
- `roles`
- `actions`
- `scopes`
- `token_type`
- `redaction`

This keeps API and runtime behavior aligned and auditable.
