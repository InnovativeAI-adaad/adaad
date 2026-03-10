# SPDX-License-Identifier: Apache-2.0
# ADAAD Phase 25 Upgrade Plan — Pressure Adjustment Audit Ledger

**Issued by:** ArchitectAgent
**Version:** 1.0.0
**Date:** 2026-03-09
**Target version:** v4.10.0
**Baseline:** v4.9.0 · PR-24-REL · 2,915+ tests passing
**Authority chain:** `CONSTITUTION.md > ARCHITECTURE_CONTRACT.md > AGENTS.md`

---

## 1. Problem Statement

Phase 24 established `HealthPressureAdaptor` as an advisory surface with
`advisory_only: True` and a deterministic `adjustment_digest`. However, every
`PressureAdjustment` is ephemeral — computed on demand, never persisted. When
`GET /governance/review-pressure` is called twice in succession, both responses
are indistinguishable without external logging.

This is an auditability gap. The Phase 24 value statement commits to an
"auditable, deterministic advisory surface." Without a verifiable history of
what recommendations were made, when, and at what health score, the surface is
deterministic but not auditable in the governance-grade sense.

Phase 25 closes this gap with the same architectural pattern as Phase 21
(`FileTelemetrySink` / `TelemetryLedgerReader`):

1. `PressureAuditLedger` — SHA-256 hash-chained append-only JSONL ledger
   recording every `PressureAdjustment` emission. Structurally identical
   chain model to `FileTelemetrySink`.
2. `PressureAuditReader` — read-only query interface over the ledger:
   history by pressure tier, pressure tier frequency series, chain verification.
3. Wire `PressureAuditLedger` into `GET /governance/review-pressure` — every
   request that produces an adjustment appends it to the ledger (when a ledger
   path is configured via env or kwarg).
4. `GET /governance/pressure-history` — bearer-auth-gated read-only endpoint
   returning paginated ledger records and tier frequency summary.

**What Phase 25 does NOT do:**

- Does not modify `HealthPressureAdaptor`, `PressureAdjustment`, or any
  existing endpoint contracts.
- Does not change `GovernanceGate`, constitutional rules, or any mutation path.
- Does not change `FileTelemetrySink` or `TelemetryLedgerReader`.
- Ledger writes in `GET /governance/review-pressure` are best-effort:
  failures are logged as WARNING and never propagated (Phase 21 isolation contract).

---

## 2. Design Invariants

| Invariant | Class | Enforcement |
|---|---|---|
| Ledger is append-only | Architecture | `PressureAuditLedger` never overwrites; `verify_chain()` detects tampering |
| Chain integrity is fail-closed | Architecture | `chain_verify_on_open=True` raises `PressureAuditChainError` at construction if broken |
| Emit failure never propagates | Architecture | `PressureAuditLedger.emit()` catches all I/O failures; logs WARNING only |
| Reader is read-only | Authority | `PressureAuditReader` has no write path |
| Deterministic replay | Determinism | Same ledger file → same query results; same records → same chain hashes |
| GENESIS_PREV_HASH matches pattern | Determinism | `"sha256:" + "0" * 64` — same sentinel as `FileTelemetrySink` |
| Ledger inactive by default | Stability | No env var or kwarg → no file written; existing behaviour unchanged |

---

## 3. PR Sequence

| PR | Title | CI tier | Deps | Tests |
|---|---|---|---|---|
| PR-25-PLAN | This document | docs | Phase 24 ✅ | — |
| PR-25-01 | `PressureAuditLedger` + `PressureAuditReader` | critical | PR-25-PLAN | ≥ 32 new |
| PR-25-02 | Wire ledger into endpoint + `GET /governance/pressure-history` | standard | PR-25-01 | ≥ 18 new |
| PR-25-REL | v4.10.0: VERSION, CHANGELOG, agent state | docs | PR-25-02 | — |

Total new tests target: **≥ 50**

---

## 4. PR-25-01 Specification: `PressureAuditLedger` + `PressureAuditReader`

### Change surfaces

- `runtime/governance/pressure_audit_ledger.py` — **new**
- `runtime/governance/__init__.py` — add exports: `PressureAuditLedger`,
  `PressureAuditReader`, `PressureAuditChainError`, `PRESSURE_LEDGER_GENESIS_PREV_HASH`,
  `PRESSURE_LEDGER_VERSION`
- `tests/test_pressure_audit_ledger.py` — **new** (≥ 32 tests)

### Constants

