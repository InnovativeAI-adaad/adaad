# Claims-to-Evidence Matrix

This matrix maps major external/public claims to objective, versioned repository artifacts. Release/governance announcements are blocked until every required entry is marked `Complete` with resolvable evidence links.

| Claim ID | External claim | Objective evidence artifacts (must resolve in-repo) | Status |
| --- | --- | --- | --- |
| `ci-status-requirements` | "All required CI checks pass before governance/public-readiness promotion." | [CI workflow definition](../../.github/workflows/ci.yml); [determinism lint workflow](../../.github/workflows/determinism_lint.yml) | Complete |
| `replay-proof-outputs` | "Replay behavior is reproducible and auditable." | [Replay audit boot CI check](../../.github/workflows/ci.yml#L89); [Determinism replay tests](../../tests/determinism/test_replay_equivalence.py) | Complete |
| `forensic-bundle-examples` | "Forensic artifacts are available for incident reconstruction." | [Aponi v2 forensics + health model](../governance/APONI_V2_FORENSICS_AND_HEALTH_MODEL.md); [Forensic bundle lifecycle](../governance/FORENSIC_BUNDLE_LIFECYCLE.md) | Complete |
| `codeql-status` | "CodeQL analysis status is published and enforceable." | [CodeQL workflow](../../.github/workflows/codeql.yml) | Complete |
| `versioned-docs-spec-links` | "Public claims are backed by versioned release/spec documentation." | [Versioned release notes (1.0.0)](../releases/1.0.0.md); [Governance schema versioning spec](../governance/schema_versioning_and_migration.md) | Complete |
| `stable-v1-maturity` | "ADAAD is stable for governed audit/replay workflows and staged mutation review." | [README project status + limitations](../../README.md); [1.0.0 release scope](../releases/1.0.0.md) | Complete |
| `deterministic-governance-primitives` | "Governance primitives are deterministic and test-backed." | [Determinism foundation module](../../runtime/governance/foundation/determinism.py); [determinism test suite](../../tests/determinism/test_scoring_algorithm_determinism.py) | Complete |
| `fail-closed-replay-enforcement` | "Replay divergence fail-closes execution." | [Replay runtime enforcement test](../../tests/determinism/test_replay_runtime_harness.py); [strict replay invariants spec](../governance/STRICT_REPLAY_INVARIANTS.md) | Complete |
| `append-only-ledger-lineage` | "Ledger and lineage integrity checks are enforced." | [Ledger guardian tests](../../tests/governance/test_ledger_guardian.py); [lineage integrity tests](../../tests/test_lineage_v2_integrity.py) | Complete |
| `replay-proof-bundle-verification` | "Replay proof bundles can be generated and verified." | [Replay proof runtime module](../../runtime/evolution/replay_proof.py); [replay proof verification tests](../../tests/test_replay_proof.py) | Complete |
| `federation-precedence-local-runtime` | "Federation coordination and precedence resolution are policy-gated in local runtime flows." | [Federation coordination runtime](../../runtime/governance/federation/coordination.py); [federation coordination tests](../../tests/governance/test_federation_coordination.py) | Complete |
| `cryovant-agent-cert-hmac` | "Agent certificate verification is payload-bound (HMAC/signature) with audited migration fallback." | [Cryovant certificate verifier](../../security/cryovant.py); [Cryovant signature tests](../../tests/test_cryovant_dev_signatures.py) | Complete |
| `codex-governed-build-alignment` | "Codex governed-build behavior is discoverable, gate-tiered, and aligned with ADAAD v1.1 governance docs." | [Agent contract](../../AGENTS.md); [Codex setup runbook](../governance/CODEX_SETUP.md); [CI tier classifier](../governance/ci-gating.md) | Complete |
| `governance-adapter-shim-verified` | "Root `governance/` is adapter-only; canonical implementation lives under `runtime/governance/`, and app-layer imports use `runtime.api.app_layer`." | [Import boundary lint](../../tools/lint_import_paths.py); [Adapter regression tests](../../tests/governance/test_runtime_governance_adapters.py); [Runtime canonical mutation ledger](../../runtime/governance/mutation_ledger.py); [Runtime canonical promotion gate](../../runtime/governance/promotion_gate.py) | Complete |
| `strict-replay-provider-enforcement` | "Strict replay mode never falls back to non-deterministic entropy providers for envelope generation." | [Determinism provider selection](../../runtime/governance/foundation/determinism.py); [AGM envelope enforcement](../../runtime/evolution/agm_event.py); [strict replay provider tests](../../tests/test_default_provider_strict_replay.py) | Complete |
| `architecture-snapshot-build-hygiene` | "Architecture snapshot metadata remains structurally valid and report-version aligned in the build lane before implementation edits proceed." | [Architecture snapshot validator](../../scripts/validate_architecture_snapshot.py); [Implementation alignment snapshot target](../README_IMPLEMENTATION_ALIGNMENT.md); [Codex setup remediation runbook](../governance/CODEX_SETUP.md) | Complete |
| `snapshot-atomicity` | "Ledger snapshots are staged atomically and latest valid recovery snapshot selection is sequence-ordered." | [Snapshot manager implementation](../../runtime/recovery/ledger_guardian.py); [Snapshot guardian tests](../../tests/governance/test_ledger_guardian.py) | Complete |
| `boot-env-validation` | "ADAAD rejects startup with unknown or misconfigured environment values; dev tokens and dev signatures are rejected in strict environments." | [Boot guard](../../app/main.py); [Cryovant env enforcement](../../security/cryovant.py); [Boot guard tests](../../tests/test_boot_env_validation.py); [Strict env tests](../../tests/test_cryovant_strict_env_rejection.py) | Complete |

| `federation-key-pinning` | "Federation messages are accepted only from registered, trusted key IDs; caller-supplied key substitution is rejected." | [Key registry loader](../../runtime/governance/federation/key_registry.py); [Transport enforcement](../../runtime/governance/federation/transport.py); [Registry file](../../governance/federation_trusted_keys.json); [Key registry tests](../../tests/governance/federation/test_federation_key_registry.py) | Complete |
| `sandbox-injection-hardening` | "Sandbox preflight blocks shell metacharacter injection, IFS word-splitting bypasses, shell evaluation primitives, and disallowed environment variables." | [Preflight implementation](../../runtime/sandbox/preflight.py); [Injection hardening tests](../../tests/test_sandbox_injection_hardening.py) | Complete |
| `spdx-header-compliance` | "All Python source files carry SPDX-License-Identifier headers, enforced in CI." | [SPDX check script](../../scripts/check_spdx_headers.py); [`ci.yml` `spdx-header-lint` job](../../.github/workflows/ci.yml) | Complete — CI enforced (PR-CI-02) |

## Completion standard

An entry is considered complete only when:

1. Status is exactly `Complete`.
2. Every markdown link in the evidence column resolves to a tracked file path under this repository.
3. Links are specific enough for reviewer verification (no placeholder text such as `TBD`, `TODO`, or `coming soon`).
