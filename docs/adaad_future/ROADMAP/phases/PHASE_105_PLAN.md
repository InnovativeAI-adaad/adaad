# Phase 105 Plan — INNOV-20: Constitutional Stress Testing

**Authority:** HUMAN-0 — Dustin L. Reid  
**Target version:** v9.38.0  
**Predecessor:** Phase 104 must be shipped  
**Tests:** T105-CST-01 through T105-CST-30 (30 required)

## Objective
Generates mutations calibrated to barely pass all constitutional rules. Finds constitutional gaps and feeds them to InvariantDiscoveryEngine. Makes the constitution adversarially robust.

## Scaffold Status
Module already scaffolded in `runtime/innovations30/`. This phase promotes it from scaffold to full constitutional implementation with Hard-class invariants.

## Gate Stack
- Tier 0: Preflight (version hygiene, import contracts)
- Tier 1: Full suite (all existing + 30 new T105 tests)
- Tier 2: Governance artifact validation, evidence matrix row
- Tier 3: CHANGELOG, ROADMAP, agent state update

## pytest.ini Mark
```
"phase105: Phase 105 INNOV-20 [Constitutional Stress Testing] (CST) tests"
```

## Evidence Artifacts
```
artifacts/governance/phase105/phase105_sign_off.json
artifacts/governance/phase105/replay_digest.txt
artifacts/governance/phase105/tier_summary.json
artifacts/governance/phase105/identity_ledger_attestation.json
```

## HUMAN-0 Checkpoints
1. Plan ratification — before branch opens
2. Pre-merge — all 30 tests green, gate stack clean
3. Release — signed ILA for v9.38.0

## Commit Format
`feat(phase105): INNOV-20 Constitutional Stress Testing (CST) v9.38.0`