```python
PRESSURE_LEDGER_GENESIS_PREV_HASH: str = "sha256:" + "0" * 64
PRESSURE_LEDGER_VERSION: str = "25.0"
```

### `PressureAuditChainError`

Raised when chain verification detects a hash mismatch or sequence break.
Carries `sequence` (int) and `detail` (str).

### `PressureAuditLedger` contract

```
PressureAuditLedger(
    path: Path | str,
    *,
    chain_verify_on_open: bool = True,
)
```

- On construction: if `path` exists and `chain_verify_on_open=True`, verifies
  the existing chain; raises `PressureAuditChainError` on any violation.
- Each record written is a JSONL line containing:
  ```json
  {
    "ledger_version": "25.0",
    "sequence": 0,
    "prev_hash": "sha256:000...0",
    "record_hash": "sha256:<hash-of-this-record-without-record_hash>",
    "timestamp_iso": "...",
    "health_score": 0.72,
    "health_band": "amber",
    "pressure_tier": "elevated",
    "adjusted_tiers": ["critical", "standard"],
    "adjustment_digest": "sha256:...",
    "adaptor_version": "24.0"
  }
  ```
- `record_hash` is SHA-256 of the canonical JSON of all fields except
  `record_hash` itself (same pattern as `FileTelemetrySink`).

**`emit(adjustment: PressureAdjustment) -> None`:**
- Appends one record to the JSONL file; updates `_prev_hash`; increments sequence.
- Catches ALL I/O and serialisation failures; logs WARNING; never propagates.
- Thread-safety: single writer assumed (same as `FileTelemetrySink`).

**`verify_chain() -> bool`:**
- Reads all records; validates sequence monotonicity and hash linkage.
- Raises `PressureAuditChainError` on any violation.
- Returns `True` when chain is intact.
- O(n) streaming; does not load all records into memory simultaneously.

### `PressureAuditReader` contract

```
PressureAuditReader(path: Path | str)
```

**`history(*, pressure_tier: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]`:**
- Returns records newest-first (reverse arrival order).
- Filters by `pressure_tier` when provided.
- `limit` max 500; raises `ValueError` if exceeded.
- `offset` supports pagination.

**`tier_frequency() -> dict[str, int]`:**
- Returns `{pressure_tier: count}` across all ledger records.
- Keys: `"none"`, `"elevated"`, `"critical"` (only those that appear).

**`tier_frequency_series(*, window: int = 10) -> dict[str, list[float]]`:**
- Same rolling-window pattern as `StrategyAnalyticsEngine.activation_frequency()`.
- Returns `{pressure_tier: [freq_window0, freq_window1, ...]}`.

**`verify_chain() -> bool`:**
- Delegates to `PressureAuditLedger._verify_existing_chain()` logic.

### Test requirements (≥ 32 tests)

- `PressureAuditLedger` construction on new path creates file
- `emit()` writes a parseable JSONL record
- `emit()` increments sequence monotonically
- `emit()` links `prev_hash` to previous `record_hash`
- `emit()` on I/O failure logs warning and does not raise
- `verify_chain()` returns `True` on intact chain
- `verify_chain()` raises `PressureAuditChainError` on tampered record
- `verify_chain()` raises on sequence gap
- `chain_verify_on_open=True` raises on corrupted existing ledger
- `chain_verify_on_open=False` skips verification
- `GENESIS_PREV_HASH` matches `"sha256:" + "0" * 64`
- First record `prev_hash` equals `GENESIS_PREV_HASH`
- `PressureAuditReader.history()` returns newest-first
- `history(pressure_tier="elevated")` filters correctly
- `history(limit=5)` returns at most 5 records
- `history(offset=2)` skips first 2 records
- `history(limit=501)` raises `ValueError`
- `tier_frequency()` counts correct per-tier totals
- `tier_frequency()` on empty ledger returns empty dict
- `tier_frequency_series(window=5)` returns correct rolling frequencies
- `tier_frequency_series()` absent tiers have `0.0` in their window slots
- `verify_chain()` via reader returns `True` on intact chain
- Round-trip: emit 10 adjustments → reader returns 10 records
- `ledger_version` field in every record equals `"25.0"`
- `adaptor_version` field in every record equals `"24.0"`
- `adjustment_digest` field preserved from `PressureAdjustment`
- `health_band` field preserved
- `pressure_tier` field preserved
- Replay determinism: two ledgers with same adjustments produce identical chain hashes
- `PressureAuditChainError` carries `sequence` and `detail` attributes
- Empty ledger: `verify_chain()` returns `True`
- `PressureAuditReader` on non-existent path raises `FileNotFoundError`

