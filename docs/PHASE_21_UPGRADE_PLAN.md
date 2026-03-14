# SPDX-License-Identifier: Apache-2.0
# ADAAD Phase 21 Upgrade Plan — Telemetry Ledger & Governed Observability

**Issued by:** ArchitectAgent  
**Version:** 1.0.0  
**Date:** 2026-03-09  
**Target version:** v4.6.0  
**Baseline:** v4.5.0 · PR-20-REL · 2,714+ tests passing  
**Authority chain:** `CONSTITUTION.md > ARCHITECTURE_CONTRACT.md > AGENTS.md`

---

## 1. Problem Statement

Phases 16–19 built the full intelligence pipeline:

- **Phase 16** — 6-strategy taxonomy (`STRATEGY_TAXONOMY`)
- **Phase 17** — `IntelligenceRouter` + `RoutedDecisionTelemetry`
- **Phase 18** — `CritiqueSignalBuffer` feedback loop
- **Phase 19** — `AutonomyLoop` wired to `IntelligenceRouter`

Every intelligence routing decision is emitted via `RoutedDecisionTelemetry`. The
current default sink is `InMemoryTelemetrySink` — append-only but ephemeral. On
process restart, all routing history is lost.

**Consequence:** The governance system cannot answer questions that require decision
history — "which strategy has the highest win rate over the last 100 epochs?",
"when did `structural_refactor` last trigger?", "what is the trend in `composite_score`
for `exploratory_probe` decisions?" These questions are answered by the intelligence
and autonomy surface, but only if a persistent, queryable, chain-verified record exists.

**Phase 21** closes this gap by adding:

1. `FileTelemetrySink` — append-only JSONL sink with sha256 hash chaining
   (parallel pattern to `mutation_ledger.py` and `reviewer_reputation_ledger.py`)
2. `TelemetryLedgerReader` — deterministic query interface (by strategy, by epoch, by outcome)
3. `AutonomyLoop` default sink upgrade — wire `FileTelemetrySink` when a ledger path
   is configured; retain `InMemoryTelemetrySink` as the test-safe fallback
4. `GET /telemetry/decisions` Aponi endpoint — paginated, bearer-auth-gated read surface

**What Phase 21 does NOT do:**

- Does not change any existing public API exports (Phase 20 is already the stability baseline)
- Does not modify `InMemoryTelemetrySink` (remains unchanged, tests continue to use it)
- Does not add any new constitutional rules
- Does not grant any new mutation approval authority
- Does not change `GovernanceGate` behavior

---

## 2. Design Invariants

| Invariant | Class | Enforcement |
|---|---|---|
| Telemetry ledger is append-only | Evidence | `FileTelemetrySink` never overwrites; atomic line append only |
| Chain integrity is fail-closed | Determinism | `TelemetryLedgerReader.verify_chain()` halts on any hash mismatch |
| Emission failure never degrades routing | Architecture | Same isolation contract as Phase 17; `FileTelemetrySink.emit()` catches all exceptions |
| `InMemoryTelemetrySink` is unchanged | Stability | No modifications to `routed_decision_telemetry.py` except adding the new sink class |
| Ledger is read-only from Aponi | Authority | `GET /telemetry/decisions` is read-only; no write path exposed through server.py |
| `GovernanceGate` retains sole mutation authority | Constitutional | Telemetry is observability only; no routing decision can approve or block a mutation |
| Deterministic query output | Determinism | Same ledger state + same query parameters → identical result every time |

---

## 3. PR Sequence

| PR | Title | CI tier | Deps | Tests |
|---|---|---|---|---|
| PR-21-PLAN | This document | docs | Phase 20 ✅ | — |
| PR-21-01 | `FileTelemetrySink` + `TelemetryLedgerReader` | critical | PR-21-PLAN | ≥ 28 new |
| PR-21-02 | `AutonomyLoop` default sink upgrade + Aponi endpoint | standard | PR-21-01 | ≥ 18 new |
| PR-21-REL | v4.6.0: VERSION, CHANGELOG, agent state, README | docs | PR-21-02 | — |

Total new tests target: **≥ 46**

---

## 4. PR-21-01 Specification: `FileTelemetrySink` + `TelemetryLedgerReader`

### Purpose

