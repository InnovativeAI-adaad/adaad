# Phase 16 Upgrade Plan — Mutation Strategy Taxonomy Expansion

**Target version:** v4.1.0  
**Requires:** Phase 15 complete ✅ (v4.0.0, governance intelligence loop closed)  
**Author:** ADAAD Lead · InnovativeAI LLC  
**Date:** 2026-03-09

---

## 1. Objective

Phase 15 closed the governance intelligence loop: every signal — governance debt, lineage
health, market fitness, bandit arm, explore/exploit mode, weight accuracy — now flows into
`ProposalRequest.context` and reaches `StrategyModule.select()`.

The bottleneck is now the **StrategyModule output**. With six live signals as input it
still chooses between only two strategies:

| Strategy ID | Activation |
|---|---|
| `adaptive_self_mutate` | High mutation score + budget |
| `conservative_hold` | Long horizon + stable lineage |

This is a two-tap valve on a six-dimensional pressure gauge. Phase 16 opens the valve by
expanding the taxonomy to **six context-driven strategies** and routes each strategy type
through a dedicated ProposalAdapter prompt and a strategy-weighted CritiqueModule floor set.

---

## 2. Six-Strategy Taxonomy

| ID | Trigger Condition | Dominant Signals |
|---|---|---|
| `adaptive_self_mutate` | mutation_score ≥ 0.70 + resource_budget ≥ 0.60 | mutation_score, resource_budget |
| `conservative_hold` | lineage_health ≥ 0.80 + horizon_cycles ≥ 9 | lineage_health, horizon_cycles |
| `structural_refactor` | lineage_health < 0.50 | lineage_health (low) |
| `test_coverage_expansion` | governance_debt_score ≥ 0.55 | governance_debt_score (high) |
| `performance_optimization` | mutation_score ≥ 0.60 + market signal pressure | mutation_score, market signals |
| `safety_hardening` | governance_debt_score ≥ 0.70 + risk elevation | governance_debt_score (critical) |

Priority order when multiple strategies qualify: `safety_hardening` > `structural_refactor`
> `test_coverage_expansion` > `performance_optimization` > `adaptive_self_mutate` >
`conservative_hold`.

All strategies must still pass all `GovernanceGate` constitutional rules — the taxonomy
influences **what is proposed**, not **what is approved**. Approval authority remains
exclusively with `GovernanceGate`.

---

## 3. PR Sequence

| PR | Scope | Tests |
|---|---|---|
| PR-16-PLAN | This document | — |
| PR-16-01 | StrategyModule: 2 → 6 strategies + `STRATEGY_TAXONOMY` registry | 18 new |
| PR-16-02 | ProposalAdapter: strategy-aware prompt routing per taxonomy type | 12 new |
| PR-16-03 | CritiqueModule: per-strategy dimension floor overrides | 10 new |
| PR-16-REL | v4.1.0 release: VERSION, CHANGELOG, agent state | — |

---

## 4. Architecture invariants preserved

- `GovernanceGate` remains the sole mutation approval surface — Phase 16 only affects proposal
  generation and critique weighting, not the approval gate.
- All six strategy paths are deterministic: same `StrategyInput` → same `StrategyDecision`
  every time, no entropy, no side effects.
- `StrategyDecision.strategy_id` is constrained to `STRATEGY_TAXONOMY` values — injection
  of unknown strategy IDs raises `ValueError` at selection time.
- `CritiqueModule` dimension floor overrides are additive upper-only adjustments to existing
  floors; no floor may be lowered below the current baseline.

---

## 5. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Existing tests assert `adaptive_self_mutate` / `conservative_hold` only | LOW | Preserve both; new strategies are additive. Existing test fixture inputs still yield the same strategies. |
| ProposalAdapter prompt injection via strategy_id | LOW | strategy_id gated to `STRATEGY_TAXONOMY` enum before prompt construction |
| CritiqueModule floor lowering accidentally passes weaker proposals | LOW | Floors are only raised for riskier strategies; floors never lowered below baseline |
| Strategy priority tie-breaking non-deterministic | LOW | Tie-breaking uses lexicographic order on strategy_id as final tiebreaker |

---

## 6. Evidence gates

| Milestone | Gate |
|---|---|
| PR-16-01 merged | All 18 new strategy tests + full test suite pass |
| PR-16-02 merged | All 12 adapter tests + full test suite pass |
| PR-16-03 merged | All 10 critique tests + full test suite pass |
| v4.1.0 tagged | 2,627+ tests passing (2,587 baseline + 40 new) |
