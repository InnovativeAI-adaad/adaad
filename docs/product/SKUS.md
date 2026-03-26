# ADAAD SKU Offers

This document defines three productized ADAAD offers aligned to currently documented capabilities and contracts. It intentionally maps each commercial promise to implementation surfaces already described in the public docs.

## Community (Self-Hosted OSS)

**Included capabilities**
- Governance gate execution through the constitutional mutation path (including runtime-enforced constitutional rules).
- Replay attestations via deterministic replay modes (`audit` and `strict`) and hash-chained ledger workflows.
- Federation foundations available in the core architecture and roadmap lineage for governed multi-repo/federated mutation flows.

**Deployment model**
- Self-hosted from source or package install (`pip install adaad`) on Linux, macOS, Windows (WSL2), Docker, and Android-supported environments.

**Support tier**
- Community support (documentation, quickstart, and self-service validation commands).

**Target user persona**
- Individual builders, OSS contributors, researchers, and governance-first AI experimenters.

**Buyer value statement**
- Get full constitutional governance primitives and deterministic proof workflows without infrastructure lock-in, and run locally on commodity hardware.

---

## Team (Managed Cloud or Hosted Control Plane)

**Included capabilities**
- Everything in Community, plus team-operations workflows centered on governed execution and shared observability.
- Governance gate operations with hosted dashboard/control-plane access for live governance health, mutation history, and constitution-state visibility.
- Replay attestations run as managed jobs for repeatable environment-level verification in CI-style pipelines.
- Federation-ready operation patterns for organizations coordinating across services/repos under a unified governance policy.

**Deployment model**
- Managed cloud runtime or hosted control plane connected to customer execution environments.

**Support tier**
- Business support (SLA-backed incident response, onboarding guidance, and architecture enablement for governed rollout).

**Target user persona**
- Engineering managers, platform teams, and applied AI teams needing centralized governance without owning all platform operations.

**Buyer value statement**
- Accelerate governed AI delivery with lower operational burden while preserving deterministic replay evidence and constitutional controls.

---

## Enterprise (Private Deployment + Compliance Add-Ons)

**Included capabilities**
- Everything in Team, plus private deployment controls and compliance-oriented governance extensions.
- Governance gate hardening with strict enforcement of architecture boundaries, deterministic boot/runtime profile checks, and policy controls suitable for regulated SDLCs.
- Replay attestations with strict deterministic replay requirements and release-evidence validation gates to support audit programs.
- Federation capabilities for cross-node/cross-repo governance with explicit invariants and fail-closed enforcement behaviors.

**Deployment model**
- Private deployment (single-tenant VPC, on-prem, or controlled sovereign environment) with optional isolated control-plane patterns.

**Support tier**
- Enterprise support (named support channel, escalation matrix, change-management assistance, and compliance/readiness workshops).

**Target user persona**
- Security, compliance, and platform leadership in regulated or high-assurance organizations.

**Buyer value statement**
- Adopt autonomous evolution safely in regulated environments with private infrastructure, cryptographically grounded replay evidence, and compliance-tailored controls.

---

## Capability-to-Implementation Mapping Notes

- **Governance gate promises** map to documented constitutional gate behavior, runtime enforcement boundaries, and canonical execution flow.
- **Replay attestation promises** map to documented deterministic replay commands, replay modes, and strict boot/runtime deterministic requirements.
- **Federation promises** map to shipped federation phases and invariants documented in project governance/process artifacts.

If implementation surfaces evolve, this file should be updated in the same PR as the corresponding architecture/quickstart/readme updates.


## Source References

Capability claims above are derived from and constrained by:
- `README.md` (constitutional gate model, deterministic replay, ledger guarantees, supported run targets).
- `QUICKSTART.md` (onboarding flow, replay commands, dashboard/runtime operation, environment contract).
- `docs/ARCHITECTURE_CONTRACT.md` (layer ownership, canonical entrypoints, import-boundary and deterministic runtime contract).
