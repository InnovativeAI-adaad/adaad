# ADAAD Phase 11 — Upgrade Plan

**Baseline:** v3.5.0 · Phase 10 complete · 143 memory/autonomy tests passing  
**Date:** 2026-03-09  
**Author:** ADAAD Lead, InnovativeAI LLC

---

## 1. What Phase 10 unlocked

Phase 10 completed the Reward Learning Pipeline:

| Capability | Module | Phase |
|---|---|---|
| Cross-epoch fitness signal persistence | `reward_signal_bridge.py` | 5d |
| Guarded weight promotion gate | `policy_promotion_controller.py` | 4b |
| Live market signal integration | `market_fitness_integrator.integrate()` | 2 (enrichment) |
| Rolling baseline EMA (window=5) | `PolicyPromotionController` | 4b |
| Tamper-evident Merkle ledger | `soulbound_ledger.py` | 5c |
| Replay context injection | `context_replay_interface.py` | 0c |

The system now has end-to-end feedback: mutations are proposed, scored, governance-gated,
accepted/rejected — and those outcomes are fed back into a learning profile that influences
weight promotion, explore/exploit balance, and craft pattern dominance across future epochs.

**What is still missing:**

1. The reward learning profiles (`LearningProfileRegistry`) are updated per-epoch but never
   directly drive agent selection strategy — the E/E controller and agent selection are
   informed only by `FitnessLandscape` win/loss counts and `ContextReplayInterface` explore
   ratio adjustments. There is no closed bandit loop directly exploiting reward profile data.

2. `MarketFitnessIntegrator.integrate()` injects a live market score into `FitnessOrchestrator`
   but that score is not yet propagated into `EpochResult` as an observable field — downstream
   consumers cannot react to live market signal quality.

3. The Constitution (v0.5.0) has no invariants governing the integrity of live market signals —
   a corrupt or adversarial feed can degrade fitness scores without detection.

4. `ContextReplayInterface` injects explore ratio and a context digest but the digest is not
   yet verified against ledger chain integrity on replay — there is no cross-epoch digest
   validation path.

---

## 2. Phase 11 candidate tracks

Four tracks are proposed. One will be sequenced first; others follow in subsequent phases.

---

### Track 11-A — Bandit-informed agent selection (LEADING CANDIDATE)

**What:** Replace the heuristic recommended_agent logic in `FitnessLandscape` with a UCB1
or Thompson Sampling bandit that draws directly from `LearningProfileRegistry` reward profiles.

**Why leading:**  
- Closes the feedback loop that Phases 9-10 built — reward profiles have been accumulating
  since v3.4.0; Phase 11 is the first opportunity to exploit them in real selection decisions.
- High expected ROI: the bandit replaces a simple win-rate heuristic that has no memory
  beyond the current landscape; reward profiles carry cross-epoch agent-level performance data.
- Low blast radius: the bandit only affects agent selection preference — it does not touch
  governance, ledger writes, or weight adaptation. Regression is bounded to agent selection bias.

**Scope:**
- New module: `runtime/autonomy/agent_bandit_selector.py`
  - `AgentBanditSelector` with UCB1 (default) and Thompson Sampling (optional) strategies
  - Reads from `LearningProfileRegistry` — per-agent: accepted_count, avg_reward, epoch count
  - Returns `BanditAgentRecommendation(agent, confidence, strategy, exploration_bonus)`
  - Tracks per-agent arm stats in `data/agent_bandit_state.json`
- `runtime/evolution/fitness_landscape.py`: `recommended_agent()` extended to accept optional
  `BanditAgentRecommendation`; falls back to existing win-rate logic when bandit returns None
- `EvolutionLoop` Phase 0d (between 0c and 1): call `AgentBanditSelector.recommend()`,
  pass recommendation to `FitnessLandscape.recommended_agent()` override
- Constitution v0.6.0: `bandit_arm_integrity_invariant` — arm stats must be non-negative;
  bandit must not promote the same agent for more than N consecutive epochs without reset
- Tests: 20 tests (bandit math, arm tracking, UCB1/Thompson selection, loop wiring, constitution)

**PR sequence:**

| PR | What | Tests |
|---|---|---|
| PR-11-A-01 | `AgentBanditSelector` (UCB1 + Thompson) + arm state JSON | 12 |
| PR-11-A-02 | `FitnessLandscape` bandit override + `EvolutionLoop` Phase 0d wiring | 5 |
| PR-11-A-03 | Constitution v0.6.0 `bandit_arm_integrity_invariant` + v3.6.0 release | 3 |

**Risk:** LOW — bandit output is advisory; `FitnessLandscape.recommended_agent()` retains
fallback logic. Regression bounded to single-agent proposal concentration.

