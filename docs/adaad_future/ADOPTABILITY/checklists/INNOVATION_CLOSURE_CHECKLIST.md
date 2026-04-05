# Innovation Closure Checklist

**Use when:** Declaring an innovation phase complete (post-merge, post-tag).  
All items verified before closing the phase in governance records.

## Implementation
- [ ] Scaffold promoted to full constitutional implementation
- [ ] All Hard-class invariants implemented with exception-raising violation path
- [ ] `INVARIANTS` dict defined in module with all invariant IDs and descriptions
- [ ] `__all__` export includes all public symbols
- [ ] `_load()` is fail-open (corrupt file does not raise, silently skips)
- [ ] `_persist()` uses append-only `Path.open('a')` pattern
- [ ] All digests use sha256 (not md5, not sha1)
- [ ] No datetime.now() in any replay-sensitive path (use epoch_id-derived seeds)
- [ ] CEL integration hook added at correct step

## Tests
- [ ] Exactly 30 tests in T(NNN)-(ABBR)-01 through T(NNN)-(ABBR)-30
- [ ] pytest.ini mark added: `"phaseNNN: Phase NNN INNOV-NN [Full Name] (ABBR) tests"`
- [ ] Happy path test exists
- [ ] Boundary enforcement test exists (min and max)
- [ ] Determinism test exists (identical inputs → identical outputs)
- [ ] Fail-open test exists (corrupt file gracefully handled)
- [ ] HUMAN-0 advisory/gate test exists where applicable
- [ ] All 30 pass: `pytest -m phaseNNN -v`
- [ ] Zero regressions in full suite

## Governance Artifacts
- [ ] `artifacts/governance/phaseNNN/phaseNNN_sign_off.json` — valid JSON, no PLACEHOLDER
- [ ] `artifacts/governance/phaseNNN/replay_digest.txt` — filled, includes inputs/outputs hash
- [ ] `artifacts/governance/phaseNNN/tier_summary.json` — all tiers `"pass"`
- [ ] `artifacts/governance/phaseNNN/identity_ledger_attestation.json` — ILA complete
- [ ] ILA attestation_id follows: `ILA-NNN-YYYY-MM-DD-001`

## Documentation
- [ ] `CHANGELOG.md` top entry complete with branch, gate, tests, evidence ref
- [ ] `ROADMAP.md` phase marked `✅ shipped (vX.XX.0)` with date and evidence
- [ ] `docs/comms/claims_evidence_matrix.md` row: `phaseNNN-innovNN-abbr-shipped` = Complete
- [ ] `ADAAD_30_INNOVATIONS.md` innovation status updated to ✅ Shipped

## State
- [ ] `.adaad_agent_state.json` fully updated (all version fields, phase, next_pr)
- [ ] `human0_signoffs` array has new entry
- [ ] `completed_milestones` has phase-specific entries
- [ ] `value_checkpoints_reached` has ≥ 3 new entries

## Release
- [ ] Tag created and pushed: `vX.XX.0`
- [ ] Tag visible on remote: `git ls-remote --tags origin | grep vX.XX.0`
- [ ] HUMAN-0 release declaration recorded

## Final Verification
- [ ] `python3 -c "v=open('VERSION').read().strip(); ..."` version hygiene passes
- [ ] CI `ci-gating-summary` green on merge commit
- [ ] Next phase plan accessible: `docs/plans/PHASE_NNN+1_PLAN.md`
