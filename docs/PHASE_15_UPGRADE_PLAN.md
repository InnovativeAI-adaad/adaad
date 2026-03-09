# ADAAD Phase 15 — Governance Debt + Lineage Health Wiring Upgrade Plan

**Baseline:** v3.9.0 · Phase 14 complete · Constitution v0.7.0 · 2,564+ tests passing  
**Date:** 2026-03-09  
**Author:** ADAAD Lead, InnovativeAI LLC

---

## 1. What Phase 14 unlocked

Phase 14 completed ProposalEngine activation: `EvolutionLoop` Phase 1e now calls
`ProposalEngine.generate()` every epoch with a rich live-signal `ProposalRequest.context`.
`StrategyModule.select()` maps this context into a `StrategyDecision` that shapes the
LLM prompt. Two fields were explicitly deferred to Phase 15:

```python
"governance_debt_score": 0.0,   # Phase 15: wire GovernanceDebtLedger
"lineage_health":        1.0,   # Phase 15: wire ledger proximity mean
```

Both are hardcoded constants. This means `StrategyModule` has no visibility into:
1. Accumulated governance warning debt (which should push strategy toward conservative/defensive mutations)
2. Lineage proximity health (which should push strategy toward diversity when lineage is tight)

---

## 2. Phase 15 scope

### Track 15-A — GovernanceDebtLedger wiring

**What:**  
Wire `GovernanceDebtLedger` into `EvolutionLoop`:

1. `EvolutionLoop.__init__()`: add `debt_ledger: Optional[GovernanceDebtLedger] = None`
2. After Phase 3 (Evolve), extract warning verdicts from `all_scores` and call
   `debt_ledger.accumulate_epoch_verdicts()` to compute `compound_debt_score`
3. Store `_last_debt_score: float` on the loop, updated each epoch
4. Phase 1e context builder: replace `"governance_debt_score": 0.0` with
   `"governance_debt_score": self._last_debt_score`
5. Also feed `compound_debt_score` into `AutonomyBudgetEngine.compute_threshold()`
   via `AdaptiveBudgetContext` (already wired in `adaptive_budget.py`)

**Why valuable:**  
`GovernanceDebtLedger` already tracks `compound_debt_score` — it accumulates
exponentially-weighted warning counts per epoch and decays at `decay_per_epoch=0.9`.
When constitutional warnings spike (e.g. entropy violations, complexity warnings),
the compound debt score rises. `StrategyModule` receiving this signal will shift
strategy toward "conservative_hold" or "deliver_immediate_mutation_gain" at lower
risk thresholds — preventing the engine from proposing aggressive mutations during
governance stress periods.

**PR: PR-15-01** · Tests: ~12

---

### Track 15-B — Lineage Health wiring

**What:**  
Wire `mean_lineage_proximity` (already computed in Phase 5 of `run_epoch()`) into
the Phase 1e context for the *next* epoch:

1. Add `_last_lineage_proximity: float = 0.0` to `EvolutionLoop`
2. After Phase 5 proximity computation, store `self._last_lineage_proximity = mean_lineage_proximity`
3. Phase 1e context builder: replace `"lineage_health": 1.0` with
   `"lineage_health": self._last_lineage_proximity` (or `1.0` if not yet set)
4. Clamp to `[0.0, 1.0]` to guard against edge cases in proximity computation

**Why valuable:**  
`mean_lineage_proximity` is the average semantic similarity between accepted mutations
and their ancestors in the lineage graph. Low values (novel, diverse mutations) → lineage
is healthy. High values (tight clustering around similar code changes) → lineage is
converging, which often precedes fitness plateau. `StrategyModule` receiving this
signal can diversify strategy (e.g. shift to "introduce_semantic_novelty") when
lineage is tight, and exploit known-good patterns when lineage is diverse.

**PR: PR-15-02** · Tests: ~10

---

## 3. PR sequence

| PR | What | Tests | Target version |
|---|---|---|---|
| PR-15-01 | GovernanceDebtLedger → EvolutionLoop wiring | ~12 | — |
| PR-15-02 | lineage_health from mean_lineage_proximity | ~10 | — |
| PR-15-REL | v4.0.0 release + README/docs alignment | — | v4.0.0 |

**Why v4.0.0?**  
Phase 15 closes the last hardcoded-constant gap in `ProposalRequest.context`. With
both `governance_debt_score` and `lineage_health` live-wired, the full governance
intelligence loop is closed:

```
EpochResult → GovernanceDebtLedger → compound_debt_score
EpochResult → mean_lineage_proximity → lineage_health
both → ProposalRequest.context → StrategyModule → StrategyDecision → LLM prompt
```

This is the v4.0.0 milestone: the autonomous governance intelligence loop is complete
end-to-end. Every mutation proposal now adapts to the full governance health signal.

---

## 4. Risk register

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| DebtLedger absent → `governance_debt_score` stays 0.0 | LOW | MEDIUM | Optional injection; 0.0 default preserves Phase 14 behaviour exactly |
| Warning extraction from `all_scores` misses non-blocking failures | LOW | LOW | Warnings collected from `VALIDATOR_REGISTRY` warning-tier results; constitution gate is separate |
| `mean_lineage_proximity` is 0.0 in first epoch (no accepted mutations) | LOW | HIGH | Clamped with default 1.0 if `accepted_count == 0` or proximity computation skipped |
| Strategy over-correction on high debt (always conservative) | MEDIUM | LOW | `StrategyModule` uses weighted blend; debt is one of five signals; operator can tune |

---

## 5. Evidence gates

| Milestone | Gate |
|---|---|
| PR-15-01 merged | DebtLedger tests + full autonomy/evolution suites |
| PR-15-02 merged | Lineage tests + full suites |
| v4.0.0 tagged | 2,586+ passing (excl. pre-existing failures) |

---

*Phase 15 plan. Both PRs close the last Phase 14 TODOs in `ProposalRequest.context`.  
v4.0.0 marks the complete autonomous governance intelligence loop.*
