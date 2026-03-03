# ADAAD Milestone Roadmap · ADAAD-6 → ADAAD-9

> `innovative-ai/adaad` · Governance-grade milestone plan
> Authoritative baseline: `1.0.0 (Stable)` — `dreezy-6` → `main`

This document defines the four milestones that carry ADAAD from its v1.0.0 stable release through the Aponi-as-IDE developer environment. Each milestone is self-contained: it can ship independently of the one that follows. Each one also lays foundational capability that the next milestone depends on. The sequencing is intentional — dependencies flow forward, never backward.

---

## Milestone Architecture

```
ADAAD-6 · Stable Release (v1.0.0)          ← CURRENT — dreezy-6 → main
    │
    │  Delivers: HMAC remediation · all 11 constitutional rules enforced
    │            MCP co-pilot · Android resource_bounds · lock file ownership
    │            forensic service parameterization · 170 verified test files
    │
    ▼
ADAAD-7 · Governance Hardening (v1.2)
    │
    │  Delivers: Reviewer Reputation & Calibration Loop
    │            ledger extension · scoring engine · tier calibration
    │            Aponi reviewer panel · constitution v0.3.0
    │
    ▼
ADAAD-8 · Policy Simulation Mode (v1.3)
    │       ↑ consumes ADAAD-7 (reputation as simulation variable)
    │
    │  Delivers: Policy Simulation DSL
    │            constraint interpreter · epoch replay simulator
    │            Aponi simulation mode · exportable governance profiles
    │
    ▼
ADAAD-9 · Developer Experience (v1.4)
            ↑ consumes ADAAD-8 (simulation panel in Phase 5)

         Delivers: Aponi-as-IDE
                   proposal editor · constitutional linter · evidence viewer
                   replay inspector · simulation integration (Phase 5)
```

---

## ADAAD-6 · Stable Release

**Version:** 1.0.0 · **Branch:** `dreezy-6` → `main` · **Status:** Ready to merge

| Advancement | Status |
|---|---|
| HMAC verification stub remediated (Cryovant) | ✅ Verified |
| All 11 constitutional rules enforced (v0.2.0) | ✅ Verified |
| FastAPI lifespan migrated | ✅ Verified |
| MCP co-pilot integration (4 servers) | ✅ Verified |
| Android platform monitor + `resource_bounds` enforcement | ✅ Verified |
| `governance_runtime_profile.lock.json` ownership contract established | ✅ Verified |
| Forensic retention service parameterized (`ADAAD_ROOT`) | ✅ Verified |
| `federation/coordination.py` governed by determinism lint | ✅ Verified |
| `_reset_bootstrapped_flag` autouse fixture — strict isolation | ✅ Verified |
| Lineage v2 duplicate retired, single source enforced | ✅ Verified |
| Dependency baseline path fragility eliminated | ✅ Verified |
| 7 CI governance workflows active | ✅ Verified |
| 170 test files across 14 subdirectories | ✅ Verified |

**Merge gate:**
```
pytest tests/ -q                              → all pass
python tools/lint_determinism.py ...         → determinism lint passed
python scripts/verify_core.py                → Core verification passed
python scripts/check_dependency_baseline.py  → Dependency baseline check passed
python -m app.main --replay strict --verbose → replay_verified emitted, zero divergence
```

---

## ADAAD-7 · Governance Hardening

> **Execution detail update:** See `ADAAD_7_EXECUTION_PLAN.md` for the ordered four-phase closure plan spanning `v1.1-GA` compliance through federated readiness, and `docs/governance/ADAAD_7_GA_CLOSURE_TRACKER.md` for auditable control-by-control sign-off.


**Version target:** 1.2 · **Depends on:** ADAAD-6 merged
**Epic:** [Reviewer Reputation & Calibration Loop](./EPIC_1_Reviewer_Reputation.md)
**Labels:** `governance` `runtime` `risk-tiering` `v1.2`

This milestone introduces empirical feedback into governance calibration. The reputation engine closes the loop between human reviewer decisions and constitutional calibration without removing humans from the loop or granting execution authority from reputation. The constitutional floor — a human reviewer is always required — is architecturally enforced, not conventional.

