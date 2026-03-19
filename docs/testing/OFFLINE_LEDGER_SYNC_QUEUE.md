# Offline Ledger Sync Queue Runbook

## Design summary

`runtime/integrations/offline_ledger_sync.py` implements an append-only local operation log for offline ledger mutations.

- Every queued action is appended as an `enqueue` event with a stable `op_id` (`sha256` over deterministic operation seed including `device_id` + `op_seq`).
- Reconnect replay is idempotent: pending entries are replayed by `op_seq` order, and remote duplicate acknowledgements do not mutate state after the first successful apply.
- Conflicts are first-class queue states (`state=conflict`) with a user-visible payload (`reason`, `remote_snapshot`, `resolution_required`).
- Remote acknowledgements are fail-closed via integrity checks:
  - referenced `op_id` must exist locally
  - acknowledgement status must be one of `applied|duplicate|conflict`
  - if `op_digest` is provided, it must match local operation digest

## Operational limits

Queue limits are enforced via `QueueLimits`:

- `max_pending_operations`: **1,000**
- `ack_retention_entries`: **2,000**
- `min_retry_backoff_seconds`: **2**
- `max_retry_backoff_seconds`: **300**

Retry policy uses exponential backoff per attempted delivery (`2s, 4s, 8s, ...`) capped at 300 seconds.

## Recovery steps

### 1) Transport outage / reconnect replay

1. Recreate queue from log by constructing `OfflineLedgerSyncQueue(log_path=..., device_id=...)`.
2. Call `pending_replay(now_ts=...)`.
3. Deliver operations in returned order.
4. For each successful server apply, call `apply_remote_ack({... status="applied" ...})`.
5. For duplicate server delivery confirmation, call `apply_remote_ack({... status="duplicate" ...})`.

### 2) Conflict recovery

1. Surface `user_visible_conflicts()` in UI.
2. If user chooses server value, call `resolve_conflict_keep_remote(op_id=..., now_ts=...)`.
3. If user chooses local retry, call `resolve_conflict_retry_local(op_id=..., now_ts=...)`.
4. Resume replay loop with `pending_replay(...)`.

### 3) Integrity failure on acknowledgement

If `AckIntegrityError` is raised:

1. Stop applying incoming acknowledgements for the affected operation.
2. Fetch remote acknowledgement envelope again from source of truth.
3. Verify transport and payload canonicalization.
4. Retry `apply_remote_ack` only with validated `op_id/status/op_digest` fields.

Fail-closed behavior is intentional: unknown operations and digest mismatches are blocked instead of being silently accepted.
