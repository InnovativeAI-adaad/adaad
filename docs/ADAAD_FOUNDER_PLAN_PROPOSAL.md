# ADAAD — Founder Plan Proposal

> **Document class:** Founder-level Strategic Proposal  
> **Prepared for:** Founder / Owner · @dreezy66  
> **Date:** March 6, 2026  
> **Status:** Submitted for review  
> **Reference:** `ADAAD-PROPOSAL-2026-03-06`

---

## 1. What ADAAD Is — And What It Is Not

**ADAAD is a governed software evolution engine.** It generates, tests, scores, and selects improved versions of software agents — under strict human oversight and auditable governance. It is not a sentient system, not a business decision-maker, and not an autonomous agent acting on its own judgment.

Every action ADAAD takes is **traceable**, every improvement is **measurable**, and every autonomous operation is **reversible**. The system earns the right to act more independently — one demonstrated generation at a time.

| Principle | What It Means |
|-----------|--------------|
| **Traceability Over Speed** | Every agent, mutation, and decision has a parent and a score. Nothing ships without a verified lineage chain. |
| **Stability Over Novelty** | High-quality, proven improvements are valued over high-volume experimentation. |
| **Reversibility as Requirement** | No autonomous action permitted unless it can be fully undone within the current generation window. |
| **Human Authority Always** | Humans set goals, define constraints, and approve releases. The system advises and executes — never overrides. |

---

## 2. Current State Assessment — v2.1.0

ADAAD is at **v2.1.0** with Phase 3 (Adaptive Scoring Engine) fully shipped and Phase 4 (Semantic Mutation Diff Engine) in active development.

**What is operational today:**

| Component | Status | Function |
|-----------|--------|---------|
| `AIMutationProposer` | ✅ Live | Three AI personas (Architect/Dream/Beast) via Claude API |
| `BanditSelector` (UCB1) | ✅ Live | Intelligent agent selection, activates at ≥10 pulls |
| `ThompsonBanditSelector` | ✅ Standby | Activates when non-stationarity detected (≥30 epochs) |
| `NonStationarityDetector` | ✅ Live | Page-Hinkley sequential change detection |
| `PenaltyAdaptor` | ✅ Live | Adaptive risk/complexity weights via momentum-descent |
| `WeightAdaptor` | ✅ Live | Momentum-descent scoring, LR=0.05, bounds enforced |
| `FitnessLandscape` | ✅ Live | Per-type win/loss ledger, plateau detection |
| `PopulationManager` | ✅ Live | BLX-alpha genetic algorithm, elite preservation |
| `SemanticDiffEngine` | 🔄 In Progress | AST-based risk scoring (stdlib only, 22 tests passing) |
| `GovernanceGate` | ✅ Live | The only constitutional approval authority |
| Evidence Ledger | ✅ Live | SHA-256 hash-chained, append-only, replay-verified |
| `EpochTelemetry` | ✅ Live | Append-only analytics, 5 health indicators, weekly CI |
| CI/CD Pipeline | ✅ Live | 4-tier gate evaluation per mutation, all tiers passing |

**Current CI gate status:** All 4 tiers passing. Zero open findings. Zero blocked at gate.

---

## 3. The 18-Month Plan

| Phase | Timeline | Status | Autonomy | Gate Condition |
|-------|----------|--------|----------|---------------|
| 0 — Foundation | Q4 2025 | ✅ Complete | L0 — Manual | — |
| 1 — Bootstrap | Q1 2026 | ✅ Complete | L1 — Supervised | Replay tests, approval gates live |
| 2 — Governed Loop | Q1 2026 | ✅ Complete | L2 — Constrained | CI/CD, audit chain, scoring v2 |
| 3 — Adaptive Score | Q1 2026 | ✅ Shipped (v2.1.0) | L2+ Adaptive | PenaltyAdaptor, Thompson live |
| 4 — Semantic Diff | Q2 2026 | 🔄 In Progress | L3 — Semantic | SemanticDiffEngine GA, Phase 3 done ✅ |
| 5 — Multi-Gen Lineage | Q3 2026 | Planned | L3 — Multi-Gen | G3+ active, DAG lineage graph |
| 6 — Compound Evo. | Q1–Q2 2027 | Horizon | L4 — Gov. Auto | G7+ lineage, per-generation review |

**Gate condition (structural, not optional):** No phase transition occurs unless the prior phase demonstrates stability over defined agent generations, all audit chains pass integrity checks, and a human operator formally approves the advancement.

