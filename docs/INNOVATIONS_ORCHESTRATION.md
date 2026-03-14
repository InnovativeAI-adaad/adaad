# Phase 68 — Full Innovations Orchestration

**Status:** ✅ shipped (v9.3.0) · **Branch:** `phase68/full-innovations-orchestration` · **Tests:** T68-SEED-01..08, T68-ORC-01..04, T68-STR-01..03, T68-FED-01..03, T68-SRV-01..02

## Summary

Phase 68 completes the end-to-end orchestration of the ADAAD innovations substrate. The `ADAADInnovationEngine` and `CapabilitySeed` primitives (PR #420) and the CEL wiring layer (Phase 67) are now fully reachable through four bearer-auth-gated API endpoints and a seed lineage registration pipeline.

---

## New Capabilities

### 1. ADAAD Oracle API — `GET /innovations/oracle`

**Invariants:** ORACLE-AUTH-0, ORACLE-DETERM-0

Deterministic Q&A engine over the CEL evidence ledger. Reads `data/cel_evidence.jsonl` (configurable via `ADAAD_CEL_LEDGER` env var). Three built-in query templates:

| Query keyword | Type returned | Description |
|---------------|--------------|-------------|
| `divergence`  | `divergence_recent` | Last 10 divergence events |
| `rejected` / `reject` | `rejection_reasoning` | Last 20 rejected mutations with reasons |
| `performance` / `contributed` | `agent_contribution` | Agent ranking by cumulative fitness delta |

```http
GET /innovations/oracle?q=divergence&limit=100
Authorization: Bearer <audit:read token>
```

Response:
```json
{
  "query": "divergence",
  "event_window": 87,
  "answer": {
    "query_type": "divergence_recent",
    "count": 3,
    "events": [...]
  }
}
```

---

### 2. Aponi Story Mode — `GET /innovations/story-mode`

**Invariants:** ORACLE-AUTH-0, STORY-LEDGER-0

Renders CEL evidence ledger as a narrative arc timeline. Returns epoch arcs sorted chronologically, suitable for Aponi dashboard rendering. Read-only — no writes performed.

```http
GET /innovations/story-mode?limit=200
Authorization: Bearer <audit:read token>
```

Response:
```json
{
  "arc_count": 42,
  "arcs": [
    {"epoch": "epoch-001", "title": "Governance event", "agent": "architect", "decision": "none", "result": "promoted"},
    ...
  ],
  "engine_timeline": [...],
  "event_window": 42
}
```

---

### 3. Federated Evolution Map — `GET /innovations/federation-map`

**Invariants:** ORACLE-AUTH-0, FED-MAP-READONLY-0

Returns the cross-repo galaxy data: repositories as stars, mutation flows as paths, divergence events as flares. Suitable for rendering the Aponi federated visualization.

```http
GET /innovations/federation-map?limit=500
Authorization: Bearer <audit:read token>
```

Response:
```json
{
  "star_count": 3,
  "path_count": 7,
  "galaxy": {
    "stars": ["ADAAD", "repo-0", "repo-1"],
    "paths": [
      {"from": "ADAAD", "to": "repo-0", "state": "stable"},
      {"from": "ADAAD", "to": "repo-1", "state": "flare"}
    ]
  },
  "event_window": 87
}
```

---

### 4. Capability Seed Lineage — `POST /innovations/seeds/register` + `GET /innovations/seeds`

**Invariants:** ORACLE-AUTH-0, SEED-REG-0, SEED-IDEM-0, SEED-HASH-0

Seeds are registered as Tier-2 `CapabilityNode` entries in the in-process `CapabilityRegistry`. The node's telemetry carries the seed's `lineage_digest` for deterministic traceability.

**Register seeds:**
```http
POST /innovations/seeds/register
Authorization: Bearer <audit:read token>
Content-Type: application/json

[
  {
    "seed_id": "oracle-v1",
    "intent": "Build a deterministic query engine over evolutionary history",
    "scaffold": "def query(question, events): ...",
    "author": "operator",
    "lane": "governance"
  }
]
```

**List registered seeds:**
```http
GET /innovations/seeds
Authorization: Bearer <audit:read token>
```

---

## New Files

| File | Purpose |
|------|---------|
| `runtime/capability/seed_registry_adapter.py` | Seed → CapabilityNode adapter with idempotent bulk registration |
| `runtime/innovations_router.py` | FastAPI router for all four innovations endpoints |
| `tests/test_innovations_orchestration.py` | 20 tests (T68-SEED/ORC/STR/FED/SRV) |
| `docs/INNOVATIONS_ORCHESTRATION.md` | This document |

## Modified Files

| File | Change |
|------|--------|
| `server.py` | `innovations_router` imported and registered |

---

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `ADAAD_CEL_LEDGER` | `data/cel_evidence.jsonl` | Path to CEL evidence ledger for Oracle/Story/Federation reads |
| `ADAAD_AUDIT_TOKENS` | _(empty = allow all)_ | Comma-separated bearer tokens with audit:read scope |

---

## Constitutional Invariant Index

| Invariant | Description | Status |
|-----------|-------------|--------|
| ORACLE-AUTH-0 | All `/innovations/*` endpoints require audit:read bearer token | ✅ |
| ORACLE-DETERM-0 | Oracle answers deterministic for equal query + ledger state | ✅ |
| STORY-LEDGER-0 | Story Mode reads CEL ledger; no writes performed | ✅ |
| FED-MAP-READONLY-0 | Federation Map is read-only; no side effects | ✅ |
| SEED-REG-0 | Seeds registered as Tier-2 CapabilityNode entries | ✅ |
| SEED-IDEM-0 | Re-registering same seed_id is idempotent | ✅ |
| SEED-HASH-0 | node telemetry carries lineage_digest for traceability | ✅ |
| SEED-DEP-0 | Seeds carry no implicit dependencies; caller-supplied deps respect CAP-DEP-0 | ✅ |

---

## Full Innovations Stack Summary (Phases 420 → 67 → 68)

```
PR #420  ADAADInnovationEngine substrate (10 primitives)
Phase 67 CEL wiring: Vision Mode, Personality, G-Plugins, Self-Reflection
Phase 68 API endpoints: Oracle, Story Mode, Federation Map, Seed Registration
```

**Total innovations tests: 46 passing across all three phases.**
