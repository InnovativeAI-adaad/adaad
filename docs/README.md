# 📚 ADAAD Documentation

Welcome to the canonical ADAAD documentation home.

## 🔒 Trust Guarantees

ADAAD enforces:

- Deterministic replay validation
- Fail-closed mutation execution
- Policy-bound runtime enforcement
- Lineage and mutation traceability
- Constitution-level governance constraints

All governance decisions are reproducible across runs.

<p align="center">
  <img src="assets/governance-flow.svg" width="760" alt="Governance flow: Propose to Archive with replay and policy gates">
</p>

## 🔎 10-Minute Evaluator Path

1. Read [README.md](../README.md)
2. Read [ARCHITECTURE_CONTRACT.md](ARCHITECTURE_CONTRACT.md)
3. Review [RELEASE_EVIDENCE_MATRIX.md](RELEASE_EVIDENCE_MATRIX.md)
4. Run [QUICKSTART.md](../QUICKSTART.md)
5. Inspect [examples/mutation_cycle_trace.json](examples/mutation_cycle_trace.json)

## 🚀 Getting Started

- [Quickstart (5 minutes)](../QUICKSTART.md)
- [Top-level project README](../README.md)
- [First loop walkthrough](first-loop-30min.md)

## 🧭 Most-visited docs

| Doc | Why visit |
|---|---|
| [QUICKSTART.md](../QUICKSTART.md) | Fast setup and first governed run |
| [docs/SECURITY.md](SECURITY.md) | Security model, controls, and guarantees |
| [docs/ARCHITECTURE_CONTRACT.md](ARCHITECTURE_CONTRACT.md) | Architecture contract and runtime boundaries |
| [docs/releases/1.0.0.md](releases/1.0.0.md) | v1.0.0 release notes and scope |

## 🏗️ Architecture

- [Architecture contract](ARCHITECTURE_CONTRACT.md)
- [Architecture summary (one page)](ARCHITECTURE_SUMMARY.md)
- [Evolution architecture](EVOLUTION_ARCHITECTURE.md)
- [Architecture implementation alignment](README_IMPLEMENTATION_ALIGNMENT.md)

## 🛡️ Governance & Security

- [Security documentation](SECURITY.md)
- [Threat model](THREAT_MODEL.md)
- [Governance enforcement](GOVERNANCE_ENFORCEMENT.md)
- [Constitution](CONSTITUTION.md)
- [Governance docs directory](governance/)

## 🧾 Releases

- [Release evidence matrix](RELEASE_EVIDENCE_MATRIX.md)
- [Release replay verification procedure](DETERMINISM.md#replay-contract)
- [Mutation evidence schema](../schemas/evidence_bundle.v1.json)
- [Governance audit checklist](releases/RELEASE_AUDIT_CHECKLIST.md)
- [Release notes directory](releases/)
- [v1.0.0 release notes](releases/1.0.0.md)
- [Project changelog](../CHANGELOG.md)

## 🧪 Examples

- [Examples directory](examples/)
- [Mutation cycle trace sample](examples/mutation_cycle_trace.json)

## 🛠️ Operations / Runbooks

- [Governance runbooks and playbooks](governance/)
- [Sandbox operational notes](sandbox/README.md)
- [Federation conflict runbook](governance/FEDERATION_CONFLICT_RUNBOOK.md)
- [Aponi alert runbook](governance/APONI_ALERT_RUNBOOK.md)

---

If you need machine-oriented inventory/indexing, use [`docs/manifest.txt`](manifest.txt).
