## ADAAD v1.0.0 — Stable Release

> **Branch:** `dreezy-6` → `main` · **Version:** `0.65.x (Experimental)` → `1.0.0 (Stable)` · **Constitution:** `v0.1.0` → `v0.2.0`

This PR graduates ADAAD from experimental pre-1.0 to its first stable release. It closes every tracked open item in the governance maturity model: completes the constitutional rule set (all 11 rules now enforced), remediates a critical HMAC security gap, ships the Claude-governed MCP co-pilot integration, hardens the forensic retention service for portable deployment, establishes the `governance_runtime_profile.lock.json` ownership contract, and expands the verified test surface to 170 files across 14 subdirectories.

Every commit in this PR maps to a tracked milestone item, a documented governance gap, or a validated constitutional requirement. No speculative scope.

---

## ⚠️ CRITICAL — Review First

### HMAC Signature Verification Remediation · `security/cryovant.py`

`verify_signature()` contained a stub that unconditionally returned `False`. The Cryovant trust layer — which gates the entire governance boot sequence, agent certificate checks, and policy artifact attestation — was performing zero cryptographic verification.

```python
# BEFORE — stub: verification never executed
def verify_signature(signature: str) -> bool:
    return False

# AFTER — real HMAC-SHA-256 enforced against KEYS_DIR
def verify_signature(signature: str) -> bool:
    """Verify HMAC-SHA-256 signature against key material in KEYS_DIR."""
    normalized = _normalize_signature(signature)
    if not normalized.startswith(_HMAC_SIGNATURE_PREFIX):
        return False
    digest = normalized[len(_HMAC_SIGNATURE_PREFIX):]
    # constant-time comparison against key material in KEYS_DIR
```

**Every deployment running pre-1.0 code must treat this as the primary upgrade motivator.**

> **Governance surface:** Trust Layer (Cryovant) · boot halt behavior · agent certificate checks · policy artifact attestation
> **Verification:** `tests/test_cryovant_dev_signatures.py` · `test_cryovant_ancestry.py` · `test_cryovant_env.py` · `test_cryovant_identity.py`

---

## Advancement Inventory

### 1 · Constitutional Rule Enforcement — All 11 Rules Active

Constitution advanced to `v0.2.0`. Five previously dormant rules enforced; one new rule introduced.

| Rule | Before | After | Severity |
|---|:---:|:---:|---|
| `single_file_scope` | ✅ | ✅ | BLOCKING |
| `ast_validity` | ✅ | ✅ | BLOCKING |
| `import_smoke_test` | ✅ | ✅ | WARNING (BLOCKING in PRODUCTION tier) |
| `no_banned_tokens` | ✅ | ✅ | BLOCKING |
| `signature_required` | ✅ | ✅ | BLOCKING |
| `max_complexity_delta` | ❌ | ✅ | WARNING |
| `test_coverage_maintained` | ❌ | ✅ | WARNING |
| `max_mutation_rate` | ❌ | ✅ | WARNING + tier escalation/demotion semantics |
| `lineage_continuity` | ❌ | ✅ **ENFORCED** | **BLOCKING** |
| `resource_bounds` | ❌ | ✅ **ENFORCED** | **BLOCKING** |
| `entropy_budget_limit` | — | ✅ **INTRODUCED** | WARNING |

**`lineage_continuity`** validates against the now-canonical `runtime.evolution.lineage_v2.LineageLedgerV2`. The duplicate `security.ledger.lineage_v2` implementation has been retired; a single authoritative chain governs all lineage resolution. `RULE_DEPENDENCY_GRAPH` enforces evaluation ordering: `max_mutation_rate` gates on `lineage_continuity`; `test_coverage_maintained` gates on `resource_bounds` and `max_complexity_delta`.

**`resource_bounds`** consumes Android-aware signals from `runtime.platform.android_monitor.AndroidMonitor` — battery (`< 20%` → constrained), memory (`< 500 MB`), storage, and CPU thresholds — delivering the Pydroid3/Android enforcement profile that was a hard v1.0 prerequisite.

