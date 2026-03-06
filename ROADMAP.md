# ADAAD Roadmap

> **Constitutional principle:** Every item on this roadmap must be approved by ArchitectAgent before implementation, governed by the mutation pipeline before merge, and evidenced in the release notes before promotion.

---

## What ships today — v3.0.0

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

**Status:** ✅ shipped (v3.0.0)

Extends ADAAD from single-repo mutation to governed cross-repo evolution:

- **HMAC Key Validation (M-05)** — `key_registry.py` enforces minimum-length key at boot; fail-closed on absent key material.
- **Cross-repo lineage** — `LineageLedgerV2` extended with `federation_origin` field; mutations carry their source-repo epoch chain.
- **FederationMutationBroker** — Governed cross-repo mutation propagation; GovernanceGate approval required in BOTH source and destination repos.
- **FederatedEvidenceMatrix** — Cross-repo determinism verification gate; `divergence_count == 0` required before promotion.
- **EvolutionFederationBridge + ProposalTransportAdapter** — Lifecycle wiring for broker and evidence matrix within `EvolutionRuntime`.
- **Federated evidence bundle** — Release gate output includes `federated_evidence` section; non-zero divergence_count blocks promotion.
- **Federation Determinism CI** — `.github/workflows/federation_determinism.yml` enforces 0-divergence invariant on every PR touching federation paths.
- **HMAC key rotation runbook** — `docs/runbooks/hmac_key_rotation.md` operational documentation.

---

## Phase 6 — Autonomous Roadmap Self-Amendment

**Status:** 🟡 active · **Target:** v3.1.0 · Promoted from backlog: 2026-03-06

The mutation engine proposes amendments to this roadmap itself. Phase 5 delivery
confirms the constitutional and determinism infrastructure required for this
capability is now in place.

**Constitutional principle:** ADAAD proposes. Humans approve. The roadmap never
self-promotes without a human governor sign-off recorded in the governance ledger.

---

### M6-01 — RoadmapAmendmentEngine ✅ shipped (v3.1.0-dev)

`runtime/autonomy/roadmap_amendment_engine.py`

Governed propose → approve → reject → verify_replay lifecycle for ROADMAP.md
amendments. Authority invariants:

- `authority_level` hardcoded to `"governor-review"` — injection blocked
- `diff_score ∈ [0.0, 1.0]` enforced; scoring penalises deferred/cancelled milestones
- `lineage_chain_hash = SHA-256(prior_roadmap_hash:content_hash)` on every proposal
- `DeterminismViolation` on replay hash divergence — proposal halts immediately
- `GovernanceViolation` on short rationale (< 10 words) or invalid milestone status

**Acceptance criteria:**
- ≥85% test pass rate across 22 replay scenarios: **✅ 100%**
- JSON round-trip produces identical content_hash: **✅**
- Double-approval by same governor rejected: **✅**
- Terminal status blocks further transitions: **✅**

---

### M6-02 — ProposalDiffRenderer ✅ shipped (v3.1.0-dev)

`runtime/autonomy/proposal_diff_renderer.py`

Renders `RoadmapAmendmentProposal` as structured Markdown diff for:
- GitHub PR description auto-population
- Aponi IDE evidence viewer (D4 integration)
- Governance audit bundle output

Output sections: header + score bar, lineage fingerprints, rationale, milestone
delta table, governance status, phase transition log.

---

### M6-03 — EvolutionLoop integration 🔵 proposed

Wire `RoadmapAmendmentEngine.propose()` into the Phase 5 epoch orchestrator so
that after every Nth successful epoch (N configurable, default 10), ArchitectAgent
evaluates prerequisite gates and proposes a roadmap amendment if warranted.

**Prerequisite gates (all must be true before a proposal is emitted):**
1. `EpochTelemetry.health_score ≥ 0.80` over last 10 epochs
2. `FederatedEvidenceMatrix.divergence_count == 0` in last federated epoch
3. `WeightAdaptor.prediction_accuracy > 0.60`
4. No pending roadmap amendment proposals (prevents amendment storm)

**Acceptance criteria:**
- ArchitectAgent emits at most 1 proposal per 10 epochs
- Proposal content_hash matches re-computation from stored fields (replay proof)
- `GovernanceGate` evaluates the amendment as a standard mutation type
- Human-approval gate sign-off required; no auto-merge path exists

---

### M6-04 — Federated Roadmap Propagation 🔵 proposed

When a federation node's evolution loop generates a roadmap amendment proposal,
`FederationMutationBroker` propagates it to all peer nodes for their own governance
review. Each peer's `GovernanceGate` evaluates independently.

**Authority invariant:** Cross-repo roadmap promotion requires `divergence_count == 0`
in `FederatedEvidenceMatrix` across all participating nodes. A single divergent node
blocks the amendment.

**Acceptance criteria:**
- Amendment propagation leaves a `federation_origin` field in lineage chain
- Any node can reject without blocking its own local roadmap
- Evidence bundle includes `federated_roadmap_evidence` section before merge

---

### M6-05 — Autonomous Android Distribution 🟡 active (v3.1.0-dev)

Free public distribution via four parallel zero-cost tracks:

| Track | Status | Channel |
|-------|--------|---------|
| 1 | ✅ CI wired | GitHub Releases APK + Obtainium auto-update |
| 2A | 🟡 MR pending | F-Droid Official (reproducible build, ~1–4 weeks) |
| 2B | ✅ Documented | Self-Hosted F-Droid on GitHub Pages |
| 3 | ✅ CI wired | GitHub Pages PWA (Aponi web shell, installable on Android Chrome) |

**Governance invariant:** Every distributed APK is built by the `android-free-release.yml`
workflow, which runs the full governance gate (constitutional lint + Android lint) before
signing. No APK is distributed that has not passed the governance gate.

**Acceptance criteria:**
- `free-v*` tag triggers full pipeline in < 15 minutes end-to-end
- GitHub Release includes SHA-256 integrity hash alongside APK asset
- F-Droid metadata YAML passes `fdroid lint` without errors
- Obtainium import JSON parses and resolves the correct APK asset filter
- PWA manifests with `standalone` display mode on Android Chrome

**Launch command (zero cost, immediate public availability):**
```bash
git tag free-v3.1.0 && git push origin free-v3.1.0
```

---

## Measurement targets

| Milestone | Metric | Target |
|-----------|--------|--------|
| Phase 3 activation | `prediction_accuracy` | > 0.60 by epoch 20 |
| Phase 3 activation | Acceptance rate | 0.20–0.60 stable |
| Phase 4 semantic diff | Scoring determinism | 100% identical on identical AST |
| Phase 5 federation | Cross-repo divergence | 0 divergences per federated epoch ✅ |
| Phase 6 roadmap self-amendment | ArchitectAgent proposal governed | Human sign-off recorded in ledger |
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
