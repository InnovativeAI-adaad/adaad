## [7.2.0] — 2026-03-12

### Phase 22 — Proposal Hardening

#### PR-22-01: `fallback_to_noop=False` as LLM default

`LLMProviderConfig.fallback_to_noop` default flipped from `True` → `False`.
`load_provider_config()` env-var default also flipped (`ADAAD_LLM_FALLBACK_TO_NOOP`
reads `"false"` when unset). LLM failures now surface as explicit error payloads
rather than silently returning noop proposals. Operators can restore the prior
behaviour by setting `ADAAD_LLM_FALLBACK_TO_NOOP=true`.

#### PR-22-02: `MarketFitnessIntegrator` default-on in `EvolutionLoop`

`EvolutionLoop.__init__()` auto-provisions a zero-configuration
`MarketFitnessIntegrator()` when `market_integrator` is not injected.
Market fitness is now always active; the auto-provisioned instance uses
synthetic fallback until a live `feed_registry` is wired (signal quality
degrades gracefully — no crash, no silent skip). Explicit injection still
respected for tests and custom wiring.

#### Tests — `tests/test_phase22_proposal_hardening.py`

14 tests, 14/14 passing (5 parametrized opt-in values for PR-22-01-C).

## [7.1.0] — 2026-03-12

### Phase 21 — Core Loop Closure: AutonomyLoop wired into EvolutionLoop.run_epoch()

Closes the critical gap identified at Phase 20: the intelligence stack built across
Phases 16–20 (`AutonomyLoop`, `IntelligenceRouter`, `CritiqueSignalBuffer`,
`RoutedDecisionTelemetry`) was fully isolated from the production execution path.
`EvolutionLoop.run_epoch()` now calls `AutonomyLoop.run()` as Phase 5g.

#### Architecture (PR-21-01)

- `EvolutionLoop.__init__()` accepts `autonomy_loop: Optional[AutonomyLoop] = None`
- **Phase 5g** inserted after the GovernanceDebtLedger accumulation step (5f):
  - Calls `AutonomyLoop.run()` with live epoch signals:
    - `cycle_id` ← `epoch_id`
    - `mutation_score` ← `WeightAdaptor.prediction_accuracy`
    - `governance_debt_score` ← `_last_debt_score` (Phase 15 accumulation)
    - `fitness_trend_delta` ← `health_score − _last_epoch_health_score`
    - `epoch_pass_rate` ← `accepted_count / total_candidates`
    - `lineage_health` ← `_last_lineage_proximity` (Phase 15-02)
  - `AutonomyLoop.reset_epoch()` called immediately after `run()` — clears
    `CritiqueSignalBuffer` at epoch boundary (constitutional invariant: cap 0.20
    applies per-epoch, not across epochs)
  - Full exception isolation — `AutonomyLoop` failure never halts the epoch

- `EpochResult` extended with four intelligence output fields:
  - `intelligence_decision: str` — `"hold"` | `"self_mutate"` | `"escalate"`
  - `intelligence_strategy_id: Optional[str]` — routing strategy selected
  - `intelligence_outcome: Optional[str]` — critique outcome (`"execute"` | `"hold"`)
  - `intelligence_composite: Optional[float]` — weighted critique aggregate ∈ [0,1]

- Default: `autonomy_loop=None` — Phase 5g is skipped silently; all four new
  EpochResult fields default to `"hold"` / `None` (fully backwards-compatible)

#### Tests — `tests/test_phase21_core_loop_closure.py`

13 tests, 13/13 passing:
- PR-21-01 … PR-21-10 contract tests
- Schema completeness test (`EpochResult` dataclass fields)

## [7.0.0] — 2026-03-12

### Phase 46 — MarketSignalAdapter Live Bridge to EconomicFitnessEvaluator

Closes the highest-ROI gap in the codebase: `MarketSignalAdapter` now wires
directly into `EconomicFitnessEvaluator` as a live, fail-closed signal source
for `simulated_market_score`.

#### Architecture

- `EconomicFitnessEvaluator.__init__()` accepts new optional parameter
  `live_market_adapter: MarketSignalAdapter | None = None`.
- `_simulated_market_score()` elevated: adapter path is now the
  **highest-priority** signal source, executing before payload inspection
  and all fallback paths.
- Fail-closed: adapter exceptions are caught, logged, and silently fallen
  through to the existing payload/default path — `evaluate()` never raises
  due to adapter failure.
- Bridge statistics: `_bridge_fetch_count` and `_bridge_fallback_count`
  tracked on the evaluator instance for observability.
- `market_bridge_status()` public method exposes bridge health: `wired`,
  `bridge_fetch_count`, `bridge_fallback_count`, `last_signal` snapshot.
- Type safety: `MarketSignalAdapter` imported under `TYPE_CHECKING` only —
  zero circular-import risk at runtime.

#### New endpoint

`GET /evolution/market-fitness-bridge` (auth: `audit:read`)

Returns bridge health envelope:
```json
{
  "ok": true,
  "bridge": {
    "wired": true,
    "bridge_fetch_count": 0,
    "bridge_fallback_count": 0,
    "last_signal": {
      "dau": 0.5, "retention_d7": 0.4,
      "simulated_market_score": 0.455,
      "source": "synthetic",
      "lineage_digest": "sha256:...",
      "ingested_at": 1234567890.0
    }
  },
  "phase": "46",
  "note": "synthetic baseline active — wire a live source_fn to activate real signal"
}
```

#### Constitutional invariants

- `live_market_adapter=None` (default): all existing evaluation paths
  unchanged — backward-compatible for every existing test and caller.
- Adapter score **overrides** payload `simulated_market_score` when wired.
- Adapter failure is logged and swallowed; never propagates.
- Score clamped to `[0.0, 1.0]` on all paths.

#### Tests

- `tests/test_market_fitness_bridge.py` — **20/20 passed** (T46-01..T46-20)
  - Payload fallback when no adapter (T46-01, T46-02)
  - Live adapter override (T46-03, T46-04)
  - Fail-closed on exception (T46-05, T46-06)
  - Bridge counters (T46-07, T46-08)
  - `market_bridge_status()` correctness (T46-09..T46-12)
  - Score clamping (T46-13, T46-14)
  - Endpoint schema + auth + signal (T46-15..T46-18)
  - Synthetic vs live source field (T46-19, T46-20)

---

## [6.9.2] — 2026-03-11


### Phase 44 — Main Hardening

Four defects resolved, one SyntaxWarning eliminated:

#### RC-1: `tests/test_aponi_dashboard_e2e.py` — `test_replay_diff_http_endpoint_persists_export_bundle`
- **Root cause**: `EvidenceBundleBuilder.build_bundle` requires `ADAAD_EVIDENCE_BUNDLE_SIGNING_KEY`
  environment variable at export time. Test did not inject it → `EvidenceBundleError:
  missing_export_signing_secret:forensics-dev` → `ok=False`.
- **Fix**: Added `monkeypatch.setenv("ADAAD_EVIDENCE_BUNDLE_SIGNING_KEY", "test-signing-secret-phase44")`
  at test entry. Signing gate is not weakened — the test now supplies a deterministic test secret.

#### RC-2: `ui/features/evidence_panel.py` — failure contract hardening
- `replay_diff_export` previously caught `EvidenceBundleError` and returned an unstructured envelope.
- **Fix**: Error envelope now includes `error_class` field for audit tracing. Unknown exceptions
  (non-`EvidenceBundleError`) now **re-raise** rather than being silently swallowed — fail-closed.

#### RC-3: `server.py` — lazy `import re` in simulation DSL parser
- `import re as _re` was inside `_parse_simulation_dsl` function body (lazy import).
- **Fix**: Promoted to module-level simulation block imports alongside `hashlib`, `threading`,
  `time`, `uuid`. Consistent with module import pattern; no behavioral change.

#### RC-4: `ui/aponi_dashboard.py` — invalid Python escape sequences (SyntaxWarning)
- Four JS regex patterns embedded in non-raw Python strings contained `\.?` as single
  backslash + dot — invalid Python escape sequences (SyntaxWarning in 3.12,
  SyntaxError in 3.13+).
- Lines affected: 2999, 4318, 4319, 4320.
- **Fix**: Replaced `\.?` → `[.]?` (semantically identical JS regex for optional literal dot;
  no backslash escaping required). `python3 -W error::SyntaxWarning` now compiles cleanly.

#### Tests
- Targeted suite: **50/50 passed**

## [6.9.1] — 2026-03-11

### Phase 43 Hardening — Thread-Safety + AST Import Validation

Two post-audit advisories resolved:

#### Advisory 1 — `_SIMULATION_STORE` thread-safety (`server.py`)
- Added `import threading as _threading` and `_SIMULATION_STORE_LOCK: threading.Lock`
- All reads and writes to `_SIMULATION_STORE` wrapped with `with _SIMULATION_STORE_LOCK:`
- Added inline documentation: under multi-worker uvicorn deployments each process holds an independent store; for cross-worker lookup, replace with a shared persistence layer (Redis, sqlite)

#### Advisory 2 — AST-based import validation (`tests/test_import_roots.py`)
- Replaced regex scanning with `ast.parse()` + `ast.walk()` over `Import` / `ImportFrom` nodes
- Eliminated the entire class of false positives from docstrings, comments, and string literals containing `from ` / `import `
- Import nodes inside `Try` blocks are now skipped (optional best-effort dependencies guarded by `except` clauses)
- Added `APPROVED_OPTIONAL_EXTERNALS` set: explicitly acknowledged optional third-party packages (`jsonschema`) used under `try/except` guards in `tools/interactive_onboarding.py` and `runtime/governance/simulation/profile_exporter.py`
- Removed unused `import re` (no longer needed)
- Failure output now sorted for deterministic CI diffs

#### Tests
- All 49 previously targeted tests: **49/49 passed**

## [6.9.0] — 2026-03-11

### Phase 43 — Governance Inviolability + Simulation Endpoints + Import-Root Enforcement

#### Root Causes Resolved (3 distinct, 16 tests fixed)

| ID | File | Root Cause | Tests Fixed |
|----|------|-----------|-------------|
| F43-1 | `tests/test_import_roots.py` | Quadruple-escaped regex `[\\\\w]` only matched `w` and `\\` — stdlib imports starting with `w` (e.g. `warnings`) emitted false-positive violations; also caused 3 `TestSandbox` subprocess test failures via cascade | 4 direct + 3 sandbox cascade |
| F43-2 | `runtime/constitution.py` + `tests/governance/inviolability/test_constitution_policy_inviolability.py` | Version-mismatch error message `constitution_version_mismatch:…` lacked `invalid_schema` token required by test; test's stale `.replace('"version": "0.3.0"'…)` didn't match updated policy file `0.7.0` | 2 |
| F43-3 | `server.py` | `POST /simulation/run` and `GET /simulation/results/{run_id}` routes missing entirely — 405 Method Not Allowed instead of 401/200 | 11 |

#### Changes

**`tests/test_import_roots.py`**
- Fixed regex: `[\\\\w\\\\.\\\\/]` → `[\w./]` — restores `\w` word-character class
- Restored `APPROVED_ROOTS` to full canonical set: `adaad`, `app`, `core`, `evolution`, `governance`, `memory`, `nexus_setup`, `runtime`, `sandbox`, `scripts`, `security`, `server`, `tests`, `tools`, `ui`, `warnings`, `cryptography`

**`runtime/constitution.py`**
- `_validate_policy_schema`: error message changed from `constitution_version_mismatch:{v}!={e}` to `constitution_policy_invalid_schema:version_mismatch:{v}!={e}` — satisfies both `invalid_schema` and `version_mismatch` match patterns

**`tests/governance/inviolability/test_constitution_policy_inviolability.py`**
- `test_version_mismatch_fails_close`: stale `.replace('"version": "0.3.0"'…)` updated to `.replace('"version": "0.7.0"'…)` to match current policy file

**`server.py`**
- Added `from pydantic import BaseModel`
- Added `POST /simulation/run` — auth-gated, DSL parser, simulation-only evaluator, zero ledger writes, `simulation=true` in every response
- Added `GET /simulation/results/{run_id}` — auth-gated, returns stored simulation envelope or deterministic not-found
- Added `_parse_simulation_dsl` — validates DSL syntax, raises `HTTP 422` on unknown constraints
- Added `_evaluate_simulation` — read-only epoch evaluation against parsed constraints
- Added `_SIMULATION_STORE` — in-process simulation result cache

**`tests/test_test_sandbox.py`**
- `test_post_hook_runs_before_cleanup`, `test_hook_failures_are_logged_not_raised`: `timeout_s` increased from 5 → 15 (pytest subprocess startup takes ~7s; 5s budget was insufficient)

**`runtime/governance/health_aggregator.py`**, **`fix_import_boundaries.py`**
- Docstring prose: `from four live signals…` → `using four live signals…`; `import into a single…` → `move into a single…` (false-positive import-root matches)

#### Tests
- `tests/test_import_roots.py` — **1/1 passed**
- `tests/test_test_sandbox.py` — **14/14 passed**
- `tests/governance/inviolability/test_constitution_policy_inviolability.py` — **23/23 passed**
- `tests/test_simulation_endpoints.py` — **11/11 passed**

## [6.8.1] — 2026-03-11

### fix(orchestrator): fail-closed runtime.metrics optional import handling

- `adaad/orchestrator/dispatcher.py` now only falls back to `runtime_metrics = None` for `ModuleNotFoundError` when `runtime`/`runtime.metrics` is absent.
- Non-optional missing dependency names during `runtime.metrics` import now raise deterministic `RuntimeError` instead of being swallowed.
- Added dispatcher import-guard unit tests covering optional fallback and non-`ModuleNotFoundError` propagation.

## [6.8.0] — 2026-03-11

### Phase 42 — Critical Defect Sweep

Resolved 6 distinct root causes covering 30+ pre-existing test failures.

| Fix | File | Root Cause | Tests Fixed |
|-----|------|-----------|-------------|
| F42-1 | `runtime/sandbox/environment_snapshot.py` | Missing `import json` → `NameError` in `capture_post_execution_delta` | 9 sandbox tests |
| F42-2 | `runtime/sandbox/executor.py` | `_record_evidence` used undefined `pre_execution_snapshot` local instead of `replay_environment_fingerprint` param | 3 sandbox tests |
| F42-3 | `runtime/metrics.py` + `runtime/analysis/adversarial_scenario_harness.py` | `metrics.tail(limit=200)` offset delta silently zero when file ≥200 lines; added `line_count()` + `tail_after()` | 1 security test (RTN-001) |
| F42-4 | `tests/stability/test_null_guards.py` | `_RegistryLedgerStub` missing `read_all()` method | 3 stability tests |
| F42-5 | `app/main.py` | `app.main.run_replay_preflight` / `run_mutation_cycle` module-level names absent; added + wired delegation | 2 main refactor tests |
| F42-6 | `app/beast_mode_loop.py` | `BeastModeLoop._legacy` property absent; added lazy-init `LegacyBeastModeCompatibilityAdapter` | _legacy AttributeError resolved |
| F42-7 | `runtime/evolution/checkpoint_registry.py` | `create_checkpoint` emitted `checkpoint_created` event type; changed to `CheckpointGovernanceEvent` with `prior_checkpoint_event_hash` | 2 evolution tests |
| F42-8 | `app/dream_mode.py` | `DreamMode._clamp_aggression` static method absent | 1 full_stack_upgrade test |

**Net result:** Baseline 160 failures → ~122 failures (−38), 3535 → 3573+ passing.

#### Tests
- `tests/server/test_phase42_defect_sweep.py` — **21/21 passed**

## [6.7.0] — 2026-03-11

### Phase 41 — Cryovant Gate Middleware + SPA Index Fallback

#### server.py
- **Centralized Cryovant gate** into single `cryovant_gate_middleware` HTTP middleware
  - Protected: `/api/nexus/handshake|protocol|agents`, `/api/governance/*`, `/api/fast-path/*`, `/api/nexus/mutate*`
  - Always open: `/api/health`, `/api/version`, `/api/nexus/health`, all non-`/api/` paths
  - Returns `HTTP 423` + `X-ADAAD-GATE: locked` + `X-ADAAD-Protocol` header when locked
- **Removed** per-endpoint `_assert_gate_open()` calls from `nexus_handshake`, `nexus_protocol`, `nexus_agents`
- **Added** `CORSMiddleware` — allows browser fetch from any `localhost` port; configurable via `ADAAD_CORS_ORIGINS`
- **Fixed** lifespan: creates stub `ui/aponi/index.html` if missing (was: `RuntimeError`); server now always starts
- **Added** `if __name__ == "__main__"` entry point: `python server.py` starts uvicorn on port 8080, prints startup URLs + gate status

#### ui/aponi_dashboard.py
- **Added** `_read_gate_state()` function mirroring server.py gate logic
- **Added** `_DASHBOARD_GATE_LOCK_FILE` + `_DASHBOARD_GATE_PROTOCOL` constants
- **Added** Cryovant gate check in `do_GET` — API data paths return `HTTP 423` when locked; `/` and `/index.html` always pass
- **Fixed** `_send_json` to accept `status_code` keyword argument (default 200)
- **Added** SPA fallback: unknown `GET` paths serve `ui/aponi/index.html` so browser deep-links work

#### Tests
- `tests/server/test_phase41_cryovant_middleware_spa.py` — **29/29 passed**
  - `TestGateState` (3): gate open/locked-by-env/locked-by-file
  - `TestServerConstants` (19): all middleware constants, CORS, lifespan, `__main__` block
  - `TestAponiDashboard` (7): gate enforcement, SPA fallback, `_send_json`, `_run_background`

## [6.6.0] — 2026-03-10 · Phase 40 — BeastModeLoop Determinism Provider Injection

### What shipped

**Phase 40 — BeastModeLoop `RuntimeDeterminismProvider` injection**

`app/beast_mode_loop.py` — `BeastModeLoop.__init__()` now accepts three new
keyword-only parameters: `provider` (`RuntimeDeterminismProvider`),
`replay_mode` (`"off"` | `"strict"`), and `recovery_tier` (governance tier string).

All `time.time()` calls inside `_check_limits()` and `_check_mutation_quota()` are
replaced with `self._now()` which delegates to `provider.now_utc()`.  This makes
every throttle timestamp and cooldown calculation fully replay-safe and
audit-verifiable.

**Constitutional invariants:**

- `require_replay_safe_provider()` called at construction — strict replay and
  governance-critical tiers (`audit`, `governance`, `critical`) reject
  `SystemDeterminismProvider` fail-closed before any cycle executes.
- Auto-provisioning: strict/audit tiers with no explicit provider receive a
  `SeededDeterminismProvider` seeded from `ADAAD_DETERMINISTIC_SEED`.
- Backward-compatibility: callers that omit all three kwargs receive
  `SystemDeterminismProvider` with identical observable behaviour.
- `LegacyBeastModeCompatibilityAdapter` inherits injection via `super().__init__()`.

**Tests: `tests/determinism/test_beast_mode_provider_determinism.py`**
14 tests (T40-B01 .. T40-B12 with parametrize) — **14/14 green (100%)**

---

## [6.5.2] — 2026-03-11

### fix(server): nexus_health gate_ok field missing — UI always locked

**Root cause:** `probeHealth()` in `ui/aponi/index.html` checks `data.gate_ok !== true`
against the response from `GET /api/nexus/health`. The `nexus_health()` endpoint
returned `{"ok": ..., "protocol": ..., "gate": ...}` — the `gate_ok` field was never
included. Since `undefined !== true` is always `true`, the UI evaluated the gate as
locked on every poll regardless of actual gate state.

`GET /api/health` (different endpoint) correctly returned `gate_ok`, but the UI polls
`/api/nexus/health`, not `/api/health`.

**Fix:** `nexus_health()` now returns `gate_ok` alongside `ok` — both set to
`not gate["locked"]`. The fix is a one-field addition; no logic change.

**Test:** `tests/test_nexus_health_gate_ok.py` — 8 tests including:
- `test_gate_ok_field_present` — gate_ok must be in response
- `test_gate_ok_is_true_when_unlocked` — must be exactly `True` (not just truthy)
- `test_ok_matches_gate_ok` — both fields must agree

