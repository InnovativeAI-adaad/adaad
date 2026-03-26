# ADAAD ROI Model (Evidence-Linked)

## ROI equation

Use a conservative model:

`Annual ROI = (Time Saved + Risk Reduced + Incident Avoidance) - Annual Platform Cost`

All inputs should be tied to measurable internal baselines and verifiable ADAAD controls.

---

## 1) Time saved

### Value driver
Reduce engineering/security time spent manually coordinating governance checks, replay validation, and release evidence collection.

### Calculation template
- `Hours saved per release = (legacy manual governance hours) - (ADAAD governance hours)`
- `Annual time value = Hours saved per release × releases per year × blended hourly rate`

### Evidence links
- Tiered and always-on CI gates to automate baseline governance checks: [`docs/governance/ci-gating.md`](../governance/ci-gating.md)
- Deterministic replay commands and structured outputs for reproducibility: [`docs/governance/DETERMINISM_CONTRACT_SPEC.md`](../governance/DETERMINISM_CONTRACT_SPEC.md)
- Evidence completeness automation: [`scripts/validate_release_evidence.py`](../../scripts/validate_release_evidence.py)

---

## 2) Risk reduced

### Value driver
Lower probability of shipping governance-breaking or non-reproducible changes.

### Calculation template
- `Risk reduction value = (baseline governance failure probability - ADAAD probability) × annual change volume × average impact per failure`

### Evidence links
- Strict replay fail-closed invariants: [`docs/governance/STRICT_REPLAY_INVARIANTS.md`](../governance/STRICT_REPLAY_INVARIANTS.md)
- Deterministic provider enforcement and replay safety contract: [`docs/governance/DETERMINISM_CONTRACT_SPEC.md`](../governance/DETERMINISM_CONTRACT_SPEC.md)
- Determinism lint/control automation: [`tools/lint_determinism.py`](../../tools/lint_determinism.py)

---

## 3) Incident avoidance

### Value driver
Reduce governance/security incidents through append-only lifecycle events and attestation discipline.

### Calculation template
- `Incident avoidance value = (baseline incidents/year - ADAAD incidents/year) × avg incident cost`
- Include direct costs (response hours, downtime) and indirect costs (audit friction, launch delay).

### Evidence links
- PR lifecycle event contract and required `merge_attestation.v1`: [`docs/governance/ledger_event_contract.md`](../governance/ledger_event_contract.md)
- Replay attestation bundle verification utility: [`tools/verify_replay_attestation_bundle.py`](../../tools/verify_replay_attestation_bundle.py)
- Claims-to-evidence gating for release readiness: [`docs/comms/claims_evidence_matrix.md`](../comms/claims_evidence_matrix.md)

---

## KPI starter pack for finance + security

Track quarterly:
- Median governance cycle time per PR
- Strict replay pass rate
- Evidence completeness pass rate
- Number of blocked merges due to governance/replay controls
- Governance/security incident count and MTTR

Reference control surfaces:
- CI gate map: [`docs/governance/ci-gating.md`](../governance/ci-gating.md)
- Governance KPI threshold policy: [`docs/governance/GOVERNANCE_KPI_THRESHOLDS.md`](../governance/GOVERNANCE_KPI_THRESHOLDS.md)

---

## Modeling guidance

- Use conservative assumptions in year 1.
- Separate **hard-dollar** savings (incident spend, engineering hours) from **risk-adjusted** savings.
- Re-baseline every quarter as throughput and release frequency evolve.
