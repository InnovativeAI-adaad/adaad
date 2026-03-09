# Phase 20 Upgrade Plan — Public API Consolidation

**Target version:** v4.5.0  
**Requires:** Phase 19 complete ✅ (v4.4.0 — AutonomyLoop with persistent router)  
**Author:** ADAAD Lead · InnovativeAI LLC  
**Date:** 2026-03-09

---

## 1. Objective

Phases 16–19 added 9 new modules and 17 new public symbols. None have been
declared in their package `__init__.py` exports — they are accessible only by
direct module import. This creates three concrete problems:

1. **`AutonomyLoop` not in `runtime.autonomy.__all__`** — the Phase 19 stateful
   loop class is the recommended entry point for production use but is invisible
   to `from runtime.autonomy import *` and undocumented in the public API.

2. **Phase 16/17/18 symbols absent from `runtime.intelligence.__init__`**:
   - `STRATEGY_TAXONOMY` (Phase 16) — the canonical 6-strategy registry
   - `CritiqueSignalBuffer` (Phase 18) — breach rate accumulator
   - `RoutedDecisionTelemetry` (Phase 17) — telemetry emitter
   - `InMemoryTelemetrySink` (Phase 17) — default sink for testing
   - `EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION` (Phase 17) — canonical event type

3. **`strategy.py.bak`** left in `runtime/intelligence/` — stale file, import
   noise risk, should not exist in a production module directory.

Additionally, there are no tests that verify the public API surface is stable —
a future refactor could silently break imports without any test failure.

---

## 2. PR Sequence

| PR | Scope | Tests |
|---|---|---|
| PR-20-PLAN | This document | — |
| PR-20-01 | `runtime/intelligence/__init__.py` — export Phase 16/17/18 symbols | 10 new |
| PR-20-02 | `runtime/autonomy/__init__.py` — export `AutonomyLoop`; delete `strategy.py.bak` | 8 new |
| PR-20-REL | v4.5.0: VERSION, CHANGELOG, agent state, README | — |

---

## 3. New public exports

### `runtime.intelligence`

| Symbol | Phase | Description |
|---|---|---|
| `STRATEGY_TAXONOMY` | 16 | `frozenset[str]` — 6 canonical strategy IDs |
| `CritiqueSignalBuffer` | 18 | Per-strategy breach rate accumulator |
| `RoutedDecisionTelemetry` | 17 | Append-only telemetry emitter for router decisions |
| `InMemoryTelemetrySink` | 17 | Default in-memory sink for telemetry |
| `EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION` | 17 | `"routed_intelligence_decision.v1"` |

### `runtime.autonomy`

| Symbol | Phase | Description |
|---|---|---|
| `AutonomyLoop` | 19 | Stateful loop with persistent `IntelligenceRouter` |

---

## 4. Invariants preserved

- No existing exports removed — purely additive.
- `strategy.py.bak` deletion does not affect any import path.
- Public API tests use `from runtime.intelligence import X` style —
  they will catch any future accidental removal.

---

## 5. Evidence gates

| Milestone | Gate |
|---|---|
| PR-20-01 merged | 10 new public API tests pass |
| PR-20-02 merged | 8 new autonomy API tests pass; `strategy.py.bak` absent from repo |
| v4.5.0 tagged | 2,714+ tests passing (2,696 baseline + 18 new) |
