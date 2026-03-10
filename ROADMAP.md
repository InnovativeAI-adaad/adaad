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

**Status:** ✅ shipped · **Closed:** 2026-03-07 · **Released:** v3.1.0 · Promoted from backlog: 2026-03-06

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

### M6-03 — EvolutionLoop integration ✅ shipped (v3.1.0) · PR-PHASE6-02

`runtime/evolution/evolution_loop.py` — `_evaluate_m603_amendment_gates()`

`RoadmapAmendmentEngine.propose()` wired into the Phase 5 epoch orchestrator.
After every Nth epoch (configurable via `ADAAD_ROADMAP_AMENDMENT_TRIGGER_INTERVAL`,
default 10), the loop evaluates all six prerequisite gates deterministically.

**Prerequisite gates (all evaluated in order; any failure halts without aborting epoch):**
1. `GATE-M603-01` — `epoch_count % trigger_interval == 0`
2. `GATE-M603-02` — `EpochTelemetry.health_score(last_10) >= 0.80`
3. `GATE-M603-03` — `FederatedEvidenceMatrix.divergence_count == 0` (if federation enabled)
4. `GATE-M603-04` — `WeightAdaptor.prediction_accuracy > 0.60`
5. `GATE-M603-05` — `len(RoadmapAmendmentEngine.list_pending()) == 0`
6. `GATE-M603-06` — `amendment_trigger_interval >= 5` (misconfiguration guard)

**Acceptance criteria:**
- `EpochResult.amendment_proposed == True` only when all 6 gates pass: **✅**
- Amendment evaluation failure does NOT abort epoch (fail-closed, non-fatal): **✅**
- Identical epoch inputs produce identical gate verdicts (determinism CI job): **✅**
- `INVARIANT PHASE6-STORM-0` — at most 1 pending amendment per node: **✅**
- `INVARIANT PHASE6-AUTH-0` — `authority_level` immutable after construction: **✅**
- `INVARIANT PHASE6-HUMAN-0` — no auto-approval path exists: **✅**

**Tests:** `tests/autonomy/test_evolution_loop_amendment.py` (T6-03-01..13)

---

### M6-04 — Federated Roadmap Propagation ✅ shipped (v3.1.0) · PR-PHASE6-03

`runtime/governance/federation/mutation_broker.py` — `propagate_amendment()`

When a federation node's evolution loop generates a roadmap amendment proposal,
`FederationMutationBroker` propagates it to all peer nodes for independent
governance review. All-or-nothing propagation with rollback on any peer failure.

**Authority invariants enforced:**
- `INVARIANT PHASE6-FED-0` — source-node approval is provenance-only; destination
  nodes evaluate independently and require their own human governor sign-off
- `INVARIANT PHASE6-STORM-0` — propagation path honours per-node pending-amendment limit
- `INVARIANT PHASE6-HUMAN-0` — no autonomous merge/sign-off authority introduced

**Acceptance criteria:**
- `federated_amendment_propagated` ledger event emitted on successful propagation: **✅**
- Rollback on any peer failure emits `federated_amendment_rollback` event: **✅**
- `federation_origin` field present in destination lineage chain: **✅**
- Any peer node can reject without blocking other nodes: **✅**
- `divergence_count == 0` required before propagation proceeds: **✅**

**Tests:** `tests/governance/federation/test_federated_amendment.py` (≥8 tests)

---

### M6-05 — Autonomous Android Distribution ✅ shipped (v3.1.0) · PR-PHASE6-04

Free public distribution via four parallel zero-cost tracks:

| Track | Status | Channel |
|-------|--------|---------|
| 1 | ✅ CI wired | GitHub Releases APK + Obtainium auto-update |
| 2A | ✅ MR submitted | F-Droid Official (reproducible build, ~1–4 weeks review) |
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

## Phase 6.1 — Complexity, Safety, and Efficiency Simplification Increment

**Status:** ✅ shipped · **Released:** v3.1.1 · **Closed:** 2026-03-07 · **Lane:** Governance hardening / complexity reduction · **Tooling:** ✅ in main

This increment reduces operational complexity while preserving fail-closed
governance by introducing explicit simplification budgets and CI-enforced
contract checks.

