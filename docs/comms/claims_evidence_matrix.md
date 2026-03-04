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

## Completion standard

An entry is considered complete only when:

1. Status is exactly `Complete`.
2. Every markdown link in the evidence column resolves to a tracked file path under this repository.
3. Links are specific enough for reviewer verification (no placeholder text such as `TBD`, `TODO`, or `coming soon`).