**Files changed:**
- `server.py` — `nexus_health()`: add `gate_ok` to response
- `tests/test_nexus_health_gate_ok.py` — new regression test (8 tests)

---

## [6.5.1] — 2026-03-10

### docs: Harden all docs — accuracy, navigation, and awe

Comprehensive accuracy and hardening pass across every user-facing doc.

#### Accuracy fixes

- **VERSION** — updated from stale `6.0.0` to `6.5.0`
- **Constitution rule counts** — README hero text and governance section now
  accurately state "18 rules — 9 globally blocking, 4 tier-conditional blocking"
  (was: vague "18 deterministic rules, evaluated in order")
- **Constitution version** — `docs/README.md` incorrectly referenced `v0.7.0`
  throughout; corrected to `v0.3.0` (authoritative: `runtime/governance/constitution.yaml`)
- **docs/README.md** — all badges, version infobox, status table, and footer
  updated: v6.0.0 → v6.5.0, Phase 35 → Phase 39, 810 tests → 846 tests
- **INSTALL_ANDROID.md** — version bump v6.4.0 → v6.5.0
- **TERMUX_SETUP.md** — license corrected MIT (was Apache-2.0); version added

#### Navigation improvements

- **README.md** — nav bar now includes `Governance` anchor alongside Quick Start,
  How It Works, Android, Current Status, Constitution, Roadmap
- **README.md** — "What's active now" section restructured: recent phases table,
  full REST endpoint inventory, Phase 6 milestones, direct links to CHANGELOG/
  ROADMAP/VERSION — one place to understand current system state
- **QUICKSTART.md** — full rewrite: manual fallback, soulbound key warning,
  dashboard launch, epoch execution, test suite notes, env var quick-ref table,
  "Where to go next" navigation table
- **docs/README.md** — audience-based routes and quick-paths preserved; all
  stale content updated

#### Files changed
- `VERSION` — `6.0.0` → `6.5.0`
- `README.md` — rule accuracy, phase badge, nav bar, governance section
- `QUICKSTART.md` — full rewrite (accurate output, env vars, nav table)
- `INSTALL_ANDROID.md` — version bump
- `TERMUX_SETUP.md` — license fix, version header
- `docs/README.md` — badges, infobox, status table, constitution version, footer

---

## [6.5.0] — 2026-03-10

### fix(termux): Android Termux compatibility fixes (Complete)

Resolves three issues observed in the Termux session log.

#### Fixed

**1 — `@app.on_event("startup")` deprecation warning (`server.py`)**
- Replaced `@app.on_event("startup")` with a `@asynccontextmanager` `_lifespan`
  function passed to `FastAPI(lifespan=_lifespan)`.
- Eliminates the `DeprecationWarning` printed on every `server.py` start.
- Zero test regressions — all 60 governance endpoint tests pass.

**2 — `metadata-generation-failed` for PyNaCl on Termux (`onboard.py`)**
- Added `_is_termux()` detector (checks `$PREFIX` and `/data/data/com.termux`).
- When Termux is detected, `pip install` automatically receives
  `--only-binary :all: --prefer-binary` — skips source builds that require
  a C compiler for `PyNaCl`/`cffi`.
- Prints explicit recovery instructions when native deps fail:
  `pkg install libsodium python-cryptography -y`.

**3 — `pip install adaad` fails (not on PyPI)**
- `INSTALL_ANDROID.md`: added dedicated **Termux** section with copy-paste
  install sequence, native dep table, and soulbound key setup.
- `INSTALL_ANDROID.md`: added 5 new Termux-specific troubleshooting rows.
- `TERMUX_SETUP.md`: new standalone Termux reference guide — quick start,
  step-by-step install, environment setup, epoch execution, update flow,
  full troubleshooting table, and architecture note.
- `README.md`: added Termux install method row to Android section.

#### Files changed
- `server.py` — `asynccontextmanager` lifespan replaces `@app.on_event`
- `onboard.py` — `_is_termux()` + `--only-binary` + Termux recovery messages
- `INSTALL_ANDROID.md` — Termux section + troubleshooting rows + version bump
- `TERMUX_SETUP.md` — new file (complete Termux guide)
- `README.md` — Termux install method table in Android section

---

## [6.4.0] — 2026-03-10

### Phase 39 — DreamMode Determinism Provider Injection (Complete)

Phase 39 closes the architectural gap between `DreamMode` and the
`RuntimeDeterminismProvider` contract established in Phase 7+.  All clock and
token calls inside `DreamMode` are now provider-routed, making the agent
fully replay-safe and audit-verifiable.

#### Changed — `app/dream_mode.py`
- **`provider` param added to `__init__`**: accepts any `RuntimeDeterminismProvider`;
  defaults to `SystemDeterminismProvider()` in non-strict modes.
- **Auto-provisioning**: when `replay_mode="strict"` or recovery tier is
  `audit/governance/critical` and no provider is supplied, a
  `SeededDeterminismProvider` is automatically constructed from
  `ADAAD_DETERMINISTIC_SEED` (default `"adaad-dream-default"`) — preserving
  backward-compat for callers that rely on strict mode without explicit injection.
- **Fail-closed guard**: `require_replay_safe_provider()` called at construction —
  non-deterministic providers in strict/audit contexts raise `RuntimeError`
  immediately.
- **`issued_at` provider-routed**: `handoff_contract["issued_at"]` now uses
  `self.provider.iso_now()` instead of `time.strftime()` — enables clock
  injection in tests and pinned-epoch deterministic replay.
- **Token provider-routed**: non-strict token path uses
  `self.provider.next_token(label="dream_token")` instead of `time.time()`.
- **`discover_tasks()` payload controlled**: emits `task_count` + `task_sample`
  (capped at `ADAAD_DREAM_DISCOVERY_SAMPLE_SIZE`, default 3) rather than full
  task list; adds `tasks` only when `ADAAD_METRICS_INCLUDE_FULL_TASKS=1`.
- **`entropy_budget`**: exposed as instance attribute for test-harness reset.

#### Fixed
- **8 failing determinism tests** (`tests/determinism/test_dream_mode_provider_determinism.py`):
  all 8 now pass — strict-mode reproducibility, provider token generation,
  clock injection, replay equivalence, audit-tier rejection, discovery payload.
- **1 entropy triage spec drift** (`test_entropy_anomaly_triage_replay.py`):
  reanchored 4 fixture `expected_triage_level` values to Phase 34's
  `EntropyAnomalyTriageThresholds` ratio-based taxonomy
  (`"ok"/"warning"/"escalate"/"critical"`) which overrides the legacy
  bit-threshold taxonomy (`"none"/"monitor"/"investigate"/"block"`).

#### Added — `tests/conftest.py`
Shared pytest infrastructure: `auth_headers()`, `audit_env()`, `make_audit_client()`,
and assertion helpers (`assert_schema_version`, `assert_required_keys`,
`assert_rate_complement`, `assert_nonneg_int`, `assert_sha256_prefix`) — eliminates
per-endpoint fixture boilerplate and establishes a scalable test infrastructure
baseline for all future governance endpoint phases.

#### Test counts
- **9 tests fixed** (8 determinism + 1 triage spec): **✅ 100%**
- **No regressions** in determinism suite (71 tests all green)
- **Total targeted suite**: 939 tests green

---

## [6.3.0] — 2026-03-10

### Phase 38 — Mutation Ledger REST Endpoint (Complete)

Phase 38 surfaces `MutationLedger` via a read-only authenticated REST endpoint,
completing REST observability coverage across all ADAAD hash-chained audit ledgers.

#### Added
- **`GET /governance/mutation-ledger`** (`server.py`): bearer-auth-gated
  (`audit:read`), read-only. Query params: `limit` (default 20),
  `promoted_only` (default False). Returns `entries`, `total_in_window`,
  `total_entries`, `promoted_count`, `last_hash`, `ledger_version`.
- **12 new endpoint tests**: `tests/test_mutation_ledger_endpoint.py`
  (T38-EP-01..12) — 100% pass rate. Covers 200 OK, schema_version, all
  required data keys, entries type, ledger_version, 401 missing auth,
  403 wrong scope, total_in_window/total_entries non-negative int types,
  window ≤ total invariant, promoted_count non-negative int,
  last_hash sha256: prefix invariant.

#### Invariants preserved
- `GET /governance/mutation-ledger` is read-only — no side effects.
- Advisory only: endpoint reads ledger history; never approves or blocks mutations.
- `GovernanceGate` retains sole mutation-approval authority.
- `total_in_window <= total_entries` structural invariant enforced (tested).
- `last_hash` always carries `sha256:` prefix (genesis or chain tail), tested.
- `GovernanceGate` isolation: endpoint imports `MutationLedger` only.

#### Test counts
- **12 new tests**: `tests/test_mutation_ledger_endpoint.py` (T38-EP-01..12): **✅ 100%**
- **Total test suite**: 846 tests

---

## [6.2.0] — 2026-03-10

### Phase 37 — Reviewer Reputation Ledger REST Endpoint (Complete)

Phase 37 surfaces `ReviewerReputationLedger` (Phase 7) via a read-only authenticated
REST endpoint, closing the last major audit ledger without a REST observability
surface. Completes the ledger→endpoint pattern across all ADAAD audit subsystems.

#### Added
- **`GET /governance/reviewer-reputation-ledger`** (`server.py`): bearer-auth-gated
  (`audit:read`), read-only. Query params: `limit` (default 20),
  `epoch_id` (optional, filters by governance epoch). Returns `entries`,
  `total_in_window`, `total_entries`, `decision_breakdown`, `chain_integrity_valid`,
  `ledger_digest`, `ledger_format_version`.
- **12 new endpoint tests**: `tests/test_reviewer_reputation_ledger_endpoint.py`
  (T37-EP-01..12) — 100% pass rate. Covers 200 OK, schema_version, all
  required data keys, entries type, ledger_format_version, 401 missing auth,
  403 wrong scope, total_in_window/total_entries non-negative int types,
  window ≤ total invariant, chain_integrity_valid bool, decision_breakdown dict.

#### Invariants preserved
- `GET /governance/reviewer-reputation-ledger` is read-only — no side effects.
- Advisory only: endpoint reads ledger history; never approves or blocks mutations.
- `GovernanceGate` retains sole mutation-approval authority.
- `total_in_window <= total_entries` structural invariant enforced (tested).
- Chain integrity verified on every request via `verify_chain_integrity()`.
- `GovernanceGate` isolation: endpoint imports `ReviewerReputationLedger` only.

#### Test counts
- **12 new tests**: `tests/test_reviewer_reputation_ledger_endpoint.py` (T37-EP-01..12): **✅ 100%**
- **Total test suite**: 834 tests

---

## [6.1.0] — 2026-03-10

### Phase 36 — Gate Decisions REST Endpoint (Complete)

Phase 36 surfaces `GateDecisionLedger` (Phase 35) via a read-only authenticated
REST endpoint, completing the gate-decision observability surface and matching
the pattern established by `/governance/certifier-scans` (Phase 34),
`/governance/threat-scans` (Phase 30), and `/governance/debt` (Phase 31).

#### Added
- **`GET /governance/gate-decisions`** (`server.py`): bearer-auth-gated
  (`audit:read`), read-only. Query params: `limit` (default 20),
  `denied_only` (default False). Returns `records`, `total_in_window`,
  `approval_rate`, `rejection_rate`, `human_override_count`,
  `decision_breakdown`, `failed_rules_frequency`, `trust_mode_breakdown`,
  `ledger_version`.
- **12 new endpoint tests**: `tests/test_gate_decisions_endpoint.py`
  (T36-EP-01..12) — 100% pass rate. Covers 200 OK, schema_version, all
  required data keys, records type, ledger_version, limit/denied_only params,
  401 missing auth, 403 wrong scope, approval_rate float range,
  rejection_rate float range, complement invariant, human_override_count,
  decision_breakdown type.

#### Invariants preserved
- `GET /governance/gate-decisions` is read-only — no side effects.
- Advisory only: endpoint reads decision history; never approves or blocks mutations.
- `GovernanceGate` retains sole mutation-approval authority.
- `approval_rate + rejection_rate == 1.0` (complement invariant, tested).
- `GovernanceGate` isolation: endpoint imports only `GateDecisionReader`; never imports `GovernanceGate` directly.

#### Test counts
- **12 new tests**: `tests/test_gate_decisions_endpoint.py` (T36-EP-01..12): **✅ 100%**
- **Total test suite**: 822 tests

---

## [6.0.0] — 2026-03-10

### Phase 35 — Gate Decision Ledger & Approval Rate Health Signal (Complete)

Phase 35 closes the `GovernanceGate` observability gap: every
`approve_mutation()` outcome is now persisted in a SHA-256 hash-chained
append-only JSONL audit ledger (`GateDecisionLedger`), and the gate approval
rate becomes the **9th governance health signal** (`gate_approval_rate_score`,
weight 0.05). All 9 signals sum to 1.00.

#### Added
- **`GateDecisionLedger`** (`runtime/governance/gate_decision_ledger.py`): append-only SHA-256 hash-chained JSONL ledger for `GateDecision.to_payload()` dicts; `emit()` fail-safe; inactive by default.
- **`GateDecisionReader`**: `approval_rate()`, `rejection_rate()`, `history(denied_only=...)`, `decision_breakdown()`, `failed_rules_frequency()`, `human_override_count()`, `trust_mode_breakdown()`, `verify_chain()`.
- **`GateDecisionChainError`**: raised on chain integrity violation; carries `sequence` and `detail`.
- **`gate_approval_rate_score`** (9th signal, weight 0.05): score = `approval_rate`. Fail-safe 1.0.
- **`HealthSnapshot.gate_decision_report`**: `approval_rate`, `rejection_rate`, `human_override_count`, `available`.
- **`tests/governance/test_gate_decision_ledger.py`**: 43 tests (T35-L01..L13, R01..R11, S01..S19): **100%**.

#### Changed
- **`SIGNAL_WEIGHTS`** rebalanced (9 signals, sum = 1.00): rep 0.19→0.18, amendment 0.17→0.16, fed 0.17→0.16, debt 0.09→0.08, certifier 0.07→0.06, gate new 0.05.
- 7 updated numeric-assertion tests across `test_governance_health_aggregator.py`, `test_debt_health_signal.py`, `test_certifier_scan_ledger.py`.

#### Test counts
- **43 new tests** — T35-L/R/S: **✅ 100%**
- **Total test suite**: 810 tests

---

## [5.9.0] — 2026-03-10

### Phase 34 — Certifier Scans REST Endpoint (Complete)

Phase 34 surfaces `CertifierScanLedger` (Phase 33) via a read-only authenticated
REST endpoint, completing the certifier audit observability surface and matching
the pattern established by `/governance/threat-scans` (Phase 30) and
`/governance/admission-audit` (Phase 27).

#### Added

- **`GET /governance/certifier-scans`** (`server.py`): bearer-auth-gated
  (`audit:read`), read-only. Query params: `limit` (default 20),
  `rejected_only` (default False). Returns `records`, `total_in_window`,
  `rejection_rate`, `certification_rate`, `mutation_blocked_count`,
  `fail_closed_count`, `escalation_breakdown`, `ledger_version`.
- **12 new endpoint tests**: `tests/test_certifier_scans_endpoint.py`
  (T34-EP-01..12) — 100% pass rate. Covers 200 OK, schema_version, all
  required data keys, records type, ledger_version, limit/rejected_only
  params, 401 missing auth, 403 wrong scope, rate float range, complement
  invariant, escalation_breakdown type.

#### Invariants preserved

- `GET /governance/certifier-scans` is read-only — no side effects.
- Advisory only: endpoint reads scan history; never approves or blocks mutations.
- `GovernanceGate` retains sole mutation-approval authority.
- `certification_rate + rejection_rate == 1.0` (mathematical invariant, tested).

#### Test counts

- **12 new tests**: `tests/test_certifier_scans_endpoint.py` (T34-EP-01..12): **✅ 100%**
- **Total test suite**: 779 tests

---

## [5.9.0] — 2026-03-10

### Phase 34 — Certifier Scan REST Endpoint + Entropy Anomaly Triage (Complete)

Phase 34 ships two independently gapped capabilities:

1. **`GET /governance/certifier-scans`** — read-only authenticated REST endpoint
   surfacing `CertifierScanLedger` scan history, rejection rate, escalation
   breakdown, and mutation-blocked counts. Mirrors `GET /governance/threat-scans`
   (Phase 30) pattern.

2. **`EntropyAnomalyTriageThresholds`** — ratio-based anomaly triage class
   (`warning_ratio / escalate_ratio / critical_ratio`) wired into `EntropyPolicy`
   as a new `anomaly_triage` field. Deterministically classifies entropy budget
   utilisation into `"ok"` / `"warning"` / `"escalate"` / `"critical"` /
   `"disabled"` triage levels.

#### Added

- **`GET /governance/certifier-scans`** (`server.py`):
  - Query params: `limit` (default 20), `rejected_only` (default False)
  - Response: `records`, `total_in_window`, `rejection_rate`, `certification_rate`,
    `mutation_blocked_count`, `fail_closed_count`, `escalation_breakdown`,
    `ledger_version`
  - Auth-gated: `_require_audit_read_scope`
  - Read-only advisory: GovernanceGate retains sole mutation authority
- **`EntropyAnomalyTriageThresholds`** (`runtime/evolution/entropy_policy.py`):
  - Fields: `warning_ratio=0.70`, `escalate_ratio=0.90`, `critical_ratio=1.00`
  - `classify(mutation_ratio, epoch_ratio, policy_enabled) -> str`
  - Exported in `__all__` alongside `EntropyAnomalyThresholds`
- **`EntropyPolicy.anomaly_triage`** field (default `EntropyAnomalyTriageThresholds()`):
  - `enforce()` sets `detail["triage_level"]` via ratio classification
  - Disabled branch sets `"triage_level": "disabled"` (overrides detail spread)
  - `mutation_utilization_ratio` and `epoch_utilization_ratio` in all verdicts
- **`tests/evolution/test_entropy_policy_triage.py`** (3 tests): 100% pass rate

#### Fixed

- `EntropyPolicy.anomaly_triage` attribute error: field was called in `enforce()`
  but never declared — resolved by adding `anomaly_triage` dataclass field
- Disabled-path `triage_level` override ordering: `"disabled"` now placed after
  `**detail` spread so it correctly overrides the bits-based classification
- `dataclasses.field` import missing from `entropy_policy.py`
- `tests/evolution/test_entropy_policy_triage.py` collection error:
  `EntropyAnomalyTriageThresholds` now a real class (was missing entirely)

#### Test counts

- **3 new tests**: `tests/evolution/test_entropy_policy_triage.py` (triage determinism, disabled, ratio): **✅ 100%**
- **32 existing endpoint tests**: `test_certifier_scans_endpoint.py` + `test_debt_and_certifier_endpoints.py`: **✅ all passing**
- **Total test suite**: 802 tests — zero regressions

---

## [5.8.0] — 2026-03-10

### Phase 33 — Certifier Scan Ledger & Rejection Rate Health Signal (Complete)

Phase 33 closes the GateCertifier (Phase 31) observability gap: scan results are
now persisted in a SHA-256 hash-chained append-only JSONL audit ledger
(`CertifierScanLedger`), and the certifier rejection rate becomes the 8th
governance health signal, contributing 7% of the composite health score `h`.

#### Added

- **`CertifierScanLedger`** (`runtime/governance/certifier_scan_ledger.py`):
  append-only SHA-256 hash-chained JSONL ledger for `GateCertifier.certify()`
  result dicts; `emit()` fail-safe; `chain_verify_on_open` guard; inactive by
  default (`path=None` → no file); parent directory auto-created; resumes
  sequence on reopen.
- **`CertifierScanReader`**: read-only analytics — `history()` with limit /
  `rejected_only`; `rejection_rate()`; `certification_rate()`; `mutation_blocked_count()`;
  `fail_closed_count()`; `escalation_breakdown()`; `verify_chain()`.
- **`CertifierScanChainError`**: raised on any hash-chain integrity violation;
  carries `sequence` and `detail` fields.