**Delivered targets (all CI-enforced, fail-closed):**

| Target | Baseline | Enforced Cap | Status |
|---|---|---|---|
| Legacy branch count | 23 | ≤ 6 | ✅ |
| `runtime/constitution.py` max lines | 2200 | 2100 | ✅ |
| `app/main.py` max lines | 1200 | 800 | ✅ |
| `security/cryovant.py` max fan-in | 6 | 5 | ✅ |
| `runtime/autonomy/loop.py` max lines | 360 | 340 | ✅ |
| Metrics-schema producer coverage | — | 100% | ✅ |

**CI enforcement:** `python scripts/validate_simplification_targets.py` runs on every PR
and fails closed on complexity drift, legacy-path regression, metrics-schema contract
drift, or runtime-cost cap regression. `enforced_max_branches` locked from 23 → 6 in
`governance/simplification_targets.json`.

**Validator output (post-closeout):**
```json
{"legacy_count": 6, "metrics_coverage_percent": 100.0, "status": "ok", "errors": []}
```

---

## Phase 7 — Reviewer Reputation & Adaptive Governance Calibration

**Status:** ✅ shipped · **Released:** v3.2.0 · **Closed:** 2026-03-08 · **Requires:** Phase 6.1 shipped ✅

Phase 7 closes the feedback loop between human reviewer decisions and constitutional
calibration — a mechanism absent from all known open-source governance platforms.
Governance pressure adapts empirically to reviewer track record; the constitutional
floor (human review always required) is architecturally inviolable.

### M7-01 — Reviewer Reputation Ledger

`runtime/governance/reviewer_reputation_ledger.py`

Append-only, SHA-256 hash-chained ledger of all reviewer decisions: approve, reject,
timeout, and override events. Every entry carries `reviewer_id`, `epoch_id`,
`decision`, `rationale_length`, and `outcome_validated` (post-merge fitness signal).

- Ledger is write-once per decision — no retroactive modification
- `reviewer_id` is HMAC-derived from signing-key fingerprint (no plaintext PII)
- Replay-safe: deterministic on identical input sequences

### M7-02 — Reputation Scoring Engine

`runtime/governance/reviewer_reputation.py`

Derives reputation score `r ∈ [0.0, 1.0]` from ledger history:

```
r = α · accuracy_rate + β · coverage_rate + γ · calibration_consistency
```

- `accuracy_rate`: fraction of approved mutations with positive post-merge fitness
- `coverage_rate`: fraction of proposals reviewed within SLA window
- `calibration_consistency`: variance of rationale_length signals (lower = better)
- Weights `α=0.50, β=0.25, γ=0.25` — governance-impact changes require constitution amendment

### M7-03 — Tier Calibration Engine

`runtime/governance/review_pressure.py`

Adjusts Tier 1 review pressure based on aggregate reviewer reputation while enforcing
the constitutional floor:

- **High reputation cohort** (`avg_r >= 0.80`): review window extended to 36h, auto-reminder suppressed
- **Standard cohort** (`0.60 ≤ avg_r < 0.80`): 24h window (current default)
- **Low reputation cohort** (`avg_r < 0.60`): window reduced to 12h, escalation triggered
- **Invariant:** Tier 0 surfaces always require human review — calibration cannot remove this gate

### M7-04 — Constitution v0.3.0: `reviewer_calibration` Rule

Bump `CONSTITUTION_VERSION` from `0.2.0` → `0.3.0`. New advisory rule:

```yaml
- id: reviewer_calibration
  tier: 1
  enforcement: advisory
  rationale: >
    Records reviewer reputation posture for telemetry. Advisory only —
    does not block mutations. Feeds the tier calibration engine.
  signals: [reputation_score, coverage_rate, calibration_consistency]
```

First new constitutional rule since v0.2.0. Advisory enforcement preserves fail-closed
invariants while surfacing governance health signals to operators.

### M7-05 — Aponi Reviewer Calibration Endpoint

`GET /governance/reviewer-calibration` — read-only dashboard endpoint returning:

```json
{
  "cohort_summary": {"high": 2, "standard": 4, "low": 0},
  "avg_reputation": 0.82,
  "tier_pressure": "extended",
  "constitutional_floor": "enforced"
}
```

