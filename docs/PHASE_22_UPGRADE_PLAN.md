# SPDX-License-Identifier: Apache-2.0
# ADAAD Phase 22 Upgrade Plan — Strategy Analytics & Routing Health

**Issued by:** ArchitectAgent
**Version:** 1.0.0
**Date:** 2026-03-09
**Target version:** v4.7.0
**Baseline:** v4.6.0 · PR-21-REL · 2,775+ tests passing
**Authority chain:** `CONSTITUTION.md > ARCHITECTURE_CONTRACT.md > AGENTS.md`

---

## 1. Problem Statement

Phase 21 introduced `FileTelemetrySink` and `TelemetryLedgerReader` — a persistent,
chain-verified audit record of every `IntelligenceRouter` routing decision. The ledger
now exposes `win_rate_by_strategy()` and `strategy_summary()` as raw query primitives.

**These primitives are necessary but not sufficient for governed observability.** The
questions operators and governance reviewers need answered require higher-order analysis:

- Is the system's routing distribution healthy, or is one strategy dominating/collapsing?
- Has any strategy's win rate drifted significantly across a rolling window?
- Is routing quality improving, stable, or degrading over time?
- Which strategies have not fired recently — potential dead-code risk?

None of these can be answered by a single `win_rate_by_strategy()` call. They require
rolling-window aggregation, drift detection, and a structured health classification
(`green` / `amber` / `red`) — the same pattern Phase 8 established for governance health.

**Phase 22** closes this gap by adding:

1. `StrategyAnalyticsEngine` — rolling-window win-rate aggregation, drift detection,
   strategy staleness flags, and `RoutingHealthReport` production
2. `GET /telemetry/analytics` — full routing health report endpoint
3. `GET /telemetry/strategy/{strategy_id}` — per-strategy detail endpoint
4. `RoutingHealthReport` schema enforcement via JSON Schema

**What Phase 22 does NOT do:**

- Does not modify `FileTelemetrySink`, `TelemetryLedgerReader`, or any Phase 21 surface
- Does not add constitutional rules or modify `GovernanceGate`
- Does not change `AutonomyLoop` or `IntelligenceRouter` behavior
- Does not feed routing health into mutation approval decisions — observability only
- Does not change any existing endpoint

---

## 2. Design Invariants

| Invariant | Class | Enforcement |
|---|---|---|
| Analytics are advisory only | Authority | No `RoutingHealthReport` field gates or unblocks mutations |
| `StrategyAnalyticsEngine` is read-only | Architecture | Never writes to the telemetry ledger |
| Deterministic output | Determinism | Same ledger state + same params → identical `RoutingHealthReport` |
| Drift detection is bounded | Determinism | Window sizes are integer parameters with explicit min/max constraints |
| `GovernanceGate` retains sole mutation authority | Constitutional | Analytics engine has no reference to `GovernanceGate` |
| Health classification thresholds are constants | Determinism | No dynamic threshold; defined as named constants in the module |
| Empty ledger is valid | Stability | Engine returns a zero-data report; never raises on empty ledger |

---

## 3. PR Sequence

| PR | Title | CI tier | Deps | Tests |
|---|---|---|---|---|
| PR-22-PLAN | This document | docs | Phase 21 ✅ | — |
| PR-22-01 | `StrategyAnalyticsEngine` + `RoutingHealthReport` | critical | PR-22-PLAN | ≥ 25 new |
| PR-22-02 | Analytics Aponi endpoints | standard | PR-22-01 | ≥ 14 new |
| PR-22-REL | v4.7.0: VERSION, CHANGELOG, agent state, README | docs | PR-22-02 | — |

Total new tests target: **≥ 39**

---

## 4. PR-22-01 Specification: `StrategyAnalyticsEngine` + `RoutingHealthReport`

### Purpose

Compute rolling-window win rates, drift detection, staleness flags, and a structured
`RoutingHealthReport` from a `TelemetryLedgerReader` (or any compatible source).

### Change surfaces

- `runtime/intelligence/strategy_analytics.py` — **new**
- `runtime/intelligence/__init__.py` — export `StrategyAnalyticsEngine`,
  `RoutingHealthReport`, `StrategyWindowStats`
- `schemas/routing_health_report.v1.json` — **new**
- `tests/test_strategy_analytics.py` — **new** (≥ 25 tests)

### `StrategyWindowStats` contract

