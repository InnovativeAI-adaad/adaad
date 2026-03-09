# Phase 17 Upgrade Plan — IntelligenceRouter Closure

**Target version:** v4.2.0  
**Requires:** Phase 16 complete ✅ (v4.1.0, 6-strategy taxonomy live)  
**Author:** ADAAD Lead · InnovativeAI LLC  
**Date:** 2026-03-09

---

## 1. Objective

Phase 16 expanded `StrategyModule` to 6 strategies, added strategy-aware LLM prompts
in `ProposalAdapter`, and introduced per-strategy dimension floor overrides in
`CritiqueModule.review(strategy_id=...)`.

However, **two wiring gaps remain open**:

### Gap 1 — Router does not pass strategy_id to CritiqueModule (PR-17-01)

`IntelligenceRouter.route()` calls:

```python
critique = self._critique.review(proposal)          # ← no strategy_id
```

`CritiqueModule.review()` now accepts `strategy_id` as an optional kwarg (Phase 16).
Without the wire, every `route()` call evaluates proposals against **baseline floors**
regardless of which strategy was selected — the Phase 16 per-strategy floors are dead code.

**Fix:** Pass `strategy_id=strategy.strategy_id` to `self._critique.review()`.

### Gap 2 — RoutedIntelligenceDecision emits no telemetry (PR-17-02)

`IntelligenceRouter.route()` produces a `RoutedIntelligenceDecision` but never emits
a ledger event. The strategy selected, outcome (`execute`/`hold`), composite critique
score, and dimension verdicts are invisible to the audit trail.

**Fix:** Emit `routed_intelligence_decision.v1` as an append-only journal event on
every `route()` call, carrying: `cycle_id`, `strategy_id`, `outcome`, `composite`,
`dimension_verdicts`, `review_digest`.

---

## 2. PR Sequence

| PR | Scope | Tests |
|---|---|---|
| PR-17-PLAN | This document | — |
| PR-17-01 | Router → strategy_id wire into CritiqueModule.review() | 10 new |
| PR-17-02 | RoutedDecisionTelemetry — `routed_intelligence_decision.v1` ledger event | 12 new |
| PR-17-REL | v4.2.0 release: VERSION, CHANGELOG, agent state | — |

---

## 3. Invariants preserved

- `GovernanceGate` remains sole mutation approval surface.
- `RoutedDecisionTelemetry` is append-only; never mutates any pipeline state.
- `IntelligenceRouter.route()` signature unchanged — backward compatible.
- Telemetry emission failure is isolated (exception logged, not propagated) —
  router outcome is never degraded by a telemetry write failure.

---

## 4. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Existing router tests break on strategy_id wire | LOW | Tests use `PositiveImpactProposalModule` which passes critique; strategy_id is advisory, floors only raised |
| Telemetry event shape breaks AGM event validation | LOW | New event type `routed_intelligence_decision.v1` is registered in `CANONICAL_EVENT_TYPES` before emission |
| Loop emit failure degrades mutation throughput | LOW | Telemetry failure is caught and logged; router returns normally |

---

## 5. Evidence gates

| Milestone | Gate |
|---|---|
| PR-17-01 merged | 10 new router wiring tests + full suite pass |
| PR-17-02 merged | 12 new telemetry tests + full suite pass |
| v4.2.0 tagged | 2,649+ tests passing (2,627 baseline + 22 new) |