**Evidence gate:** `avg_reward` gain over baseline (win-rate-only) ≥ 5% across 10 simulated
epochs in CI simulation harness before PR-11-A-03 merge.

---

### Track 11-B — Market signal integrity invariant (Constitution v0.6.0)

**What:** Add a `market_signal_integrity_invariant` BLOCKING rule to the Constitution.
When `MarketFitnessIntegrator.integrate()` returns `is_synthetic=True` for more than
`MAX_SYNTHETIC_EPOCHS` consecutive epochs, block promotion of any weight adaptation.

**Why valuable:**  
- `market_fitness_integrator.py` already has a synthetic fallback (`score=0.5, confidence=0.0`).
  Without a constitutional guard, a degraded feed silently degrades fitness scoring for
  indefinite epochs without operator visibility.
- Complements the soulbound_privacy_invariant pattern: both are defensive invariants that
  guard against silent signal degradation.

**Scope:**
- `runtime/market/market_fitness_integrator.py`: expose `consecutive_synthetic_epochs` counter
  on `IntegrationResult`; reset on real reading
- `runtime/governance/constitution.yaml`: new `market_signal_integrity_invariant` BLOCKING rule;
  `MAX_SYNTHETIC_EPOCHS = 5` (operator-configurable via `ADAAD_MARKET_MAX_SYNTHETIC_EPOCHS`)
- Constitution → v0.6.0
- Tests: 10 tests

**Risk:** MEDIUM — new BLOCKING rule could gate valid epochs in environments without a live
market feed. Mitigated by operator-configurable threshold and `is_synthetic` journal events.

---

### Track 11-C — Cross-epoch ledger digest verification

**What:** Add a `verify_replay_digest()` method to `ContextReplayInterface` that validates
the `context_digest` returned at Phase 0c against the current ledger chain hash. If the
chain is tampered since the digest was computed, Phase 0c injection is skipped with a
`context_digest_mismatch.v1` journal event and a constitution audit flag.

**Why valuable:**  
- The Merkle chain in `SoulboundLedger` guarantees tamper evidence but the chain is not
  currently cross-referenced at replay time — an injected digest could be stale or forged.
- Closes the tamper-evidence loop that was left open by the Phase 9 design.

**Scope:**
- `runtime/memory/context_replay_interface.py`: `verify_replay_digest(digest, chain_hash)` method
- `runtime/memory/soulbound_ledger.py`: expose `current_chain_hash()` read method
- `EvolutionLoop` Phase 0c: call `verify_replay_digest()` before applying injection
- New journal event type: `context_digest_mismatch.v1`
- Tests: 8 tests

**Risk:** LOW — verification is read-only; mismatch skips injection (same as `skipped=True` path).

---

### Track 11-D — EpochResult live market score field

**What:** Propagate `live_market_score`, `market_confidence`, and `is_synthetic` from
`MarketFitnessIntegrator.IntegrationResult` into `EpochResult` as observable fields.
Enables downstream Orchestrator and dashboard consumers to react to market signal quality.

**Why valuable:**  
- Currently `MarketFitnessIntegrator.integrate()` fires in Phase 2 and injects into
  `FitnessOrchestrator` but the result is not surfaced to the caller. The `EpochResult`
  that the Orchestrator consumes has no market signal fields.
- Required prerequisite for any dashboard or alerting feature that wants to display
  market signal health.

**Scope:**
- `EpochResult` dataclass: `live_market_score: float = 0.0`, `market_confidence: float = 0.0`,
  `market_is_synthetic: bool = True` fields added
- `EvolutionLoop` run_epoch(): populate fields from Phase 2 `IntegrationResult`
- Tests: 5 tests

**Risk:** VERY LOW — additive fields only; no existing consumers will break.

---

## 3. Recommended sequencing

```
Phase 11 = Track 11-A (bandit selector)        ← closes reward learning loop
Phase 12 = Track 11-D (EpochResult market)     ← low-cost, unblocks dashboard
         + Track 11-C (digest verification)    ← security hardening, low blast radius
Phase 13 = Track 11-B (market integrity)       ← constitutional guard, needs 11-D data
```

Rationale: Track 11-A is the highest leverage item — it converts the passive reward profile
accumulation of Phases 9-10 into an active selection decision. Tracks 11-C and 11-D are
additive and can be combined. Track 11-B requires `consecutive_synthetic_epochs` data from
11-D, so it sequences last.

---

## 4. Phase 11-A detailed 3-PR build plan

### PR-11-A-01: AgentBanditSelector

**New file:** `runtime/autonomy/agent_bandit_selector.py`