```python
@dataclass(frozen=True)
class StrategyWindowStats:
    strategy_id: str
    window_size: int          # number of decisions in the window
    total: int                # all-time total for this strategy
    approved: int             # all-time approved count
    win_rate: float           # approved / total (0.0 if total == 0)
    window_win_rate: float    # approved / window_size within window (0.0 if window empty)
    drift: float              # abs(window_win_rate - win_rate); 0.0 if total < 2
    stale: bool               # True if strategy has fired 0 decisions in the window
    last_seen_sequence: int   # highest sequence number for this strategy; -1 if never seen
```

All fields are deterministic from the same ledger + window inputs.

### `RoutingHealthReport` contract

```python
@dataclass(frozen=True)
class RoutingHealthReport:
    status: str               # "green" | "amber" | "red"
    health_score: float       # 0.0..1.0; composite of win-rate and distribution metrics
    strategy_stats: tuple[StrategyWindowStats, ...]  # one per known strategy, sorted by strategy_id
    dominant_strategy: str | None   # strategy_id with highest window decision share; None if empty
    dominant_share: float           # fraction of window decisions for dominant strategy; 0.0 if empty
    stale_strategy_ids: tuple[str, ...]  # strategy_ids with stale=True, sorted
    drift_max: float          # max drift across all strategies; 0.0 if < 2 total
    window_size: int          # configured window size
    total_decisions: int      # all-time decision count across all strategies
    window_decisions: int     # decisions in the window
    ledger_chain_valid: bool  # result of TelemetryLedgerReader.verify_chain()
    report_digest: str        # sha256 of canonical report fields (determinism proof)
```

**Health classification thresholds (constants — never dynamic):**

```
HEALTH_GREEN_MIN_SCORE   = 0.65
HEALTH_AMBER_MIN_SCORE   = 0.35
# below HEALTH_AMBER_MIN_SCORE → "red"

DOMINANT_SHARE_AMBER_THRESHOLD = 0.75   # one strategy > 75% of window → amber at most
DOMINANT_SHARE_RED_THRESHOLD   = 0.90   # one strategy > 90% of window → red
DRIFT_AMBER_THRESHOLD          = 0.20   # max drift > 0.20 → amber at most
DRIFT_RED_THRESHOLD            = 0.40   # max drift > 0.40 → red
STALE_AMBER_FRACTION           = 0.34   # > 1/3 strategies stale → amber at most
STALE_RED_FRACTION             = 0.60   # > 3/5 strategies stale → red
```

**Health score formula (deterministic):**

```
win_rate_component      = mean(s.window_win_rate for s in strategy_stats if not s.stale)
                          (1.0 if no non-stale strategies)
distribution_penalty    = dominant_share * 0.3
staleness_penalty       = (len(stale_strategy_ids) / len(STRATEGY_TAXONOMY)) * 0.2
drift_penalty           = min(drift_max, 1.0) * 0.2
health_score = clamp(win_rate_component - distribution_penalty - staleness_penalty - drift_penalty, 0.0, 1.0)
```

**Status classification (evaluated in order — first match wins):**

1. `drift_max > DRIFT_RED_THRESHOLD` → `"red"`
2. `dominant_share > DOMINANT_SHARE_RED_THRESHOLD` → `"red"`
3. `len(stale_strategy_ids) / len(STRATEGY_TAXONOMY) > STALE_RED_FRACTION` → `"red"`
4. `health_score < HEALTH_AMBER_MIN_SCORE` → `"red"`
5. `drift_max > DRIFT_AMBER_THRESHOLD` → `"amber"`
6. `dominant_share > DOMINANT_SHARE_AMBER_THRESHOLD` → `"amber"`
7. `len(stale_strategy_ids) / len(STRATEGY_TAXONOMY) > STALE_AMBER_FRACTION` → `"amber"`
8. `health_score < HEALTH_GREEN_MIN_SCORE` → `"amber"`
9. otherwise → `"green"`

### `StrategyAnalyticsEngine` contract

```python
StrategyAnalyticsEngine(
    reader: TelemetryLedgerReader,
    *,
    window_size: int = 100,       # must be in [10, 10_000]
    strategy_taxonomy: frozenset[str] | None = None,   # defaults to STRATEGY_TAXONOMY
)
```

**`generate_report() -> RoutingHealthReport`:**

