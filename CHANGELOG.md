# CHANGELOG

Generated deterministically from merged governance metadata.

## [9.13.0] — 2026-03-19 — Phase 78

- PR ID: `PR-PHASE78-01`
- Title: Phase 78 — Journal Warm-Cache (M78-01) + Autonomous Doc Sync (M78-02)
- Lane/Tier: `runtime` / `hardening`
- Evidence refs: `phase78-journal-warm-cache`, `phase78-doc-autosync`
- Delivered:
  - **M78-01** `security/ledger/journal.py` — `_VERIFIED_TAIL_CACHE: dict[str, tuple[str,int]]` path-keyed warm-cache; O(n²) → O(n) repeated-append conversion (11.6× speedup; p99 ≤ 200 ms on 10 000-entry journal). `stat()`-based external-write detection covers multi-process pool-worker stale-cache. `invalidate_journal_cache(path)` exported for test isolation (JOURNAL-ISOLATE-0). `test_journal_integrity.py` updated to document C-04 tamper-detection contract.
  - **M78-02** `scripts/verify_doc_sync.py` — determinism gate: asserts README ADAAD badge, PyPI badge, hero alt, stats-card alt, and VERSION_INFOBOX all match `VERSION` file; exits 0 on clean, 1 on drift (DOC-SYNC-NO-BYPASS-0). `.github/workflows/docs-autosync.yml` — autonomous post-merge sync workflow with `[skip ci]` commit.
  - 23 new tests: T78-CACHE-01..08 + T78-PERF-01 + T78-SYNC-01..06 (all passing).
- Key invariants: `JOURNAL-CACHE-0`, `JOURNAL-CACHE-DETERM-0`, `JOURNAL-ISOLATE-0`, `DOC-SYNC-VERSION-0`, `DOC-SYNC-DETERM-0`, `DOC-SYNC-NO-BYPASS-0`

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
