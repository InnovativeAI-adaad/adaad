# PR-77-PLAN — Phase 77 Planning Gate

**Document type:** Phase Planning Gate (HUMAN-0 ratification required)
**Authored:** 2026-03-15 · ArchitectAgent
**Scope:** v9.11.0 → v9.12.0
**Constitutional authority:** CONSTITUTION.md v0.9.0 · ARCHITECTURE_CONTRACT.md · ARCHITECT_SPEC_v8.0.0.md
**Governor:** Dustin L. Reid · Innovative AI LLC

> **PHASE6-HUMAN-0**: This plan document is a proposal only. Phase 77
> implementation may not open until Dustin L. Reid explicitly ratifies
> the direction below and the `chore/state-align-phase76-77` PR is
> merged to main.

---

## 1 — Organism Status at Phase 77 Boundary

| Metric | Value |
|---|---|
| **Released version** | v9.11.0 |
| **Phases shipped** | 76 |
| **Test suite** | 437 test files / 4,649 tests |
| **PyPI** | `adaad 9.11.0` published |
| **Seed Lifecycle Pipeline** | ✅ Complete (Phases 71–76) — register → evolve → graduate → promote → review → propose → inject → record outcome |
| **Constitutional invariants active** | HUMAN-0, AUDIT-0, REPLAY-0, SEED-REVIEW-HUMAN-0, SEED-PROP-LEDGER-0, SEED-CEL-AUDIT-0, GATE-0, MEMORY-0, CEL-WIRE-FAIL-0, SEED-OUTCOME-0..IDEM-0 |
| **Open P0/P1 findings** | 4 active (see §3) |

### What Phase 76 completed

Phase 76 delivered the final ring in the Seed Lifecycle: `record_cel_outcome()` writes a `SeedCELOutcomeEvent` to `LineageLedgerV2` after every CEL epoch that ran with an injected seed proposal (Phase 75). The outcome (success / partial / failed / skipped) is idempotent on `(seed_id, cycle_id)`, deterministically hashed, and surfaced in the Aponi UI as a status-keyed toast. The full pipeline is now:

```
Seed registered → evolved (epoch hook) → graduation ceremony
  → FIFO promotion queue (SEED-PROMO-HUMAN-0 advisory)
  → operator review (record_review, SEED-REVIEW-HUMAN-0)
  → proposal bridge (build_proposal_request, SEED-PROP-LEDGER-0)
  → CEL Step 4 injection (inject_seed_proposal_into_context, SEED-CEL-AUDIT-0)
  → outcome recorded (record_cel_outcome, SEED-OUTCOME-AUDIT-0)  ← Phase 76
```

The organism can now complete and **audit** a full seed-to-capability evolution cycle end-to-end.

---

## 2 — Pre-Phase 77 Governance Blockers

The following items from the deep-dive audit (2026-03-14) remain open.
**CRITICAL items block Phase 77 implementation.** HIGH/MEDIUM items
must be tracked but do not block the implementation PR opening.

| ID | Severity | Status | Owner | Action |
|---|---|---|---|---|
| **FINDING-AUDIT-C02** | 🔴 CRITICAL | OPEN — Dustin (HUMAN-0 only) | Dustin (local git) | GPG-sign tags v9.7.0–v9.10.0 at exact SHAs (see §2.1). Latest non-founder attempt evidence: `artifacts/governance/phase91/HUMAN0_TAG_CEREMONY_2026-03-26.md` (`No secret key`). |
| **FINDING-AUDIT-C03** | 🔴 CRITICAL | OPEN — Phase 77 | Dustin + Claude | GitHub App governance — Phase 77 primary scope (see §4) |
| **FINDING-66-003** | 🔴 P1 | OPEN — legal | Dustin (counsel) | Patent provisional filing — clock running since v1.1-GA |
| **FINDING-AUDIT-H04** | 🟡 HIGH | OPEN — Dustin | Dustin | GA versioning clarification (v1.0.0-GA vs v1.1-GA) |
| `CONSTITUTION_VERSION = "0.7.0"` | 🟡 HIGH | NEW | Claude (Phase 77) | Runtime code constant still reads 0.7.0; doc header fixed to 0.9.0 in state-align PR; code must follow |
| free-v9.11.0 tag | 🟡 MEDIUM | OPEN | Dustin | `git tag free-v9.11.0 && git push origin free-v9.11.0` triggers APK/PWA pipeline |
| GA checklist (M-03) | 🟡 MEDIUM | STALE | Claude + Dustin | V1_GA_READINESS_CHECKLIST.md frozen at v7.5.0 / Phase 51 baseline |

