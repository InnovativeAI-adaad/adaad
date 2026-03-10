# SPDX-License-Identifier: Apache-2.0
# ADAAD Phase 23 Upgrade Plan — Routing Health Signal Integration

**Issued by:** ArchitectAgent
**Version:** 1.0.0
**Date:** 2026-03-09
**Target version:** v4.8.0
**Baseline:** v4.7.0 · PR-22-REL · 2,822+ tests passing
**Authority chain:** `CONSTITUTION.md > ARCHITECTURE_CONTRACT.md > AGENTS.md`

---

## 1. Problem Statement

Phase 22 delivered `RoutingHealthReport` — a structured, deterministic,
green/amber/red assessment of the intelligence routing pipeline's health.
The `GET /telemetry/analytics` endpoint exposes it. The governance health
dashboard (`GET /governance/health`) does **not** consume it.

This is an observability gap: a degraded routing pipeline (all decisions
routing to `conservative_hold`; all six strategies stale except one) is
invisible to the governance health score. Operators looking at the governance
dashboard see a green `h = 0.78` while the routing layer is silent and drifted.

**Phase 23** closes this gap:

1. `routing_health_score` becomes the **fifth signal** in
   `GovernanceHealthAggregator` — weight `0.15`, with existing four signals
   rebalanced to sum to 1.0.
2. `RoutingHealthReport.health_score` is the raw input; it is clamped to
   `[0.0, 1.0]` and defaults to `1.0` (full contribution) when no telemetry
   ledger is available — preserving the existing degraded-signal convention.
3. `GET /governance/routing-health` — dedicated read-only endpoint returning
   the full `RoutingHealthReport` as a governed response.
4. `GET /governance/health` response adds `routing_health` field (structured
   summary of the routing health report — additive, non-breaking).

**What Phase 23 does NOT do:**

- Does not grant `RoutingHealthReport` any mutation approval authority.
- Does not change `GovernanceGate` behavior.
- Does not modify `StrategyAnalyticsEngine` or `TelemetryLedgerReader`.
- Does not add new constitutional rules.
- The `schema_version` of existing endpoints remains `"1.0"`.

---

## 2. Design Invariants

| Invariant | Class | Enforcement |
|---|---|---|
| Signal weights sum to exactly 1.0 | Determinism | `_validate_weights()` assertion at construction; test enforced |
| `routing_health_score` defaults to 1.0 when unavailable | Architecture | Same convention as `federation_divergence_clean` (single-node default) |
| GovernanceGate retains sole authority | Constitutional | `RoutingHealthReport.health_score` is an advisory signal input; never gates mutations |
| `GET /governance/routing-health` is read-only | Authority | GET-only; no write path |
| Existing `/governance/health` response fields unchanged | Stability | New `routing_health` field is additive only |

---

## 3. New Signal Weights (Phase 23)

| Signal | Old weight | New weight | Source |
|---|---|---|---|
| `avg_reviewer_reputation` | 0.30 | 0.25 | Phase 7 |
| `amendment_gate_pass_rate` | 0.25 | 0.22 | Phase 6 |
| `federation_divergence_clean` | 0.25 | 0.22 | Phase 5 |
| `epoch_health_score` | 0.20 | 0.16 | Core |
| `routing_health_score` | — | **0.15** | Phase 22 |
| **Total** | **1.00** | **1.00** | |

Rationale: `routing_health_score` is a new signal with limited production history;
it receives the smallest weight (0.15). The four original signals are reduced
proportionally to accommodate it, with `avg_reviewer_reputation` retaining dominance.

---

## 4. PR Sequence

| PR | Title | CI tier | Deps | Tests |
|---|---|---|---|---|
| PR-23-PLAN | This document | docs | Phase 22 ✅ | — |
| PR-23-01 | `routing_health_score` signal in `GovernanceHealthAggregator` | critical | PR-23-PLAN | ≥ 22 new |
| PR-23-02 | `GET /governance/routing-health` + health response field | standard | PR-23-01 | ≥ 16 new |
| PR-23-REL | v4.8.0: VERSION, CHANGELOG, agent state | docs | PR-23-02 | — |

