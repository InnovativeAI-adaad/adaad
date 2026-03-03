# Release Evidence Matrix

This matrix is the release-facing evidence index for constitutional and security claims.

## Core governance guarantees

| Feature | Test / Verification | Artifact |
|---|---|---|
| Lineage continuity enforcement | `tests/test_lineage_continuity.py` | `security/ledger/lineage_v2.jsonl` |
| Resource bounds enforcement | `tests/test_resource_bounds.py` | Structured `resource_bounds_exceeded` + `resource_measurements_missing` constitutional events |
| Replay proof bundle | `tests/test_replay_proof.py` | `security/ledger/replay_proofs/*.json` |
| Replay tamper detection | `tests/test_replay_proof_tamper.py` | Offline verification output from `tools/verify_replay_bundle.py` |
| Sandbox hardening | `tests/sandbox/test_syscall_filter.py`, `tests/sandbox/test_fs_rules.py` | Sandbox evidence bundle snapshot/signature |
| Governance CI and branch protection | Governance CI jobs + secret scan + branch protection workflow checks | `.github/workflows/ci.yml`, `.github/workflows/secret_scan.yml`, `.github/workflows/branch_protection_check.yml` |
| PR-2 constitutional rule activation (lineage/resource/complexity/coverage/mutation rate) | `pytest tests/ -k "lineage or resource_bounds or complexity or mutation_rate" -q` | Constitutional policy v0.2.0 + validator/test evidence |

## v1.1-GA strict closure mapping (Phase 1)

| Step | Required outcome | Minimum evidence bundle |
|---|---|---|
| 1.1 auth contract enforcement | `GateCertifier.passed` uses `token_ok`, CI green on exact SHA | Merge SHA + CI run URL + reviewer attestation |
| 1.2 `verify_session()` call-site audit | Only approved test-only usage remains | Call-site inventory + security sign-off |
| 1.3 CI hardening merge | Secret scan workflow present and branch-protection-enforced | Workflow file path + branch rule export/screenshot |
| 1.4 evidence matrix alignment | Strict gate claims map 1:1 to tests/artifacts/owners | Matrix diff + governance sign-off note |
| 1.5 deterministic gate module | Gate outcomes are pure/replay-safe | Determinism proof + replay parity record |
| 1.6 mutation risk suite expansion | 25+ deterministic cases passing | Test summary + fixture list + CI run |

## Supporting hardening controls (required for enterprise readiness)

| Control | Verification expectation | Artifact |
|---|---|---|
| Key-rotation enforcement audit | Freshness policy and escalation posture validated | Rotation attestation + audit memo |
| Replay-proof trust-root hardening scope | Third-party verifier compatibility design approved | Scope document + schema/contract note |
| `/replay/diff` endpoint abuse hardening | Rate-limiting evidence under red-team scenario | Runtime config diff + endpoint test evidence |
| Sandbox timeout parity across backends | Fail-closed behavior shown for each backend path | Backend-by-backend evidence + runbook update |

## Gate execution profile

- Release gate trigger: governance/public-readiness tag pushes via `.github/workflows/governance_strict_release_gate.yml`.
- Runtime verification: `tools/verify_replay_bundle.py` against `security/ledger/replay_proofs/*.json`.
- Test validation: governance and sandbox suites executed with `PYTHONPATH=.` to match CI import behavior.

## Sandbox control-state semantics

- Telemetry syscall validation is implemented and fail-closed in executor evidence checks.
- In-kernel seccomp filtering is currently guaranteed only for container backend paths with configured Docker seccomp profiles.
- Namespace/cgroup hard isolation is currently reported as enabled only for container backend paths; process backend remains best-effort.
- Evidence bundles expose per-control capability flags (`enforced_in_kernel`, `best_effort`, `simulated_or_observed_only`) to prevent claim drift.
