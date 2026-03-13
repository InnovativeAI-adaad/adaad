## Description
Briefly describe the change and why it is needed.

## Type of change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactor / maintenance

## Governance impact
- [ ] No governance impact
- [ ] Changes policy/constitution behavior
- [ ] Changes replay or ledger behavior

## Invariant notes (required for mutation/governance logic changes)
If this PR touches mutation execution, governance gates, replay logic, or ledger
write paths, list every constitutional invariant affected and confirm it is preserved:

| Invariant ID | Rule | Status |
|---|---|---|
| _(e.g. GOV-SOLE-0)_ | _(GovernanceGate is the sole approval surface)_ | ✅ Preserved / ⚠️ Changed (explain) |

> Leave this table empty only if the "No governance impact" box is checked above.

## Migration notes (required for governed contract changes)
If this PR changes a public API, schema, governance policy, or replay contract,
document the migration path here. PRs that change governed contracts without
migration notes will be blocked at the Evidence lane gate.

- [ ] No governed contract changed
- [ ] Migration notes provided below:

_(Describe what changes, what breaks, and how consumers migrate.)_

## Testing
- [ ] Tests pass locally (`python -m pytest` or targeted suite)
- [ ] Replay verification checked (`python -m app.main --verify-replay --replay strict`)
- [ ] Manual validation completed
- [ ] New tests added (if applicable)

## Checklist
- [ ] Documentation updated (if applicable)
- [ ] CHANGELOG updated (if applicable)
- [ ] No secrets or sensitive data added

## Post-merge docs automation contract
- [ ] Post-merge docs automation contract satisfied (`scripts/validate_post_merge_doc_sync.py`)
- [ ] Contract artifact links included:
  - [ ] `ROADMAP.md` update link
  - [ ] `docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md` update link
  - [ ] `docs/releases/<version>.md` link
  - [ ] `docs/comms/claims_evidence_matrix.md` evidence row link

## CI gating
Review the CI gating policy: [`docs/governance/ci-gating.md`](../docs/governance/ci-gating.md).

## Phase 5 sequence reference (when applicable)
- [ ] If this PR targets Phase 5, IDs and dependencies align to canonical sequence: `PR-PHASE5-01` → `PR-PHASE5-02` → `PR-PHASE5-03` (`docs/governance/ADAAD_PR_PROCESSION_2026-03.md`).
