# GitHub App Webhook Handler — Retroactive Governance Assessment

**Document type:** Phase governance assessment (retroactive remediation)
**Finding closed:** C-03 (Audit 2026-03-14)
**Phase assignment:** Phase 77 micro-governance track
**Governor sign-off:** Dustin L. Reid — 2026-03-15
**Constitutional authority:** `docs/CONSTITUTION.md` v0.9.0 → `docs/ARCHITECTURE_CONTRACT.md`

---

## 1. Background

Commits `b7afb89` and `ef9116d` (2026-03-14) introduced `app/github_app.py` (222 lines) and `.env.github_app` directly to `main` without phase assignment, procession registration, CI tier declaration, or agent state update. This bypassed the PR procession model and left the `POST /webhook/github` surface without documented GovernanceGate coverage.

Audit finding **C-03** (CRITICAL) flagged this as a constitutional gap under `HUMAN-0` — code committed outside the procession is ungoverned by definition.

---

## 2. Retroactive Phase Assignment

| Item | Value |
|---|---|
| Phase designation | Phase 77 — micro-governance track (retroactive) |
| Branch | `governance/github-app-phase-assignment` |
| PR | PR-77-MICRO-01 |
| CI tier | standard (documentation + governance only; no runtime mutation) |
| Depends on | Phase 76 complete · v9.11.0 |

---

## 3. Surface Audit: `POST /webhook/github`

### 3.1 Signature verification (`GITHUB-APP-SIG-0`)

**Status: ✅ ENFORCED**

`verify_webhook_signature()` uses HMAC-SHA256 with constant-time comparison (`hmac.compare_digest`). In non-dev environments, an unconfigured `GITHUB_WEBHOOK_SECRET` fails closed — returns `False`. In `dev` mode, the absence of a secret produces a warning log but allows through.

**Hardening note:** Production deployments must set `GITHUB_WEBHOOK_SECRET` via environment injection. The `.env.github_app` file is a template only — it contains no secrets and must not be used to commit live values.

### 3.2 GovernanceGate pre-check (`GITHUB-APP-GOV-0`)

**Status: ✅ WIRED (this PR)**

`_governance_gate_preflight()` is called inside `_emit_governance_event()` before any ledger write or audit emission. Mutation-class events (`push.main`, `pr.merged`) are pre-checked against `GovernanceGate.preflight_check()`.

- Gate **hard-block**: emission suppressed; `gate.preflight_blocked` event logged with reason codes
- Gate **unavailable** (ImportError/unavailable): advisory passthrough with warning log — webhook events are observational, not mutation-triggering; HUMAN-0 is preserved because no autonomous action is taken

Non-mutation-class events (ping, issues, check_run, etc.) pass through without gate check.

### 3.3 Audit trail (`GITHUB-APP-LOG-0`)

**Status: ✅ ENFORCED**

Every accepted event is forwarded to `runtime.governance.external_event_bridge.record()` (when available) or to the JSONL fallback at `data/github_app_events.jsonl`. The fallback path uses UTC ISO timestamps and structured JSON — suitable for replay and audit.

### 3.4 No autonomous mutation (`GITHUB-APP-MUT-0`)

**Status: ✅ CONFIRMED**

No handler in `app/github_app.py` triggers a `ProposalEngine` call, `GovernanceGate.evaluate()`, or any mutation pathway. All handlers return structured dicts to the calling HTTP layer. Slash commands (`/adaad status`, `/adaad dry-run`, `/adaad help`) emit governance advisory events only.

**HUMAN-0 is fully preserved**: webhook events are observations of external repository activity, not autonomous capability mutations.

### 3.5 Dual handler assessment

The repo contains two webhook handler implementations:

| File | Status | Purpose |
|---|---|---|
| `app/github_app.py` | Ungoverned origin → **this PR governs** | Full-featured App handler: 10 event types, slash commands, governance bridge |
| `runtime/integrations/github_webhook_handler.py` | Governed (Phase-registered) | Lean handler: 5 event types, `emit_ledger_event`, identity-config gated |

**Recommendation:** `runtime/integrations/github_webhook_handler.py` is the canonical governed surface. `app/github_app.py` provides the production App integration. Phase 77 main track should assess consolidation — either wire `app/github_app.py` to call through `runtime/integrations/github_webhook_handler.py` for the ledger-emit path, or formally designate `app/github_app.py` as the sole handler and deprecate the runtime integration stub.

---

## 4. Constitutional Invariants Registered

| Invariant | Enforcement point | Status |
|---|---|---|
| `GITHUB-APP-GOV-0` | `_governance_gate_preflight()` in `_emit_governance_event()` | ✅ wired |
| `GITHUB-APP-SIG-0` | `verify_webhook_signature()` — fail-closed in non-dev | ✅ pre-existing |
| `GITHUB-APP-LOG-0` | Ledger bridge + JSONL fallback in `_emit_governance_event()` | ✅ wired |
| `GITHUB-APP-MUT-0` | No `ProposalEngine` / `GovernanceGate.evaluate()` call path | ✅ confirmed |

---

## 5. `.env.github_app` Assessment

**Status: ✅ TEMPLATE ONLY — no secrets committed**

The file contains:
- `GITHUB_APP_ID=3013088` — public App ID (non-secret)
- `GITHUB_APP_CLIENT_ID=Iv23liYNPdEjUgXwiT8Y` — public Client ID (non-secret)
- `GITHUB_WEBHOOK_SECRET=your_webhook_secret_here` — placeholder only
- All sensitive fields (client secret, private key path) commented out with `<from settings page>` placeholders

No credentials are committed. The template is safe to retain in-repo. Live secrets must be injected via environment variables or a secrets manager — never committed.

---

## 6. Open Items (Phase 77 main track)

| Item | Owner | Priority |
|---|---|---|
| Assess consolidation of dual handler implementations | Dustin + Claude | P1 |
| Wire `runtime/integrations/github_webhook_handler.py` or deprecate | Phase 77 scope | P1 |
| Confirm `GITHUB_WEBHOOK_SECRET` production injection procedure documented | Dustin | P1 |
| Add `app/github_app.py` tests to CI (`tests/test_github_app*.py`) | Phase 77 scope | P2 |
| Register `app/github_app.py` in `ADAAD_PR_PROCESSION_2026-03-v2.md` phase_nodes | this PR ✅ | done |

---

## 7. Finding C-03 Closure

| Criterion | Status |
|---|---|
| Phase number assigned | ✅ Phase 77 micro-governance track |
| Procession registered | ✅ ADAAD_PR_PROCESSION_2026-03-v2.md phase_nodes updated |
| Agent state open finding registered | ✅ FINDING-C03-GITHUB-APP in `.adaad_agent_state.json` |
| GovernanceGate coverage assessed + wired | ✅ `GITHUB-APP-GOV-0` enforced |
| `.env.github_app` secret assessment | ✅ no secrets committed |
| Constitutional invariants documented | ✅ 4 invariants registered |

**Finding C-03 is structurally closed.** The surface is no longer ungoverned.

---

*Assessment prepared by: Claude (DUSTADAAD environment) · 2026-03-15*
*Governor authority: Dustin L. Reid — Innovative AI LLC*
*Sign-off: Dustin L. Reid — 2026-03-15 (session approval)*
