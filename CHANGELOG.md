# CHANGELOG

Generated deterministically from merged governance metadata.

## [9.15.0] — 2026-03-20 — Phase 80 Complete (Multi-Generation Compound Evolution)

### Phase 80 — Multi-Seed Competitive Epoch

#### Track A — Multi-Seed Competition Infrastructure (#PR-80-01)

- `runtime/seed_competition.py` — `SeedCompetitionOrchestrator` (new): population-level competitive epoch runner
  - `SeedCandidate` (frozen dataclass): candidate_id + fitness_context + metadata
  - `CompetitionResult` (frozen dataclass): epoch_id, winner_id, ranked_ids, fitness_scores, gate_verdict, competition_digest
  - `_rank_candidates()`: deterministic fitness ranking, tie-break by lexicographic candidate_id
  - `_competition_digest()`: SHA-256 of canonical sorted inputs (SEED-RANK-0)
- `runtime/evolution/lineage_v2.py` — `SeedCompetitionEpochEvent` (frozen dataclass) + `append_competition_epoch()` on `LineageLedgerV2`
- `runtime/fitness_pipeline.py` — `rank_seeds_by_fitness()`: multi-seed ranking surface using FitnessOrchestrator
- `tests/test_phase80_seed_competition.py` — 24 constitutional tests T80-COMP-01..24 (24/24 pass)
- `artifacts/governance/phase80/track_a_sign_off.json` — governance sign-off artifact
- `pytest.ini` — phase80 mark registered

**Invariants introduced:**
- `SEED-COMP-0`: No seed promoted without competitive ranking of all candidates in epoch window
- `SEED-RANK-0`: Fitness ranking deterministic — equal inputs → identical rank orderings; ties lexicographic
- `COMP-GOV-0`: GovernanceGate evaluates all candidates before any single candidate advances
- `COMP-LEDGER-0`: `SeedCompetitionEpochEvent` written to `LineageLedgerV2` before any promotion

#### Track B — GA Unblock Sprint (#PR-80-02)

- `android/fdroid/com.innovativeai.adaad.yml` — v9.14.0 build entry (versionCode 91400); `CurrentVersion` → 9.14.0
- `docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md` — § 2.3 updated: v1.1-GA canonical declaration (closes FINDING-H04-GA-VERSIONING pending Gate 4); phase80 node added to automation contract
- `docs/IP_PATENT_FILING_ARTIFACT.md` — Phase 80 Track B transmittal checklist + H-03 filing instructions appended

**HUMAN-0 gate actions (non-delegable — not included in this release):**
- Gate 3: F-Droid MR submission (Dustin)
- Gate 4: GPG v1.1-GA sign-off commit (Dustin)
- C-02: GPG tag ceremony v9.7.0–v9.10.0 (Dustin)
- H-03: Patent counsel engagement + provisional filing (Dustin)

### Metrics at v9.15.0
- Tests: 4,772+ passing (+24)
- Phases complete: 80
- Constitutional invariants: 27 (+4)
- Seed competition: population-level competitive epoch now operational

## [9.14.0] — 2026-03-20 — Phases 78 + 79 + Thesis

### Phase 78 — Production Signing Infrastructure + Aponi GitHub Feed + Doc Autosync

- **M78-01 Journal warm-cache** (`JOURNAL-CACHE-0`): 9 constitutional tests confirming O(n) append performance, tamper detection, and cross-instance isolation
- **M78-02 Autonomous Doc Sync** (`DOC-SYNC-VERSION-0`): `.github/workflows/docs-autosync.yml` triggers on VERSION/CHANGELOG/ROADMAP push; `scripts/verify_doc_sync.py` exits 1 on any version drift
- **Ed25519/HMAC production signers** (`LEDGER-SIGN-0`): `HMACEnvSigner` (ADAAD_LEDGER_HMAC_SECRET), `Ed25519FileSigner` (ADAAD_SIGNING_KEY_PATH), `build_signer_from_env()` priority factory. 21 tests
- **Aponi GitHub Feed Panel**: `data-view="github"` nav, `loadGithubFeed()` async, event-type-keyed CSS classes (push/pr/ci/slash/install/rejected), governance bridge fallback. 16 tests
- Total: 46 new tests

