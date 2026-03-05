# Changelog

## [Unreleased]

### ADAAD-10 — Live Market Signal Adapters (v1.4)

- **PR-10-02 — POST /market/signal webhook endpoint + integration tests:** `server.py` gains `POST /market/signal` bearer-auth-gated endpoint routing raw payloads through `LiveSignalRouter` → lineage-stamped `MarketSignalReading` → fitness advisory injection; journal event `market_signal_ingested.v1`. `tests/test_market_fitness_integrator.py`: 11 tests covering integrator bridging (live, synthetic fallback, lineage propagation, journal), `FitnessOrchestrator.inject_live_signal()` override (score override, no-override passthrough, clamping, bad epoch silent drop). ADAAD-10 Track A complete.

- **PR-10-01 — FeedRegistry + concrete adapters + schema:** `runtime/market/feed_registry.py` — deterministic adapter ordering, TTL caching, fail-closed stale guard, confidence-weighted composite score. `runtime/market/adapters/live_adapters.py` — `VolatilityIndexAdapter` (inverted market stress), `ResourcePriceAdapter` (normalised compute cost), `DemandSignalAdapter` (DAU/WAU/retention composite). `schemas/market_signal_reading.v1.json` — validated signal reading schema. 19 tests in `tests/market/test_feed_registry.py`.

### ADAAD-9 — Developer Experience (v1.3)

- **PR-9-03 — Phase 5: Simulation Panel Integration (D3):** `ui/aponi/simulation_panel.js` delivers the inline simulation panel within the Aponi IDE proposal editor workflow. Wires `POST /simulation/run` and `GET /simulation/results/{run_id}` (Epic 2 / ADAAD-8 endpoints) with pre-populated constitution constraint defaults from `/simulation/context`. Surfaces comparative outcomes (actual vs simulated, delta per metric) and provenance (deterministic flag, replay seed) inline without navigation. `ui/aponi/index.html` gains section '04 · Inline Simulation' with `proposalSimulationPanel`, `simulationRun`, `simulationResults` IDs (required by `test_simulation_submission_and_inline_result_rendering`). Android epoch range limit honoured from context. Authority invariant maintained: panel authors simulation requests only; execution authority remains with GovernanceGate.
- **PR-9-02 — Phase 4: Replay Inspector e2e test extension (D5):** `tests/test_aponi_dashboard_e2e.py` extended with 4 new inspector tests: epoch chain coverage (last-N epochs in `proof_status`), canonical digest surfacing in replay diff, divergence alert visual distinction markers, and lineage navigation from a mutation to its full ancestor chain. All tests verify the existing `replay_inspector.js` + `/replay/diff` + `/replay/divergence` surface against the EPIC_3 D5 acceptance criteria.
- **PR-9-01 — Phase 3: Evidence Viewer (D4):** `ui/aponi/evidence_viewer.js` delivers a read-only, bearer-auth-gated evidence bundle inspector within the Aponi IDE. Fetches from `GET /evidence/{bundle_id}` and renders provenance fields (`bundle_id`, `constitution_version`, `scoring_algorithm_version`, `governor_version`, fitness/goal hashes), risk summaries (with high-risk highlighting), export metadata with signer fields, sandbox snapshot, and replay proof chain. `ui/aponi/index.html` gains section 03 · Evidence Viewer and wires `evidence_viewer.js` and `proposal_editor.js` as separate script modules. `tests/test_evidence_viewer.py` added: 17 tests covering schema conformance against `schemas/evidence_bundle.v1.json`, provenance field presence, auth gating, determinism, and high-risk flag propagation.

### ADAAD-8 — Policy Simulation Mode (v1.2)

