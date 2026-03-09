# ADAAD Phase 14 — ProposalEngine Activation Upgrade Plan

**Baseline:** v3.8.0 · Phase 13 complete · Constitution v0.7.0 · 2,531+ tests passing  
**Date:** 2026-03-09  
**Author:** ADAAD Lead, InnovativeAI LLC

---

## 1. What Phase 13 unlocked

Phase 13 completed the Market Signal Integrity guard:

| Capability | Module | Phase |
|---|---|---|
| Consecutive synthetic market epoch tracking | `market_fitness_integrator.py` | 13 |
| `market_signal_integrity_invariant` BLOCKING rule | `constitution.py` / `constitution.yaml` | 13 |
| `EpochResult.consecutive_synthetic_market_epochs` observable | `evolution_loop.py` | 13 |
| Cross-epoch digest verification | `context_replay_interface.py` | 12 |
| Live market signal fields on `EpochResult` | `evolution_loop.py` | 12 |
| AgentBanditSelector — UCB1 + Thompson (Phase 11-A) | `agent_bandit_selector.py` | 11 |

The system now has a full, constitutionally-gated feedback loop:
mutations are proposed, scored, governance-gated, accepted/rejected, those outcomes
update learning profiles, the bandit selector exploits them, live market signals
are guard-railed, and all of this is tamper-evident via the Merkle ledger.

**What is still missing:**

The `ProposalEngine` (introduced in `runtime/evolution/proposal_engine.py`) is a
fully implemented, LLM-backed mutation proposal generator with a typed `StrategyModule`
that prioritises objectives based on live signals — yet it is **not wired into
`EvolutionLoop`**. The main loop still uses `propose_from_all_agents()`, a direct
three-agent call that:

1. Sends raw `CodebaseContext` to each agent without structured strategy context
2. Does not inject live signals (`market_score`, `bandit_rec`, `explore_ratio`) as
   structured fields into the prompt context
3. Has no per-cycle objective prioritisation — all three agents always run the same
   prompt shape regardless of epoch health, governance debt, or market signal quality

`ProposalEngine.generate()` activation is the **single highest-leverage remaining
task for commercial viability**: it converts ADAAD from a system that loops three
agents identically into one that adapts its mutation strategy per-epoch based on the
governance intelligence accumulated in Phases 9–13.

---

## 2. Phase 14 scope

### Track 14-A — ProposalEngine → EvolutionLoop wiring

**What:**  
Wire `ProposalEngine` as an optional parallel injection path in `EvolutionLoop` Phase 1.
When injected, the engine's `generate()` call runs alongside `propose_from_all_agents`
and its output is converted into a `MutationCandidate` that enters the same governed
pipeline. When not injected, the loop is completely unchanged (backwards-compatible).

**PR sequence:**

| PR | What | Tests |
|---|---|---|
| PR-14-01 | `ProposalEngine` → `EvolutionLoop` Phase 1e wiring + `Proposal` → `MutationCandidate` bridge | 12 |
| PR-14-02 | Live signal population into `ProposalRequest.context` (market, bandit, explore ratio) | 8 |
| PR-14-REL | v3.9.0 release + Phase 14 plan doc + README/docs alignment | — |

---

## 3. PR-14-01: EvolutionLoop Phase 1e wiring

**`runtime/evolution/evolution_loop.py`:**

- `EvolutionLoop.__init__()`: add `proposal_engine: Optional[ProposalEngine] = None`
- Phase 1e (inserted after Phase 1, before Phase 1.5):
  - If `self._proposal_engine is not None`:
    - Build `ProposalRequest(cycle_id=epoch_id, strategy_id="auto", context={})`
    - Call `self._proposal_engine.generate(request)` — noop result is silently skipped
    - If `Proposal.real_diff` is non-empty: convert to `MutationCandidate` and append to `all_proposals`
  - Exception-isolated: any failure silently skips the engine proposal

**`_proposal_to_candidate()` bridge function (new, module-level):**

```python
def _proposal_to_candidate(proposal: Proposal, *, epoch_id: str) -> Optional[MutationCandidate]:
    """Convert a ProposalEngine Proposal to a MutationCandidate for EvolutionLoop."""
    if not proposal.real_diff:
        return None  # noop proposals have no diff — skip silently
    return MutationCandidate(
        mutation_id        = proposal.proposal_id,
        expected_gain      = float(proposal.estimated_impact),
        risk_score         = float(proposal.projected_impact.get("risk", 0.5)),
        complexity         = float(proposal.projected_impact.get("complexity", 0.5)),
        coverage_delta     = float(proposal.projected_impact.get("coverage_delta", 0.0)),
        agent_origin       = "proposal_engine",
        epoch_id           = epoch_id,
        python_content     = proposal.real_diff,   # diff content scored by semantic diff engine
        operator_category  = "llm_strategy",
        operator_version   = "14.0.0",
    )
```