| Deliverable | Module | Verification |
|---|---|---|
| Ledger — reviewer metadata fields | `schemas/pr_lifecycle_event.v1.json` `security/ledger/journal.py` | `tests/governance/test_pr_lifecycle_event_contract.py` |
| Reputation scoring engine | `runtime/governance/reviewer_reputation.py` | `tests/governance/test_reviewer_reputation.py` |
| Tier calibration + constitutional floor | `runtime/governance/review_pressure.py` | `tests/governance/test_review_pressure.py` |
| `reviewer_calibration` advisory constitutional rule | `runtime/governance/constitution.yaml` | `tests/test_constitution_policy.py` |
| Aponi `/governance/reviewer-calibration` endpoint | `server.py` | `tests/test_server_audit_endpoints.py` |
| Aponi reviewer panel | `ui/aponi_dashboard.py` | `tests/test_aponi_dashboard_e2e.py` |

**Constitutional impact:** `CONSTITUTION_VERSION` → `0.3.0`. One advisory rule introduced. No existing rules modified. No existing rule severities altered.

**Determinism constraint:** All scoring functions are governed by `tools/lint_determinism.py`. Wall-clock calls (`datetime.now()`, `time.time()`) fail lint in all scorer modules — all time inputs route through the governance clock.

**Merge gate:**
```
pytest tests/ -q                              → all pass
python tools/lint_determinism.py ...         → determinism lint passed
python -m app.main --replay strict --verbose → reputation outcomes reproduced from ledger
```

---

## ADAAD-8 · Policy Simulation Mode

**Version target:** 1.3 · **Depends on:** ADAAD-7 (reputation data as simulation variable)
**Epic:** [Policy Simulation DSL](./EPIC_2_Policy_Simulation_DSL.md)
**Labels:** `governance` `simulation` `Aponi` `v1.3`

This milestone democratizes governance reasoning. Non-technical stakeholders — compliance, product, audit — can express hypothetical constraints via a toggle UI or a bounded DSL, replay them against historical epochs, and measure tradeoffs before any amendment is filed. No simulated constraint can reach a live governance surface. The isolation invariant is architectural.

| Deliverable | Module | Verification |
|---|---|---|
| DSL grammar (10 constraint types) | `runtime/governance/simulation/dsl_grammar.py` | `tests/governance/test_simulation_dsl.py` |
| Constraint interpreter | `runtime/governance/simulation/constraint_interpreter.py` | `tests/governance/test_simulation_dsl.py` |
| Epoch replay simulator | `runtime/governance/simulation/epoch_simulator.py` | `tests/governance/test_epoch_simulator.py` |
| Simulation isolation invariant | `runtime/governance/simulation/epoch_simulator.py` | `tests/governance/test_simulation_isolation.py` |
| `POST /simulation/run`, `GET /simulation/results/{run_id}` | `server.py` | `tests/test_server_audit_endpoints.py` |
| Aponi simulation UI + constraint builder panel | `ui/aponi_dashboard.py` | `tests/test_aponi_dashboard_e2e.py` |
| Profile exporter | `runtime/governance/simulation/profile_exporter.py` | `tests/governance/test_simulation_profile_export.py` |
| Schema: `governance_simulation_policy.v1.json` | `schemas/` | `tests/governance/test_schema_validator.py` |
| Schema: `governance_profile.v1.json` | `schemas/` | `tests/governance/test_schema_validator.py` |

**Isolation invariant:** `SimulationPolicy.simulation = True` is checked at the `GovernanceGate` boundary before any ledger write, constitution state transition, or mutation execution. `tests/governance/test_simulation_isolation.py` asserts zero side effects across all simulation execution paths.

**DSL governance:** Grammar version-locked at 10 types for v1.3. Extensions require a versioned grammar PR with `governance-impact` label.

**Merge gate:**
```
pytest tests/ -q                              → all pass, including test_simulation_isolation.py
python tools/lint_determinism.py ...         → determinism lint passed (covers runtime/governance/simulation/)
python -m app.main --replay strict --verbose → simulation runs reproducible from recorded inputs
```

