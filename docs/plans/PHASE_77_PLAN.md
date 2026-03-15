# Phase 77 — ArchitectAgent Proposal Package

**Prepared by:** Claude (ArchitectAgent role, DUSTADAAD environment)
**Prepared:** 2026-03-15
**For ratification by:** Dustin L. Reid — Governor, Innovative AI LLC
**Constitutional authority:** `CONSTITUTION.md v0.9.0 → ARCHITECTURE_CONTRACT.md`
**Base version:** v9.11.0 (Phase 76 complete)
**Target release:** v9.12.0
**HUMAN-0 gate:** Direction must be ratified by Dustin before PR-77-01 may open

---

## Executive Summary

Phase 77 is a **dual-track phase**:

- **Track A (Governance Sprint):** Closes the four remaining Dustin-executable audit findings from the 2026-03-14 deep dive — GitHub App dual-handler consolidation, `external_event_bridge` module, KMS/HSM event signing production implementation, and `GovernancePlugin` base completion. Closes C-03 structurally at the code level.
- **Track B (First Seed Epoch Run):** Executes the first end-to-end live seed lifecycle run — from an existing promoted seed through CEL injection to outcome recording — producing the inaugural `AutonomousCapabilityEvolution` evidence artifact sourced from the Seed Pipeline.

Track A is code quality and governance infrastructure. Track B is a milestone capability demonstration. Both can proceed concurrently under separate PRs.

**Recommended ratification:** Both tracks. Track A must merge before Track B opens (Track B depends on clean governance surface).

---

## Candidate Directions

### Candidate 1 (Recommended — P0): Track A · Governance Maintenance Sprint

**Rationale:** Three `NotImplementedError` stubs in production-path modules (`EventSigner`, `EventVerifier`, `GovernancePlugin.evaluate`) and an absent `external_event_bridge` module represent live governance gaps. The dual webhook handler (`app/github_app.py` vs `runtime/integrations/github_webhook_handler.py`) is unresolved. These are constitutional debt items — the procession model requires they be governed before Phase 77 capability work opens.

**Scope:**

| Work Item | File(s) | Finding |
|---|---|---|
| `external_event_bridge` module implementation | `runtime/governance/external_event_bridge.py` | C-03 structural close |
| `EventSigner` / `EventVerifier` production implementation | `runtime/evolution/event_signing.py` | Technical debt |
| `GovernancePlugin.evaluate()` base completion | `runtime/innovations.py` | Technical debt |
| Dual webhook handler consolidation | `app/github_app.py` ↔ `runtime/integrations/github_webhook_handler.py` | C-03 remnant |
| `FitnessPipeline` abstract method stub | `runtime/fitness_pipeline.py` | Technical debt |

**Key invariants to introduce:**
- `EXT-BRIDGE-0`: `external_event_bridge.record()` is the sole mechanism for external-surface events to enter the governance ledger
- `EXT-BRIDGE-DETERM-0`: equal event inputs produce identical bridge records
- `EXT-BRIDGE-AUDIT-0`: bridge record written to `LineageLedgerV2` before acknowledgement

**Target:** v9.12.0 · CI tier: constitutional · Estimated tests: 15–20

---

### Candidate 2 (Recommended — P0): Track B · First Seed Epoch Run

**Rationale:** The Seed Lifecycle Pipeline (Phases 71–76) is complete end-to-end in code. No live seed has yet been injected into a real CEL epoch and had its outcome recorded. Track B closes this gap by running the first governed seed-to-outcome cycle with a real promoted seed, producing a `SeedCELOutcomeEvent` in the lineage ledger that is cryptographically linked to the originating seed and epoch.

**Scope:**

| Work Item | File(s) | Detail |
|---|---|---|
| Select and promote a qualifying seed | `runtime/seed_promotion.py` | Seed with `expansion_score >= 0.85` enqueued |
| Execute governed review (operator gate) | `runtime/seed_review.py` | `record_review()` with operator_id |
| Build proposal request | `runtime/seed_proposal.py` | `build_proposal_request()` — approved-only |
| Inject into CEL context | `runtime/seed_cel_injector.py` | `inject_seed_proposal_into_context()` |
| Run governed epoch | `runtime/evolution_loop.py` | `LiveWiredCEL.run_epoch(context=epoch_context)` |
| Record outcome | `runtime/seed_cel_outcome.py` | `record_cel_outcome()` — ledger-anchored |
| Produce evidence artifact | `artifacts/governance/phase77/seed_epoch_run_evidence.json` | Full lineage digest chain |