**Acceptance criteria:**
- Reputation score is deterministic on identical ledger state ✅ (CI gate)
- Tier calibration never removes Tier 0 human-review requirement ✅ (invariant test)
- `CONSTITUTION_VERSION = "0.3.0"` in all environments after migration ✅
- `reviewer_calibration` rule verdict present in every governance telemetry event ✅
- Aponi endpoint returns 200 in `dev` and `staging` environments ✅

**PRs planned:** PR-7-01 (ledger) → PR-7-02 (scoring) → PR-7-03 (calibration) → PR-7-04 (constitution) → PR-7-05 (Aponi)

---

**Status:** ✅ complete · **Closed:** 2026-03-06

All Phase 0 Track A audit findings resolved. The platform is now hardened to InnovativeAI production standards with fail-closed boot validation, deterministic entropy, SPDX compliance, and unified CI gating.

| PR | Finding | Description | Closed |
|---|---|---|---|
| PR-CI-01 | H-01 | Unified Python version pin to `3.11.9` across all CI workflows | ✅ 2026-03-06 |
| PR-CI-02 | H-08 | SPDX license header enforcement wired always-on in CI | ✅ 2026-03-06 |
| PR-LINT-01 | H-05 | Determinism lint extended to `adaad/orchestrator/` | ✅ |
| PR-HARDEN-01 | C-01, H-02 | Boot env validation + signing key assertion (fail-closed) | ✅ |
| PR-SECURITY-01 | C-03 | Federation key pinning registry | ✅ |
| PR-PERF-01 | C-04 | Streaming lineage ledger verify path | ✅ |
| PR-OPS-01 | H-07, M-02 | Snapshot atomicity + sequence ordering | ✅ |
| PR-DOCS-01 | C-03 | Federation key registry governance doc | ✅ |

**Next gate:** Phase 7 ✅ closed (2026-03-08, v3.2.0) → Phase 8 · v3.3.0 target

---

## Phase 8 — Governance Health Dashboard & Telemetry Unification

**Status:** 🔵 planned · **Target:** v3.3.0 · **Requires:** Phase 7 shipped ✅

Phase 8 unifies the telemetry streams from Phase 7 (reviewer reputation), Phase 6
(autonomous roadmap amendment gates), and Phase 5 (federated convergence) into a
single authoritative **Governance Health Score** — a real-time, replay-safe composite
that operators can act on, not just observe.

### M8-01 — GovernanceHealthAggregator

`runtime/governance/health_aggregator.py`

Deterministic composite health score `h ∈ [0.0, 1.0]` derived from four live signals:

| Signal | Weight | Source |
|---|---|---|
| `avg_reviewer_reputation` | 0.30 | `ReviewerReputationLedger` via `reviewer_calibration_service()` |
| `amendment_gate_pass_rate` | 0.25 | `RoadmapAmendmentEngine.list_pending()` + gate verdicts |
| `federation_divergence_clean` | 0.25 | `FederatedEvidenceMatrix.divergence_count == 0` |
| `epoch_health_score` | 0.20 | `EpochTelemetry.health_score(last_10)` |

Scores are epoch-scoped; weight vector snapshotted per epoch (same invariant as Phase 7).
`h < 0.60` triggers `GOVERNANCE_HEALTH_DEGRADED` journal event and Aponi alert badge.

### M8-02 — HealthScore Evidence Binding

Every `GovernanceHealthAggregator` computation emits a `governance_health_snapshot.v1`
ledger event carrying: `epoch_id`, `health_score`, `signal_breakdown`, `weight_snapshot_digest`,
`constitution_version`, `scoring_algorithm_version`. Replay-safe: deterministic on identical
signal inputs and weight snapshot.

### M8-03 — Aponi Governance Health Panel

`GET /governance/health` — read-only endpoint returning current and rolling health scores.
Aponi dashboard gains a persistent health indicator: green (h ≥ 0.80), amber (0.60–0.80),
red (< 0.60). Badge is non-dismissible; degraded state surfaces signal breakdown for triage.

### M8-04 — Constitution v0.4.0: `governance_health_floor` Rule

