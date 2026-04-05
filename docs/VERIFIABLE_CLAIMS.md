# ADAAD — Verifiable Claims

> **Governance principle:** Every claim in this document is traceable to a module, a test file, a governance artifact, and a verification command. Unverifiable claims are not listed here.
>
> **Last updated:** 2026-04-05 · v9.55.0 · Phase 122

---

## How to verify

```bash
# 1. Clone
git clone https://github.com/InnovativeAI-adaad/adaad.git && cd adaad

# 2. Install test dependencies
pip install pytest --break-system-packages

# 3. Run all acceptance tests
PYTHONPATH=. pytest tests/ -v

# 4. Verify ledger chain integrity
python scripts/verify_ledger.py artifacts/governance/phase121/das_ledger.jsonl

# 5. Replay a stored epoch
python scripts/replay_epoch.py artifacts/governance/phase121/das_ledger.jsonl
```

Each row below maps a specific claim to the code that enforces it and the test that proves it.

---

## Core pipeline claims

| Claim | Module | Test file | Governance artifact | Verification command |
|---|---|---|---|---|
| Every epoch produces a verifiable evidence hash (CEL-EVIDENCE-0) | `runtime/constitutional_evolution_loop.py` | `tests/test_phase87_cel.py` | `artifacts/governance/phase87/` | `pytest tests/test_phase87_cel.py -k evidence` |
| Mutations are byte-identical replayable (CEL-REPLAY-0) | `runtime/constitutional_evolution_loop.py` | `tests/test_phase87_cel.py` | `artifacts/governance/phase87/` | `pytest tests/test_phase87_cel.py -k replay` |
| Step ordering cannot be bypassed (CEL-ORDER-0) | `runtime/constitutional_evolution_loop.py` | `tests/test_phase87_cel.py` | `artifacts/governance/phase87/` | `pytest tests/test_phase87_cel.py -k order` |
| Governance gate is the sole promotion path (GOV-SOLE-0) | `runtime/governance_gate.py` | `tests/test_governance_gate.py` | `artifacts/governance/phase87/` | `pytest tests/test_governance_gate.py` |
| Shadow harness writes nothing to production (LSME-0) | `runtime/innovations30/temporal_regret.py` | `tests/test_phase91_lsme.py` | `artifacts/governance/phase91/` | `pytest tests/test_phase91_lsme.py -k zero_write` |
| Red Team cannot approve its own challenges (AFRT-0) | `runtime/innovations30/red_team_agent.py` | `tests/test_phase92_afrt.py` | `artifacts/governance/phase92/` | `pytest tests/test_phase92_afrt.py -k cannot_approve` |
| Critical mutations require GPG-signed human key (HUMAN-0) | `runtime/governance_gate.py` | `tests/test_human_gate.py` | `artifacts/governance/phase66/` | `pytest tests/test_human_gate.py` |
| All 162 Hard-class invariants enforced at runtime | `runtime/constitutional_invariants.py` | `tests/test_invariants.py` | `artifacts/governance/phase121/tier_summary.json` | `pytest tests/test_invariants.py` |

---

## Innovation module claims (INNOV-01 through INNOV-35)

