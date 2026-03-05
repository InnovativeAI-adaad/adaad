# Contributing

By submitting a contribution, you agree that your work is licensed under the Apache License, Version 2.0 (see `LICENSE`). No trademark rights are granted or implied; see `TRADEMARKS.md` and `BRAND_LICENSE.md`.

## Development setup

1. Create and activate a virtual environment.
2. Install dependencies from `requirements.server.txt`.
3. Initialize local workspace with `python nexus_setup.py` and run `python nexus_setup.py --validate-only` (or `--validate-only --json` for machine-readable output).
4. Verify boot diagnostics with `python -m app.main --replay audit --verbose`.

## Branch naming

Use descriptive topic branches:

- `docs/<short-description>`
- `fix/<short-description>`
- `feat/<short-description>`
- `governance/<short-description>`

## §6 · Commit Message Convention

Commit messages for governed PR work should include structured trailers so reviewers
can audit intent and gate evidence quickly.

Required trailers:

- `PR-ID: <id>`
- `CI tier: <docs|low|standard|critical>`
- `Replay proof: <value>`

`Replay proof` is always required, but valid values depend on the `CI tier` field:

- `critical` tier: must include the strict replay output artifact hash
  (example format: `Replay proof: sha256:<hash>`).
- non-critical tiers (`docs`, `low`, `standard`): must be exactly
  `Replay proof: not-required`.

Reviewers should validate `Replay proof` against `CI tier` using
`docs/governance/ci-gating.md`.

Examples:

```text
feat(governance): enforce token_ok in gate certifier

PR-ID: PR-HARDEN-01
CI tier: critical
Replay proof: sha256:4f6b9f0c2d0f6e9f7fb9d4e35e8d7a2b8a5af1d4a7df6c2edc36f90bfed2ee11
```

```text
docs(governance): document federation key registry controls

PR-ID: PR-DOCS-01
CI tier: docs
Replay proof: not-required
```

## Governed build-agent contract

Contributor-facing governed automation behavior is defined in [`AGENTS.md`](AGENTS.md).
Review it before opening governance-impacting PRs so lane expectations, fail-closed behavior, and evidence requirements are applied consistently.

## Governance-impact labeling

If your change touches governance-critical surfaces (policy, replay, ledger, cryovant, mutation authorization), include `governance-impact` in your PR labels and describe risk in the PR body.

Governance-critical paths include (non-exhaustive):

- `runtime/constitution*`
- `runtime/evolution/*`
- `security/ledger/*`
- `security/cryovant.py`
- `app/mutation_executor.py`
- `app/main.py`

## Replay requirements for PR validation

At minimum for affected areas:

- Run replay audit mode during local validation.
- Governance-impact PRs must pass strict replay verification locally before submission.

Recommended commands:

```bash
python -m app.main --replay audit --verbose
python -m app.main --verify-replay --replay strict --verbose
```

## Test requirements

- Add tests for functional changes.
- Run targeted pytest suites for impacted modules.
- Do not merge changes with failing tests.

Example:

```bash
python -m pytest -q tests/test_preflight_import_smoke.py
```


## Canonical agent runtime namespace

`adaad.agents` is the canonical runtime namespace for agent implementation code.

- Import agent modules from `adaad.agents.*` in new code.
- `app.agents.*` exists only as a temporary compatibility shim during migration.
- CI import-lint gates reject newly introduced `app.agents.*` imports outside the shim package.

## Code expectations

- Follow existing code style and keep SPDX headers in source files.
- Keep dependencies documented and compatible with existing tooling.
- Avoid introducing nondeterministic behavior in governance paths.

## Security and telemetry hygiene

- Do **not** log secrets, credentials, tokens, or raw command lines containing sensitive values.
- Use allowlisted, minimal fields in metrics payloads.
- Keep JSONL entries single-line UTF-8 records for parseability.

## Starter example

- Run minimal single-agent loop: `python examples/single-agent-loop/run.py`.
- Read walkthrough: `examples/single-agent-loop/README.md`.


## Determinism guardrails

Do not introduce in governance-critical paths:

- random behavior without fixed seed
- time-based scoring or policy decisions
- environment-dependent policy evaluation