New advisory rule that surfaces `h < 0.60` as a governance telemetry signal. When
`ADAAD_SEVERITY_ESCALATIONS` promotes it to `blocking`, a degraded health score halts
new amendment proposals until the floor is restored. `CONSTITUTION_VERSION` bumped
`0.3.0 → 0.4.0`.

**Acceptance criteria:**
- `h` is deterministic on identical signal inputs ✅ (CI gate)
- `GOVERNANCE_HEALTH_DEGRADED` event always emitted when `h < 0.60` ✅
- No signal input can unilaterally drive `h` to 0.0 or 1.0 (weight bounds enforced) ✅
- `GovernanceGate` remains sole mutation approval surface; health score is advisory ✅
- Aponi endpoint returns 200 with `constitutional_floor: enforced` field ✅

**PRs planned:** PR-8-01 (aggregator + evidence binding) → PR-8-02 (Aponi panel) → PR-8-03 (constitution v0.4.0)

---



| Milestone | Metric | Target | Status |
|-----------|--------|--------|--------|
| Phase 3 activation | `prediction_accuracy` | > 0.60 by epoch 20 | ✅ |
| Phase 3 activation | Acceptance rate | 0.20–0.60 stable | ✅ |
| Phase 4 semantic diff | Scoring determinism | 100% identical on identical AST | ✅ |
| Phase 5 federation | Cross-repo divergence | 0 divergences per federated epoch | ✅ |
| Phase 6 roadmap self-amendment | ArchitectAgent proposal governed | Human sign-off recorded in ledger | ✅ |
| Phase 7 reviewer reputation | Reputation score determinism | Identical on identical ledger state | ✅ |
| Phase 7 reviewer reputation | Constitutional floor | `CONSTITUTIONAL_FLOOR_MIN_REVIEWERS = 1` always enforced | ✅ |
| Phase 8 governance health | `avg_reputation` stability | ±0.05 variance over 10-epoch rolling window | 🔵 |
| Phase 25 admission control | `advisory_only` invariant | `advisory_only == True` on every AdmissionDecision | ✅ |
| Phase 25 admission control | Admission determinism | Identical inputs → identical digest | ✅ |
| Phase 26 admission rate | Signal weight sum | `sum(SIGNAL_WEIGHTS) == 1.0` | ✅ |
| Phase 26 admission rate | Tracker fail-safe | Empty history → `admission_rate_score == 1.0` | ✅ |
| Phase 27 admission audit | Append-only invariant | No record overwritten or deleted | ✅ |
| Phase 27 admission audit | Chain determinism | Identical decision sequence → identical chain hashes | ✅ |
| All phases | Evidence matrix | 100% Complete before promotion | ✅ |
| All phases | Replay proofs | 0 divergences in CI | ✅ |

---

## Phase 34 — Certifier Scans REST Endpoint

**Status:** ✅ shipped · **Released:** v5.9.0 · **Closed:** 2026-03-10 · **Requires:** Phase 33 shipped ✅

Phase 34 surfaces the `CertifierScanLedger` via a read-only authenticated REST
endpoint, completing the certifier audit surface and closing the Phase 33
observability gap. Mirrors `/governance/threat-scans` (Phase 30) pattern.

### Endpoint

```
GET /governance/certifier-scans
Authorization: Bearer <token with audit:read scope>
```

Query params: `limit` (int, default 20), `rejected_only` (bool, default false).

Response payload (under `data`):

| Field | Type | Description |
|-------|------|-------------|
| `records` | list | Certifier scan records (chronological) |
| `total_in_window` | int | Count of returned records |
| `rejection_rate` | float | Fraction of all scans REJECTED |
| `certification_rate` | float | Fraction of all scans CERTIFIED |
| `mutation_blocked_count` | int | Scans with mutation_blocked=True |
| `fail_closed_count` | int | Scans with fail_closed=True |
| `escalation_breakdown` | dict | escalation_level → count |
| `ledger_version` | str | `"33.0"` |

### Acceptance criteria

