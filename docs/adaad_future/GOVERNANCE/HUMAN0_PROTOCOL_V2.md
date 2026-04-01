# HUMAN-0 Authority Protocol v2

**Governor:** Dustin L. Reid  
**Organization:** InnovativeAI LLC  
**Protocol version:** 2.0  
**Effective from:** v9.32.0 (Phase 99)  
**Supersedes:** HUMAN-0 Protocol v1 (pre-Phase 94)

---

## What HUMAN-0 Is

HUMAN-0 is the constitutional authority layer of ADAAD. It is the mechanism by which a human being retains meaningful control over an autonomous code evolution system without blocking routine evolution.

HUMAN-0 is **not** a rubber stamp. It is a gate with specific triggering conditions, specific evidence requirements, and specific cryptographic attestation artifacts. A HUMAN-0 sign-off that doesn't meet these requirements is invalid.

HUMAN-0 is **not** delegable by default. The governor (Dustin L. Reid) is the named authority. Session-level delegation is permissible for Soft-class decisions only and must be explicitly declared at session start.

---

## HUMAN-0 Triggering Conditions

### Mandatory HUMAN-0 — cannot proceed without

| Condition | Evidence required |
|---|---|
| New phase launch (plan ratification) | Signed plan document, agent state updated |
| Pre-merge sign-off for any innovation phase | All tests green, gate stack summary, evidence matrix row |
| Release promotion (version tag) | ILA entry, CHANGELOG verified, VERSION aligned |
| New Hard-class invariant introduction | Invariant ID registered, test coverage verified |
| Constitutional amendment (new/modify/retire rule) | Amendment proposal, impact analysis, evidence |
| Governance bankruptcy discharge | Health ≥ target, clean epoch streak met, BANK-HUMAN-0 satisfied |
| Double-HUMAN-0 conditions (entropy budget ≥ 30%) | Two separate sign-off entries required |

### Advisory HUMAN-0 — system recommends, human decides

| Condition | Notes |
|---|---|
| Agent reputation balance ceiling exceeded | STAKE-HUMAN-0 advisory |
| New emergent role archetype discovered | ROLE-HUMAN-0 notification |
| New market signal source added | MCF signal trust review |
| Custom regulatory rule authorship | RCL-HUMAN-0 mandatory |
| Mirror Test calibration epoch triggered | SAI calibration review |

---

## Sign-Off Artifact Format

Every HUMAN-0 action produces a sign-off artifact. The canonical format:

```json
{
  "phase": 100,
  "innovation": "INNOV-15",
  "scope": "Agent Reputation Staking — 30/30 tests green — 4 STAKE invariants — v9.33.0 release",
  "governor": "DUSTIN L REID",
  "date": "2026-04-XX",
  "session_digest": "phase100-ars-impl-2026-04-XX",
  "attestation_ref": "ILA-100-2026-04-XX-001",
  "gate_results": {
    "tier_0": "pass",
    "tier_1": "pass",
    "tier_2": "pass",
    "tier_3": "pass"
  },
  "new_invariants": ["STAKE-0", "STAKE-DETERM-0", "STAKE-HUMAN-0", "STAKE-BURN-0"],
  "cumulative_invariants": 50,
  "test_count": 2774,
  "release_sha": "XXXXXXX",
  "release_tag": "v9.33.0"
}
```

---

## Identity Ledger Attestation (ILA) Format

The ILA is the permanent cryptographic record of the HUMAN-0 sign-off. It lives in `artifacts/governance/phaseNNN/identity_ledger_attestation.json`.

```json
{
  "schema_version": "2.0",
  "attestation_id": "ILA-100-2026-04-XX-001",
  "phase": 100,
  "governor": "DUSTIN L REID",
  "timestamp_utc": "2026-04-XXT00:00:00Z",
  "innovation": "INNOV-15",
  "innovation_name": "Agent Reputation Staking",
  "version_attested": "v9.33.0",
  "release_sha": "XXXXXXX",
  "test_count": 2774,
  "new_invariants": ["STAKE-0", "STAKE-DETERM-0", "STAKE-HUMAN-0", "STAKE-BURN-0"],
  "cumulative_hard_invariants": 50,
  "gate_results": {"tier_0": "pass", "tier_1": "pass", "tier_2": "pass", "tier_3": "pass"},
  "evidence_references": [
    "artifacts/governance/phase100/phase100_sign_off.json",
    "artifacts/governance/phase100/replay_digest.txt",
    "artifacts/governance/phase100/tier_summary.json"
  ],
  "claims_matrix_row": "phase100-innov15-ars-shipped",
  "attestation_digest": "sha256:XXXXXXXX"
}
```

---

## agent_state.json HUMAN-0 Entry Format

Every HUMAN-0 sign-off appends to the `human0_signoffs` array in `.adaad_agent_state.json`:

```json
{
  "date": "2026-04-XX",
  "governor": "DUSTIN L REID",
  "scope": "Phase 100 INNOV-15 Agent Reputation Staking — 30/30 tests — 4 invariants — v9.33.0",
  "session_digest": "phase100-ars-impl-2026-04-XX",
  "attestation_ref": "ILA-100-2026-04-XX-001"
}
```

---

## Double-HUMAN-0 Protocol

Triggered when Constitutional Entropy Budget (INNOV-26) detects drift ≥ 30%.

1. First HUMAN-0 sign-off: Amendment proposal reviewed and accepted in principle
2. 10-epoch cooling period enforced (no amendments accepted)
3. Second HUMAN-0 sign-off: Amendment executed after cooling period
4. Both sign-offs must appear in `human0_signoffs` array with `"double_human0": true`
5. `CEB-COOL-0` invariant enforces the cooling period computationally

---

## Session Delegation (Soft-class only)

At the start of a session, the governor may declare:

```
HUMAN-0 DELEGATION: [scope description]
Governor: Dustin L. Reid
Date: YYYY-MM-DD
Delegated authority: [SOFT-CLASS only / specific scope]
Expires: [session end / specific condition]
```

Delegation never extends to:
- New Hard-class invariant introduction
- Phase release promotion (version tagging)
- Constitutional amendments
- Governance bankruptcy discharge
- Any action requiring cryptographic sign-off

---

## Version Hygiene Gate (Enforced by CI)

Before any HUMAN-0 sign-off is accepted as valid, the CI version-hygiene job must confirm:

```
VERSION == pyproject.toml.version == CHANGELOG.md top entry version
```

Mismatch fails the CI gate and blocks the phase.

---

*Protocol authority: Dustin L. Reid, HUMAN-0, InnovativeAI LLC*  
*All HUMAN-0 records are permanent, append-only, and cryptographically linked*
