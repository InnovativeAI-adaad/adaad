# ADAAD Milestone Roadmap · ADAAD-6 → ADAAD-9

![Status: Stable](https://img.shields.io/badge/Status-Stable-2ea043)
![Milestone: ADAAD-8 Complete](https://img.shields.io/badge/Milestone-ADAAD--8_Complete-2ea043)
![Milestone: ADAAD-8 Complete](https://img.shields.io/badge/Milestone-ADAAD--8_Complete-2ea043)
![Next: ADAAD-9](https://img.shields.io/badge/Next-ADAAD--9-0ea5e9)

> Governance-grade milestone plan · `innovative-ai/adaad` · Authoritative baseline: `1.1.0 (Stable)`

**Last reviewed:** 2026-03-05

---

## Milestone Architecture

```
ADAAD-6 · Stable Release (v1.0.0)          ✅ COMPLETE
    │
    │  HMAC remediation · all 11 constitutional rules enforced
    │  MCP co-pilot · Android resource_bounds · lock file ownership
    │  forensic service parameterization · 170 verified test files
    │
    ▼
ADAAD-7 · Governance Hardening (v1.1)       ✅ COMPLETE — 2026-03-05
    │
    │  Reviewer Reputation & Calibration Loop
    │  ledger extension · scoring engine · tier calibration
    │  Aponi reviewer panel · constitution v0.3.0
    │
    ▼
ADAAD-8 · Policy Simulation Mode (v1.2)     ✅ COMPLETE — 2026-03-05
    │       ↑ consumes ADAAD-7 reputation as simulation variable
    │
    │  Policy Simulation DSL
    │  constraint interpreter · epoch replay simulator
    │  Aponi simulation mode · exportable governance profiles
    │
    ▼
ADAAD-9 · Developer Experience (v1.3)       ⬜ NEXT
            ↑ consumes ADAAD-8 simulation panel (Phase 5)

         Aponi-as-IDE
         proposal editor · constitutional linter · evidence viewer
         replay inspector · simulation integration
```

---

## ADAAD-6 · Stable Release

**Version:** 1.0.0 · **Status:** ✅ Complete

| Advancement | Status |
|---|---|
| HMAC verification stub remediated (Cryovant) | ✅ |
| All 11 constitutional rules enforced (v0.2.0) | ✅ |
| FastAPI lifespan migrated | ✅ |
| MCP co-pilot integration (4 servers) | ✅ |
| Android platform monitor + `resource_bounds` enforcement | ✅ |
| `governance_runtime_profile.lock.json` ownership contract | ✅ |
| Forensic retention service parameterized (`ADAAD_ROOT`) | ✅ |
| Lineage v2 duplicate retired, single source enforced | ✅ |

---

## ADAAD-7 · Governance Hardening

**Version:** 1.1.0 · **Status:** ✅ Complete · **Merged:** 2026-03-05 · **Constitution:** v0.3.0

### Deliverables

| Deliverable | Files | Status |
|---|---|---|
| Reviewer action outcome ledger extension | `schemas/pr_lifecycle_event.v1.json`, `runtime/governance/pr_lifecycle_event_contract.py` | ✅ |
| Reputation scoring engine | `runtime/governance/reviewer_reputation.py` | ✅ |
| Tier calibration + constitutional floor | `runtime/governance/review_pressure.py` | ✅ |
| `reviewer_calibration` advisory rule | `runtime/governance/constitution.yaml` | ✅ |
| CONSTITUTION_VERSION → 0.3.0 | `runtime/constitution.py` | ✅ |
| Aponi `/governance/reviewer-calibration` endpoint | `server.py` | ✅ |
| Aponi reviewer panel | `ui/aponi_dashboard.py` | ✅ |

### Test coverage

- PR-7-01: 25 tests — ledger event contract
- PR-7-02: 23 tests — reputation scoring engine
- PR-7-03: 23 tests — tier calibration + constitutional floor
- PR-7-04: 38 tests — constitution policy
- PR-7-05: 13 tests — server endpoints + dashboard E2E
- **Total: 76 new tests · all passing**

### Architectural invariants (ADAAD-7)

- Constitutional floor: minimum 1 human reviewer — enforced across all tiers and all reputation scores.
- Epoch weight snapshot: scoring weights are snapshotted per epoch; replay binds to the epoch-scoped snapshot.
- Score version binding: `scoring_algorithm_version` is recorded in every `reviewer_action_outcome` ledger event.
- Reviewer reputation calibrates panel **size only** — never authority or voting weight.

---

## ADAAD-8 · Policy Simulation Mode

**Version:** 1.2.0 · **Status:** ✅ Complete · **Merged:** 2026-03-05 · **Prerequisite:** ADAAD-7 merged ✅

### Scope

| PR | Title | CI tier | Deps |
|---|---|---|---|
| PR-10 | Simulation DSL Grammar + Interpreter | critical | ✅ Merged |
| PR-11 | Epoch Replay Simulator + Isolation Invariant | critical | ✅ Merged |
| PR-12 | Simulation Aponi Endpoints | standard | ✅ Merged |
| PR-13 | Governance Profile Exporter | critical (milestone) | ✅ Merged |

### Architectural intent

- Policy simulation must remain isolated from live governance state.
- Simulation epoch ranges are bounded and constitution-context-scoped.
- Governance profiles exported must be deterministically reproducible.
- Reputation scores from ADAAD-7 feed simulation as a parameterizable variable.

---

## ADAAD-9 · Developer Experience

**Version:** 1.3.0 · **Status:** ⬜ Next · **Prerequisite:** ADAAD-8 merged ✅

### Scope

| PR | Title | CI tier | Deps |
|---|---|---|---|
| PR-14 | Mutation Proposal Editor (Aponi Phase 1) | critical | ADAAD-7 ✅ |
| PR-15 | Inline Constitutional Linter | critical | PR-14 |
| PR-16 | Evidence Viewer + Endpoint | standard | PR-15 |
| PR-17 | Replay Inspector UI | standard | PR-16 |
| PR-18 | Simulation Panel Integration | standard | PR-12 |

### Authority invariant

Aponi surfaces are authoring and analysis only. They do not grant execution authority at any phase.

---

## Value Acceleration Checkpoints

| Checkpoint | Trigger | Action |
|---|---|---|
| ADAAD-7 complete | PR-7-05 merged + milestone gate passes | Flag for patent filing readiness review; begin ADAAD-8 |
| Market coupling live | ADAAD-8 PR-12 + PR-13 staged | Income approach transitions from speculative to grounded |
| v1.2-GA readiness | All ADAAD-8 PRs merged; evidence complete | Surface full Go/No-Go checklist; explicit operator sign-off required |
