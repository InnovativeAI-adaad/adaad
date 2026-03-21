# PHASE 86 PLAN — Evolution Engine Integration + CompoundEvolutionTracker

**Status:** PROPOSED — awaiting governor ratification (HUMAN-0)
**Author:** Claude (agent) — 2026-03-21
**Baseline:** v9.16.0 · Phase 85 complete · `e4fbbe2`
**Target version:** v9.17.0
**Dependency:** Phase 85 merged ✅

---

## Executive Summary

Phases 81–85 delivered the full evolution reasoning stack:
`ConstitutionalSelfDiscoveryLoop`, `ParetoCompetitionOrchestrator`,
`CausalFitnessAttributor`, `FitnessDecayScorer`, and governance state
sync hardening. **None of these are wired into the live
`ConstitutionalEvolutionLoop` (CEL).** Phase 86 closes that gap.

CEL Step 8 (`FITNESS-SCORE`) currently uses a placeholder stub:
```python
# Phase 64: composite score is derived from sandbox_ok boolean;
# real FitnessEngineV2 integration is a Phase 65+ wiring task.
score = 0.65 if sr.get("sandbox_ok") else 0.0
```

Every promoted mutation since Phase 64 has been scored `0.65` or `0.0`.
Phase 86 replaces this with the full reasoning stack and ships
`CompoundEvolutionTracker` — the originally planned Phase 81 deliverable,
now buildable with the complete infrastructure in place.

---

## Track A — CEL Fitness Wiring (PR-86-01) · v9.17.0

### A1 — Step 8 real fitness scoring

Replace the `0.65` stub in `_step_08_fitness_score` with:

1. `FitnessOrchestrator.score(context)` — real composite score from
   the 5-component weighted regime
2. `FitnessDecayScorer.evaluate(record, current_vector)` — apply
   temporal half-life discount to any historical score reused this epoch
3. `CausalFitnessAttributor.attribute(candidate_id, context)` — compute
   per-op Shapley contributions; store as `state["fitness_attribution"]`

**Wiring contract:**
- `fitness_summary` entries → `(mutation_id, composite_score, decay_coeff,
  attribution_digest)`
- All three calls must be ledger-recorded before `state["fitness_summary"]`
  is written (`STEP8-LEDGER-FIRST-0`)
- Determinism gate: identical `sandbox_results` + identical
  `CodebaseStateVector` → identical `fitness_summary` (`STEP8-DETERM-0`)

### A2 — Step 8.5 (new step) — PARETO-SELECT

Insert new Step 8.5 between existing Steps 8 and 9:

```
Step 8.5 — PARETO-SELECT    Multi-objective Pareto frontier from scored candidates.
                             ParetoCompetitionOrchestrator.run_epoch(candidates).
                             promoted_ids replaces the naive score > 0.5 threshold.
                             Frontier written to ledger (PARETO-GOV-0).
                             state["pareto_frontier_ids"] → consumed by Step 9.
```

**CEL-ORDER-0 impact:** total steps becomes 15; docstring updated; step
numbers ≥ 9 shift by 1. All 14-step tests updated to 15-step contract.

**New invariants:**
- `CEL-PARETO-0`: Pareto selection result written to ledger before Step 9
- `CEL-PARETO-DETERM-0`: identical scored candidates → identical frontier

### A3 — Step 14.5 (post-epoch) — SELF-DISCOVERY hook

Insert `ConstitutionalSelfDiscoveryLoop.run()` as Step 14.5 (post-epoch,
pre-state-advance is wrong — run after Step 14 state advance, outside the
main 15-step sequence, non-blocking):

- Triggered only when `epoch_seq % SELF_DISC_FREQUENCY == 0` (default: 5)
- Failures in this step do not block epoch completion (`CEL-SELF-DISC-NONBLOCK-0`)
- Any ratified invariant candidates written to a `self_discovery_candidates`
  ledger stream; **HUMAN-0 gate required before any candidate is promoted
  to CONSTITUTION.md** (`SELF-DISC-HUMAN-0`)

**New invariants:**
- `CEL-SELF-DISC-0`: Self-discovery runs post-epoch at configured frequency
- `CEL-SELF-DISC-NONBLOCK-0`: Self-discovery failure never blocks epoch
- `SELF-DISC-HUMAN-0`: No self-discovered invariant enters CONSTITUTION.md
  without governor sign-off

### A4 — Tests

| Suite | Count |
|---|---|
| `tests/test_phase86_cel_fitness_wiring.py` | 20–24 |
| `tests/test_phase86_pareto_select_step.py` | 12–15 |
| `tests/test_phase86_self_discovery_hook.py` | 8–10 |

**Total:** ~40–50 new constitutional tests

---

## Track B — CompoundEvolutionTracker (PR-86-02) · v9.17.0