| Innovation | Claim | Module | Test file | Artifact | Verify |
|---|---|---|---|---|---|
| INNOV-01 · CSAP | ADAAD proposes amendments to its own constitutional rules; unconditional HUMAN-0 ratification required before any amendment takes effect | `runtime/innovations30/constitutional_stress_test.py` | `tests/test_phase87_innov01.py` | `artifacts/governance/phase87/` | `pytest tests/test_phase87_innov01.py` |
| INNOV-02 · ACSE | Dedicated adversarial agent stress-tests every constitutional rule each epoch | `runtime/innovations30/self_awareness_invariant.py` | `tests/test_phase87_innov02.py` | `artifacts/governance/phase87/` | `pytest tests/test_phase87_innov02.py` |
| INNOV-03 · TIFE | Predicts which invariants will be violated in future epochs before they fail | `runtime/innovations30/temporal_governance.py` | `tests/test_phase87_innov03.py` | `artifacts/governance/phase87/` | `pytest tests/test_phase87_innov03.py` |
| INNOV-04 · SCDD | Detects when constitutional behaviour drifts from its historical baseline; chain-verified | `runtime/innovations30/constitutional_entropy_budget.py` | `tests/test_phase88_scdd.py` | `artifacts/governance/phase88/` | `pytest tests/test_phase88_scdd.py` |
| INNOV-05 · AOEP | Proposes entirely new architectural organs to close capability gaps; HUMAN-0 ratification required | `runtime/innovations30/governance_archaeology.py` | `tests/test_phase89_aoep.py` | `artifacts/governance/phase89/` | `pytest tests/test_phase89_aoep.py` |
| INNOV-06 · CEPD | Every mutation cryptographically bound to all causal ancestors via Merkle root; independently verifiable | `runtime/innovations30/counterfactual_fitness.py` | `tests/test_phase90_cepd.py` | `artifacts/governance/phase90/` | `pytest tests/test_phase90_cepd.py` |
| INNOV-07 · LSME | Zero-write shadow harness runs against real traffic patterns; divergence regression is a hard block | `runtime/innovations30/temporal_regret.py` | `tests/test_phase91_lsme.py` | `artifacts/governance/phase91/` | `pytest tests/test_phase91_lsme.py` |
| INNOV-08 · AFRT | Adversarial Red Team challenges every proposal before governance scoring; structurally cannot approve | `runtime/innovations30/red_team_agent.py` | `tests/test_phase92_afrt.py` | `artifacts/governance/phase92/` | `pytest tests/test_phase92_afrt.py` |
| INNOV-09 · AFIT | Code readability scored across 5 AST axes as a constitutionally-bounded fitness signal; weight in [0.05, 0.30] | `runtime/innovations30/aesthetic_fitness.py` | `tests/test_phase93_afit.py` | `artifacts/governance/phase93/` | `pytest tests/test_phase93_afit.py` |
| INNOV-10 · MMEM | Hash-chained self-model consulted before every proposal; identity drift detected at root; never blocks epoch | `runtime/innovations30/morphogenetic_memory.py` | `tests/test_phase94_mmem.py` | `artifacts/governance/phase94/` | `pytest tests/test_phase94_mmem.py` |
| INNOV-11 · DSTE | Speculative mutation rehearsal across epoch boundaries; never touches production state | `runtime/innovations30/dream_state.py` | `tests/test_phase96_dste.py` | `artifacts/governance/phase96/` | `pytest tests/test_phase96_dste.py` |
| INNOV-12 · MGV | Full lineage graph for every mutation from proposal to terminal outcome; deterministic from epoch_id | `runtime/innovations30/mutation_genealogy.py` | `tests/test_phase97_mgv.py` | `artifacts/governance/phase97/` | `pytest tests/test_phase97_mgv.py` |
| INNOV-13 · IMT | Signed capability transfer protocol; cryptographically verified cross-agent learning | `runtime/innovations30/knowledge_transfer.py` | `tests/test_phase98_imt.py` | `artifacts/governance/phase98/` | `pytest tests/test_phase98_imt.py` |
| INNOV-14 · CEB (CJS) | Multi-agent constitutional jury decides contested mutations; no single-agent approval path | `runtime/innovations30/constitutional_entropy_budget.py` | `tests/test_phase99_cjs.py` | `artifacts/governance/phase99/` | `pytest tests/test_phase99_cjs.py` |
| INNOV-15 · RST | Agents stake reputation on proposals; slashed on failure; chain-verified ledger | `runtime/innovations30/reputation_staking.py` | `tests/test_phase104_rst.py` | `artifacts/governance/phase104/` | `pytest tests/test_phase104_rst.py` |
| INNOV-16 · ERS | Agents self-specialize into constitutional roles based on performance history | `runtime/innovations30/emergent_roles.py` | `tests/test_phase101_ers.py` | `artifacts/governance/phase101/` | `pytest tests/test_phase101_ers.py` |
| INNOV-17 · APM | Every terminated agent answers structured constitutional debrief before teardown | `runtime/innovations30/agent_postmortem.py` | `tests/test_phase102_apm.py` | `artifacts/governance/phase102/` | `pytest tests/test_phase102_apm.py` |
| INNOV-18 · GJR | Health-adaptive rule severity — non-critical rules soften during high-health epochs; hard constitutional stops | `runtime/innovations30/constitutional_jury.py` | `tests/test_phase103_gjr.py` | `artifacts/governance/phase103/` | `pytest tests/test_phase103_gjr.py` |
| INNOV-19 · RST (GAM) | Cryptographically verified decision timeline reconstruction for any mutation_id | `runtime/innovations30/reputation_staking.py` | `tests/test_phase104_rst.py` | `artifacts/governance/phase104/` | `pytest tests/test_phase104_rst.py` |
| INNOV-20 · BRM | Adversarial scenario catalogue; append-only gap ledger feeds invariant discovery | `runtime/innovations30/blast_radius_model.py` | `tests/test_phase105_brm.py` | `artifacts/governance/phase105/` | `pytest tests/test_phase105_brm.py` |
| INNOV-21 · GBP | Bounded bankruptcy state machine; discharge progression monotonic; re-entry blocked | `runtime/innovations30/governance_bankruptcy.py` | `tests/test_phase106_gbp.py` | `artifacts/governance/phase106/` | `pytest tests/test_phase106_gbp.py` |
| INNOV-22 · MCF | Constitutional conflict detection; severity stratification; HUMAN-0 escalation advisory | `runtime/innovations30/mutation_conflict_framework.py` | `tests/test_phase107_mcf.py` | `artifacts/governance/phase107/` | `pytest tests/test_phase107_mcf.py` |
| INNOV-23 · CES | Anticipatory warning emission before Hard-class invariant breach; warning fires before violation | `runtime/innovations30/constitutional_epoch_sentinel.py` | `tests/test_phase108_ces.py` | `artifacts/governance/phase108/` | `pytest tests/test_phase108_ces.py` |
| INNOV-24 · SVP | Independent constitutional validation layer operating outside the core mutation pipeline | `runtime/innovations30/semantic_version_enforcer.py` | `tests/test_phase109_svp.py` | `artifacts/governance/phase109/` | `pytest tests/test_phase109_svp.py` |
| INNOV-25 · HAF | Fitness scoring dynamically calibrated to available hardware resource envelope | `runtime/innovations30/hardware_adaptive_fitness.py` | `tests/test_phase110_haf.py` | `artifacts/governance/phase110/` | `pytest tests/test_phase110_haf.py` |
| INNOV-26 · GDA | Rate-limits constitutional drift; 30% rule-change threshold triggers double HUMAN-0 ratification | `runtime/innovations30/graduated_invariants.py` | `tests/test_phase111_gda.py` | `artifacts/governance/phase111/` | `pytest tests/test_phase111_gda.py` |
| INNOV-27 · RCI | Regulatory compliance mapping; constitutional invariants traceable to external frameworks | `runtime/innovations30/regulatory_compliance.py` | `tests/test_phase112_rci.py` | `artifacts/governance/phase112/` | `pytest tests/test_phase112_rci.py` |
| INNOV-28 · IPV | No mutation may reduce system self-monitoring observability; transparency is constitutional | `runtime/innovations30/intent_preservation.py` | `tests/test_phase113_ipv.py` | `artifacts/governance/phase113/` | `pytest tests/test_phase113_ipv.py` |
| INNOV-29 · CED | Inverted-fitness exploration every 25 epochs; hard constitutional stops prevent catastrophe | `runtime/innovations30/curiosity_engine.py` | `tests/test_phase114_ced.py` | `artifacts/governance/phase114/` | `pytest tests/test_phase114_ced.py` |
| INNOV-30 · MIRROR | Historical proposal prediction audit every 50 epochs; low accuracy triggers calibration epoch | `runtime/innovations30/mirror_test.py` | `tests/test_phase115_mirror.py` | `artifacts/governance/phase115/` | `pytest tests/test_phase115_mirror.py` |
| INNOV-31 · IDE | Autonomous invariant discovery from failure signals; proposed invariants require HUMAN-0 ratification | `runtime/innovations30/invariant_discovery.py` | `tests/test_phase116_ide.py` | `artifacts/governance/phase116/` | `pytest tests/test_phase116_ide.py` |
| INNOV-32 · CRTV | Cryptographically governed constitutional rollback; rollback requires HUMAN-0 gate; chain-verified | `runtime/innovations30/constitutional_rollback.py` | `tests/test_phase117_crtv.py` | `artifacts/governance/phase117/` | `pytest tests/test_phase117_crtv.py` |
| INNOV-33 · KBEP | Standardized, cryptographically verified knowledge bundle exchange across federation members | `runtime/innovations30/knowledge_bundle_exchange.py` | `tests/test_phase118_kbep.py` | `artifacts/governance/phase118/` | `pytest tests/test_phase118_kbep.py` |
| INNOV-34 · FGCON | Formal consensus protocol for federation-wide constitutional amendments; strict majority quorum | `runtime/innovations30/federation_governance_consensus.py` | `tests/test_phase119_fgcon.py` | `artifacts/governance/phase119/` | `pytest tests/test_phase119_fgcon.py` |
| INNOV-35 · SPIE | System proposes its own next innovations from failure and gap signals; HUMAN-0 ratification required | `runtime/innovations30/self_proposing_innovation_engine.py` | `tests/test_phase120_spie.py` | `artifacts/governance/phase120/` | `pytest tests/test_phase120_spie.py` |

