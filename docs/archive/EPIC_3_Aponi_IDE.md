# Epic: Aponi-as-IDE — Governance-First Developer Environment

> **Labels:** `Aponi` `DX` `IDE` `enhancement` `v1.4`
> **Milestone:** ADAAD-9 Developer Experience
> **Complexity:** Major feature (> 8 hours)
> **Governance impact:** Introduces governed command capabilities — mutation authoring, constitutional linting, simulation

---

## Problem Statement

ADAAD has a governance spine — constitutional rules, replay attestation, lineage tracking, policy simulation — but the human authoring workflow lives entirely outside it. A developer proposing a mutation today must compose code externally, run tests in isolation, manually verify constitutional rules, and then import the output into the pipeline. The governance intelligence resident in the system is unavailable at the authoring moment when it would be most consequential.

Aponi is currently a read-only governance observatory: it surfaces system state but plays no role in the development loop. As ADAAD matures toward enterprise and multi-contributor deployments, this gap becomes the primary adoption constraint — teams will not sustain a governance system that demands a second toolchain to author the artifacts it governs.

---

## Architecture Framing

Aponi-as-IDE reorients the dashboard from a governance observer into a **governance-first authoring environment**. The reorientation is not additive feature layering on top of the existing dashboard. It is a first-principles shift: governance linting, simulation, and evidence inspection become foundational primitives in the development workflow, not post-hoc audit steps.

```
Developer opens Aponi
        │
        ▼
Mutation proposal authored in the editor
        │
        ▼  (inline, debounced, non-blocking)
Constitutional linter surfaces policy violations
        │
        ▼
Developer runs inline simulation against historical epochs
        │
        ▼
Evidence viewer surfaces projected fitness and risk scores
        │
        ▼
Developer submits proposal ──▶ MCP queue ──▶ constitutional evaluation ──▶ staging
        │
        ▼
Replay inspector surfaces the deterministic transition trace
```

**The authority invariant holds throughout the entire flow:** Aponi never executes mutations. It authors proposals. Execution authority remains exclusively with the constitutional evaluation engine and the governance gate — the IDE surface neither holds nor approximates that authority.

---

## Goal

Deliver a governance-first IDE within Aponi that supports mutation proposal authoring, inline constitutional linting, evidence inspection, and replay trace navigation — all within a single browser-accessible interface, with simulation integration wired in Phase 5 upon Epic 2 completion.

---

## Deliverables

**D1 — Mutation Proposal Editor** · `ui/aponi_dashboard.py` + `ui/aponi/` frontend

A Python-syntax editor panel for authoring mutation proposals. Every submission routes through the existing MCP pipeline — the editor is a governed UI surface, not a new execution path.

Capabilities:
- Author or paste a mutation candidate with Python syntax highlighting
- Specify target file path, `agent_id`, and mutation metadata
- Submit proposals as `MutationRequest` objects via `POST /mutation/propose` (existing MCP endpoint)
- Every editor-originated submission emits journal event `aponi_editor_proposal_submitted.v1` — traceable from proposal to ledger

**D2 — Inline Constitutional Linter** · `runtime/mcp/linting_bridge.py`

Real-time constitutional pre-evaluation wired to the editor via `runtime/mcp/mutation_analyzer.py`. A debounced, async call to `analyze_mutation()` runs on the current editor state and returns inline annotations before submission.

Linting invariants:
- Linting must use the same rule engine and rule dependency graph as `GovernanceGate`.
- Linting must not persist mutable cross-proposal cache/state that can alter verdict determinism.
- Linting remains informational and never bypasses or replaces constitutional evaluation at queue-append time.

```
Warning [max_complexity_delta]: Complexity delta 0.23 exceeds advisory threshold 0.15.
  → Rule: max_complexity_delta (WARNING)
  → Active policy: constitution.yaml v0.2.0

Blocked [no_banned_tokens]: Token 'os.system' is in the banned token list.
  → Rule: no_banned_tokens (BLOCKING)
  → This proposal will be rejected at constitutional evaluation.
```

Linting is informational — it never gates the editor. The authoritative governance gate remains the constitutional evaluation at queue-append time. On Android, linting frequency is governed by `AndroidMonitor.should_throttle()` to respect device resource constraints.