**Tests (12):**
- `proposal_engine` absent → no change to existing proposals
- `proposal_engine` injected → `generate()` called once per epoch
- noop proposal (empty `real_diff`) → silently skipped, not added to candidates
- valid proposal → `MutationCandidate` appended to `all_proposals`
- `generate()` raises → exception isolated, epoch continues
- `_proposal_to_candidate` field mapping (mutation_id, agent_origin, expected_gain, risk_score)
- `_proposal_to_candidate` returns None on empty diff
- `MutationCandidate` from engine enters `PopulationManager.seed()` normally
- `EpochResult.accepted_count` reflects engine-sourced accepted mutations
- Constitution gate applies identically to engine-sourced mutations

---

## 4. PR-14-02: Live signal population into ProposalRequest.context

**`runtime/evolution/evolution_loop.py` Phase 1e context builder:**

Build `ProposalRequest.context` from live epoch state captured earlier in `run_epoch()`:

```python
context = {
    # Market signal quality
    "market_score":             _market_live_score,
    "market_confidence":        _market_confidence,
    "market_is_synthetic":      _market_is_synthetic,
    "consecutive_synthetic":    _market_consec_synthetic,
    # Bandit strategy recommendation
    "bandit_agent":             _bandit_rec.agent if _bandit_rec else None,
    "bandit_confidence":        _bandit_rec.confidence if _bandit_rec else 0.0,
    "exploration_bonus":        _bandit_rec.exploration_bonus if _bandit_rec else 0.0,
    # Explore/exploit state
    "explore_ratio":            context.explore_ratio,
    "evolution_mode":           mode_str,
    # Governance state
    "epoch_id":                 epoch_id,
    "epoch_count":              self._epoch_count,
    "last_health_score":        self._last_epoch_health_score,
    # Standard ProposalEngine fields
    "mutation_score":           self._adaptor.prediction_accuracy,
    "governance_debt_score":    0.0,   # TODO: wire GovernanceDebtLedger in Phase 15
    "lineage_health":           mean_lineage_proximity if ... else 1.0,
}
```

**`StrategyModule.select()` then maps these signals into a `StrategyDecision`** that
the `ProposalAdapter` uses to shape the LLM prompt — market degradation → conservative
strategy; high explore ratio → experimental strategy; high bandit confidence → exploit.

**Tests (8):**
- context builder populates `market_score` from `_market_live_score`
- context builder populates `bandit_agent` from bandit recommendation
- context builder populates `explore_ratio` from `context.explore_ratio`
- context builder populates `mutation_score` from `prediction_accuracy`
- no bandit → `bandit_agent` is None in context
- synthetic market → `market_is_synthetic` is True in context
- `ProposalRequest.context` dict passed to `engine.generate()` unchanged
- context fields survive `_build_strategy_input()` mapping correctly

---

## 5. Risk register

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| Engine proposal duplicates existing agent proposal content | LOW | LOW | `mutation_id` is `proposal_id` (cycle:strategy) — dedup in `PopulationManager` by MD5 hash |
| Engine noop when no API key configured | LOW | HIGH | Noop silently skipped; existing loop unaffected |
| `StrategyModule` sends contradictory strategy to agents | LOW | MEDIUM | Engine runs as independent path; agent proposals unaffected |
| `ProposalAdapter` LLM latency degrades epoch time | MEDIUM | MEDIUM | Exception-isolated; engine call is fire-and-catch; timeout via `ADAAD_LLM_TIMEOUT_SECONDS` |

---

## 6. Evidence gates

| Milestone | Gate | Target |
|---|---|---|
| PR-14-01 merged | All autonomy + evolution tests | 0 new failures |
| PR-14-02 merged | Context signal mapping tests | 8/8 passing |
| v3.9.0 tagged | Full suite (excl. pre-existing failures) | 2,551+ passing |

---

## 7. Immediate next actions

1. Implement PR-14-01: `_proposal_to_candidate()` bridge + Phase 1e wiring in `evolution_loop.py`
2. Tests: 12 tests in `tests/evolution/test_proposal_engine_evolution_wiring.py`
3. Merge PR-14-01 → implement PR-14-02 (signal context population)
4. PR-14-REL: VERSION 3.8.0 → 3.9.0, CHANGELOG, README/docs update

---

*Phase 14 plan. ProposalEngine activation is the highest-leverage commercial gap.  
Constitutional invariants gate every merge.*
