# Phase 18 Upgrade Plan — CritiqueSignal Feedback Loop

**Target version:** v4.3.0  
**Requires:** Phase 17 complete ✅ (v4.2.0, router fully wired + telemetry live)  
**Author:** ADAAD Lead · InnovativeAI LLC  
**Date:** 2026-03-09

---

## 1. Objective

Phase 17 closed the router: strategy_id flows into CritiqueModule, and every routing
decision emits a `routed_intelligence_decision.v1` telemetry event.

The remaining gap: **critique outcomes don't influence future strategy selection.**

When `CritiqueModule` rejects a proposal with `risk_below_floor` or
`governance_below_floor`, that floor breach carries signal — the selected strategy
produced a proposal that failed its own elevated floor. Phase 18 closes this loop:

```
CritiqueResult (floor_breach) → CritiqueSignalBuffer
CritiqueSignalBuffer → StrategyModule.select() → floor_breach_penalty on payoff
```

This is the **learn-from-critique** cycle: strategies that consistently produce
floor-breaching proposals accumulate a payoff penalty, shifting selection toward
strategies whose proposals pass critique.

---

## 2. Design

### CritiqueSignalBuffer (`runtime/intelligence/critique_signal.py`)

Epoch-scoped accumulator of per-strategy critique outcomes:

```python
buffer.record(strategy_id="safety_hardening", approved=False, risk_flags=["governance_below_floor:..."])
score = buffer.breach_rate(strategy_id="safety_hardening")  # 0.0–1.0
```

- Append-only within an epoch; no retroactive modification.
- Deterministic: identical record sequence → identical breach_rate.
- `breach_rate` = (breach_count / total_count) clamped [0.0, 1.0]. Returns 0.0 for
  unseen strategies (no penalty on first appearance).

### StrategyModule penalty integration

`StrategyModule.select()` accepts optional `signal_buffer: CritiqueSignalBuffer | None`.

When provided:
- Each candidate's payoff is reduced by `breach_rate(strategy_id) × _BREACH_PENALTY_WEIGHT`
- `_BREACH_PENALTY_WEIGHT = 0.20` — bounded; cannot drive payoff below 0.0
- Penalty is applied **after** trigger qualification, **before** sort — does not
  disqualify strategies, only lowers their payoff relative to breach-free alternatives
- `parameters["breach_penalties"]` reports the applied penalty per candidate

### IntelligenceRouter wire

`IntelligenceRouter` holds a `CritiqueSignalBuffer` instance across `route()` calls:
- After every critique, calls `buffer.record(strategy_id, approved, risk_flags)`
- Passes `signal_buffer=buffer` to next `StrategyModule.select()`
- Buffer resets per-epoch via `IntelligenceRouter.reset_epoch()` (explicit, not automatic)

---

## 3. PR Sequence

| PR | Scope | Tests |
|---|---|---|
| PR-18-PLAN | This document | — |
| PR-18-01 | `CritiqueSignalBuffer` + `StrategyModule` breach penalty integration | 15 new |
| PR-18-02 | `IntelligenceRouter` buffer wire across route() calls | 10 new |
| PR-18-REL | v4.3.0 release: VERSION, CHANGELOG, agent state | — |

---

## 4. Invariants preserved

- `GovernanceGate` remains sole mutation approval surface — unchanged.
- Penalty cannot drive payoff below 0.0 (clamped).
- Penalty does not disqualify strategies — only re-ranks by payoff.
- Without `signal_buffer` (default), `StrategyModule.select()` is identical to Phase 17 — fully backward compatible.
- `CritiqueSignalBuffer` is append-only within epoch; `reset_epoch()` is explicit.

---

## 5. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Penalty drives all payoffs to 0.0 under sustained breach | LOW | Penalty capped at `breach_rate × 0.20`; max reduction 0.20 per strategy |
| Feedback loop locks out a strategy permanently | LOW | Buffer is epoch-scoped; `reset_epoch()` clears all state |
| Existing StrategyModule tests break | LOW | `signal_buffer` is optional; absent → no penalty → identical behaviour |

---

## 6. Evidence gates

| Milestone | Gate |
|---|---|
| PR-18-01 merged | 15 new signal/strategy tests + full suite pass |
| PR-18-02 merged | 10 new router wire tests + full suite pass |
| v4.3.0 tagged | 2,674+ tests passing (2,649 baseline + 25 new) |