- `GET /governance/certifier-scans` returns 200 with full payload: **✅**
- Missing auth → 401: **✅**
- Insufficient scope → 403: **✅**
- `certification_rate + rejection_rate == 1.0`: **✅**
- `limit` and `rejected_only` params accepted: **✅**
- Read-only: no side effects on GovernanceGate authority: **✅**
- **12 tests** — `test_certifier_scans_endpoint.py` (T34-EP-01..12): **✅ 100%**

---

## Phase 33 — Certifier Scan Ledger & Rejection Rate Health Signal

**Status:** ✅ shipped · **Released:** v5.8.0 · **Closed:** 2026-03-10 · **Requires:** Phase 32 shipped ✅

Phase 33 closes the GateCertifier observability gap: scan results are persisted
in `CertifierScanLedger` (SHA-256 hash-chained append-only JSONL), and the certifier
rejection rate becomes the 8th governance health signal (`certifier_rejection_rate_score`,
weight 0.07). All 8 signals sum to 1.00.

### Signal normalisation

    certifier_health = 1.0 - rejection_rate

- `rejection_rate == 0.0` → `1.0` (all scans certified, pristine)
- `rejection_rate == 1.0` → `0.0` (all scans rejected, fully degraded)
- No reader / empty history / exception → `1.0` (fail-safe)

### Weight table (post-Phase 33)

| Signal | Weight | Source |
|--------|--------|--------|
| `avg_reviewer_reputation` | 0.19 | `ReviewerReputationLedger` (Ph.7) |
| `amendment_gate_pass_rate` | 0.17 | `RoadmapAmendmentEngine` (Ph.6) |
| `federation_divergence_clean` | 0.17 | `FederatedEvidenceMatrix` (Ph.5) |
| `epoch_health_score` | 0.12 | `EpochTelemetry` (core) |
| `routing_health_score` | 0.10 | `StrategyAnalyticsEngine` (Ph.22) |
| `admission_rate_score` | 0.09 | `AdmissionRateTracker` (Ph.26) |
| `governance_debt_health_score` | 0.09 | `GovernanceDebtLedger` (Ph.32) |
| `certifier_rejection_rate_score` | 0.07 | `CertifierScanReader` (Ph.33) |

### Acceptance criteria

- `CertifierScanLedger.emit()` persists scan into hash-chained JSONL: **✅**
- Chain verifies after multiple emits: **✅**
- Chain resumes correctly on reopen: **✅**
- `CertifierScanReader.rejection_rate()` correct: **✅**
- `certifier_rejection_rate_score` in `signal_breakdown`: **✅**
- Fail-safe `1.0` on no reader / empty history / exception: **✅**
- `HealthSnapshot.certifier_report` populated with 4 required fields: **✅**
- Weight sum == 1.00 after rebalance (CI-enforced): **✅**
- Backward compat: callers without `certifier_scan_reader` unaffected: **✅**
- **38 tests** — `test_certifier_scan_ledger.py` (T33-L01..L12, R01..R08, S01..S18): **✅ 100%**

---

## Phase 32 — Governance Debt Health Signal Integration

**Status:** ✅ shipped · **Released:** v5.7.0 · **Closed:** 2026-03-10 · **Requires:** Phase 31 shipped ✅

Phase 32 closes the integration gap between the `GovernanceDebtLedger` (Phase 31)
and the `GovernanceHealthAggregator`. `compound_debt_score` is now wired as the
7th governance health signal, normalized to `[0.0, 1.0]` with weight `0.10`.
All other signals rebalanced proportionally; weight sum invariant preserved at `1.00`.

### Signal normalisation

    debt_health = max(0.0, 1.0 − compound_debt_score / breach_threshold)

- `compound_debt_score == 0` → `1.0` (pristine)
- `compound_debt_score >= breach_threshold` → `0.0` (fully breached)
- No ledger / no snapshot / `breach_threshold ≤ 0` → `1.0` (fail-safe)

### Weight table (post-Phase 32)

| Signal | Weight | Source |
|--------|--------|--------|
| `avg_reviewer_reputation` | 0.20 | `ReviewerReputationLedger` (Ph.7) |
| `amendment_gate_pass_rate` | 0.18 | `RoadmapAmendmentEngine` (Ph.6) |
| `federation_divergence_clean` | 0.18 | `FederatedEvidenceMatrix` (Ph.5) |
| `epoch_health_score` | 0.13 | `EpochTelemetry` (core) |
| `routing_health_score` | 0.11 | `StrategyAnalyticsEngine` (Ph.22) |
| `admission_rate_score` | 0.10 | `AdmissionRateTracker` (Ph.26) |
| `governance_debt_health_score` | 0.10 | `GovernanceDebtLedger` (Ph.31) |