---

## ADAAD-9 · Developer Experience

**Version target:** 1.4 · **Depends on:** ADAAD-8 (simulation panel in Phase 5)
**Epic:** [Aponi-as-IDE](./EPIC_3_Aponi_IDE.md)
**Labels:** `Aponi` `DX` `IDE` `v1.4`

This milestone closes the authoring loop. Mutation proposals are authored, constitutionally linted, simulated, and submitted entirely within Aponi. Evidence bundles and replay traces are navigable alongside the editor. No new execution path is introduced — Aponi-as-IDE is a governed UI layer over the MCP pipeline shipped in v1.0. All authority checks, Tier-0 restrictions, and constitutional evaluations execute at the same points they execute today.

| Deliverable | Module | Verification |
|---|---|---|
| Proposal editor component | `ui/aponi/` | `tests/test_aponi_dashboard_e2e.py` |
| Editor → MCP submission + `aponi_editor_proposal_submitted.v1` journal event | `ui/aponi_dashboard.py` | `tests/test_aponi_dashboard_e2e.py` |
| Inline constitutional linter | `runtime/mcp/linting_bridge.py` | `tests/mcp/test_linting_bridge.py` |
| `GET /evidence/{bundle_id}` endpoint | `server.py` | `tests/test_server_audit_endpoints.py` |
| Evidence viewer UI | `ui/aponi/` | `tests/test_aponi_dashboard_e2e.py` |
| Replay inspector UI | `ui/aponi/` | `tests/test_aponi_dashboard_e2e.py` |
| Android throttle integration | `runtime/mcp/linting_bridge.py` | `tests/platform/test_android_monitor.py` |
| Simulation panel (Phase 5 — gated on Epic 2) | `ui/aponi/` | `tests/test_aponi_dashboard_e2e.py` |

**Authority invariant:** Every editor-originated proposal submission produces a journal entry with event type `aponi_editor_proposal_submitted.v1`. `authority_level` remains clamped to `governor-review` by `proposal_validator.py` for all editor-originated proposals. The IDE surface inherits all existing governance invariants without exception.

**Android constraint:** Linting frequency is governed by `AndroidMonitor.should_throttle()` when the device is resource-constrained. Simulation panel respects the `max_epoch_range` Android limit from ADAAD-8.

**Merge gate:**
```
pytest tests/ -q                              → all pass
python tools/lint_determinism.py ...         → determinism lint passed (covers linting_bridge.py)
python -m app.main --replay strict --verbose → replay_verified emitted
```

---

## Forward Dependency Map

```
ADAAD-6 (v1.0.0)
    ├── MCP infrastructure (proposal queue · validator · analyzer · ranker)
    │       └─▶ ADAAD-9 editor submissions route through this
    │
    ├── Android platform monitor
    │       └─▶ ADAAD-9 linting bridge governed by AndroidMonitor.should_throttle()
    │
    └── Constitution v0.2.0 (all 11 rules enforced)
            └─▶ ADAAD-7 introduces reviewer_calibration rule → v0.3.0
                    └─▶ Reputation data available as simulation variable
                            └─▶ ADAAD-8 DSL + epoch replay simulator
                                    └─▶ ADAAD-9 simulation panel (Phase 5)
```

---

## Post-ADAAD-9 Governance Items (not yet scoped)

These are tracked but not assigned to a milestone. Each requires a human-authored issue with `governance-impact` label before scope is committed.

| Item | Context |
|---|---|
| Distributed federation wire protocol | Multi-instance ADAAD coordination across devices; `LocalFederationTransport` in v1.0 is the foundation |
| Cryptographic replay proof bundles for external verifiers | `ReplayProofBuilder` infrastructure is live; trust-root distribution for third-party verification remains unscoped |
| Key-rotation enforcement escalation | Audit closure item before enterprise GA |
| Android swarm coordination | Multiple Pydroid3 instances sharing governance state via federation wire protocol; depends on federation epic |

---

*This roadmap is governed by the standard constitutional amendment process. Milestone scope adjustments require a PR with `governance-impact` label and human-in-the-loop review before the milestone is modified.*
