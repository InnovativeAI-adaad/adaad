# Metering and Entitlements

## Overview

The API runtime now tracks billable usage in-memory and enforces entitlement checks in request middleware.

### Billable events and counters

Defined in `runtime/metrics.py`:

- `active_users`: unique `X-ADAAD-User-Id` values observed on successful API requests.
- `active_seats`: unique `X-ADAAD-Seat-Id` values observed on successful API requests.
- `mutation_epochs_executed`: successful `POST /api/nexus/agents/{agent_id}/mutate` requests.
- `replay_verifications`: successful `GET /api/audit/epochs/{epoch_id}/replay-proof` requests.
- `governance_approvals`: successful proposal submissions (`POST /api/mutations/proposals`, `POST /mutation/propose`).

Runtime helper APIs:

- `metrics.register_billable_usage(...)`
- `metrics.billable_usage_snapshot()`
- `metrics.reset_billable_usage()` (tests)

## Entitlement checks in API request path

`server.py` now includes a metering + entitlements middleware (`metering_entitlements_middleware`) that evaluates:

1. Plan (`X-ADAAD-Plan` header, or `ADAAD_DEFAULT_PLAN`, default: `enterprise`).
2. Enabled features (`X-ADAAD-Features` optional additive override).
3. Plan limits for users, seats, and billable event counters.

If a request exceeds limits or uses a disabled feature, API returns `402` with:

- `detail: entitlement_denied`
- `reason`: `feature_disabled`, `plan_limit_reached`, `active_users_limit`, or `active_seats_limit`
- `plan`, `event`, and current `usage` counters.

## Plan model

Built-in plans:

- `free`
- `pro`
- `enterprise`

Each plan has:

- feature gates (`_PLAN_FEATURES`)
- numeric limits (`_PLAN_LIMITS`)

## Admin usage endpoints

Protected by audit scope (`audit:read`):

- `GET /api/admin/usage`
  - Returns usage snapshot, configured default plan, and all plan limits/features.
- `GET /api/admin/usage/plan/{plan_id}`
  - Returns plan-specific limits/features plus current usage counters.

## Headers

Optional request headers:

- `X-ADAAD-Plan: <free|pro|enterprise>`
- `X-ADAAD-Features: feature_a,feature_b`
- `X-ADAAD-User-Id: user-123`
- `X-ADAAD-Seat-Id: seat-456`

`Authorization: Bearer <token>` with `audit:read` scope is required for admin usage endpoints.
