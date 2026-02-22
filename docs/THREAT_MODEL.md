# Threat Model (v0.70.0)

## Scope
Governance-enforced mutation runtime, lineage ledger, replay proofs, and hardened sandbox execution.

## Primary threats
- **Lineage tampering:** forged ancestry or detached parent links.
- **Resource exhaustion:** unbounded CPU/memory/wall-time during mutation execution.
- **Replay forgery:** invalid proof bundles and tampered hashes.
- **Sandbox escape:** syscall and filesystem writes outside approved workspace.
- **Governance bypass:** merges without branch protection or required status checks.

## Mitigations
- Blocking lineage continuity validation at constitutional gate.
- Environment-configurable but deterministic resource caps and blocking exceptions.
- Canonical replay proof bundle generation + offline verifier.
- Linux-first sandbox hardening with syscall allowlist, workspace write constraints, and namespace capability checks.
- CI branch protection verification and release evidence gate.

## Residual risks / assumptions

- Branch-protection workflow requires repository/org Actions permissions that include `administration: read`.
- Sandbox snapshot in evidence bundles reflects export-time hardening policy capability; execution-time policy capture remains tracked for future hardening.