**Key invariant to demonstrate:**
- `SEED-LIFECYCLE-COMPLETE-0`: An end-to-end seed epoch run produces a `SeedCELOutcomeEvent` that is hash-linked to its originating `SeedCELInjectionEvent`, `SeedProposalEvent`, `SeedReviewDecisionEvent`, `SeedGraduationEvent`, and `SeedEvolutionEvent` in `LineageLedgerV2` — the full provenance chain is deterministically replayable

**Target:** v9.13.0 (sequential after Track A) · CI tier: constitutional · Estimated tests: 20–25

---

### Candidate 3 (P1): KMS/HSM Event Signing Production Activation

**Rationale:** `EventSigner` and `EventVerifier` abstract interfaces exist but are not wired to any production key provider. `DeterministicMockSigner` is used in tests. Production ledger events are SHA-256 hash-chained but not asymmetrically signed. This gap means an attacker with write access to the ledger file could substitute events without cryptographic detection.

**Scope:** Wire `EventSigner` to AWS KMS or a local Ed25519 key file (configurable via `ADAAD_SIGNING_BACKEND` env var). Gate all `LineageLedgerV2.append_event()` calls through the active signer. Add `signature_bundle` field to `LineageLedgerV2` event records.

**Key invariants:**
- `LEDGER-SIGN-0`: every lineage ledger event carries a `SignatureBundle` from the active `EventSigner`
- `LEDGER-VERIFY-0`: `verify_integrity()` validates all `SignatureBundle` fields

**Target:** v9.14.0 · CI tier: constitutional · Estimated tests: 20+

---

### Candidate 4 (P1): Aponi GitHub Feed Panel

**Rationale:** `app/github_app.py` emits governance events for push, PR merge, check failures, and slash commands. None of these are surfaced in the Aponi dashboard. An Aponi GitHub Feed panel would give the governor real-time visibility into repository activity alongside seed lifecycle events — a unified governance console.

**Scope:** New Aponi sub-panel (key `8`): live GitHub event feed sourced from `InnovationsEventBus`; wire `_emit_governance_event()` to emit typed bus frames; renders push/PR/CI event toasts and a paginated feed card.

**Target:** v9.14.0 · CI tier: standard (UI only) · Estimated tests: 10–12

---

## Recommended Ratification

Ratify both **Track A (Candidate 1)** and **Track B (Candidate 2)** as Phase 77.

Track A opens immediately as `PR-77-01`. Track B opens as `PR-77-02` after Track A merges. Candidates 3 and 4 are deferred to Phase 78 — they depend on the event signing infrastructure and Aponi panel architecture established in 77.

---

## Phase 77 Delivery Spec (upon ratification)

### Track A — PR-77-01: Governance Infrastructure Sprint

```
Branch: feat/phase-77-governance-infrastructure
Base:   main @ v9.11.0
Target: v9.12.0
CI tier: constitutional
```

**Deliverables:**

1. `runtime/governance/external_event_bridge.py` — new module
   - `record(event_name: str, data: dict) -> None`
   - Writes `ExternalBridgeEvent` to `LineageLedgerV2` before returning
   - JSONL fallback if ledger unavailable
   - Invariants: `EXT-BRIDGE-0`, `EXT-BRIDGE-DETERM-0`, `EXT-BRIDGE-AUDIT-0`

2. `runtime/evolution/event_signing.py` — implement `HmacEventSigner` and `HmacEventVerifier`
   - Backed by `ADAAD_LEDGER_HMAC_SECRET` env var
   - Deterministic — equal inputs → identical `SignatureBundle`
   - `DeterministicMockSigner` retained for test parity