---

## 4. Measurable Success Criteria

| Metric | Target | Phase Gate | Measurement Method |
|--------|--------|-----------|-------------------|
| Mutation pass rate | ≥ 87% | Phase 3 GA | Automated test + replay gate count |
| Lineage completeness | 100% | Phase 2 | Graph integrity validator — no orphan nodes |
| CI/CD compliance | ≥ 95% | Phase 2 | Per-run gate evaluation log |
| Governance overhead | < 15% | Phase 3 | Compute time + human-hours per generation |
| Agent generation depth | G7+ | Phase 5 horizon | Lineage graph depth at horizon close |
| Reversibility rate | 100% | All phases | Mutation blocked if non-reversible — no exceptions |
| `WeightAdaptor` accuracy | > 0.60 | Phase 3 (epoch 20) | `prediction_accuracy` field in telemetry JSON |

**North star:** Useful mutation rate — 10 high-quality, traceable, approved improvements beats 100 unverified ones by every meaningful measure.

---

## 5. Founder-Level Governance Commitments (8 Structural Guarantees)

These are non-negotiable. They are enforced architecturally — not aspirationally.

1. **Human release authority is permanent.** No autonomy level permits automated production deployment without an explicit human approval event.

2. **Constraint layer is enforced by the system.** Mutation bounds are defined by humans; they cannot be overridden autonomously at any phase. All weights bounded `[0.05, 0.70]` by constitution.

3. **Every autonomous action is cryptographically logged.** Agent ID, parent ID, score, timestamp, and decision rationale — SHA-256 chained, append-only.

4. **Audit chain integrity is a release gate.** All logs are append-only, chain-linked, and verified on every CI/CD run. A broken chain blocks the release, no exceptions.

5. **Rollback is immediate and unilateral.** Any designated operator may revert a generation without quorum, approval, or system delay.

6. **Autonomy advancement requires formal milestone review.** Demonstrated stability + passing audit chains + written human sign-off. No phase skipping.

7. **Android/Pydroid3 compatibility is a hard floor.** No mutation that breaks mobile compatibility enters production, regardless of fitness score. Zero new C-compiled dependencies without explicit approval.

8. **Lineage graph becomes canonical system of record.** By Q2 2027, every released artifact has a complete, auditable generational provenance chain published in the repo.

---

## 6. Recommended Next Actions — Priority-Ordered

| Priority | Action | Owner | Done When |
|----------|--------|-------|-----------|
| 🔴 !1 | Ship Phase 4 GA — `SemanticDiffEngine` fully wired + 22 tests all green | Founder | `semantic_diff_v1.0` in prod, v2.2.0 tagged |
| 🔴 !2 | Validate `WeightAdaptor.prediction_accuracy` at epoch 20 | Founder | Telemetry JSON shows `> 0.60` |
| 🟡 !3 | Design lineage DAG schema v1 — node/edge structure for multi-gen tracking | Founder | Schema committed to `docs/governance/` |
| 🟡 !4 | Draft Phase 5 gate criteria — stability threshold for L3 → L3+ advancement | Founder | Criteria doc committed, human sign-off recorded |
| ⚪ !5 | Activate Thompson Sampling in production — verify ≥30 epoch condition met | System | `_thompson_active: true` in landscape state JSON |
| ⚪ !6 | Run first cross-branch fitness comparison — lineage branch A vs. B | Founder | Comparison report committed to `docs/releases/` |

---

## 7. Relationship to Active Roadmap Work

| Roadmap Item | Status | Forecast Alignment |
|-------------|--------|-------------------|
| PR-PHASE3-01: PenaltyAdaptor | ✅ Merged | Phase 3 objective achieved |
| PR-PHASE3-02: Thompson + NSD | ✅ Merged | Phase 3 + Phase 4 prep |
| PR-PHASE4-01: SemanticDiffEngine | 🔄 In Progress | Phase 4 — final gate remaining |
| Phase 5: Multi-Gen Lineage Graph | Planned | Structural goal of forecast horizon |
| PR-CI-01: Python version pin | ✅ Merged | CI compliance target |
| Weekly epoch analytics CI | ✅ Live | Governance overhead monitoring |

---

*ADAAD Founder Plan Proposal v2.1 · InnovativeAI-adaad · March 6, 2026*  
*Governance: Human-authored. Audit lineage: git log — full provenance available.*  
*Reference: ADAAD-PROPOSAL-2026-03-06*