- **`certifier_rejection_rate_score`** (8th signal): `GovernanceHealthAggregator`
  now accepts `certifier_scan_reader=CertifierScanReader` kwarg. Score computed
  as `1.0 - rejection_rate`. Fail-safe: returns `1.0` on missing reader, empty
  history, or any exception.
- **`HealthSnapshot.certifier_report`**: Optional dict — `rejection_rate`,
  `certification_rate`, `mutation_blocked_count`, `available`.
- **`tests/governance/test_certifier_scan_ledger.py`**: 38 acceptance-criteria tests
  — 100% pass rate. Covers ledger (L01..L12), reader (R01..R08), signal (S01..S18).

#### Changed

- **`SIGNAL_WEIGHTS`** rebalanced to accommodate 8th signal (sum = 1.00):

  | Signal | Old (Ph.32) | New (Ph.33) |
  |--------|-------------|-------------|
  | `avg_reviewer_reputation` | 0.20 | **0.19** |
  | `amendment_gate_pass_rate` | 0.18 | **0.17** |
  | `federation_divergence_clean` | 0.18 | **0.17** |
  | `epoch_health_score` | 0.13 | **0.12** |
  | `routing_health_score` | 0.11 | **0.10** |
  | `admission_rate_score` | 0.10 | **0.09** |
  | `governance_debt_health_score` | 0.10 | **0.09** |
  | `certifier_rejection_rate_score` | — | **0.07** (new) |

- Updated numeric-assertion tests in `test_governance_health_aggregator.py`
  and `test_debt_health_signal.py` to reflect new weight baseline.

#### Invariants preserved

- Weight sum invariant: `sum(SIGNAL_WEIGHTS.values()) == 1.00` (CI-enforced).
- `GovernanceGate` retains sole mutation-approval authority.
- `certifier_rejection_rate_score` is advisory input to `h`.
- Append-only: no record is ever overwritten or deleted.
- Emit failure isolation: I/O errors never propagate to callers.
- Deterministic replay: same scan sequence → same chain hashes.
- Backward compatible: callers without `certifier_scan_reader` unchanged.

#### Test counts

- **38 new tests**: `tests/governance/test_certifier_scan_ledger.py` (T33-L/R/S): **✅ 100%**
- **5 updated tests**: weight baseline updates in `test_governance_health_aggregator.py` and `test_debt_health_signal.py`
- **Total test suite**: 767 tests

---

## [5.7.0] — 2026-03-10

### Phase 32 — Governance Debt Health Signal Integration (Complete)

Phase 32 closes the integration gap between Phase 31 (`GovernanceDebtLedger`)
and the `GovernanceHealthAggregator`: `compound_debt_score` is now the 7th
governance health signal, normalized to `[0.0, 1.0]` and contributing 10% of
the composite health score `h`. The signal is fail-safe (defaults to `1.0`
when no ledger is wired or no snapshot exists) and deterministically replayable.
Weight sum invariant preserved: all 7 signals sum to `1.00`.

#### Added

- **`governance_debt_health_score`** (7th signal): `GovernanceHealthAggregator`
  now accepts `debt_ledger=GovernanceDebtLedger` kwarg. Score computed as
  `max(0.0, 1.0 - compound_debt_score / breach_threshold)` — 1.0 = pristine,
  0.0 = fully breached. Fail-safe: returns `1.0` on missing ledger, no snapshot,
  `breach_threshold ≤ 0`, or any exception.
- **`HealthSnapshot.debt_report`**: Optional dict field populated when ledger is
  wired and a snapshot exists. Fields: `compound_debt_score`, `breach_threshold`,
  `threshold_breached`, `warning_count`, `snapshot_hash`, `available`.
- **`tests/governance/test_debt_health_signal.py`**: 23 acceptance-criteria tests
  — 100% pass rate. Covers fail-safe paths, normalization at 0/0.5/1.0 boundary,
  over-breach clamping, misconfiguration guard, determinism, backward compatibility,
  weight sum invariant, and weight rebalance values.

#### Changed

- **`SIGNAL_WEIGHTS`** rebalanced to accommodate 7th signal (sum = 1.00):

  | Signal | Old weight | New weight |
  |--------|-----------|-----------|
  | `avg_reviewer_reputation` | 0.22 | **0.20** |
  | `amendment_gate_pass_rate` | 0.20 | **0.18** |
  | `federation_divergence_clean` | 0.20 | **0.18** |
  | `epoch_health_score` | 0.15 | **0.13** |
  | `routing_health_score` | 0.13 | **0.11** |
  | `admission_rate_score` | 0.10 | 0.10 |
  | `governance_debt_health_score` | — | **0.10** (new) |

- **3 existing tests** in `test_governance_health_aggregator.py` updated to reflect
  new weight baseline values (numeric assertions only; test intent unchanged).

#### Invariants preserved

- Weight sum invariant: `sum(SIGNAL_WEIGHTS.values()) == 1.00` (CI-enforced).
- `GovernanceGate` retains sole mutation-approval authority.
- `governance_debt_health_score` is advisory input to `h`; `h` is itself advisory.
- Deterministic replay: identical `(compound_debt_score, breach_threshold)` →
  identical `governance_debt_health_score`.
- Fail-safe: absent ledger, missing snapshot, or any exception → `1.0` (never stalls).
- Backward compatibility: callers without `debt_ledger` continue to work unchanged.

#### Test counts

- **23 new tests**: `tests/governance/test_debt_health_signal.py` (T32-01..22): **✅ 100%**
- **3 updated tests**: `test_governance_health_aggregator.py` (T8-01-07, T8-01-09, T8-01-21)
- **Total test suite**: 775 tests

---

## [5.6.0] — 2026-03-10

### Phase 31 — Governance Debt & Gate Certifier Endpoints (Complete)

Phase 31 closes the two remaining API gaps in the governance runtime surface:
GET /governance/debt exposes the live GovernanceDebtLedger snapshot with decay,
breach detection, and hash-chaining; POST /governance/certify runs the
GateCertifier security scanner against any repo-relative Python file.

#### Added

- **`GET /governance/debt`**: bearer-auth-gated (audit:read), read-only; returns
  live GovernanceDebtLedger snapshot including compound_debt_score, breach_threshold,
  threshold_breached, warning_count, warning_rules, snapshot_hash; falls back to
  zero-state snapshot when no live epoch data is available.
- **`POST /governance/certify`**: bearer-auth-gated (audit:read); accepts
  file_path (repo-relative) + optional metadata; runs GateCertifier AST security
  scan; returns CERTIFIED | REJECTED status, escalation level, mutation_blocked,
  fail_closed, per-check breakdown; rejects absolute paths and path traversal (422).
- **21 new unit tests**: `tests/governance/test_governance_debt_service.py` (T31-01..06).
- **20 new endpoint tests**: `tests/test_debt_and_certifier_endpoints.py` (T31-EP-01..20).

#### Invariants preserved

- GET /governance/debt is read-only — no side effects on GovernanceGate authority.
- POST /governance/certify is advisory-only — result is informational; GovernanceGate
  retains sole mutation-approval authority.
- Path traversal protection on certify endpoint (relative paths only, within repo root).

---

## [5.5.0] — 2026-03-10

### Phase 30 — Threat Scan Ledger & Endpoint (Complete)

Phase 30 closes the ThreatMonitor observability gap: scan results now flow
into a SHA-256 hash-chained append-only JSONL ledger (ThreatScanLedger),
surfaced via a read-only authenticated REST endpoint. Mirrors the
AdmissionAuditLedger pattern from Phase 27.

#### Added

- **`ThreatScanLedger`** (`runtime/governance/threat_scan_ledger.py`):
  append-only SHA-256 hash-chained JSONL ledger for ThreatMonitor scan dicts;
  emit() fail-safe (never raises); chain_verify_on_open guard; inactive by
  default (path=None → no file); parent directory auto-created; resumes
  sequence on reopen.
- **`ThreatScanReader`**: read-only analytics — history() with limit,
  recommendation_filter, triggered_only; recommendation_breakdown();
  triggered_rate(); escalation_rate(); avg_risk_score(); risk_level_breakdown();
  verify_chain().
- **`ThreatScanChainError`**: raised on any hash-chain integrity violation;
  carries sequence and detail fields.
- **`GET /governance/threat-scans`**: bearer-auth-gated (audit:read), read-only;
  accepts limit, recommendation, triggered_only query params; returns records,
  triggered_rate, escalation_rate, avg_risk_score, recommendation_breakdown,
  risk_level_breakdown, ledger_version.
- **36 new unit tests**: `tests/governance/test_threat_scan_ledger.py` (T30-01..09).
- **10 new endpoint tests**: `tests/test_threat_scan_endpoint.py` (T30-EP-01..10).

#### Invariants preserved

- GovernanceGate retains sole mutation-approval authority.
- Append-only: no record is ever overwritten or deleted.
- Deterministic replay: same scan sequence → same chain hashes.
- Emit failure isolation: I/O errors never surface to callers.

---

## [5.4.0] — 2026-03-10

### Phase 29 — Enforcement Verdict Audit Binding (Complete)

Phase 29 closes the enforcement audit loop: AdmissionAuditLedger.emit() now
accepts an optional EnforcerVerdict (Phase 28) and persists its fields
(escalation_mode, blocked, block_reason, verdict_digest, enforcer_version)
into the SHA-256 hash-chained JSONL record, covered by record_hash.
AdmissionAuditReader gains three enforcement analytics methods.

#### Changed

- **`AdmissionAuditLedger.emit(decision, *, verdict=None)`**: extended to
  accept optional EnforcerVerdict; when provided, enforcement fields written
  into chained record payload and covered by record_hash; backward-compatible
  (existing callers without verdict get enforcement_present=False / null fields).
- **`_build_record()`**: accepts verdict kwarg; enforcement fields always
  present in output (None when verdict=None).
- **`ADMISSION_LEDGER_VERSION`**: bumped `"27.0" → "29.0"`.
- **`GET /governance/admission-audit`**: response data extended with
  blocked_count, enforcement_rate, escalation_breakdown, blocked_only param.

#### Added

- **`AdmissionAuditReader.blocked_count()`**: count of blocked==True records.
- **`AdmissionAuditReader.enforcement_rate()`**: fraction of records with enforcement data.
- **`AdmissionAuditReader.escalation_mode_breakdown()`**: mode → count dict.
- **`AdmissionAuditReader.history_with_enforcement()`**: filtered history for enforcement records.
- **30 new unit tests**: `tests/governance/test_enforcement_verdict_audit.py` (T29-01..08).
- **6 new endpoint tests**: `tests/test_admission_enforcement_endpoint.py` (T29-EP-01..06).

#### Invariants preserved

- Chain hash determinism: same decision+verdict sequence → same chain hashes.
- GovernanceGate retains sole mutation-approval authority.
- advisory_only structurally True on every AdmissionDecision.
- Emit failure isolation: I/O errors never propagate to callers.

---

## [5.3.0] — 2026-03-10

### Phase 28 — Admission Band Enforcement Binding (Complete)

Phase 28 wires the advisory AdmissionDecision (Phase 25) into a new
enforcement layer — AdmissionBandEnforcer — that resolves escalation mode
from ADAAD_SEVERITY_ESCALATIONS and can escalate HALT-band outcomes to
blocking when operators explicitly opt in. Advisory mode (default) is
unchanged; GovernanceGate retains sole actual mutation-approval authority.

#### Added

- **`AdmissionBandEnforcer`** (`runtime/governance/admission_band_enforcer.py`):
  resolves escalation mode from env var; evaluates MutationAdmissionController
  result; `blocked=True` only when mode=blocking AND band=halt (emergency stop
  only); deterministic verdict_digest over (decision_digest, blocked, block_reason);
  fail-safe: None/invalid health_score defaults to GREEN (1.0).
- **`EnforcerVerdict`**: frozen dataclass carrying AdmissionDecision,
  escalation_mode, blocked, block_reason, verdict_digest, enforcer_version.
- **`GET /governance/admission-enforcement`**: bearer-auth-gated (`audit:read`),
  read-only; accepts risk_score query param; returns full EnforcerVerdict payload.
- **29 new unit tests**: `tests/governance/test_admission_band_enforcer.py`.
- **10 new endpoint tests**: `tests/test_admission_enforcement_endpoint.py`.

#### Invariants preserved

- `advisory_only: True` is structurally preserved on the underlying AdmissionDecision.
- GovernanceGate retains sole mutation-approval authority; enforcer never imports it.
- Deterministic: identical inputs → identical verdict_digest.
- Fail-safe: any exception defaults to GREEN-band advisory (never silently stalls pipeline).

---

## [5.2.0] — 2026-03-10

### Phase 27 — Admission Audit Ledger (Complete)

Phase 27 makes every `AdmissionDecision` evidence-bound: `AdmissionAuditLedger`
persists each advisory outcome to a SHA-256 hash-chained append-only JSONL
ledger, and `AdmissionAuditReader` provides a read-only analytics surface over
the ledger. The pattern mirrors `PressureAuditLedger` (Phase 25), bringing
the admission control surface to full audit parity.

#### Added

- **`AdmissionAuditLedger`** (`runtime/governance/admission_audit_ledger.py`):
  append-only SHA-256 hash-chained JSONL ledger for `AdmissionDecision`;
  `emit(decision)` fail-safe (never raises); `chain_verify_on_open` guard;
  inactive by default (no file written when `path=None`); parent directory
  auto-created; resumes sequence on reopen.
- **`AdmissionAuditReader`**: read-only analytics — `history()` with `limit`,
  `band_filter`, `admitted_only`; `band_frequency()`; `admission_rate()`;
  `verify_chain()`.
- **`AdmissionAuditChainError`**: raised on any hash-chain integrity violation;
  carries `sequence` and `detail` fields.
- **`GET /governance/admission-audit`**: bearer-auth-gated (`audit:read`),
  read-only; accepts `limit`, `band`, `admitted_only` query params; returns
  records, admission rate, and band frequency.
- **36 new tests**: `tests/governance/test_admission_audit_ledger.py` (36).

#### Invariants preserved

- `GovernanceGate` retains sole mutation-approval authority.
- `AdmissionAuditLedger` never imports or calls `GovernanceGate`.
- Append-only: no record is ever overwritten or deleted.
- Deterministic replay: same `AdmissionDecision` sequence → same chain hashes.
- Timestamp excluded from `record_hash` — chain is wall-clock independent.
- `emit()` failure isolation: I/O errors logged and swallowed; caller unaffected.

---

## [5.1.0] — 2026-03-10


### Phase 26 — Admission Rate Signal Integration (Complete)

Phase 26 closes the Phase 25 feedback loop: `AdmissionRateTracker` records
per-epoch admission outcomes and produces a rolling `admission_rate_score`
signal, now wired into `GovernanceHealthAggregator` as the sixth and final
governance signal. When sustained health pressure causes many mutations to be
deferred, the admission rate degrades the composite health score — a
self-reinforcing governance feedback loop with no authority delegation.

#### Added

- **`AdmissionRateTracker`** (`runtime/governance/admission_tracker.py`):
  `record_decision(epoch_id, admitted)` + `generate_report() → AdmissionRateReport`;
  configurable rolling window (default 10 epochs); fail-safe empty-history
  default of `1.0`; deterministic `report_digest` SHA-256; eviction of
  out-of-window epoch entries on every insert.
- **`AdmissionRateReport`** frozen dataclass: `admission_rate_score`,
  `admitted_count`, `total_count`, `epochs_in_window`, `max_epochs`,
  `report_digest`, `tracker_version`.
- **`admission_rate_score` signal** in `GovernanceHealthAggregator` (weight
  `0.10`); sourced from `AdmissionRateTracker.admission_rate_score()`; defaults
  to `1.0` when no tracker is wired; clamped `[0.0, 1.0]`; fail-safe on
  exception.
- **Signal weight rebalance**: five original signals rebalanced to accommodate
  the sixth; total weight sum invariant `== 1.0` preserved.
- **`admission_rate_report` field** in `HealthSnapshot`: additive, non-breaking;
  carries `admission_rate_score`, `admitted_count`, `total_count`,
  `epochs_in_window`, `report_digest`.
- **`GET /governance/admission-rate`**: bearer-auth-gated (`audit:read`),
  read-only; returns full `AdmissionRateReport` from a default tracker.
- **34 new tests**: `test_admission_tracker.py` (26), `test_admission_rate_endpoint.py` (8).

#### Invariants preserved

- `GovernanceGate` retains sole mutation-approval authority.
- `AdmissionRateTracker` never imports or calls `GovernanceGate`.
- `admission_rate_score` is advisory — it informs `h`, which is itself advisory.
- Determinism: identical decision sequence → identical score → identical digest.
- Weight sum invariant: `sum(SIGNAL_WEIGHTS.values()) == 1.0` (CI-enforced).

---

## [5.0.0] — 2026-03-10


### Phase 25 — Mutation Admission Control (Complete)

## [4.10.0] — 2026-03-09

### Phase 25 — Pressure Adjustment Audit Ledger (Complete)

Phase 25 persists every `PressureAdjustment` into a hash-chained audit ledger,
completing the governance advisory arc: emit → persist → verify → query.

#### Added

- **`PressureAuditLedger`** (`runtime/governance/pressure_audit_ledger.py`):
  append-only JSONL; SHA-256 hash chain with `GENESIS_PREV_HASH = "sha256:" + "0"*64`;
  `emit(adjustment)` isolates all failures; `chain_verify_on_open=True` default;
  `PressureAuditChainError(sequence, detail)` on any violation.
- **`PressureAuditReader`**: `history()` (newest-first, filter, limit/offset, ≤500);
  `tier_frequency()`; `tier_frequency_series(window)`; `verify_chain()`.
- **Deterministic replay**: `timestamp_iso` excluded from `record_hash` — same
  adjustment sequence → identical chain hashes (test-verified).
- **`GET /governance/review-pressure` extended**: emits to `PressureAuditLedger`
  when `ADAAD_PRESSURE_LEDGER_PATH` env set; adds `ledger_active` and `ledger_sequence`
  fields; emit failure never propagates; inactive by default.
- **`GET /governance/pressure-history`**: bearer-auth-gated, read-only; `pressure_tier`
  filter; `limit` 1–500; `422` on limit>500; `ledger_active: false` when no env/file.
- **50 new tests**: `test_pressure_audit_ledger.py` (32), `test_pressure_history_endpoint.py`
  (12), `test_review_pressure_ledger_wiring.py` (6).

#### Invariants preserved

- `GovernanceGate` and `HealthPressureAdaptor` unmodified.
- Ledger is append-only; no record is ever overwritten or deleted.
- `advisory_only: True` structural invariant unchanged.

---

## [4.9.0] — 2026-03-09


### Phase 24 — Health-Driven Review Pressure Adaptation (Complete)

Phase 24 acts on the unified governance health signal: when `h` degrades,
`HealthPressureAdaptor` surfaces an advisory recommendation to raise reviewer
counts proportionally. All output is advisory — GovernanceGate and human
sign-off retain all actual authority.

#### Added

- **`HealthPressureAdaptor`** (`runtime/governance/health_pressure_adaptor.py`):
  `compute(health_score) → PressureAdjustment`; three pressure bands (none/elevated/
  critical); `advisory_only: True` structural invariant; `adjustment_digest`
  deterministic SHA-256; `low` tier never adjusted; proposed `min_count` capped
  at `max_count`, floored at `CONSTITUTIONAL_FLOOR_MIN_REVIEWERS`.
- **`PressureAdjustment`** frozen dataclass: `health_score`, `health_band`,
  `pressure_tier`, `proposed_tier_config`, `baseline_tier_config`, `adjusted_tiers`,
  `advisory_only`, `adjustment_digest`, `adaptor_version`.
- **`GET /governance/review-pressure`**: bearer-auth-gated (`audit:read`), read-only;
  returns full `PressureAdjustment` for current governance health score.
- **`review_pressure` field** in `GET /governance/health` response: additive,
  non-breaking; carries `pressure_tier`, `health_band`, `adjusted_tiers`,
  `advisory_only`, `adjustment_digest`.
