# Developer Guide — Contributing to ADAAD

**Audience:** Developers who have been granted delegation by HUMAN-0 (Dustin L. Reid)

---

## The Golden Rules

1. **Never merge without HUMAN-0 sign-off.** No exceptions.
2. **Never skip the test count.** Every phase requires exactly 30 new tests.
3. **Ledger before state.** Every innovation that persists data must write the JSONL record before updating in-memory state (STAKE-0 pattern).
4. **Determinism is mandatory.** If a function takes identical inputs, it must produce identical outputs. No datetime.now() in replay paths.
5. **Fail-open everything.** Missing or corrupt persistence files are not errors — they are empty starting states.
6. **Free tier first.** No paid LLM API calls without HUMAN-0 authorization.
7. **Version hygiene always.** VERSION, pyproject.toml, and CHANGELOG top entry must agree.

---

## Understanding the Architecture

Read in this order:
1. `VISION/IDEAL_FUTURE_ADAAD.md` — what we're building toward
2. `ARCHITECTURE/ADAAD_V10_SYSTEM_DESIGN.md` — how it fits together
3. `GOVERNANCE/HUMAN0_PROTOCOL_V2.md` — how authority works
4. `GOVERNANCE/CONSTITUTIONAL_INVARIANT_REGISTRY.md` — what cannot be changed

---

## Before Writing Any Code

1. Confirm your phase is the current eligible phase (check `next_pr` in agent_state)
2. Read the phase plan: `docs/plans/PHASE_NNN_PLAN.md`
3. Read the scaffold: `runtime/innovations30/<module>.py`
4. Read the INNOV spec: `ROADMAP/innovations/INNOV_NN_SPEC.md` (if exists)
5. Get HUMAN-0 plan ratification before opening a branch

---

## The Invariant Pattern

Every new innovation module follows this pattern for its master invariant:

```python
# At the top of every method that satisfies the master invariant:
# INNOV-N-0: [description of what this invariant ensures]
self._persist(record)    # ← write first
self.in_memory = value   # ← then update
```

The `-0` invariant is sacred. It defines the module's core architectural promise.

---

## Test Naming

Tests follow strict naming:
```python
def test_T100_ARS_01_register_agent(self, tmp_path):
    """T100-ARS-01: [one sentence describing what this tests]."""
```

Format: `test_T{phase}_{ABBR}_{NN}_{snake_case_description}`

---

## Getting Help

- Phase plan: `docs/plans/PHASE_NNN_PLAN.md`
- Innovation spec: `ROADMAP/innovations/INNOV_NN_SPEC.md`
- Adoption recipe: `ADOPTABILITY/recipes/ADD_NEW_INNOVATION.md`
- Past phase examples: look at `runtime/innovations30/constitutional_jury.py` (most recent complete)
- Governance questions: `GOVERNANCE/HUMAN0_PROTOCOL_V2.md`
