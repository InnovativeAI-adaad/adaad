# ADAAD API v1 Reference

## Base URL
- Versioned namespace: `/api/v1`
- Compatibility namespace: `/api`

## Core System Endpoints
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/health` | `GET` | Service health, gate state, runtime profile |
| `/api/v1/version` | `GET` | Live version snapshot |
| `/api/v1/nexus/health` | `GET` | Nexus health with gate assertion |
| `/api/v1/nexus/handshake` | `GET` | Nexus protocol handshake metadata |
| `/api/v1/nexus/protocol` | `GET` | Protocol details and gate-cycle metadata |
| `/api/v1/nexus/agents` | `GET` | Registered agent inventory summary |

## Governance & Fast-Path (v1 aliases)
All existing `/api/governance/...` and `/api/fast-path/...` routes are exposed as `/api/v1/governance/...` and `/api/v1/fast-path/...` aliases.

## OpenAPI Schema
The complete machine-readable reference is committed at:

- `docs/api/openapi.v1.json`

Regenerate via:

```bash
python scripts/export_openapi.py
```

## Deprecation
Deprecation behavior is governed by:

- `docs/api/CHANGE_POLICY.md`