- **48 new tests**: `test_health_pressure_adaptor.py` (32),
  `test_review_pressure_endpoint.py` (10), `test_governance_health_pressure_field.py` (6).

#### Invariants preserved

- `GovernanceGate` retains sole mutation-approval authority.
- `advisory_only: True` is a structural invariant — no runtime path sets it `False`.
- `HealthPressureAdaptor` has no access to `GovernanceGate`.
- No new constitutional rules introduced.

---

## [4.8.0] — 2026-03-09

### Phase 23 — Routing Health Signal Integration (Complete)

Phase 23 wires `RoutingHealthReport.health_score` as the fifth governance signal,
unifying the routing observability surface (Phase 22) with the composite governance
health score (Phase 8).

#### Added

- **`routing_health_score` signal** in `GovernanceHealthAggregator`: weight `0.15`;
  sourced from `StrategyAnalyticsEngine.generate_report().health_score`; defaults
  to `1.0` when no engine is wired; clamped `[0.0, 1.0]`; fail-safe on exception.
- **Signal weight rebalance**: four original signals rebalanced; total weight sum
  remains exactly `1.0` (test-enforced).
- **`HealthSnapshot.routing_health_report`**: serialized `RoutingHealthReport` dict
  when engine active; `None` otherwise.
- **`GET /governance/routing-health`**: bearer-auth-gated (`audit:read`) read-only
  endpoint; returns full `RoutingHealthReport`; `available: false` degraded mode
  when no file sink active; `window_size` 10–10000.
- **`routing_health` field** in `GET /governance/health` response: additive, non-breaking;
  carries `available`, `status`, `health_score`, `dominant_strategy`, `report_digest`,
  `analytics_version`. Existing fields and `schema_version` unchanged.
- **45 new tests**: `test_routing_health_signal.py` (26), `test_routing_health_endpoint.py`
  (12), `test_governance_health_routing_field.py` (7).

#### Invariants preserved

- `GovernanceGate` retains sole mutation-approval authority.
- `StrategyAnalyticsEngine`, `TelemetryLedgerReader`, `FileTelemetrySink` unmodified.
- No new constitutional rules introduced.

---

## [4.7.0] — 2026-03-09

### Phase 22 — Strategy Analytics & Routing Health (Complete)

Phase 22 builds higher-order analytics over the Phase 21 telemetry ledger, adding
structured health classification for the intelligence routing surface.

#### Added

- **`StrategyAnalyticsEngine`** (`runtime/intelligence/strategy_analytics.py`): read-only
  analytics engine consuming `TelemetryLedgerReader`; rolling-window win rates, drift
  detection (`abs(window_win_rate - all_time_win_rate)`), staleness flags, dominant
  strategy detection, health score formula, and green/amber/red classification with 6
  named threshold constants.
- **`RoutingHealthReport`** (frozen dataclass): structured health report with deterministic
  `report_digest` (sha256 of canonical fields); all 6 `STRATEGY_TAXONOMY` members always
  present in `strategy_stats`, sorted by `strategy_id`.
- **`StrategyWindowStats`** (frozen dataclass): per-strategy rolling-window statistics.
- **`StrategyAnalyticsError`**: raised on invalid `window_size` (< 10 or > 10,000).
- **`schemas/routing_health_report.v1.json`**: JSON Schema enforcement for report structure.
- **`GET /telemetry/analytics`** (`server.py`): bearer-auth-gated (`audit:read`); `window_size`
  param (10–10000); full `RoutingHealthReport` as structured JSON; file or memory sink.
- **`GET /telemetry/strategy/{strategy_id}`** (`server.py`): per-strategy `StrategyWindowStats`;
  404 on unknown `strategy_id`.
- **47 new tests**: `test_strategy_analytics.py` (33), `test_analytics_endpoints.py` (14).

#### Invariants preserved

- `StrategyAnalyticsEngine` is read-only — never writes to the telemetry ledger.
- `GovernanceGate` retains sole mutation-approval authority; analytics are advisory only.
- No new constitutional rules introduced.
- All Phase 21 and Phase 22 telemetry surfaces are append-only or read-only.

---

## [4.6.0] — 2026-03-09

### Phase 21 — Telemetry Ledger & Governed Observability (Complete)

Phase 21 converts intelligence routing telemetry from ephemeral in-memory state to
a durable, sha256-chained, queryable audit ledger — completing the evidence infrastructure
for the intelligence surface.

#### Added

- **`FileTelemetrySink`** (`runtime/intelligence/file_telemetry_sink.py`): append-only
  JSONL sink with sha256 hash chaining; `verify_chain()` is O(n) memory and fail-closed
  on any hash, `prev_hash`, or sequence-gap mismatch; `GENESIS_PREV_HASH` matches
  `mutation_ledger.py` sentinel; emit failures are caught and never propagate to callers.
- **`TelemetryLedgerReader`** (`runtime/intelligence/file_telemetry_sink.py`): read-only
  query interface — `query()` with `strategy_id`, `outcome`, `limit`, `offset`;
  `win_rate_by_strategy()`; `strategy_summary()`; `verify_chain()`.
- **`schemas/telemetry_decision_record.v1.json`**: schema for chained telemetry records.
- **`AutonomyLoop.telemetry_ledger_path`** kwarg: `FileTelemetrySink` activates when
  path is configured; `InMemoryTelemetrySink` remains the unchanged default;
  `ADAAD_TELEMETRY_LEDGER_PATH` env var respected; explicit kwarg takes precedence.
- **`GET /telemetry/decisions`** endpoint (`server.py`): bearer-auth-gated (`audit:read`),
  read-only; `strategy_id` / `outcome` filters; `limit` (1–500) / `offset` pagination;
  `sink_type` reflects active sink; `_set_telemetry_sink_for_server()` for test injection.
- **61 new tests**: `test_file_telemetry_sink.py` (38), `test_autonomy_telemetry_sink.py`
  (16), `test_telemetry_endpoint.py` (7).

#### Invariants preserved

- `GovernanceGate` retains sole mutation-approval authority; telemetry is observability only.
- `InMemoryTelemetrySink` and all existing `AutonomyLoop` callers are unmodified.
- No new constitutional rules introduced.

---

## [4.5.0] — 2026-03-09

### Phase 20 — Public API Consolidation (Complete)

Phase 20 declares the Phase 16–19 intelligence and autonomy work as stable
public API by exporting all new symbols from their package `__init__` files,
adds import-contract tests, and removes the stale `strategy.py.bak` file.

**PR-20-PLAN** `docs/PHASE_20_UPGRADE_PLAN.md` — gap analysis, export table

**PR-20-01** `runtime/intelligence/__init__.py` — Phase 16/17/18 exports
- New exports: `STRATEGY_TAXONOMY`, `CritiqueSignalBuffer`,
  `RoutedDecisionTelemetry`, `InMemoryTelemetrySink`,
  `EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION`
- All added to `__all__`
- 10 contract tests (`tests/test_intelligence_public_api_phase20.py`)

**PR-20-02** `runtime/autonomy/__init__.py` — `AutonomyLoop` export + cleanup
- `AutonomyLoop` added to import and `__all__`
- `runtime/intelligence/strategy.py.bak` deleted
- 8 contract tests (`tests/test_autonomy_public_api_phase20.py`)

**Totals:** 18 new tests (Phase 20) · 2,714+ passing

---

## [4.4.0] — 2026-03-09

### Phase 19 — AutonomyLoop Intelligence Integration (Complete)

Phase 19 fixes three structural gaps that prevented the Phase 18 CritiqueSignal
feedback loop from functioning in production.

**PR-19-PLAN** `docs/PHASE_19_UPGRADE_PLAN.md` — gap analysis, design, PR sequence

**PR-19-01** `AutonomyLoopResult` intelligence fields + `lineage_health` wire
- `runtime/autonomy/loop.py`:
  * `AutonomyLoopResult` — three new optional fields (default `None`):
    `intelligence_strategy_id: str | None`, `intelligence_outcome: str | None`,
    `intelligence_composite: float | None`
  * `run_self_check_loop()` — new `lineage_health: float | None = None` kwarg
    (backward compatible; `None` → 1.0); passed into `StrategyInput` so
    `structural_refactor` (lineage < 0.50) and `conservative_hold` (lineage >= 0.80)
    triggers are no longer permanently blind
  * `AutonomyLoopResult` now carries strategy_id, outcome, and composite score
    from the `RoutedIntelligenceDecision`
- 12 new tests (`tests/test_autonomy_loop_intelligence_phase19.py`)

**PR-19-02** `AutonomyLoop` class — persistent `IntelligenceRouter` across `run()` calls
- `runtime/autonomy/loop.py`:
  * `class AutonomyLoop` — stateful wrapper holding one `IntelligenceRouter`
    instance across all `run()` calls
  * Resolves the critical gap: `IntelligenceRouter()` was previously instantiated
    fresh per `run_self_check_loop()` call — `CritiqueSignalBuffer` never accumulated
  * `reset_epoch()` — explicit epoch-boundary buffer clear
  * `router` property for inspection and testing
  * Accepts optional injected `router` for testing
  * `run_self_check_loop()` unchanged — backward compatible for existing callers
- 10 new tests (`tests/test_autonomy_loop_persistent_router_phase19.py`)

**Totals:** 22 new tests (Phase 19) · 2,696+ passing

---

## [4.3.0] — 2026-03-09

### Phase 18 — CritiqueSignal Feedback Loop (Complete)

Phase 18 closes the learn-from-critique loop: per-strategy critique breach rates
now feed back into StrategyModule payoff scoring, penalising strategies that
consistently produce floor-breaching proposals.

**PR-18-PLAN** `docs/PHASE_18_UPGRADE_PLAN.md` — gap analysis, design, PR sequence

**PR-18-01** `CritiqueSignalBuffer` + `StrategyModule` breach penalty integration
- `runtime/intelligence/critique_signal.py` (new):
  * `CritiqueSignalBuffer` — epoch-scoped append-only accumulator of per-strategy
    critique outcomes (approved, risk_flags). `breach_rate()`, `breach_penalty()`,
    `snapshot()`, `reset_epoch()`. Deterministic.
  * `_BREACH_PENALTY_WEIGHT = 0.20` — max payoff reduction per strategy; clamped
    so payoff ≥ 0.0.
- `runtime/intelligence/strategy.py`:
  * `StrategyModule.select(context, *, signal_buffer=None)` — optional kwarg;
    absent → identical Phase 17 behaviour (backward compatible).
  * Penalty applied after trigger qualification, before sort: payoff reduced by
    `breach_rate × 0.20` per candidate; never negative.
  * `parameters["breach_penalties"]` reports applied penalties per candidate.
- 15 new tests (`tests/test_critique_signal_phase18.py`)

**PR-18-02** `IntelligenceRouter` buffer wire across `route()` calls
- `runtime/intelligence/router.py`:
  * Owns `CritiqueSignalBuffer` instance (injectable for testing).
  * `route()` passes `signal_buffer` to `StrategyModule.select()` then calls
    `buffer.record(strategy_id, approved, risk_flags)` after each critique.
  * `reset_epoch()` — explicit epoch boundary reset; not automatic.
  * `signal_buffer` property for inspection and testing.
- 10 new tests (`tests/test_router_signal_wire_phase18.py`)

**Totals:** 25 new tests (Phase 18) · 2,674+ passing

---

## [4.2.0] — 2026-03-09

### Phase 17 — IntelligenceRouter Closure (Complete)

Phase 17 closes two wiring gaps left open after Phase 16's strategy taxonomy expansion.

**PR-17-PLAN** Phase 17 upgrade plan
- `docs/PHASE_17_UPGRADE_PLAN.md`: Gap analysis, PR sequence, risk register

**PR-17-01** Router → strategy_id wire into CritiqueModule.review()
- `runtime/intelligence/router.py`:
  * `self._critique.review(proposal, strategy_id=strategy.strategy_id)` — Phase 16
    per-strategy dimension floor overrides are now active in every route() call
  * Previously `review(proposal)` was called without strategy_id — floors defaulted
    to baseline regardless of which strategy was selected (dead code gap)
- `tests/test_intelligence_router.py`: `IncompleteDimensionCritiqueModule.review()`
  fixture updated to accept `strategy_id` kwarg
- 10 new tests (`tests/test_router_strategy_wire_phase17.py`)

**PR-17-02** RoutedDecisionTelemetry — `routed_intelligence_decision.v1`
- `runtime/intelligence/routed_decision_telemetry.py`:
  * `EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION = "routed_intelligence_decision.v1"`
  * `build_routed_decision_payload()` — deterministic payload: cycle_id, strategy_id,
    outcome, composite_score, dimension_verdicts, review_digest, confidence, risk_flags,
    payload_digest (SHA-256 of key fields)
  * `InMemoryTelemetrySink` — append-only in-memory sink for testing and single-process use
  * `RoutedDecisionTelemetry` — accepts any callable sink; defaults to InMemoryTelemetrySink;
    emission failure caught and logged, never propagated to router
- `runtime/intelligence/router.py`: `RoutedDecisionTelemetry` injected; `route()` calls
  `self._telemetry.emit_routed_decision(decision)` after every successful route
- `runtime/governance/event_taxonomy.py`:
  * `EVENT_TYPE_ROUTED_INTELLIGENCE_DECISION` constant registered
  * Added to `CANONICAL_EVENT_TYPES` and `__all__`
- 12 new tests (`tests/test_routed_decision_telemetry_phase17.py`)

**Totals:** 22 new tests (Phase 17) · 2,649+ passing

---

## [4.1.0] — 2026-03-09

### Phase 16 — Mutation Strategy Taxonomy Expansion (Complete)

Phase 16 expands the `StrategyModule` from a binary 2-strategy decision (introduced in
Phase 14) to a **six-strategy context-driven taxonomy**, routes each strategy through a
dedicated `ProposalAdapter` LLM system prompt, and applies per-strategy dimension floor
overrides in `CritiqueModule`. Floors may only be raised — never lowered below baseline.

**PR-16-PLAN** Phase 16 upgrade plan
- `docs/PHASE_16_UPGRADE_PLAN.md`: Strategy taxonomy 2→6 design, PR sequence, risk register

**PR-16-01** StrategyModule: 2 → 6 strategies + `STRATEGY_TAXONOMY` registry
- `runtime/intelligence/strategy.py`:
  * `STRATEGY_TAXONOMY: frozenset[str]` — canonical 6-strategy registry
  * `_STRATEGY_PRIORITY` — priority ordering: safety_hardening > structural_refactor >
    test_coverage_expansion > performance_optimization > adaptive_self_mutate > conservative_hold
  * `StrategyDecision.__post_init__` validates strategy_id against STRATEGY_TAXONOMY; raises
    ValueError on unknown IDs — injection blocked
  * `StrategyModule.select()` expanded: 6 trigger evaluations with payoff-primary / priority-
    secondary sort; confidence floor guaranteed ≥ 0.55; fallback only when no trigger qualifies
  * `parameters["strategy_taxonomy_version"] = "16.0"` on every StrategyDecision
- 18 new tests (`tests/test_strategy_taxonomy_phase16.py`)
- Updated 2 fixtures in `tests/test_intelligence_strategy.py` (debt/lineage params adjusted
  to isolate legacy strategy triggers from Phase 16 higher-priority strategies)

**PR-16-02** ProposalAdapter: strategy-aware prompt routing
- `runtime/intelligence/proposal_adapter.py`:
  * `_STRATEGY_SYSTEM_PROMPTS` — 6 dedicated system prompts, one per taxonomy strategy
  * `_system_prompt_for_strategy()` — validates strategy_id against STRATEGY_TAXONOMY before
    lookup; raises ValueError on unknown IDs — LLM prompt injection blocked
  * `build_from_strategy()` now routes system prompt via `_system_prompt_for_strategy()`
  * Evidence field `strategy_prompt_version: "16.0"` on every ProposalAdapter build
- 12 new tests (`tests/test_proposal_adapter_phase16.py`)

**PR-16-03** CritiqueModule: per-strategy dimension floor overrides
- `runtime/intelligence/critique.py`:
  * `STRATEGY_FLOOR_OVERRIDES` — per-strategy dict of dimension floor raises (additive only)
  * `_effective_floors(strategy_id)` — returns max(baseline, override) per dimension;
    unknown/None strategy_id returns baseline unchanged
  * `CritiqueModule.review()` accepts optional `strategy_id` kwarg; applies effective floors
  * `review_digest` now includes `strategy_id` for determinism tracing
  * `metadata["critique_taxonomy_version"] = "16.0"` on every CritiqueResult
  * Backward-compatible: `review(proposal)` with no strategy_id uses baseline floors
- 10 new tests (`tests/test_critique_phase16.py`)

**Totals:** 40 new tests (Phase 16) · 2,627+ passing

---

## [4.0.0] — 2026-03-09

### Phase 15 — Governance Debt + Lineage Health Wiring (Complete)
### v4.0.0 Milestone: Autonomous Governance Intelligence Loop Complete

Phase 15 closes the last two hardcoded-constant gaps in `ProposalRequest.context`
introduced in Phase 14. With both `governance_debt_score` and `lineage_health`
live-wired, the full governance intelligence loop is closed end-to-end.

**PR-15-PLAN** Phase 15 upgrade plan
- `docs/PHASE_15_UPGRADE_PLAN.md`: GovernanceDebt + LineageHealth wiring plan,
  v4.0.0 milestone definition

**PR-15-01** GovernanceDebtLedger → EvolutionLoop wiring
- `runtime/evolution/evolution_loop.py`:
  * Import + optional injection of `GovernanceDebtLedger`
  * `_last_debt_score: float = 0.0` persisted across epochs
  * Phase 5f: exception-isolated debt accumulation after Phase 5e;
    warning_verdicts from rejected all_scores; compound_debt_score stored
  * Phase 1e context: `governance_debt_score = float(self._last_debt_score)`
- 12 new tests (`tests/evolution/test_governance_debt_ledger_wiring.py`)

**PR-15-02** lineage_health from mean_lineage_proximity
- `runtime/evolution/evolution_loop.py`:
  * `_last_lineage_proximity: float = 1.0` persisted across epochs
  * After Phase 5 proximity computation: clamped [0.0, 1.0], stored when
    accepted_count > 0; previous value preserved on sparse epochs
  * Phase 1e context: `lineage_health = float(self._last_lineage_proximity)`
  * Both Phase 14 TODOs now resolved; no hardcoded constants remain
- 11 new tests (`tests/evolution/test_lineage_health_wiring.py`)

**v4.0.0 governance intelligence loop — fully closed:**

```
EpochResult → GovernanceDebtLedger → compound_debt_score
EpochResult → mean_lineage_proximity → lineage_health
MarketFitnessIntegrator → consecutive_synthetic → market signal quality
AgentBanditSelector → recommendation → bandit strategy
ExploreExploitController → mode + explore_ratio → diversity signal
WeightAdaptor → prediction_accuracy → mutation_score
All signals → ProposalRequest.context → StrategyModule.select()
           → StrategyDecision → ProposalAdapter LLM prompt
           → Proposal → MutationCandidate → governed evolution pipeline
```

**Totals:** 23 new tests (Phase 15) · 2,587+ passing

## [3.9.0] — 2026-03-09

### Phase 14 — ProposalEngine Activation (Complete)

**PR-14-PLAN** Phase 14 upgrade plan document
- `docs/PHASE_14_UPGRADE_PLAN.md`: full build plan for ProposalEngine activation,
  the single highest-leverage commercial gap in ADAAD
- `governance/rule_applicability.yaml`: bandit_arm_integrity_invariant and
  market_signal_integrity_invariant entries added (fixes policy drift CI gate)

**PR-14-01** ProposalEngine → EvolutionLoop Phase 1e wiring
- `runtime/evolution/evolution_loop.py`:
  * `_proposal_to_candidate()`: new bridge function — Proposal → MutationCandidate.
    Maps proposal_id→mutation_id, estimated_impact→expected_gain, projected_impact
    fields, agent_origin='proposal_engine', operator_category='llm_strategy',
    operator_version='14.0.0'. Returns None for noop proposals (empty real_diff).
  * `EvolutionLoop.__init__()`: `proposal_engine: Optional[ProposalEngine] = None`
  * Phase 1e block: exception-isolated; builds ProposalRequest; calls generate();
    bridges to MutationCandidate; appends to all_proposals if non-None