**D3 — Policy Simulation Integration** · Leverages Epic 2 (Phase 5)

An inline "Simulate against history" panel surfaced within the editor workflow, delivered after Epic 2 reaches production.

Flow:
1. Editor pre-populates the simulation constraint set from the active constitution
2. Developer optionally governs hypothetical constraints via the Epic 2 toggle surface
3. Simulation executes against the most recent N epochs (configurable; default 10)
4. Results surface inline: "Under current policy, this mutation type was advanced in 7 of 10 recent epochs. Under your proposed constraint, it would have been gated in 3."

**D4 — Evidence Viewer** · `ui/aponi_dashboard.py` + new endpoint

A structured viewer for evidence bundles (`schemas/evidence_bundle.v1.json`) associated with a mutation proposal or a completed epoch.

Surfaces:
- Fitness scores (with determinism provenance: scoring algorithm version, weights schema version)
- Constitutional evaluation results per rule (verdict, reason, tier override applied)
- Sandbox evidence (syscall profile, filesystem writes, resource consumption)
- Replay attestation digest and verification status

New endpoint: `GET /evidence/{bundle_id}` — returns full evidence bundle by ID; bearer-auth gated; response schema-enforced against `schemas/evidence_bundle.v1.json`.

**D5 — Replay Inspector** · `ui/aponi_dashboard.py` + existing replay endpoints

A navigable transition trace viewer built over the existing `/replay/divergence` and `/replay/diff?epoch_id=...` endpoints (both live in v1.0). No new execution paths.

Surfaces:
- Epoch-by-epoch transition chain with deterministic digest per step
- Diff view: delta between two epoch states
- Divergence alerts: where the current epoch diverged from strict replay expectations
- Lineage navigation: from a mutation in the trace, navigate to its full lineage — from proposal through staging to final decision

**D6 — Android/Pydroid3 Compatibility**

Aponi-as-IDE is a browser-accessible web app served by `server.py`. On Pydroid3, the same server runs locally and the developer opens the dashboard in a mobile browser. No native Android components are required.

Governed behaviors under constrained conditions:
- Linting frequency governed by `AndroidMonitor.should_throttle()` when device is resource-constrained
- Simulation panel respects the `max_epoch_range` Android limit (from Epic 2)
- Heavy operations (simulation, evidence bundle fetch) surface loading indicators; they do not block the editor

---

## Acceptance Criteria

- [ ] Developers can author and submit a mutation proposal entirely within Aponi without departing to a second toolchain
- [ ] Constitutional linting surfaces BLOCKING and WARNING annotations before submission; linting never gates the editor or blocks typing
- [ ] Linting uses the same rule engine and dependency graph as `GovernanceGate`; preview and execution verdict semantics are aligned
- [ ] Every BLOCKING annotation references the active `CONSTITUTION_VERSION` and rule name so developers know precisely what to resolve
- [ ] Inline simulation (Phase 5, upon Epic 2 completion) surfaces results without navigation away from the editor
- [ ] Evidence bundles are viewable and structurally conform to `schemas/evidence_bundle.v1.json`; evidence viewer tests are covered in `tests/test_aponi_dashboard_e2e.py`
- [ ] Evidence bundles include `scoring_algorithm_version` and `constitution_version` metadata for replay-grade provenance
- [ ] Replay inspector surfaces the epoch transition chain for the configurable last-N epochs; divergence events are visually distinguished
- [ ] All Aponi write paths (proposal submissions) produce journal entries traceable to the Aponi session; event type `aponi_editor_proposal_submitted.v1`
- [ ] All new endpoints (`/evidence/{bundle_id}`) are bearer-auth gated and covered in `tests/test_server_audit_endpoints.py`
- [ ] `authority_level` remains clamped to `governor-review` by `proposal_validator.py` for all editor-originated submissions — the IDE surface introduces no authority exceptions
- [ ] `AndroidMonitor.should_throttle()` governs linting call frequency when the device is resource-constrained
- [ ] CHANGELOG entry promoted under `[Unreleased]`

---

## Execution Plan

