# Formal Amendment Verification Scope (Bounded Model)

## Purpose

This document defines what the repository's formal amendment workflow model does and does **not** guarantee.

The executable model is implemented in `tools/formal/amendment_state_model.py` and exercised by
`tests/formal/test_amendment_state_model.py`.

## Modeled workflow states

The model uses a minimal state machine with these states:

- `proposal`
- `pending`
- `approved`
- `rejected`
- `federated`

These are intentionally compact abstractions for amendment lifecycle reasoning.

## Executable properties (formally checked)

The bounded model checker evaluates all action traces up to a fixed depth and enforces:

1. **`INVARIANT PHASE6-AUTH-0` / `Phase6-SEC-01`**
   - `authority_level` remains immutable as `"governor-review"`.
2. **`INVARIANT PHASE6-STORM-0` / `Phase6-SEC-09`**
   - At most one pending amendment exists (`pending_count <= 1`).
3. **`INVARIANT PHASE6-FED-0` / `Phase6-SEC-12`**
   - Source approval never binds destination node state.
4. **`INVARIANT PHASE6-HUMAN-0` / `Phase6-SEC-07`**
   - Approval state does not imply human sign-off token presence.

## CI enforcement

CI job: `amendment-formal-model-check` in `.github/workflows/ci.yml`.

The job runs on PRs that touch `runtime/`, `security/`, `governance/`, or amendment-specific
logic and executes:

- `PYTHONPATH=. python tools/formal/amendment_state_model.py`
- `PYTHONPATH=. pytest tests/formal/test_amendment_state_model.py -q`

## What is formally guaranteed vs test-guaranteed

### Formally guaranteed (bounded model)

- The abstract transition system preserves the four invariants above for all enumerated traces
  within the configured bound.
- Invariant regressions are machine-detected in CI for gated change surfaces.

### Test-guaranteed (implementation/runtime)

- Concrete runtime behavior in `runtime/autonomy/roadmap_amendment_engine.py` and federated
  broker code remains validated by unit/integration tests, not by this abstract model alone.
- Replay/ledger semantics, cryptographic checks, and I/O allowlist enforcement are covered by
  existing deterministic/governance test suites and policy gates.

## Limitations

- **Bounded exploration:** this is not unbounded theorem proving; guarantees are trace-depth-bounded.
- **Abstraction gap:** model fields are reduced and do not encode full runtime payload schemas.
- **Single-proposal focus:** model reasons about one proposal lifecycle with summarized counters.
- **No crypto proofing:** HMAC/signature correctness remains test/policy enforced, not modeled here.

Operators should treat this model as an additional safety net layered on top of deterministic
runtime tests and governance release gates.
