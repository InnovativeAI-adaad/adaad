# Access Control Matrix

## Purpose

This matrix describes logical access boundaries across governance, security, replay, and operational surfaces.

## Role Matrix

| Role / Actor | Read governance docs/evidence | Execute validation scripts | Trigger governed build (`ADAAD`) | Merge authority (`DEVADAAD`) | Modify governance-critical code |
| --- | --- | --- | --- | --- | --- |
| General contributor | Yes | Yes (local/CI) | No | No | Via reviewed PR only |
| Repository maintainer | Yes | Yes | Yes (workflow context) | No (unless explicitly authorized) | Via reviewed PR + gates |
| Authorized operator (merge authority) | Yes | Yes | Yes | Yes, only when all merge gates pass | Via reviewed PR + full gate stack |
| Autonomous governed agent | Yes | Yes (required) | Yes | Conditional, only under `DEVADAAD` trigger and passing Tier M | Within governed scope, fail-closed |

## Control Boundaries

| Surface | Control expectation | Technical anchor |
| --- | --- | --- |
| Governance mutation approval | GovernanceGate binding; advisory systems cannot self-approve | Security invariants + architecture contracts |
| Session/token validation | Cryptographic verification with strict-env controls | `security/cryovant.py` + invariants matrix |
| Replay verification | Deterministic replay checks and divergence fail-close | Replay validators + strict replay invariants |
| Federation trust | Trusted-key registry enforcement; reject unknown key IDs | Federation trust invariants |
| Merge execution | Full gate stack + merge attestation write before merge | DEVADAAD merge contract |

## Authentication and Authorization Notes

- Dev-mode token/signature allowances are explicitly restricted to declared development mode.
- Strict environments reject dev overrides and missing required signing key material.
- Human sign-off remains required for constitutionally protected amendment paths.

## Evidence-Linked Enforcement

- Security invariants source: `docs/governance/SECURITY_INVARIANTS_MATRIX.md`.
- Recovery/operator control points: `docs/governance/fail_closed_recovery_runbook.md`.
- Validation tooling anchors:
  - `scripts/validate_governance_schemas.py`
  - `scripts/validate_architecture_snapshot.py`
  - `tools/lint_import_paths.py`
  - `scripts/validate_release_evidence.py`
