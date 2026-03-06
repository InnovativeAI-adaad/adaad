## [SECURITY · AUTH · DETERMINISM] Production Auth Contract + Certifier Gate Hardening + Tier De-escalation Semantics

**Codex alignment:** Pre-PR-05 security gate / D-05 hardening prerequisite  
**Tier-map classification:** `critical` (Tier-0: `runtime/governance/**`, `runtime/evolution/**`; Tier-1: `security/**`, `tests/**`)  
**Target release:** v1.1.0-GA  
**Branch:** `feat/auth-contract-enforcement`

---

## Description

This PR closes three compounding security and governance gaps that were silently coexisting in v1.0.0:

1. **`GateCertifier.passed` excluded `token_ok`** — a file containing forbidden token primitives could pass certification provided its AST and imports were clean.
2. **`verify_session` is a deprecated no-op in production** — both `ArchitectGovernor` and `GateCertifier` were gating auth on a function that always returns `False` unless `CRYOVANT_DEV_TOKEN` is set.
3. **Deterministic-provider enforcement excluded `governance` and `critical` tiers** — the highest-severity operational states could silently produce non-reproducible evidence.

This PR also introduces a production-capable governance token contract (`cryovant-gov-v1`), enforces dev-mode gating for legacy static signatures, and normalizes `TierManager` de-escalation semantics with recovery-window gating.

---

## Change surface

| File | Change type | Governance impact |
|---|---|---|
| `adaad/agents/architect_governor.py` | Security fix | `verify_session` → `verify_governance_token` on refactor gate |
| `runtime/governance/gate_certifier.py` | Security fix | `token_ok` added to conjunctive `passed`; `verify_session` → `verify_governance_token` |
| `runtime/governance/foundation/determinism.py` | Enforcement expansion | `require_replay_safe_provider` covers `{audit, governance, critical}` |
| `runtime/evolution/entropy_discipline.py` | Enforcement expansion | `deterministic_context` covers `{audit, governance, critical}` |
| `security/cryovant.py` | Security fix + new contract | Legacy static sig gated to dev mode; `sign_governance_token` / `verify_governance_token` added |
| `tests/test_cryovant_dev_signatures.py` | Test hardening | Static sig rejection in prod, governance token round-trip, dev override gating |
| `tests/test_evolution_infrastructure.py` | New behavioral tests | `TierManager` de-escalation boundary tests |
| `docs/governance/*.md` | **NEW docs** | Security invariants, determinism contract, state machine normalization, auth contract, red-team plan |
| `CHANGELOG.md` | Fixed + Security sections | Auditable changelog entries for all three gap closures |
| `README.md`, `docs/README.md` | Enforcement changelog + doc index | Discovery surface updated |

---

## Root cause analysis

### Gap 1 — Certifier `passed` excluded `token_ok`

```python
# Before
passed = import_ok and ast_ok and auth_ok

# After
passed = import_ok and token_ok and ast_ok and auth_ok
```

### Gap 2 — `verify_session` deprecated/no-op in production

Governance-critical call sites were using a deprecated helper that is not production-capable by design.

### Gap 3 — Determinism guard excluded highest-severity tiers

`require_replay_safe_provider` and `deterministic_context` only enforced `audit` alias + strict mode, leaving `governance` and `critical` tiers unguarded.

### Gap 3a — Tier de-escalation timing not constrained

`TierManager` de-escalation now requires recovery-window elapsed time, preventing churn-based premature tier reductions.

---

## Security invariants activated

| Invariant | Before | After |
|---|---|---|
| `token_ok=false` → certification passes | **Yes** | No; reject + `forbidden_token_detected` |
| Governance-critical auth path uses `verify_session` | Yes | No; migrated to `verify_governance_token` |
| `cryovant-gov-v1` production token | Not implemented | Implemented (`sign_`/`verify_`) |
| `cryovant-static-*` in prod mode | Accepted | Rejected + audit event |
| Non-deterministic provider in `governance`/`critical` | Accepted | Rejected |
| Tier de-escalation before recovery window | Permitted | Blocked |

---

## Testing highlights

- Governance token verification round-trip + expiry rejection tests.
- Static signature acceptance in explicit dev mode and rejection in prod mode.
- Gate certifier test proving `token_ok` is load-bearing.
- Test proving governance-critical paths do not call deprecated `verify_session`.
- TierManager tests validating de-escalation only after recovery-window elapsed.

---

## CI gating

**Tier classification:** `critical`

Expected suites:
- `schema-validation` ✅
- `determinism-lint` ✅
- `confidence-fast` ✅
- `strict-replay` ✅
- `evidence-suite` ✅
- `promotion-suite` ✅

Reference: `docs/governance/ci-gating.md`

---

## Pre-merge sign-off gate

- [ ] `strict-replay` suite passed on this exact commit SHA
- [ ] `evidence-suite` forensic export event verified
- [ ] `promotion-suite` constitutional invariant checks clean
- [ ] Reviewer confirms `token_ok` is load-bearing in certifier `passed`
- [ ] Reviewer confirms no new governance call sites use `verify_session`
- [ ] Governance lead sign-off recorded (Tier-0 path modification)