### Acceptance criteria

- `governance_debt_health_score` in `HealthSnapshot.signal_breakdown`: **✅**
- Fail-safe `1.0` on no ledger, no snapshot, `breach_threshold ≤ 0`, exception: **✅**
- `HealthSnapshot.debt_report` populated with 6 required fields: **✅**
- Weight sum == 1.00 after rebalance (CI-enforced): **✅**
- All weights individually in `(0.0, 1.0)`: **✅**
- Determinism: identical inputs → identical score: **✅**
- Backward compat: callers without `debt_ledger` unaffected: **✅**
- Breach drives `h` below no-debt baseline: **✅**
- **23 tests** — `test_debt_health_signal.py` (T32-01..22): **✅ 100%**

---

## Phase 31 — Governance Debt & Gate Certifier Endpoints

**Status:** ✅ shipped · **Released:** v5.6.0 · **Closed:** 2026-03-10 · **Requires:** Phase 30 shipped ✅

Phase 31 closes the last two API surface gaps: GovernanceDebtLedger and
GateCertifier had no REST endpoints. Operators can now inspect live debt
snapshots and run security certification scans via authenticated endpoints.

### Acceptance criteria

- GET /governance/debt returns 200 with full snapshot payload: **✅**
- Debt schema_version, snapshot_hash, threshold_breached all present: **✅**
- Zero-state fallback when no live epoch data: **✅**
- POST /governance/certify returns CERTIFIED | REJECTED with checks breakdown: **✅**
- Absolute paths and path traversal rejected with 422: **✅**
- GovernanceGate authority boundary preserved (both endpoints advisory/read-only): **✅**
- **41 tests**: unit (21) + endpoint (20): **✅**

---

## Phase 30 — Threat Scan Ledger & Endpoint

**Status:** ✅ shipped · **Released:** v5.5.0 · **Closed:** 2026-03-10 · **Requires:** Phase 29 shipped ✅

Phase 30 closes the ThreatMonitor observability gap by adding a hash-chained
audit ledger for scan results and a read-only API endpoint for operator triage.

### Constitutional invariants

- Append-only: no record is overwritten or deleted.
- Deterministic replay: same scan sequence → same chain hashes.
- GovernanceGate authority unchanged.
- Emit failure isolation: I/O errors never propagate.

### Acceptance criteria

- ThreatScanLedger.emit(scan) persists scan into hash-chained JSONL: **✅**
- Chain verifies after multiple emits: **✅**
- Chain resumes correctly on reopen: **✅**
- Real ThreatMonitor scan output accepted: **✅**
- triggered_rate() / escalation_rate() / avg_risk_score() correct: **✅**
- GET /governance/threat-scans returns 200 with full payload: **✅**
- **46 tests**: unit (36) + endpoint (10): **✅**

---

## Phase 29 — Enforcement Verdict Audit Binding

**Status:** ✅ shipped · **Released:** v5.4.0 · **Closed:** 2026-03-10 · **Requires:** Phase 28 shipped ✅

Phase 29 closes the enforcement audit loop by extending AdmissionAuditLedger
to persist EnforcerVerdict fields alongside AdmissionDecision in the hash-chained
JSONL ledger. Enforcement escalation state is now cryptographically anchored and
replay-verifiable, matching the audit-depth of the admission-control arc.

### Constitutional invariants

- Chain hash determinism preserved: enforcement fields are part of the chained payload covered by record_hash.
- Backward-compatible: existing callers without verdict get enforcement_present=False / null fields.
- GovernanceGate authority boundary unchanged.
- Emit failure isolation: I/O errors never propagate to callers.

### Acceptance criteria