Persistent, chain-verified append-only telemetry sink that follows the established
ledger pattern (`mutation_ledger.py`, `reviewer_reputation_ledger.py`).

### Change surfaces

- `runtime/intelligence/file_telemetry_sink.py` — **new**
- `runtime/intelligence/__init__.py` — add `FileTelemetrySink`, `TelemetryLedgerReader`
  to exports and `__all__`
- `schemas/telemetry_decision_record.v1.json` — **new**
- `tests/test_file_telemetry_sink.py` — **new** (≥ 28 tests)

### `FileTelemetrySink` contract

```
FileTelemetrySink(path: Path | str, *, chain_verify_on_open: bool = True)
```

**Construction:**
- `path` is the JSONL ledger file path. Created if absent (including parent dirs).
- If `chain_verify_on_open=True` and the file exists, run `verify_chain()` before
  accepting any new emit. If verification fails → raise `TelemetryChainError` at
  construction. Caller must not proceed with a broken chain.
- `chain_verify_on_open=False` is only valid in test contexts where the caller
  explicitly opts out. Production code must use the default.

**`emit(payload: dict[str, Any]) -> None`:**
- Build a `TelemetryRecord`: `{sequence: int, prev_hash: str, record_hash: str, payload: dict}`
- `sequence` is the next integer (0-indexed, monotonically increasing).
- `prev_hash` is the `record_hash` of the previous record, or `GENESIS_PREV_HASH` for
  sequence 0. `GENESIS_PREV_HASH = "sha256:" + ("0" * 64)` (matches `mutation_ledger.py`).
- `record_hash = sha256(json.dumps({sequence, prev_hash, payload}, sort_keys=True))`.
- Serialize the full record as a single JSON line and append atomically.
- Emit failure (file I/O, serialization) is caught, logged at WARNING, and never
  propagated to the caller (matches Phase 17 isolation contract).

**`verify_chain() -> bool`:**
- Streams the JSONL file line by line (O(n) memory, not O(n²)).
- For each record: recompute `record_hash` from stored `{sequence, prev_hash, payload}`.
- Verify: computed hash == stored `record_hash`.
- Verify: stored `prev_hash` == previous record's `record_hash` (or GENESIS for seq=0).
- Verify: `sequence` is monotonically increasing with no gaps.
- Returns `True` on success. Raises `TelemetryChainError` with sequence number and
  computed/stored hash mismatch detail on any violation. Never returns `False` silently.

**`entries() -> tuple[dict[str, Any], ...]`:**
- Returns all payload dicts in append order (sequence ascending). For memory-bounded
  use only; callers with large ledgers should use `TelemetryLedgerReader`.

**`__len__() -> int`:**
- Returns number of records in the ledger.

### `TelemetryLedgerReader` contract

```
TelemetryLedgerReader(path: Path | str)
```

Read-only. Does not write to the ledger file. Does not acquire write locks.

**`query(*, strategy_id: str | None = None, outcome: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]`:**
- Streams ledger JSONL, filters by `strategy_id` and/or `outcome` if provided.
- Returns matched payload dicts, newest-first (reverse sequence order).
- `limit` max is 500. `offset` enables pagination.
- Deterministic: same ledger + same params → identical result.

**`win_rate_by_strategy() -> dict[str, float]`:**
- For each `strategy_id`, compute `approved_count / total_count` where
  `outcome == "approved"` is the win condition.
- Returns `{}` on empty ledger. Returns `0.0` for strategies with zero approvals.
- Deterministic.

**`strategy_summary() -> dict[str, dict[str, int]]`:**
- Returns `{strategy_id: {total, approved, rejected, held}}` counts.
- `held` = outcome not in `{approved, rejected}`.

**`verify_chain() -> bool`:**
- Delegates to the same chain-verification algorithm as `FileTelemetrySink.verify_chain()`.
- Read-only — does not mutate the file.

### Schema: `schemas/telemetry_decision_record.v1.json`

Required fields:
- `sequence` — integer, monotonically increasing
- `prev_hash` — `"sha256:[64 hex chars]"` or GENESIS value
- `record_hash` — `"sha256:[64 hex chars]"`
- `payload` — the raw `routed_intelligence_decision.v1` payload dict

### Test requirements (≥ 28 tests in `tests/test_file_telemetry_sink.py`)

