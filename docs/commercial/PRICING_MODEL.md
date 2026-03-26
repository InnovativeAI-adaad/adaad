# ADAAD Commercial Pricing Model (Proposed)

## Positioning baseline

ADAAD is positioned as a governance-first autonomy platform where value is tied to verifiable controls (strict replay, fail-closed gates, append-only attestations) rather than generic "AI seat" access.

Evidence anchors:
- Tiered CI and mandatory baseline/critical gates: [`docs/governance/ci-gating.md`](../governance/ci-gating.md)
- Strict replay invariants and fail-closed behavior: [`docs/governance/STRICT_REPLAY_INVARIANTS.md`](../governance/STRICT_REPLAY_INVARIANTS.md)
- Determinism contract and replay CLI namespace: [`docs/governance/DETERMINISM_CONTRACT_SPEC.md`](../governance/DETERMINISM_CONTRACT_SPEC.md)
- Lifecycle attestation contract including `merge_attestation.v1`: [`docs/governance/ledger_event_contract.md`](../governance/ledger_event_contract.md)

---

## Model A — Seat-based (governed operator licensing)

Best for organizations with centralized platform teams.

### Packaging
- **Starter**: up to 10 seats (engineering + security reviewers)
- **Growth**: up to 50 seats (adds governance admin roles)
- **Enterprise**: 50+ seats (SSO/SCIM, premium support, dedicated onboarding)

### Metering unit
- Named seats with role classes:
  - `Operator` (run governance/replay workflows)
  - `Reviewer` (approvals, evidence signoff)
  - `Auditor` (read-only compliance evidence)

### Why buyers pay
- Codified gate enforcement and required checks lower manual governance overhead.
- Built-in evidence matrix and validator reduce release-attestation toil.

Supporting repository controls:
- Release evidence validator: [`scripts/validate_release_evidence.py`](../../scripts/validate_release_evidence.py)
- Critical artifact verifier: [`scripts/verify_critical_artifacts.py`](../../scripts/verify_critical_artifacts.py)

---

## Model B — Usage-based (governance execution consumption)

Best for teams with bursty activity and variable automation demand.

### Billable dimensions
- **Governance runs**: per full gate-stack run
- **Replay verifications**: per strict replay verification execution
- **Attestation bundle verifications**: per replay/attestation bundle verification

### Why this maps to product value
- Billing follows high-assurance operations that directly reduce merge/release risk.
- Unit economics are tied to objective artifacts, not subjective user activity.

Supporting repository controls:
- Replay verification flows and deterministic replay commands: [`app/main.py`](../../app/main.py), [`docs/governance/DETERMINISM_CONTRACT_SPEC.md`](../governance/DETERMINISM_CONTRACT_SPEC.md)
- Offline attestation bundle verification: [`tools/verify_replay_attestation_bundle.py`](../../tools/verify_replay_attestation_bundle.py)

---

## Model C — Hybrid (recommended)

Best default for commercial packaging.

### Proposed formula
- **Platform fee (seats)**: covers baseline governance access, support, and onboarding
- **Consumption overage (usage)**: governance/replay runs above plan thresholds

### Suggested rationale
- Predictable spend for finance teams (base seat component)
- Elasticity for heavy governance/release windows (usage component)
- Clean linkage between spend and auditable controls (replay + attestation + evidence)

---

## Commercial packaging guardrails

- Do **not** market unsupported claims; map each plan claim to repository evidence row(s) in [`docs/comms/claims_evidence_matrix.md`](../comms/claims_evidence_matrix.md).
- Keep pricing language aligned with constitutional fail-closed posture and replay guarantees.
- For enterprise procurement, include explicit references to:
  - CI gate policy: [`docs/governance/ci-gating.md`](../governance/ci-gating.md)
  - Replay invariants: [`docs/governance/STRICT_REPLAY_INVARIANTS.md`](../governance/STRICT_REPLAY_INVARIANTS.md)
  - Merge attestation event contract: [`docs/governance/ledger_event_contract.md`](../governance/ledger_event_contract.md)
