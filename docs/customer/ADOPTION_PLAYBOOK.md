# ADAAD Customer Adoption Playbook

This playbook provides a practical onboarding path from sandbox evaluation to production operation. Each phase maps to concrete repository artifacts, governance evidence expectations, and executable validation commands.

---

## Track 1: Technical onboarding (sandbox → production)

### Phase A — Sandbox validation (Week 0–1)

**Goal:** Prove installability, baseline governance behavior, and deterministic local execution.

**Primary artifacts to review**
- Environment and setup: [`docs/README.md`](../README.md), [`docs/ENVIRONMENT_VARIABLES.md`](../ENVIRONMENT_VARIABLES.md), [`docs/sandbox/README.md`](../sandbox/README.md)
- Governance model baseline: [`docs/CONSTITUTION.md`](../CONSTITUTION.md), [`docs/governance/ci-gating.md`](../governance/ci-gating.md)
- Determinism contract: [`docs/DETERMINISM.md`](../DETERMINISM.md), [`docs/governance/DETERMINISM_CONTRACT_SPEC.md`](../governance/DETERMINISM_CONTRACT_SPEC.md)

**Command checklist**
```bash
python scripts/validate_governance_schemas.py
python scripts/validate_architecture_snapshot.py
python tools/lint_determinism.py runtime/ security/ adaad/orchestrator/ app/main.py
python tools/lint_import_paths.py
PYTHONPATH=. pytest tests/determinism/ tests/recovery/test_tier_manager.py -k "not shared_epoch_parallel_validation_is_deterministic_in_strict_mode" -q
```

**Exit criteria**
- Tier 0 baseline gates pass locally with zero failures.
- Sandbox operators can run and interpret deterministic gate outputs.

---

### Phase B — Pre-production hardening (Week 2–4)

**Goal:** Validate full suite behavior and release evidence readiness for controlled rollout.

**Primary artifacts to review**
- Gate taxonomy and lane ownership: [`docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md`](../ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md), [`docs/governance/LANE_OWNERSHIP.md`](../governance/LANE_OWNERSHIP.md)
- Replay and fail-closed operations: [`docs/governance/STRICT_REPLAY_INVARIANTS.md`](../governance/STRICT_REPLAY_INVARIANTS.md), [`docs/governance/fail_closed_recovery_runbook.md`](../governance/fail_closed_recovery_runbook.md)
- Security controls: [`docs/SECURITY.md`](../SECURITY.md), [`docs/governance/SECURITY_INVARIANTS_MATRIX.md`](../governance/SECURITY_INVARIANTS_MATRIX.md)

**Command checklist**
```bash
PYTHONPATH=. pytest tests/ -q
PYTHONPATH=. pytest tests/ -k governance -q
python scripts/verify_critical_artifacts.py
python scripts/validate_readme_alignment.py
python scripts/validate_release_evidence.py --require-complete
```

**Exit criteria**
- No regressions across full test suite.
- Governance and critical artifact validation pass.
- Evidence validator reports complete release evidence rows.

---

### Phase C — Production promotion readiness (Week 4+)

**Goal:** Demonstrate replay safety, governance traceability, and production runbook fitness.

**Primary artifacts to review**
- Replay exchange and bundle lifecycle: [`docs/governance/REPLAY_PROOF_OF_LEGITIMACY_EXCHANGE.md`](../governance/REPLAY_PROOF_OF_LEGITIMACY_EXCHANGE.md), [`docs/governance/FORENSIC_BUNDLE_LIFECYCLE.md`](../governance/FORENSIC_BUNDLE_LIFECYCLE.md)
- Key and policy operations: [`docs/governance/KEY_CEREMONY_RUNBOOK_v1.md`](../governance/KEY_CEREMONY_RUNBOOK_v1.md), [`docs/governance/POLICY_ARTIFACT_SIGNING_GUIDE.md`](../governance/POLICY_ARTIFACT_SIGNING_GUIDE.md)
- Incident/alert readiness: [`docs/governance/APONI_ALERT_RUNBOOK.md`](../governance/APONI_ALERT_RUNBOOK.md), [`docs/governance/FEDERATION_CONFLICT_RUNBOOK.md`](../governance/FEDERATION_CONFLICT_RUNBOOK.md)

**Command checklist**
```bash
ADAAD_ENV=dev CRYOVANT_DEV_MODE=1 ADAAD_FORCE_DETERMINISTIC_PROVIDER=1 ADAAD_DETERMINISTIC_SEED=ci-strict-replay \
  PYTHONPATH=. python -m app.main --verify-replay --replay strict
python scripts/validate_release_evidence.py --require-complete
python scripts/verify_mutation_ledger.py
```

**Exit criteria**
- Strict replay passes with stable digest behavior.
- Ledger verification succeeds for the promoted candidate.
- Operations team confirms readiness against incident and key ceremony runbooks.

---

## Track 2: Security/compliance review checklist

Use this checklist in architecture/security review meetings and release go/no-go gates.