- emit(decision, verdict=verdict) persists all 5 enforcement fields into record: **✅**
- emit(decision) (no verdict) sets enforcement_present=False and fields to None: **✅**
- Chain verifies after mixed verdict/no-verdict emits: **✅**
- record_hash differs between verdict-carrying and plain records: **✅**
- blocked_count() / enforcement_rate() / escalation_mode_breakdown() correct: **✅**
- GET /governance/admission-audit returns blocked_count, enforcement_rate, escalation_breakdown: **✅**
- ledger_version bumped to 29.0: **✅**
- **36 tests**: unit (30) + endpoint (6): **✅**

---

## Phase 28 — Admission Band Enforcement Binding

**Status:** ✅ shipped · **Released:** v5.3.0 · **Closed:** 2026-03-10 · **Requires:** Phase 27 shipped ✅

Phase 28 wires the advisory AdmissionDecision into an enforcement layer that
can be escalated from advisory to blocking via ADAAD_SEVERITY_ESCALATIONS,
enabling operators to activate an emergency-stop on HALT-band mutation proposals
without granting GovernanceGate bypass authority.

### Constitutional invariants

- `advisory_only: True` is structurally preserved on AdmissionDecision; enforcer only sets its own `blocked` flag.
- AdmissionBandEnforcer never imports or calls GovernanceGate.
- `blocked=True` only when `escalation_mode == "blocking"` AND `admission_band == "halt"`.
- Fail-safe: invalid or absent health_score defaults to GREEN (1.0) — never silently stalls pipeline.
- Deterministic: identical (health_score, risk_score, escalation_config) → identical verdict_digest.

### Acceptance criteria

- Advisory mode (default): `blocked` always `False` regardless of band: **✅**
- Blocking mode, green/amber/red bands: `blocked` always `False`: **✅**
- Blocking mode, halt band: `blocked == True` with non-empty block_reason: **✅**
- ADAAD_SEVERITY_ESCALATIONS parsing: advisory/blocking/invalid/missing all handled: **✅**
- Verdict digest determinism: identical inputs → identical sha256: **✅**
- `GET /governance/admission-enforcement` returns 200 with full payload: **✅**
- Authority boundary: no GovernanceGate import in enforcer module: **✅**
- **39 tests**: unit (29) + endpoint (10): **✅**

---

## Phase 27 — Admission Audit Ledger

**Status:** ✅ shipped · **Released:** v5.2.0 · **Closed:** 2026-03-10 · **Requires:** Phase 25 shipped ✅

Phase 27 makes every `AdmissionDecision` evidence-bound via a SHA-256
hash-chained append-only JSONL ledger, bringing admission control to full
audit parity with the pressure adjustment surface (Phase 25 remote).

### Constitutional invariants

- `AdmissionAuditLedger` never imports or calls `GovernanceGate`.
- Append-only: no record is ever overwritten or deleted.
- Fail-closed chain verification: any hash mismatch → `AdmissionAuditChainError`.
- `emit()` failure isolation: I/O errors logged and swallowed; caller unaffected.
- Timestamp excluded from `record_hash` — chain is wall-clock independent.
- Deterministic replay: identical decision sequence → identical chain hashes.

### Acceptance criteria

- `emit()` creates file and appends hash-chained JSONL records: **✅**
- `chain_verify_on_open=True` raises on tampered records: **✅**
- Inactive ledger (`path=None`) emits no file and never raises: **✅**
- `AdmissionAuditReader.admission_rate()` defaults to `1.0` on empty: **✅**
- `GET /governance/admission-audit` returns records with band/rate summary: **✅**
- **36 tests**: `test_admission_audit_ledger.py` (36): **✅**

---



---

## Phase 26 — Admission Rate Signal Integration

**Status:** ✅ shipped · **Released:** v5.1.0 · **Closed:** 2026-03-10 · **Requires:** Phase 25 shipped ✅

Phase 26 closes the Phase 25 feedback loop: the rolling admission rate from
`AdmissionRateTracker` becomes the sixth governance health signal, creating
a self-reinforcing governance feedback cycle — sustained health pressure
→ mutations deferred → admission rate drops → composite health score
degrades further — entirely within the advisory surface, with GovernanceGate
authority inviolate throughout.

### Constitutional invariants