The original Phase 81 planned deliverable. Now buildable: `MultiGenLineageGraph`
(Phase 79), `SeedCompetitionEpochEvent` (Phase 80), `ParetoCompetitionResult`
(Phase 82), and `CausalAttributionReport` (Phase 83) all exist.

### Deliverables

**`runtime/evolution/compound_evolution.py`** — `CompoundEvolutionTracker`:

```python
class CompoundEvolutionTracker:
    """Multi-generation fitness aggregator.

    Synthesises ancestry provenance (MultiGenLineageGraph) with
    competitive epoch outcomes (ParetoCompetitionResult, SeedCompetitionEpochEvent)
    and per-op causal attribution (CausalAttributionReport).

    Invariants:
      COMP-TRACK-0:      compound fitness score deterministic given identical ledger contents
      COMP-ANCESTRY-0:   every compound record traces to a MultiGenLineageGraph node
      COMP-GOV-WRITE-0:  compound record written to ledger before any surface emitted
      COMP-CAUSAL-0:     per-generation causal attribution surfaced in every compound record
    """

    def track_epoch(
        self,
        epoch_id: str,
        pareto_result: ParetoCompetitionResult,
        lineage_graph: MultiGenLineageGraph,
        attributions: Dict[str, CausalAttributionReport],
    ) -> CompoundEvolutionRecord: ...
```

**`schemas/compound_evolution_record.py`** — `CompoundEvolutionRecord`
dataclass with full provenance chain and `record_digest`.

**`tests/test_phase86_compound_evolution.py`** — 20–25 constitutional tests.

**`artifacts/governance/phase86/track_b_sign_off.json`** — governance artifact.

---

## Track C — ROADMAP + Procession Update (PR-86-03 / chore)

- `ROADMAP.md`: Phase 86 entry added; Phase 81 planned entry superseded
- `docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md`: phase86 node added
  as `in_progress` at branch cut
- `pytest.ini`: `phase86` mark registered
- `VERSION`: `9.16.0` → `9.17.0`
- `CHANGELOG.md`: Phase 86 entry

---

## Constitutional Invariants Introduced (Phase 86)

| ID | Requirement |
|---|---|
| `STEP8-LEDGER-FIRST-0` | All fitness calls ledger-recorded before `fitness_summary` written |
| `STEP8-DETERM-0` | Identical sandbox results + codebase state → identical fitness summary |
| `CEL-PARETO-0` | Pareto selection result written to ledger before Step 9 |
| `CEL-PARETO-DETERM-0` | Identical scored candidates → identical Pareto frontier |
| `CEL-SELF-DISC-0` | Self-discovery runs post-epoch at configured frequency |
| `CEL-SELF-DISC-NONBLOCK-0` | Self-discovery failure never blocks epoch completion |
| `SELF-DISC-HUMAN-0` | No self-discovered invariant enters CONSTITUTION.md without HUMAN-0 |
| `COMP-TRACK-0` | Compound fitness score deterministic given identical ledger contents |
| `COMP-ANCESTRY-0` | Every compound record traces to a `MultiGenLineageGraph` node |
| `COMP-GOV-WRITE-0` | Compound record written to ledger before any surface emitted |
| `COMP-CAUSAL-0` | Per-generation causal attribution surfaced in every compound record |

---

## Acceptance Criteria (Gate for v9.17.0)

- [ ] CEL Step 8 calls `FitnessOrchestrator`, `FitnessDecayScorer`,
  `CausalFitnessAttributor`; stub removed
- [ ] CEL Step 8.5 (`PARETO-SELECT`) inserted; `run_epoch()` replaces
  `score > 0.5` threshold; ledger write confirmed
- [ ] `ConstitutionalSelfDiscoveryLoop` fires post-epoch at `epoch_seq % 5 == 0`;
  non-blocking confirmed by test
- [ ] `CompoundEvolutionTracker.track_epoch()` produces deterministic
  `CompoundEvolutionRecord` with ancestry trace
- [ ] All 11 new invariants have corresponding constitutional tests
- [ ] `pytest -m phase86` → 0 failures
- [ ] Governance state drift gate passes clean (`validate_governance_state_drift.py`)

---

## HUMAN-0 Non-Delegable Actions

| Action | Trigger |
|---|---|
| Ratify this plan (governor sign-off) | Before branch creation |
| Review `SELF-DISC-HUMAN-0` policy language | Before PR-86-01 merge |
| GPG tag `v9.17.0` | After all three PRs merged |

---

## Execution Order

```
PR-86-01  feat/phase86-cel-fitness-wiring
  └── Step 8 real scoring · Step 8.5 Pareto · Step 14.5 self-discovery · tests

PR-86-02  feat/phase86-compound-evolution-tracker
  └── CompoundEvolutionTracker · schemas · tests · sign-off artifact

PR-86-03  chore/phase86-close
  └── VERSION 9.17.0 · CHANGELOG · ROADMAP · procession · pytest.ini
```
