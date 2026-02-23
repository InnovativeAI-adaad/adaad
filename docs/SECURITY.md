# Cryovant Key Handling ![Internal](https://img.shields.io/badge/Security-Internal-blue)

> This security note covers private-key handling and lineage ledger hygiene for ADAAD deployments.
> Follow these controls to avoid credential leakage and maintain deterministic forensic evidence chains.
> Use private reporting channels for vulnerabilities.

> **Doc metadata:** Audience: Operator / Auditor · Last validated release: `v1.0.0`

> ✅ **Do this:** Keep `security/keys/` owner-restricted and validate ledger writes through governance tooling.
>
> ⚠️ **Caveat:** Misconfigured filesystem permissions can silently expose signing material.
>
> 🚫 **Out of scope:** Never disclose vulnerabilities or key material in public issue trackers.

- `security/keys/` is created automatically on first run by Cryovant; if you need to provision it manually, run `mkdir -p security/keys` before setting owner-only permissions (`chmod 700 security/keys`).
Private keys MUST:
- Never be committed
- Never be world-readable
- Never be transmitted over unsecured channels
- Ledger writes are recorded in `security/ledger/lineage.jsonl` and mirrored to `reports/metrics.jsonl`.