- 19 new tests (`tests/evolution/test_proposal_engine_evolution_wiring.py`)

**PR-14-02** Live signal population into ProposalRequest.context
- Phase 1e context builder: market signals (consecutive_synthetic), bandit
  recommendation (agent, confidence, exploration_bonus), explore_ratio,
  evolution_mode, epoch_id/count, last_health_score, mutation_score
  (WeightAdaptor.prediction_accuracy), governance_debt_score / lineage_health
  (Phase 15 TODOs)
- 14 new tests (`tests/evolution/test_proposal_engine_context_signals.py`)

**Totals:** 33 new tests (Phase 14) · 2,564+ passing

## [3.8.0] — 2026-03-09

### Phase 13 — Market Signal Integrity Invariant (Track 11-B, Complete)

**PR-13-B-01** consecutive_synthetic_epochs counter on IntegrationResult
- `IntegrationResult`: `consecutive_synthetic_epochs: int = 0` field — running count of
  consecutive synthetic integrate() calls, reset to 0 on any live reading
- `MarketFitnessIntegrator`: `_consecutive_synthetic` counter; increments on synthetic,
  resets on live; stamped onto every `IntegrationResult`
- `consecutive_synthetic_epochs` property + `reset_synthetic_counter()` operator hook
- Journal event `market_fitness_integrated.v1` now includes counter in payload
- `EpochResult`: `consecutive_synthetic_market_epochs: int = 0` field populated from Phase 2m
- 13 new tests (`tests/market/test_consecutive_synthetic_epochs.py`)

**PR-13-B-02** Constitution v0.7.0 — `market_signal_integrity_invariant` BLOCKING rule
- New rule `market_signal_integrity_invariant` added to `runtime/governance/constitution.yaml`
  (severity: BLOCKING; SANDBOX tier_override: warning; max_synthetic_epochs: 5;
  env-override: `ADAAD_MARKET_MAX_SYNTHETIC_EPOCHS`)
- `runtime/constitution.py`: `_validate_market_signal_integrity()` validator reads
  `consecutive_synthetic_market_epochs` from checkpoint chain tip; blocks promotion when
  cap exceeded; advisory pass when chain absent / unreadable
- `CONSTITUTION_VERSION`: `0.6.0` → `0.7.0`
- `VALIDATOR_REGISTRY`: `market_signal_integrity_invariant` entry added
- 22 new tests (`tests/governance/test_constitution_market_signal_integrity.py`)

**Totals:** 35 new tests · 2,545+ passing

## [3.7.0] — 2026-03-09

### Phase 12 — EpochResult Market Fields + Cross-Epoch Digest Verification (Complete)

**PR-12-D-01** EpochResult live market signal fields (Track 11-D)
- `EpochResult` gains three observable market fields: `live_market_score` (float, default 0.0),
  `market_confidence` (float, default 0.0), `market_is_synthetic` (bool, default True)
- `EvolutionLoop.__init__()` accepts `market_integrator: Optional[MarketFitnessIntegrator]`
- Phase 2m in `run_epoch()` calls `integrate(epoch_id=...)` and populates the three fields;
  exception-isolated — epoch completes with synthetic defaults on any integrator failure
- 14 new tests (`tests/evolution/test_epoch_result_market_fields.py`)

**PR-12-C-01** Cross-epoch ledger digest verification (Track 11-C)
- `SoulboundLedger.current_chain_hash()` — semantically explicit alias for `last_chain_hash()`;
  exposes current Merkle chain tip to replay verification callers
- `ContextReplayInterface.verify_replay_digest(digest, epoch_id) -> bool` — compares
  `context_digest` from a previous `ReplayInjection` against current ledger chain tip;
  emits `context_digest_mismatch.v1` journal event on mismatch, empty digest, or read error;
  fully exception-isolated, never raises
- `EvolutionLoop` Phase 0c: `verify_replay_digest()` called before applying `ReplayInjection`;
  injection skipped silently when verification fails; mismatch event emitted
- 17 new tests (`tests/memory/test_context_replay_digest_verify.py`)

**Totals:** 31 new tests · 2,497+ passing


## [3.6.0] — 2026-03-09

### Phase 11-A — Bandit-Informed Agent Selection (Complete)

**PR-11-A-01** AgentBanditSelector — UCB1 + Thompson Sampling
- `runtime/autonomy/agent_bandit_selector.py` — reward-profile-informed bandit
  - `ArmRewardState`: float-reward arm (pull_count, reward_mass, loss_mass, consecutive_recommendations)
  - UCB1: mean_reward + C × sqrt(ln(N)/n_i); Thompson: Beta(reward_mass+1, loss_mass+1)
  - `BanditAgentRecommendation` (frozen dataclass): agent, confidence, strategy, exploration_bonus, is_active
  - `AgentBanditSelector.recommend()`: epoch_id-seeded determinism for Thompson
  - `AgentBanditSelector.update()`: float reward clamped to [0,1]; consecutive tracking
  - `AgentBanditSelector.from_registry()`: bootstrap from LearningProfileRegistry decisions
  - State persistence: `data/agent_bandit_state.json`; corrupt state → graceful fresh fallback
- **22 tests** (T11-A-01..12 + sub-tests)

**PR-11-A-02** FitnessLandscape bandit override + EvolutionLoop Phase 0d/5e
- `runtime/autonomy/fitness_landscape.py`: `recommended_agent(bandit_rec=None)` override tier
  - AgentBanditSelector wins when `is_active=True` and `confidence >= 0.60`; falls through otherwise
- `runtime/evolution/evolution_loop.py`:
  - Phase 0d: `bandit_selector.recommend()` called; result passed to `landscape.recommended_agent()`
  - Phase 5e: `bandit_selector.update(agent, reward)` after Phase 5d; exception-isolated
  - `EvolutionLoop.__init__` accepts `bandit_selector: Optional[AgentBanditSelector] = None`
- **9 tests** (T11-B-01..05 + sub-tests)

**PR-11-A-03** Constitution v0.6.0 + v3.6.0 release
- `runtime/governance/constitution.yaml` → v0.6.0: `bandit_arm_integrity_invariant` BLOCKING rule
  - Invariants: `arm_stats_non_negative`, `consecutive_epoch_cap_respected`, `agent_diversity_maintained`
  - `MAX_CONSECUTIVE_BANDIT_EPOCHS=10`; configurable via `ADAAD_BANDIT_MAX_CONSECUTIVE_EPOCHS`
  - SANDBOX tier: warning; PRODUCTION/STABLE: blocking
- `runtime/constitution.py` → CONSTITUTION_VERSION 0.6.0:
  - `_validate_bandit_arm_integrity()` validator registered
  - Version map entry `_validate_bandit_arm_integrity: "1.0.0"`
- **7 tests** (T11-C-01..03 + sub-tests)

**Deferred from Phase 9 (now complete)**
- `ContextReplayInterface` → `EvolutionLoop` Phase 0c wiring (PR-9-03)
- `ADAAD_SOULBOUND_KEY` docs: `ENVIRONMENT_VARIABLES.md`, `QUICKSTART.md`, `onboard.py`

**Test suite:** 228/228

---

## [3.5.0] -- 2026-03-09

### Phase 10 -- Reward Learning Pipeline (Complete)

**PR-10-01** RewardSignalBridge + EvolutionLoop Phase 5d wiring
- `runtime/memory/reward_signal_bridge.py` -- bridges MutationScore -> reward_learning pipeline
- `runtime/memory/reward_signal_bridge.py` -- persists fitness_signal to SoulboundLedger
- EvolutionLoop Phase 5d: ingest() after Phase 5c, isolated exception guard
- `OBSERVATION_RING_BUFFER_SIZE = 20` ring buffer for PolicyPromotionController

**PR-10-02** PolicyPromotionController + MarketFitnessIntegrator
- `runtime/memory/policy_promotion_controller.py` -- guarded weight promotion gate
  - Rolling baseline EMA (BASELINE_WINDOW_SIZE=5) from recent reward signals
  - GuardedPromotionPolicy regression thresholds; rollback to last authorized profile
  - Cold-start always promotes (< threshold epochs)
- EvolutionLoop Phase 4b: promotion gate between Phase 4 and Phase 5
- `runtime/market/market_fitness_integrator.py` -- added integrate() method
  - IntegrationResult dataclass: live_market_score, confidence, is_synthetic, lineage_digest
  - FeedRegistry.composite_reading() path; synthetic fallback when registry/reading absent
  - score clamped to [0.0, 1.0]; journal event market_fitness_integrated.v1

**Fixes**
- `runtime/autonomy/reward_learning.py` -- OBSERVATION_RING_BUFFER_SIZE exported in __all__

**Test suite:** 680/680

## [3.4.0] — 2026-03-09

### Phase 9 — Soulbound Context (Complete)

**PR-9-01** SoulboundKey + SoulboundLedger + ContextFilterChain + Schema
- `runtime/memory/soulbound_key.py` — HMAC-ENV keying (ADAAD_SOULBOUND_KEY), fail-closed
- `runtime/memory/soulbound_ledger.py` — tamper-evident Merkle-chain context history
- `runtime/memory/context_filter_chain.py` — 4 constitutional pre-screen filters
- `schemas/soulbound_context_event.v1.json` — JSON Schema 2020-12 for 7 event types

**PR-9-02** CraftPatternExtractor + EvolutionLoop Phase 5c wiring
- `runtime/memory/craft_pattern_extractor.py` — per-agent reasoning pattern extraction
- EvolutionLoop Phase 5c: CraftPatternExtractor wired after E/E commit
- Signal quality flag (CF-3 mitigation): low_velocity epochs flagged

**PR-9-03** ContextReplayInterface + Constitution v0.5.0
- `runtime/memory/context_replay_interface.py` — ledger-sourced context digest injection
- Constitution 0.4.0 → 0.5.0: `soulbound_privacy_invariant` BLOCKING rule
- Explore ratio adjustment from dominant craft pattern (experimental +10%, structural -10%)
- Low-velocity entry exclusion (CF-3 guard in replay window)

**Critical findings resolved** (CF-2, CF-3, CF-4)
- CF-2: ExploreExploitController explore lock fixed (prior_epoch_score → _last_epoch_health_score)
- CF-3: PenaltyAdaptor floor fixed (simulate=True baseline; signal_quality_flag in patterns)
- CF-4: MutationEngine stats starvation fixed (cursor reset on missing metrics file)

**Test suite:** 574/574 (governance + memory + CF fixes)

# Changelog

## [3.4.0-dev] — 2026-03-09 · Phase 9 Soulbound Context (in progress)

### PR-9-01 — SoulboundLedger + ContextFilterChain + SoulboundKey + Event Registration
- **New:** `runtime/memory/soulbound_ledger.py` — tamper-evident, HMAC-signed, append-only context ledger
  - Merkle-chain structure: `chain_hash = SHA256(prev_chain_hash + context_digest)` per entry
  - `VALID_CONTEXT_TYPES`: mutation_proposal, fitness_signal, governance_advisory, craft_pattern, replay_injection
  - `append()` → `AppendResult`; `verify_chain()` → `(bool, List[str])`; `rotate_key()`
  - Fail-closed: missing `ADAAD_SOULBOUND_KEY` raises `SoulboundKeyError`, emits `soulbound_key_absent.v1`
- **Existing:** `runtime/memory/context_filter_chain.py` — 4 built-in constitutional filters
  - epoch_id_required · payload_size_limit (64 KB) · no_private_key_leak · context_type_allowlist
  - First rejection halts chain; custom filters registerable via `register(fn)`
- **Existing:** `runtime/memory/soulbound_key.py` — HMAC-ENV keying (ADAAD_SOULBOUND_KEY, ≥32 bytes)
- **Updated:** `runtime/governance/event_taxonomy.py` — 7 Phase 9 event types registered:
  - `context_ledger_entry_accepted.v1`, `context_ledger_entry_rejected.v1`
  - `context_ledger_tamper_detected.v1`, `soulbound_key_rotation.v1`
  - `craft_pattern_extracted.v1`, `context_replay_injected.v1`, `soulbound_key_absent.v1`
- **Tests:** `tests/memory/test_soulbound_pr901.py` — consolidated canonical suite for T9-01-01..25 (including legacy `test_pr9_01.py` assertions), all passing
  - Legacy paths retained as compatibility stubs to reduce long-lived merge conflicts during branch transitions
  - SoulboundKey (5), SoulboundLedger (12), ContextFilterChain (8)

### Critical Findings Resolved (CF-2, CF-3, CF-4)
- **CF-2:** ExploreExploitController 30-epoch explore lock — `_last_epoch_health_score` tracking added
- **CF-3:** PenaltyAdaptor floor-stuck weights — `simulate=True` baseline enforced in production
- **CF-4:** MutationEngine stats empty after file loss — cursor reset on missing metrics file
- **Tests:** `tests/test_cf_fixes.py` — 15 regression tests (T-CF2..CF4), all passing

## [3.3.0] — 2026-03-08 · Phase 8 Governance Health Dashboard

### Phase 8 — Governance Health Dashboard & Telemetry Unification (SHIPPED)

#### PR-8-01 — GovernanceHealthAggregator + Evidence Binding
- **New:** `runtime/governance/health_aggregator.py` — deterministic composite health score h ∈ [0.0, 1.0]
- Signal weights: avg_reviewer_reputation (0.30), amendment_gate_pass_rate (0.25), federation_divergence_clean (0.25), epoch_health_score (0.20)
- h < 0.60 emits `governance_health_degraded.v1` journal event and Aponi alert
- `governance_health_snapshot.v1` ledger event on every computation — replay-safe, epoch-scoped
- Single-node fallback: absent FederatedEvidenceMatrix → federation_divergence_clean = 1.0
- Authority invariant: GovernanceGate retains sole mutation approval authority; health score advisory only
- New schema: `schemas/governance_health_snapshot.v1.json`
- **Tests: 25 new tests passing (T8-01-01..25)**

#### PR-8-02 — Governance Health Service + GET /governance/health Endpoint
- **New:** `runtime/governance/health_service.py` — standalone service facade
- **New endpoint:** `GET /governance/health` — health_score, status (green/amber/red), signal_breakdown, weight_snapshot_digest; auth-gated
- Status bands: green (h ≥ 0.80), amber (0.60–0.80), red (h < 0.60); constitutional_floor: enforced
- **Tests: 15 new tests passing (T8-02-01..15)**

#### PR-8-03 — Constitution v0.4.0: governance_health_floor Rule
- **CONSTITUTION_VERSION: 0.3.0 → 0.4.0**
- New rule: `governance_health_floor` — advisory, tier 0, enabled; degraded_threshold: 0.60
- Promotable to blocking via ADAAD_SEVERITY_ESCALATIONS
- New validator `_validate_governance_health_floor` in VALIDATOR_REGISTRY
- **Tests: 10 new tests passing (T8-03-01..10)**

### CF-1 Fix — Agent State Realigned
- `.adaad_agent_state.json`: last_completed_pr: PR-PHASE7-05, next_pr: PR-8-04 (Phase 8 complete), Phase 7 checkpoints recorded

### Phase 9 Soulbound Context Whitepaper
- Whitepaper v2.0 added to docs — fully aligned with ADAAD runtime architecture



## [3.2.0] — 2026-03-08 · Phase 7 — Reviewer Reputation & Adaptive Governance Calibration

All five Phase 7 milestones ship in `v3.2.0`. The system now closes the feedback loop
between human reviewer decisions and constitutional calibration — empirical reputation
replaces static reviewer-count heuristics while preserving the inviolable constitutional
floor that human review is always required.

### PR-7-01 — Reviewer Reputation Ledger

`runtime/governance/reviewer_reputation_ledger.py` (602 lines)

Append-only, SHA-256 hash-chained ledger of all reviewer decisions:
`DECISION_APPROVE`, `DECISION_REJECT`, `DECISION_TIMEOUT`, `DECISION_OVERRIDE`.

- **Write-once invariant:** entries are immutable once appended; no retroactive modification.
- **Privacy invariant:** `reviewer_id` stored as HMAC-derived opaque token over signing-key
  fingerprint — no plaintext PII in the ledger.
- **In-memory default:** replay-harness-compatible by default; persistence opt-in via
  `ledger_path` + `flush()` / `load()`.
- **Hash-chain:** every entry carries `prev_entry_hash` + `entry_hash` for offline
  chain-integrity verification.
- **Deterministic / replay-safe:** all state derived from the event stream; no wall-clock
  or random calls inside core logic.

Tests: `tests/governance/test_reviewer_reputation_ledger.py` — **45 tests** covering
chain integrity, append invariants, HMAC privacy, flush/load round-trips, and
decision taxonomy validation.

### PR-7-02 — Reputation Scoring Engine

`runtime/governance/reviewer_reputation.py` (263 lines)

Deterministic, epoch-scoped composite reputation score `r ∈ [0.0, 1.0]` derived from
ledger history across four dimensions:

| Dimension | Default Weight | Description |
|---|---|---|
| `latency` | 0.20 | Response timeliness relative to SLA windows |
| `override_rate` | 0.30 | Frequency of decisions overridden by higher authority |
| `long_term_mutation_impact` | 0.30 | Post-merge quality and stability of approved mutations |
| `governance_alignment` | 0.20 | Consistency with constitutional and policy outcomes |

**Epoch weight snapshot invariant:** weight vector is snapshotted and journaled per epoch
before any scorer execution. Replay consumes epoch-scoped weight snapshots, never
current-runtime weights. Mid-epoch weight changes are disallowed.

**Scoring version binding invariant:** `scoring_algorithm_version = "1.0"` is recorded in
every epoch context and `reviewer_reputation_update` event. Any scoring algorithm change
requires a version bump; prior epochs are never retroactively reinterpreted.

Exports: `compute_reviewer_reputation()`, `compute_epoch_reputation_batch()`,
`snapshot_digest()`, `validate_epoch_weights()`.

Tests: `tests/governance/test_reviewer_reputation.py` — **23 tests** covering determinism,
weight validation, version binding, batch computation, and edge-case score bounds.
`tests/governance/test_pr_lifecycle_reviewer_outcome.py` — **14 tests** covering
lifecycle event consumption and outcome integration.

### PR-7-03 — Tier Calibration Engine + Constitutional Floor

`runtime/governance/review_pressure.py` (188 lines)

Translates aggregate reviewer reputation into adjusted reviewer-count recommendations
per governance tier, subject to hardcoded constitutional floor enforcement.

| Tier | Base | Min | Max |
|---|---|---|---|
| `low` | 1 | 1 | 2 |
| `standard` | 2 | 1 | 3 |
| `critical` | 3 | 2 | 4 |
| `governance` | 3 | 3 | 5 |

**Calibration thresholds:** reputation ≥ 0.80 → count reduced by 1; reputation ≤ 0.40 →
count increased by 1; both bounded by per-tier min/max.

**Constitutional floor invariant:** `CONSTITUTIONAL_FLOOR_MIN_REVIEWERS = 1` is architecturally
enforced. No tier configuration may set `min_count < 1`; `validate_tier_config()` raises
`ValueError` on boot if any tier violates the floor. Reputation can never reduce the
required reviewer count below this boundary.

Exports: `compute_tier_reviewer_count()`, `compute_panel_calibration()`, `validate_tier_config()`.

### PR-7-04 — Constitution v0.3.0: `reviewer_calibration` Advisory Rule

`docs/CONSTITUTION.md` bumped to **v0.3.0** (already in effect). `runtime/governance/constitution.yaml`
carries the new rule:

```yaml
- name: reviewer_calibration
  enabled: true
  severity: advisory
  validator: reviewer_calibration
  reason: "Expose reviewer calibration context as governance telemetry"
```

Advisory enforcement: captures reviewer reputation posture for telemetry and audit evidence;
does not block mutations. Environment variable `ADAAD_SEVERITY_ESCALATIONS` allows operators
to escalate to `blocking` without a code change.

**Invariant:** Tier 0 surfaces always require human review. The `reviewer_calibration` rule
cannot demote Tier 0 gates — calibration adjusts reviewer count within tier bounds only.

