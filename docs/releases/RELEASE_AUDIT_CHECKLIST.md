# Release Audit Checklist

Use this checklist before approving any governed release state transition.

Canonical operator preflight checklist: [`docs/release/release_checklist.md`](../release/release_checklist.md).

## Core constitutional checks

- [ ] Deterministic replay confirmed
- [ ] CI governance gates passed
- [ ] Mutation lineage attached
- [ ] Constitution version locked
- [ ] Evidence bundle includes `scoring_algorithm_version`, `constitution_version`, `governor_version`, `fitness_weights_hash`, and `goal_graph_hash` provenance fields.
- [ ] Evidence matrix complete
- [ ] Tagged/release commit has matching release note in `docs/releases/<version>.md`
- [ ] Replay on two independent environments produces matching digest outputs
- [ ] Constitution checksum verified
- [ ] Evidence bundle reproducibility test completed
- [ ] Port canonicalization verification completed (Aponi constants)

## v1.1-GA closure controls (historical blocking baseline)

- [ ] 1.1 Auth contract enforcement merged and CI-green on release SHA
- [ ] 1.2 `verify_session()` call-site audit complete (no runtime/app usage)
- [ ] 1.3 CI hardening merged with enforced secret-scan branch protection
- [ ] 1.4 Release evidence matrix reconciled to strict gate logic
- [ ] 1.5 Governance gate deterministic refactor validated
- [ ] 1.6 Mutation risk scorer suite expanded (25+ deterministic cases)
- [ ] Key-rotation enforcement audit evidence attached

## Evidence pointers

- Replay and determinism: [`docs/DETERMINISM.md`](../DETERMINISM.md)
- Release evidence matrix: [`docs/comms/claims_evidence_matrix.md`](../comms/claims_evidence_matrix.md)
- Program PR procession (active): [`docs/governance/ADAAD_PR_PROCESSION_2026-03.md`](../governance/ADAAD_PR_PROCESSION_2026-03.md)
- Program roadmap (active): [`ROADMAP.md`](../../ROADMAP.md)
- v1.1-GA closure tracker (historical): [`docs/governance/ADAAD_7_GA_CLOSURE_TRACKER.md`](../governance/ADAAD_7_GA_CLOSURE_TRACKER.md)
- Mutation evidence schema: [`schemas/evidence_bundle.v1.json`](../../schemas/evidence_bundle.v1.json)
- Constitution contract: [`docs/CONSTITUTION.md`](../CONSTITUTION.md)