**CI tier: critical**

---

## 5. PR-25-02 Specification: Endpoint Wiring + History Endpoint

### Change surfaces

- `server.py` — wire `PressureAuditLedger` into `GET /governance/review-pressure`;
  add `GET /governance/pressure-history`
- `tests/test_pressure_history_endpoint.py` — **new** (≥ 12 tests)
- `tests/test_review_pressure_ledger_wiring.py` — **new** (≥ 6 tests)
- `docs/comms/claims_evidence_matrix.md` — new evidence rows

### `GET /governance/review-pressure` wiring

Extend existing endpoint: after computing `PressureAdjustment`, if
`ADAAD_PRESSURE_LEDGER_PATH` env var is set and non-empty, emit to
`PressureAuditLedger`. Failure is silent (WARNING log only).

Response gains two new fields in `data`:
```json
{
  ...existing fields...,
  "ledger_active": true,
  "ledger_sequence": 42
}
```
`ledger_active: false` and `ledger_sequence: null` when no ledger configured.

### `GET /governance/pressure-history`

- **Auth:** `audit:read` scope
- **Query params:** `pressure_tier` (opt), `limit` (1–500, default 100), `offset` (default 0)
- **Response:**
  ```json
  {
    "schema_version": "1.0",
    "authn": { ... },
    "data": {
      "records": [...],
      "total_queried": 42,
      "tier_frequency": {"none": 10, "elevated": 25, "critical": 7},
      "ledger_active": true,
      "ledger_path": "/path/to/ledger.jsonl"
    }
  }
  ```
- When no ledger configured: `ledger_active: false`, `records: []`, `tier_frequency: {}`.
- **422** on `limit > 500`.

### Test requirements

`tests/test_pressure_history_endpoint.py` (≥ 12 tests):
- Returns 200 with schema
- Without auth returns 401
- `ledger_active: false` when no env var set
- `ledger_active: true` when env var set and ledger has records
- `records` is a list
- `tier_frequency` is a dict
- `total_queried` is int ≥ 0
- `pressure_tier` filter returns only matching records
- `limit=501` returns 422
- `ledger_path` is str or null
- Records contain `pressure_tier`, `health_band`, `adjustment_digest`
- `schema_version: "1.0"`

`tests/test_review_pressure_ledger_wiring.py` (≥ 6 tests):
- `GET /governance/review-pressure` returns `ledger_active: false` without env
- `GET /governance/review-pressure` returns `ledger_active: true` with env set
- `ledger_sequence` is int when active
- `ledger_sequence` is null when inactive
- Calling endpoint twice increments `ledger_sequence`
- Ledger file exists after first call with env var set

**CI tier: standard**

---

## 6. Commit Message Templates

### PR-25-01
```
feat(governance): PressureAuditLedger + PressureAuditReader — SHA-256 hash-chained pressure audit trail [32 tests]

PR-ID: PR-25-01
CI tier: critical
Replay proof: sha256:<strict-replay-artifact-hash>
```

### PR-25-02
```
feat(governance): GET /governance/pressure-history + ledger wiring into review-pressure [18 tests]

PR-ID: PR-25-02
CI tier: standard
Replay proof: not-required
```

### PR-25-REL
```
chore(release): Phase 25 milestone closure · v4.10.0

PR-ID: PR-25-REL
CI tier: docs
Replay proof: not-required
```

---

## 7. Evidence Gates

| Milestone | Gate |
|---|---|
| PR-25-01 merged | ≥ 32 new tests pass; chain tamper-detection test passes; replay SHA committed |
| PR-25-02 merged | ≥ 18 new tests pass; existing review-pressure tests unaffected |
| v4.10.0 tagged | ≥ 2,965 tests (2,915 baseline + 50 new); evidence rows Complete |

---

## 8. Value Statement

Phase 24 produced advisory `PressureAdjustment` records. Phase 25 makes them
permanent. Every recommendation is now immutably chained — hash-linked to its
predecessor, tamper-evident, and queryable. The `tier_frequency` and
`tier_frequency_series` surfaces answer the governance question: "Is the system
consistently recommending elevated pressure? Is it oscillating? Is it trending
toward critical?" These are the retrospective signals that allow human reviewers
to assess whether the advisory system is calibrated correctly — and to propose
constitutional amendments to its thresholds if it is not. Phase 25 completes the
governance advisory arc: emit → persist → verify → query.