- **PR-10 — DSL Grammar + Constraint Interpreter:** `runtime/governance/simulation/constraint_interpreter.py` delivers `SimulationPolicy` (frozen dataclass, `simulation=True` structurally enforced) and `interpret_policy_block()`. 10 constraint types: approval thresholds, risk ceilings, rate limits, complexity deltas, tier lockdowns, rule assertions, coverage floors, entropy caps, reviewer escalation, lineage depth requirements. `schemas/governance_simulation_policy.v1.json` schema-enforces `simulation: true`. 50 tests.
- **PR-11 — Epoch Replay Simulator + Isolation Invariant:** `runtime/governance/simulation/epoch_simulator.py` delivers `EpochReplaySimulator` as a read-only substrate over `ReplayEngine`. `SimulationPolicy.simulation=True` checked at `GovernanceGate` boundary before any evaluation. Zero ledger writes, zero constitution state transitions, zero mutation executor calls during simulation. `EpochSimulationResult` and `SimulationRunResult` are frozen dataclasses with deterministic `policy_digest` and `run_digest`. 38 tests including explicit isolation assertion tests.
- **PR-12 — Aponi Simulation Endpoints:** `POST /simulation/run` and `GET /simulation/results/{run_id}` added to `server.py`. Both bearer-auth gated (`audit:read` scope). `simulation: true` structurally present in all responses. `simulation_only_notice` always in `POST` response. 422 on DSL parse error. 11 tests.
- **PR-13 — Governance Profile Exporter (milestone):** `runtime/governance/simulation/profile_exporter.py` exports `SimulationRunResult` + `SimulationPolicy` as self-contained `GovernanceProfile` artifacts. `schemas/governance_profile.v1.json` schema-enforces `simulation: true` and `profile_digest` SHA-256 format. Determinism guarantee: identical inputs → identical `profile_digest`. `validate_profile_schema()` performs structural + optional JSON schema validation. 23 tests.

### CI / Governance

- **PR-DOCS-01 — C-03 docs closure:** `docs/governance/FEDERATION_KEY_REGISTRY.md` governance doc published. Documents registry architecture, key format, rotation policy, threat model, and operator runbook for adding/revoking keys. PR-OPS-01 prerequisite satisfied before publication. C-03 docs lane closed.
- **PR-OPS-01 — H-07/M-02 closure:** Snapshot atomicity and sequence ordering hardened. `runtime/governance/branch_manager.py` uses `_atomic_copy()` for all snapshot writes. `runtime/recovery/ledger_guardian.py` enforces sequence-ordered snapshot iteration with `snapshot_ordering_fallback_to_mtime` as the tie-break policy. H-07 and M-02 findings closed.
- **PR-PERF-01 — C-04 closure:** Streaming lineage ledger verify path implemented. Lineage verification now streams ledger entries incrementally rather than loading the full ledger into memory, reducing peak memory consumption for large lineage chains. `runtime/evolution/` verify paths updated. C-04 finding closed.
- **PR-SECURITY-01 — C-03 closure:** Federation key pinning registry implemented. `governance/federation_trusted_keys.json` is the governance-signed source of truth for all trusted federation public keys. `runtime/governance/federation/key_registry.py` loads and caches the registry at process boot. `runtime/governance/federation/transport.py` `verify_message_signature()` now calls `get_trusted_public_key(key_id)` — caller-supplied key substitution attacks are closed. `FederationTransportContractError` raised for any unregistered `key_id`. C-03 finding closed. `docs/governance/FEDERATION_KEY_REGISTRY.md` governance doc published.
- **PR-HARDEN-01 — C-01/H-02 closure:** Boot env validation and signing key assertion hardened in `app/main.py` and `security/cryovant.py`. `ADAAD_GOVERNANCE_SESSION_SIGNING_KEY` presence is asserted at orchestrator boot in strict environments (`staging`, `production`, `prod`) with fail-closed `CRITICAL` log emission. `BootPreflightService.validate_cryovant()` wires `security.cryovant.validate_environment()` as a typed `StatusEnvelope` gate. C-01 and H-02 findings closed.
- **PR-LINT-01 — H-05 closure:** Determinism lint extended to `adaad/orchestrator/` (dispatcher, registry, bootstrap). `tools/lint_determinism.py` `TARGET_DIRS` and `ENTROPY_ENFORCED_PREFIXES` now include `adaad/orchestrator/`; `REQUIRED_GOVERNANCE_FILES` declares the four orchestrator modules. `determinism-lint` job in `.github/workflows/ci.yml` scans `adaad/orchestrator/` on every push/PR. `determinism_lint.yml` standalone workflow triggers on orchestrator path changes. H-05 finding closed.
- **PR-CI-01 — H-01 closure:** Unified Python version pin at `3.11.9` across all
  `.github/workflows/*.yml` files. `scripts/check_workflow_python_version.py` enforces
  the pin and is wired as a fail-closed CI guard. GA-1.1..GA-1.6 and GA-KR.1 controls
  confirmed complete in `docs/governance/ADAAD_7_GA_CLOSURE_TRACKER.md`.
