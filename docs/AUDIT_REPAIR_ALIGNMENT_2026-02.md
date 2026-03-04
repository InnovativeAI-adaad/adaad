# ADAAD Strategic Hardening Audit — February 2026

## Scope

This audit records code-grounded hardening actions applied after review feedback on the previous PR stack.

## Completed hardening actions

1. **Circular import hardening**
   - Converted runtime facade exports to lazy-loading surfaces:
     - `runtime/api/__init__.py`
     - `runtime/api/agents.py`
     - `runtime/evolution/__init__.py`
   - Result: reduced collection-time failures caused by runtime/api ↔ runtime/evolution ↔ app mutation engine dependency loops.

2. **Constitution policy loader resilience**
   - Added hermetic fallback parser when `yaml` package is unavailable (`runtime/constitution.py`).
   - Loader still prefers canonical JSON/YAML semantics and raises explicit parse errors on malformed input.

3. **Governance envelope determinism hardening**
   - Excluded volatile runtime telemetry counters/timestamps from governance envelope digest detail hashing (`runtime/constitution.py`).
   - Prevents digest drift across otherwise equivalent evaluations.

4. **Resource snapshot precedence correction**
   - `coalesce_resource_usage_snapshot(...)` now prioritizes explicit observed measurements and only uses telemetry as fallback (`runtime/governance/resource_accounting.py`).

5. **Evidence bundle resilience**
   - Added fail-closed fallback metadata behavior when governance policy artifact loading fails (`runtime/evolution/evidence_bundle.py`).

6. **Federation test gating for optional crypto dependency**
   - Security transport test now uses `pytest.importorskip("cryptography")` for hermetic environments (`runtime/governance/federation/tests/test_federation_transport_protocol_security.py`).

7. **Market adapter scoring precedence correction**
   - Fitness evaluator now prefers `market_adapter_output.scoring_inputs.simulated_market_score` over weaker fallback fields (`runtime/evolution/economic_fitness.py`).

## Validation commands

```bash
python -m py_compile runtime/constitution.py runtime/api/__init__.py runtime/api/agents.py runtime/api/app_layer.py runtime/evolution/__init__.py
pytest -q tests/test_constitution_policy.py tests/test_economic_fitness.py tests/evolution/test_evidence_bundle.py tests/test_intelligence_router.py tests/test_intelligence_proposal_adapter.py tests/test_orchestrator_dispatcher.py
pytest -q tests/determinism/test_boot_runtime_profile.py tests/determinism/test_concurrent_replay.py tests/test_tool_contract.py tests/test_mutation_transaction.py
```

## Remaining follow-up

- End-to-end full-suite execution still contains a small set of collection/runtime failures outside this hardening scope (notably some dream/mutation integration paths). These should be addressed in dedicated PRs tied to the intelligence/runtime integration epic.


## Additional repair slice (post-audit feedback)

8. **Strict replay DreamMode provider safety**
   - `app/dream_mode.py` now auto-selects `SeededDeterminismProvider` when `replay_mode="strict"` and no provider is injected.

9. **Policy artifact signature compatibility path**
   - `runtime/governance/policy_artifact.py` now verifies signatures through `cryovant.verify_payload_signature(...)` first (for compatibility with governance tests and signer metadata), then falls back to existing signature/dev/hmac checks.

10. **Checkpoint continuity compatibility**
   - `runtime/evolution/runtime.py` now treats `prior_checkpoint_missing` as deterministic `no_checkpoints` pass status (instead of hard failure) for replay harness epochs that have no checkpoint events.

11. **Import-root guard correction**
   - `tests/test_import_roots.py` regex fixed for module root parsing and approved root set updated for active project namespaces used in this repository (`adaad`, `server`, `nexus_setup`, optional `cryptography`).

12. **Determinism lint test fix**
   - `tests/test_lint_determinism.py` now imports `ast` required by existing hardened-path assertions.

Validation extension:

```bash
pytest -q tests/governance/test_policy_artifact.py tests/test_import_roots.py tests/determinism/test_replay_equivalence.py::test_dream_mutation_token_determinism tests/determinism/test_replay_runtime_harness.py tests/test_lint_determinism.py
```


13. **README + docs integrity guards**
   - Added `scripts/validate_readme_alignment.py` to enforce key implementation-status/configuration statements across root/module/release documentation.
   - Added `scripts/validate_docs_integrity.py` to scan all markdown files, validate local markdown links/image targets, and fail when image alt text is missing in markdown image syntax or HTML `<img>` tags.

Validation extension (documentation guards):

```bash
python scripts/validate_readme_alignment.py --format json
python scripts/validate_docs_integrity.py --format json
```
