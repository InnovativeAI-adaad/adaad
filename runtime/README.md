# Earth (runtime) ![Stable](https://img.shields.io/badge/Runtime-Stable-2ea043)

The runtime element owns invariant checks, metrics, warm-pool infrastructure, capability registry, and root paths. It must initialize before any other element. All metrics and capability events are logged to `reports/metrics.jsonl` and persisted under `data/`.

> Runtime is the canonical governance and replay substrate for ADAAD boot and mutation control.
> It defines deterministic primitives, policy enforcement boundaries, and evidence/export contracts.
> Consumers should import runtime-native modules first, with adapters used only for compatibility.

> **Doc metadata:** Audience: Contributor / Auditor · Last validated release: `v1.0.0`

> ✅ **Do this:** Add governance/evolution logic under `runtime/*` and keep imports on canonical paths.
>
> ⚠️ **Caveat:** Compatibility adapters (`governance/*`) are legacy-facing shims and should not gain new business logic.
>
> 🚫 **Out of scope:** Do not introduce alternate runtime roots or duplicate governance implementation trees.

Runtime is the only authoritative implementation root for governance and replay.


## Canonical import paths ![Internal](https://img.shields.io/badge/Contract-Internal-blue)

<details>
<summary><strong>Core path ownership</strong></summary>

- Authoritative governance foundation modules live in `runtime/governance/foundation/`.
- Authoritative evolution governance helpers live in `runtime/evolution/` (`scoring.py`, `promotion_state_machine.py`, `checkpoint.py`).
- `governance/` at repo root is compatibility-only and must re-export runtime implementations rather than duplicate logic.

</details>

<details>
<summary><strong>Determinism and invariants</strong></summary>

Deterministic replay-sensitive entry points now consume a shared provider abstraction from `runtime/governance/foundation/determinism.py` for UTC clock access and ID/token generation.

- Epoch checkpoint registry/verifier: `runtime/evolution/checkpoint_registry.py`, `runtime/evolution/checkpoint_verifier.py`.
- Entropy enforcement primitives: `runtime/evolution/entropy_detector.py`, `runtime/evolution/entropy_policy.py` with declared+observed telemetry accounting and per-epoch durable entropy totals.
- Entropy observability helper: `runtime/evolution/telemetry_audit.py` (`get_epoch_entropy_breakdown`).
- Lineage replay integrity distinguishes verified replay digests (strict/production) from explicit unverified forensic digest recomputation (tamper analysis).
- Constitutional lineage continuity validates parent mutation IDs plus ancestor chains and emits deterministic `lineage_violation_detected` events before execution.
- Strict replay/audit determinism requires deterministic providers to preserve replay and forensic guarantees.
- Mutation transactions (`runtime/tools/mutation_tx.py`) derive replay-safe stable IDs from deterministic context labels and verify path/touched-file/metadata invariants before commit.
- Strict replay invariants reference: `docs/governance/STRICT_REPLAY_INVARIANTS.md` (digest policy, provider requirements, replay-equivalence guarantees).

</details>

<details>
<summary><strong>Security, federation, and evidence contracts</strong></summary>

- Hardened sandbox isolation primitives: `runtime/sandbox/{executor,policy,manifest,evidence,isolation,preflight}.py` with strict pre-exec enforcement preparation and fail-closed integrity events.
- Federation coordination primitives: `runtime/governance/federation/` for deterministic policy exchange, quorum/consensus recording, and governance precedence checks.
- Federation transport canonical messages include `policy_exchange`, `federation_vote`, and `replay_proof_bundle`, each requiring canonical JSON digest and deterministic Ed25519 signature validation.
- Deterministic promotion simulation runner: `runtime/evolution/simulation_runner.py` with CI entrypoint `scripts/run_simulation_runner.py`.
- Deterministic epoch-frozen fitness orchestration: `runtime/evolution/fitness_orchestrator.py` (`survival_only`/`hybrid`/`economic_full` regimes, epoch snapshot ledger emission, stable config hashing).
- Canon Law v1.0 YAML enforcement is wired through `runtime/governance/{canon_law.py,policy_validator.py,gate_certifier.py}` with deterministic escalation tiers and fail-closed defaults.
- Policy-driven privileged-operation governance adapter: `runtime/governance/policy_adapter.py` with orchestration gate `runtime/director.py`, baseline Rego policy at `governance/policies.rego`, deterministic decision audit records (`input_digest`, `policy_hash`, `decision`, `reason`) to metrics + journal evidence streams.
- Goal graph supports signed hot-reload via `GoalGraph.reload_goal_graph(...)` with Cryovant payload signature verification before activation.
- MCP proposal writer runtime: `runtime/mcp/` deterministic FastAPI endpoints and hash-linked queue append flow.
- Canonical governance event taxonomy/normalization: `runtime/governance/event_taxonomy.py`.
- Constitution resource governance + shared accounting: `runtime/governance/constitution.yaml`, `runtime/governance/resource_accounting.py`.
- Replay attestation bundles: `runtime/evolution/replay_attestation.py` (signed replay-proof exports + offline verification helpers).
- Forensic evidence bundles: `runtime/evolution/evidence_bundle.py` (`schemas/evidence_bundle.v1.json`), including pre-digest `governor_version`, `fitness_weights_hash`, and `goal_graph_hash` provenance anchors.
- Governance signing and operations guides: `docs/governance/POLICY_ARTIFACT_SIGNING_GUIDE.md`, `docs/governance/FORENSIC_BUNDLE_LIFECYCLE.md`, `docs/governance/FEDERATION_CONFLICT_RUNBOOK.md`, and founders-law model docs.

</details>


## Determinism and boundary enforcement

- Governance-critical paths (`runtime/governance/`, `runtime/evolution/`, `runtime/autonomy/`, `security/`) are enforced by `tools/lint_determinism.py` as a primary verification gate in `scripts/verify_core.py` and `scripts/verify_core.sh`.
- The determinism lint blocks dynamic execution/import primitives (`eval`, `exec`, `compile`, `__import__`, `importlib.import_module`) including importlib alias forms.
- Runtime import boundary blocking uses a PEP 451 `MetaPathFinder`/loader (`runtime/import_guard.py`) and is only activated in explicit strict/test contexts (`ADAAD_RUNTIME_IMPORT_GUARD=strict|test`, `ADAAD_REPLAY_MODE=strict`, or test execution), so normal runtime imports remain unaffected by default.


## Architecture ownership contract

- Canonical entrypoint: `app/main.py` (`python -m app.main`).
- `runtime/__init__.py` is an adapter-only root surface (`ROOT_DIR`, `REPO_ROOT`, import-guard install), not an orchestration layer.
- Import boundary checks are enforced by `tools/lint_import_paths.py` and must pass in CI.
- See `docs/ARCHITECTURE_CONTRACT.md` for strict layer ownership and forbidden import edges.


## Deterministic Guarantees

This runtime layer guarantees:

- Stable governance envelope hashing over canonical detail surfaces
- Replay/version validation comparisons strip ephemeral runtime fields via `runtime/governance_surface.py::strip_version_comparison_ephemerals` to prevent false divergence (e.g., `nonce`, `generated_at`, `run_id`).
- Replay-stable constitution loading with hermetic fallback behavior
- Environment-configurable and ledger-visible dispatcher latency configuration