Must cover:
- `FileTelemetrySink.emit()` — single record, chain integrity verified after emit
- `FileTelemetrySink.emit()` — 10 records, chain integrity verified after all
- `FileTelemetrySink` — creation of parent directories if absent
- `FileTelemetrySink` — emit failure (mock I/O error) does not raise; logs WARNING
- `FileTelemetrySink.verify_chain()` — valid chain returns `True`
- `FileTelemetrySink.verify_chain()` — tampered `record_hash` raises `TelemetryChainError`
- `FileTelemetrySink.verify_chain()` — tampered `payload` raises `TelemetryChainError`
- `FileTelemetrySink.verify_chain()` — sequence gap raises `TelemetryChainError`
- `FileTelemetrySink` construction with `chain_verify_on_open=True` on broken chain raises at init
- `FileTelemetrySink.__len__()` — correct count
- `FileTelemetrySink.entries()` — correct payload order
- `TelemetryLedgerReader.query()` — no filter returns all, newest-first
- `TelemetryLedgerReader.query(strategy_id=...)` — filters correctly
- `TelemetryLedgerReader.query(outcome=...)` — filters correctly
- `TelemetryLedgerReader.query(limit=..., offset=...)` — pagination deterministic
- `TelemetryLedgerReader.win_rate_by_strategy()` — correct rates
- `TelemetryLedgerReader.win_rate_by_strategy()` — empty ledger returns `{}`
- `TelemetryLedgerReader.strategy_summary()` — correct counts
- `TelemetryLedgerReader.verify_chain()` — valid chain passes
- `TelemetryLedgerReader.verify_chain()` — tampered file raises `TelemetryChainError`
- `GENESIS_PREV_HASH` — value matches `mutation_ledger.py` constant
- `FileTelemetrySink` — `entries()` is a tuple (immutable return type)
- Replay determinism: two `FileTelemetrySink` instances emitting identical payloads
  in identical order produce identical `record_hash` chains
- Schema validation: emitted records match `telemetry_decision_record.v1.json`

**CI tier: critical** (new persistence surface, chain-integrity requirement)

**Replay proof required:** strict replay artifact hash in commit trailer.

---

## 5. PR-21-02 Specification: `AutonomyLoop` Sink Upgrade + Aponi Endpoint

### Purpose

Wire `FileTelemetrySink` as the default sink for `AutonomyLoop` when a ledger
path is configured. Expose a read-only Aponi endpoint for telemetry inspection.

### Change surfaces

- `runtime/autonomy/loop.py` — add `telemetry_ledger_path` kwarg to `__init__`
- `server.py` — add `GET /telemetry/decisions` endpoint
- `tests/test_autonomy_telemetry_sink.py` — **new** (≥ 12 tests)
- `tests/test_telemetry_endpoint.py` — **new** (≥ 6 tests)
- `docs/comms/claims_evidence_matrix.md` — new rows

### `AutonomyLoop` sink upgrade contract

```python
AutonomyLoop(
    ...,
    telemetry_ledger_path: Path | str | None = None,
)
```

- If `telemetry_ledger_path` is `None` (default): use `InMemoryTelemetrySink` as before.
  Behavior is **identical** to pre-Phase-21 for all existing callers and tests.
- If `telemetry_ledger_path` is provided: construct `FileTelemetrySink(path)` and use
  its `.emit` method as the sink for `RoutedDecisionTelemetry`.
- The `ADAAD_TELEMETRY_LEDGER_PATH` environment variable is checked at boot in
  `app/main.py` — if set and non-empty, the value is passed as `telemetry_ledger_path`.
- `ADAAD_TELEMETRY_LEDGER_PATH` unset or empty → `InMemoryTelemetrySink` (no file I/O,
  identical behavior to v4.5.0).

**Invariants:**
- Existing `AutonomyLoop` tests must pass without modification. The new kwarg is
  additive and backward-compatible.
- `GovernanceGate` is not modified.
- No new constitutional rules are added.

### `GET /telemetry/decisions` endpoint contract

- **Auth:** bearer token, `audit:read` scope (same as existing governance read endpoints)
- **Query params:** `strategy_id` (optional), `outcome` (optional), `limit` (default 100,
  max 500), `offset` (default 0)
- **Response:** `{"decisions": [...], "total_queried": int, "ledger_path": str | null,
  "sink_type": "file" | "memory"}`