- **PR-CI-02 — H-08 closure:** SPDX license header enforcement wired always-on as
  `spdx-header-lint` job in `.github/workflows/ci.yml`. `scripts/check_spdx_headers.py`
  confirms all Python source files carry `SPDX-License-Identifier: Apache-2.0`.
  Fixed missing header in `tests/test_branch_protection_policy_workflow.py`.
  `docs/GOVERNANCE_ENFORCEMENT.md` required checks table updated. Claims evidence matrix
  `spdx-header-compliance` row marked Complete.

### Fixed
- Mutation fitness simulation now uses a deterministic structural DNA clone with `deepcopy` fallback, bounded LRU stable-hash score caching, agent-scoped cache keys within a shared bounded LRU cache, tuple-marker hash hardening, and a fail-closed simulation budget guard (resolved once at orchestrator boot); simulation fails closed when required DNA lineage is missing.
- Governance certifier now binds `token_ok` in pass/fail decisions and emits explicit `forbidden_token_detected` violations when token scan checks fail.
- Governance-critical auth call sites (`GateCertifier`, `ArchitectGovernor`) now use `verify_governance_token(...)` instead of deprecated `verify_session(...)`.
- Recovery tier auto-application now enforces explicit escalation/de-escalation semantics with recovery-window-gated de-escalation.

### Security
- Payload-bound legacy static signatures (`cryovant-static-*`) are now accepted only in explicit dev mode (`ADAAD_ENV=dev` + `CRYOVANT_DEV_MODE`) and rejected in non-dev mode with audit telemetry.
- Added deterministic production governance token contract (`cryovant-gov-v1`) via `sign_governance_token(...)` and `verify_governance_token(...)`.
- Governance token signer/verifier now rejects `key_id`/`nonce` delimiter ambiguity (`:`) for fail-closed token-structure validation.
- Deterministic-provider enforcement now covers governance-critical recovery tiers (`governance`, `critical`) while retaining `audit` alias compatibility.

### Added
- MCP schemas for proposal request/response and mutation analysis response under `schemas/mcp/`.

### ADAAD-9 Foundation
- Editor submission telemetry now emits `aponi_editor_proposal_submitted.v1` only for explicit Aponi editor request context headers, with actor/session metadata and no proposal body leakage.
- Aponi dashboard now serves replay inspector assets (`/ui/aponi/replay_inspector.js`) and exposes deterministic replay lineage drill-down metadata in `/replay/diff` responses (`lineage_chain`).
- Added governed simulation passthrough endpoints in standalone Aponi mode: `GET /simulation/context`, `POST /simulation/run`, and `GET /simulation/results/{run_id}` with constitution provenance and bounded epoch-range guardrails.
- Added deterministic `MutationLintingBridge` for editor preflight annotations and authenticated read-only evidence endpoint `GET /evidence/{bundle_id}` for Aponi evidence viewers.
- Added Aponi proposal-editor lint preview endpoint `GET /api/lint/preview` and explicit editor proposal journal event emission (`aponi_editor_proposal_submitted.v1`) on editor-origin submissions.
- MCP test coverage for tools parity, proposal validation, mutation analysis, rejection explanation, candidate ranking, and server route/auth contracts.

### Fixed
- Autonomy role registry tests now include the `ClaudeProposalAgent` role mapping.

### Changed
- Documented MCP architecture, route map, and server→tool mapping in `docs/mcp/IMPLEMENTATION.md`.

### Added
- Claude-governed MCP co-pilot integration (feat/claude-mcp-copilot).
  New mcp-proposal-writer server (runtime/mcp/server.py): governed write
  surface for LLM mutation proposals. ClaudeProposalAgent implements
  MutatorAgent role. proposal_queue.py: append-only hash-linked staging.
  mutation_analyzer.py: deterministic fitness + constitutional pre-check.
  rejection_explainer.py: guard_report → plain-English explanation.
  candidate_ranker.py: fitness-weighted proposal ranking.
  tools_registry.py: MCP tools/list handler for all 4 servers.
  --serve-mcp flag added to ui/aponi_dashboard.py.
  .github/mcp_config.json: GitHub Copilot-compatible server configuration.

### Fixed
- CRITICAL: verify_signature() in security/cryovant.py now performs real
  HMAC-SHA-256 verification. Stub that always returned False removed.
- BLOCKING: --serve-mcp CLI flag now exists in ui/aponi_dashboard.py.

### Changed
- docs/CONSTITUTION.md: added LLM Proposal Agent governance clause.
- runtime/autonomy/roles.py: registered ClaudeProposalAgent.