### PR-7-05 — Aponi Reviewer Calibration Endpoint

`GET /governance/reviewer-calibration` — read-only Aponi dashboard endpoint backed by
`runtime/api/runtime_services.reviewer_calibration_service()`.

**Response schema (v1.0):**
```json
{
  "schema_version": "1.0",
  "authn": { "scope": "audit:read" },
  "data": {
    "cohort_summary": { "high": 2, "standard": 4, "low": 0 },
    "avg_reputation": 0.82,
    "tier_pressure": "extended | nominal | elevated",
    "constitutional_floor": "enforced",
    "epoch_id": "<requested_epoch>",
    "constitution_version": "0.3.0",
    "scoring_algorithm_version": "1.0"
  }
}
```

Requires `epoch_id` query parameter; returns 422 if absent. Auth-gated to `audit:read`
scope via `_require_audit_read_scope()`. Read-only — the endpoint surfaces telemetry only;
no reputation scores are modified by this call.

### Authority invariants upheld throughout Phase 7

- `ReviewerReputationLedger` records outcomes — it never approves or blocks mutations.
- `ReputationScoringEngine` produces scores — it never adjusts reviewer authority or voting rights.
- `TierCalibrationEngine` adjusts reviewer count only — constitutional floor is architecturally
  inviolable; no auto-approval path exists.
- `GovernanceGate` remains the sole mutation approval authority.
- `CONSTITUTIONAL_FLOOR_MIN_REVIEWERS = 1` cannot be reduced by any reputation signal.

---

## [3.1.1] — 2026-03-07 · chore/phase6-closeout-docs-v311 · Phase 6.1 GA + Roadmap + Doc Sync

### Phase 6.1 GA Closeout

- Phase 6.1 status promoted from 🟡 active → ✅ shipped in `ROADMAP.md`
- All Phase 6 M6-01..M6-05 milestones confirmed ✅ shipped in `README.md`
- `VERSION` bumped `3.1.0` → `3.1.1`
- `docs/releases/3.1.1.md` created with full milestone evidence and governance invariants
- README version badge, phase badge, nav link, active-phase section, phase history table,
  and version infobox all updated to reflect `v3.1.1` / Phase 6.1 state

### Phase 7 Roadmap Published

`ROADMAP.md` now includes Phase 7 — Reviewer Reputation & Adaptive Governance
Calibration (`v3.2.0` target):
- M7-01 Reviewer Reputation Ledger
- M7-02 Reputation Scoring Engine
- M7-03 Tier Calibration Engine
- M7-04 Constitution v0.3.0 (`reviewer_calibration` advisory rule)
- M7-05 Aponi Reviewer Calibration Endpoint
- Planned PR sequence: PR-7-01 → PR-7-05

---

## [3.1.1] — 2026-03-07 · feat/phase6-1-simplification-enforcement · Phase 6.1 — Simplification Contract Enforcement

### Phase 6.1 · Simplification Contract Enforcement (Legacy Reduction + Budget Lock)

**feat/phase6-1-simplification-enforcement** enforces the Phase 6 simplification
contract that was previously defined but not yet binding. The `simplification-contract-gate`
CI job now hard-fails on any regression above the 70% reduction target.

**Legacy branch reduction — baseline 23 → enforced ≤ 6**

17 `\blegacy\b` occurrences replaced with semantically equivalent `compat` /
`deprecated` / `backward-compat` across 13 source files. Six occurrences are
intentionally retained where the term is load-bearing (protocol string literals,
API facade modules, schema migration docstrings). `enforced_max_branches` locked
from `23` → `6` in `governance/simplification_targets.json`. Any future commit
that re-introduces a legacy branch above the cap fails the CI gate immediately.

Files with replacements:
- `security/cryovant.py` (4 docstring / comment refs → `deprecated` / `compat`)
- `app/mutation_executor.py` (3 refs → `compat` / `deprecated`)
- `runtime/evolution/epoch.py` (2 comment refs → `deprecated`)
- `app/main.py`, `app/beast_mode_loop.py`, `app/cli_args.py` (1 ref each)
- `app/agents/test_subject/__init__.py`, `runtime/capabilities.py` (1 ref each)
- `runtime/evolution/impact.py`, `runtime/evolution/fitness.py`, `runtime/evolution/entropy_policy.py` (1 ref each)

**Critical file budget tightening (actual+margin)**

| File | max_lines before→after | max_fan_in before→after |
|---|---|---|
| `runtime/constitution.py` | 2200 → 2100 | 22 → 20 |
| `app/main.py` | 1200 → 800 | 8 → 8 |
| `security/cryovant.py` | 950 → 950 | 6 → 5 |
| `runtime/autonomy/loop.py` | 360 → 340 | 3 → 5 |

Budgets now sit within ~50 lines / 1 fan-in unit of current actuals. Growth
triggers CI failure immediately rather than at a distant ceiling.

**Validator output (post-PR)**
```json
{
  "legacy_count": 6,
  "metrics_coverage_percent": 100.0,
  "status": "ok",
  "errors": []
}
```

**Invariants added / tightened**
- `INVARIANT 6.1-LEGACY-0` — `legacy_count ≤ 6` enforced on every PR via `simplification-contract-gate`
- `INVARIANT 6.1-BUDGET-0` — critical file line + fan-in budgets reflect actual baseline; no unbounded ceiling

## [3.1.0] — 2026-03-07 · PR-PHASE6-04 · Phase 6 Close-Out + v3.1.0 GA

### Phase 6 · Complete (M6-03 · M6-04 · M6-05)

**PR-PHASE6-04** closes Phase 6 — Autonomous Roadmap Self-Amendment. All five
milestones (M6-01 through M6-05) are shipped and the platform advances to v3.1.0 GA.

**M6-03 — EvolutionLoop integration** (`runtime/evolution/evolution_loop.py`)

Six-gate prerequisite check (`_evaluate_m603_amendment_gates`) wired into
`EvolutionLoop.run_epoch()`. After every Nth epoch (default 10, configurable via
`ADAAD_ROADMAP_AMENDMENT_TRIGGER_INTERVAL`), the loop evaluates all gates deterministically;
any failing gate logs the gate ID and continues the epoch without aborting it.
`EpochResult` gains `amendment_proposed: bool` and `amendment_id: Optional[str]`.

Constitutional invariants enforced:
- `INVARIANT PHASE6-AUTH-0` — `authority_level` immutable after construction
- `INVARIANT PHASE6-STORM-0` — at most 1 pending amendment per node
- `INVARIANT PHASE6-HUMAN-0` — no auto-approval path

Tests: `tests/autonomy/test_evolution_loop_amendment.py` (T6-03-01..13)

**M6-04 — Federated Roadmap Propagation** (`runtime/governance/federation/mutation_broker.py`)

`FederationMutationBroker.propagate_amendment()` ships all-or-nothing propagation
with rollback on peer failure. Source-node approval is provenance only; each
destination node evaluates independently under its own `GovernanceGate`.

`INVARIANT PHASE6-FED-0` enforced: source approval never binds destination nodes.
Ledger events: `federated_amendment_propagated`, `federated_amendment_rollback`.

Tests: `tests/governance/federation/test_federated_amendment.py`

**M6-05 — Autonomous Android Distribution**

All four distribution tracks wired and documented:
- Track 1 (GitHub Releases + Obtainium): CI pipeline verified end-to-end
- Track 2A (F-Droid Official): MR submitted; under F-Droid review queue
- Track 2B (Self-Hosted F-Droid on GitHub Pages): `repo.xml` validated
- Track 3 (PWA on GitHub Pages): `standalone` display mode verified

`INVARIANT PHASE6-APK-0` enforced: every APK passes full governance gate before signing.

**Documentation close-out:**
- `ROADMAP.md` — Phase 6 status → `✅ shipped`; M6-03/04/05 status corrected
- `VERSION` — promoted from `3.1.0-dev` → `3.1.0`
- `docs/releases/3.1.0.md` — Phase 6 GA release evidence

### Phase 6.1 · Simplification Contract Alignment

Phase 6.1 keeps the simplification contract in **tightening mode**. No budget
relaxation was introduced for this change set.

| Critical file | Policy | Budget |
|---|---|---|
| `runtime/constitution.py` | Tightening retained | `max_lines: 2200`, `max_fan_in: 22` |
| `app/main.py` | Tightening retained | `max_lines: 1200`, `max_fan_in: 8` |
| `security/cryovant.py` | Tightening retained | `max_lines: 950`, `max_fan_in: 6` |
| `runtime/autonomy/loop.py` | Tightening retained | `max_lines: 360`, `max_fan_in: 3` |

`INVARIANT 6.1-BUDGET-0`: Budget changes must be explicitly classified as either
**tightening** or **exception**. Tightening claims are valid only when no budget is
loosened in the same change set; any required relaxation must be labeled as an
exception with rationale.

---

## [3.1.0-dev] — 2026-03-07 · PR-PHASE6-03 · M6-04 Federated Roadmap Propagation Complete

### Phase 6 · M6-04 Completion (post-merge close-out)

**PR-PHASE6-03** is complete: `FederationMutationBroker.propagate_amendment()` now
ships atomic all-or-nothing propagation, destination-side independent gate checks,
and ledger emission for `federated_amendment_propagated`.

**Constitutional invariants satisfied:**
- `INVARIANT PHASE6-FED-0` — source-node approval is provenance-only and never binds destination nodes.
- `INVARIANT PHASE6-STORM-0` — propagation path remains compatible with per-node pending-amendment limits.
- `INVARIANT PHASE6-HUMAN-0` — no autonomous merge/sign-off authority introduced.

**Evidence alignment:**
- `docs/comms/claims_evidence_matrix.md` row `phase6-m604-federated-propagation` marked `Complete` with final implementation/test/evidence links.
- `docs/governance/ledger_event_contract.md` payload contract for `federated_amendment_propagated` verified against runtime implementation fields.

---

## [3.1.0-dev] — 2026-03-07 · PR-PHASE6-02 · M6-03 EvolutionLoop × RoadmapAmendmentEngine Wire

### Phase 6 · M6-03 Implementation

**PR-PHASE6-02** ships the M6-03 milestone: `RoadmapAmendmentEngine` is wired
into `EvolutionLoop` at the post-epoch-N checkpoint behind a 6-gate prerequisite
check. No amendment proposal is emitted unless all gates pass.

**Files changed:**

| File | Change |
|---|---|
| `runtime/evolution/evolution_loop.py` | `_evaluate_m603_amendment_gates()` inserted at epoch checkpoint; `EpochResult` extended with `amendment_proposed: bool` and `amendment_id: Optional[str]` |
| `runtime/autonomy/roadmap_amendment_engine.py` | `list_pending()` storm-guard method — enforces `INVARIANT PHASE6-STORM-0` (at most 1 pending amendment per node) |
| `tests/autonomy/test_evolution_loop_amendment.py` | T6-03-01..13 acceptance test suite (13 tests) |
| `docs/governance/ledger_event_contract.md` | 6 Phase 6 ledger event types registered |
| `docs/ENVIRONMENT_VARIABLES.md` | `ADAAD_ROADMAP_AMENDMENT_TRIGGER_INTERVAL` documented |
| `docs/comms/claims_evidence_matrix.md` | `phase6-m603-evolution-loop-wire` evidence row |

**Constitutional invariants enforced:**
- `INVARIANT PHASE6-AUTH-0` — `authority_level` immutable after construction
- `INVARIANT PHASE6-STORM-0` — `list_pending()` gate blocks storm condition
- `INVARIANT PHASE6-HUMAN-0` — no auto-approval path present

**CI jobs added:** `phase6-amendment-gate-determinism` · `phase6-storm-invariant` · `phase6-human-signoff-path`

## [3.1.0-dev] — 2026-03-07 · ArchitectAgent Phase 6 Completion Specification

### Governance — ArchitectAgent Specification v3.1.0

ArchitectAgent has issued the authoritative constitutional specification for Phase 6
completion, covering M6-03 (EvolutionLoop × RoadmapAmendmentEngine wire), M6-04
(Federated Roadmap Propagation), and M6-05 (Android Distribution close).

**New governance artifacts:**

| Artifact | Purpose |
|---|---|
| `docs/governance/ARCHITECT_SPEC_v3.1.0.md` | Canonical Phase 6 completion spec — PR gates, invariants, failure modes, acceptance criteria |
| `docs/governance/ADAAD_PR_PROCESSION_2026-03.md` (addendum) | PR-PHASE6-02, PR-PHASE6-03, PR-PHASE6-04 definitions + v3.1.0 tag gate |
| `ROADMAP.md` (updated) | M6-03 and M6-04 assigned to PR-PHASE6-02 and PR-PHASE6-03 |
| `docs/ARCHITECTURE_SUMMARY.md` (updated) | Canonical spec pointer updated to v3.1.0 |

**New constitutional invariants (Phase 6 additions):**
- `INVARIANT PHASE6-AUTH-0` — `authority_level` immutable on amendment proposals
- `INVARIANT PHASE6-STORM-0` — at most 1 pending amendment per node
- `INVARIANT PHASE6-HUMAN-0` — human sign-off non-delegatable for amendments
- `INVARIANT PHASE6-FED-0` — source approval never binds destination nodes
- `INVARIANT PHASE6-APK-0` — every APK passes governance gate before signing

**Phase 6 PR sequence now governed:**
```
PR-PHASE6-02  →  PR-PHASE6-03  →  PR-PHASE6-04  →  v3.1.0 tag
  (M6-03)          (M6-04)         (M6-05 close)
```

---

## [3.1.0-dev] — 2026-03-06 · Phase 6 + Free Android Distribution

### PR-PHASE6-01 · ArchitectAgent Constitutional Spec v3.1.0 + Phase 6 Governance Foundations

**ArchitectAgent deliverable — no code generated. All outputs are governance specifications,
machine-interpretable invariants, and audit-ready architectural blueprints.**

**New governance documents:**

| Document | Purpose |
|----------|---------|
| `docs/governance/ARCHITECT_SPEC_v3.1.0.md` | Canonical Phase 6 constitutional specification — 18 constitutional rules, Founders Law amendment `FL-ROADMAP-SIGNOFF-V1`, complete subsystem blueprints for M6-02/M6-03/M6-04/M6-05, all Phase 6 failure modes |
| `docs/governance/ledger_event_contract.md` §8 | Phase 6 roadmap amendment event type registration — 7 new event types with required payload schemas |
| `docs/ENVIRONMENT_VARIABLES.md` | `ADAAD_ROADMAP_AMENDMENT_TRIGGER_INTERVAL` registered — default `'10'`, min-1 enforced at boot |
| `docs/governance/SECURITY_INVARIANTS_MATRIX.md` | Phase 6 security invariants appended — 12 new invariants covering authority, storage, human sign-off, anti-manipulation, and federated amendment |

**Constitutional invariants issued (Phase 6 additions to 18-rule set):**
- Rule 17: `roadmap_mutation_human_signoff_required` — BLOCKING — halts any ROADMAP.md modification without human sign-off
- Rule 18: `amendment_no_auto_merge` — BLOCKING — no automated merge path for roadmap amendments
- Founders Law: `FL-ROADMAP-SIGNOFF-V1` — new blocking rule in `DEFAULT_LAW_RULES`

**Phase 6 PR sequence authorised:**

| PR | Milestone | CI Tier | Human Sign-off |
|----|-----------|---------|----------------|
| `PR-PHASE6-02` | M6-03 EvolutionLoop wire | critical | **REQUIRED** |
| `PR-PHASE6-03` | M6-04 Federated propagation | critical | **REQUIRED per node** |
| `PR-PHASE6-04` | M6-05 Distribution complete | standard | Required (F-Droid MR) |
| **v3.1.0 tag** | Phase 6 GA | — | **REQUIRED** |



The mutation engine can now propose, score, and submit governed amendments to
ROADMAP.md itself. All proposals are constitutional-gated (authority_level =
`governor-review`), require ≥2 human governor approvals, and are deterministically
replayable via `verify_replay()`.

**New modules:**

| Module | Purpose |
|--------|---------|
| `runtime/autonomy/roadmap_amendment_engine.py` | `RoadmapAmendmentEngine` — propose, approve, reject, replay-verify roadmap amendments |
| `runtime/autonomy/proposal_diff_renderer.py` | `render_proposal_diff()` — Markdown diff output for Aponi IDE and PR descriptions |
| `tests/autonomy/test_roadmap_amendment_engine.py` | 22 acceptance-criteria tests covering scoring, authority invariants, determinism, and terminal states |

**Authority invariants:**
- `authority_level` is hardcoded to `"governor-review"` and cannot be injected by any agent
- No change to ROADMAP.md occurs without 2 governor approvals + human-approval gate sign-off
- Every proposal carries a `lineage_chain_hash` (SHA-256 of prior_roadmap_hash + content_hash)
- `DeterminismViolation` raised on replay hash divergence — proposal halts, no commit

**Acceptance criteria shipped:**
- `diff_score ∈ [0.0, 1.0]` enforced on every proposal
- `GovernanceViolation` on short rationale (< 10 words) or invalid milestone status
- Double-approval by same governor rejected
- Terminal status (APPROVED/REJECTED) blocks further transitions
- JSON round-trip deterministic across 100% of test scenarios

### Free Android Distribution (v3.1.0)

ADAAD is now publicly launchable on Android at **zero cost** via three parallel tracks:

| Track | Channel | Latency |
|-------|---------|---------|
| 1 | GitHub Releases + Obtainium | Immediate on `free-v*` tag |
| 2A | F-Droid Official Repository | ~1–4 week review |
| 2B | Self-Hosted F-Droid (GitHub Pages) | Minutes |
| 3 | GitHub Pages PWA | Minutes (CI) |

**New files:**

| File | Purpose |
|------|---------|
| `.github/workflows/android-free-release.yml` | Free 5-job CI: governance gate → signed APK → GitHub Release → F-Droid metadata → PWA deploy |
| `android/fdroid/com.innovativeai.adaad.yml` | F-Droid application metadata (categories, build spec, reproducibility config) |
| `android/obtainium.json` | Obtainium import config for auto-update from GitHub Releases |
| `DISTRIBUTION.md` | Full free launch playbook with day-0 checklist, cost matrix, and security notes |

**Total launch cost: $0**

---

## [3.0.0] — 2026-03-06

### Phase 5 — Multi-Repo Federation (SHIPPED)

#### PR-PHASE5-01: HMAC Key Validation (M-05)
- **New:** `runtime/governance/federation/key_registry.py` enforces minimum-length HMAC key at boot
- **New:** Boot halts with `FederationKeyError` if key material is absent or below minimum threshold (fail-closed)
- `tests/governance/federation/test_federation_hmac_key_validation.py` — 100% branch coverage

#### PR-PHASE5-02: Cross-Repo Lineage (`federation_origin`)
- **New:** `LineageLedgerV2` extended with `federation_origin: FederationOrigin | None` field
- **New:** Mutations carrying federated origin are traceable to source-repo epoch chain; origin preserved across serialization round-trips
- `tests/test_lineage_federation_origin.py` — replay-stable verification

#### PR-PHASE5-03: FederationMutationBroker
- **New:** `runtime/governance/federation/mutation_broker.py` — governed cross-repo mutation propagation
- **New:** `GovernanceGate.approve_mutation()` required in BOTH source and destination repos before any federated mutation is accepted
- Fail-closed: any gate failure in either repo rejects the federated proposal unconditionally
- `tests/test_federation_mutation_broker.py`

#### PR-PHASE5-04: FederatedEvidenceMatrix
- **New:** `runtime/governance/federation/federated_evidence_matrix.py` — cross-repo determinism verification gate
- **New:** Release gate output includes `federated_evidence` section; `divergence_count > 0` blocks promotion
- `tests/test_federated_evidence_matrix.py`

#### PR-PHASE5-05: EvolutionFederationBridge + ProposalTransportAdapter
- **New:** `runtime/governance/federation/evolution_federation_bridge.py` — lifecycle wiring: broker and evidence matrix initialised and torn down with `EvolutionRuntime`
- **New:** `runtime/governance/federation/proposal_transport_adapter.py` — flush/receive proposals via `FederationTransport`
- `tests/test_evolution_federation_bridge.py`, `tests/test_proposal_transport_adapter.py`

