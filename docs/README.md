## Governance

- [Security Invariants Matrix](governance/SECURITY_INVARIANTS_MATRIX.md)
- [Determinism Contract Specification](governance/DETERMINISM_CONTRACT_SPEC.md)
- [Governance State Machine Normalization](governance/GOVERNANCE_STATE_MACHINE_NORMALIZATION.md)
- [Production Auth Contract Design](governance/PRODUCTION_AUTH_CONTRACT_DESIGN.md)
- [Red-Team Threat Model — Next Phase Plan](governance/RED_TEAM_THREAT_MODEL_NEXT_PHASE.md)

# 📚 ADAAD Documentation Hub

Welcome to the central navigation page for ADAAD docs.

<p align="center">
  <img src="assets/governance-flow.svg" width="760" alt="ADAAD governance flow from proposal to replay verification and evidence archival">
</p>

## 🌈 Quick visual routes

| I want to... | Go here |
| --- | --- |
| 🚀 Launch a governed run fast | [Quickstart](../QUICKSTART.md) |
| 🧠 Understand architecture boundaries | [Architecture Contract](ARCHITECTURE_CONTRACT.md) |
| 🛡️ Validate governance and security posture | [Security](SECURITY.md) + [Constitution](CONSTITUTION.md) |
| 📦 Ship with release discipline | [Release checklist](release/release_checklist.md) |

## 🚀 Most-used docs

| Doc | Why start here |
| --- | --- |
| [Quickstart](../QUICKSTART.md) | Fastest way to run ADAAD locally. |
| [Security](SECURITY.md) | Key handling, reporting process, and audit artifact locations. |
| [Architecture Contract](ARCHITECTURE_CONTRACT.md) | Canonical ownership and layer boundaries. |
| [Release checklist](release/release_checklist.md) | Governance-ready release go/no-go gates. |

## 🎯 Documentation by intent

- **Run ADAAD fast:** [Quickstart](../QUICKSTART.md)
- **Understand system boundaries:** [Architecture Contract](ARCHITECTURE_CONTRACT.md)
- **Validate governance controls:** [Constitution](CONSTITUTION.md)
- **Prepare releases safely:** [Release checklist](release/release_checklist.md)

## 🧭 Core references

- [Constitution](CONSTITUTION.md)
- [Governance mutation lifecycle](governance/mutation_lifecycle.md)
- [Threat model](THREAT_MODEL.md)
- [Release evidence matrix](RELEASE_EVIDENCE_MATRIX.md)
- [Diagram ownership](DIAGRAM_OWNERSHIP.md)

## Start here next

### New user
- [Quickstart](../QUICKSTART.md)
- [Single-agent runnable example](../examples/single-agent-loop/README.md)
- [Security and key handling](SECURITY.md)

### Contributor
- [Contribution guide](../CONTRIBUTING.md)
- [Release checklist](release/release_checklist.md)
- [Repository README](../README.md)

### Governance/audit reviewer
- [Constitution and governance boundaries](CONSTITUTION.md)
- [Governance policy artifact](../governance/governance_policy_v1.json)
- [Release evidence checklist](release/release_checklist.md)

<details>
<summary><strong>Need deeper governance references?</strong></summary>

- [Governance mutation lifecycle](governance/mutation_lifecycle.md)
- [Release evidence matrix](RELEASE_EVIDENCE_MATRIX.md)
- [Diagram ownership contract](DIAGRAM_OWNERSHIP.md)

</details>


## License and Compliance Baseline

- Repository license: **MIT** (root `LICENSE`).
- Compliance metadata: `LICENSES.md` and `NOTICE` in repository root.
- Automated license compliance gate: `python scripts/validate_license_compliance.py`.
- Safety-critical use should record third-party license attestations in release evidence.

## Current Weak-Point Mitigation Priorities

The documentation set tracks hardening and optimization priorities around:

1. deterministic orchestration contracts and replay parity,
2. fail-closed governance paths under missing or malformed inputs, and
3. conservative performance improvements that do not alter public APIs.

Use the release checklist and evidence matrix to show each mitigation is backed
by deterministic tests before merge.


## Orchestration hardening invariants

`app/orchestration/mutation_orchestration_service.py` enforces these invariants:

- Task normalization is deterministic (first-seen order, deduplicated labels).
- Empty/whitespace-only task batches resolve to `safe_boot=True`.
- Malformed/non-string task records are ignored without raising side effects.
- Transition failures preserve fail-closed behavior (`run_cycle=False`).
- Blocked transition payloads are isolated per envelope to prevent cross-call mutation bleed.

Related: [governance mutation lifecycle](governance/mutation_lifecycle.md).
