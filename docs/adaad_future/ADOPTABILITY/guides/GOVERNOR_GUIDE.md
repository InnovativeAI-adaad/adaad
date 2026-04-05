# HUMAN-0 Governor Guide

**For:** Dustin L. Reid (and any future authorized governor)  
**Role:** HUMAN-0 — final authority on all phase ratifications and releases

---

## Your Responsibilities

As HUMAN-0, you are the only person who can:
- Ratify a phase plan (authorize work to begin)
- Sign off on a pre-merge gate stack (authorize merge)
- Promote a release (authorize version tag)
- Introduce new Hard-class invariants
- Amend the constitution
- Discharge a governance bankruptcy

You cannot delegate any of these to the autonomous system. You cannot delegate them to a team member without explicit protocol. The system is designed to wait for you.

---

## Session Workflow

### Starting a Session

1. Check current state: `cat .adaad_agent_state.json | python3 -m json.tool`
2. Confirm the next phase: look for `next_pr` field
3. Confirm predecessor is shipped: `last_completed_phase` should match
4. Open the phase plan: `docs/plans/PHASE_NNN_PLAN.md`

### Ratifying a Phase Plan

Read the plan. If you approve:
1. Say: "Phase NNN plan ratified. Branch may open."
2. This triggers the agent to open the branch and begin implementation
3. Your ratification is recorded in `human0_signoffs` in agent_state

### Pre-Merge Sign-Off

After implementation completes:
1. Review test results: all 30 T<NNN> tests must be green
2. Review governance artifacts in `artifacts/governance/phaseNNN/`
3. Review CHANGELOG top entry
4. Review claims-evidence matrix row
5. If satisfied: "Phase NNN pre-merge approved. Proceed with merge."

### Release Sign-Off

After merge:
1. Verify version: `cat VERSION` matches `pyproject.toml` matches CHANGELOG
2. Review the ILA: `artifacts/governance/phaseNNN/identity_ledger_attestation.json`
3. Approve: "vX.XX.0 release authorized. Tag and push."

---

## Red Flags — Do Not Approve If

- Test count is below required (30 per phase)
- Any tier shows `fail` in tier_summary.json
- VERSION / pyproject.toml / CHANGELOG are not aligned
- Invariant IDs don't follow naming convention
- ILA attestation_digest is missing or `PLACEHOLDER`
- Claims-evidence matrix row is not `Complete`
- `next_pr` in agent_state doesn't point to the correct next phase

---

## Emergency Procedures

### Governance Bankruptcy (debt_score > 0.90)
1. Do not approve any new proposals
2. Review `data/bankruptcy_declarations.jsonl`
3. Activate RemediationAgent via: "Governance bankruptcy acknowledged. Remediation authorized."
4. Monitor health score over next 5 clean epochs
5. Discharge when health ≥ 0.65 and 5 clean streak: "Bankruptcy discharged. Proposal queue reopened."

### Mirror Test Failure (accuracy < 0.80)
1. Do not approve any new evolution cycles
2. Review `data/mirror_test_records.jsonl` for accuracy trends
3. Authorize calibration: "Constitutional calibration epoch authorized."
4. After calibration: re-run mirror test before resuming

### Constitutional Entropy Threshold (drift ≥ 30%)
1. Double-HUMAN-0 required for any amendment
2. First sign-off: "Amendment proposal accepted in principle. Cooling period begins."
3. Wait 10 epochs
4. Second sign-off: "Cooling period complete. Amendment authorized."
