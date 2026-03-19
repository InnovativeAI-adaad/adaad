# Wood + Fire (app) ![Stable](https://img.shields.io/badge/App-Stable-2ea043)

The app layer orchestrates boot order and creative/evaluative cycles. Architect (Wood) scans agents for required metadata, while Dream and Beast (Fire) run mutation and evaluation loops. All operations must honor Cryovant gating and log to `reports/metrics.jsonl`.

> The app package is the orchestration shell around ADAAD runtime governance components.
> It should coordinate boot lifecycle and mutation execution handoffs without owning canonical governance primitives.
> Keep this layer thin, deterministic, and boundary-safe.

> **Doc metadata:** Audience: Contributor · Last validated release: `v1.0.0`

> ✅ **Do this:** Keep orchestration responsibilities in `app/*` and delegate policy/replay primitives to `runtime/*`.
>
> ⚠️ **Caveat:** Coupling orchestrators directly to `app.main` internals breaks import-boundary guarantees.
>
> 🚫 **Out of scope:** Do not add new business logic to compatibility shims or legacy module-level adapter paths.


## Canonical entrypoint contract ![Internal](https://img.shields.io/badge/Contract-Internal-blue)

- Canonical platform entrypoint: `python -m app.main` (`app/main.py`).
- `app/mutation_executor.py` is the pure execution engine and should remain UI/entrypoint agnostic.
- `adaad/orchestrator/*` is orchestration/wiring only. Any direct `app.main` coupling is forbidden.
- Legacy module-level compatibility paths are adapter-only and must not grow business logic.
- Dispatcher call sites in orchestration paths must fail closed on non-success envelopes before reading `result` payloads (deterministic `dispatch failed:<code>` RuntimeError on error/missing result/explicit non-success result status).
- Dispatch guard failures should be observable via dispatcher logger records to preserve triage/audit visibility for rejected envelopes.
- See `docs/ARCHITECTURE_CONTRACT.md` for ownership and enforcement boundaries.


### Enforcement

These constraints are enforced by `tools/lint_import_paths.py` (rule id: `layer_boundary_violation`) and the always-on CI job `import-boundary-lint`.
Relative imports that resolve to forbidden modules are also blocked.

Legitimate exceptions require updating both `tools/lint_import_paths.py` and `docs/ARCHITECTURE_CONTRACT.md` in the same PR with rationale.

## Metrics payload minimization for dream tasks

- `dream_discovery` metrics in `app/dream_mode.py` emit deterministic summaries by default (`task_count` + ordered `task_sample`) instead of full task arrays.
- Full task lists are opt-in for debug-only diagnostics via `ADAAD_METRICS_INCLUDE_FULL_TASKS=1`.
- Sample size is deterministic and configurable with `ADAAD_DREAM_DISCOVERY_SAMPLE_SIZE` (default `3`).
- `_health_check_dream` in `app/main.py` emits normalized summary payloads (`task_count`, `safe_boot`) to reduce noisy telemetry while preserving replay-safe observability.

## Key-rotation boot gate behavior

- `Orchestrator._check_key_rotation_status()` now validates `security/keys/rotation.json` via the key-rotation attestation path when the attestation file exists.
- Environments without rotation attestations keep the existing mtime-based key freshness fallback for migration compatibility.

## DEVADAAD merge authorization replay gate behavior

- `app/orchestration/adaad_trigger.py` now treats replay verification metadata as a hard merge-context prerequisite for `DEVADAAD`.
- Merge-ready orchestration output must include verified-SHA replay context: manifest path, bundle digest, verification result, schema/signature validity, and divergence flag.
- Any missing replay metadata or `divergence=true` result fail-closes merge authorization status.

## Goal graph initialization fail-closed behavior

- `MutationExecutor` now treats `runtime/evolution/goal_graph.json` as a fail-closed initialization dependency in strict contexts.
- Parse/schema/I-O failures emit structured telemetry (`goal_graph_init_failed`) and halt initialization in strict/fail-closed modes.
- Empty-graph fallback is only permitted in explicitly non-strict development contexts (`ADAAD_ENV in {dev,test}` **and** `CRYOVANT_DEV_MODE=1`).


## Module map (composition-root refactor)

- `app/main.py` is the thin composition root and startup wire-up surface.
- `app/boot_preflight.py` owns boot environment validation and storage-profile config loading.
- `app/cli_args.py` owns CLI parser construction and replay-proof export argument flow.
- `app/replay_verification.py` owns replay preflight execution/state projection.
- `app/mutation_cycle.py` owns mutation cycle orchestration logic.
