# ADAAD Implementation ↔ Documentation Alignment

<!-- ARCH_SNAPSHOT_METADATA:START -->
## Architecture Deep-Dive Snapshot

| Metric | Value |
| --- | --- |
| Report version | `1.0.0` |
| Branch | `work` |
| Tag | `(none)` |
| Short SHA | `fd41317` |

All future architecture snapshots MUST include branch, tag (if any), and short SHA.
<!-- ARCH_SNAPSHOT_METADATA:END -->

This document cross-references `README.md` operational claims with concrete implementation modules and tests.

## Governance Philosophy Alignment

README governance principles are implemented via:

- **Determinism controls**: `runtime/evolution/entropy_discipline.py`
  - `deterministic_context(...)`
  - `deterministic_id(...)`
  - `deterministic_token(...)`
  - `deterministic_token_with_budget(...)`
- **Replay enforcement and fail-closed semantics**: `runtime/evolution/replay_mode.py` and `runtime/evolution/runtime.py`
  - `ReplayMode.fail_closed`
  - `ReplayMode.should_verify`
  - `EvolutionRuntime.replay_preflight(...)`
- **Tiered safety posture**: `runtime/recovery/tier_manager.py`
  - `RecoveryTierLevel`
  - `RecoveryPolicy.for_tier(...)`
  - `TierManager.evaluate_tier(...)`

## Replay Contract Alignment

README replay contract (`off`, `audit`, `strict`) is implemented by:

- `runtime/evolution/replay_mode.py`
  - Mode normalization (`normalize_replay_mode`)
  - CLI parsing helper (`parse_replay_args`)
- `runtime/evolution/runtime.py`
  - `replay_preflight(...)` returning:
    - `mode`
    - `verify_target`
    - `has_divergence`
    - `decision`
    - `results`
- Integration replay parity harness: `tests/determinism/test_replay_runtime_harness.py`
  - Calls `EvolutionRuntime.verify_epoch(...)`, `EvolutionRuntime.replay_preflight(...)`, and `ReplayEngine.replay_epoch(...)` directly
  - Verifies canonical parity against ledger epoch digests and `ReplayVerificationEvent` payload fields

## Recovery Tier Ladder Alignment

README ladder (`none`, `advisory`, `conservative`, `governance`, `critical`) is implemented by:

- `runtime/recovery/tier_manager.py`
  - Tier enum and ordering semantics
  - Policy mapping (mutation rate, approval requirements, fail-close behavior)
  - Escalation triggers (ledger errors, governance violations, mutation failures, anomalies)

## Snapshot / Recovery Alignment

Snapshot and restore flows described in docs are implemented by:

- `runtime/recovery/ledger_guardian.py`
  - `SnapshotManager.create_snapshot(...)` (single-file and lineage+journal signatures)
  - `SnapshotManager.list_snapshots()`
  - `SnapshotManager.get_latest_snapshot()`
  - `SnapshotManager.restore_snapshot(...)`
  - `AutoRecoveryHook` integrity failure handlers and `attempt_recovery(...)`

## Mutation Lifecycle Alignment

README mutation lifecycle concepts map to:

- **Discovery + staging**: `app/dream_mode.py`
- **Mutation ID determinism**: `app/mutation_executor.py`
- **Epoch lifecycle + digest tracking**: `runtime/evolution/epoch.py`, `runtime/evolution/runtime.py`
- **Promotion transition + events**: `runtime/evolution/promotion_state_machine.py`, `runtime/evolution/promotion_events.py`, `runtime/evolution/promotion_policy.py`, `runtime/evolution/simulation_runner.py`
- **Fitness scoring support**: `runtime/evolution/fitness.py`, `runtime/fitness_pipeline.py`, `runtime/evolution/scoring_algorithm.py`, `runtime/evolution/scoring_validator.py`, `runtime/evolution/scoring_ledger.py`
- **Lineage digest verification**: `runtime/evolution/lineage_v2.py`, `runtime/evolution/replay.py`
- **Economic mutation credit ledger (append-only, replay-verifiable)**: `runtime/evolution/mutation_credit_ledger.py`
  - Hash-chained JSONL entries (`prev_hash` + `record_hash`)
  - Idempotency-key enforcement
  - `verify_integrity()` + deterministic `replay_balances()`
- **Null-safe governance accessors for mutable logs/state**: `runtime/governance/foundation/safe_access.py`, consumed in `app/beast_mode_loop.py`, `runtime/evolution/checkpoint_registry.py`, and audit/entropy tools under `tools/`.

## Validation Coverage

The following tests validate alignment-critical behavior:

- `tests/test_orchestrator_replay_mode.py`
- `tests/test_entropy_discipline_replay.py`
- `tests/determinism/test_replay_equivalence.py`
- `tests/determinism/test_replay_runtime_harness.py`
- `tests/recovery/test_tier_manager.py`
- `tests/governance/test_ledger_guardian.py`
- `tests/test_evolution_infrastructure.py`
- `tests/test_promotion_events.py`
- `tests/test_promotion_policy.py`
- `tests/determinism/test_scoring_algorithm_determinism.py`
- `tests/test_scoring_validator.py`
- `tests/test_scoring_ledger.py`
- `tests/test_mutation_guard.py`
- `tests/evolution/test_checkpoint_registry.py`
- `tests/stability/test_null_guards.py`
- `tests/evolution/test_entropy_policy.py`
- `tests/sandbox/test_sandbox_evidence.py`
- `tests/sandbox/test_sandbox_policy_enforcement.py`
- `tests/sandbox/test_sandbox_replay.py`
- `tests/sandbox/test_sandbox_executor.py`

## Current Validation Status

Run the full suite:

```bash
pytest -q
```

Expected status in this repository branch: governance/intelligence/dispatcher targeted suites are passing, while full-suite collection may vary by environment and optional dependency availability. Use targeted validation commands in the audit checklist below for deterministic hardening verification.

- Governance schema versioning policy: `docs/governance/schema_versioning_and_migration.md`


## Sovereignty Requirements: Implemented vs Planned

| Requirement | Evidence in repository | Status | Validation posture |
|---|---|---|---|
| Deterministic substrate | `runtime.governance.foundation.{canonical,hashing,clock,determinism}` plus replay/determinism tests in `tests/determinism/*` | Implemented | Validated guarantee for governance/replay execution paths |
| Sandbox hardening depth | Sandbox policy + enforcement + isolation/preflight primitives in `runtime/sandbox/*` and tests in `tests/sandbox/test_sandbox_*` | Partially implemented | Enhanced deterministic fail-closed baseline validated; kernel/container hardening depth remains roadmap |
| Replay proofs | Replay preflight/runtime harnesses in `runtime/evolution/*`, attestation builder `runtime/evolution/replay_attestation.py`, and determinism tests in `tests/determinism/test_replay_*` | Implemented baseline | Deterministic replay verification + signed attestations validated in-tree; external trust-root hardening remains roadmap |
| Federation | Deterministic federation coordination entrypoint (`run_coordination_cycle`), handshake envelope serializers, local deterministic transport (`runtime/governance/federation/transport.py`), and versioned transport schema (`schemas/federation_transport_contract.v1.json`) validated by federation governance tests | Implemented baseline | In-tree quorum/verification + strict replay divergence fail-close behavior are implemented and tested; multi-instance authenticated transport hardening and broader protocol resilience remain roadmap |

## Phase 2 Migration Checklist

- Treat `tools/lint_determinism.py` as the canonical migration gate for governance/evolution determinism hardening.
- Phase 2 migration completion requires a clean determinism lint run with no forbidden nondeterministic filesystem API usage in `runtime/governance/` and `runtime/evolution/`.


## PR-08 Implementation Checklist (Evidence bundle provenance)

- [x] `schemas/evidence_bundle.v1.json` requires `scoring_algorithm_version` and `constitution_version`.
- [x] `runtime/evolution/evidence_bundle.py` populates both fields from runtime constants for newly built bundles.
- [x] `_validate_schema_subset` enforcement remains fail-closed for missing required keys on new bundles.
- [x] Legacy validation path is explicit (`validate_bundle(..., allow_legacy=True)`) and only backfills newly required provenance fields.

## PR Milestone Reconciliation (PR-1 .. PR-6 + PR-3H)

| Milestone | Status in docs | Reconciled repository posture |
|---|---|---|
| PR-1 | Complete | Keep as complete (scoring + deterministic ledger/test claims present and aligned) |
| PR-2 | Complete | Constitutional rule set is fully enabled and validated (not open); see `runtime/constitution.py` (validator registry + policy loading/enabled-rule gating) and `tests/test_constitution_policy.py` (coverage for lineage/coverage/mutation-rate/resource-bounds behavior). |
| PR-3 | Complete | Checkpoint registry/verifier and entropy policy enforcement are implemented with deterministic coverage in-tree; milestone scope is satisfied for 0.65.x. |
| PR-3H (hardening extension) | Proposed | New implementation request label because PR-3 is already complete: acceptance requires deterministic checkpoint tamper-escalation evidence, entropy anomaly triage policy thresholds validated under strict replay, and audit-ready hardening tests. |
| PR-4 | Complete | PR lifecycle contracts, promotion policy/state transitions, and deterministic ledger/event paths are implemented and validated in-tree; Aponi transport/UX integration now anchors on `runtime/integrations/aponi_sync.py` and `ui/aponi_dashboard.py` with a shared runtime port constant source. |
| PR-5 | Complete baseline | Keep complete for baseline hardening; additional depth remains roadmap |
| PR-6 | Implemented baseline | Deterministic federation coordination/protocol contracts are implemented in-tree; transport/distributed hardening remains roadmap. |