### Changed
- Cryovant agent certificate checks now prefer payload-bound HMAC verification with legacy static/dev fallback telemetry during migration.
- Fixed constitution document version parsing regex so governance version-gate checks evaluate real markdown versions.
- Test sandbox pre-exec hooks are now invocation-scoped (thread-safe) instead of shared mutable instance state.
- `verify_session()` now emits a deprecation warning clarifying non-production behavior.
- Consolidated lineage chain resolution on `runtime.evolution.lineage_v2` and removed the duplicate `security.ledger.lineage_v2` implementation.
- Hardened replay-mode provider synchronization so `EvolutionRuntime.set_replay_mode()` aligns the epoch manager provider with the governor provider before strict replay checks.
- Improved deterministic shared-epoch concurrency behavior in governor validation ordering for strict replay lanes.
- Mutation executor now preserves backwards compatibility with legacy `_run_tests` monkeypatches that do not accept keyword args.
- Replay digest recomputation now tolerates historical/tampered chain analysis workflows by recomputing from recorded payloads without requiring hash-chain integrity prevalidation.
- Beast-mode loop explicit-agent cycles now consistently route through the legacy compatibility adapter path.
- Entropy baseline profiling CLI now bootstraps repository root imports automatically when invoked as `python tools/profile_entropy_baseline.py`.

- Added explicit verified vs unverified lineage incremental digest APIs to separate strict validation from forensic reconstruction workflows.
- Strict replay now emits warning metrics events when nonce format is malformed, improving replay auditability for concurrent validation lanes.
- Cryovant dev signature allowance remains explicitly gated by `CRYOVANT_DEV_MODE` opt-in semantics for local/dev workflows.
- Determinism foundation once again enforces deterministic providers for audit recovery tier (`audit_tier_requires_deterministic_provider`).
- Added Cryovant dev-signature acceptance telemetry (`cryovant_dev_signature_accepted`) for security visibility in dev-gated flows.
- Added strict replay invariants reference document under `docs/governance/STRICT_REPLAY_INVARIANTS.md`.
- Added shared-epoch strict replay stress coverage across repeated parallel runs to validate digest/order stability.
- Fixed a circular import between constitutional policy loading and metrics analysis by lazily importing lineage replay dependencies during determinism scoring.
- Metrics analysis lineage-ledger factory now supports explicit or `ADAAD_LINEAGE_PATH` path resolution, validates `LEDGER_V2_PATH` fallback, and creates parent directories before ledger initialization.
- Journal tail-state recovery now records deterministic warning metrics events when cached tail hashes require full-chain rescans.
- UX tools now include real-time CLI stage parsing, optional global error excepthook installer, expanded onboarding validation checks, and WebSocket-first enhanced dashboard updates with polling fallback.
- UX tooling refresh: richer enhanced dashboard visuals, expanded enhanced CLI terminal UX, comprehensive error dictionary formatting, and guided 8-step interactive onboarding.
- Added optional UX tooling package: enhanced static dashboard, enhanced CLI wrapper, interactive onboarding helper, and structured error dictionary for operator clarity.
- Aponi governance UI hardened with `Cache-Control: no-store` and CSP, plus externalized UI script delivery for non-inline execution compliance.
- Added deterministic replay-seed issuance/validation across governor, mutation executor, manifest schema, and manifest validator plus replay runtime parity integration tests.
- Replay, promotion manifest, baseline hashing, governor certificate fallback checkpoint digest, and law-evolution certificate hashing now use canonical runtime governance hashing/clock utilities.
- Runtime import root policy now explicitly allows `governance` compatibility adapters.
- Governance documentation now defines canonical runtime import paths and adapter expectations.
- Verbose boot diagnostics strengthened with replay mode normalization echo, fail-closed state output, replay score output, replay summary block, replay manifest path output, and explicit boot completion marker.
- `QUICKSTART.md` expanded with package sanity checks and first-time strict replay baseline guidance.
- Governance surfaces table in README and architecture legend in `docs/assets/architecture-simple.svg`.
- Bug template field for expected governance surface to accelerate triage.
- README clarified staging-only mutation semantics for production posture.
- CONTRIBUTING now requires strict replay verification for governance-impact PRs and adds determinism guardrails.
- Evolution kernel `run_cycle()` now supports a kernel-native execution path for explicit `agent_id` runs while preserving compatibility-adapter routing for default/no-agent flows.
- Hardened `EvolutionKernel` agent lookup by resolving discovered and requested paths before membership checks, eliminating alias/symlink/`..` false `agent_not_found` failures.
- Added regression coverage for mixed lexical-vs-resolved agent path forms in `tests/test_evolution_kernel.py`.
- Aponi execution-control now validates queue targets by command id, returning explicit `target_not_found` or `target_not_executable` errors before orchestration.

