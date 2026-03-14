# ADAAD v1.0.0-GA Readiness Checklist

> **Authority:** This document is the canonical gate checklist for the `v1.0.0-GA` public-readiness tag.
> It is referenced by `docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md` § 2.2.
> **Last updated:** 2026-03-12 · **Status:** IN PROGRESS

---

## What v1.0.0-GA Is

`v1.0.0-GA` (General Availability) is the governed public-readiness milestone for ADAAD. It does **not** change the version series (currently `v7.x.x`) — it is a governance tag applied to a specific commit that has cleared every gate below. Once tagged, ADAAD is cleared for:

- Public announcement and community launch
- F-Droid listing activation
- External operator onboarding
- Claims/evidence matrix publication

---

## Gate 1 — CI Quality (Automated)

| Check | Command / Artifact | Status |
|---|---|---|
| All CI required checks green on release commit | `.github/workflows/ci.yml` — all jobs pass | ⏳ |
| Determinism test suite passes | `pytest tests/determinism/ -q` → 0 failures | ⏳ |
| Governance inviolability suite passes | `pytest tests/governance/inviolability/ -q` → 0 failures | ⏳ |
| CodeQL analysis green | `.github/workflows/codeql.yml` — no high/critical findings | ⏳ |
| SPDX header enforcement passes | `python scripts/check_spdx_headers.py` → 0 violations | ⏳ |
| Architecture snapshot valid | `python scripts/validate_architecture_snapshot.py` → pass | ⏳ |
| Release evidence complete | `python scripts/validate_release_evidence.py --require-complete` → pass | ⏳ |
| Release hardening claims valid | `python scripts/validate_release_hardening_claims.py` → pass | ⏳ |

---

## Gate 2 — Governance Documentation (Human-reviewed)

| Check | Artifact | Status |
|---|---|---|
| ROADMAP complete through Phase 51 | `ROADMAP.md` — Phase 52 shipped (`v7.6.0`), roadmap currently points to Phase 68 | ✅ |
| Procession doc v2 authored and committed | `docs/governance/ADAAD_PR_PROCESSION_2026-03-v2.md` | ✅ |
| Agent state synced to Phase 51 / v7.5.0 | `.adaad_agent_state.json` | ⏳ (done at Phase 51 commit) |
| Claims/evidence matrix — all rows `Complete` | `docs/comms/claims_evidence_matrix.md` | ✅ (verified at v7.4.0) |
| Constitution version correct throughout docs | `CONSTITUTION_VERSION = "0.7.0"` propagated | ✅ |
| Release notes exist for v7.0.0–v7.5.0 | `docs/releases/7.x.x.md` | ⏳ (7.5.0 needed) |

---

## Gate 3 — Android / F-Droid Distribution (Manual)

| Check | Notes | Status |
|---|---|---|
| F-Droid MR submitted | Submit at `https://gitlab.com/fdroid/fdroid-data/-/merge_requests` | ⏳ **MANUAL — Dustin** |
| F-Droid MR URL recorded | `android/fdroid/com.innovativeai.adaad.yml` has no embedded MR URL field; canonical MR submission endpoint is `https://gitlab.com/fdroid/fdroid-data/-/merge_requests` (explicit N/A for in-file URL) | ⏳ blocked on above |
| APK build pipeline green | `.github/workflows/android-free-release.yml` passes | ⏳ |
| `INSTALL_ANDROID.md` links valid | No broken install links | ✅ |
| Obtainium config valid | `android/obtainium.json` references correct release URL | ✅ |

---

## Gate 4 — Human Sign-off (Founder Gate — Hard Block)

| Check | Notes | Status |
|---|---|---|
| Founder reviews this checklist | All gates above inspected by Dustin | ⏳ |
| Founder GPG-signed commit to ledger | Commit message: `governance: v1.0.0-GA human sign-off — [DATE]` | ⏳ |
| Sign-off SHA recorded in procession doc v2 | Update § 2.3 of `ADAAD_PR_PROCESSION_2026-03-v2.md` | ⏳ |

> **Constitutional invariant HUMAN-0:** No governance milestone may be tagged without explicit human sign-off. This gate cannot be automated, delegated to an agent, or skipped.

---

## Gate 5 — Phase 52 Direction Ratified

| Check | Notes | Status |
|---|---|---|
| Phase 52 candidate selected | Selected: Governed Cross-Epoch Memory & Learning Store (recorded in `ROADMAP.md` Phase 52 section) | ✅ |
| Direction recorded in procession doc | `ADAAD_PR_PROCESSION_2026-03-v2.md` § 4 now records Phase 52 as ratified + shipped (`v7.6.0`) | ✅ |
| Phase 52 branch created from v7.5.0 HEAD | Historical closure recorded via shipped Phase 52 release state in roadmap/changelog (branch command N/A post-release) | ✅ (N/A — already shipped) |

---

## Gate 6 — Governance Strict Release Gate (Automated — Final)

| Check | Artifact | Status |
|---|---|---|
| `.github/workflows/governance_strict_release_gate.yml` terminal `release-gate` job passes | Must run on the GA tag commit | ⏳ |

> This gate runs automatically on tag push. All prior gates must be satisfied before pushing the `v1.0.0-GA` tag.

---

## Tagging Procedure (Final Step)

Once all 6 gates are cleared:

```bash
# On main at the GA-ready commit
git tag -a v1.0.0-GA -m "v1.0.0-GA — All governance gates cleared — Phase 51 complete — [DATE]"
git push origin v1.0.0-GA
```

The governance strict release gate workflow fires on tag push and performs terminal verification.

---

## Summary Status

| Gate | Description | Status |
|---|---|---|
| 1 | CI Quality (automated) | ⏳ |
| 2 | Governance Documentation | ⏳ (Phase 51 closes most items) |
| 3 | Android / F-Droid Distribution | ⏳ **F-Droid MR is hard block** |
| 4 | Human Sign-off (Founder Gate) | ⏳ **Hard block — cannot be automated** |
| 5 | Phase 52 Direction Ratified | ✅ |
| 6 | Governance Strict Release Gate | ⏳ (unblocked after Gates 1–5) |

**Current blocker:** Gates 3 and 4 require manual action from Dustin (F-Droid MR submission + GPG sign-off). Phase 52 ratification is already closed and evidenced; remaining automation proceeds after manual gates clear.