- **Behavior when `InMemoryTelemetrySink` is active:** returns in-memory entries.
  `"sink_type": "memory"`, `"ledger_path": null`.
- **Behavior when `FileTelemetrySink` is active:** delegates to `TelemetryLedgerReader`.
  `"sink_type": "file"`, `"ledger_path": "<configured path>"`.
- **422** on invalid query parameters.
- **Read-only.** No POST, no mutation.

### Test requirements

`tests/test_autonomy_telemetry_sink.py` (≥ 12 tests):
- `AutonomyLoop` with `telemetry_ledger_path=None` uses `InMemoryTelemetrySink`
- `AutonomyLoop` with `telemetry_ledger_path=<tmp>` uses `FileTelemetrySink`
- `ADAAD_TELEMETRY_LEDGER_PATH` env var respected at construction
- Routing decisions emitted to `FileTelemetrySink` are persisted and chain-verified
- Existing `AutonomyLoop` tests unaffected (regression gate)

`tests/test_telemetry_endpoint.py` (≥ 6 tests):
- `GET /telemetry/decisions` returns 200 with correct schema
- `GET /telemetry/decisions?strategy_id=x` filters correctly
- `GET /telemetry/decisions?limit=1&offset=0` paginates correctly
- `GET /telemetry/decisions` without auth returns 401
- `GET /telemetry/decisions?limit=501` returns 422
- `sink_type` field reflects active sink correctly

**CI tier: standard** (no governance-critical path changes; Tier 2 replay not required)

---

## 6. PR-21-REL: v4.6.0 Closure

Required deliverables:

| Artifact | Path | Notes |
|---|---|---|
| Version bump | `VERSION` | `4.5.0` → `4.6.0` |
| Release notes | `docs/releases/4.6.0.md` | Validated guarantees vs. roadmap rule |
| CHANGELOG entry | `CHANGELOG.md` | Phase 21 section |
| Evidence rows | `docs/comms/claims_evidence_matrix.md` | `file-telemetry-sink`, `telemetry-ledger-reader`, `aponi-telemetry-endpoint` |
| Agent state | `.adaad_agent_state.json` | `schema_version: 1.2.0`, `last_completed_pr: PR-21-REL`, `next_pr: PR-22-PLAN (Phase 22 — Strategy Analytics & Routing Health)`, `active_phase: Phase 21 COMPLETE · v4.6.0` |

Evidence validator must pass: `python scripts/validate_release_evidence.py --require-complete`

**CI tier: docs**

---

## 7. Commit Message Templates

### PR-21-01
```
feat(intelligence): FileTelemetrySink + TelemetryLedgerReader — sha256-chained telemetry persistence

PR-ID: PR-21-01
CI tier: critical
Replay proof: sha256:<strict-replay-artifact-hash>
```

### PR-21-02
```
feat(autonomy): AutonomyLoop telemetry sink upgrade + GET /telemetry/decisions endpoint

PR-ID: PR-21-02
CI tier: standard
Replay proof: not-required
```

### PR-21-REL
```
chore(release): Phase 21 milestone closure · v4.6.0

PR-ID: PR-21-REL
CI tier: docs
Replay proof: not-required
```

---

## 8. Evidence Gates

| Milestone | Gate |
|---|---|
| PR-21-01 merged | ≥ 28 new tests pass; `verify_chain()` tamper tests pass; strict replay SHA committed |
| PR-21-02 merged | ≥ 18 new tests pass; existing `AutonomyLoop` tests unaffected |
| v4.6.0 tagged | ≥ 2,760 tests passing (2,714 baseline + 46 new); evidence rows Complete |

---

## 9. Value Statement

The intelligence pipeline built in Phases 16–19 makes routing decisions on every
autonomy cycle. Without persistence, those decisions are invisible to every downstream
consumer: health aggregators, governance reviewers, and the `TelemetryLedgerReader`
query surface that future phases will depend on. Phase 21 converts the ephemeral
in-memory telemetry into a durable, chain-verified, queryable audit record — the same
architectural pattern that made the mutation ledger and reviewer reputation ledger
trustworthy. This completes the evidence infrastructure for the intelligence surface
and positions Phase 22 to build higher-order analytics on top of a verified history.
