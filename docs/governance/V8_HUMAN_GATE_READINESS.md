# V8 Human Gate Readiness Checklist

**Scope:** Constitutional gate readiness for v8 phases 59, 63, 64, and 65.  
**Source of truth:** `ROADMAP.md` and `docs/governance/ARCHITECT_SPEC_v8.0.0.md`.

## Machine-checkable status contract

Use only the following values in the `status` column:

- `NOT_STARTED`
- `IN_REVIEW`
- `READY_FOR_SIGNOFF`
- `SIGNED_OFF`
- `BLOCKED`

Validation regex (case-sensitive):

```regex
^(NOT_STARTED|IN_REVIEW|READY_FOR_SIGNOFF|SIGNED_OFF|BLOCKED)$
```

## Gate readiness checklist

| gate_id | phase | required_approver | required_evidence_artifact_path | acceptance_condition | status |
|---|---:|---|---|---|---|
| CAP-REGISTRY | 59 | HUMAN-0 | `artifacts/governance/phase59/capability_registry_review.json` | First 10 capability contracts reviewed; `bound_modules` correct; `governance_tags` verified. | NOT_STARTED |
| GATE-V2-RULES | 63 | HUMAN-0 (constitutional amendment) | `artifacts/governance/phase63/gate_v2_rules_signoff.json` | All 5 GovernanceGate v2 rules reviewed; exception token schema accepted; AST-COMPLEX-0 thresholds approved. | NOT_STARTED |
| CEL-DRY-RUN | 64 | HUMAN-0 | `artifacts/governance/phase64/cel_dry_run_attestation.json` | SANDBOX_ONLY dry-run results reviewed in Aponi; EpochEvidence ledger write verified; calibration accepted. | NOT_STARTED |
| MUTATION-TARGET | 65 | HUMAN-0 | `artifacts/governance/phase65/mutation_target_signoff.json` | Human selects and approves first mutation target in Aponi console; mutation diff reviewed; Class A or B classification confirmed. | NOT_STARTED |
| AUDIT-0 | 65 | AUDIT-0 approver | `artifacts/governance/phase65/v9_release_audit_report.json` | Full release audit completed with zero blocking findings for v9.0.0 release gate. | NOT_STARTED |
| REPLAY-0 | 65 | REPLAY-0 approver | `artifacts/governance/phase65/v9_replay_verification.json` | Replay verification passes on committed mutation SHA with no divergence. | NOT_STARTED |

## Phase 65 completion rule

Phase 65 is considered governance-ready only when all three rows are `SIGNED_OFF`:

- `MUTATION-TARGET`
- `AUDIT-0`
- `REPLAY-0`
