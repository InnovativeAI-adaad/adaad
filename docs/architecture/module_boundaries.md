# Module Boundaries and Dependency Directions

This document defines package-level responsibilities and allowed dependency directions for core ADAAD runtime modules.

## Boundary Graph (high level)

```
app/ (entrypoints)
  -> adaad/orchestrator/ (workflow coordination)
  -> runtime.api/* (stable runtime facade)
  -> security/* (validation + policy)

adaad/orchestrator/ (coordination)
  -> runtime/* (domain services + public adapters)
  -> security/* (token/session/governance checks)
  X  app/* (except CLI contract types explicitly passed in)
  X  ui/*
  X  infra internals (runtime.integrations.* internals, runtime.platform.* internals)

security/ (validation)
  -> runtime.metrics (telemetry only)
  -> security.ledger/*
  X  app/*
  X  ui/*

adapter layers (filesystem/network/integration)
  - filesystem adapters: provide deterministic I/O wrappers and snapshot/replay compatibility.
  - network adapters: isolate outbound protocol details from orchestrator domain logic.
  - integration adapters: map external APIs into internal contracts.
```

## Package Responsibilities

## `app/` — boot and runtime entrypoints

**Owns**
- CLI argument parsing and process-mode decisions.
- Boot lifecycle wiring and runtime startup sequencing.
- User/operator-facing orchestration state and reporting.

**Must import through**
- `runtime.api.*` facades (not runtime internals).
- `security.*` public validation entrypoints.
- `adaad.orchestrator.*` dispatcher/bootstrap interfaces.

## `security/` — token/session/governance validation

**Owns**
- Session token verification and governance token parsing.
- Signing-key material handling and signature verification.
- Governance validation invariants and evidence journaling hooks.

**Must not**
- Depend on `app/` entrypoint modules.
- Depend on UI modules.

## `adaad/orchestrator/` — workflow coordination

**Owns**
- Tool dispatch registration and deterministic invocation.
- Workflow-level status and remediation wiring.
- Orchestration contracts between runtime surfaces.

**Must not**
- Import `app.*` or `ui.*` modules.
- Import infra internals directly; integration goes via stable adapter/public interfaces.

## Adapter Layers — filesystem/network/integration interfaces

Adapters expose stable contracts and hide implementation detail from orchestration logic.

- Filesystem adapters isolate path layout, persistence shape, and deterministic read/write behavior.
- Network adapters isolate transport/auth/retry concerns.
- Integration adapters map external ecosystems (e.g., platform/tool APIs) to ADAAD domain contracts.

## Enforcement

`tools/lint_import_paths.py` enforces boundary violations, including:
- orchestration importing entrypoint/UI modules,
- runtime internals importing `app/*` directly,
- and orchestration importing infra internals (`runtime.integrations.*`, `runtime.platform.*`).