```python
# Key interfaces:
@dataclass(frozen=True)
class BanditAgentRecommendation:
    agent: str                # "architect" | "dream" | "beast"
    confidence: float         # UCB1 score or Thompson sample
    strategy: str             # "ucb1" | "thompson"
    exploration_bonus: float  # extra explore_ratio boost from arm uncertainty

class AgentBanditSelector:
    STRATEGIES = ("ucb1", "thompson")
    DEFAULT_STATE_PATH = Path("data/agent_bandit_state.json")

    def recommend(self, *, epoch_id: str) -> BanditAgentRecommendation
    def update(self, *, agent: str, reward: float, epoch_id: str) -> None
    def reset_arm(self, *, agent: str) -> None
    def arm_stats(self) -> Dict[str, Dict[str, Any]]
```

UCB1 formula: `score_i = mean_reward_i + sqrt(2 * ln(total_pulls) / pulls_i)`  
Thompson: beta distribution per arm, sample from `Beta(successes+1, failures+1)`  
Arm state persists to `data/agent_bandit_state.json` via `VersionedMemoryStore`.

**Tests (12):** UCB1 math, Thompson sampling distribution, arm initialization, update,
reset, cold-start (no data → uniform random), state persistence, `LearningProfileRegistry`
integration, JSON state round-trip, boundary conditions.

---

### PR-11-A-02: FitnessLandscape bandit override + EvolutionLoop Phase 0d

**`runtime/evolution/fitness_landscape.py`:**
- `recommended_agent(bandit_rec: Optional[BanditAgentRecommendation] = None) -> str`
- When `bandit_rec` is provided and `confidence ≥ BANDIT_CONFIDENCE_FLOOR = 0.60`:
  return `bandit_rec.agent` (bandit wins)
- Otherwise: retain existing win-rate heuristic

**`runtime/evolution/evolution_loop.py`:**
- Phase 0d inserted between Phase 0c and Phase 1
- `self._bandit_selector: Optional[AgentBanditSelector] = None` (injected via __init__)
- Call `recommend()` → pass to `landscape.recommended_agent(bandit_rec=...)`
- After Phase 5d: call `bandit_selector.update(agent=..., reward=epoch_avg_reward)`

**Tests (5):** bandit confidence floor gating, fallback to win-rate, loop wiring.

---

### PR-11-A-03: Constitution v0.6.0 + v3.6.0 release

**`runtime/governance/constitution.yaml`:** Add `bandit_arm_integrity_invariant`:
- Arm stats must be non-negative (no negative rewards stored)
- No single agent may be recommended for more than `MAX_CONSECUTIVE_BANDIT_EPOCHS = 10`
  consecutive epochs without at least one competing agent being tried

**VERSION:** `3.5.0` → `3.6.0`  
**CONSTITUTION_VERSION:** `0.5.0` → `0.6.0`  
**CHANGELOG:** Phase 11 entry

**Tests (3):** Constitution validator for new rule, consecutive epoch cap, negative reward guard.

---

## 5. Risk register

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| Bandit concentrates on one agent, reducing diversity | MEDIUM | LOW | `MAX_CONSECUTIVE_BANDIT_EPOCHS` constitutional cap; Thompson sampling's natural exploration |
| `LearningProfileRegistry` empty on first Phase 11 epoch | LOW | CERTAIN | Cold-start uniform random recommendation |
| Bandit state file corruption | LOW | LOW | `VersionedMemoryStore` + reset_arm fallback |
| Market integrity invariant (11-B) blocks valid CI runs | MEDIUM | MEDIUM | Operator-configurable `ADAAD_MARKET_MAX_SYNTHETIC_EPOCHS`; default=5 is generous |
| Digest verification (11-C) false mismatch on key rotation | LOW | LOW | Chain hash recalculated from genesis on every rotation; injection skip is safe |

---

## 6. Metrics and evidence gates

| Milestone | Evidence Gate | Target |
|---|---|---|
| PR-11-A-01 merged | AgentBanditSelector UCB1/Thompson unit tests | 12/12 passing |
| PR-11-A-02 merged | No regression in memory/evolution/CF/market suites | 0 new failures |
| PR-11-A-03 merged | Simulated 10-epoch baseline comparison: bandit vs win-rate | `avg_reward` ≥ +5% |
| Phase 11 complete | Full test suite (excl. server/api) | 2421+ passing |

---

## 7. Immediate next actions

1. `git checkout -b phase11/pr-11-a-01` from HEAD (`080643d`)
2. Implement `runtime/autonomy/agent_bandit_selector.py` per the interface spec above
3. Write 12 tests in `tests/autonomy/test_agent_bandit_selector.py`
4. Open PR-11-A-01 against `main`
5. After merge: PR-11-A-02 (FitnessLandscape + Phase 0d wiring)
6. After merge: PR-11-A-03 (Constitution v0.6.0 + v3.6.0 release)

---

*Phase 11 plan document. Track 11-A leads. Constitutional invariants gate every merge.*