**`entropy_budget_limit`** enforces a per-epoch entropy ceiling, paired with `runtime/evolution/telemetry_audit.py` for declared-vs-observed entropy breakdown.

> **Verification:** `tests/test_constitution_policy.py` · `test_resource_bounds.py` · `test_lineage_continuity.py` · `test_mutation_rate_rule.py` · `test_complexity_delta.py` · `test_entropy_budget.py` · `test_constitution_doc_version.py`

---

### 2 · FastAPI Lifespan Migration · `server.py`

Migrated from the deprecated `@app.on_event('startup')` decorator to the `asynccontextmanager` lifespan handler. Eliminates 2 deprecation warnings per server start; hardens against future FastAPI API removal.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    ui_dir, ui_index, mock_dir, ui_source = _resolve_ui_paths(create_placeholder=True)
    app.state.ui_dir = ui_dir
    app.state.ui_index = ui_index
    app.state.mock_dir = mock_dir
    app.state.ui_source = ui_source
    logging.getLogger(__name__).info("ADAAD server UI source=%s index=%s", ui_source, ui_index)
    yield

app = FastAPI(title="InnovativeAI-adaad Unified Server", lifespan=lifespan)
```

> **Verification:** `tests/test_server_import_smoke.py` · `test_server_audit_endpoints.py` · `test_server_ui_resolution.py`

---

### 3 · Forensic Retention Service — Deployment Hardening · `ops/systemd/`

The service file previously hardcoded `WorkingDirectory=/workspace/ADAAD`, making the unit non-portable outside the CI workspace. The service is now fully parameterized via `ADAAD_ROOT`:

```ini
# BEFORE — hardcoded CI path, non-deployable
WorkingDirectory=/workspace/ADAAD
ExecStart=/workspace/ADAAD/ops/systemd/run_forensic_retention.sh

# AFTER — environment-driven, deployment-portable
Environment=ADAAD_ROOT=/opt/adaad
EnvironmentFile=-/etc/default/adaad
WorkingDirectory=/
ExecStart=/usr/bin/env bash -lc '"${ADAAD_ROOT:-/opt/adaad}/ops/systemd/run_forensic_retention.sh"'
```

`run_forensic_retention.sh` now self-resolves `ADAAD_ROOT` at invocation time — defaulting to the repo root when invoked directly (development), consuming the environment variable when invoked via the systemd unit (production):

```bash
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
ADAAD_ROOT="${ADAAD_ROOT:-${DEFAULT_ROOT}}"
cd "${ADAAD_ROOT}"
```

To deploy at a non-default path:
```bash
printf 'ADAAD_ROOT=/srv/adaad\n' | sudo tee /etc/default/adaad >/dev/null
```

`docs/governance/FORENSIC_BUNDLE_LIFECYCLE.md` now documents the `ADAAD_ROOT` resolution chain and override mechanism. This closes the `WorkingDirectory` portability gap from prior review.

---

### 4 · `governance_runtime_profile.lock.json` — Ownership Contract Established

`docs/ARCHITECTURE_CONTRACT.md` now carries the explicit ownership contract:

> - **Writer:** release/governance maintainers when the runtime contract evolves.
> - **Readers:** `runtime.preflight.validate_boot_runtime_profile(...)` and deterministic replay boot tests.
> - **VCS policy:** committed in-repo as a canonical governance lock — must never be `.gitignore`d.

`docs/governance/STRICT_REPLAY_INVARIANTS.md` introduces Invariant 6 (hermetic runtime profile must validate before governance-critical boot; lock file is versioned with governance/release) and Invariant 7 (fail-closed boot posture — any runtime profile mismatch halts boot prior to mutation execution).

The lock file SHA256 has been advanced to `7b3d06cf33c0cae90708dce16e87d53738f34e1805e92b41c4c783651b1bf593`, reflecting the dependency fingerprint after all v1.0 changes land. Enforcement path: `runtime.preflight.validate_boot_runtime_profile(...)` executes in `app/main.py` before runtime initialization. This closes the lock file ownership gap from prior review.

---

### 5 · Determinism Lint Scope — `federation/coordination.py` Enforced

`tools/lint_determinism.py` `REQUIRED_GOVERNANCE_FILES` now governs `runtime/governance/federation/coordination.py`:

```python
REQUIRED_GOVERNANCE_FILES: tuple[str, ...] = (
    "runtime/evolution/fitness_orchestrator.py",
    "runtime/evolution/economic_fitness.py",           # ← active evaluator path enforced
    "runtime/governance/federation/transport.py",
    "runtime/governance/federation/coordination.py",   # ← enforced
)
```

CI fails immediately if any required governance file is absent or renamed. `coordination.py` was promoted to implemented baseline in a prior PR but remained outside the explicit lint scope.

> **Verification:** `tests/test_lint_determinism.py`

---

### 6 · Test Isolation — `_reset_bootstrapped_flag` Autouse Fixture

`tests/test_adaad_core_and_dispatcher.py` now governs `_BOOTSTRAPPED` reset via a `pytest` autouse fixture, replacing the prior `teardown_function`:

```python
@pytest.fixture(autouse=True)
def _reset_bootstrapped_flag() -> None:
    """Enforce clean bootstrap module state before and after each test."""
    bootstrap_module._BOOTSTRAPPED = False
    try:
        yield
    finally:
        bootstrap_module._BOOTSTRAPPED = False