### 2.1 — Tag Ceremony Reference (Dustin, local)

Execute before or alongside Phase 77 opening:

```bash
git tag -s v9.7.0  0fab652219cd6ca4e7832d81fb512f298d0812a6 \
         -m "Phase 72: Seed Promotion Queue + Graduation UI (v9.7.0)"

git tag -s v9.8.0  93911830513d41422b7d676829c15ea59fec7c9c \
         -m "Phase 73: Seed Review Decision + Governance Wire (v9.8.0)"

git tag -s v9.9.0  b783a4a0f14a1eddc0a133f81e8d31c07e76ea68 \
         -m "Phase 74: Seed-to-Proposal Bridge (v9.9.0)"

git tag -s v9.10.0 4abfe5fc1611d49e5386dd803ee8bf656e1bdb06 \
         -m "Phase 75: Seed Proposal CEL Injection (v9.10.0)"

git push origin v9.7.0 v9.8.0 v9.9.0 v9.10.0
```

---

## 3 — Phase 77 Direction: Candidate Slate

Three directions are presented for Dustin's ratification. They are
not mutually exclusive — the recommendation (§5) proposes a split-track
model.

---

### Direction A — GitHub App Governance Integration *(P0 — closes C-03)*

**Rationale:** `app/github_app.py` (223 lines) and
`runtime/integrations/github_webhook_handler.py` were committed to main
outside the PR procession (commits `b7afb89`, `c0e5528`, `ef9116d`).
This is a Constitutional HUMAN-0 gap. The `POST /webhook/github`
endpoint is not registered in `app/main.py`, not gated by
`GovernanceGate`, and `runtime/governance/external_event_bridge` does
not exist — so all governance events fall back to a JSONL flat file at
`data/github_app_events.jsonl`. The integration has no audit trail in
the evolution ledger.

**Deliverables:**

| # | Item | Invariant |
|---|---|---|
| A-01 | Register `POST /webhook/github` in `app/main.py` router with HMAC-verified, fail-closed signature gate | HUMAN-0 surface closure |
| A-02 | Implement `runtime/governance/external_event_bridge.py` — `record(event_name, data)` writes `GitHubAppEvent` to `LineageLedgerV2` with deterministic digest | GITHUB-AUDIT-0 |
| A-03 | Wire `GovernanceGate` observability: GitHub App events with governance-relevant action types (`push.main`, `pr.merged`, `ci.failure`) emit `ExternalGovernanceSignal` readable by the gate health aggregator | GITHUB-GATE-OBS-0 |
| A-04 | `CONSTITUTION_VERSION` runtime constant updated `"0.7.0"` → `"0.9.0"` in `runtime/constitution.py`, `runtime/autonomy/epoch_memory_store.py`, `runtime/evolution/evolution_loop.py` | M-01 code-side closure |
| A-05 | Phase 77 procession entry, governance artifact `artifacts/governance/phase77/github_app_signoff.json` (HUMAN-0 signed) | Procession compliance |
| A-06 | Test suite: `tests/test_phase77_github_app_governance.py` — HMAC verification, ledger write, gate signal, fallback path, idempotency on duplicate delivery | ≥20 tests |

**Version bump:** `9.11.0 → 9.12.0`
**CI tier:** Tier 1 (Stable — runtime/governance path touches)
**Risk:** LOW — `app/github_app.py` is already written and HMAC-verified; this phase governs it, it does not rewrite it.

---

### Direction B — GA Readiness Full Refresh *(P1 — closes M-03, M-02, L-02)*