## Final Governance Maturity Matrix (0.65.x)

| Milestone | Final 0.65.x status | Scope note |
|---|---|---|
| PR-1 | Complete | Scoring foundation + deterministic scoring/ledger substrate validated in-tree. |
| PR-2 | Complete | Constitutional rule engine semantics (enabled gating, tier overrides, deterministic evaluation) validated in-tree; milestone is not open. |
| PR-3 | Complete | Checkpoint + entropy policy enforcement paths are implemented and tested in-tree. |
| PR-3H (hardening extension) | Proposed next | Use this as the current implementation request label for post-PR-3 hardening acceptance criteria and governance evidence review gating. |
| PR-4 | Complete | Lifecycle/promotion contract wiring is implemented with deterministic event/ledger behavior, including shared canonical Aponi port resolution in `runtime/integrations/aponi_sync.py` and `ui/aponi_dashboard.py`. |
| PR-5 | Complete baseline | Deterministic sandbox policy/enforcement baseline is validated; deeper hardening remains roadmap. |
| PR-6 | Implemented baseline | Federation coordination/protocol baseline is implemented in-tree; broader distributed hardening remains roadmap. |

#### PR-04 Implementation Checklist (Aponi integration alignment)

- [x] `runtime/integrations/aponi_sync.py` default API URL composes from runtime canonical constants (`APONI_PORT` / `APONI_URL`) instead of a hardcoded legacy port.
- [x] `ui/aponi_dashboard.py` standalone `--port` fallback resolves from `runtime.constants.APONI_PORT` while preserving `APONI_PORT` env override behavior.
- [x] Test coverage asserts both modules derive canonical defaults from the same runtime port source.

## Next governance audit

- Audit key-rotation enforcement next: verify epoch/key-rotation freshness policy coverage and escalation posture before 1.0 freeze.

## Release Notes Rule: Guarantees vs Roadmap

For `CHANGELOG.md` and release notes:

- Put only tested, branch-validated behavior under **Validated guarantees**.
- Put future work and unverified posture claims under **Roadmap**.
- Do not label planned federation or deep hardening items as production guarantees until explicit validation artifacts/tests are present.

### Roadmap clarification for absent expected modules

- `runtime/evolution/mutation_credit_ledger.py` is implemented in this snapshot; remaining ADAAD-11/14 controls still require merged modules plus validation evidence before promotion to guarantees.


- Fail-closed recovery runbook: `docs/governance/fail_closed_recovery_runbook.md`


## Architecture contract and boundary enforcement

- Canonical platform entrypoint is `app/main.py`; legacy adapter paths are documented as adapter-only in app/runtime READMEs.
- Layer ownership and forbidden cross-layer imports are defined in `docs/ARCHITECTURE_CONTRACT.md`.
- CI enforces import boundaries via `python tools/lint_import_paths.py` plus `tests/test_lint_import_paths.py` guard tests, including relative-import boundary checks.


## February 2026 hardening audit snapshot

- Runtime facade imports were hardened to lazy-load symbols (`runtime/api/__init__.py`, `runtime/api/agents.py`, `runtime/evolution/__init__.py`) to reduce circular import failures during collection and strict replay paths.
- Constitution policy loading now includes a hermetic fallback parser when external YAML packages are unavailable; canonical JSON policy files remain the authoritative source.
- Federation signature-contract tests now skip cleanly when `cryptography` is unavailable in hermetic environments.
- Determinism envelope hashing was hardened by excluding volatile runtime-only detail fields from governance envelope digest material.

Recommended validation set:

```bash
pytest -q tests/test_constitution_policy.py tests/test_economic_fitness.py tests/evolution/test_evidence_bundle.py tests/test_intelligence_router.py tests/test_intelligence_proposal_adapter.py tests/test_orchestrator_dispatcher.py
```


## Governance surface registry

- Canonical governance digest surfaces are now centralized in `runtime/governance_surface.py` using explicit whitelist + volatile-key exclusion semantics.
- `ADAAD_DETERMINISTIC_LOCK` disables adaptive runtime tuning paths where configured.
- Dispatcher supports `ADAAD_DISPATCH_LATENCY_MODE=static|adaptive`; adaptive behavior is environment-derived and auditable via runtime metrics events.