```

The fixture enforces clean state on both sides of each test execution. The prior `teardown_function` only cleaned up after; dirty state from a previous session could poison the first test of a new run. This was the root cause of the 4 intermittent failures identified in prior analysis.

---

### 7 · MCP Co-Pilot — Claude-Governed Proposal Surface

A governed write surface for LLM mutation proposals, delivered via four MCP servers defined in `.github/mcp_config.json` and implemented across `runtime/mcp/`. All write paths are JWT-gated, constitutionally pre-evaluated, and `authority_level` is clamped server-side to `governor-review` — no client can self-elevate.

```
ClaudeProposalAgent (MutatorAgent role)
        │
        ▼
runtime/mcp/server.py                 JWT-gated FastAPI; /health is the sole open route
        │
        ▼
runtime/mcp/proposal_validator.py
    ├─ Schema enforcement    schemas/mcp/proposal_request.v1.json
    ├─ Tier-0 gate           Tier-0 targets rejected without human elevation_token
    ├─ Constitutional gate   evaluate_mutation() enforced before queue append
    └─ Authority clamp       authority_level forced to "governor-review"
        │
        ▼
runtime/mcp/proposal_queue.py         Append-only, hash-linked JSONL
        │
        ├─▶ mutation_analyzer.py      Deterministic fitness + risk prediction
        ├─▶ rejection_explainer.py    guard_report → plain-English explanation
        └─▶ candidate_ranker.py       Fitness-weighted deterministic ranking
