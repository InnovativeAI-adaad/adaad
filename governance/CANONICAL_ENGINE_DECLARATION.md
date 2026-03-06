# CANONICAL ENGINE DECLARATION

- **record_type**: canonical_engine_declaration
- **schema_version**: 2.0.0
- **engine_id**: adaad-evolution-engine-v2
- **status**: active
- **effective_at**: 2026-03-06T00:00:00Z
- **supersedes_record**: none

## Engine Identity

The canonical evolution engine for ADAAD v2.0.0 is the AI-driven mutation pipeline
comprising `AIMutationProposer`, `EvolutionLoop`, `WeightAdaptor`, `FitnessLandscape`,
and `PopulationManager`, all governed exclusively by `GovernanceGate`.

## Authority

- **Single approval surface:** `runtime/governance/gate_certifier.py` + `GovernanceGate`
- **Constitutional spec:** `docs/governance/ARCHITECT_SPEC_v2.0.0.md`
- **No agent, adapter, or subsystem may approve mutations outside this surface.**

## Process Metadata

- **governance_workflow**: declaration-review-ratify
- **required_approvals**: 2
- **signature_scheme**: ed25519
- **signature_threshold**: 2-of-3
- **attestation_artifact**: governance/attestations/canonical_engine_declaration.json

## Pending

Signed ed25519 attestation (requires 2-of-3 governance key holders). Until signed,
this declaration is authoritative by consensus and architectural contract.
