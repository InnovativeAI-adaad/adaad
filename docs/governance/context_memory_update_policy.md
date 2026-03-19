# Context Memory Update Policy

`context/context.json` is the machine-readable orientation record for active phase state, governance references, lane ownership pointers, CI gates, and integration surfaces.

## Mandatory update triggers

Update `context/context.json` in the same PR when any of the following occur:

1. **Architecture or release-state transition**
   - `pyproject.toml` version changes
   - `docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md` `expected_active_phase` or `expected_next_pr` changes
2. **New integration point or integration contract change**
   - QR asset/registry path changes
   - Whale.Dic path or interface contract changes
   - service worker location or install contract changes
   - ledger event contract/path changes
3. **Governance lane or ownership mapping changes**
   - `docs/governance/LANE_OWNERSHIP.md` updates
   - module boundary moves that affect ownership references
4. **Gate or CI tier policy changes**
   - `docs/governance/ci-gating.md` tier semantics change
   - Tier 0/Tier 1/Tier 2 command contract changes
5. **Authority-chain or invariant updates**
   - updates to authoritative docs list
   - new, removed, or modified invariants used by governed automation

## Enforcement

CI validates context memory by running:

```bash
python scripts/validate_context_memory.py
```

Validation fails on schema drift, missing path references, or stale phase/version alignment with canonical sources.
