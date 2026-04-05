# Release Readiness Checklist

**Use before `git tag` and `git push origin vX.XX.0`.**  
All items must pass. HUMAN-0 reviews this list before authorizing the tag.

---

## Code Quality
- [ ] All 30 T(NNN) tests PASS: `pytest -m phaseNNN -v`
- [ ] Zero regressions: `pytest --tb=short -q` shows same pass count as pre-branch
- [ ] No import errors: `python3 -c "import runtime.innovations30.<module>"`
- [ ] `__all__` is defined and includes all public exports

## Version Hygiene (CI-enforced, also manual check)
- [ ] `VERSION` file contains new version: `cat VERSION`
- [ ] `pyproject.toml` version matches: `grep ^version pyproject.toml`
- [ ] `CHANGELOG.md` top entry version matches: `head -5 CHANGELOG.md`
- [ ] All three are identical

## Governance Artifacts
- [ ] `artifacts/governance/phaseNNN/phaseNNN_sign_off.json` exists and is valid JSON
- [ ] `artifacts/governance/phaseNNN/replay_digest.txt` exists
- [ ] `artifacts/governance/phaseNNN/tier_summary.json` exists with all `"pass"`
- [ ] `artifacts/governance/phaseNNN/identity_ledger_attestation.json` exists
- [ ] No `PLACEHOLDER` strings remain in any artifact

## Constitutional Invariants
- [ ] All new invariant IDs follow naming convention: `MODULE[-KEYWORD]-N`
- [ ] New invariants are documented in `GOVERNANCE/CONSTITUTIONAL_INVARIANT_REGISTRY.md`
- [ ] Invariant IDs are declared in module's `INVARIANTS` dict or docstring
- [ ] Each new invariant has at least one positive test and one negative test

## Documentation
- [ ] `CHANGELOG.md` entry includes: branch, HUMAN-0 gate, test count, evidence ref
- [ ] `ROADMAP.md` phase marked as shipped with version and date
- [ ] `docs/comms/claims_evidence_matrix.md` row added as `Complete`
- [ ] `docs/plans/PHASE_NNN_PLAN.md` exists (authored before phase started)

## Agent State
- [ ] `last_completed_phase` updated correctly
- [ ] `current_version`, `software_version`, `version` all updated to new version
- [ ] `phase` incremented to next phase number
- [ ] `next_pr` points to next phase
- [ ] `value_checkpoints_reached` includes at least 3 new phase checkpoints
- [ ] `human0_signoffs` array has new entry for this phase
- [ ] `completed_milestones` updated

## HUMAN-0 Pre-Merge Sign-Off
- [ ] HUMAN-0 has reviewed gate stack summary
- [ ] HUMAN-0 has declared: *"Phase NNN pre-merge approved. Proceed with merge."*
- [ ] HUMAN-0 sign-off recorded in agent_state `human0_signoffs`

## Merge
- [ ] Merge is `--no-ff`: `git merge --no-ff feat/phaseNNN-...`
- [ ] Merge commit message references phase, innovation, version, HUMAN-0
- [ ] Push to main successful

## Tag
- [ ] Tag created: `git tag -a vX.XX.0 -m "Phase NNN: INNOV-NN [Full Name]"`
- [ ] Tag pushed: `git push origin vX.XX.0`
- [ ] Tag visible on remote: `git ls-remote --tags origin | grep vX.XX.0`

## HUMAN-0 Release Sign-Off
- [ ] HUMAN-0 has reviewed the tag and ILA
- [ ] HUMAN-0 has declared: *"vX.XX.0 release authorized."*

---

**Release authorized when all items checked.**
