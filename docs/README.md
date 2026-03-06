# ADAAD Documentation Hub

![Status: Stable](https://img.shields.io/badge/Status-Stable-2ea043)
![Governance: Fail-Closed](https://img.shields.io/badge/Governance-Fail--Closed-critical)
![Replay: Deterministic](https://img.shields.io/badge/Replay-Deterministic-0ea5e9)

> Central navigation for all canonical ADAAD references — governance, architecture, security, and release.

**Last reviewed:** 2026-03-05

<p align="center">
  <img src="assets/governance-flow.svg" width="760" alt="ADAAD governance flow from proposal through replay verification and evidence archival">
</p>

---

## Quick paths

| I want to… | Go here |
|---|---|
| 🚀 Launch a governed run | [Quickstart](../QUICKSTART.md) |
| 🧠 Understand architecture | [Architecture Contract](ARCHITECTURE_CONTRACT.md) |
| 🛡️ Validate governance posture | [Security](SECURITY.md) · [Constitution](CONSTITUTION.md) |
| 📦 Ship with release discipline | [Release checklist](release/release_checklist.md) |
| 🧱 Review build strategy | [Strategic build suggestions](ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md) |
| 👥 Understand reviewer calibration | [Reviewer Reputation Epic](archive/EPIC_1_Reviewer_Reputation.md) |

---

## Audience-based routes

### New user
- [Quickstart](../QUICKSTART.md) — first governed run in under 5 minutes
- [Single-agent example](../examples/single-agent-loop/README.md) — minimal runnable loop
- [Security and key handling](SECURITY.md)

### Contributor
- [Contribution guide](../CONTRIBUTING.md)
- [Architecture contract](ARCHITECTURE_CONTRACT.md) — interface and boundary invariants
- [Repository README](../README.md)
- [Governance policy artifact](../governance/governance_policy_v1.json)

### Governance / audit reviewer
- [Constitution](CONSTITUTION.md) — hard constraints and tier definitions
- [Security invariants matrix](governance/SECURITY_INVARIANTS_MATRIX.md)
- [Governance policy artifact](../governance/governance_policy_v1.json)
- [Release evidence matrix](comms/claims_evidence_matrix.md)

### Lane owner / CI maintainer
- [Strategic build suggestions](ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md) — lane model, gate order, merge sequencing
- [Lane ownership register](governance/LANE_OWNERSHIP.md) — which lanes you own
- [CI gating](governance/ci-gating.md) — tier classification and gate triggers
- [Codex setup runbook](governance/CODEX_SETUP.md)
- [GA closure tracker](governance/ADAAD_7_GA_CLOSURE_TRACKER.md)

---

## Core references

| Document | Purpose |
|---|---|
| [**ArchitectAgent Spec v2.0.0**](governance/ARCHITECT_SPEC_v2.0.0.md) | Canonical architectural + constitutional specification |
| [Constitution](CONSTITUTION.md) | Hard governance constraints; 14 rules; cannot be overridden |
| [Architecture Contract](ARCHITECTURE_CONTRACT.md) | Interface and boundary contracts |
| [Security](SECURITY.md) | Auth, signing, fail-closed controls |
| [Threat model](THREAT_MODEL.md) | Attack surfaces and mitigations |
| [Determinism contract](DETERMINISM.md) | Replay and determinism invariants |
| [Release evidence matrix](comms/claims_evidence_matrix.md) | Claims-to-evidence mapping |
| [Diagram ownership](DIAGRAM_OWNERSHIP.md) | Visual asset governance |

---

## Governance references

| Document | Purpose |
|---|---|
| [Security Invariants Matrix](governance/SECURITY_INVARIANTS_MATRIX.md) | All enforced security invariants |
| [Determinism Contract Spec](governance/DETERMINISM_CONTRACT_SPEC.md) | Determinism and replay contract detail |
| [Governance State Machine](governance/GOVERNANCE_STATE_MACHINE_NORMALIZATION.md) | State machine normalization |
| [Production Auth Contract](governance/PRODUCTION_AUTH_CONTRACT_DESIGN.md) | Auth design and token contracts |
| [Red-Team Threat Model](governance/RED_TEAM_THREAT_MODEL_NEXT_PHASE.md) | Next-phase red-team plan |
| [Mutation Lifecycle](governance/mutation_lifecycle.md) | End-to-end mutation governance lifecycle |
| [Federation Key Registry](governance/FEDERATION_KEY_REGISTRY.md) | Key lifecycle and rotation runbook |

---

## Release references

| Document | Purpose |
|---|---|
| [Release checklist](release/release_checklist.md) | Canonical operator preflight |
| [Release audit checklist](releases/RELEASE_AUDIT_CHECKLIST.md) | Evidence verification |
| [v2.0.0 Release notes](releases/2.0.0.md) | AI Mutation Capability Expansion · Principal/Staff grade |
| [v1.1.0 Release notes](releases/1.1.0.md) | Phase 0 hardening complete |
| [Claims-evidence matrix](comms/claims_evidence_matrix.md) | Evidence completeness gate |

---

## Documentation validators

Both validators run as fail-closed CI checks:

```bash
python scripts/validate_readme_alignment.py --format json
python scripts/validate_docs_integrity.py --format json
```

- `validate_readme_alignment.py` — enforces contract snippets across key README and release files.
- `validate_docs_integrity.py` — scans all `.md` files, validates local links and image targets, flags missing alt text.

---

## Orchestration hardening invariants

`app/orchestration/mutation_orchestration_service.py` enforces:

- Task normalization is deterministic (first-seen order, deduplicated labels).
- Empty/whitespace-only task batches resolve to `safe_boot=True`.
- Malformed/non-string task records are ignored without raising side effects.
- Transition failures preserve fail-closed behavior (`run_cycle=False`).
- Blocked transition payloads are isolated per envelope to prevent cross-call mutation bleed.

---

## Brand and visual assets

ADAAD visual assets in `docs/assets/` are available for repository documentation and release artifacts.

- Per-file provenance and usage notes: [`assets/IMAGE_PROVENANCE.md`](assets/IMAGE_PROVENANCE.md)
- `assets/adaad-banner.svg` requires owner approval for external packaging or marketing redistribution.
- Use of ADAAD names/logos does not grant trademark rights. See [`../BRAND_LICENSE.md`](../BRAND_LICENSE.md).

---

## License and compliance

- Repository license: **MIT** (root `LICENSE`)
- Compliance metadata: `LICENSES.md` and `NOTICE`
- Compliance gate: `python scripts/validate_license_compliance.py`

---

## Strategic Forecast & Founder Plan

| Document | Format | Purpose |
|----------|--------|---------|
| [ADAAD Horizon Forecast 2026](ADAAD_HORIZON_FORECAST_2026.md) | Markdown | 18-month directional forecast — phases, metrics, governance, risks |
| [ADAAD Horizon v2](ADAAD_Horizon_v2.html) | HTML | Interactive visual forecast — human-oriented editorial design |
| [Founder Plan Proposal](ADAAD_FOUNDER_PLAN_PROPOSAL.md) | Markdown | 8 structural governance commitments, milestone gates, next actions |
| [Founder Plan Proposal](ADAAD_Founder_Plan_Proposal.html) | HTML | Interactive visual proposal — print-optimized founder document |

> **Current system state:** v2.1.0 · Phase 3 shipped · Phase 4 in progress · CI gates: all passing  
> **Forecast last updated:** March 6, 2026