---

## Deterministic Audit Sandbox (Phase 121 · INNOV-36)

| Claim | Module | Test file | Artifact | Verify |
|---|---|---|---|---|
| Epoch replay is bit-identical from stored JSONL alone (DAS-DETERM-0) | `runtime/innovations30/deterministic_audit_sandbox.py` | `tests/test_phase121_das.py` | `artifacts/governance/phase121/` | `python scripts/replay_epoch.py artifacts/governance/phase121/das_ledger.jsonl` |
| HMAC-SHA256 chain detects any single-byte tampering (DAS-CHAIN-0) | `runtime/innovations30/deterministic_audit_sandbox.py` | `tests/test_phase121_das.py` | `artifacts/governance/phase121/` | `python scripts/verify_ledger.py artifacts/governance/phase121/das_ledger.jsonl` |
| External party can verify without ADAAD codebase knowledge (DAS-VERIFY-0) | `scripts/verify_ledger.py` | `tests/test_phase121_das.py` | `artifacts/governance/phase121/DEMO.md` | `docker compose up das-verify` |
| One-command reproducible demo with no API keys (DAS-DOCKER-0) | `Dockerfile.demo`, `docker-compose.yml` | `tests/test_phase121_das.py` | `DEMO.md` | `docker compose up das-demo` |