### Governance controls
- [ ] Confirm constitutional and architecture constraints are unchanged or intentionally amended with governance traceability.
  - References: [`docs/CONSTITUTION.md`](../CONSTITUTION.md), [`docs/ARCHITECTURE_CONTRACT.md`](../ARCHITECTURE_CONTRACT.md)
- [ ] Validate CI tier classification and required gate stack.
  - Reference: [`docs/governance/ci-gating.md`](../governance/ci-gating.md)
- [ ] Verify no invariant violations in security matrix.
  - Reference: [`docs/governance/SECURITY_INVARIANTS_MATRIX.md`](../governance/SECURITY_INVARIANTS_MATRIX.md)

### Cryptographic and policy controls
- [ ] Validate key-ceremony and key-rotation evidence.
  - References: [`docs/governance/KEY_CEREMONY_RUNBOOK_v1.md`](../governance/KEY_CEREMONY_RUNBOOK_v1.md), `python scripts/validate_key_rotation_attestation.py`
- [ ] Verify policy artifact signing flow is followed and reproducible.
  - References: [`docs/governance/POLICY_ARTIFACT_SIGNING_GUIDE.md`](../governance/POLICY_ARTIFACT_SIGNING_GUIDE.md), `scripts/sign_policy_artifact.sh`, `scripts/verify_policy_artifact.sh`

### Runtime safety and replay controls
- [ ] Run fail-closed and replay verification steps before release approval.
  - References: [`docs/governance/fail_closed_recovery_runbook.md`](../governance/fail_closed_recovery_runbook.md), [`docs/governance/STRICT_REPLAY_INVARIANTS.md`](../governance/STRICT_REPLAY_INVARIANTS.md)
- [ ] Validate forensic bundle integrity and retention requirements.
  - References: [`docs/governance/FORENSIC_BUNDLE_LIFECYCLE.md`](../governance/FORENSIC_BUNDLE_LIFECYCLE.md), `python scripts/enforce_forensic_retention.py`

### Evidence and auditability controls
- [ ] Ensure claims-evidence row is present and complete for each adoption phase.
  - References: [`docs/comms/claims_evidence_matrix.md`](../comms/claims_evidence_matrix.md), `python scripts/validate_release_evidence.py --require-complete`
- [ ] Run governance docs consistency and drift checks.
  - Commands: `python scripts/validate_governance_doc_consistency.py`, `python scripts/validate_governance_state_drift.py`

---

## Track 3: Value realization milestones + KPI templates

This section helps customer teams quantify onboarding progress and business value while preserving governance quality.

### Milestone map

| Milestone | Target window | Technical signal | Governance/evidence signal |
|---|---:|---|---|
| M1: Sandbox operational | Week 1 | Tier 0 gates passing on clean branch | Baseline entry in claims-evidence matrix |
| M2: Pre-prod confidence | Week 2–4 | Full suite + governance tests pass | Release evidence validator passes complete |
| M3: Production-ready | Week 4+ | Strict replay and ledger verification pass | Evidence row includes replay + artifact verification |
| M4: Steady-state optimization | Ongoing | Stable pass rate and low incident frequency | Periodic governance drift and KPI threshold review |

### KPI template (copy into internal scorecard)

| KPI | Definition | Formula / source | Target | Reporting cadence |
|---|---|---|---|---|
| Gate pass rate | Reliability of required validation gates | `passed_gates / total_gates` from CI and local run logs | ≥ 99% | Weekly |
| Mean time to governable release | Cycle time from branch cut to evidence-complete candidate | `release_ready_timestamp - branch_start_timestamp` | Decreasing trend | Bi-weekly |
| Replay integrity success | Deterministic replay success rate | `successful_strict_replays / attempted_strict_replays` | 100% | Per release |
| Evidence completeness SLA | Percent of releases with complete evidence rows | `complete_rows / release_rows` via `validate_release_evidence.py` | 100% | Per release |
| Security control adherence | Pass rate on security/compliance checklist items | `checked_items_passed / total_items` | 100% | Monthly |
| Time to incident containment | Speed of resolving governance/runtime incidents | `incident_closed - incident_opened` from runbook logs | Downward trend | Monthly |

### KPI capture commands and artifact links

```bash
python scripts/generate_governance_metrics_report.py
python scripts/validate_release_evidence.py --require-complete
python scripts/validate_governance_state_drift.py
```

- Threshold guidance: [`docs/governance/GOVERNANCE_KPI_THRESHOLDS.md`](../governance/GOVERNANCE_KPI_THRESHOLDS.md)
- Evidence of outcomes: [`docs/comms/claims_evidence_matrix.md`](../comms/claims_evidence_matrix.md)
- Release-level audit trail: [`docs/releases/RELEASE_AUDIT_CHECKLIST.md`](../releases/RELEASE_AUDIT_CHECKLIST.md)

---

## Recommended operating cadence

1. **Weekly**: run Tier 0 + KPI report commands, review deltas.
2. **Per release candidate**: run Tier 1 stack + strict replay + evidence completeness.
3. **Monthly governance review**: evaluate KPI thresholds, drift outputs, and security checklist closure.

This cadence keeps technical onboarding, compliance assurance, and value tracking aligned to the same repository-native proof artifacts.
