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

### Four Non-Negotiable Design Principles

| Principle | What It Means |
|-----------|--------------|
| **Traceability Over Speed** | Every agent, mutation, and decision has a parent and a score. Nothing ships without a verified lineage chain. |
| **Stability Over Novelty** | High-quality, proven improvements are valued over high-volume experimentation. |
| **Reversibility as Requirement** | No autonomous action permitted unless it can be fully undone within the current generation window. |
| **Human Authority Always** | Humans set goals, define constraints, and approve releases. The system advises and executes — it never overrides human judgment. |

---

## 2. Current State Assessment

ADAAD is in **Phase 1 — Meta-Controller Bootstrap** at v2.1.0. Phase 0 (Foundation & Scaffold) is complete.

**What is operational today:**
- `BanditSelector` (UCB1 + Thompson Sampling) — agent selection learning
- `PenaltyAdaptor` — adaptive scoring weights (risk_penalty, complexity_penalty)
- `SemanticDiffEngine` — AST-aware mutation risk scoring
- `EpochTelemetry` — append-only analytics with health indicators
- `GovernanceGate` — the sole constitutional approval authority
- Evidence Ledger — SHA-256 hash-chained, append-only, replay-verified
- `StageBranchCreator` — deterministic branch naming with provenance manifest

**Current autonomy level:** L1 — Supervised. Every action requires human review.

**Current CI status:** Full pipeline with 11 governance axes evaluated per mutation.

---

## 3. The 18-Month Plan

Five phases. Each increases autonomy by one level — only after demonstrated stability at the prior level.

| Phase | Timeline | Status | Autonomy | Key Gate |
|-------|----------|--------|----------|----------|
| 0 — Foundation | Q4 2025 | ✅ Complete | L0 — Manual | — |
| 1 — Bootstrap | Q1–Q2 2026 | ◉ Active | L1 — Supervised | Scoring rubric v1, replay tests, approval gates |
| 2 — Governed Loop | Q3 2026 | Planned | L2 — Constrained | E/E loop live, CI/CD, audit chain, scoring v2 |
| 3 — Adaptive Score | Q4 2026 | Planned | L3 — Adaptive | ≥87% pass rate, G3+ agents, multi-gen lineage |
| 4 — Compound Evo. | Q1–Q2 2027 | Horizon | L4 — Gov. Auto | G7+ generations, per-generation review, lineage as record |

**Gate condition:** No phase transition occurs unless the prior phase demonstrates stability over N agent generations, all audit chains pass integrity checks, and a human operator formally approves the advancement.

---

## 4. Measurable Success Criteria

Every target is quantified. No vague goals.

| Metric | Target | Phase Gate |
|--------|--------|-----------|
| Mutation pass rate | 87% | Phase 3 |
| Lineage completeness | 100% | Phase 2 |
| CI/CD compliance | ≥ 95% | Phase 2 |
| Governance overhead | < 15% of throughput | Phase 3 |
| Agent generation depth | G7+ | Phase 4 |
| Reversibility rate | 100% | All phases |
| Human review cadence | Δ per generation (from per-mutation) | Phase 4 |

**North star:** Useful mutation rate — not mutation volume. Ten high-quality, traceable, human-approved improvements per generation outperforms one hundred unverified ones.

---

## 5. Founder-Level Governance Commitments

These are structural guarantees built into the architecture — not aspirational guidelines.

1. **Human authority over all releases is permanent.** No autonomy level permits automated production deployment without an explicit human approval event.

2. **The constraint layer is enforced by the system itself.** Humans define mutation bounds; those bounds cannot be overridden autonomously at any phase.

3. **Every autonomous action is logged.** Signed entry: `agent_id, parent_id, score, timestamp, decision_rationale`. No silent actions.

4. **All audit logs are append-only and cryptographically chained.** Integrity verification runs on every CI/CD pipeline push. A broken chain blocks the release.

5. **Rollback authority is immediate and unilateral.** Any designated operator may revert a generation without quorum or delay.

6. **Autonomy level advancement requires formal milestone review.** Demonstrated stability + passing audit chains + written human sign-off. No phase skipping.

7. **The Android/Pydroid3 execution constraint is a hard floor.** No mutation that breaks mobile compatibility enters production, regardless of fitness score.

8. **ADAAD's lineage graph will be published as the canonical system of record for all released artifacts by Q2 2027.**

---

## 6. Recommended Next Actions

Ordered by priority. Each has a clear completion signal.

### Critical
1. **Wire the first human approval gate** — Build the minimum viable gate: a mutation cannot advance to "scored" state without a logged human approval event. Done signal: first approved mutation in audit log.

2. **Define Phase 2 gate criteria formally** — Document the stability threshold required to advance from L1 → L2. Minimum: N consecutive approved mutations, 100% lineage completeness, zero audit chain failures. Commit to repo as a governance doc.

### High Priority
3. **Draft lineage graph schema v1** — Define DAG node/edge structure: `agent_id, parent_id, score, timestamp, mutation_delta, human_approved_by`. Done signal: first multi-node lineage chain in graph.

4. **Establish replay test suite baseline** — Write 5 deterministic scenarios: known input → known mutation → known score. All 5 must pass in Pydroid3 environment.

### Standard
5. **Update epoch analytics targets** — Align `EpochTelemetry` health targets with the forecast metrics defined in §4 above. Add `mutation_pass_rate` and `lineage_completeness` as first-class health indicators.

6. **Tag v2.1.0 formally** — Complete GA closure tracker, SPDX CI enforcement, governance sign-offs. This clears the backlog before Phase 2 work begins.

---

## 7. Relationship to Active Work

This proposal is additive to the existing ADAAD roadmap. No existing work is cancelled or contradicted.

| Active Work Item | Relationship to This Proposal |
|-----------------|-------------------------------|
| PR-CI-01 formal closure | Prerequisite for clean Phase 2 entry |
| PR-CI-02 SPDX enforcement | Governance overhead reduction (§4 metric) |
| Phase 3 — Adaptive Penalty Weights | Already shipped in v2.1.0 — Phase 1 maturity signal |
| Phase 4 — Semantic Diff Engine | Active — lineage completeness enabler |
| Phase 5 — Multi-Repo Federation | Phase 4 enabler in the 18-month view |
| Phase 6 — Autonomous Roadmap Amendment | Aligns with Phase 4 "Compound Evolution" in forecast |

---

*Interactive visual version: `docs/ADAAD_Founder_Plan_Proposal.html`*  
*Full strategic forecast: `docs/ADAAD_HORIZON_FORECAST_2026.md`*  
*Horizon interactive view: `docs/ADAAD_Horizon_v2.html`*
