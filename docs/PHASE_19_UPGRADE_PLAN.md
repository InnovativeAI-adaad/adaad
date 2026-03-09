# Phase 19 Upgrade Plan — AutonomyLoop Intelligence Integration

**Target version:** v4.4.0  
**Requires:** Phase 18 complete ✅ (v4.3.0 — CritiqueSignalBuffer feedback loop live)  
**Author:** ADAAD Lead · InnovativeAI LLC  
**Date:** 2026-03-09

---

## 1. Objective

Phase 18 closed the learn-from-critique feedback loop inside `IntelligenceRouter`.
However, three structural gaps prevent this from working in production:

### Gap 1 — Fresh IntelligenceRouter per run_loop() call (CRITICAL)

```python
# runtime/autonomy/loop.py — line 447
routed_intelligence = IntelligenceRouter().route(...)
```

`IntelligenceRouter()` is instantiated fresh on **every** call to `run_loop()`.
`CritiqueSignalBuffer` is owned by the router — a fresh instance has an empty buffer.
Phase 18's breach-rate feedback loop never accumulates across consecutive loop calls.

**Fix:** `AutonomyLoop` holds a persistent `IntelligenceRouter` instance across calls.
`reset_epoch()` is called at explicit epoch boundaries (not per cycle).

### Gap 2 — lineage_health not passed to StrategyInput

```python
StrategyInput(
    cycle_id=cycle_id,
    mutation_score=mutation_score,
    governance_debt_score=governance_debt_score,
    signals={"epoch_pass_rate": epoch_pass_rate},
    # lineage_health missing → defaults to 1.0
)
```

`structural_refactor` trigger: `lineage_health < 0.50`.
`conservative_hold` trigger: `lineage_health >= 0.80`.
Both are permanently blind. `lineage_health` comes from `governance_debt_score`
context that is already available in the loop.

**Fix:** Pass `lineage_health` kwarg into `StrategyInput` in `run_loop()`.
The loop already receives `governance_debt_score`; `lineage_health` can be
derived or passed as a new kwarg with default `None → 1.0` (backward-compatible).

### Gap 3 — Intelligence decision silently discarded from AutonomyLoopResult

`routed_intelligence` is computed but never included in `AutonomyLoopResult`.
The strategy chosen, outcome, and composite score are invisible to callers.
This blocks any downstream audit, dashboard, or test that wants to verify
what the intelligence layer decided during a loop cycle.

**Fix:** Add `intelligence_strategy_id`, `intelligence_outcome`, and
`intelligence_composite` fields to `AutonomyLoopResult`. All optional to preserve
backward compatibility (default `None`).

---

## 2. PR Sequence

| PR | Scope | Tests |
|---|---|---|
| PR-19-PLAN | This document | — |
| PR-19-01 | `AutonomyLoopResult` intelligence fields + `lineage_health` wire | 12 new |
| PR-19-02 | Persistent `IntelligenceRouter` in `AutonomyLoop` + buffer accumulation | 10 new |
| PR-19-REL | v4.4.0: VERSION, CHANGELOG, agent state, README | — |

---

## 3. Invariants preserved

- `run_loop()` signature: `lineage_health` added as optional kwarg with default `None`
  (coerced to `1.0`) — fully backward compatible.
- `AutonomyLoopResult` new fields are `| None` with default `None` — frozen dataclass
  fields added at end; existing field order unchanged.
- `GovernanceGate` remains sole mutation approval surface — unchanged.
- Persistent router is per-`AutonomyLoop` instance; top-level `run_loop()` function
  creates a new router per call (existing API unchanged for function callers).

---

## 4. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| AutonomyLoopResult frozen dataclass field addition breaks existing tests | LOW | New fields are `field(default=None)` appended at end |
| Persistent router state leaks between unrelated runs | LOW | Buffer scoped per `AutonomyLoop` instance; each new instance starts fresh |
| lineage_health default 1.0 changes test outcomes | LOW | 1.0 was already the implicit default; no behaviour change for existing callers |

---

## 5. Evidence gates

| Milestone | Gate |
|---|---|
| PR-19-01 merged | 12 new tests + full intelligence suite pass |
| PR-19-02 merged | 10 new tests + full intelligence suite pass |
| v4.4.0 tagged | 2,696+ tests passing (2,674 baseline + 22 new) |