#### PR-PHASE5-06: Federated Evidence Bundle + Release Gate
- **New:** `runtime/evolution/evidence_bundle.py` extended: `federated_evidence` section emitted in release gate output
- **New:** Release gate fails if `federated_evidence.divergence_count > 0`
- `tests/test_evidence_bundle_federated.py`

#### PR-PHASE5-07: Federation Determinism CI + HMAC Key Rotation Runbook
- **New:** `.github/workflows/federation_determinism.yml` — Phase 5 required CI gate enforcing 0-divergence invariant on every PR touching federation runtime, evidence bundle, governance gate, or federation tests
- **New:** `docs/runbooks/hmac_key_rotation.md` — operational runbook for HMAC key rotation in production federation deployments

### Summary
Phase 5 completes the multi-repo federation architecture described in the ADAAD roadmap. Every federated mutation now requires dual GovernanceGate approval, carries cross-repo lineage provenance, and is blocked by the FederatedEvidenceMatrix if any determinism divergence is detected. The federation_determinism CI job enforces these invariants on every PR. Phase 6 (Autonomous Roadmap Self-Amendment) is promoted to active.


## [2.3.0] — 2026-03-06

### Phase 4 — AST-Aware Scoring + Pipeline Intelligence (SHIPPED)

#### PR-PHASE4-02: SemanticDiffEngine wired into scoring pipeline
- **New:** `MutationFitnessEvaluator.evaluate()` enriches code_diff with AST-derived risk/complexity via `enrich_code_diff_with_semantic()` when `python_content` is available
- **New:** `scoring_algorithm_version: "semantic_diff_v1.0"` injected into every scored payload
- **New:** `EpochResult.semantic_scored_count` + `scoring_algorithm_version` fields
- Graceful degradation: falls back to v1 LOC heuristics on SyntaxError or parse failure
- Backward-compatible: all existing scoring consumers unaffected

#### PR-PHASE4-03: MutationRouteOptimizer — Phase 2.5 pre-scoring gate
- **New:** `EvolutionLoop.run_epoch()` Phase 2.5: routes each candidate (TRIVIAL / STANDARD / ELEVATED) before deep scoring
- **New:** ELEVATED mutations annotated in `EpochResult.elevated_mutation_ids` for human-review
- **New:** TRIVIAL count reported in `EpochResult.trivial_fast_pathed`
- **New:** `mutation_route_decision` ledger event emitted per epoch
- Fail-graceful: routing errors never halt the epoch

#### PR-PHASE4-04: EntropyFastGate — Phase 1.5 entropy preflight
- **New:** Phase 1.5 preflight: proposals containing nondeterministic sources (random, uuid, time.time, os.urandom) scanned before seeding
- **New:** DENY → proposal quarantined, `entropy_gate_quarantine` ledger event emitted
- **New:** `EpochResult.entropy_quarantined` + `entropy_warned` fields
- Strict mode by default (`strict=True`): nondeterministic proposals never reach population

#### PR-PHASE4-05: CheckpointChain — epoch transition anchoring
- **New:** `EvolutionLoop.__init__` loads and verifies `data/checkpoint_chain.jsonl` at boot — halts on integrity failure (fail-closed)
- **New:** Phase 5c: every epoch anchored to running `CheckpointChain` (append-only JSONL, hash-linked)
- **New:** `EpochResult.checkpoint_digest` — chain_digest of the new epoch link
- Chain integrity check via `verify_checkpoint_chain()` at boot; tampering → `RuntimeError`

#### PR-PHASE4-06: ParallelGovernanceGate — concurrent axis evaluation
- **New:** `GateDecision.gate_mode: str` field (`"serial"` | `"parallel"`) in all ledger events
- **New:** `GovernanceGate.approve_mutation(parallel=True)` delegates to `ParallelGovernanceGate.approve_mutation_parallel()`
- Serial path fully backward-compatible (default `parallel=False`)
- Parallel fallback: any failure reverts to serial (fail-safe)

#### PR-PHASE4-07: Lineage confidence scoring + semantic determinism CI
- **New:** `LineageLedgerV2.semantic_proximity_score()` — cosine similarity in (risk, complexity) 2D space against rolling mean of last 10 accepted mutations
  - `proximity_bonus ∈ [0.0, 0.15]` — semantic similarity to accepted lineage
  - `exploration_bonus ∈ [0.0, 0.10]` — semantic novelty reward
- **New:** `EpochResult.mean_lineage_proximity` — mean lineage score for accepted mutations
- **New CI job:** `semantic-diff-determinism` — 10 fixed AST fixture proofs on every push

[2.2.0] — 2026-03-06

### Phase 2 — Governed Explore/Exploit Loop (SHIPPED)

#### PR-PHASE2-01: ExploreExploitController
- **New:** `runtime/autonomy/explore_exploit_controller.py` — governed mode switching between Explore (breadth-first) and Exploit (depth-first refinement)
- Constitutional invariant: `MIN_EXPLORE_RATIO = 0.20` — hard floor enforced at every epoch (≥20% epochs must be EXPLORE)
- `MAX_CONSECUTIVE_EXPLOIT = 4` — automatic EXPLORE reversion after 4 consecutive EXPLOIT epochs
- Transition priority order: human_override > plateau_detected > consecutive_limit > explore_floor > score_threshold > default_explore
- Plateau detection wired: `FitnessLandscape.is_plateau()` triggers forced EXPLORE
- Every mode transition emits a signed `ModeTransitionEvent` to audit ledger
- State persisted as JSON across epochs; reloads cleanly across restarts
- Audit writer failure never blocks mode selection (fail-open on audit only)
- **Tests: 23 ExploreExploitController tests passing**

#### PR-PHASE2-02: HumanApprovalGate
- **New:** `runtime/governance/human_approval_gate.py` — structural human-in-the-loop approval gate
- Lifecycle: PENDING → APPROVED/REJECTED → REVOKED (append-only; no in-place mutation)
- `is_approved()` is the canonical fail-closed gate check: returns False for pending, rejected, revoked, and unknown mutations
- `batch_approve()` for L2+ per-generation review cadence
- Every approval/rejection/revocation is signed with SHA-256 digest and appended to immutable audit ledger
- `audit_trail()` filterable by mutation_id for full provenance
- Audit writer failure never blocks approval decisions
- **Tests: 22 HumanApprovalGate tests passing**

#### PR-PHASE2-03: LineageDAG
- **New:** `runtime/evolution/lineage_dag.py` — multi-generational directed acyclic graph for G0→G7+ lineage tracking
- `add_node()`: validates parent existence, generation correctness (parent.gen+1), max depth (G20), and promoted⟹approved invariant
- `promote_node()`: immutable promotion record appended to JSONL; in-memory state updated
- `get_lineage_chain()`: full ancestor trace from any node back to G0
- `compare_branches()`: fitness delta + common ancestor + generation distance between two subtrees
- `generation_summary()`: per-generation statistics (node_count, avg_fitness, top_node, approved/promoted counts)
- `integrity_check()`: SHA-256 rolling chain verified from genesis to current tip
- `health_snapshot()`: governance-ready summary including approval_rate, promotion_rate, chain_digest
- Full persistence: JSONL append-only log with promotion events as distinct record type
- **Tests: 22 LineageDAG tests passing**

#### PR-PHASE2-04: PhaseTransitionGate
- **New:** `runtime/governance/phase_transition_gate.py` — governed autonomy level advancement (L0→L4)
- 5-criteria gate per phase: min_approved_mutations, min_mutation_pass_rate, min_lineage_completeness, audit_chain_intact, min_consecutive_clean_epochs
- Phase skip enforcement: transitions can only advance by exactly one level
- `evaluate_gate()`: read-only multi-criteria evaluation with per-criterion `CriterionResult`
- `attempt_transition()`: commits transition if gate passes; always writes audit record
- `record_epoch_outcome()`: tracks consecutive clean epochs; dirty epoch resets counter to zero
- `demote_phase()`: immediate operator rollback to any lower phase, no criteria required
- `PHASE_GATE_CRITERIA` monotonically increasing requirements (Phase 4 requires 100% lineage completeness)
- All transitions write signed audit records to append-only JSONL
- **Tests: 35 PhaseTransitionGate tests passing**

#### PR-PHASE2-05: EvolutionLoop wiring
- `EvolutionLoop` wired with `ExploreExploitController` — injected via optional `controller` kwarg (test-safe)
- `EpochResult` extended: `evolution_mode` (str) and `window_explore_ratio` (float) fields added
- Phase 0b injection in `run_epoch()`: mode selected before proposal phase; committed after landscape recording
- `controller.commit_epoch()` called after every epoch with actual mode used
- Backward-compatible: all existing `EpochResult` consumers unaffected (new fields have defaults)
- **Tests: 5 integration tests passing**

### Summary
- **102 new tests passing** (23 + 22 + 22 + 35 + 5 = 102) — zero regressions on existing test suite
- All modules: pure Python stdlib, Android/Pydroid3 compatible
- All audit writers: fail-open on external ledger failures; core operations never blocked by audit unavailability
- Constitutional invariant coverage: MIN_EXPLORE_RATIO, MAX_CONSECUTIVE_EXPLOIT, phase-skip prevention, promoted⟹approved, G20 depth cap, 100% lineage requirement at L4


## [2.1.0] — 2026-03-06

### Phase 3 — Adaptive Penalty Weights (SHIPPED)

#### PR-PHASE3-01: PenaltyAdaptor
- **New:** `runtime/autonomy/penalty_adaptor.py` — momentum-descent learner for `risk_penalty` and `complexity_penalty`
- Activation gate: `MIN_EPOCHS_FOR_PENALTY=5` (pass-through below threshold)
- Signal derivation: post-merge `actually_risky`/`actually_complex` flags (quality-1); heuristic `risk_score > 0.50` (fallback)
- EMA smoothing (alpha=0.25), momentum=0.80, learning_rate=0.04
- All weights bounded `[0.05, 0.70]` — constitutional invariant enforced
- `WeightAdaptor` wired: penalty state path derived from adaptor path (test-safe)
- Pre-existing test bug fixed: `acceptance_threshold` default corrected 0.25→0.24
- **Tests: 17 PenaltyAdaptor + 1 integration = 18 new tests passing**

#### PR-PHASE3-02: Thompson Sampling + Non-Stationarity Detector
- **New:** `runtime/autonomy/non_stationarity_detector.py` — Page-Hinkley sequential change detection
- PH constants: threshold=0.20, delta=0.02, MIN_OBSERVATIONS=5, cooldown=3 epochs
- EMA warm-start: `running_mean` initialised to first observation (prevents false-positive accumulation)
- `FitnessLandscape` wired: live UCB1 win rates fed into detector after every `record()`
- Escalation order: plateau→dream, thompson_active→ThompsonBanditSelector, UCB1→BanditSelector, v1 fallback
- Thompson rng seeded from hash(sorted arm state) — deterministic, no external entropy
- `_thompson_active` flag persisted in landscape state JSON (survives restarts)
- **Tests: 15 detector + 8 integration = 23 new tests passing**

### Phase 4 — Semantic Mutation Diff Engine (IN PROGRESS)

#### PR-PHASE4-01: SemanticDiffEngine
- **New:** `runtime/evolution/semantic_diff.py` — AST-based risk and complexity scoring (332 lines)
- `ASTMetrics.from_source()`: node_count, max_depth, cyclomatic complexity, import_count, function_count, class_count, max_nesting
- Risk formula: `(ast_depth_delta × 0.3) + (cyclomatic_delta × 0.4) + (import_surface_delta × 0.3)`
- Complexity formula: `(node_count_norm × 0.5) + (nesting_depth_norm × 0.5)`
- Normalization caps: MAX_AST_DEPTH=50, MAX_CYCLOMATIC=30, MAX_IMPORTS=20, MAX_NODES=500, MAX_NESTING=15
- Graceful fallback on None input or SyntaxError → 0.5/0.5 (no scoring regression)
- `enrich_code_diff_with_semantic()`: backward-compatible dict enrichment with semantic scores
- Algorithm version: `semantic_diff_v1.0` (baked in for replay verification)
- Zero new dependencies — uses Python stdlib `ast` module only
- **Tests: 22 new tests passing**

## [Unreleased]

## [2.1.0] — 2026-03-06

### Phase 3 — Adaptive Penalty Weights (SHIPPED)

#### PR-PHASE3-01: PenaltyAdaptor
- **New:** `runtime/autonomy/penalty_adaptor.py` — momentum-descent learner for `risk_penalty` and `complexity_penalty`
- Activation gate: `MIN_EPOCHS_FOR_PENALTY=5` (pass-through below threshold)
- Signal derivation: post-merge `actually_risky`/`actually_complex` flags (quality-1); heuristic `risk_score > 0.50` (fallback)
- EMA smoothing (alpha=0.25), momentum=0.80, learning_rate=0.04
- All weights bounded `[0.05, 0.70]` — constitutional invariant enforced
- `WeightAdaptor` wired: penalty state path derived from adaptor path (test-safe)
- Pre-existing test bug fixed: `acceptance_threshold` default corrected 0.25→0.24
- **Tests: 17 PenaltyAdaptor + 1 integration = 18 new tests passing**

#### PR-PHASE3-02: Thompson Sampling + Non-Stationarity Detector
- **New:** `runtime/autonomy/non_stationarity_detector.py` — Page-Hinkley sequential change detection
- PH constants: threshold=0.20, delta=0.02, MIN_OBSERVATIONS=5, cooldown=3 epochs
- EMA warm-start: `running_mean` initialised to first observation (prevents false-positive accumulation)
- `FitnessLandscape` wired: live UCB1 win rates fed into detector after every `record()`
- Escalation order: plateau→dream, thompson_active→ThompsonBanditSelector, UCB1→BanditSelector, v1 fallback
- Thompson rng seeded from hash(sorted arm state) — deterministic, no external entropy
- `_thompson_active` flag persisted in landscape state JSON (survives restarts)
- **Tests: 15 detector + 8 integration = 23 new tests passing**

### Phase 4 — Semantic Mutation Diff Engine (IN PROGRESS)

#### PR-PHASE4-01: SemanticDiffEngine
- **New:** `runtime/evolution/semantic_diff.py` — AST-based risk and complexity scoring (332 lines)
- `ASTMetrics.from_source()`: node_count, max_depth, cyclomatic complexity, import_count, function_count, class_count, max_nesting
- Risk formula: `(ast_depth_delta × 0.3) + (cyclomatic_delta × 0.4) + (import_surface_delta × 0.3)`
- Complexity formula: `(node_count_norm × 0.5) + (nesting_depth_norm × 0.5)`
- Normalization caps: MAX_AST_DEPTH=50, MAX_CYCLOMATIC=30, MAX_IMPORTS=20, MAX_NODES=500, MAX_NESTING=15
- Graceful fallback on None input or SyntaxError → 0.5/0.5 (no scoring regression)
- `enrich_code_diff_with_semantic()`: backward-compatible dict enrichment with semantic scores
- Algorithm version: `semantic_diff_v1.0` (baked in for replay verification)
- Zero new dependencies — uses Python stdlib `ast` module only
- **Tests: 22 new tests passing**

### Strategic Evolution — Post-v2.0.0 (2026-03-06)

**PR-EVOLUTION-01: UCB1 Multi-Armed Bandit Agent Selection (Phase 2)**
- `runtime/autonomy/bandit_selector.py` — UCB1 algorithm for agent persona selection
  score(agent) = win_rate + √2 × √(ln N / nᵢ); unpulled arms score +inf
- `FitnessLandscape.recommended_agent()` upgraded: UCB1 active when `total_pulls >= 10`
- `ThompsonBanditSelector` implemented as Phase 3 extension point (not wired)
- `BanditSelector.from_landscape_records()` bootstraps from existing TypeRecord data
- Bandit state persisted alongside landscape in `data/fitness_landscape_state.json`
- 26 tests: arm math, activation threshold, exploration/exploitation, persistence, bootstrap

**PR-EVOLUTION-02: Epoch Telemetry Engine + Weekly Analytics CI**
- `runtime/autonomy/epoch_telemetry.py` — Append-only epoch analytics engine
  Collects: acceptance rate series, rolling mean, weight trajectory, agent distribution,
  plateau events, bandit activation epoch, 5 health indicators
- `tools/epoch_analytics.py` — CLI report generator with `--summary`, `--health`,
  `--fail-on-warning` (CI gate), `--output` flags; exit codes: 0/1/2/3
- `.github/workflows/epoch_analytics.yml` — Weekly CI (Monday 06:00 UTC):
  generates report JSON artifact, writes summary to $GITHUB_STEP_SUMMARY, 90d retention
- 32 tests: all health indicator scenarios, persistence round-trip, determinism

**PR-MCP-01: Evolution Pipeline MCP Tool Registration**
- `runtime/mcp/evolution_pipeline_tools.py` — 5 read-only tools:
    fitness_landscape_summary, weight_state, epoch_recommend, bandit_state, telemetry_health
- MCP server: 5 new GET routes (`/evolution/*`)
- `.github/mcp_config.json`: `evolution-pipeline` server registered with 5 tools
- Pre-existing MCP test bug fixed: `test_propose_contracts_deterministic_ids`
  (off-by-one in SeededDeterminismProvider assertion); 7/7 tests now pass

**PR-DOCS-01: ROADMAP.md + Strategic README**
- `ROADMAP.md` — 6-phase evolution roadmap:
    Phase 3: Adaptive penalty weights (Thompson Sampling unlock)
    Phase 4: Semantic mutation diff engine (AST-based risk scoring)
    Phase 5: Multi-repo federation (cross-repo governed mutations)
    Phase 6: Autonomous roadmap self-amendment (constitutionally governed)
  Measurement targets, hard non-goals, constitutional authority chain
- `README.md`: Phase 2 live status, UCB1 algorithm, health targets table,
  performance benchmarks, ROADMAP link in footer, Evolution History milestones

### Repository Hardening — v2.0.0 (2026-03-06)

**Structural simplification**
- Moved 9 historical planning docs from root to `docs/archive/` (EPIC_*.md, ADAAD_7_EXECUTION_PLAN.md, ADAAD_DEEP_DIVE_AUDIT.md, MILESTONE_ROADMAP_ADAAD6-9.md, MERGE_READY_REVIEW_COMMENT_BLOCK.md, PR_v1.0.0_body.md)
- Moved `GOVERNANCE_RISK_SIGNOFF_MEMO.md` from root to `docs/governance/` (canonical governance path)
- Consolidated ephemeral PR comment files from `comments/` and `pr_comments/` into `docs/archive/pr_comments/`
- Added `docs/archive/README.md` — audit trail mapping superseded docs to replacements

**Evidence and governance**
- Added 7 new rows to `docs/comms/claims_evidence_matrix.md` covering v2.0.0 AI mutation claims
- Closed all remaining open GA closure tracker items (GA-RP.1, GA-SB.1) with evidence links
- Finalized `governance/CANONICAL_ENGINE_DECLARATION.md` — `engine_id: adaad-evolution-engine-v2`, status: active
- Updated `governance/DEPRECATION_REGISTRY.md` — replaced placeholder with 8 real entries covering retired and deprecated components

**Documentation**
- Created `docs/releases/2.0.0.md` — formal v2.0.0 release note with evidence matrix
- Rewrote `docs/manifest.txt` — complete v2.0.0 structure map (all 15 top-level directories documented)
- Updated `docs/README.md` — added ARCHITECT_SPEC_v2.0.0.md entry, v2.0.0 release note link, fixed broken EPIC archive link
- Updated `docs/ARCHITECTURE_SUMMARY.md` — AI Mutation Layer documented, canonical spec referenced

**Code quality**
- Added SPDX header and docstring to `tests/market/__init__.py` (was empty)
- All 644 Python files pass AST validation
- Zero broken imports

## [2.0.0] — 2026-03-06 · AI Mutation Capability Expansion

### Principal/Staff Engineer Grade Implementation

Six-file capability expansion delivering the first functional AI mutation pipeline for ADAAD. Every sub-system that was stub-level or statically hardcoded is now a production-ready, self-improving, lineage-tracked engine.

