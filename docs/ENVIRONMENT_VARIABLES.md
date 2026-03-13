# ADAAD Environment Variable Reference

This page catalogs `ADAAD_*` environment variables currently read by executable ADAAD code (`*.py`) and operational shell wrappers (`*.sh`) in this repository.

> Compatibility note: older historical docs may reference `ADAAD_AMENDMENT_TRIGGER_INTERVAL`; use `ADAAD_ROADMAP_AMENDMENT_TRIGGER_INTERVAL` for all current configuration and automation.

## Production-safety highlights

- **`ADAAD_METRICS_INCLUDE_FULL_TASKS`**: keep unset/false in production. Enabling it emits full dream task lists in metrics payloads, which increases telemetry volume and can leak sensitive agent identifiers. Use only for short-lived debugging.

- **`ADAAD_ROOT`**: pin this explicitly in production service units to a trusted, immutable deployment root. Mis-pointing it can make maintenance jobs execute against the wrong tree or data directory.

- **`ADAAD_FEDERATION_HMAC_KEY`**: required when federation is enabled. The platform boot-halts fail-closed if this is absent or below minimum length. Supply via a secret manager in every federation-enabled deployment.

- Secrets (`*_KEY*`, `*_TOKEN*`, `*_SECRET*`) should come from a secret manager, not checked-in env files.

- Boolean flags in ADAAD generally treat `1/true/yes/on` as enabled; any other value is treated as disabled unless code documents a stricter parser.


## Scope legend

- **application orchestration (app)**: boot orchestration, dream/beast cycles, runtime gates.

- **runtime/governance engine**: policy enforcement, sandboxing, federation, replay, and metrics internals.

- **agent/orchestrator packages**: agent mutation/orchestration helpers.

- **security/cryptographic controls**: signing/verifier controls.

- **ops wrappers/systemd jobs** and **ops/verification scripts**: operational commands and validation tools.


## Variable catalog

