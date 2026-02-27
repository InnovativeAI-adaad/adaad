# Release Audit Checklist

Use this checklist before approving any governed release state transition.

- [ ] Deterministic replay confirmed
- [ ] CI governance gates passed
- [ ] Mutation lineage attached
- [ ] Constitution version locked
- [ ] Evidence bundle includes `scoring_algorithm_version` and `constitution_version` provenance fields.
- [ ] Evidence matrix complete

- [ ] Replay on two independent environments produces matching digest outputs
- [ ] Constitution checksum verified
- [ ] Evidence bundle reproducibility test completed
- [ ] Port canonicalization verification completed (Aponi constants)
## Evidence pointers

- Replay and determinism: [`docs/DETERMINISM.md`](../DETERMINISM.md)
- Release evidence matrix: [`docs/RELEASE_EVIDENCE_MATRIX.md`](../RELEASE_EVIDENCE_MATRIX.md)
- Mutation evidence schema: [`schemas/evidence_bundle.v1.json`](../../schemas/evidence_bundle.v1.json)
- Constitution contract: [`docs/CONSTITUTION.md`](../CONSTITUTION.md)
