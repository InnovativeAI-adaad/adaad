# Phase 67 — Innovations Wiring

**Status:** ✅ shipped (v9.2.0) · **Branch:** `phase67/wire-innovations-into-cel` · **Tests:** T67-VIS-01..04, T67-PER-01..05, T67-PLG-01..05, T67-REF-01..05, T67-INT-01..02

## Summary

Phase 67 wires the deterministic innovation substrate introduced in PR #420 into the live `ConstitutionalEvolutionLoop` lifecycle.  All four innovation injection points are fail-safe (CEL-WIRE-FAIL-0) and additive — the 14-step CEL sequence (CEL-ORDER-0) is never altered.

---

## Injection Points

### 1. Vision Mode — Step 4 (PROPOSAL-GENERATE)

**Invariant:** INNOV-VISION-0

Before `ProposalEngine.generate()` is called, `ADAADInnovationEngine.run_vision_mode()` forecasts the next `VISION_HORIZON` (100) epochs using event history stored in `state["oracle_events"]`.

The projection is written to `state["vision_projection"]` and surfaced in the Step 4 detail block:
```json
{
  "horizon_epochs": 100,
  "trajectory_score": 0.25,
  "projected_capabilities": ["oracle", "story_mode"],
  "dead_end_paths": []
}
```

**Fail-safe:** if `run_vision_mode` raises, the step continues with `vision_projection: {}`.

---

### 2. Mutation Personality — Step 4 (PROPOSAL-GENERATE)

**Invariant:** INNOV-PERSONA-0

Immediately after Vision Mode, `select_personality()` deterministically selects one of three persisted personality profiles (Architect, Dream, Beast) for the epoch. Profiles are loaded from `data/personality_profiles.json` via `PersonalityProfileStore`, with deterministic defaults used only when no persisted file exists. The selected philosophy (`minimalist` / `exploratory` / `aggressive`) is injected into the `ProposalRequest` context so the proposal engine may reflect it in strategy metadata.

The active personality is written to `state["active_personality"]` and the Step 4 detail block. A deterministic epoch usage record is also upserted in `data/persona_epoch_records.jsonl`.

**Default profiles:**

| Agent | Philosophy | Vector |
|-------|-----------|--------|
| architect | minimalist | (0.9, 0.2, 0.3, 0.1) |
| dream | exploratory | (0.6, 0.8, 0.4, 0.2) |
| beast | aggressive | (0.5, 0.5, 0.9, 0.8) |

**Fail-safe:** if `select_personality` raises, the step continues with `active_personality: {}`.

---


### 2b. Personality Impact Persistence — Step 10 (GOVERNANCE-GATE)

After GovernanceGate/G-Plugin outcomes are known, `record_personality_impact()` writes deterministic epoch-level persona impact records. Impact data includes:

- selected persona and philosophy
- strategy id for the epoch
- win/loss outcome tied to promotion result
- aggregate epoch impact score from `fitness_summary`
- vector delta (`vector_before` → `vector_after`)
- revision/win/loss counters in `data/personality_profiles.json`

The calculated impact is stored in `state["personality_impact"]` and included in Step 10 detail output.

### 3. Governance Plugins — Step 10 (GOVERNANCE-GATE)

**Invariants:** GPLUGIN-BLOCK-0, GPLUGIN-POST-0

G-plugins run **after** `GovernanceGate.approve_mutation()` approves each candidate.  A GovernanceGate rejection short-circuits before any plugin sees the mutation.

For each approved mutation, all registered `GovernancePlugin` instances evaluate the mutation payload.  If any plugin returns `passed=False`, the mutation is removed from `mutations_succeeded` and Step 10 returns `BLOCKED` with `reason="gplugin_rejection"`.

Plugin results are written to `state["gplugin_outcomes"]` and the Step 10 detail block.

**Example plugins bundled (from `runtime.innovations`):**
- `NoNewDependenciesPlugin` — blocks mutations that declare new dependencies
- `DocstringRequiredPlugin` — blocks mutations with missing docstrings

**Fail-safe:** if the engine crashes, `run_gplugins` returns `[]` (no block), logs WARNING.

---

### 4. Self-Reflection — Step 14 (STATE-ADVANCE)

**Invariant:** INNOV-REFLECT-0

Every `REFLECTION_CADENCE` (100) epochs, `ADAADInnovationEngine.self_reflect()` analyses agent score distributions and emits a `ReflectionReport`.

The report is written to `state["reflection_report"]` and merged into the Step 14 detail block:
```json
{
  "epoch_id": "epoch-200",
  "dominant_agent": "architect",
  "underperforming_agent": "beast",
  "rebalance_hint": "rebalance bandit weights",
  "cadence": 100
}
```

Between cadence ticks, no report is produced and Step 14 runs identically to the Phase 65 base.

**Fail-safe:** if `self_reflect` raises, Step 14 returns the unmodified base result.

---

## New Files

| File | Purpose |
|------|---------|
| `runtime/innovations_wiring.py` | Adapter module: vision/persona/plugin/reflection + impact persistence |
| `tests/test_innovations_wiring.py` | 21+ tests covering injection points + persisted personality regressions |
| `runtime/personality_profiles.py` | Deterministic profile store (`data/personality_profiles.json`, `data/persona_epoch_records.jsonl`) |
| `docs/INNOVATIONS_WIRING.md` | This document |

## Modified Files

| File | Change |
|------|--------|
| `runtime/evolution/cel_wiring.py` | Imports; `LiveWiredCEL.__init__` new params; Step 4/10/14 overrides |
| `runtime/__init__.py` | Exports wiring helpers |

---

## Constitutional Invariant Index

| Invariant | Description | Status |
|-----------|-------------|--------|
| CEL-ORDER-0 | 14-step sequence unaltered | ✅ |
| CEL-WIRE-FAIL-0 | Innovation hooks are fail-safe | ✅ |
| GPLUGIN-BLOCK-0 | Plugin failure blocks promotion | ✅ |
| GPLUGIN-POST-0 | Plugins evaluate after GovernanceGate only | ✅ |
| INNOV-DETERM-0 | All innovation computations deterministic | ✅ |
| INNOV-VISION-0 | Vision Mode injected pre-proposal | ✅ |
| INNOV-PERSONA-0 | Personality selection injected pre-proposal | ✅ |
| INNOV-REFLECT-0 | Self-reflection on cadence, post-advance | ✅ |

---

## Upgrade Path

```python
# Minimal: opt-in with no plugins (vision + personality only)
from runtime.evolution.cel_wiring import LiveWiredCEL
from runtime.innovations import ADAADInnovationEngine

cel = LiveWiredCEL(innovations_engine=ADAADInnovationEngine())

# Full: all four injection points active
from runtime.innovations import (
    ADAADInnovationEngine, NoNewDependenciesPlugin, DocstringRequiredPlugin
)

cel = LiveWiredCEL(
    innovations_engine=ADAADInnovationEngine(),
    gplugins=[NoNewDependenciesPlugin(), DocstringRequiredPlugin()],
)
result = cel.run_epoch(epoch_id="epoch-001", context={"oracle_events": [...]})
```