Total new tests target: **≥ 38**

---

## 5. PR-23-01 Specification: `routing_health_score` Signal

### Change surfaces

- `runtime/governance/health_aggregator.py` — add `routing_health_score` to
  `SIGNAL_WEIGHTS`; rebalance all weights; add `routing_health_report` field
  to `HealthSnapshot`; add `_collect_routing_health()` collector;
  add `routing_analytics_engine` constructor kwarg
- `tests/test_routing_health_signal.py` — **new** (≥ 22 tests)

### `GovernanceHealthAggregator` changes

New constructor kwarg:
```python
routing_analytics_engine=None  # StrategyAnalyticsEngine | None
```

When `None` (default): `routing_health_score` defaults to `1.0`
(same convention as `federation_divergence_clean` single-node default).
When provided: `routing_health_score = engine.generate_report().health_score`.

New `SIGNAL_WEIGHTS` (values as per §3 above).

`HealthSnapshot` gains one new field:
```python
routing_health_report: Optional[dict] = None
```
This field holds the `RoutingHealthReport` as a serialized dict when available,
`None` when no engine is wired. It is included in `signal_breakdown` as
`routing_health_score` (the scalar), not the full report.

### `_collect_routing_health()` contract

```python
def _collect_routing_health(self) -> float:
    if self._routing_engine is None:
        return 1.0  # no telemetry → full contribution (same convention)
    try:
        report = self._routing_engine.generate_report()
        return float(max(0.0, min(1.0, report.health_score)))
    except Exception:
        log.warning("GovernanceHealthAggregator: routing health collection failed; defaulting to 1.0")
        return 1.0
```

### Weight validation

`_validate_weights()` already enforces sum-to-1.0. The new weights must pass
this check. Add an explicit test that `sum(SIGNAL_WEIGHTS.values()) == 1.0`
with tolerance `1e-9`.

### Test requirements (≥ 22 tests)

- `SIGNAL_WEIGHTS` sums to 1.0
- `SIGNAL_WEIGHTS` has exactly 5 keys
- `routing_health_score` key present in `SIGNAL_WEIGHTS` with value `0.15`
- `GovernanceHealthAggregator` with `routing_analytics_engine=None` defaults signal to `1.0`
- `GovernanceHealthAggregator` with engine returning health_score=0.8 uses it
- `GovernanceHealthAggregator` with engine raising exception defaults to `1.0` (never raises)
- `signal_breakdown` includes `routing_health_score` key
- `HealthSnapshot.routing_health_report` is `None` when no engine
- `HealthSnapshot.routing_health_report` is a dict when engine provided
- Existing four signals still collected correctly with new weights
- `health_score` is within `[0.0, 1.0]`
- Weight rebalance: `avg_reviewer_reputation` weight is `0.25`
- Weight rebalance: `amendment_gate_pass_rate` weight is `0.22`
- Weight rebalance: `federation_divergence_clean` weight is `0.22`
- Weight rebalance: `epoch_health_score` weight is `0.16`
- Full aggregation with all signals including routing health is deterministic
- `routing_health_score` clamped to `[0.0, 1.0]` even if engine returns OOB value
- Degraded threshold behavior unchanged (`h < 0.60` → degraded)
- `weight_snapshot_digest` changes when weights change (regression guard)
- Journal events still emitted with new signal
- Existing `GovernanceHealthAggregator` tests pass without modification
- `routing_health_score=1.0` default does not inflate score unreasonably
  (test: all signals at baseline, routing default → h matches expected)

**CI tier: critical**

---

## 6. PR-23-02 Specification: Endpoint + Health Field

### Change surfaces

- `server.py` — add `GET /governance/routing-health`; extend
  `GET /governance/health` with `routing_health` field