### Added
- Constitutional enforcement semantics now consistently apply enabled-rule gating with applicability pass-through (`rule_not_applicable`) and tier override resolution, improving deterministic verdict replay behavior.
- Replay/determinism posture updated for constitutional evaluation, increasing deterministic evidence surface while preserving reproducible policy-hash/version coupling across audits.
- Added read-only Aponi replay forensics endpoints (`/replay/divergence`, `/replay/diff?epoch_id=...`) and versioned governance health model metadata (`v1.0.0`).
- Added Aponi V2 governance docs: replay forensics + health model, red-team pressure scenario, and 0.70.0 draft release notes.
- Added epoch entropy observability helper (`runtime/evolution/telemetry_audit.py`) for declared vs observed entropy breakdown by epoch.
- Added fail-closed governance recovery runbook (`docs/governance/fail_closed_recovery_runbook.md`).
- Completed PR-5 sandbox hardening baseline: deterministic manifest/policy validation, syscall/fs/network/resource checks, and replayable sandbox evidence hashing.
- Added checkpoint registry and verifier modules, entropy policy/detector primitives, and hardened sandbox isolation evidence plumbing for PR-3/PR-4/PR-5 continuation.
- Added deterministic promotion event creation and priority-based promotion policy engine with unit tests.
- Mutation executor promotion integration now enforces valid transition edges and fail-closed policy rejection (`promotion_policy_rejected`).
- Completed PR-1 scoring foundation modules: deterministic scoring algorithm, scoring validator, and append-only scoring ledger with determinism tests.
- Added replay-safe determinism provider abstraction (`runtime.governance.foundation.determinism`) and wired provider injection through mutation executor, epoch manager, evolution governor, promotion manifest writer, and ledger snapshot recovery paths.
- Added governance schema validation policy, validator module/script, and draft-2020-12 governance schemas (`scoring_input`, `scoring_result`, `promotion_policy`, `checkpoint`, `manifest`) with tests.
- Deterministic governance foundation helpers under `runtime.governance.foundation` (`canonical`, `hashing`, `clock`) with compatibility adapters under top-level `governance.*`.
- Evolution governance helpers for deterministic checkpoint digests, promotion transition enforcement, and authority score clamping/threshold resolution.
- Unit tests covering governance foundation canonicalization/hash determinism and promotion state transitions.


### Security
- Enabled blocking constitutional checks for `lineage_continuity` and `resource_bounds`, strengthening mutation safety controls while retaining policy-defined tier behavior.
- Enabled warning-path governance checks for `max_complexity_delta` and `test_coverage_maintained`, and enforced `max_mutation_rate` tier escalation/demotion semantics for production/sandbox replay consistency.

### Milestone reconciliation (PR-1 .. PR-6 + PR-3H)

Authoritative current version/maturity for these notes: **0.65.x, Experimental / pre-1.0**.

| Milestone | Status | Reconciled claim |
|---|---|---|
| PR-1 | Implemented | Scoring foundation + deterministic governance/scoring ledger/test coverage landed in this branch |
| PR-2 | Implemented | Constitutional rule set v0.2.0 enabled with deterministic validators, governance envelope digest, drift detection, and coverage artifact pipeline contracts (not open) |
| PR-3 | Implemented | Checkpoint registry/verifier and entropy policy enforcement paths landed with deterministic coverage in this branch |
| PR-3H (hardening extension) | Planned | New post-PR-3 hardening scope: (1) deterministic checkpoint tamper-escalation evidence path, (2) entropy anomaly triage policy thresholds + replay fixtures, and (3) audit-ready hardening acceptance tests for strict replay governance reviews |
| PR-4 | Implemented | Lifecycle/promotion policy state-machine and ledger/event contract wiring landed with deterministic coverage in this branch |
| PR-5 | Implemented (baseline) | Deterministic sandbox policy checks and evidence hashing landed |
| PR-6 | Implemented (baseline) | Deterministic federation coordination/protocol baseline landed; distributed transport hardening remains roadmap |

### Validated guarantees (this branch)