**Rationale:** `V1_GA_READINESS_CHECKLIST.md` is frozen at v7.5.0 / Phase
51. The system shipped 25 phases and a full major version series since.
v1.1-GA was tagged without Gate 4 Founder GPG sign-off being confirmed.
F-Droid MR was never submitted. Release notes for v9.1.0–v9.11.0 do not
have confirmed existence. The distribution tag pipeline (`free-v*`) has
no v9.x entry.

**Deliverables:**

| # | Item | Owner |
|---|---|---|
| B-01 | Full refresh of `V1_GA_READINESS_CHECKLIST.md` against v9.11.0 — verify all CI gates, re-evaluate Gate 2 doc state, Gate 3 F-Droid status, Gate 4 sign-off status | Dustin + Claude |
| B-02 | Author `docs/releases/` stubs for v9.1.0–v9.11.0 (11 release notes) | Claude |
| B-03 | Clarify and document canonical GA tag: v1.0.0-GA vs v1.1-GA. Update `ADAAD_PR_PROCESSION_2026-03-v2.md` §2.3 with decision and sign-off SHA | Dustin |
| B-04 | Trigger `free-v9.11.0` distribution tag to activate APK + PWA pipeline | Dustin (local) |
| B-05 | Submit F-Droid MR at `https://gitlab.com/fdroid/fdroid-data/-/merge_requests` | Dustin (manual) |
| B-06 | Archive the superseded 2026-03-13 Phase 65 completion plan to `archives/plans/` | Claude |

**Version bump:** Docs-only — no runtime version increment. Could be bundled with A as `9.12.0`.
**CI tier:** Tier 2 (Docs / governance docs only)
**Risk:** LOW — documentation only.

---

### Direction C — `CONSTITUTION_VERSION` Runtime Code Alignment *(HIGH — standalone micro-PR)*

**Rationale:** Even after the `chore/state-align-phase76-77` commit
fixes the `CONSTITUTION.md` header, the runtime code contains hardcoded
`"0.7.0"` in three places:

```
runtime/constitution.py:133          CONSTITUTION_VERSION = "0.7.0"
runtime/autonomy/epoch_memory_store.py:240,268   "0.7.0"
runtime/evolution/evolution_loop.py:1008         "0.7.0"
```

These values flow into `EpochEvidence`, `EpochRecord`, and governance
health snapshots — meaning every CEL epoch has been stamping evidence
artifacts with the wrong constitutional version since Phase 63. This can
be packaged as a fast micro-PR inside Phase 77-A or as a standalone
`fix/constitution-version-0.9.0` PR.

**Deliverables:**

| # | Item |
|---|---|
| C-01 | `runtime/constitution.py` line 133: `"0.7.0"` → `"0.9.0"` |
| C-02 | `runtime/autonomy/epoch_memory_store.py` lines 240, 268: default fallback `"0.7.0"` → `"0.9.0"` |
| C-03 | `runtime/evolution/evolution_loop.py` line 1008: hardcoded `"0.7.0"` → `"0.9.0"` |
| C-04 | Update `CONSTITUTION_VERSION` propagation note in `docs/governance/V1_GA_READINESS_CHECKLIST.md` Gate 2 (was `"0.7.0"`) |
| C-05 | Test: confirm `EpochEvidence.constitution_version` emitted as `"0.9.0"` in CEL step evidence |

**Version bump:** `9.11.0 → 9.12.0` (bundled with A) or patch `9.11.1` if standalone.
**CI tier:** Tier 1 (runtime touch)
**Risk:** VERY LOW — string constant only; no behavioral change.

---

## 4 — Recommended Phase 77 Structure

The recommendation is a **two-track Phase 77**:

### Track 1 — PR-77-GOVERN (fast-track, unblocks everything)

Bundle Directions A + C into a single governed PR:

1. `external_event_bridge.py` — new module
2. `POST /webhook/github` router registration
3. GovernanceGate observability wiring
4. `CONSTITUTION_VERSION` constant aligned across 3 files
5. Phase 77 governance artifact + HUMAN-0 sign-off
6. ≥25 tests

**Branch:** `feat/phase77-github-app-governance`
**Version:** `9.11.0 → 9.12.0`
**Closes:** C-03, FINDING-AUDIT-C03, M-01 (code side)

### Track 2 — PR-77-GA-REFRESH (docs, can open in parallel)

