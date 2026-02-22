# Release Evidence Matrix (v0.70.0)

| Feature | Test | Artifact |
|---|---|---|
| Lineage continuity enforcement | `tests/test_lineage_continuity.py` | `security/ledger/lineage_v2.jsonl` |
| Resource bounds enforcement | `tests/test_resource_bounds.py` | Structured `resource_bounds_exceeded` + `resource_measurements_missing` constitutional events |
| Replay proof bundle | `tests/test_replay_proof.py` | `security/ledger/replay_proofs/*.json` |
| Replay tamper detection | `tests/test_replay_proof_tamper.py` | Offline verification output from `tools/verify_replay_bundle.py` |
| Sandbox hardening | `tests/sandbox/test_syscall_filter.py`, `tests/sandbox/test_fs_rules.py` | Sandbox evidence bundle snapshot/signature |
| Governance CI and branch protection | governance CI jobs and branch protection workflow | `.github/workflows/ci.yml`, `.github/workflows/branch_protection_check.yml` |

## Gate execution profile

- Release gate trigger: tag `v0.70.0`.
- Runtime verification: `tools/verify_replay_bundle.py` against `security/ledger/replay_proofs/*.json`.
- Test validation: governance and sandbox suites executed with `PYTHONPATH=.` to match CI import behavior.