- Deterministic governance/replay substrate for canonical runtime paths.
- Fail-closed replay decision flow and strict replay enforcement behavior.
- Append-only lineage/scoring ledger behavior and related determinism coverage.
- PR lifecycle ledger event contract with schema-backed event types (`pr_lifecycle_event.v1.json`, `pr_lifecycle_event_stream.v1.json`), deterministic idempotency derivation, and append-only invariant validation helpers.
- Rule applicability system: `governance/rule_applicability.yaml` is loaded at constitutional boot; evaluations emit `applicability_matrix`, and inapplicable rules are emitted as `rule_not_applicable` pass-through verdicts.
- CI tiering classifier with conditional strict/evidence/promotion suites and audit-ready gating summary emission per run.
- Release evidence gate enforcing `docs/comms/claims_evidence_matrix.md` completeness and resolvable evidence links for governance/public-readiness tags.
- CodeQL workflow enabled for push/PR on `main` with scheduled analysis.

### Roadmap (not yet validated guarantees)

- Sandbox hardening depth beyond current baseline checks.
- Portable cryptographic replay proof bundles suitable for external verifier exchange.
- Federation and cross-instance sovereignty hardening beyond current in-tree coordination/protocol baseline.
- Key-rotation enforcement escalation and audit closure before 1.0 freeze.
- ADAAD-10/11/14 follow-on modules remain roadmap items until merged and file-presence-verified in this branch snapshot; `runtime/evolution/mutation_credit_ledger.py` is now present with append-only replay verification, while deployment authority/reviewer-pressure tracks remain roadmap.

## 0.65.0 - Initial import of ADAAD He65 tree

- Established canonical `User-ready-ADAAD` tree with five-element ownership (Earth, Wood, Fire, Water, Metal).
- Added Cryovant gating with ledger/keys scaffolding and certification checks to block uncertified Dream/Beast execution.
- Normalized imports to canonical roots and consolidated metrics into `reports/metrics.jsonl`.
- Introduced deterministic orchestrator boot order, warm pool startup, and minimal Aponi dashboard endpoints.

## [Unreleased] — ADAAD-10 · v1.4.0

### ADAAD-10 Track A — Live Market Signal Adapters

- **PR-10-02 — POST /market/signal webhook endpoint + integration tests:** `server.py` gains `POST /market/signal` bearer-auth-gated endpoint routing raw payloads through `LiveSignalRouter` → lineage-stamped `MarketSignalReading` → fitness advisory injection; journal event `market_signal_ingested.v1`. `tests/test_market_fitness_integrator.py`: 11 tests covering integrator bridging (live, synthetic fallback, lineage propagation, journal), `FitnessOrchestrator.inject_live_signal()` override (score override, no-override passthrough, clamping, bad epoch silent drop). ADAAD-10 Track A complete.

- **PR-10-01 — MarketFitnessIntegrator + FitnessOrchestrator live signal injection:** `runtime/market/market_fitness_integrator.py` bridges `FeedRegistry.composite_reading()` into `FitnessOrchestrator.inject_live_signal()` replacing the static `simulated_market_score` with confidence-weighted live readings; synthetic fallback (0.5, zero confidence) on source failure. `runtime/evolution/fitness_orchestrator.py`: `inject_live_signal()` method + `_apply_live_override()` wired into `score()` pre-snapshot. `runtime/market/__init__.py` updated. Authority invariant: GovernanceGate retains final mutation-approval authority; market scores are fitness inputs only.

## [1.4.0] — 2026-03-05 · ADAAD-10 Live Market Signal Adapters

Live economic signals replace synthetic constants across the entire fitness pipeline.

**FeedRegistry** (`runtime/market/feed_registry.py`): deterministic adapter ordering, TTL caching, fail-closed stale guard, confidence-weighted composite. Three concrete adapters: `VolatilityIndexAdapter` (inverted market stress), `ResourcePriceAdapter` (normalised compute cost), `DemandSignalAdapter` (DAU/WAU/retention composite).

**MarketFitnessIntegrator** (`runtime/market/market_fitness_integrator.py`): bridges FeedRegistry composite into `FitnessOrchestrator.score()` as live `simulated_market_score`. Lineage digest + signal source propagated. Journal event `market_fitness_signal_enriched.v1`.

**Schema**: `schemas/market_signal_reading.v1.json` — validated signal reading contract.

Authority invariant: adapters are read-only; they influence fitness scoring but cannot approve mutations.


### ADAAD-11 Track B — Darwinian Agent Budget Competition

