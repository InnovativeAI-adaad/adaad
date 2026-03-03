# Changelog

## [Unreleased]

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
