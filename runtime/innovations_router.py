# SPDX-License-Identifier: Apache-2.0
"""Phase 68 — Innovations API Router.

Exposes three bearer-auth-gated endpoints backed by ADAADInnovationEngine:

  GET  /innovations/oracle          — ADAAD Oracle: query evolutionary history
  GET  /innovations/story-mode      — Aponi Story Mode: CEL evidence as narrative arcs
  GET  /innovations/federation-map  — Federated Evolution Map galaxy data
  POST /innovations/seeds/register  — Capability Seed lineage registration

Constitutional invariants
=========================
ORACLE-AUTH-0       All endpoints require `audit:read` bearer token scope.
ORACLE-DETERM-0     Oracle answers are deterministic for equal query + events.
STORY-LEDGER-0      Story Mode reads CEL evidence ledger; no writes performed.
FED-MAP-READONLY-0  Federation Map is read-only; no side effects.
SEED-REG-0          Seeds registered via POST /innovations/seeds/register are
                    always Tier-2 (delegated to seed_registry_adapter).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Header

from runtime.capability.capability_registry import CapabilityRegistry
from runtime.capability.seed_registry_adapter import register_seeds_bulk
from runtime.innovations import ADAADInnovationEngine, CapabilitySeed
from runtime.audit_auth import require_audit_read_scope
from ui.features.story_mode import build_federated_evolution_map, build_story_arcs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/innovations", tags=["innovations"])

# Shared engine instance (stateless — no side effects on calls)
_engine = ADAADInnovationEngine()

# Shared in-process capability registry for seed registration
_seed_registry = CapabilityRegistry()


# ---------------------------------------------------------------------------
# Auth helper (mirrors pattern from server.py)
# ---------------------------------------------------------------------------

def _require_audit_read(authorization: Optional[str]) -> None:
    """Raise 401/403 if bearer token missing or scope not audit:read.

    ORACLE-AUTH-0: all innovations endpoints require audit:read scope.
    """
    require_audit_read_scope(authorization)


# ---------------------------------------------------------------------------
# Oracle event loader (reads CEL evidence ledger JSONL)
# ---------------------------------------------------------------------------

def _load_oracle_events(limit: int = 500) -> List[Dict[str, Any]]:
    """Load events from the CEL evidence ledger for Oracle queries.

    STORY-LEDGER-0: read-only; no writes performed.
    """
    import json

    ledger_path = Path(os.getenv("ADAAD_CEL_LEDGER", "data/cel_evidence.jsonl"))
    if not ledger_path.exists():
        return []
    events: List[Dict[str, Any]] = []
    try:
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("innovations_router: ledger read failed — %s", exc)
    return events


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/oracle")
def oracle_query(
    q: str = "divergence",
    limit: int = 100,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """ADAAD Oracle: deterministic Q&A over evolutionary history.

    ORACLE-AUTH-0: requires audit:read bearer token.
    ORACLE-DETERM-0: equal q + ledger state → equal answer.

    Query examples:
      ?q=divergence          — last 10 divergence events
      ?q=rejected            — last 20 rejected mutations
      ?q=performance         — agent contribution ranking
    """
    _require_audit_read(authorization)
    events = _load_oracle_events(limit=limit)
    answer = _engine.answer_oracle(q, events)
    return {
        "query": q,
        "event_window": len(events),
        "answer": answer,
    }


@router.get("/story-mode")
def story_mode(
    limit: int = 200,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Aponi Story Mode: CEL evidence ledger as narrative arc timeline.

    STORY-LEDGER-0: reads ledger, never writes.
    ORACLE-AUTH-0: requires audit:read bearer token.
    """
    _require_audit_read(authorization)
    events = _load_oracle_events(limit=limit)
    arcs = build_story_arcs(events)
    engine_arcs = _engine.story_mode(events)
    return {
        "arc_count": len(arcs),
        "arcs": arcs,
        "engine_timeline": engine_arcs,
        "event_window": len(events),
    }


@router.get("/federation-map")
def federation_map(
    limit: int = 500,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Federated Evolution Map: cross-repo event galaxy data.

    FED-MAP-READONLY-0: read-only. No side effects.
    ORACLE-AUTH-0: requires audit:read bearer token.

    Returns stars (repos), paths (mutation flows), divergence flares.
    """
    _require_audit_read(authorization)
    events = _load_oracle_events(limit=limit)
    galaxy = build_federated_evolution_map(events)
    return {
        "star_count": len(galaxy["stars"]),
        "path_count": len(galaxy["paths"]),
        "galaxy": galaxy,
        "event_window": len(events),
    }


@router.post("/seeds/register")
def register_seeds(
    seeds: List[Dict[str, Any]] = Body(default=[]),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Register Capability Seeds in the lineage ledger.

    SEED-REG-0: all seeds registered as Tier-2 nodes.
    SEED-IDEM-0: re-registering an existing seed_id is idempotent.
    ORACLE-AUTH-0: requires audit:read bearer token.

    Request body: list of seed objects:
      [{"seed_id": "...", "intent": "...", "scaffold": "...",
        "author": "...", "lane": "governance"}]
    """
    _require_audit_read(authorization)
    seed_objects: List[CapabilitySeed] = []
    parse_errors: List[Dict[str, Any]] = []

    for raw in seeds:
        try:
            seed_objects.append(CapabilitySeed(
                seed_id=str(raw["seed_id"]),
                intent=str(raw.get("intent", "")),
                scaffold=str(raw.get("scaffold", "")),
                author=str(raw.get("author", "operator")),
                lane=str(raw.get("lane", "experimental")),
            ))
        except Exception as exc:  # noqa: BLE001
            parse_errors.append({"raw": raw, "error": str(exc)})

    results = register_seeds_bulk(_seed_registry, seed_objects)
    registered = [r for r in results if r["registered"]]

    # Phase 70 — emit seed_planted frame for each new seed
    for seed in seed_objects:
        if any(r["seed_id"] == seed.seed_id and r["registered"] for r in results):
            try:
                from runtime.innovations_bus import emit_seed_planted  # noqa: PLC0415
                emit_seed_planted(seed.seed_id, seed.lane, seed.intent, seed.author)
            except Exception:  # noqa: BLE001
                pass

    return {
        "submitted": len(seeds),
        "registered": len(registered),
        "results": results,
        "parse_errors": parse_errors,
        "registry_size": len(_seed_registry.list_ids()),
    }


@router.get("/seeds")
def list_seeds(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """List all registered Capability Seeds (Tier-2 nodes with SEED-REG-0 tag).

    ORACLE-AUTH-0: requires audit:read bearer token.
    """
    _require_audit_read(authorization)
    seed_nodes = [
        {
            "capability_id": n.capability_id,
            "version": n.version,
            "description": n.contract.description,
            "tier": n.contract.tier,
            "tags": sorted(n.governance_tags),
            "telemetry": n.telemetry,
            "node_hash": n.node_hash,
        }
        for n in _seed_registry.list_nodes()
        if "SEED-REG-0" in n.governance_tags
    ]
    return {
        "seed_count": len(seed_nodes),
        "seeds": seed_nodes,
    }


__all__ = ["router"]