- **PR-11-02 — DarwinianSelectionPipeline + tests (ADAAD-11 complete):** `runtime/evolution/budget/darwinian_pipeline.py` post-fitness hook couples `FitnessOrchestrator` scores to `BudgetArbitrator` completing the Darwinian selection loop; `darwinian_selection_complete.v1` journal event. `tests/test_darwinian_budget.py`: 16 tests — AgentBudgetPool (invariants, reallocation, eviction, ledger), BudgetArbitrator (Softmax, starvation, market scalar), CompetitionLedger (append-only, persist, audit export), FitnessOrchestrator post-fitness wire. ADAAD-11 Track B complete.
- **PR-11-01 — AgentBudgetPool + BudgetArbitrator + CompetitionLedger:** `runtime/evolution/budget/` package: `pool.py` (finite pool, append-only allocation ledger, starvation detection, eviction), `arbitrator.py` (Softmax fitness-weighted reallocation, market pressure scalar, starvation accumulation, eviction at threshold), `competition_ledger.py` (append-only JSONL-backed event log, eviction history, audit export, sha256 lineage digests). Authority invariant: arbitrator writes to pool only; never approves or signs mutations.

### ADAAD-12 Track C — Real Container-Level Isolation Backend

- **PR-12-02 — executor.py orchestrator wiring + lifecycle audit trail + tests:** `tests/test_container_orchestrator.py`: 20 tests covering ContainerPool (bounded pool, acquire/release/quarantine), ContainerOrchestrator (allocate, mark_running, release, health checks, journal events, pool_status), ContainerHealthProbe (liveness/readiness, quarantine detection, empty container_id), lifecycle FSM (IDLE→PREPARING→RUNNING→IDLE/QUARANTINE, lineage digest on transition). ADAAD_SANDBOX_CONTAINER_ROLLOUT=true activates ContainerOrchestrator as default. ADAAD-12 Track C complete.
- **PR-12-01 — ContainerOrchestrator + ContainerHealthProbe + default profiles:** `runtime/sandbox/container_orchestrator.py`: `ContainerOrchestrator` (pool management, lifecycle state machine IDLE→PREPARING→RUNNING→DONE/FAILED/QUARANTINE, journal events for allocation/release/health), `ContainerPool` (bounded slot ceiling, acquire/release, quarantine), `ContainerSlot` (sha256 lineage digest per transition). `runtime/sandbox/container_health.py`: `ContainerHealthProbe` (liveness + readiness checks, graceful degradation in CI). `runtime/sandbox/container_profiles/`: `default_seccomp.json` (syscall allowlist), `default_network.json` (deny-all egress), `default_resources.json` (cgroup v2 quotas: 50% CPU, 256MB RAM, 64 PIDs). Authority invariant: container backend does not expand mutation authority.

### ADAAD-13 Track D — Fully Autonomous Multi-Node Federation

- **PR-13-02 — Federation integration tests + split-brain resolution (ADAAD-13 complete):** `tests/test_federation_autonomous.py`: 26 tests — PeerRegistry (registration, heartbeat, stale/alive TTL detection, partition threshold, deregister, idempotent re-registration), GossipProtocol (valid/malformed event handling, queue drain, digest format), FederationConsensusEngine (initial follower, election→candidate→leader, majority vote, log append leader-only, commit_entry, quorum gate for policy_change, heartbeat reset, vote grant/deny), FederationNodeSupervisor (healthy/partitioned tick, safe_mode_active, partition journal event). ADAAD-13 Track D complete.
- **PR-13-01 — PeerRegistry + GossipProtocol + FederationConsensusEngine + FederationNodeSupervisor:** `runtime/governance/federation/peer_discovery.py`: `PeerRegistry` (TTL-based liveness, stale/alive partition detection, idempotent registration, heartbeat update, partition threshold check), `GossipProtocol` (HTTP broadcast to alive peers, inbound event validation + queue, sha256 lineage digest per event, best-effort non-blocking). `runtime/governance/federation/consensus.py`: `FederationConsensusEngine` (Raft-inspired — leader election with term-based majority vote, append-only log with lineage digests, constitutional quorum gate for policy changes, heartbeat/rejoin). `runtime/governance/federation/node_supervisor.py`: `FederationNodeSupervisor` (heartbeat tick, partition detection → safe mode, autonomous rejoin broadcast, degraded state tracking). Authority invariant: consensus provides ordering only; GovernanceGate retains execution authority.

## [1.7.0] — 2026-03-05 · ADAAD-13 Autonomous Multi-Node Federation

