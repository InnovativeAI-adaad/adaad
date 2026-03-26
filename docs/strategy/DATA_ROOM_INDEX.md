# DATA ROOM INDEX

**Version:** 1.0.0
**Last updated (UTC):** 2026-03-26
**Document owner:** Governance Program Office (GPO)
**Review cadence:** Monthly (first business week) + event-driven updates on every release candidate, security incident, or material architecture change.

## Purpose

This index is the canonical entry point for external and internal due-diligence reviews. It maps data-room content to repository sources, accountable owners, and refresh cadence.

## Versioning and Change Control

- **Versioning scheme:** Semantic (`MAJOR.MINOR.PATCH`).
  - **MAJOR:** structural redesign of index sections or owner model.
  - **MINOR:** new data-room sections, new artifact classes, or owner additions.
  - **PATCH:** path updates, wording clarifications, or cadence refinements.
- Every update to this index must be committed with the corresponding artifact/doc change when possible.
- If an artifact is not yet generated for a release window, mark status as `Planned` and include target path.

## Owner Mapping and Update Cadence

| Domain | Primary owner | Backup owner | Standard cadence | Event-driven triggers |
|---|---|---|---|---|
| Architecture and Security Documentation | Platform Architecture Lead | Security Engineering Lead | Monthly | Architecture boundary changes, new threat model, security control redesign |
| Dependency and SBOM Artifacts | Release Engineering Lead | Security Compliance Lead | Per release candidate + monthly baseline | Dependency baseline change, new third-party package, critical CVE response |
| Customer Reliability Metrics | SRE Lead | Product Operations Lead | Weekly rollup + monthly summary | SLO breach, sustained latency regression, uptime incident |
| Incident History and Remediation SLAs | Security Operations Lead | Reliability Incident Commander | Within 1 business day of incident closure + monthly audit | Sev-1/Sev-2 incident closure, SLA policy updates |
| Release Governance Evidence | Governance Program Office | Release Manager | Per release + monthly governance audit | Constitutional/gating changes, release sign-off, evidence schema updates |

## 1) Architecture and Security Docs

| Artifact | Path | Status | Refresh cadence | Owner |
|---|---|---|---|---|
| Architecture contract (normative) | `docs/ARCHITECTURE_CONTRACT.md` | Active | Monthly + on contract changes | Platform Architecture Lead |
| Architecture summary | `docs/ARCHITECTURE_SUMMARY.md` | Active | Monthly | Platform Architecture Lead |
| Module boundary map | `docs/architecture/module_boundaries.md` | Active | Monthly + boundary updates | Platform Architecture Lead |
| Security overview | `docs/SECURITY.md` | Active | Monthly + control changes | Security Engineering Lead |
| Threat model | `docs/THREAT_MODEL.md` | Active | Quarterly + incident-triggered | Security Engineering Lead |
| Security invariants matrix | `docs/governance/SECURITY_INVARIANTS_MATRIX.md` | Active | Per governance release | Governance Program Office |

## 2) Dependency and SBOM Artifacts

| Artifact | Path | Status | Refresh cadence | Owner |
|---|---|---|---|---|
| Dependency baseline policy/check | `scripts/check_dependency_baseline.py` | Active | Per release candidate | Release Engineering Lead |
| Dependency baseline guard tests | `tests/test_dependency_baseline_guard.py` | Active | Per release candidate | Release Engineering Lead |
| SPDX header compliance check | `scripts/check_spdx_headers.py` | Active | Per release candidate | Security Compliance Lead |
| SBOM export bundle (CycloneDX/SPDX) | `artifacts/ci/sbom/` | Planned (versioned output path reserved) | Per release candidate + monthly snapshot | Security Compliance Lead |
| Dependency lock snapshot ledger | `artifacts/ci/dependency_snapshot/` | Planned (versioned output path reserved) | Monthly + dependency change events | Release Engineering Lead |

## 3) Customer Reliability Metrics

| Artifact | Path | Status | Refresh cadence | Owner |
|---|---|---|---|---|
| Reliability policy (SLO/SLA) | `docs/ops/SLO_SLA.md` | Active | Monthly | SRE Lead |
| Customer operations readiness guidance | `docs/customer/ADOPTION_PLAYBOOK.md` | Active | Monthly | Product Operations Lead |
| Reliability metrics evidence bundle | `artifacts/ci/reliability_metrics/` | Planned (versioned output path reserved) | Weekly rollup + release summary | SRE Lead |

## 4) Incident History and Remediation SLAs

| Artifact | Path | Status | Refresh cadence | Owner |
|---|---|---|---|---|
| Incident response standard | `docs/compliance/INCIDENT_RESPONSE.md` | Active | Monthly + post-incident | Security Operations Lead |
| Remediation SLA policy | `docs/compliance/REMEDIATION_SLA.md` | Active | Monthly + policy updates | Security Operations Lead |
| Incident playbook scenarios | `docs/governance/incident_playbooks/scenario_narratives.md` | Active | Quarterly + postmortem updates | Reliability Incident Commander |
| Incident record ledger export | `artifacts/ci/incident_history/` | Planned (versioned output path reserved) | Within 1 business day of closure | Security Operations Lead |

## 5) Release Governance Evidence

| Artifact | Path | Status | Refresh cadence | Owner |
|---|---|---|---|---|
| Claims/evidence matrix (canonical) | `docs/comms/claims_evidence_matrix.md` | Active | Per PR + per release | Governance Program Office |
| Release evidence matrix | `docs/RELEASE_EVIDENCE_MATRIX.md` | Active | Per release | Release Manager |
| Evidence completeness validator | `scripts/validate_release_evidence.py` | Active | Per release candidate | Governance Program Office |
| PR sequence and dependency control | `docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md` | Active | On sequence change | Governance Program Office |
| Governance sign-off artifacts | `artifacts/governance/` | Active (versioned by phase) | Per release/phase | Governance Program Office |

## Data Room Maintenance Rules

1. **Single source rule:** Keep links pointed at canonical docs (contract/spec first, summaries second).
2. **Versioned artifact rule:** New machine outputs should be written under date- or release-versioned paths in `artifacts/ci/` or `artifacts/governance/`.
3. **Owner accountability rule:** Any section with `Planned` status must include an accountable owner and target generation cadence.
4. **Evidence parity rule:** Release governance entries must remain consistent with `docs/comms/claims_evidence_matrix.md`.
5. **Auditability rule:** Changes to this index should be included in release/change reviews and referenced in governance evidence when materially updated.