**Phase 1 — Editor and Submission (self-contained; no simulation dependency)**
1. Deliver mutation proposal editor component in `ui/aponi/` with Python syntax highlighting
2. Wire editor submission to `POST /mutation/propose` (existing MCP endpoint)
3. Wire `aponi_editor_proposal_submitted.v1` journal event on every editor-originated submission
4. Ship editor submission tests in `tests/test_aponi_dashboard_e2e.py`

**Phase 2 — Inline Constitutional Linter**
5. Deliver `runtime/mcp/linting_bridge.py` — debounced async wrapper over `mutation_analyzer.py` returning annotation objects
6. Wire linting annotations to editor UI (inline gutter + summary panel)
7. Ship `tests/mcp/test_linting_bridge.py` — determinism tests for annotation output across all BLOCKING and WARNING rule types and preview/execution rule-engine parity
8. Wire `AndroidMonitor.should_throttle()` to linting frequency controller

**Phase 3 — Evidence Viewer**
9. Wire `GET /evidence/{bundle_id}` endpoint with bearer auth and schema enforcement
10. Deliver evidence viewer UI component
11. Extend audit endpoint test suite to cover the evidence endpoint
12. Ship `tests/test_evidence_viewer.py` including provenance-field assertions (`scoring_algorithm_version`, `constitution_version`)

**Phase 4 — Replay Inspector**
13. Deliver replay inspector UI over existing `/replay/divergence` and `/replay/diff` endpoints
14. Wire lineage navigation (from mutation in trace → full lineage chain view)
15. Extend `tests/test_aponi_dashboard_e2e.py` to cover inspector surfaces

**Phase 5 — Simulation Integration (requires Epic 2 at production)**
16. Wire Epic 2 `POST /simulation/run` into the editor workflow as the inline simulation panel
17. Pre-populate simulation constraint set from the active constitution on panel open
18. Surface inline results without navigating away from the editor

---

## Risk Register

| Risk | Mitigation |
|---|---|
| Editor surface mistaken for execution authority | UI consistently labels the editor as "Proposal Editor"; submissions route to the proposal queue, not the mutation executor; documented explicitly in UI and `docs/mcp/IMPLEMENTATION.md` |
| Linting introduces perceived latency in the authoring loop | Debounce at 800ms minimum; surface a loading indicator; linting failures are non-blocking; editor responsiveness is the primary constraint |
| Replay inspector is expensive for large epoch ranges on Android | Default to last 10 epochs; expose configurable limit; governed by `should_throttle()` |
| IDE feature scope expands without governance review | Deliverables are bounded to D1–D6; any new IDE surface requires a separate issue against this epic with `governance-impact` label |
| Editor write surface broadens the attack surface | Every editor-originated write is journaled; the proposal endpoint remains JWT-gated; `authority_level` clamping remains enforced by `proposal_validator.py` — the IDE surface inherits all existing governance invariants without exception |
| Lint preview diverges from GovernanceGate verdicts | Enforce shared rule engine + dependency graph contracts and parity tests between lint preview and governance evaluation |

---

## Authority Invariant Summary

The Aponi IDE introduces no new execution path. The complete flow remains:

```
Aponi editor
    ──▶ MCP proposal queue
    ──▶ constitutional evaluation (GovernanceGate)
    ──▶ staging
```

The editor is a governed UI layer over the MCP infrastructure shipped in v1.0. All authority checks, Tier-0 restrictions, and constitutional evaluations execute at the same points they execute today. The editor cannot reach, shortcut, or approximate any governance gate.

---

## Governance Lineage

- `runtime/mcp/server.py` — existing MCP server; editor submissions route here
- `runtime/mcp/mutation_analyzer.py` — linting bridge consumes this for inline evaluation
- `runtime/mcp/proposal_validator.py` — `authority_level` clamping remains enforced here; IDE surface cannot override
- `tests/test_aponi_dashboard_e2e.py` — existing e2e test suite; extend, do not retire
- `ui/aponi_dashboard.py` — existing dashboard; IDE capabilities are surfaced here
- `docs/mcp/IMPLEMENTATION.md` — MCP architecture reference governing editor integration
- Epic 1 (Reviewer Reputation) — evidence viewer should surface reviewer calibration data alongside mutation evidence bundles
- Epic 2 (Policy Simulation DSL) — Phase 5 simulation integration is gated on Epic 2 reaching production
