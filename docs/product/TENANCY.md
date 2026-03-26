# ADAAD Tenancy Model

## Purpose

This document defines tenant/workspace isolation for API request handling and ledger-backed governance/audit data paths.

## Request lifecycle

Tenant scope is represented by:

- `tenant_id`
- `workspace_id`

Resolution contract:

1. API dependencies resolve scope from:
   - `X-Tenant-Id` and `X-Workspace-Id` headers, or
   - `tenant_id` and `workspace_id` query parameters.
2. Missing scope is rejected (`400 tenant_scope_required`).
3. Invalid scope format is rejected (`400 invalid_tenant_scope`).

## Ledger partitioning

Tenant-scoped ledger paths are partitioned under:

`security/ledger/tenants/<tenant_id>/<workspace_id>/...`

Current tenant-aware adapters include:

- `runtime/evolution/lineage_v2.py` (`LineageLedgerV2`)
- `security/ledger/journal.py` (`write_entry`, `read_entries`, `append_tx`)

These adapters include tenant metadata (`tenant_id`, `workspace_id`) in payloads for API-driven writes and filter reads to tenant scope.

## Governance and audit boundary checks

Tenant context is enforced on governance and audit endpoints that expose tenant-sensitive data, including:

- `/api/governance/parallel-gate/*`
- `/api/audit/epochs/{epoch_id}/lineage`
- `/api/audit/epochs/{epoch_id}/replay-proof`
- `/api/audit/bundles/{bundle_id}`

For evidence bundles/replay proofs that declare tenant metadata, mismatched tenant scope is rejected (`403 tenant_scope_mismatch`).

## Backward compatibility

Older global (non-partitioned) ledger files remain readable by non-tenant-aware paths. Tenant-enforced API routes are intentionally fail-closed and require explicit tenant context per request.
