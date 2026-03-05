# EPIC 2 · Policy Simulation DSL

![Status: Complete](https://img.shields.io/badge/Status-Complete-2ea043)
![Milestone: ADAAD-8](https://img.shields.io/badge/Milestone-ADAAD--8-2ea043)
![Version: v1.2](https://img.shields.io/badge/Version-v1.2-2ea043)

> Declarative governance sandbox — hypothetical constraints evaluated against historical epochs, with zero live governance side effects.

**Last reviewed:** 2026-03-05 · **Merged:** 2026-03-05 · **PRs:** PR-10 → PR-13

---


## Problem Statement

Governance constraints in ADAAD are set once, enforced continuously, and evolved only through the constitutional amendment process. The cost of discovering that a proposed constraint carries catastrophic velocity impact is incurring that impact in production after the amendment has landed.

Non-technical stakeholders — compliance teams, product owners, external auditors — have no mechanism to reason about governance tradeoffs without touching live policy or internalizing the constitutional evaluation engine.

This makes governance tuning an expert-only activity, even though the people most accountable for governance outcomes are often not the people with implementation access.

---

## Architecture Framing

This is not a debugger or a test harness. It is a **declarative governance sandbox** — a surface where hypothetical constraints can be expressed in plain language and their consequences measured against the ledger before any amendment is filed.

The foundational insight: ADAAD already possesses everything the simulation layer needs — an append-only ledger, a constitutional evaluation engine, a strict replay substrate, and epoch-level fitness scores. The simulation layer is a governed evaluation skin over existing infrastructure, not a parallel execution engine.

```
hypothetical constraint (DSL expression or UI toggles)
              │
              ▼
constraint interpreter  →  SimulationPolicy (simulation=true, no side-effect paths)
              │
              ▼
replay engine (historical epochs, read-only substrate)
              │
              ▼
simulated evaluation results per epoch
              │
              ├─▶ velocity impact report
              ├─▶ drift risk analysis
              ├─▶ mutation block/pass delta vs. actual history
              └─▶ governance health score
```

**The isolation invariant is architectural, not conventional.** `SimulationPolicy.simulation = True` is checked at the `GovernanceGate` boundary before any ledger write, constitution state transition, or mutation execution. No simulated constraint can reach a live governance surface.

---

## Goal

Deliver a declarative simulation language and Aponi UI that allow operators and non-technical stakeholders to express hypothetical governance constraints, replay them against historical epochs, and measure tradeoffs before any live policy is amended.

---

## Deliverables

**D1 — DSL Grammar** · `runtime/governance/simulation/dsl_grammar.py`
A bounded constraint expression language. Grammar version-locked at 10 core constraint types for v1.3; semantic versioning governs any future grammar extensions.

| Constraint Type | Example Expression | Semantics |
|---|---|---|
| Approval threshold | `require_approvals(tier=PRODUCTION, count=3)` | Minimum reviewer count per tier |
| Risk ceiling | `max_risk_score(0.4)` | Gate mutations above a fitness risk threshold |
| Mutation rate ceiling | `max_mutations_per_epoch(10)` | Hard ceiling on candidates advanced per epoch |
| Complexity delta ceiling | `max_complexity_delta(0.15)` | Constitutional rule parameter override |
| Tier lockdown | `freeze_tier(PRODUCTION, reason="audit period")` | Suspend promotion to a tier for a window |
| Dependency rule assertion | `require_rule(lineage_continuity, severity=BLOCKING)` | Assert rule is active at minimum severity |
| Coverage floor | `min_test_coverage(0.80)` | Minimum coverage threshold before promotion |
| Entropy cap | `max_entropy_per_epoch(0.30)` | Per-epoch entropy ceiling for simulation |
| Reviewer count escalation | `escalate_reviewers_on_risk(threshold=0.6, count=2)` | Dynamic reviewer count based on risk score |
| Lineage depth requirement | `require_lineage_depth(min=3)` | Minimum ancestor chain depth for promotion |

Each constraint type has a UI toggle equivalent in Aponi — non-technical stakeholders can drive simulation without writing DSL directly.

**D2 — Constraint Interpreter** · `runtime/governance/simulation/constraint_interpreter.py`
Parses DSL expressions into a `SimulationPolicy` object structurally compatible with the existing `GovernanceGate` evaluation interface. `simulation=True` is set at construction and enforced at the `GovernanceGate` boundary before any state-affecting operation. Malformed expressions raise `SimulationDSLError` with the offending token and position.

**D3 — Epoch Replay Simulator** · `runtime/governance/simulation/epoch_simulator.py`
Integrates with the existing `ReplayEngine` as a read-only substrate. Re-evaluates historical epochs under a `SimulationPolicy` and returns a structured result per epoch:

```python
@dataclass
class EpochSimulationResult:
    epoch_id: str
    actual_mutations_advanced: int
    simulated_mutations_advanced: int
    blocked_by_simulation: list[str]      # mutation IDs gated under hypothetical policy
    velocity_delta_pct: float             # (simulated − actual) / actual
    drift_risk_delta: float               # drift risk score delta under simulation
    governance_health_score: float        # composite score for this epoch under simulation
```

**D4 — Aponi Policy Simulation Mode** · `ui/aponi_dashboard.py` + new endpoints

Two endpoints introduced:
- `POST /simulation/run` — accepts `{dsl_text, epoch_range}` or `{constraints: [...], epoch_range}`; returns `SimulationRunResult`
- `GET /simulation/results/{run_id}` — retrieves a completed simulation run by ID

Aponi UI surface:
- Constraint builder panel (toggle UI that emits equivalent DSL expressions)
- Epoch range selector (respects platform `max_epoch_range` limit)
- Results view: velocity impact chart · drift risk chart · mutation block/pass heatmap per epoch · governance health score timeline (actual vs. simulated)
- Export control (surfaces D5)
- **Mandatory "SIMULATION ONLY" badge** on all result views — prominent, non-dismissible

**D5 — Exportable Governance Profiles** · `runtime/governance/simulation/profile_exporter.py`
Exports a completed simulation run as a self-contained `GovernanceProfile` artifact. Profiles are deterministic: identical ledger slice + identical `SimulationPolicy` + epoch-bound scoring versions → identical profile.

```json
{
  "schema_version": "governance_profile.v1",
  "simulation": true,
  "generated_at": "...",
  "epoch_range": { "start": "...", "end": "..." },
  "simulation_policy": { ... },
  "summary": {
    "epochs_evaluated": 0,
    "velocity_impact_pct": 0.0,
    "mutations_gated": 0,
    "drift_risk_delta_mean": 0.0,
    "governance_health_score_mean": 0.0
  },
  "epoch_results": [ ... ],
  "scoring_versions": {
    "fitness": "...",
    "risk": "..."
  }
}
```

---

## Isolation and Replay Invariants (Required)

- `SimulationPolicy.simulation = True` must be enforced at the `GovernanceGate` boundary; caller convention is insufficient.
- Simulation runs must instantiate:
  - ephemeral lineage ledger,
  - ephemeral entropy ledger,
  - isolated policy evaluation context.
- No shared mutable runtime structures are allowed between simulation and live governance execution (including caches, counters, and singleton state).
- Simulation state is discarded after run completion; only explicit simulation artifacts/events persist.
- Simulation must bind to the `scoring_algorithm_version` recorded in each replayed epoch when evaluating risk/fitness-dependent constraints.
- `SimulationResult` and exported `GovernanceProfile` must include scoring-version metadata used during replay.
- Identical ledger slice + identical `SimulationPolicy` + identical epoch-scoped scoring versions must produce identical simulation results and exported profiles.

---

## Acceptance Criteria

- [ ] DSL governs at least 10 core constraint types covering approval thresholds, risk ceilings, rate limits, complexity deltas, tier lockdowns, and dependency assertions
- [ ] `SimulationPolicy.simulation = True` is architecturally enforced at the `GovernanceGate` boundary; it cannot be bypassed by calling internal evaluation methods directly
- [ ] Simulation isolation is verified by `tests/governance/test_simulation_isolation.py` — zero ledger writes, zero constitution state transitions, zero mutation executor calls during any simulation run
- [ ] Simulation produces deterministic results: identical ledger slice + identical `SimulationPolicy` + epoch-scoped scoring versions → identical `SimulationResult`
- [ ] `python -m app.main --replay strict` can replay simulation runs from their recorded inputs without re-running live epoch evaluation
- [ ] Aponi simulation endpoints are read-only (POST for simulation runs with zero side effects; GET for retrieval); both are bearer-auth gated and covered in `tests/test_server_audit_endpoints.py`
- [ ] Exported governance profiles pass schema validation against `schemas/governance_profile.v1.json`; `simulation: true` field is always present and schema-enforced
- [ ] Velocity and drift impact results surface at epoch-level granularity in Aponi
- [ ] `tools/lint_determinism.py` governs all modules under `runtime/governance/simulation/`
- [ ] CHANGELOG entry promoted under `[Unreleased]`

---

## Execution Plan

**Phase 1 — Grammar and Interpreter (no UI; foundation for all subsequent phases)**
1. Deliver `runtime/governance/simulation/dsl_grammar.py` with parser for 10 initial constraint types and `SimulationDSLError` for malformed input
2. Deliver `runtime/governance/simulation/constraint_interpreter.py` — DSL → `SimulationPolicy` with `simulation=True` enforced at construction
3. Ship `tests/governance/test_simulation_dsl.py` covering: parse + interpret for all 10 types, malformed expression rejection, `simulation=True` presence assertion
4. Introduce `schemas/governance_simulation_policy.v1.json`

**Phase 2 — Epoch Simulator**
5. Deliver `runtime/governance/simulation/epoch_simulator.py` wired to the existing `ReplayEngine` as a read-only substrate
6. Ship `tests/governance/test_epoch_simulator.py` — determinism tests, simulation isolation tests, and scoring-version binding assertions
7. Ship `tests/governance/test_simulation_isolation.py` — explicitly asserts `simulation=True` is checked at `GovernanceGate` boundary before any state-affecting call

**Phase 3 — Aponi Integration**
8. Wire `POST /simulation/run` and `GET /simulation/results/{run_id}` endpoints
9. Extend audit endpoint test suite to cover both simulation endpoints
10. Surface constraint builder panel and results view in Aponi dashboard

**Phase 4 — Profile Export**
11. Deliver `runtime/governance/simulation/profile_exporter.py`
12. Introduce `schemas/governance_profile.v1.json` with `simulation: true` as a required field and scoring-version metadata requirements
13. Wire export control to Aponi results view
14. Ship export tests confirming deterministic profile generation and scoring-version metadata presence

---

## Risk Register

| Risk | Mitigation |
|---|---|
| Simulation isolation broken by shared mutable state in evaluation engine | Enforce `simulation=True` at `GovernanceGate` boundary; ship explicit isolation assertion tests |
| Long epoch ranges produce expensive simulations on Pydroid3/Android | Enforce configurable `max_epoch_range`; default 50 epochs on Linux, 10 on Android; surface limit in API docs |
| DSL grammar scope creep over time | Grammar version-locked at 10 types for v1.3; extensions require a versioned grammar PR with governance-impact label |
| Stakeholders mistake simulation results for live policy guarantees | "SIMULATION ONLY" badge is mandatory and non-dismissible on all result views; `simulation: true` is schema-enforced in all exported profiles |
| Sparse ledgers produce sparse simulation coverage | Emit `simulation_insufficient_history` warning when epoch coverage falls below threshold; document minimum ledger depth for meaningful results |
| Risk-model refactors cause retroactive simulation drift | Bind simulation to epoch-scoped scoring algorithm versions and export scoring-version metadata in all simulation artifacts |

---

## Governance Lineage

- `runtime/governance/constitution.yaml` — live policy that simulation contrasts against; never mutated by simulation runs
- `runtime.evolution.replay_attestation` — replay substrate that simulation builds on
- `tests/governance/test_governance_simulation_harness.py` — existing simulation harness tests; extend rather than retire
- `tools/simulate_governance_harness.py` — existing CLI tool; DSL integration extends this surface
- Epic 1 (Reviewer Reputation) — reputation data must be available as a simulation variable: "what if 3 reviewers had been required instead of 2 across these epochs?"
- Epic 3 (Aponi-as-IDE) — simulation mode is a foundational capability for inline governance linting and policy preview in the IDE surface