```

**Four MCP servers (`.github/mcp_config.json`):**

| Server | Tools |
|---|---|
| `aponi-local` | `system_intelligence`, `risk_summary`, `evolution_timeline`, `replay_diff`, `policy_simulate`, `mutation_analyze`, `mutation_explain_rejection`, `mutation_rank` |
| `ledger-mirror` | `ledger_list`, `ledger_read` |
| `sandbox-proxy` | `policy_simulate`, `skill_profiles_list` |
| `mcp-proposal-writer` | `mutation_propose`, `mutation_analyze`, `mutation_explain_rejection`, `mutation_rank` |

`tests/mcp/test_tools_parity.py` enforces exact match between `mcp_config.json` and `runtime/mcp/tools_registry.py` — names, order, and set must be identical at all times.

> **Implementation reference:** `docs/mcp/IMPLEMENTATION.md`
> **Verification:** `tests/mcp/test_mcp_server.py` · `test_tools_parity.py` · `test_proposal_validator.py` · `test_mutation_analyzer.py` · `test_rejection_explainer.py` · `test_candidate_ranker.py`

---

### 8 · Lineage Consolidation — Single Source of Truth

The duplicate `security.ledger.lineage_v2` implementation has been retired. All lineage chain resolution now routes exclusively through `runtime.evolution.lineage_v2.LineageLedgerV2`. This consolidation was a hard prerequisite for promoting `lineage_continuity` to BLOCKING — constitutional enforcement against a split implementation is not tractable.

> **Verification:** `tests/test_lineage_v2_integrity.py` · `test_lineage_ancestry_validation.py` · `test_lineage_continuity.py`

---

### 9 · Expanded CI Governance Workflows (7 active)

| Workflow | Trigger | Governance Purpose |
|---|---|---|
| `ci.yml` | push/PR to `main` | Tiered classifier computes `pr_tier`, `run_strict_replay`, `run_evidence_suite`, `run_promotion_suite` from path filters. Governance-impact paths automatically enforce strict replay. |
| `determinism_lint.yml` | PR touching `runtime/governance/**`, `runtime/evolution/**`, `security/**`, `app/main.py` | AST-based determinism linter |
| `entropy_baseline.yml` | Scheduled | Entropy baseline profiling |
| `entropy_health.yml` | Scheduled | Entropy health monitoring |
| `governance_strict_release_gate.yml` | `v*-governance-*` / `v*-public-readiness-*` tags | Determinism lint + entropy discipline + strict replay validation before any release tag lands |
| `release_evidence_gate.yml` | `v0.70.0` tag | Enforces `docs/comms/claims_evidence_matrix.md` completeness |
| `codeql.yml` | push/PR on `main` (scheduled) | Static security analysis |

---

### 10 · Dependency Baseline — Path Fragility Eliminated

`scripts/check_dependency_baseline.py` now resolves all requirement file paths via `REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]`, executing correctly from any working directory. Three packages enforced: `fastapi==0.115.5`, `uvicorn==0.30.6`, `anthropic==0.40.0`.

---

### 11 · Schema Surface Hardened

Schemas introduced under `schemas/` to govern the federation transport contract, entropy policies, MCP proposal surface, and evidence bundles:

- `federation_transport_contract.v1.json`, `federation_handshake_{envelope,request,response}.v1.json`
- `federation_policy_exchange.v1.json`, `federation_vote.v1.json`, `federation_replay_proof_bundle.v1.json`
- `entropy_metadata.v1.json`, `entropy_policy.v1.json`, `evidence_bundle.v1.json`
- `llm_mutation_proposal.v1.json`
- `mcp/proposal_request.v1.json`, `mcp/proposal_response.v1.json`, `mcp/analysis_response.v1.json`

All schemas are enforced by `runtime/governance/schema_validator.py` and verified by `tests/governance/test_schema_validator.py`.

---

## Governance Impact Matrix

| Surface | Advancement | Risk |
|---|---|---|
| Trust Layer (Cryovant) | HMAC verification stub **remediated** — real enforcement now active | HIGH — improvement direction; prior behavior was insecure |
| Constitution | All 11 rules **enforced**, `v0.2.0` | HIGH — mutations that previously passed without enforcement will now be gated |
| Execution (MCP) | Governed LLM proposal surface **introduced** | MEDIUM — JWT-gated, constitutionally pre-evaluated, authority clamped server-side |
| Ledger | Lineage v2 duplicate **retired**, single authority enforced | MEDIUM — consolidation prerequisite for BLOCKING rule |
| Server | FastAPI lifespan **migrated** | LOW — behavioral equivalence preserved |
| Platform | Android `resource_bounds` profile **delivered** | LOW — additive, fail-closed direction |
| Ops | Systemd path **parameterized** | LOW — deployment portability hardened |
| Governance lock | Ownership contract **established**, SHA256 **advanced** | LOW — documentation completeness + state synchronization |
| Lint scope | `federation/coordination.py` **enforced** | LOW — enforcement improvement, zero behavioral regression |
| Test isolation | Autouse fixture **governs** bootstrap reset | LOW — strictly stronger isolation |

---

## Advancement Classification

- [x] Security remediation (HMAC verification stub)
- [x] Constitutional enforcement (5 dormant rules activated, 1 introduced)
- [x] Feature delivery (MCP co-pilot, Android platform monitor, entropy budget rule)
- [x] Documentation hardening (architecture contract, forensic bundle lifecycle, strict replay invariants)
- [x] Infrastructure consolidation (lifespan migration, lineage consolidation, systemd parameterization)

## Governance Impact

- [x] Advances policy/constitution behavior
- [x] Advances replay or ledger behavior

---

## Reviewer Checklist

### 🔐 Security (required before merge)

- [ ] `security/cryovant.py` `verify_signature()` — confirm HMAC-SHA-256 comparison is constant-time against `KEYS_DIR`; missing key material must halt verification, not pass it
- [ ] `runtime/mcp/proposal_validator.py` — confirm `authority_level` clamping to `governor-review` cannot be circumvented by any client-supplied input shape, including nested or aliased objects
- [ ] `runtime/mcp/server.py` — confirm `/health` is the sole unauthenticated route; Tier-0 rejection is enforced before `proposal_queue.append_proposal()` is ever reached

### 📜 Constitutional Completeness (required before merge)

- [ ] `grep -c '"enabled": true' runtime/governance/constitution.yaml` → `11`
- [ ] `grep CONSTITUTION_VERSION runtime/constitution.py` → `"0.2.0"`
- [ ] `python -m app.main --dry-run --replay audit --verbose` — boot completes, governance spine fully initialized, zero constitutional evaluation errors

### 🧪 Test Suite (required before merge)

- [ ] `pytest tests/ -q` — all tests pass, zero collection errors
- [ ] `tests/mcp/test_tools_parity.py` passes — MCP config/registry parity enforced
- [ ] `tests/test_cryovant_dev_signatures.py` passes — confirms HMAC verification is real and non-trivial
- [ ] `tests/test_resource_bounds.py` passes — confirms `lineage_continuity` and `resource_bounds` BLOCKING enforcement

### 🔁 Replay and Determinism (required for governance-impact PRs)

- [ ] `python tools/lint_determinism.py runtime/ security/ app/main.py` → `determinism lint passed`
- [ ] `python scripts/verify_core.py` → `Core verification passed`
- [ ] `python scripts/check_dependency_baseline.py` → `Dependency baseline check passed`
- [ ] `python -m app.main --replay strict --verbose` → `replay_verified` emitted, zero divergence reported

### 🔒 Lock File and Ops

- [ ] `cat governance_runtime_profile.lock.json | python -c "import json,sys; d=json.load(sys.stdin); print(d['dependency_lock']['sha256'])"` → matches SHA256 of current `requirements.server.txt`
- [ ] `ops/systemd/adaad-forensic-retention.service` — `WorkingDirectory=/` and `ADAAD_ROOT` env override confirmed for target deployment

---

## Verification Evidence (expected output)

```
pytest tests/ -q
  → all tests pass

python tools/lint_determinism.py runtime/ security/ app/main.py
  → determinism lint passed

python scripts/verify_core.py
  → Core verification passed

python scripts/check_dependency_baseline.py
  → Dependency baseline check passed

grep -c '"enabled": true' runtime/governance/constitution.yaml
  → 11

cat VERSION
  → 1.0.0

grep CONSTITUTION_VERSION runtime/constitution.py
  → CONSTITUTION_VERSION = "0.2.0"
```

---

## Post-Merge Governance Roadmap

Items tracked but intentionally outside this PR's scope:

| Item | Tracked in |
|---|---|
| Distributed federation wire protocol (multi-instance coordination across devices) | Future epic · PR-6 extension |
| Cryptographic replay proof bundles for external verifiers | Future epic |
| Aponi command surface (governed approve/reject from dashboard) | Epic 3 — Aponi-as-IDE |
| Reviewer reputation & calibration loop | Epic 1 — ADAAD-7 |
| Policy simulation DSL | Epic 2 — ADAAD-8 |

---

## CHANGELOG

This PR corresponds to the full `[Unreleased]` block in `CHANGELOG.md`. On merge, the block should be promoted to `## [1.0.0]` with today's date.

PR milestone reconciliation: **PR-1 through PR-6 all implemented.** PR-3H (hardening extension) remains planned post-merge.

> Authoritative maturity on merge: **1.0.0, Stable**.

---

## CI Gating

Review the CI gating policy: [`docs/governance/ci-gating.md`](docs/governance/ci-gating.md).