| Variable | Default | Allowed values | Environment scope | Primary source |
|---|---|---|---|---|
| `ADAAD_AI_STRATEGY_CONTEXT` | `'mutation_cycle'` | string/JSON per caller contract | agent/orchestrator packages | `adaad/agents/mutation_strategies.py` |
| `ADAAD_AI_STRATEGY_GOAL` | `'Improve agent fitness while preserving stability'` | string/JSON per caller contract | agent/orchestrator packages | `adaad/agents/mutation_strategies.py` |
| `ADAAD_AI_STRATEGY_PERSIST_HINTS` | `''` | string/JSON per caller contract | agent/orchestrator packages | `adaad/agents/mutation_strategies.py` |
| `ADAAD_ALLOW_GENESIS` | `'0'` | boolean-like: `1|true|yes|on` enables | security/cryptographic controls | `security/cryovant.py` |
| `ADAAD_ANTHROPIC_API_KEY` | `unset` | secret string; required in secured deployments | runtime/governance engine | `runtime/intelligence/llm_provider.py` |
| `ADAAD_AUDIT_DEV_TOKEN` | `unset` | secret string; required in secured deployments | API server surface | `server.py` |
| `ADAAD_AUDIT_MTLS_SCOPE` | `unset` | string/JSON per caller contract | API server surface | `server.py` |
| `ADAAD_AUDIT_TOKENS` | `unset` | secret string; required in secured deployments | API server surface | `server.py` |
| `ADAAD_AUTONOMY_THRESHOLD` | `'0.25'` | numeric string parsed as int/float | application orchestration (app) | `app/beast_mode_loop.py` |
| `ADAAD_BEAST_COOLDOWN_SEC` | `'300'` | numeric string parsed as int/float | application orchestration (app) | `app/beast_mode_loop.py` |
| `ADAAD_BEAST_CYCLE_BUDGET` | `'50'` | numeric string parsed as int/float | application orchestration (app) | `app/beast_mode_loop.py` |
| `ADAAD_BEAST_CYCLE_WINDOW_SEC` | `'3600'` | numeric string parsed as int/float | application orchestration (app) | `app/beast_mode_loop.py` |
| `ADAAD_BEAST_MUTATION_QUOTA` | `'25'` | numeric string parsed as int/float | application orchestration (app) | `app/beast_mode_loop.py` |
| `ADAAD_BEAST_MUTATION_WINDOW_SEC` | `'3600'` | numeric string parsed as int/float | application orchestration (app) | `app/beast_mode_loop.py` |
| `ADAAD_BEAST_STATE_LOCK_CONTENTION_SEC` | `'0.25'` | numeric string parsed as int/float | application orchestration (app) | `app/beast_mode_loop.py` |
| `ADAAD_BLOCKED_IMPORT_ROOTS` | `'core,engines,adad_core,ADAAD22'` | comma-separated import root list | runtime/governance engine | `runtime/import_guard.py` |
| `ADAAD_CONSTITUTION_VERSION` | `'', '0.2.0'` | string/JSON per caller contract | application orchestration (app) | `app/main.py` |
| `ADAAD_CONTAINER_HASH` | `'unavailable'` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/evidence_bundle.py` |
| `ADAAD_DEBUG_SIMULATION_INVARIANTS` | `''` | string/JSON per caller contract | application orchestration (app) | `app/main.py` |
| `ADAAD_DETERMINISTIC_LOCK` | `''` | boolean-like: `1|true|yes|on` enables | runtime/governance engine | `runtime/governance_surface.py` |
| `ADAAD_DETERMINISTIC_SEED` | `'adaad'` | string/JSON per caller contract | runtime/governance engine | `runtime/governance/foundation/determinism.py` |
| `ADAAD_DISPATCHER_VERSION` | `'v1'` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/evidence_bundle.py` |
| `ADAAD_DRY_RUN` | `''` | boolean-like: `1|true|yes|on` enables | application orchestration (app) | `app/main.py` |
| `ADAAD_DYNAMIC_AGENT_PRESSURE` | `'0.0'` | string/JSON per caller contract | runtime/governance engine | `runtime/platform/android_monitor.py` |
| `ADAAD_ENV` | **Required** — `dev`, `test`, `staging`, `production`, `prod` | Boot guard rejects unknown/unset values with `SystemExit`. For local dev: `export ADAAD_ENV=dev` | `app/main.py` boot guard | `quickstart.sh` |
| `ADAAD_EVIDENCE_BUNDLE_KEY_ID` | `'forensics-dev'` | string key selector. The resolver checks `ADAAD_EVIDENCE_BUNDLE_KEY_<KEY_ID>` first (uppercased, `-`→`_`), then `ADAAD_EVIDENCE_BUNDLE_SIGNING_KEY`; if neither is set export fails closed with `missing_export_signing_secret:<key_id>`. | runtime/governance engine | `runtime/evolution/evidence_bundle.py` |
| `ADAAD_EVIDENCE_BUNDLE_SIGNING_ALGO` | `unset` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/evidence_bundle.py` |
| `ADAAD_EVIDENCE_BUNDLE_SIGNING_KEY` | `'', unset` | secret string fallback for evidence export signing; required unless an env-specific `ADAAD_EVIDENCE_BUNDLE_KEY_<KEY_ID>` is configured. Missing keys fail closed deterministically. | runtime/governance engine | `runtime/evolution/evidence_bundle.py` |
| `ADAAD_FEDERATION_ENABLED` | `'false'` | boolean-like: `1|true|yes|on` enables | runtime/governance engine | `runtime/governance/federation/coordination.py` |
| `ADAAD_FEDERATION_HMAC_KEY` | `unset` | secret string; **required** when `ADAAD_FEDERATION_ENABLED=true`. Minimum length enforced at boot; absent or undersized key raises `FederationKeyError` (fail-closed). Must be sourced from a secret manager. | runtime/governance engine | `runtime/governance/federation/key_registry.py` |
| `ADAAD_FEDERATION_LOCK_TTL` | `'120'` | numeric string parsed as int/float | runtime/governance engine | `runtime/governance/federation/coordination.py` |
| `ADAAD_FEDERATION_MANIFEST_TTL` | `'300'` | numeric string parsed as int/float | runtime/governance engine | `runtime/governance/federation/coordination.py` |
| `ADAAD_FITNESS_CACHE_MAXSIZE` | `'2048'` | numeric string parsed as int/float | application orchestration (app) | `app/main.py` |
| `ADAAD_FITNESS_COVERAGE_BASELINE_PATH` | `unset` | filesystem path/list string | runtime/governance engine | `runtime/constitution.py` |
| `ADAAD_FITNESS_COVERAGE_POST_PATH` | `unset` | filesystem path/list string | runtime/governance engine | `runtime/constitution.py` |
| `ADAAD_FITNESS_SIMULATION_BUDGET_SECONDS` | `'0.25'` | numeric string parsed as int/float | application orchestration (app) | `app/main.py` |
| `ADAAD_FITNESS_THRESHOLD` | `'0.70'` | numeric string parsed as int/float | application orchestration (app) | `app/beast_mode_loop.py` |
| `ADAAD_FORCE_DETERMINISTIC_PROVIDER` | `''` | boolean-like: `1|true|yes|on` enables | runtime/governance engine | `runtime/governance/foundation/determinism.py` |
| `ADAAD_FORCE_TIER` | `unset` | enum string defined by caller | runtime/governance engine | `runtime/constitution.py` |
| `ADAAD_FORENSIC_EXPORT_SCOPE` | `unset` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/evidence_bundle.py` |
| `ADAAD_FORENSIC_RETENTION_DAYS` | `unset` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/evidence_bundle.py` |
| `ADAAD_GATE_HUMAN_OVERRIDE` | `''` | string/JSON per caller contract | application orchestration (app) | `app/main.py` |
| `ADAAD_GOVERNANCE_CI_MODE` | `''` | enum string defined by caller | application orchestration (app) | `app/main.py` |
| `ADAAD_GOVERNANCE_POLICY_PATHS` | `''` | filesystem path/list string | runtime/governance engine | `runtime/governance/policy_adapter.py` |
| `ADAAD_GOVERNOR_ENTROPY_BUDGET` | `unset` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/governor.py` |
| `ADAAD_GOVERNOR_VERSION` | `'3.0.0'` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/evidence_bundle.py` |
| `ADAAD_KEY_ROTATION_FILE` | `'security/keys/rotation.json'` | filesystem path/list string | ops/verification scripts | `scripts/validate_key_rotation_attestation.py` |
| `ADAAD_KEY_ROTATION_MAX_AGE_DAYS` | `'90'` | integer string (`int(...)`); malformed values fail closed via `invalid_key_rotation_max_age_days` in governance gate | application orchestration (app) | `app/main.py` |
| `ADAAD_KEY_ROTATION_STATUS_FILE` | `'key_rotation_status.json'` | filesystem path/list string | ops/verification scripts | `scripts/validate_key_rotation_attestation.py` |
| `ADAAD_LIFECYCLE_DRY_RUN` | `''` | boolean-like: `1|true|yes|on` enables | application orchestration (app) | `app/mutation_executor.py` |
| `ADAAD_LINEAGE_PATH` | `''` | filesystem path/list string | runtime/governance engine | `runtime/metrics_analysis.py` |
| `ADAAD_LLM_FALLBACK_TO_NOOP` | `unset` | boolean-like: `1|true|yes|on` enables | runtime/governance engine | `runtime/intelligence/llm_provider.py` |
| `ADAAD_LLM_MAX_TOKENS` | `unset` | numeric string parsed as int/float | runtime/governance engine | `runtime/intelligence/llm_provider.py` |
| `ADAAD_LLM_MODEL` | `unset` | enum string defined by caller | runtime/governance engine | `runtime/intelligence/llm_provider.py` |
| `ADAAD_LLM_TIMEOUT_SECONDS` | `unset` | numeric string parsed as int/float | runtime/governance engine | `runtime/intelligence/llm_provider.py` |
| `ADAAD_LOCAL_PEER_ID` | `'local-node'` | string/JSON per caller contract | runtime/governance engine | `runtime/governance/federation/coherence_validator.py` |
| `ADAAD_MAX_COMPLEXITY_DELTA` | `'5'` | numeric string parsed as int/float | runtime/governance engine | `runtime/constitution.py` |
| `ADAAD_RESOURCE_CPU_SECONDS` | `'30'` | numeric string parsed as int/float; canonical resource limit (deprecated alias: `ADAAD_MAX_CPU_SECONDS`) | runtime/governance engine | `runtime/governance/validators/resource_bounds.py` |
| `ADAAD_MAX_EPOCH_ENTROPY_BITS` | `'4096'` | numeric string parsed as int/float | runtime/governance engine | `runtime/constitution.py` |
| `ADAAD_RESOURCE_MEMORY_MB` | `'512'` | numeric string parsed as int/float; canonical resource limit (deprecated alias: `ADAAD_MAX_MEMORY_MB`) | runtime/governance engine | `runtime/governance/validators/resource_bounds.py`, `runtime/sandbox/executor.py` |
| `ADAAD_MAX_MUTATIONS_PER_HOUR` | `'60'` | numeric string parsed as int/float | UI/API helpers | `ui/aponi_dashboard.py` |
| `ADAAD_MAX_MUTATION_ENTROPY_BITS` | `'128'` | numeric string parsed as int/float | runtime/governance engine | `runtime/constitution.py` |
| `ADAAD_RESOURCE_WALL_SECONDS` | `'30'` | numeric string parsed as int/float; canonical resource limit (deprecated alias: `ADAAD_MAX_WALL_SECONDS`) | runtime/governance engine | `runtime/governance/validators/resource_bounds.py` |
| `ADAAD_MCP_JWT_SECRET` | `''` | numeric string parsed as int/float | runtime/governance engine | `runtime/mcp/server.py` |
| `ADAAD_MODEL_ID` | `'unknown_model'` | enum string defined by caller | runtime/governance engine | `runtime/evolution/baseline.py` |
| `ADAAD_MUTATION_EMA_ALPHA` | `'0.3'` | numeric string parsed as int/float | agent/orchestrator packages | `adaad/agents/mutation_engine.py` |
| `ADAAD_MUTATION_EXPLORATION_RATE` | `'0.1'` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/governor.py` |
| `ADAAD_MUTATION_EXPLORATION_STEP` | `'0.05'` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/governor.py` |
| `ADAAD_MUTATION_LOW_IMPACT_THRESHOLD` | `'0.3'` | numeric string parsed as int/float | agent/orchestrator packages | `adaad/agents/mutation_engine.py` |
| `ADAAD_MUTATION_MAX_EXPLORATION` | `'0.5'` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/governor.py` |
| `ADAAD_MUTATION_MIN_EXPLORATION` | `'0.0'` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/governor.py` |
| `ADAAD_MUTATION_MIN_ROI` | `'0.1'` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/governor.py` |
| `ADAAD_MUTATION_PER_CYCLE_BUDGET` | `'100'` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/governor.py` |
| `ADAAD_MUTATION_PER_EPOCH_BUDGET` | `'10000'` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/governor.py` |
| `ADAAD_MUTATION_RATE_WINDOW_SEC` | `'3600', unset` | numeric string parsed as int/float | runtime/governance engine | `runtime/constitution.py` |
| `ADAAD_MUTATION_SAMPLE_SIZE` | `'1'` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/baseline.py` |
| `ADAAD_MUTATION_SAMPLING_STRATEGY` | `'default'` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/baseline.py` |
| `ADAAD_MUTATION_SKILL_WEIGHT_COEF` | `'0.6'` | numeric string parsed as int/float | agent/orchestrator packages | `adaad/agents/mutation_engine.py` |
| `ADAAD_MUTATION_TEMPERATURE` | `'0.0'` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/baseline.py` |
| `ADAAD_MUTATION_TOP_P` | `'1.0'` | numeric string parsed as int/float | runtime/governance engine | `runtime/evolution/baseline.py` |
| `ADAAD_POLICY_ARTIFACT_SIGNING_KEY` | `unset` | secret string; required in secured deployments | ops/verification scripts | `scripts/sign_policy_artifact.sh` |
| `ADAAD_POLICY_SIGNER_KEY_ID` | `unset` | secret string; required in secured deployments | ops/verification scripts | `scripts/sign_policy_artifact.sh` |
| `ADAAD_POLICY_VERSION` | `'local'` | string/JSON per caller contract | runtime/governance engine | `runtime/governance/federation/coherence_validator.py` |
| `ADAAD_PROMPT_PACK_HASH` | `'sha256:unknown'` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/baseline.py` |
| `ADAAD_PROMPT_PACK_VERSION` | `'unknown_prompt_pack'` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/baseline.py` |
| `ADAAD_PROVIDER_ID` | `'unknown_provider'` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/baseline.py` |
| `ADAAD_RECOVERY_TIER` | `unset` | enum string defined by caller | agent/orchestrator packages | `adaad/orchestrator/dispatcher.py` |
| `ADAAD_REPLAY_MODE` | `'', 'audit', 'off', 'strict', unset` | enum string defined by caller; `strict` requires deterministic provider/seed | runtime/governance engine + agent/orchestrator packages | `runtime/governance/foundation/determinism.py`, `adaad/orchestrator/dispatcher.py` |
| `ADAAD_ROADMAP_AMENDMENT_TRIGGER_INTERVAL` | `'10'` | numeric string parsed as int; minimum number of successful epochs between roadmap amendment proposal emissions; value is read once at epoch start and held constant for the epoch duration — cannot be modified mid-epoch; values < 1 are rejected with `ValueError` at boot | runtime/evolution (Phase 6) | `runtime/evolution/evolution_loop.py` (M6-03 integration) |
| `ADAAD_REPLAY_PROOF_ALGO` | `unset` | string/JSON per caller contract; `ed25519` requires `nacl` and fails closed if unavailable unless explicit downgrade is allowed | runtime/governance engine | `runtime/evolution/replay_attestation.py` |
| `ADAAD_REPLAY_PROOF_ALLOW_ED25519_DOWNGRADE` | `unset` | boolean-like: `1|true|yes|on` enables explicit downgrade from requested `ed25519` to `hmac-sha256` when `nacl` is unavailable (no silent downgrade) | runtime/governance engine | `runtime/evolution/replay_attestation.py` |
| `ADAAD_REPLAY_PROOF_KEYRING_PATH` | `unset` | secret string; required in secured deployments | runtime/governance engine | `runtime/evolution/replay_attestation.py` |
| `ADAAD_REPLAY_PROOF_KEY_ID` | `'replay-proof-dev'` | secret string; required in secured deployments | runtime/governance engine | `runtime/evolution/replay_attestation.py` |
| `ADAAD_ROOT` | `repo root (code), ${DEFAULT_ROOT} (ops wrappers)` | filesystem path/list string | agent/orchestrator packages | `adaad/core/root.py` |
| `ADAAD_RUNTIME_BUILD_HASH` | `'unavailable'` | string/JSON per caller contract | runtime/governance engine | `runtime/evolution/evidence_bundle.py` |
| `ADAAD_RUNTIME_IMPORT_GUARD` | `''` | boolean-like: `1|true|yes|on` enables | runtime/governance engine | `runtime/import_guard.py` |
| `ADAAD_SANDBOX_CONTAINER_IMAGE` | `unset` | string/JSON per caller contract | runtime/governance engine | `runtime/sandbox/executor.py` |
| `ADAAD_SANDBOX_CONTAINER_NETWORK_PROFILE` | `unset` | string/JSON per caller contract | runtime/governance engine | `runtime/sandbox/executor.py` |
| `ADAAD_SANDBOX_CONTAINER_RESOURCE_PROFILE` | `unset` | string/JSON per caller contract | runtime/governance engine | `runtime/sandbox/executor.py` |
| `ADAAD_SANDBOX_CONTAINER_ROLLOUT` | `unset` | string/JSON per caller contract | runtime/governance engine | `runtime/sandbox/executor.py` |
| `ADAAD_SANDBOX_CONTAINER_RUNTIME_PROFILE` | `unset` | string/JSON per caller contract | runtime/governance engine | `runtime/sandbox/executor.py` |
| `ADAAD_SANDBOX_CONTAINER_SECCOMP_PROFILE` | `unset` | numeric string parsed as int/float | runtime/governance engine | `runtime/sandbox/executor.py` |
| `ADAAD_SANDBOX_CONTAINER_WRITE_PROFILE` | `unset` | string/JSON per caller contract | runtime/governance engine | `runtime/sandbox/executor.py` |
| `ADAAD_SANDBOX_TIMEOUT_SECONDS` | `'30', unset` | numeric string parsed as int/float | runtime/governance engine | `runtime/sandbox/executor.py` |
| `ADAAD_SEVERITY_ESCALATIONS` | `''` | string/JSON per caller contract | runtime/governance engine | `runtime/constitution.py` |
| `ADAAD_SIMULATION_ALLOW_UNSUPPORTED_DNA_DEEPCOPY` | `''` | boolean-like: `1|true|yes|on` enables **only when `CRYOVANT_DEV_MODE` is also enabled**; otherwise unsupported DNA types fail-closed | application orchestration (app) | `app/simulation_utils.py` |
| `ADAAD_SOULBOUND_KEY` | `unset` | hex-encoded string; **required** when Soulbound Context Ledger is active (Phase 9+). Minimum 32 bytes / 64 hex chars. Absent or malformed value raises `SoulboundKeyError` (fail-closed). Must be sourced from a secret manager in all non-dev deployments. Generate a dev key: `python -c "import secrets; print(secrets.token_hex(32))"` | runtime/memory (Phase 9) | `runtime/memory/soulbound_key.py` |
| `ADAAD_SOVEREIGN_MODE` | `''` | enum string defined by caller | runtime/governance engine | `runtime/evolution/governor.py` |
| `ADAAD_STAGED_CONTENT_MAX_LEN` | `'10000'` | numeric string parsed as int/float | application orchestration (app) | `app/beast_mode_loop.py` |
| `ADAAD_TEST_SANDBOX_PREEXEC_DISABLED` | `unset` | boolean-like: `1|true|yes|on` enables | runtime/governance engine | `runtime/test_sandbox.py` |
| `ADAAD_TRUST_MODE` | `'dev'` | enum string defined by caller | application orchestration (app) | `app/main.py` |
| `ADAAD_UI_MOCKS` | `''` | boolean-like: `1|true|yes|on` enables | API server surface | `server.py` |