- `runtime/api/runtime_services.py` — extend `governance_health_service()` to
  wire `routing_analytics_engine` and return `routing_health` summary
- `tests/test_routing_health_endpoint.py` — **new** (≥ 10 tests)
- `tests/test_governance_health_routing_field.py` — **new** (≥ 6 tests)
- `docs/comms/claims_evidence_matrix.md` — new rows

### `GET /governance/routing-health`

- **Auth:** `audit:read` scope
- **Response:**
  ```json
  {
    "schema_version": "1.0",
    "authn": { ... },
    "data": {
      "status": "green" | "amber" | "red",
      "health_score": 0.82,
      "strategy_stats": [...],
      "dominant_strategy": "conservative_hold",
      "dominant_share": 0.61,
      "stale_strategy_ids": [],
      "drift_max": 0.08,
      "window_size": 100,
      "total_decisions": 234,
      "window_decisions": 100,
      "ledger_chain_valid": true,
      "report_digest": "sha256:...",
      "available": true
    }
  }
  ```
- When no file sink active: `available: false`, `status: "green"`,
  `health_score: 1.0`, all lists/counts at zero defaults. Returns 200.

### `GET /governance/health` extension

Adds `routing_health` to existing response — additive only:
```json
{
  ...existing fields...,
  "routing_health": {
    "available": true,
    "status": "green",
    "health_score": 0.82,
    "dominant_strategy": "conservative_hold",
    "report_digest": "sha256:..."
  }
}
```

### Test requirements

`tests/test_routing_health_endpoint.py` (≥ 10 tests):
- Returns 200 with schema
- Without auth returns 401
- `available: false` when no file sink
- `available: true` with records
- `status` in `{"green", "amber", "red"}`
- `health_score` is float in `[0.0, 1.0]`
- `report_digest` is sha256-format string
- `ledger_chain_valid` is bool
- `strategy_stats` is a list
- `dominant_strategy` is str or null

`tests/test_governance_health_routing_field.py` (≥ 6 tests):
- `GET /governance/health` includes `routing_health` field
- `routing_health.available` is bool
- `routing_health.status` is in `{"green", "amber", "red"}`
- `routing_health.health_score` is float in `[0.0, 1.0]`
- `routing_health.report_digest` is str
- Existing `/governance/health` fields unchanged

**CI tier: standard**

---

## 7. Commit Message Templates

### PR-23-01
```
feat(governance): routing_health_score signal in GovernanceHealthAggregator [22 tests]

PR-ID: PR-23-01
CI tier: critical
Replay proof: sha256:<strict-replay-artifact-hash>
```

### PR-23-02
```
feat(governance): GET /governance/routing-health + health field integration [16 tests]

PR-ID: PR-23-02
CI tier: standard
Replay proof: not-required
```

### PR-23-REL
```
chore(release): Phase 23 milestone closure · v4.8.0

PR-ID: PR-23-REL
CI tier: docs
Replay proof: not-required
```

---

## 8. Evidence Gates

| Milestone | Gate |
|---|---|
| PR-23-01 merged | ≥ 22 new tests pass; weight sum test passes; strict replay SHA committed |
| PR-23-02 merged | ≥ 16 new tests pass; existing governance health tests unaffected |
| v4.8.0 tagged | ≥ 2,860 tests (2,822 baseline + 38 new); evidence rows Complete |

---

## 9. Value Statement

The routing pipeline now produces a chain-verified, analytically rich health signal
(Phase 22). Failing to wire it into the governance health score means operators
have two separate health surfaces that can give contradictory readings. Phase 23
unifies them: `RoutingHealthReport.health_score` becomes a first-class governance
signal with weight 0.15, making the composite governance health score sensitive to
routing degradation without granting routing analytics any decision authority.
This completes the observability arc and positions Phase 24 to act on the unified
signal — for example, raising the `constitutional_floor` reviewer count when the
governance health composite falls into amber.