### Phase 79 — Multi-Generation Lineage Graph

- `runtime/evolution/multi_gen_lineage.py`: `GenerationNode` (frozen dataclass, `node_digest`), `MultiGenLineageGraph` (DAG: `register_node`, `ancestor_path`, `descendant_set`, `generation_summary`, `graph_digest`, `to_dict`, `from_ledger`)
- `MULTIGEN-0`: every node ledger-anchored; `MULTIGEN-ACYC-0`: DAG, cycles structurally impossible; `MULTIGEN-DETERM-0`: identical ledger → identical `graph_digest`; `MULTIGEN-REPLAY-0`: graph reconstructable from ledger alone; `MULTIGEN-ISOLATE-0`: no shared state
- Foundation for Phase 80 compound evolution
- 26 tests

### Thesis

- `docs/thesis/ADAAD_THESIS.md`: 500-line comprehensive technical thesis covering architecture, all 23 constitutional invariants, proven capabilities, operator model, current live state, and evolution trajectory

### Metrics at v9.14.0
- Tests: 4,748+ passing
- Phases complete: 79
- Constitutional invariants: 23
- Evidence ledger entries: 12,441+

## [9.13.0] — 2026-03-20 — Phase 77 Complete (Track A + Track B)

### Track A — Constitutional Governance Infrastructure (#PR-77-01)

