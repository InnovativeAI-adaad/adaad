# Phase 104 Plan — INNOV-19: Governance Archaeology Mode

**Authority:** HUMAN-0 — Dustin L. Reid  
**Target version:** v9.37.0  
**Predecessor:** Phase 103 must be shipped  
**Tests:** T104-GAM-01 through T104-GAM-30 (30 required)

## Objective
Complete cryptographically-verified decision timeline reconstruction for any mutation from proposal to outcome. Every event carries a SHA-256 digest chain.

## Scaffold Status
Module already scaffolded in `runtime/innovations30/`. This phase promotes it from scaffold to full constitutional implementation with Hard-class invariants.

## Gate Stack
- Tier 0: Preflight (version hygiene, import contracts)
- Tier 1: Full suite (all existing + 30 new T104 tests)
- Tier 2: Governance artifact validation, evidence matrix row
- Tier 3: CHANGELOG, ROADMAP, agent state update

## pytest.ini Mark
```
"phase104: Phase 104 INNOV-19 [Governance Archaeology Mode] (GAM) tests"
```

## Evidence Artifacts
```
artifacts/governance/phase104/phase104_sign_off.json
artifacts/governance/phase104/replay_digest.txt
artifacts/governance/phase104/tier_summary.json
artifacts/governance/phase104/identity_ledger_attestation.json
```

## HUMAN-0 Checkpoints
1. Plan ratification — before branch opens
2. Pre-merge — all 30 tests green, gate stack clean
3. Release — signed ILA for v9.37.0

## Commit Format
`feat(phase104): INNOV-19 Governance Archaeology Mode (GAM) v9.37.0`