- Reads all records from `reader` once per call (streaming, O(n) memory).
- Computes all-time stats from full ledger; window stats from last `window_size` records.
- Calls `reader.verify_chain()`; stores result in `ledger_chain_valid`.
- Raises `StrategyAnalyticsError` if `window_size` is out of `[10, 10_000]`.
- Returns `RoutingHealthReport` with deterministic `report_digest`.
- Never writes to the ledger.
- Never references `GovernanceGate`.

**`report_digest` computation:**

```python
digest_input = json.dumps({
    "status": report.status,
    "health_score": round(report.health_score, 8),
    "dominant_strategy": report.dominant_strategy,
    "dominant_share": round(report.dominant_share, 8),
    "drift_max": round(report.drift_max, 8),
    "window_size": report.window_size,
    "total_decisions": report.total_decisions,
    "window_decisions": report.window_decisions,
    "stale_strategy_ids": list(report.stale_strategy_ids),
    "strategy_stats": [
        {
            "strategy_id": s.strategy_id,
            "win_rate": round(s.win_rate, 8),
            "window_win_rate": round(s.window_win_rate, 8),
            "drift": round(s.drift, 8),
            "stale": s.stale,
        }
        for s in report.strategy_stats
    ],
}, sort_keys=True, separators=(",", ":"))
report_digest = "sha256:" + hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
```

### Schema: `schemas/routing_health_report.v1.json`

Required top-level fields: `status`, `health_score`, `strategy_stats`,
`dominant_strategy`, `dominant_share`, `stale_strategy_ids`, `drift_max`,
`window_size`, `total_decisions`, `window_decisions`, `ledger_chain_valid`,
`report_digest`.

### Test requirements (≥ 25 tests in `tests/test_strategy_analytics.py`)

Must cover:
- `StrategyAnalyticsEngine` on empty ledger returns valid report, status "green", zero counts
- Single-strategy ledger: correct win_rate, stale=False for active strategy, stale=True for others
- Multi-strategy ledger: win_rate_by_strategy matches `TelemetryLedgerReader.win_rate_by_strategy()`
- Window smaller than total: window stats reflect only last N records
- Drift detection: strategy shifts from high to low win rate → drift > 0
- Dominant strategy detection: correct `dominant_strategy` and `dominant_share`
- Stale detection: strategy with zero window decisions is stale
- Health score is in [0.0, 1.0] for all test cases
- Status "red" triggered by high drift (> DRIFT_RED_THRESHOLD)
- Status "red" triggered by dominant share (> DOMINANT_SHARE_RED_THRESHOLD)
- Status "red" triggered by high stale fraction
- Status "amber" triggered by moderate drift
- Status "amber" triggered by moderate dominance
- Status "green" on balanced healthy ledger
- `report_digest` is deterministic: same ledger + same window → same digest
- `report_digest` changes when ledger changes
- `ledger_chain_valid` True on valid chain, False on tampered chain
- `StrategyAnalyticsError` raised on window_size < 10
- `StrategyAnalyticsError` raised on window_size > 10_000
- `strategy_stats` tuple is sorted by strategy_id
- `stale_strategy_ids` tuple is sorted
- All 6 STRATEGY_TAXONOMY members always appear in `strategy_stats` (even if unseen)
- Empty window (window_size > total decisions): window == all-time stats
- `generate_report()` never mutates the ledger file

**CI tier: critical** (new analytics surface; report_digest determinism requirement)

---

## 5. PR-22-02 Specification: Analytics Aponi Endpoints

### Purpose

Expose `RoutingHealthReport` and per-strategy detail via read-only bearer-auth-gated
endpoints following the established governance health endpoint pattern.

### Change surfaces

- `server.py` — add `GET /telemetry/analytics` and `GET /telemetry/strategy/{strategy_id}`
- `tests/test_analytics_endpoints.py` — **new** (≥ 14 tests)
- `docs/comms/claims_evidence_matrix.md` — new rows

### `GET /telemetry/analytics` contract

- **Auth:** bearer token, `audit:read` scope
- **Query params:** `window_size` (optional int, 10–10000, default 100)
- **Response:** `{"schema_version": "1.0", "authn": {...}, "data": <RoutingHealthReport as dict>}`
- **Behavior when no FileTelemetrySink configured:** returns a zero-data report from
  the in-memory sink (if populated); `total_decisions: 0` is valid and not an error.
- **422** on `window_size` out of range.
- **Read-only.** No write path.

### `GET /telemetry/strategy/{strategy_id}` contract