3. `runtime/innovations.py` — implement `GovernancePlugin.evaluate()` contract
   - Default implementation returns `PluginRuleResult(passed=True, reason="no_rule")`
   - `NoNewDependenciesPlugin` and `DocstringRequiredPlugin` fully implemented

4. `runtime/fitness_pipeline.py` — implement `FitnessPipeline` abstract stubs

5. Webhook consolidation: `app/github_app.py` calls `runtime/integrations/github_webhook_handler.handle_webhook()` for the ledger-emit path — single source of truth for ledger writes

6. `tests/test_phase77_governance_infra.py` — ≥15 tests
   - `EXT-BRIDGE-*` invariants
   - `HmacEventSigner` / `HmacEventVerifier` determinism and round-trip
   - `GovernancePlugin` concrete implementations
   - Webhook consolidation integration test

**Evidence artifact:** `artifacts/governance/phase77/governance_infra_evidence.json`

---

### Track B — PR-77-02: First Seed Epoch Run

```
Branch: feat/phase-77-seed-epoch-run
Base:   main @ v9.12.0 (after Track A merged)
Target: v9.13.0
CI tier: constitutional
```

**Deliverables:**

1. `scripts/run_seed_epoch.py` — governed CLI for executing a seed lifecycle run
   - Accepts `--seed-id`, `--operator-id`, `--dry-run`
   - Runs the full pipeline: promote → review → propose → inject → epoch → record
   - Outputs structured evidence JSON

2. `artifacts/governance/phase77/seed_epoch_run_evidence.json` — evidence artifact
   - `run_id`, `seed_id`, `cycle_id`, `epoch_id`
   - Full lineage digest chain: `SeedEvolutionEvent` → `SeedGraduationEvent` → `SeedProposalEvent` → `SeedCELInjectionEvent` → `SeedCELOutcomeEvent`
   - `outcome_status`, `fitness_delta`, `mutation_count`
   - `SEED-LIFECYCLE-COMPLETE-0` satisfied flag
   - Governor sign-off: `Dustin L. Reid — [date]`

3. `tests/test_phase77_seed_epoch_run.py` — ≥20 tests
   - Full pipeline integration test (mocked CEL epoch)
   - Lineage chain verification — each event hash-links to predecessor
   - `SEED-LIFECYCLE-COMPLETE-0` invariant proof test
   - Deterministic re-run produces identical evidence digest

**Constitutional invariant:**
`SEED-LIFECYCLE-COMPLETE-0` — An end-to-end seed epoch run produces a `SeedCELOutcomeEvent` hash-linked to all upstream seed lifecycle events in `LineageLedgerV2`. The full chain is deterministically replayable.

---

## Governance Gate Requirements (Phase 77)

| Gate | Requirement | Track |
|---|---|---|
| HUMAN-0 | Direction ratified by Dustin before PR-77-01 opens | Both |
| HUMAN-0 | Evidence artifact `seed_epoch_run_evidence.json` requires Dustin GPG sign-off | Track B |
| AUDIT-0 | All new ledger events hash-chained; no retroactive modification | Both |
| REPLAY-0 | Phase 77 evidence artifacts deterministically replayable | Both |
| EXT-BRIDGE-AUDIT-0 | `ExternalBridgeEvent` written before acknowledgement | Track A |
| SEED-LIFECYCLE-COMPLETE-0 | Full provenance chain verified in evidence artifact | Track B |

---

## Ratification Block

> **HUMAN-0 gate — awaiting Dustin L. Reid approval**
>
> To ratify this proposal, Dustin records approval in a GPG-signed commit:
>
> ```
> governance: Phase 77 direction ratified — Dual Track A+B
>
> Track A: Governance Infrastructure Sprint (v9.12.0)
> Track B: First Seed Epoch Run (v9.13.0)
>
> HUMAN-0: direction ratified by Dustin L. Reid — [DATE]
> ```
>
> Upon ratification, `PR-77-01` opens on branch `feat/phase-77-governance-infrastructure`.

---

*Proposal prepared by: Claude (ArchitectAgent role, DUSTADAAD environment) · 2026-03-15*
*Governor authority: Dustin L. Reid — Innovative AI LLC*
