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

## Installation checklist (v1.1 alignment)

- [ ] `AGENTS.md` is present at repository root and matches v1.1.0 contract semantics.
- [ ] Codex has read access to the full ADAAD repository tree.
- [ ] `.adaad_agent_state.json` is ignored via `.gitignore`.
- [ ] `.adaad_agent_state.json` is registered in `docs/DIAGRAM_OWNERSHIP.md` (owner: build-agent).
- [ ] `CONTRIBUTING.md` references `AGENTS.md` for governed build contributions.
- [ ] `.adaad_operator_contacts.json` (if used) is local-only and never committed.
- [ ] `docs/governance/LANE_OWNERSHIP.md` has current lane owners.
- [ ] First invocation test executed with `ADAAD status`.
- [ ] Second invocation test executed with `ADAAD preflight`.
- [ ] Third invocation test executed with `ADAAD`.

## Ongoing synchronization checklist

Run this checklist whenever `AGENTS.md` workflow semantics change.

- [ ] This runbook reflects trigger variants (`status`, `preflight`, `verify`, `audit`, `retry`).
- [ ] Tier 0/1/2/3 gate definitions remain consistent with `AGENTS.md`.
- [ ] `docs/comms/claims_evidence_matrix.md` includes or updates a claim row for agent/governance-operability assertions.
- [ ] Required scripts/commands are documented with deterministic invocation examples.
- [ ] Canonical-path guidance remains consistent with `docs/ARCHITECTURE_CONTRACT.md`.

## Operator note

Changes to trigger contracts, gate order, workflow semantics, or tier taxonomy in
`AGENTS.md` should be followed by a Codex prompt synchronization check in the
same change window.