Direction B as a pure documentation PR. No runtime version bump.
GA checklist refresh, release notes, archive, procession §2.3 clarification.

**Branch:** `docs/phase77-ga-refresh`
**Closes:** M-02 trigger note, M-03, L-01, L-02, FINDING-AUDIT-H04 (if Dustin confirms)

---

## 5 — Evidence Matrix (pre-populated for Phase 77-GOVERN)

To be completed during Phase 77 implementation. Governor sign-off
required before version tag.

| ID | Artifact | Gate | Status |
|---|---|---|---|
| E77-01 | `artifacts/governance/phase77/github_app_signoff.json` | HUMAN-0 | ⏳ |
| E77-02 | `runtime/governance/external_event_bridge.py` — `record()` determinism verified | GITHUB-AUDIT-0 | ⏳ |
| E77-03 | `GovernanceGate` health snapshot includes `github_app_signal_count` | GITHUB-GATE-OBS-0 | ⏳ |
| E77-04 | `runtime/constitution.py` `CONSTITUTION_VERSION == "0.9.0"` | M-01 code closure | ⏳ |
| E77-05 | `tests/test_phase77_github_app_governance.py` — ≥25 passing | CI-0 | ⏳ |
| E77-06 | `POST /webhook/github` HMAC rejection test passes | HMAC-FAIL-CLOSED | ⏳ |
| E77-07 | FINDING-AUDIT-C03 status → `resolved` in agent state | State integrity | ⏳ |

---

## 6 — Constitutional Invariants Introduced in Phase 77

| Invariant ID | Rule | Enforcement Point |
|---|---|---|
| **GITHUB-AUDIT-0** | Every GitHub App event must be written to `LineageLedgerV2` as `GitHubAppEvent` before `_emit_governance_event()` returns. JSONL fallback is permitted only when ledger module is unavailable; fallback path must log a WARNING. | `external_event_bridge.record()` |
| **GITHUB-GATE-OBS-0** | GitHub App events with governance-relevant action types (`push.main`, `pr.merged`, `ci.failure`, `slash_command`) must emit an `ExternalGovernanceSignal` readable by `GovernanceHealthAggregator`. Gate observability must not depend on a live GitHub connection. | `github_app.py` dispatch path |
| **HMAC-FAIL-CLOSED** | `verify_webhook_signature()` must return `False` (and log at ERROR) in any non-dev environment where `GITHUB_WEBHOOK_SECRET` is absent. `ADAAD_ENV != "dev"` is the authority check. Already implemented — Phase 77 adds test coverage and router-level enforcement. | `app/github_app.py:verify_webhook_signature()` |

---

## 7 — Phase 77 CI Tier Declaration

| Tier | Trigger | Rationale |
|---|---|---|
| **Tier 0** | Not applicable | No Tier 0 paths modified |
| **Tier 1** | `runtime/governance/external_event_bridge.py`, `runtime/constitution.py`, `runtime/autonomy/epoch_memory_store.py`, `runtime/evolution/evolution_loop.py` | Core governance runtime — full test suite required |
| **Tier 2** | `app/main.py` router addition, `app/github_app.py` wiring | Application layer |
| **Tier 3** | `docs/`, `artifacts/` | Governance documentation |

---

## 8 — Ratification Block (Dustin — HUMAN-0)

```
Phase 77 Direction Ratification
────────────────────────────────────────────────────────────
Governor:           Dustin L. Reid · Innovative AI LLC
Ratification date:  ___________
Selected direction: [ ] A+C (Track 1 — Governance Integration)
                    [ ] B   (Track 2 — GA Refresh only)
                    [ ] A+B+C (Full Phase 77 — both tracks)
                    [ ] Other: ___________

Track 1 branch:     feat/phase77-github-app-governance
Track 2 branch:     docs/phase77-ga-refresh

Signature:          ___________
Notes:              ___________
────────────────────────────────────────────────────────────
```

*No implementation PR may open until this block is signed.*

---

*Document prepared by: ArchitectAgent (DUSTADAAD environment) · 2026-03-15*
*Pending merge of: `chore/state-align-phase76-77` (PR open on GitHub)*
