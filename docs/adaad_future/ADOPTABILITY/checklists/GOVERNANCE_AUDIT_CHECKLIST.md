# Governance Audit Checklist

**Frequency:** Quarterly (or before any major release milestone)  
**Authority:** HUMAN-0 — Dustin L. Reid

## Constitutional Integrity
- [ ] All Hard-class invariants in registry have corresponding tests
- [ ] No invariant has been silent for > 100 epochs (potential dead letter)
- [ ] Constitutional entropy drift < 0.20 (check INNOV-26 once shipped)
- [ ] Constitution.yaml hash matches expected genesis hash

## Governance Artifacts
- [ ] All shipped phases have complete artifact sets in `artifacts/governance/phaseNNN/`
- [ ] No PLACEHOLDER values in any artifact
- [ ] All ILA attestation_ids follow correct format
- [ ] SHA-256 digests verified for latest phase sign-off

## Agent State Integrity
- [ ] `VERSION` == `pyproject.toml version` == `CHANGELOG.md top entry`
- [ ] `current_version` == `software_version` == `version` in agent_state
- [ ] `phase` (int) == `last_completed_phase` phase number + 1
- [ ] `human0_signoffs` array is monotonically growing
- [ ] No FINDING with status `open` and severity P0 or P1

## Test Suite Health
- [ ] Test count ≥ expected minimum (30 × completed phases from 87 onward + base)
- [ ] Zero failing tests on main branch
- [ ] All phase marks in pytest.ini have corresponding test classes
- [ ] Import contract tests all pass

## Documentation Currency
- [ ] `ADAAD_30_INNOVATIONS.md` innovation statuses match shipped phases
- [ ] `ROADMAP.md` shipped phases all show ✅ with correct versions
- [ ] `docs/comms/claims_evidence_matrix.md` all shipped phases are Complete
- [ ] `docs/plans/PHASE_94_114_EXECUTION_MANIFEST.md` progress tracker updated

## LLM Provider Health
- [ ] Groq API key is valid and within rate limits
- [ ] Ollama local instance responsive (if in use)
- [ ] DorkEngine fallback tested within last 10 epochs
- [ ] No paid API dependencies introduced without HUMAN-0 authorization

## Findings Review
- [ ] All open findings reviewed and categorized
- [ ] No P0 findings older than 7 days
- [ ] No P1 findings older than 30 days
- [ ] All resolved findings have resolution date and evidence reference