- PR ID: `PR-77-01`
- Title: Close 4 constitutional stubs — ABC enforcement + webhook consolidation
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase77-track-a-abc-enforcement`, `phase77-webhook-shim-deleg-0`
- Closes: `FINDING-AUDIT-C03` remnant (dual webhook handler) + 3 `NotImplementedError` stubs
- Delivered:
  - `runtime/evolution/event_signing.py` — `EventSigner` / `EventVerifier` → proper ABC (`EVENT-SIGN-ABSTRACT-0`)
  - `runtime/innovations.py` — `GovernancePlugin.evaluate()` → proper ABC (`GPLUGIN-ABSTRACT-0`)
  - `runtime/fitness_pipeline.py` — `FitnessEvaluator` abstractmethod contract clarified
  - `runtime/integrations/github_webhook_handler.py` — replaced with governed shim delegating 100% to `app.github_app` (`WEBHOOK-SHIM-DELEG-0` / `WEBHOOK-SHIM-COMPAT-0`)
  - 26 constitutional closure tests (`tests/test_phase77_track_a_close.py`)
- Key invariants: `EVENT-SIGN-ABSTRACT-0`, `GPLUGIN-ABSTRACT-0`, `WEBHOOK-SHIM-DELEG-0`, `WEBHOOK-SHIM-COMPAT-0`

### Track B — First Seed Epoch Run (#PR-77-02)

- PR ID: `PR-77-02`
- Title: First Seed Epoch Run — SEED-LIFECYCLE-COMPLETE-0 demonstrated
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `artifacts/governance/phase77/seed_epoch_run_evidence.json`
- run_digest: `sha256:b3a41c40b99177dc51d5cfdd43d826c27aa7bf718f93fd936f7a5658869590ab`
- Milestone: **First live demonstration of end-to-end Seed Lifecycle Pipeline** (Phases 71–76)
- Delivered:
  - `scripts/run_phase77_seed_epoch.py` — reproducible 7-step pipeline executor
  - `artifacts/governance/phase77/seed_epoch_run_evidence.json` — inaugural `EpochEvidence` artifact
  - Full pipeline executed: `CapabilitySeed` → `SeedPromotionQueue` → human review → `ProposalRequest` → CEL injection → `LiveWiredCEL.run_epoch()` (14 steps) → `SeedCELOutcomeEvent`
  - 27 constitutional tests (`tests/test_phase77_track_b_seed_epoch.py`)
- Key invariants demonstrated: `SEED-LIFECYCLE-COMPLETE-0`, `SEED-PROMO-0`, `SEED-REVIEW-HUMAN-0`, `SEED-PROP-LEDGER-0`, `SEED-CEL-AUDIT-0`, `SEED-OUTCOME-AUDIT-0`, `CEL-ORDER-0`
- Total: 53 new tests | 150 passing across affected modules | 0 regressions
- Governor: Dustin L. Reid — 2026-03-20

## [9.12.1] — 2026-03-19 — Optimize: 7-Fault Sweep

- PR ID: `PR-508-OPTIMIZE-v9.12.1`
- Title: Optimize — 7-fault sweep (warm-cache regression · constitution version drift · import contracts · GitHub App wiring)
- Lane/Tier: `runtime` / `hotfix`
- Evidence refs: `optimize-warm-cache-lineage-v2`, `optimize-constitution-version-drift`, `optimize-import-contracts`, `optimize-github-app-wiring`
- Fixes:
  - `runtime/evolution/lineage_v2.py` — O(n→n²) warm-cache regression in `append_event()`; `_verified_tail_hash` now advanced post-append (C-04 contract)
  - `app/github_app.py` — governance event emission wiring completed
  - `app/main.py` — import contract alignment (5 modules)
  - Test suite: `test_lineage_v2_streaming`, `test_replay_attestation_determinism`, `test_constitution_*` — version constant sync
- Phase 78 note: Journal-level `_VERIFIED_TAIL_CACHE` (11.6× speedup, 1700ms→146ms) deferred — shared journal test-isolation pre-condition required first

## [9.12.0] — 2026-03-19 — Phase 77

- PR ID: `PR-PHASE77-01`
- Title: GitHub App Governance + Constitution Version Alignment
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase77-github-audit-bridge`, `phase77-external-event-bridge`, `phase77-constitution-version-0.9.0`
- Closes: `FINDING-AUDIT-C03` — `app/github_app.py` and `runtime/integrations/github_webhook_handler.py` governance gap
- Delivered:
  - `runtime/governance/external_event_bridge.py` — SHA-256 hash-chained JSONL audit ledger
  - `ExternalGovernanceSignal` emitted for mutation-class events (`push.main`, `pr.merged`, `ci.failure`)
  - `app/github_app._emit_governance_event` wired to bridge keyword API
  - `CONSTITUTION_VERSION` updated `"0.7.0"` → `"0.9.0"` in 3 runtime files + `constitution.yaml`
  - All 31 Phase-77 tests passing (T77-BRG-01..10, T77-SIG-01..06, T77-CHAIN-01..04, T77-WIRE-01..03, T77-CONST-01..03, T77-IDEM-01..02)
- Key invariants: `GITHUB-AUDIT-0`, `GITHUB-GATE-OBS-0`, `GITHUB-SIG-CLOSED-0`, `GITHUB-DETERM-0`, `GITHUB-FAILSAFE-0`, `GITHUB-GATE-ISO-0`

## [9.11.0] — 2026-03-15 — Phase 76

- PR ID: `PR-PHASE76-01`
- Title: Seed CEL Outcome Recorder
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.10.0] — 2026-03-14 — Phase 75

- PR ID: `PR-PHASE75-01`
- Title: Seed Proposal CEL Injection
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.9.0] — 2026-03-14 — Phase 74

- PR ID: `PR-PHASE74-01`
- Title: Seed-to-Proposal Bridge
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.8.0] — 2026-03-14 — Phase 73

- PR ID: `PR-PHASE73-01`
- Title: Seed Review Decision + Governance Wire
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.7.0] — 2026-03-14 — Phase 72