### ADAAD-10 · Live Market Signal Adapters
FeedRegistry + VolatilityIndex/ResourcePrice/DemandSignal adapters + MarketSignalReading schema + MarketFitnessIntegrator + FitnessOrchestrator.inject_live_signal() + POST /market/signal webhook. Live DAU/retention signals replace synthetic constants activating real Darwinian selection pressure.

### ADAAD-11 · Darwinian Agent Budget Competition
AgentBudgetPool + BudgetArbitrator (Softmax, market pressure scalar, starvation/eviction) + CompetitionLedger (append-only, sha256 lineage) + DarwinianSelectionPipeline (post-fitness hook). High-fitness agents earn allocation; low-fitness agents starve and are evicted.

### ADAAD-12 · Real Container-Level Isolation Backend
ContainerOrchestrator (pool lifecycle FSM, health probes, journal events) + ContainerHealthProbe + 3 default profiles (seccomp/network/resources). ADAAD_SANDBOX_CONTAINER_ROLLOUT=true activates kernel-enforced cgroup v2 limits.

### ADAAD-13 · Fully Autonomous Multi-Node Federation
PeerRegistry (TTL liveness, partition detection) + GossipProtocol (HTTP broadcast, inbound queue, sha256 lineage) + FederationConsensusEngine (Raft-inspired — term election, log replication, constitutional quorum gate) + FederationNodeSupervisor (heartbeat, safe mode, autonomous rejoin). Federation moves from file-based to autonomous peer discovery, quorum consensus, and cross-node constitutional enforcement.

**Authority invariants maintained throughout all four milestones:**
- Market adapters influence fitness only; GovernanceGate retains mutation authority.
- Budget arbitration reallocates pool shares; never approves mutations.
- Container backend hardens execution surface; does not expand mutation authority.
- Consensus provides ordering; GovernanceGate retains execution authority for cross-node policy changes.


## [1.3.0] — 2026-03-05 · ADAAD-9 Developer Experience

### ADAAD-9 · Aponi-as-IDE — Governance-First Developer Environment

Aponi evolves from a read-only governance observatory into a **governance-first authoring environment**. Developers can now author, lint, simulate, and inspect evidence for mutation proposals entirely within a single browser-accessible interface — without departing to a second toolchain.

**D1 — Mutation Proposal Editor:** `ui/aponi/proposal_editor.js` routes proposals through `POST /mutation/propose`; emits `aponi_editor_proposal_submitted.v1` journal event on every editor-originated submission.

**D2 — Inline Constitutional Linter:** `runtime/mcp/linting_bridge.py` (`MutationLintingBridge`) wraps `mutation_analyzer.py`; debounced 800ms; uses same rule engine as `GovernanceGate`; `AndroidMonitor.should_throttle()` governs call frequency; determinism tests in `tests/mcp/test_linting_bridge.py`.

**D3 — Simulation Panel:** `ui/aponi/simulation_panel.js`; wires Epic 2 `POST /simulation/run` + `GET /simulation/results/{run_id}`; pre-populates constraints from `/simulation/context`; surfaces comparative outcomes (actual/simulated/delta) and provenance (deterministic, replay_seed) inline.

**D4 — Evidence Viewer:** `ui/aponi/evidence_viewer.js`; fetches `GET /evidence/{bundle_id}`; renders provenance fields (`constitution_version`, `scoring_algorithm_version`, `governor_version`, hashes), risk summaries with high-risk highlight, signer fields, sandbox snapshot, replay proof chain. 17 tests in `tests/test_evidence_viewer.py` covering schema conformance, auth gating, provenance presence, determinism.

**D5 — Replay Inspector:** `ui/aponi/replay_inspector.js` over `/replay/divergence` + `/replay/diff`; navigable epoch-by-epoch transition chain; divergence alert distinction; lineage navigation from mutation to full ancestor chain. 4 new e2e tests in `tests/test_aponi_dashboard_e2e.py`.

**D6 — Android/Pydroid3 Compatibility:** All heavy operations (simulation, evidence fetch) respect `AndroidMonitor.should_throttle()`; epoch range bounded by platform limit from `/simulation/context`.

**Authority invariant:** Aponi IDE introduces no new execution path. All write operations route through `POST /mutation/propose` → MCP queue → `GovernanceGate` → constitutional evaluation → staging. `authority_level` clamped to `governor-review` by `proposal_validator.py` for all editor-originated submissions.

