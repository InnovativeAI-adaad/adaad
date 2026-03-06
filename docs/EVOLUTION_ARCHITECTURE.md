# ADAAD Evolution Architecture — v2.0

> **Status:** Production-Ready | **Updated:** 2026-03-06

This document describes the complete AI mutation capability pipeline introduced
in the v2.0 principal-engineer capability expansion.

---

## Component Topology

```
                    ┌─────────────────────────────────────────────────┐
                    │              EVOLUTION LOOP                      │
                    │         run_epoch(CodebaseContext)               │
                    │  Phase0:Strategy → Phase1:Propose → Phase2:Seed │
                    │  Phase3:Evolve → Phase4:Adapt → Phase5:Record   │
                    │  → EpochResult                                   │
                    └────────────┬─────────────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                       ▼
  ┌──────────────────┐  ┌────────────────────┐  ┌──────────────────┐
  │  AI MUTATION     │  │   POPULATION        │  │ FITNESS          │
  │  PROPOSER        │  │   MANAGER           │  │ LANDSCAPE        │
  │                  │  │                     │  │                  │
  │ ARCHITECT ───────┼─▶│ seed(candidates)    │  │ win_rate/type    │
  │ DREAM     ───────┼─▶│ evolve_generation() │  │ plateau detect   │
  │ BEAST     ───────┘  │ crossover()         │  │ agent recommend  │
  │                     │ diversity_enforce() │  └──────────────────┘
  │ CodebaseContext      └────────────────────┘           │
  │ context_hash()                │                        │
  └──────────────────┐            │                        │
                     │            ▼                        ▼
              ┌──────▼──────────────────────────────────────────────┐
              │           WEIGHT ADAPTOR                             │
              │  adapt(outcomes) → new ScoringWeights per epoch     │
              │  momentum velocity | prediction_accuracy rolling     │
              └──────────────────────────────────────────────────────┘
                                   │
                                   ▼
              ┌──────────────────────────────────────────────────────┐
              │          MUTATION SCAFFOLD v2                         │
              │  ScoringWeights (adaptive)  | MutationLineage DAG    │
              │  PopulationState            | Dynamic threshold       │
              │  Elitism bonus              | Epoch binding           │
              └──────────────────────────────────────────────────────┘
```

---

## Epoch Lifecycle

| Phase | Action | Output |
|---|---|---|
| **0: Strategy** | `FitnessLandscape.recommended_agent()` | agent preference string |
| **1: Propose** | `propose_from_all_agents()` → Claude API | `list[MutationCandidate]` × 3 agents |
| **2: Seed** | `PopulationManager.seed()` — dedup + cap at 12 | Diverse population |
| **3: Evolve** | N generations: score → elites → crossover → advance | `list[MutationScore]` per gen |
| **4: Adapt** | `WeightAdaptor.adapt(outcomes)` — momentum descent | Updated `ScoringWeights` |
| **5: Record** | `FitnessLandscape.record()` — win/loss per type | Persistent JSON state |
| **Return** | `EpochResult` dataclass | Consumed by Orchestrator |

---

## File Map

