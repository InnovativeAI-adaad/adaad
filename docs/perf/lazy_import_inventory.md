# Lazy Import Inventory and Startup Impact (2026-03-25)

## 1) Module-scope import/initializer inventory

### `server.py`
- **Kept eager (security-critical or low-risk core wiring):** `runtime.metrics`, `security.ledger.journal`, `runtime.constitution`, `security.whaledic_secrets.enforce_whaledic_secret_policy`, FastAPI routing/middleware setup.
- **Deferred behind memoized accessors:**
  - `runtime.metrics_analysis.{rolling_determinism_score, mutation_rate_snapshot}`
  - `runtime.mcp.proposal_validator.validate_proposal`
  - `runtime.mcp.proposal_queue.append_proposal`
  - `runtime.governance.foundation.determinism.default_provider`
  - `runtime.intelligence.router.IntelligenceRouter`
  - `runtime.mcp.linting_bridge.MutationLintingBridge`
  - `runtime.evolution.evidence_bundle.EvidenceBundleBuilder`
- **Diagnostics added:** `lazy_init_success` / `lazy_init_failure` metrics + structured logger errors.

### `ui/aponi_dashboard.py`
- **Kept eager (security/governance state and deterministic constants):** `runtime.constitution`, `runtime.metrics`, governance taxonomy constants, response schema validator, gate state constants.
- **Deferred behind memoized accessors:**
  - `runtime.evolution` classes (`LineageLedgerV2`, `ReplayEngine`, `EvidenceBundleBuilder`, `EvidenceBundleError` type)
  - `runtime.evolution.evidence_graph.build_evidence_graph_projection`
  - `runtime.evolution.lineage_v2.resolve_certified_ancestor_path`
  - `runtime.evolution.replay_attestation` helpers + `REPLAY_PROOFS_DIR`
  - UI feature helpers from `ui.features.{evidence_panel,replay_panel,timeline}`
- **Deferred initializers:** governance and instability policy loading are now lazy-cached with fail-closed errors on first required access.
- **Diagnostics added:** `lazy_init_success` / `lazy_init_failure` metrics for imports and policy loaders.

### `app/main.py`
- **Kept eager fail-closed boot invariants:** `security.cryovant` assertions and `enforce_whaledic_secret_policy` execution in `Orchestrator.boot()` remain eager.
- **Deferred behind accessor:** `ui.aponi_dashboard.AponiDashboard` is imported via `_build_aponi_dashboard()` at orchestrator construction.
- **Diagnostics added:** `lazy_init_success` / `lazy_init_failure` metrics for dashboard module resolution.

## 2) Reproducible measurement commands

```bash
python -X importtime -c "import server"
ADAAD_ENV=dev CRYOVANT_DEV_MODE=1 python -X importtime -c "import ui.aponi_dashboard"
ADAAD_ENV=dev CRYOVANT_DEV_MODE=1 python -X importtime -c "import app.main"
ADAAD_ENV=dev CRYOVANT_DEV_MODE=1 python scripts/measure_import_time.py --iterations 3
```

## 3) Before/after cumulative import-time snapshots (single run)

| Module | Before (ms) | After (ms) | Delta |
|---|---:|---:|---:|
| `server` | 4405.939 | 3416.153 | **-989.786** |
| `ui.aponi_dashboard` | 839.703 | 1170.437 | +330.734 |
| `app.main` | 1955.332 | 5114.951 | +3159.619 |

### 3-run post-change mean (`scripts/measure_import_time.py --iterations 3`)

| Module | Mean (ms) | Median (ms) | Min (ms) | Max (ms) |
|---|---:|---:|---:|---:|
| `server` | 2633.990 | 2540.365 | 2363.656 | 2997.950 |
| `ui.aponi_dashboard` | 750.285 | 753.826 | 665.501 | 831.528 |
| `app.main` | 2572.335 | 2619.132 | 2200.203 | 2897.669 |

## 4) Expected improvement statement

- The primary startup target (`import server`) improves in both one-shot and 3-run sampled measurements.
- Deferred modules now fail with explicit `lazy_init_failed:<module>.<symbol>` errors at call-time, preserving fail-closed semantics while reducing unconditional startup work.