**mutation_scaffold.py — v2 Upgrade (MODIFY)**
- Added `ScoringWeights` dataclass: externally-injectable, epoch-scoped weight bundle replacing hardcoded float constants. Owned by `WeightAdaptor`, consumed as pure input by the scoring engine.
- Added `PopulationState` dataclass: GA-epoch bookkeeping (generation counter, elite roster, diversity pressure signal). Owned by `PopulationManager`.
- Extended `MutationCandidate` with five lineage fields (`parent_id`, `generation`, `agent_origin`, `epoch_id`, `source_context_hash`) — all `Optional` with defaults, 100% backward-compatible with existing 5-positional-arg constructors.
- Adaptive acceptance threshold: `adjusted_threshold = base_threshold × (1 - diversity_pressure × 0.4)`. Exploration epochs become more permissive automatically.
- Elitism bonus: `+0.05` score applied post-threshold-adjustment for children of elite-roster parents (lineage reward).
- `MutationScore` extended with `epoch_id`, `parent_id`, `agent_origin`, `elitism_applied` for full DAG traceability.

**ai_mutation_proposer.py — NEW**
- Connects the Claude API (`claude-sonnet-4-20250514`) to the mutation pipeline for the first time.
- Three agent personas with engineered system prompts: Architect (structural, low-medium risk), Dream (experimental, high-gain), Beast (conservative, coverage/performance).
- `CodebaseContext` dataclass with stable MD5 `context_hash()` for lineage binding.
- Pure `urllib.request` — zero third-party deps, Android/Pydroid3 safe.
- Markdown fence stripping (```json...```) for Claude formatting non-compliance robustness.
- `propose_from_all_agents()` as primary EvolutionLoop entry point.

**weight_adaptor.py — NEW**
- Momentum-based coordinate descent (`LR=0.05`, `momentum=0.85`) on `gain_weight` and `coverage_weight`.
- Rolling EMA prediction accuracy (`alpha=0.3`) tracking correct-prediction rate.
- `risk_penalty` and `complexity_penalty` remain static (Phase 2 — requires post-merge telemetry).
- JSON persistence to `data/weight_adaptor_state.json` after every `adapt()` call.
- `MIN_WEIGHT=0.05`, `MAX_WEIGHT=0.70` bounds enforced via clamp — no weight ever zeroed or dominated.

**fitness_landscape.py — NEW**
- Persistent per-mutation-type win/loss ledger with `TypeRecord` dataclasses.
- Plateau detection: all tracked types with `>= 3` attempts below `20%` win rate → switch to Dream.
- Agent recommendation decision tree: plateau→dream, structural wins→architect, perf/coverage wins→beast.
- JSON persistence to `data/fitness_landscape_state.json`.
- Extension point documented: UCB1/Thompson Sampling bandit selector (Phase 2).

**population_manager.py — NEW**
- GA-style population evolution: seed → elitism → BLX-alpha crossover → diversity enforcement → cap.
- BLX-alpha=0.5 crossover: result range `[lo-extent, hi+extent]` with `extent=(hi-lo)×0.5`.
- `MAX_POPULATION=12`, `ELITE_SIZE=3`, `CROSSOVER_RATE=0.4`.
- MD5 fingerprint deduplication (4 fields, 3 d.p.) prevents near-duplicate population lock-in.
- Crossover children inherit `parent_id=parent_a.mutation_id` for elitism bonus eligibility.

**evolution_loop.py — NEW**
- Five-phase epoch orchestrator: Strategy → Propose → Seed → Evolve → Adapt → Record.
- `EpochResult` dataclass: `epoch_id`, `generation_count`, `total_candidates`, `accepted_count`, `top_mutation_ids`, `weight_accuracy`, `recommended_next_agent`, `duration_seconds`.
- `simulate_outcomes=True` mode derives synthetic outcomes from scored population for unit testing without CI integration.
- Graceful degradation: `propose_from_all_agents()` failure captured, empty population handled cleanly.

**adaad/core/health.py — PR #12 FIX**
- `gate_ok` field now always present in health payload (was missing, blocking PR #12 merge).
- Default `gate_ok=True` for backward compatibility; Orchestrator overrides via `extra` dict.
- New `gate_ok` kwarg on `health_report()` for explicit governance gate injection.
- All v1 health payload fields (`status`, `timestamp_iso`, `timestamp_unix`, `timestamp`) preserved.

**Tests (44 new, 0 regressions)**
- `tests/test_mutation_scaffold_v2.py`: 8 tests — v1 compat, weight defaults, adaptive threshold, elitism, lineage, state advance, elite cap, rank kwargs.
- `tests/test_fitness_landscape.py`: 6 tests — record, plateau, sparse guard, dream recommendation, architect recommendation, persistence.
- `tests/test_weight_adaptor.py`: 6 tests — defaults, accuracy convergence, bounds, noop, persistence, momentum smoothing.
- `tests/test_ai_mutation_proposer.py`: 8 tests — proposals, origin, fence stripping, invalid agent, parent_id, context hash, all agents, malformed JSON.
- `tests/test_population_manager.py`: 6 tests — BLX range, lineage, dedup, max cap, elite ids, generation advance.
- `tests/test_evolution_loop.py`: 5 integration tests — EpochResult, accepted count, weight accuracy, landscape recording, agent recommendation.
- `tests/test_pr12_gate_ok.py`: 5 tests — presence, default, override, kwarg, backward compat.


### ADAAD-14 — Cross-Track Convergence (v1.8)

- **PR-14-03 — MarketDrivenContainerProfiler: market × container convergence:** `runtime/sandbox/market_driven_profiler.py` — `MarketDrivenContainerProfiler` uses `score_provider` callable (wrapping `FeedRegistry` or `FederatedSignalBroker`) to select `ContainerProfileTier` (CONSTRAINED / STANDARD / BURST); thresholds: <0.35 → CONSTRAINED (cpu=25%, mem=128MB), ≥0.65 → BURST (cpu=80%, mem=512MB); confidence guard (below 0.30 → STANDARD forced, `overridden=True`); `ProfileSelection` dataclass with lineage digest + journal event; `profile_for_slot()` convenience returning resource dict directly. Two new container profiles: `container_profiles/market_constrained.json` + `market_burst.json`. Factory helpers: `make_profiler_from_feed_registry()` + `make_profiler_from_federated_broker()`. Authority invariant: profiler is advisory; ContainerOrchestrator retains pool authority. 22 tests in `tests/test_market_driven_profiler.py`.

: Darwinian × federation convergence:** `runtime/evolution/budget/cross_node_arbitrator.py` — `CrossNodeBudgetArbitrator` merges peer fitness reports (via `FederationBudgetGossip` + `GossipProtocol`) with local `BudgetArbitrator` for cluster-wide Softmax reallocation; `PeerFitnessReport` with 45 s freshness TTL; `ClusterArbitrationResult` with `effective_evictions` quorum gate (blocks eviction when >50% cluster agents evicted and `ConsensusEngine.has_quorum()` returns false); lineage digest per cluster epoch; allocation broadcast after each run. Authority invariant: writes only to local AgentBudgetPool; never approves mutations. 23 tests in `tests/test_cross_node_budget_arbitrator.py`.

: market × federation convergence:** `runtime/market/federated_signal_broker.py` — `FederatedSignalBroker` bridges `FeedRegistry` live composite readings into `GossipProtocol` broadcasts; `FederationMarketGossip` serialises `MarketSignalReading` ↔ `GossipEvent` (`market_signal_broadcast.v1`); `PeerReading` dataclass with freshness guard (60 s TTL, zero-confidence filter, stale-flag). `cluster_composite()` produces confidence-weighted aggregate across all alive nodes with graceful fallback to local reading on peer absence/failure. Authority invariant: broker never calls GovernanceGate. 24 tests in `tests/market/test_federated_signal_broker.py`.

### ADAAD-10 — Live Market Signal Adapters (v1.4)

- **PR-10-02 — MarketFitnessIntegrator + FitnessOrchestrator live wiring:** `runtime/market/market_fitness_integrator.py` — confidence-weighted composite from FeedRegistry injected into FitnessOrchestrator scoring context as `simulated_market_score`. Lineage digest + signal source propagated. Fail-closed: broken registry yields synthetic fallback. Journal event `market_fitness_signal_enriched.v1`. 12 tests in `tests/market/test_market_fitness_integrator.py` including end-to-end orchestrator integration.
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
  Added missing headers to 8 files: `app/api/__init__.py`, `app/api/nexus/__init__.py`,
  `app/api/nexus/mutate.py`, `security/canonical.py`, `security/challenge.py`,
  `security/challenge_store.py`, `security/ledger/append.py`, `tests/autonomy/__init__.py`.
  `docs/GOVERNANCE_ENFORCEMENT.md` audit freshness updated. `docs/governance/SECURITY_INVARIANTS_MATRIX.md`
  SPDX invariant section updated with CI enforcement reference. Claims evidence matrix
  `spdx-header-compliance` row confirmed Complete. H-08 finding closed 2026-03-06.

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
- PR-3 hardening: checkpoint chain now emits `checkpoint_created`/`checkpoint_chain_verified`/`checkpoint_chain_violated` events, boot enforces chain verification after Cryovant, and epoch-boundary continuity checks fail closed.- Hardened replay-mode provider synchronization so `EvolutionRuntime.set_replay_mode()` aligns the epoch manager provider with the governor provider before strict replay checks.
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
| PR-3H (hardening extension) | Implemented | Post-PR-3 hardening scope is now implemented in-tree: (1) deterministic checkpoint tamper-escalation evidence path, (2) entropy anomaly triage policy thresholds + replay fixtures, and (3) audit-ready hardening acceptance tests for strict replay governance reviews |
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
- PR-3H hardening extension acceptance criteria are validated in-tree: checkpoint tamper-escalation governance events and halt reasons are emitted deterministically, entropy anomaly triage thresholds are policy-enforced with deterministic violation details, and strict-replay checkpoint hard-stop behavior is covered by hardening acceptance tests.

### Roadmap (not yet validated guarantees)

- Sandbox hardening depth beyond current baseline checks.
- Portable cryptographic replay proof bundles suitable for external verifier exchange.
- Federation and cross-instance sovereignty hardening beyond current in-tree coordination/protocol baseline.
- Key-rotation enforcement escalation and audit closure before 1.0 freeze.
- Additional hardening depth beyond PR-3H acceptance criteria (for example external verifier interoperability and broader runtime threat-model expansion) remains roadmap.
- ADAAD-10/11/14 follow-on modules remain roadmap items until merged and file-presence-verified in this branch snapshot; `runtime/evolution/mutation_credit_ledger.py` is now present with append-only replay verification, while deployment authority/reviewer-pressure tracks remain roadmap.

## 0.65.0 - Initial import of ADAAD He65 tree

- Established canonical `User-ready-ADAAD` tree with five-element ownership (Earth, Wood, Fire, Water, Metal).
- Added Cryovant gating with ledger/keys scaffolding and certification checks to block uncertified Dream/Beast execution.
- Normalized imports to canonical roots and consolidated metrics into `reports/metrics.jsonl`.
- Introduced deterministic orchestrator boot order, warm pool startup, and minimal Aponi dashboard endpoints.

## [2.1.0] — 2026-03-06

### Phase 3 — Adaptive Penalty Weights (SHIPPED)

#### PR-PHASE3-01: PenaltyAdaptor
- **New:** `runtime/autonomy/penalty_adaptor.py` — momentum-descent learner for `risk_penalty` and `complexity_penalty`
- Activation gate: `MIN_EPOCHS_FOR_PENALTY=5` (pass-through below threshold)
- Signal derivation: post-merge `actually_risky`/`actually_complex` flags (quality-1); heuristic `risk_score > 0.50` (fallback)
- EMA smoothing (alpha=0.25), momentum=0.80, learning_rate=0.04
- All weights bounded `[0.05, 0.70]` — constitutional invariant enforced
- `WeightAdaptor` wired: penalty state path derived from adaptor path (test-safe)
- Pre-existing test bug fixed: `acceptance_threshold` default corrected 0.25→0.24
- **Tests: 17 PenaltyAdaptor + 1 integration = 18 new tests passing**

#### PR-PHASE3-02: Thompson Sampling + Non-Stationarity Detector
- **New:** `runtime/autonomy/non_stationarity_detector.py` — Page-Hinkley sequential change detection
- PH constants: threshold=0.20, delta=0.02, MIN_OBSERVATIONS=5, cooldown=3 epochs
- EMA warm-start: `running_mean` initialised to first observation (prevents false-positive accumulation)
- `FitnessLandscape` wired: live UCB1 win rates fed into detector after every `record()`
- Escalation order: plateau→dream, thompson_active→ThompsonBanditSelector, UCB1→BanditSelector, v1 fallback
- Thompson rng seeded from hash(sorted arm state) — deterministic, no external entropy
- `_thompson_active` flag persisted in landscape state JSON (survives restarts)
- **Tests: 15 detector + 8 integration = 23 new tests passing**

### Phase 4 — Semantic Mutation Diff Engine (IN PROGRESS)

#### PR-PHASE4-01: SemanticDiffEngine
- **New:** `runtime/evolution/semantic_diff.py` — AST-based risk and complexity scoring (332 lines)
- `ASTMetrics.from_source()`: node_count, max_depth, cyclomatic complexity, import_count, function_count, class_count, max_nesting
- Risk formula: `(ast_depth_delta × 0.3) + (cyclomatic_delta × 0.4) + (import_surface_delta × 0.3)`
- Complexity formula: `(node_count_norm × 0.5) + (nesting_depth_norm × 0.5)`
- Normalization caps: MAX_AST_DEPTH=50, MAX_CYCLOMATIC=30, MAX_IMPORTS=20, MAX_NODES=500, MAX_NESTING=15
- Graceful fallback on None input or SyntaxError → 0.5/0.5 (no scoring regression)
- `enrich_code_diff_with_semantic()`: backward-compatible dict enrichment with semantic scores
- Algorithm version: `semantic_diff_v1.0` (baked in for replay verification)
- Zero new dependencies — uses Python stdlib `ast` module only
- **Tests: 22 new tests passing**

## [Unreleased]

## [2.1.0] — 2026-03-06

### Phase 3 — Adaptive Penalty Weights (SHIPPED)

#### PR-PHASE3-01: PenaltyAdaptor
- **New:** `runtime/autonomy/penalty_adaptor.py` — momentum-descent learner for `risk_penalty` and `complexity_penalty`
- Activation gate: `MIN_EPOCHS_FOR_PENALTY=5` (pass-through below threshold)
- Signal derivation: post-merge `actually_risky`/`actually_complex` flags (quality-1); heuristic `risk_score > 0.50` (fallback)
- EMA smoothing (alpha=0.25), momentum=0.80, learning_rate=0.04
- All weights bounded `[0.05, 0.70]` — constitutional invariant enforced
- `WeightAdaptor` wired: penalty state path derived from adaptor path (test-safe)
- Pre-existing test bug fixed: `acceptance_threshold` default corrected 0.25→0.24
- **Tests: 17 PenaltyAdaptor + 1 integration = 18 new tests passing**

#### PR-PHASE3-02: Thompson Sampling + Non-Stationarity Detector
- **New:** `runtime/autonomy/non_stationarity_detector.py` — Page-Hinkley sequential change detection
- PH constants: threshold=0.20, delta=0.02, MIN_OBSERVATIONS=5, cooldown=3 epochs
- EMA warm-start: `running_mean` initialised to first observation (prevents false-positive accumulation)
- `FitnessLandscape` wired: live UCB1 win rates fed into detector after every `record()`
- Escalation order: plateau→dream, thompson_active→ThompsonBanditSelector, UCB1→BanditSelector, v1 fallback
- Thompson rng seeded from hash(sorted arm state) — deterministic, no external entropy
- `_thompson_active` flag persisted in landscape state JSON (survives restarts)
- **Tests: 15 detector + 8 integration = 23 new tests passing**

### Phase 4 — Semantic Mutation Diff Engine (IN PROGRESS)

#### PR-PHASE4-01: SemanticDiffEngine
- **New:** `runtime/evolution/semantic_diff.py` — AST-based risk and complexity scoring (332 lines)
- `ASTMetrics.from_source()`: node_count, max_depth, cyclomatic complexity, import_count, function_count, class_count, max_nesting
- Risk formula: `(ast_depth_delta × 0.3) + (cyclomatic_delta × 0.4) + (import_surface_delta × 0.3)`
- Complexity formula: `(node_count_norm × 0.5) + (nesting_depth_norm × 0.5)`
- Normalization caps: MAX_AST_DEPTH=50, MAX_CYCLOMATIC=30, MAX_IMPORTS=20, MAX_NODES=500, MAX_NESTING=15
- Graceful fallback on None input or SyntaxError → 0.5/0.5 (no scoring regression)
- `enrich_code_diff_with_semantic()`: backward-compatible dict enrichment with semantic scores
- Algorithm version: `semantic_diff_v1.0` (baked in for replay verification)
- Zero new dependencies — uses Python stdlib `ast` module only
- **Tests: 22 new tests passing** — ADAAD-10 · v1.4.0

### ADAAD-10 Track A — Live Market Signal Adapters

- **PR-10-02 — POST /market/signal webhook endpoint + integration tests:** `server.py` gains `POST /market/signal` bearer-auth-gated endpoint routing raw payloads through `LiveSignalRouter` → lineage-stamped `MarketSignalReading` → fitness advisory injection; journal event `market_signal_ingested.v1`. `tests/market/test_market_fitness_integrator.py`: canonical consolidated suite covering enrich/integrate pathways, integrator bridging (live, synthetic fallback, lineage propagation, journal), and `FitnessOrchestrator.inject_live_signal()` advisory override semantics. ADAAD-10 Track A complete.

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

## [1.8.0] — 2026-03-05 · ADAAD-14 Cross-Track Convergence

All four ADAAD-10–13 runtime tracks converge into a unified, production-grade autonomous governance stack.

### ADAAD-14 · Cross-Track Convergence — What shipped

**PR-14-01 · FederatedSignalBroker (market × federation)**
`runtime/market/federated_signal_broker.py` — `FederatedSignalBroker` publishes local `FeedRegistry` composite readings to all alive federation peers via `GossipProtocol` (`market_signal_broadcast.v1`); ingests peer readings with 60 s TTL freshness guard; `cluster_composite()` produces confidence-weighted aggregate across all nodes; graceful fallback to local reading on peer absence or feed failure. 24 tests.

**PR-14-02 · CrossNodeBudgetArbitrator (Darwinian × federation)**
`runtime/evolution/budget/cross_node_arbitrator.py` — `CrossNodeBudgetArbitrator` gossips local agent fitness scores to peers (`budget_fitness_broadcast.v1`), merges cluster-wide scores (local authoritative on conflict), runs Softmax reallocation across the cluster, broadcasts allocation decisions (`budget_allocation_broadcast.v1`). Quorum gate: evictions affecting >50% of cluster agents require `ConsensusEngine.has_quorum()` before applying (fail-open in single-node mode). 23 tests.

**PR-14-03 · MarketDrivenContainerProfiler (market × container)**
`runtime/sandbox/market_driven_profiler.py` — `MarketDrivenContainerProfiler` queries `FeedRegistry` or `FederatedSignalBroker` cluster composite to select cgroup v2 resource tier: CONSTRAINED (cpu=25%, mem=128 MB) below score 0.35; BURST (cpu=80%, mem=512 MB) at or above 0.65; STANDARD otherwise. Confidence guard (below 0.30 → STANDARD forced). Two new container profiles added: `market_constrained.json` + `market_burst.json`. 22 tests.

### Authority invariants upheld
- `FederatedSignalBroker` is advisory only — market readings influence fitness but never approve mutations.
- `CrossNodeBudgetArbitrator` writes to local `AgentBudgetPool` only — consensus provides ordering, never execution authority.
- `MarketDrivenContainerProfiler` is advisory — `ContainerOrchestrator` retains pool and lifecycle authority.
- `GovernanceGate` remains the sole mutation approval authority across all convergence surfaces.

---

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
