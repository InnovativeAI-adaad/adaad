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
- [ ] Replay on two independent environments produces matching digest outputs
- [ ] Constitution checksum verified
- [ ] Evidence bundle reproducibility test completed
- [ ] Port canonicalization verification completed (Aponi constants)

## v1.1-GA closure controls (blocking)

- [ ] 1.1 Auth contract enforcement merged and CI-green on release SHA
- [ ] 1.2 `verify_session()` call-site audit complete (no runtime/app usage)
- [ ] 1.3 CI hardening merged with enforced secret-scan branch protection
- [ ] 1.4 Release evidence matrix reconciled to strict gate logic
- [ ] 1.5 Governance gate deterministic refactor validated
- [ ] 1.6 Mutation risk scorer suite expanded (25+ deterministic cases)
- [ ] Key-rotation enforcement audit evidence attached

## Evidence pointers

- Replay and determinism: [`docs/DETERMINISM.md`](../DETERMINISM.md)
- Release evidence matrix: [`docs/RELEASE_EVIDENCE_MATRIX.md`](../RELEASE_EVIDENCE_MATRIX.md)
- v1.1-GA closure tracker: [`docs/governance/ADAAD_7_GA_CLOSURE_TRACKER.md`](../governance/ADAAD_7_GA_CLOSURE_TRACKER.md)
- Mutation evidence schema: [`schemas/evidence_bundle.v1.json`](../../schemas/evidence_bundle.v1.json)
- Constitution contract: [`docs/CONSTITUTION.md`](../CONSTITUTION.md)
