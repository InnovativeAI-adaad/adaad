# Phase 106 Plan — INNOV-21: Governance Debt Bankruptcy

**Authority:** HUMAN-0 — Dustin L. Reid  
**Target version:** v9.39.0  
**Predecessor:** Phase 105 must be shipped  
**Tests:** T106-GDB-01 through T106-GDB-30 (30 required)

## Objective
When governance debt_score exceeds 0.90: declare bankruptcy, suspend proposals, activate RemediationAgent. Discharge requires HUMAN-0 approval plus 5 clean epochs.

## Scaffold Status
Module already scaffolded in `runtime/innovations30/`. This phase promotes it from scaffold to full constitutional implementation with Hard-class invariants.

## Gate Stack
- Tier 0: Preflight (version hygiene, import contracts)
- Tier 1: Full suite (all existing + 30 new T106 tests)
- Tier 2: Governance artifact validation, evidence matrix row
- Tier 3: CHANGELOG, ROADMAP, agent state update

## pytest.ini Mark
```
"phase106: Phase 106 INNOV-21 [Governance Debt Bankruptcy] (GDB) tests"
```

## Evidence Artifacts
```
artifacts/governance/phase106/phase106_sign_off.json
artifacts/governance/phase106/replay_digest.txt
artifacts/governance/phase106/tier_summary.json
artifacts/governance/phase106/identity_ledger_attestation.json
```

## HUMAN-0 Checkpoints
1. Plan ratification — before branch opens
2. Pre-merge — all 30 tests green, gate stack clean
3. Release — signed ILA for v9.39.0

## Commit Format
`feat(phase106): INNOV-21 Governance Debt Bankruptcy (GDB) v9.39.0`