---

## Ledger and chain integrity claims

| Claim | Enforcement | Verification |
|---|---|---|
| Append-only JSONL ledger — no record can be deleted without chain break | `_flush_record()` in each ledger-bearing module | `python scripts/verify_ledger.py <ledger_path>` |
| Chain links are HMAC-SHA256 keyed on `(record_id + prev_digest)` | All `_compute_chain_link()` implementations | Read any `*.jsonl` ledger and inspect `chain_link` field |
| Genesis record has a fixed sentinel prev_digest (`0000...0000`) | All ledger implementations | Inspect first record in any JSONL ledger |
| Every governance artifact has a phase sign-off with epoch_id and ILA identifier | `artifacts/governance/phaseNNN/phaseNNN_sign_off.json` | `cat artifacts/governance/phase121/phase121_sign_off.json` |

---

## HUMAN-0 gate claims

| Claim | Enforcement | Verification |
|---|---|---|
| GPG-signed tag required for every GA version promotion | `KEY_CEREMONY_RUNBOOK_v1.md` | `git tag -v <tag>` — verifies against key `4C95E2F99A775335B1CF3DAF247B015A1CCD95F6` |
| HUMAN-0 boundary cannot be delegated via chat instruction | Architectural — no code path exists for verbal delegation | See `docs/governance/agent_contract_v1.md` |
| Patent and IP decisions are HUMAN-0-only | Explicitly listed in `HUMAN-0` role constraints | `docs/governance/LANE_OWNERSHIP.md` |

---

## What is not claimed here

The following are **not** claimed as independently verified:

- External peer review of constitutional invariants (as of v9.55.0, no published peer review exists)
- Third-party security audit of the GPG key ceremony
- Formal verification of the CEL state machine
- Regulatory certification of any kind

These items are tracked in `docs/governance/V1_GA_READINESS_CHECKLIST.md`.

---

*This document is regenerated each phase. Additions require a corresponding test and governance artifact.*
*Authority: DEVADAAD (Track A) under HUMAN-0 ratification.*