- `AdmissionRateTracker` never imports or calls `GovernanceGate`.
- `admission_rate_score` is advisory input to `h`, which is itself advisory.
- Weight sum invariant: `sum(SIGNAL_WEIGHTS.values()) == 1.0` (CI-enforced).
- Fail-safe: empty history returns `1.0`; exceptions default to `1.0`.
- Deterministic: identical decision sequence → identical digest.

### Signal weight table (post-Phase 26)

| Signal | Weight | Source |
|--------|--------|--------|
| `avg_reviewer_reputation` | 0.22 | `ReviewerReputationLedger` (Ph.7) |
| `amendment_gate_pass_rate` | 0.20 | `RoadmapAmendmentEngine` (Ph.6) |
| `federation_divergence_clean` | 0.20 | `FederatedEvidenceMatrix` (Ph.5) |
| `epoch_health_score` | 0.15 | `EpochTelemetry` (core) |
| `routing_health_score` | 0.13 | `StrategyAnalyticsEngine` (Ph.22) |
| `admission_rate_score` | 0.10 | `AdmissionRateTracker` (Ph.26) |

### Acceptance criteria

- `admission_rate_score` wired into `GovernanceHealthAggregator`: **✅**
- Empty history → `admission_rate_score == 1.0` fail-safe: **✅**
- `HealthSnapshot.admission_rate_report` populated when tracker wired: **✅**
- Weight sum invariant preserved after rebalance: **✅**
- `GET /governance/admission-rate` returns full `AdmissionRateReport`: **✅**
- **34 tests**: `test_admission_tracker.py` (26) + `test_admission_rate_endpoint.py` (8): **✅**

---



---

## Phase 25 — Mutation Admission Control

**Status:** ✅ shipped · **Released:** v5.0.0 · **Closed:** 2026-03-10 · **Requires:** Phase 24 shipped ✅

Phase 25 closes the health→action feedback loop: `MutationAdmissionController`
translates the composite governance health score into a per-mutation advisory
admission decision, deferring high-risk candidates when health degrades and
issuing an epoch-pause advisory at catastrophic health levels.

### Constitutional invariants

- `advisory_only: True` — GovernanceGate retains sole mutation-approval authority.
- `MutationAdmissionController` never imports or calls `GovernanceGate`.
- `epoch_paused` advisory is informational only; operator and GovernanceGate decide.
- Deterministic: identical `(health_score, mutation_risk_score)` → identical digest.
- Fail-safe: out-of-range inputs clamped, never raised.

### Admission band mapping (constitutional)

| Band  | health_score        | risk_threshold | admits_all | epoch_paused |
|-------|---------------------|----------------|------------|--------------|
| GREEN | h ≥ 0.80            | 1.01 (all)     | True       | False        |
| AMBER | 0.60 ≤ h < 0.80     | 0.60           | False      | False        |
| RED   | 0.40 ≤ h < 0.60     | 0.35           | False      | False        |
| HALT  | h < 0.40            | 0.00 (none)    | False      | True (advisory) |

### Acceptance criteria

- GREEN band: all mutations admitted regardless of risk_score: **✅**
- AMBER band: `risk_score ≥ 0.60` mutations deferred: **✅**
- RED band: only `risk_score < 0.35` mutations admitted: **✅**
- HALT band: no mutations admitted; `epoch_paused = True` advisory: **✅**
- `advisory_only` structurally `True` on every path: **✅**
- `GET /governance/admission-status` returns full `AdmissionDecision`: **✅**
- **44 tests**: `test_mutation_admission.py` (32) + `test_admission_status_endpoint.py` (12): **✅**

---

## What will not be built

To maintain constitutional clarity:

- **No autonomous promotion** — The pipeline never promotes a mutation to production without human sign-off. GovernanceGate cannot be delegated.
- **No non-deterministic entropy** in governance decisions — Randomness is only allowed in agent proposals (seeded from epoch_id), never in scoring or gate evaluation.
- **No retroactive evidence** — Evidence cannot be added after a release is tagged.
- **No silent failures** — Every pipeline halt produces a named failure mode in the evidence ledger.

---

*This roadmap is governed by `docs/CONSTITUTION.md` and `docs/governance/ARCHITECT_SPEC_v2.0.0.md`. Amendments require ArchitectAgent approval and a CHANGELOG entry.*