| File | Type | Lines | Purpose |
|---|---|---|---|
| `runtime/autonomy/mutation_scaffold.py` | MODIFIED | +120 | ScoringWeights, PopulationState, lineage, adaptive threshold |
| `runtime/autonomy/ai_mutation_proposer.py` | NEW | 198 | Claude API integration, 3 agent personas |
| `runtime/autonomy/weight_adaptor.py` | NEW | 122 | Momentum weight learning, JSON persistence |
| `runtime/autonomy/fitness_landscape.py` | NEW | 100 | Win/loss tracking, plateau detection |
| `runtime/evolution/population_manager.py` | NEW | 130 | GA: BLX crossover, elitism, diversity |
| `runtime/evolution/evolution_loop.py` | NEW | 110 | Full epoch orchestration, EpochResult |
| `adaad/core/health.py` | FIXED | +4 | gate_ok added (PR #12) |

---

## Adaptive Scoring Formulas

### Acceptance Threshold

```
adjusted_threshold = base_threshold × (1.0 - diversity_pressure × 0.4)

Examples:
  diversity_pressure = 0.0 (exploit): threshold = 0.25  (unchanged)
  diversity_pressure = 0.5 (balanced): threshold = 0.20
  diversity_pressure = 1.0 (explore): threshold = 0.15
```

### Elitism Bonus

```
if candidate.parent_id in population_state.elite_ids:
    score += 0.05  (clamped to 1.0)
```

Applied AFTER threshold adjustment — elites compare against the adjusted bar.

### Weight Adaptation (Momentum)

```
velocity[dim] = 0.85 × velocity[dim] + 0.05 × error_signal
new_weight[dim] = clamp(current + velocity[dim], min=0.05, max=0.70)

prediction_accuracy = 0.3 × epoch_accuracy + 0.7 × previous_accuracy
```

### BLX-Alpha Crossover (α=0.5)

```
lo, hi = min(a,b), max(a,b)
extent = (hi - lo) × 0.5
child_value ~ Uniform(lo - extent, hi + extent)
```

---

## Agent Specialisation

| Agent | System Prompt Focus | Expected gain | Risk | mutation_type |
|---|---|---|---|---|
| **Architect** | Structural cohesion, interface contracts, coupling | 0.3–0.6 | 0.1–0.4 | `structural` |
| **Dream** | Novelty, breadth, cross-domain, experimental | 0.5–0.9 | 0.4–0.8 | `experimental` |
| **Beast** | Conservative, measurable, micro-optimisation | 0.2–0.5 | 0.05–0.2 | `performance`/`coverage` |

---

## Plateau Detection & Agent Selection

```python
# Plateau: all types with >= 3 attempts below 20% win rate
if is_plateau():       return 'dream'        # Maximum exploration
if best == structural: return 'architect'    # Exploit structural wins
if best in (perf,cov): return 'beast'        # Exploit safe wins
else:                  return 'beast'        # Conservative default
```

### Phase 2 Extension: Bandit Selector (UCB1 / Thompson Sampling)

```python
# UCB1 per agent:
score(agent) = win_rate(agent) + sqrt(2 × log(total_pulls) / pulls(agent))

# Thompson Sampling alternative:
sample from Beta(successes+1, failures+1) per agent
select agent with highest sample
```

---

## Measurable Success Criteria

| Metric | Target | Measurement |
|---|---|---|
| New test pass rate | 44/44 (100%) | `pytest tests/test_*.py` |
| Existing test regressions | 0 | `pytest tests/test_orchestrator_replay_mode.py` |
| Weight prediction accuracy | > 0.60 by epoch 5 | `WeightAdaptor.prediction_accuracy` |
| Weight bounds | All in [0.05, 0.70] | `ScoringWeights` field assertions |
| Plateau detection | `True` when all < 20% | `FitnessLandscape.is_plateau()` |
| BLX crossover validity | 100% in range | `population_manager.py::test_crossover_child_in_blx_range` |
| gate_ok presence | Always in health payload | `test_pr12_gate_ok.py` |
| Epoch duration | < 45s with real API | `EpochResult.duration_seconds` |
| Mutation acceptance rate | 0.20–0.60 | `accepted_count / total_candidates` |

---

## System-Level Health Indicators (after 10 live epochs)

| Indicator | Formula | Healthy Range |
|---|---|---|
| Acceptance rate | `accepted / total_candidates` | 0.20–0.60 |
| Weight accuracy | `WeightAdaptor.prediction_accuracy` | > 0.55 by epoch 10 |
| Plateau frequency | `is_plateau()` triggers | < 2 per 10 epochs |
| Agent distribution | Proposals per agent | Balanced unless landscape biased |
| Crossover utilisation | Children in pop / total pop | 0.05–0.25 |
| Epoch duration trend | `avg(duration_seconds)` over 5 epochs | Stable or decreasing |

---

## Extension Roadmap

| Phase | Feature | Module |
|---|---|---|
| 2 | Bandit agent selector (UCB1/Thompson) | `runtime/autonomy/bandit_selector.py` |
| 2 | Semantic mutation diff engine (AST-based risk scoring) | `runtime/autonomy/semantic_diff.py` |
| 3 | Cross-agent synthesis pipeline (Arch→Dream→Beast chain) | `runtime/evolution/synthesis_pipeline.py` |
| 3 | Cryovant epoch snapshot/restore integration | `runtime/cryovant/snapshot.py` |
| 4 | Real test coverage binding (`pytest --cov` delta) | `runtime/testing/coverage_runner.py` |
| 4 | Auto-context builder (AST + git history extraction) | `runtime/autonomy/context_builder.py` |