- **Auth:** bearer token, `audit:read` scope
- **Query params:** `window_size` (optional int, 10–10000, default 100)
- **Path param:** `strategy_id` — must be in `STRATEGY_TAXONOMY`
- **Response:** `{"schema_version": "1.0", "authn": {...}, "data": <StrategyWindowStats as dict>}`
- **404** if `strategy_id` not in `STRATEGY_TAXONOMY`.
- **422** on `window_size` out of range.
- **Read-only.**

### Test requirements (≥ 14 tests in `tests/test_analytics_endpoints.py`)

Must cover:
- `GET /telemetry/analytics` returns 200 with required schema fields
- `GET /telemetry/analytics` without auth returns 401
- `GET /telemetry/analytics?window_size=5` returns 422
- `GET /telemetry/analytics?window_size=10001` returns 422
- `GET /telemetry/analytics` with file sink active returns correct strategy_stats count
- `GET /telemetry/analytics` status field is one of {green, amber, red}
- `GET /telemetry/analytics` report_digest field is sha256 prefixed string
- `GET /telemetry/strategy/conservative_hold` returns 200 with strategy_id field
- `GET /telemetry/strategy/unknown_strategy` returns 404
- `GET /telemetry/strategy/conservative_hold` without auth returns 401
- `GET /telemetry/strategy/adaptive_self_mutate` returns correct strategy_id
- `GET /telemetry/analytics?window_size=50` respects window_size param
- `GET /telemetry/analytics` with empty sink returns valid zero-data report (not error)
- Response `data.ledger_chain_valid` is boolean

**CI tier: standard**

---

## 6. PR-22-REL: v4.7.0 Closure

| Artifact | Path | Notes |
|---|---|---|
| Version bump | `VERSION` | `4.6.0` → `4.7.0` |
| Release notes | `docs/releases/4.7.0.md` | Validated guarantees vs. roadmap rule |
| CHANGELOG entry | `CHANGELOG.md` | Phase 22 section |
| Evidence rows | `docs/comms/claims_evidence_matrix.md` | `strategy-analytics-engine`, `routing-health-report`, `aponi-analytics-endpoints` |
| Agent state | `.adaad_agent_state.json` | `schema_version: 1.3.0`, `last_completed_pr: PR-22-REL`, `next_pr: PR-23-PLAN (Phase 23 — Routing Health Signal Integration)`, `active_phase: Phase 22 COMPLETE · v4.7.0` |

Evidence validator must pass: `python scripts/validate_release_evidence.py --require-complete`

**CI tier: docs**

---

## 7. Commit Message Templates

### PR-22-01
```
feat(intelligence): StrategyAnalyticsEngine + RoutingHealthReport — rolling win-rate analytics

PR-ID: PR-22-01
CI tier: critical
Replay proof: sha256:<strict-replay-artifact-hash>
```

### PR-22-02
```
feat(server): GET /telemetry/analytics + GET /telemetry/strategy/{id} endpoints

PR-ID: PR-22-02
CI tier: standard
Replay proof: not-required
```

### PR-22-REL
```
chore(release): Phase 22 milestone closure · v4.7.0

PR-ID: PR-22-REL
CI tier: docs
Replay proof: not-required
```

---

## 8. Evidence Gates

| Milestone | Gate |
|---|---|
| PR-22-01 merged | ≥ 25 new tests pass; report_digest determinism test passes; strict replay SHA committed |
| PR-22-02 merged | ≥ 14 new tests pass; existing telemetry endpoint tests unaffected |
| v4.7.0 tagged | ≥ 2,814 tests (2,775 baseline + 39 new); evidence rows Complete |

---

## 9. Value Statement

Phase 21 created the audit trail. Phase 22 makes it actionable. Without analytics,
operators must manually query raw ledger data to detect when `conservative_hold` is
capturing 90% of routing decisions (a signal of either systematic governance pressure or
a broken fitness pipeline), or when `adaptive_self_mutate` has not fired in 500 epochs
(a signal of suppression). The `RoutingHealthReport` surfaces these conditions as
structured, machine-readable, deterministic artifacts — with the same green/amber/red
classification operators already know from Phase 8's governance health endpoint.

The `report_digest` provides cryptographic proof of report reproducibility, enabling
any downstream consumer to verify that two routing health assessments were produced
from identical ledger state and configuration. This positions Phase 23 to wire routing
health as an input to the adaptive constitutional governance loop introduced in the
ADAAD-15 ArchitectAgent specification.
