# Phase 102 Plan — INNOV-17: Agent Post-Mortem Interviews

**Authority:** HUMAN-0 — Dustin L. Reid  
**Target version:** v9.35.0  
**Predecessor:** Phase 101 must be shipped  
**Tests:** T102-APM-01 through T102-APM-30 (30 required)

## Objective
Structured failure analysis interviews after every blocked proposal. Feeds InvariantDiscoveryEngine with failure pattern data. Closes the agent accountability loop.

## Scaffold Status
Module already scaffolded in `runtime/innovations30/`. This phase promotes it from scaffold to full constitutional implementation with Hard-class invariants.

## Gate Stack
- Tier 0: Preflight (version hygiene, import contracts)
- Tier 1: Full suite (all existing + 30 new T102 tests)
- Tier 2: Governance artifact validation, evidence matrix row
- Tier 3: CHANGELOG, ROADMAP, agent state update

## pytest.ini Mark
```
"phase102: Phase 102 INNOV-17 [Agent Post-Mortem Interviews] (APM) tests"
```

## Evidence Artifacts
```
artifacts/governance/phase102/phase102_sign_off.json
artifacts/governance/phase102/replay_digest.txt
artifacts/governance/phase102/tier_summary.json
artifacts/governance/phase102/identity_ledger_attestation.json
```

## HUMAN-0 Checkpoints
1. Plan ratification — before branch opens
2. Pre-merge — all 30 tests green, gate stack clean
3. Release — signed ILA for v9.35.0

## Commit Format
`feat(phase102): INNOV-17 Agent Post-Mortem Interviews (APM) v9.35.0`
