# Codex Setup for ADAAD Governed Build Agent

This runbook provides the discovery path and installation checklist for enabling
Codex with the ADAAD governed build-agent contract.

## Alignment objective

Codex setup is considered aligned only when the following stay synchronized:

1. Trigger/authorization contract in `AGENTS.md`.
2. Governance authority hierarchy and gate taxonomy used by active build sessions.
3. Evidence production expectations in `docs/comms/claims_evidence_matrix.md`.
4. Session-state lifecycle requirements for `.adaad_agent_state.json`.

## Source-of-truth files

- Agent contract: `AGENTS.md` (repository root).
- Strategic build model: `docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md`.
- Lane ownership register: `docs/governance/LANE_OWNERSHIP.md`.
- CI tier classifier: `docs/governance/ci-gating.md`.

## System prompt location policy

The full Codex system prompt content may be maintained outside this repository
(for example in a Codex admin console or private operator runbook).

When prompt text is maintained outside git, this file is the required discovery
entry point and must document:

1. where the authoritative prompt is stored,
2. who can update it,
3. when it was last synchronized with `AGENTS.md`.

## Installation checklist (current agent-state schema alignment)

- [ ] `AGENTS.md` is present at repository root and matches current governed contract semantics.
- [ ] Codex has read access to the full ADAAD repository tree.
- [ ] `.adaad_agent_state.json` is ignored via `.gitignore`.
- [ ] `python scripts/validate_adaad_agent_state.py` passes before session actions.
- [ ] `.adaad_agent_state.json` is registered in `docs/DIAGRAM_OWNERSHIP.md` (owner: build-agent).
- [ ] `CONTRIBUTING.md` references `AGENTS.md` for governed build contributions.
- [ ] `.adaad_operator_contacts.json` (if used) is local-only and never committed.
- [ ] `docs/governance/LANE_OWNERSHIP.md` has current lane owners.
- [ ] First invocation test executed with `ADAAD status`.
- [ ] Second invocation test executed with `ADAAD preflight`.
- [ ] Third invocation test executed with `ADAAD`.

## Agent-state schema contract (canonical guidance)

### Canonical schema location

The canonical JSON Schema for `.adaad_agent_state.json` is maintained at:

- `docs/schemas/adaad_agent_state.schema.json`

Operational validator logic remains in `scripts/validate_adaad_agent_state.py`; the script and schema must evolve together so preflight behavior stays deterministic.

### Supported-version policy

The validator must run in one of two explicit governance modes:

1. **Strict latest (default)**
   - Accept only the current schema version.
   - Reject every older/newer unknown version fail-closed.
2. **Controlled allowlist (migration windows only)**
   - Accept only versions explicitly listed in a deterministic allowlist.
   - Require a documented removal date for legacy versions.

Never use open-ended version acceptance (for example prefix-only checks or semantic "greater-than" acceptance).

### Deterministic fail-closed examples

Expected validator outcomes (machine-readable and reproducible):

- **Unsupported version**

  ```text
  adaad_agent_state_validation:failed
  - schema_version:unsupported:<value>
  ```

- **Missing required keys**

  ```text
  adaad_agent_state_validation:failed
  - missing_keys:last_gate_results,pending_evidence_rows
  ```

- **Invalid tier status**

  ```text
  adaad_agent_state_validation:failed
  - last_gate_results.tier_2:invalid_status
  ```

The validator must return non-zero exit status for all three classes above.

### CI enforcement lane

Agent-state validator coverage is enforced in CI through:

- **Workflow:** `.github/workflows/ci.yml`
- **Job lane:** `full-test-suite`
- **Mechanism:** `PYTHONPATH=. pytest tests/ -q`, which includes `tests/test_validate_adaad_agent_state.py`

In addition, operators should keep the direct script call (`python scripts/validate_adaad_agent_state.py`) in local ADAAD preflight before any build actions.

## Ongoing synchronization checklist

Run this checklist whenever `AGENTS.md` workflow semantics change.

- [ ] This runbook reflects trigger variants (`status`, `preflight`, `verify`, `audit`, `retry`).
- [ ] Tier 0/1/2/3 gate definitions remain consistent with `AGENTS.md`.
- [ ] `docs/comms/claims_evidence_matrix.md` includes or updates a claim row for agent/governance-operability assertions.
- [ ] Required scripts/commands are documented with deterministic invocation examples.
- [ ] Session-start guard `python scripts/validate_adaad_agent_state.py` is included in local preflight.
- [ ] Canonical-path guidance remains consistent with `docs/ARCHITECTURE_CONTRACT.md`.

## Architecture snapshot drift remediation (builder workflow)

If Tier 0 preflight fails at `python scripts/validate_architecture_snapshot.py`
with `architecture snapshot metadata drift detected`, treat it as a **build-state
alignment issue** (not product behavior drift).

Required remediation sequence:

1. Refresh metadata in-place:

   ```bash
   python scripts/validate_architecture_snapshot.py --write
   ```

2. Stage the regenerated `docs/README_IMPLEMENTATION_ALIGNMENT.md` change in the
   same commit window **only when the script rewrites the file**.
3. Re-run Tier 0 preflight to confirm the repository is clean before any
   implementation file is touched.

Prevent recurrence by keeping the metadata block structure intact and re-running
`--write` only when report-version or metadata schema expectations change.

## Operator note

Changes to trigger contracts, gate order, workflow semantics, or tier taxonomy in
`AGENTS.md` should be followed by a Codex prompt synchronization check in the
same change window.


## Environment bootstrap (recommended before ADAAD preflight)

Preferred setup path (governed, end-to-end):

```bash
python onboard.py
```

Fallback (use only when `onboard.py` cannot run in your environment):

```bash
python -m pip install --upgrade pip
pip install -r requirements.server.txt
pip install -r requirements.dev.txt
python - <<'PY'
import importlib.util
assert importlib.util.find_spec("yaml") is not None, "PyYAML missing"
assert importlib.util.find_spec("nacl") is not None, "PyNaCl missing"
assert importlib.util.find_spec("cryptography") is not None, "cryptography missing"
assert importlib.util.find_spec("pytest_benchmark") is not None, "pytest-benchmark missing"
print("dependency bootstrap ok: runtime + test extras present")
PY
```

Then run Tier-0 preflight commands exactly as specified in `AGENTS.md`.

## Tier 0 remediation helper policy

Use `python scripts/tier0_remediation.py` to run Tier 0 gate verification and print deterministic next steps.

- The helper intentionally does **not** run `git checkout -b`, `git push`, or `gh pr create`.
- VCS network operations belong in a separate wrapper script.
- Optional local-only commit mode is available via `--local-commit` (no network).
- The helper always prints a deterministic commit message template for operator use.


## Replay proof signing key material setup

Replay proof key material is now fail-closed and must not be committed in `security/replay_proof_keyring.json`.

- Keep committed keyring entries metadata-only (`algorithm`, `public_key`, `*_ref` fields).
- Store local developer secrets in `security/replay_proof_keyring.local.json` (gitignored).
- For CI/production, mount secrets and set `ADAAD_REPLAY_PROOF_KEYRING_SECRET_PATH`.
- Environment overrides (`ADAAD_REPLAY_PROOF_HMAC_SECRET[_<KEY_ID>]`, `ADAAD_REPLAY_PROOF_PRIVATE_KEY[_<KEY_ID>]`) take highest precedence.
- Outside explicit dev/test mode, placeholder or missing secret values cause replay proof load to fail closed.

Run the guard before committing:

```bash
python scripts/check_replay_keyring_secrets.py
```