- PR ID: `PR-PHASE72-01`
- Title: Seed Promotion Queue + Graduation UI
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.6.0] — 2026-03-14 — Phase 71

- PR ID: `PR-PHASE71-01`
- Title: Oracle Persistence + Seed Evolution
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.5.0] — 2026-03-14 — Phase 70

- PR ID: `PR-PHASE70-01`
- Title: WebSocket Live Epoch Feed
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.4.0] — 2026-03-14 — Phase 69

- PR ID: `PR-PHASE69-01`
- Title: Aponi Innovations UI
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.3.0] — 2026-03-14 — Phase 68

- PR ID: `PR-PHASE68-01`
- Title: Full Innovations Orchestration
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.2.0] — 2026-03-14 — Phase 67

- PR ID: `PR-PHASE67-01`
- Title: Innovations Wiring (CEL)
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.1.0] — 2026-03-14 — Phase 66

- PR ID: `PR-PHASE66-01`
- Title: Doc Alignment + Deep Dive
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [9.0.0] — unknown-date — Phase 65

- PR ID: `PR-PHASE65-01`
- Title: Emergence — First Autonomous Capability Evolution
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase65-preflight-determinism-import-hardening`

## [8.7.0] — unknown-date — Phase 64

- PR ID: `PR-PHASE64-01`
- Title: Phase 64
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [8.6.0] — unknown-date — Phase 63

- PR ID: `PR-PHASE63-01`
- Title: Phase 63
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [8.5.0] — unknown-date — Phase 62

- PR ID: `PR-PHASE62-01`
- Title: Phase 62
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: _none_

## [8.4.0] — unknown-date — Phase 61

- PR ID: `PR-PHASE61-01`
- Title: Phase 61
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase61-ci-tier-gating-enforced`, `phase61-critical-file-budget-enforced`, `phase61-legacy-path-reduction-target`, `phase61-lineage-engine-v840`, `phase61-metrics-schema-coverage-100`, `phase61-runtime-cost-and-experiment-caps`

## [8.3.0] — unknown-date — Phase 60

- PR ID: `PR-PHASE60-01`
- Title: Phase 60
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase60-ast-mutation-substrate-sandbox-v830`

## [8.2.0] — unknown-date — Phase 59

- PR ID: `PR-PHASE59-01`
- Title: Phase 59
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase59-capability-graph-v2-v820`

## [8.1.0] — unknown-date — Phase 58

- PR ID: `PR-PHASE58-01`
- Title: Phase 58
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase58-code-intelligence-layer-v810`

## [8.0.0] — unknown-date — Phase 57

- PR ID: `PR-PHASE57-01`
- Title: Phase 57
- Lane/Tier: `governance` / `constitutional`
- Evidence refs: `phase57-proposal-engine-autoprovisioning`

## [7.5.0] — 2026-03-12 — Phase 51

- PR ID: `PR-PHASE51-01`
- Title: Phase 51
- Lane/Tier: `governance` / `standard`
- Evidence refs: _none_

## [7.4.0] — unknown-date — Phase 50

- PR ID: `PR-PHASE50-01`
- Title: Phase 50
- Lane/Tier: `governance` / `standard`
- Evidence refs: _none_

## [7.3.0] — 2026-03-12 — Phase 49

- PR ID: `PR-PHASE49-01`
- Title: Phase 49
- Lane/Tier: `governance` / `standard`
- Evidence refs: _none_

## [7.2.0] — 2026-03-12 — Phase 48

- PR ID: `PR-PHASE48-01`
- Title: Phase 48
- Lane/Tier: `governance` / `standard`
- Evidence refs: _none_

## [7.1.0] — 2026-03-12 — Phase 47

- PR ID: `PR-PHASE47-01`
- Title: Phase 47
- Lane/Tier: `governance` / `standard`
- Evidence refs: _none_
