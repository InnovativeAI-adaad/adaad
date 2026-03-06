# ADAAD Roadmap

> **Constitutional principle:** Every item on this roadmap must be approved by ArchitectAgent before implementation, governed by the mutation pipeline before merge, and evidenced in the release notes before promotion.

---

## What ships today — v2.3.0

The self-improving loop is live. Three AI agents compete. The fittest mutations survive. Weights adapt. Evidence is permanent.

| Subsystem | Status | Description |
|-----------|--------|-------------|
| `AIMutationProposer` | ✅ shipped | Claude API connected — Architect / Dream / Beast personas |
| `EvolutionLoop` | ✅ shipped | 5-phase epoch orchestrator, `EpochResult` dataclass |
| `WeightAdaptor` | ✅ shipped | Momentum-descent scoring weight adaptation (`LR=0.05`) |
| `FitnessLandscape` | ✅ shipped | Per-type win/loss ledger, plateau detection |
| `PopulationManager` | ✅ shipped | BLX-alpha GA, MD5 deduplication, elite preservation |
| `BanditSelector` | ✅ shipped | UCB1 multi-armed bandit agent selection (Phase 2) |
| `EpochTelemetry` | ✅ shipped | Append-only analytics engine, health indicators |
| MCP Evolution Tools | ✅ shipped | 5 read-only observability endpoints for the pipeline |
| `GovernanceGate` | ✅ shipped | Constitutional authority — the only surface that approves mutations |
| Evidence Ledger | ✅ shipped | Append-only, SHA-256 hash-chained, replay-proof |
| Deterministic Replay | ✅ shipped | Every decision byte-identical on re-run; divergence halts |

---

## Phase 3 — Adaptive Penalty Weights

**Status:** ✅ shipped (v2.1.0)

Currently `risk_penalty` (0.20) and `complexity_penalty` (0.10) are static. Phase 3 makes them adaptive by harvesting post-merge telemetry:

- **`WeightAdaptor` Phase 2 unlock** — Extend momentum-descent to include `risk_penalty` and `complexity_penalty` using post-merge outcome data from the evidence ledger.
- **Telemetry feedback loop** — `EpochTelemetry` drives weight adjustments: if high-risk mutations consistently underperform, `risk_penalty` climbs; if complexity is rarely determinative, it decays.
- **Thompson Sampling activation** — `ThompsonBanditSelector` (already implemented, not yet wired) activates as an alternative to UCB1 when non-stationary reward is detected across ≥30 epochs.
- **Gate:** ArchitectAgent approval + `≥30 epoch` data requirement before Phase 2 weight activation.

**Acceptance criteria:**
- `risk_penalty` and `complexity_penalty` in `[0.05, 0.70]` bounds at all times
- Weight trajectory stored in telemetry for every epoch
- `WeightAdaptor.prediction_accuracy > 0.60` by epoch 20

---

## Phase 4 — Semantic Mutation Diff Engine

**Target:** v2.2.0 ✅ · Requires: Phase 3 shipped

Replace the heuristic complexity/risk scoring with AST-aware semantic analysis:

- **`SemanticDiffEngine`** (`runtime/autonomy/semantic_diff.py`) — AST-based mutation diff: counts node insertions/deletions, detects control-flow changes, measures cyclomatic complexity delta.
- **Risk scoring upgrade** — Replace `mutation_risk_scorer.py`'s regex heuristics with semantic parse-tree analysis. Score is now: `(ast_depth_delta × 0.3) + (cyclomatic_delta × 0.4) + (import_surface_delta × 0.3)`.
- **Lineage confidence scoring** — Mutations that are semantically close to previous accepted mutations get a lineage bonus; semantically novel mutations get an exploration bonus.
- **Gate:** Requires semantic diff to produce identical scores on identical AST inputs (determinism CI job).

---

## Phase 5 — Multi-Repo Federation

**Target:** v3.0.0 · Requires: Phase 4 shipped + stable federation key infrastructure

Extend ADAAD from single-repo mutation to governed cross-repo evolution:

- **Federation broker upgrade** — `FederatedSignalBroker` moves from read-only signal ingestion to governed mutation propagation: accepted mutations in one repo can propose downstream changes in dependent repos.
- **Cross-repo lineage** — `LineageLedgerV2` extended with `federation_origin` field; mutations carry their source-repo epoch chain.
- **Federated evidence matrix** — Release evidence must include cross-repo determinism verification before any federated mutation is accepted.
- **Constitutional requirement** — A federated mutation requires GovernanceGate approval in BOTH source and destination repos.

---

## Phase 6 — Autonomous Roadmap Self-Amendment

**Target:** v3.1.0 · Pioneering tier

The mutation engine proposes amendments to this roadmap itself:

- ADAAD runs an evolution epoch against the codebase and roadmap simultaneously.
- If the Architect agent identifies that Phase N+1 prerequisites are met and Phase N targets were achieved, it proposes a `ROADMAP.md` mutation advancing the milestone.
- The mutation is governed like any other: GovernanceGate, constitutional compliance, replay proof.
- A human governance sign-off is required for any roadmap mutation — the system cannot self-promote without human approval.

This closes the loop: ADAAD evolves its own evolution plan, under the same constitutional constraints it applies to every other change.

---

## Measurement targets

| Milestone | Metric | Target |
|-----------|--------|--------|
| Phase 3 activation | `prediction_accuracy` | > 0.60 by epoch 20 |
| Phase 3 activation | Acceptance rate | 0.20–0.60 stable |
| Phase 4 semantic diff | Scoring determinism | 100% identical on identical AST |
| Phase 5 federation | Cross-repo divergence | 0 divergences per federated epoch |
| All phases | Evidence matrix | 100% Complete before promotion |
| All phases | Replay proofs | 0 divergences in CI |

---

## What will not be built

To maintain constitutional clarity:

- **No autonomous promotion** — The pipeline never promotes a mutation to production without human sign-off. GovernanceGate cannot be delegated.
- **No non-deterministic entropy** in governance decisions — Randomness is only allowed in agent proposals (seeded from epoch_id), never in scoring or gate evaluation.
- **No retroactive evidence** — Evidence cannot be added after a release is tagged.
- **No silent failures** — Every pipeline halt produces a named failure mode in the evidence ledger.

---

*This roadmap is governed by `docs/CONSTITUTION.md` and `docs/governance/ARCHITECT_SPEC_v2.0.0.md`. Amendments require ArchitectAgent approval and a CHANGELOG entry.*
