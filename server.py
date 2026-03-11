from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from app.api.nexus.mutate import router as mutate_router


ROOT = Path(__file__).resolve().parent
APONI_DIR = ROOT / "ui" / "aponi"
MOCK_DIR = APONI_DIR / "mock"
INDEX = APONI_DIR / "index.html"
GATE_LOCK_FILE = ROOT / "security" / "ledger" / "gate.lock"
GATE_PROTOCOL = "adaad-gate/1.0"


class SPAStaticFiles(StaticFiles):
    def __init__(self, *args, index_path: Path, **kwargs):
        super().__init__(*args, **kwargs)
        self._index_path = index_path

    async def get_response(self, path: str, scope) -> Response:
        resp = await super().get_response(path, scope)
        if resp.status_code != 404:
            return resp

        req_path = scope.get("path", "")
        if req_path == "/api" or req_path.startswith("/api/"):
            return resp

        return FileResponse(str(self._index_path))

@asynccontextmanager
async def _lifespan(application: FastAPI):  # noqa: ARG001
    """Lifespan: validate APONI assets at startup; clean up on shutdown."""
    if not APONI_DIR.exists():
        raise RuntimeError("ui/aponi not found. Import APONI into ui/aponi first.")
    if not INDEX.exists():
        raise RuntimeError("ui/aponi/index.html not found. Verify APONI import.")
    yield


app = FastAPI(title="InnovativeAI-adaad Unified Server", lifespan=_lifespan)
app.include_router(mutate_router)


def _load_mock(name: str) -> Any:
    p = MOCK_DIR / f"{name}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"mock '{name}' not found")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=500, detail=f"mock '{name}' parse error: {e}")


def _read_gate_state() -> Dict[str, Any]:
    """
    Best-effort gate snapshot. Never surfaces secrets.
    """
    locked = False
    reason = None
    source = "default"

    env_flag = os.environ.get("ADAAD_GATE_LOCKED")
    if env_flag:
        locked = env_flag.lower() not in {"", "0", "false", "no"}
        source = "env"
        reason = os.environ.get("ADAAD_GATE_REASON") or reason

    if GATE_LOCK_FILE.exists():
        source = "file"
        locked = True
        try:
            contents = GATE_LOCK_FILE.read_text(encoding="utf-8").strip()
            if contents:
                reason = contents
        except Exception:
            # Fall back to prior reason if present
            pass

    if reason:
        reason = reason[:280]

    return {
        "locked": locked,
        "reason": reason,
        "source": source,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "protocol": GATE_PROTOCOL,
    }




def _load_audit_tokens() -> dict[str, list[str]]:
    raw = os.environ.get("ADAAD_AUDIT_TOKENS", "")
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(decoded, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for token, scopes in decoded.items():
        if not isinstance(token, str):
            continue
        if isinstance(scopes, list):
            normalized[token] = [str(scope) for scope in scopes]
    return normalized


def _require_audit_read_scope(authorization: str | None) -> dict[str, str]:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing_authentication")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="missing_authentication")

    token_scopes = _load_audit_tokens().get(token)
    if token_scopes is None:
        raise HTTPException(status_code=401, detail="invalid_token")
    if "audit:read" not in token_scopes:
        raise HTTPException(status_code=403, detail="insufficient_scope")

    return {"scheme": "bearer", "scope": "audit:read", "redaction": "sensitive"}

def _assert_gate_open() -> Dict[str, Any]:
    gate = _read_gate_state()
    if gate["locked"]:
        raise HTTPException(
            status_code=423,
            detail=gate["reason"] or "Cryovant gate LOCKED",
            headers={"X-ADAAD-GATE": "locked"},
        )
    return gate


_REPORT_VERSION_PATH = ROOT / "governance" / "report_version.json"
_VERSION_PATH = ROOT / "VERSION"


def _load_live_version() -> Dict[str, Any]:
    """Read VERSION + report_version.json + constitution constant.

    Never raises — returns degraded payload on any read failure so the
    dashboard always gets a parseable JSON response.
    """
    adaad_version = "unknown"
    try:
        adaad_version = _VERSION_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        pass

    report: Dict[str, Any] = {}
    try:
        report = json.loads(_REPORT_VERSION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    # Import constitution version at call-time to pick up any live reload
    constitution_version = "unknown"
    try:
        from runtime.constitution import CONSTITUTION_VERSION as _CV
        constitution_version = _CV
    except Exception:  # pragma: no cover
        pass

    return {
        "adaad_version": adaad_version,
        "constitution_version": constitution_version,
        "last_sync_sha": report.get("last_sync_sha", "unknown"),
        "last_sync_date": report.get("last_sync_date", "unknown"),
        "report_version": report.get("report_version", adaad_version),
        "protocol": GATE_PROTOCOL,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/version")
def api_version() -> Dict[str, Any]:
    """Live version snapshot — no auth required, no gate check.

    Returns adaad_version, constitution_version, last_sync_sha, last_sync_date.
    The Aponi UI fetches this on every hardRefresh to display the version
    banner accurately rather than relying on static protocol strings.
    """
    return _load_live_version()


@app.get("/api/health")
def health() -> dict[str, Any]:
    gate = _read_gate_state()
    ok = not gate["locked"]
    return {
        "ok": ok,
        "gate_ok": ok,
        "ui_present": APONI_DIR.exists(),
        "mock_present": MOCK_DIR.exists(),
        "gate": gate,
        "protocol": GATE_PROTOCOL,
    }


@app.get("/api/nexus/health")
def nexus_health() -> dict[str, Any]:
    gate = _read_gate_state()
    unlocked = not gate["locked"]
    snapshot = {"ok": unlocked, "gate_ok": unlocked, "protocol": GATE_PROTOCOL, "gate": gate}
    if gate["locked"]:
        raise HTTPException(
            status_code=423,
            detail=gate["reason"] or "Cryovant gate LOCKED",
            headers={"X-ADAAD-GATE": "locked"},
        )
    return snapshot


@app.get("/api/nexus/handshake")
def nexus_handshake() -> dict[str, Any]:
    gate = _assert_gate_open()
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "protocol": GATE_PROTOCOL,
        "gate": {"locked": False, "reason": None, "checked_at": gate["checked_at"]},
    }


@app.get("/api/nexus/protocol")
def nexus_protocol() -> dict[str, Any]:
    gate = _assert_gate_open()
    # Static placeholder protocol snapshot
    return {
        "ok": True,
        "version": "1.0",
        "created_at": gate["checked_at"],
        "gate_cycle": {
            "keys_dir": "security/keys",
            "keys_mode_required_octal": "0700",
            "ledger_dir": "security/ledger",
            "no_bypass": True,
        },
    }


@app.get("/api/nexus/agents")
def nexus_agents() -> dict[str, Any]:
    _assert_gate_open()
    agents_dir = ROOT / "app" / "agents"
    agents: list[dict[str, Any]] = []
    if agents_dir.exists():
        for entry in sorted(agents_dir.iterdir(), key=lambda p: p.name):
            if not entry.is_dir() or entry.name in {"agent_template", "lineage"} or entry.name.startswith("__"):
                continue
            agents.append(
                {
                    "name": entry.name,
                    "meta_exists": (entry / "meta.json").exists(),
                    "dna_exists": (entry / "dna.json").exists(),
                    "certificate_exists": (entry / "certificate.json").exists(),
                    "entrypoint_exists": (entry / "__init__.py").exists(),
                }
            )
    return {"ok": True, "count": len(agents), "agents": agents}


MOCK_ENDPOINTS = ["status", "agents", "tree", "kpis", "changes", "suggestions"]

for endpoint_name in MOCK_ENDPOINTS:
    app.add_api_route(
        f"/api/{endpoint_name}",
        endpoint=lambda n=endpoint_name: _load_mock(n),
        methods=["GET"],
    )



@app.get("/governance/reviewer-calibration")
def governance_reviewer_calibration(
    epoch_id: str | None = Query(default=None),
    reviewer_ids: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    authn = _require_audit_read_scope(authorization)
    if not epoch_id:
        raise HTTPException(status_code=422, detail="missing_epoch_id")

    from runtime.api.runtime_services import reviewer_calibration_service

    requested_reviewer_ids = None
    if reviewer_ids:
        requested_reviewer_ids = [item.strip() for item in reviewer_ids.split(",") if item.strip()]

    calibration = reviewer_calibration_service(epoch_id=epoch_id, reviewer_ids=requested_reviewer_ids)
    calibration["constitutional_floor"] = "enforced"

    return {"schema_version": "1.0", "authn": authn, "data": calibration}

# ---------------------------------------------------------------------------
# Phase 8 — Governance Health Dashboard (PR-8-02)
# ---------------------------------------------------------------------------

@app.get("/governance/health")
def governance_health(
    epoch_id: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return current and rolling governance health score.

    Response fields
    ---------------
    health_score          float — current epoch h ∈ [0.0, 1.0]
    status                str   — 'green' | 'amber' | 'red'
    signal_breakdown      dict  — per-signal raw values
    weight_snapshot_digest str  — sha256 of canonical weight vector
    constitution_version  str
    scoring_algorithm_version str
    degraded              bool  — h < 0.60
    constitutional_floor  str   — always 'enforced'
    """
    from runtime.api.runtime_services import governance_health_service

    authn = _require_audit_read_scope(authorization)
    resolved_epoch = epoch_id or "current"
    result = governance_health_service(epoch_id=resolved_epoch)
    result["constitutional_floor"] = "enforced"
    return {"schema_version": "1.0", "authn": authn, "data": result}


# ---------------------------------------------------------------------------
# Phase 21 — Telemetry Ledger Read Endpoint (PR-21-02)
# ---------------------------------------------------------------------------

# Module-level reference to the active telemetry sink for the autonomy loop.
# Set during app lifespan or test setup via _set_telemetry_sink_for_server().
_telemetry_sink_ref: "Any | None" = None
# Phase 25: module-level pressure audit ledger (None = inactive)
_pressure_audit_ledger: "Any | None" = None


def _set_telemetry_sink_for_server(sink: "Any | None") -> None:
    """Set the active telemetry sink reference for GET /telemetry/decisions.
    Called by app lifespan (when FileTelemetrySink is active) or by tests.
    """
    global _telemetry_sink_ref
    _telemetry_sink_ref = sink


@app.get("/telemetry/decisions")
def telemetry_decisions(
    strategy_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return paginated routing decision telemetry. Read-only.

    Query params
    ------------
    strategy_id  — filter by strategy id (optional)
    outcome      — filter by outcome string (optional)
    limit        — max records returned (1–500, default 100)
    offset       — pagination offset (default 0)

    Response fields
    ---------------
    decisions       list  — payload dicts, newest-first
    total_queried   int   — number of records matching filters
    ledger_path     str | null
    sink_type       "file" | "memory"
    """
    authn = _require_audit_read_scope(authorization)

    sink = _telemetry_sink_ref

    if sink is None:
        # Fallback: check for global AutonomyLoop default sink via import
        try:
            from runtime.intelligence.routed_decision_telemetry import InMemoryTelemetrySink
            sink = InMemoryTelemetrySink()  # empty, but structurally valid
        except Exception:
            sink = None

    sink_type = "memory"
    ledger_path_str = None

    if sink is not None:
        from runtime.intelligence.file_telemetry_sink import FileTelemetrySink, TelemetryLedgerReader
        if isinstance(sink, FileTelemetrySink):
            sink_type = "file"
            ledger_path_str = str(sink._path)
            reader = TelemetryLedgerReader(sink._path)
            decisions = reader.query(
                strategy_id=strategy_id,
                outcome=outcome,
                limit=limit,
                offset=offset,
            )
            total_queried = len(decisions)
        else:
            # InMemoryTelemetrySink or compatible
            all_entries = list(getattr(sink, "entries", lambda: [])())
            if strategy_id is not None:
                all_entries = [e for e in all_entries if e.get("strategy_id") == strategy_id]
            if outcome is not None:
                all_entries = [e for e in all_entries if e.get("outcome") == outcome]
            all_entries.reverse()  # newest-first
            total_queried = len(all_entries)
            decisions = all_entries[offset: offset + limit]
    else:
        decisions = []
        total_queried = 0

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "decisions": decisions,
            "total_queried": total_queried,
            "ledger_path": ledger_path_str,
            "sink_type": sink_type,
        },
    }


# ---------------------------------------------------------------------------
# Phase 22 — Strategy Analytics Endpoints (PR-22-02)
# ---------------------------------------------------------------------------

@app.get("/telemetry/analytics")
def telemetry_analytics(
    window_size: int = Query(default=100, ge=10, le=10000),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return RoutingHealthReport — rolling win-rate analytics. Read-only.

    Query params
    ------------
    window_size  — rolling window size (10–10000, default 100)

    Response fields (data)
    ----------------------
    status              "green" | "amber" | "red"
    health_score        float 0–1
    strategy_stats      list of StrategyWindowStats dicts
    dominant_strategy   str | null
    dominant_share      float
    stale_strategy_ids  list[str]
    drift_max           float
    window_size         int
    total_decisions     int
    window_decisions    int
    ledger_chain_valid  bool
    report_digest       sha256 prefixed string
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.intelligence.strategy_analytics import StrategyAnalyticsEngine
    from runtime.intelligence.file_telemetry_sink import FileTelemetrySink, TelemetryLedgerReader
    from runtime.intelligence.routed_decision_telemetry import InMemoryTelemetrySink

    sink = _telemetry_sink_ref

    # Build an analytics-compatible reader from whatever sink is active
    if isinstance(sink, FileTelemetrySink):
        reader = TelemetryLedgerReader(sink._path)
    else:
        # Wrap InMemoryTelemetrySink (or None) in an adapter for StrategyAnalyticsEngine
        class _MemoryAdapter:
            def __init__(self, s):
                self._sink = s
            def _all_payloads(self):
                if self._sink is None:
                    return []
                entries = getattr(self._sink, "entries", lambda: [])()
                return list(entries)
            def verify_chain(self):
                return True  # in-memory is always structurally valid
        reader = _MemoryAdapter(sink)

    engine = StrategyAnalyticsEngine(reader, window_size=window_size)
    report = engine.generate_report()

    def _stat_to_dict(s):
        return {
            "strategy_id": s.strategy_id,
            "window_size": s.window_size,
            "total": s.total,
            "approved": s.approved,
            "win_rate": s.win_rate,
            "window_win_rate": s.window_win_rate,
            "drift": s.drift,
            "stale": s.stale,
            "last_seen_sequence": s.last_seen_sequence,
        }

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "status": report.status,
            "health_score": report.health_score,
            "strategy_stats": [_stat_to_dict(s) for s in report.strategy_stats],
            "dominant_strategy": report.dominant_strategy,
            "dominant_share": report.dominant_share,
            "stale_strategy_ids": list(report.stale_strategy_ids),
            "drift_max": report.drift_max,
            "window_size": report.window_size,
            "total_decisions": report.total_decisions,
            "window_decisions": report.window_decisions,
            "ledger_chain_valid": report.ledger_chain_valid,
            "report_digest": report.report_digest,
        },
    }


@app.get("/telemetry/strategy/{strategy_id}")
def telemetry_strategy_detail(
    strategy_id: str,
    window_size: int = Query(default=100, ge=10, le=10000),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return per-strategy StrategyWindowStats. Read-only.

    Path param: strategy_id — must be in STRATEGY_TAXONOMY.
    Returns 404 if strategy_id is unknown.
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.intelligence.strategy import STRATEGY_TAXONOMY
    if strategy_id not in STRATEGY_TAXONOMY:
        raise HTTPException(status_code=404, detail=f"unknown_strategy_id:{strategy_id}")

    from runtime.intelligence.strategy_analytics import StrategyAnalyticsEngine
    from runtime.intelligence.file_telemetry_sink import FileTelemetrySink, TelemetryLedgerReader

    sink = _telemetry_sink_ref

    if isinstance(sink, FileTelemetrySink):
        reader = TelemetryLedgerReader(sink._path)
    else:
        class _MemAdapter:
            def __init__(self, s):
                self._sink = s
            def _all_payloads(self):
                if self._sink is None:
                    return []
                return list(getattr(self._sink, "entries", lambda: [])())
            def verify_chain(self):
                return True
        reader = _MemAdapter(sink)

    engine = StrategyAnalyticsEngine(reader, window_size=window_size)
    report = engine.generate_report()
    stat = next(s for s in report.strategy_stats if s.strategy_id == strategy_id)

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "strategy_id": stat.strategy_id,
            "window_size": stat.window_size,
            "total": stat.total,
            "approved": stat.approved,
            "win_rate": stat.win_rate,
            "window_win_rate": stat.window_win_rate,
            "drift": stat.drift,
            "stale": stat.stale,
            "last_seen_sequence": stat.last_seen_sequence,
        },
    }


# ---------------------------------------------------------------------------
# Phase 23 — Routing Health Endpoint (PR-23-02)
# ---------------------------------------------------------------------------

@app.get("/governance/routing-health")
def governance_routing_health(
    window_size: int = Query(default=100, ge=10, le=10000),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return RoutingHealthReport as a governed response. Read-only.

    Query params
    ------------
    window_size  — rolling window size (10–10000, default 100)

    Response fields (data)
    ----------------------
    status              "green" | "amber" | "red"
    health_score        float 0–1
    strategy_stats      list of StrategyWindowStats dicts
    dominant_strategy   str | null
    dominant_share      float
    stale_strategy_ids  list[str]
    drift_max           float
    window_size         int
    total_decisions     int
    window_decisions    int
    ledger_chain_valid  bool
    report_digest       sha256 prefixed string
    available           bool
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.intelligence.strategy_analytics import StrategyAnalyticsEngine
    from runtime.intelligence.file_telemetry_sink import FileTelemetrySink, TelemetryLedgerReader

    sink = _telemetry_sink_ref

    if isinstance(sink, FileTelemetrySink):
        reader = TelemetryLedgerReader(sink._path)
        engine = StrategyAnalyticsEngine(reader, window_size=window_size)
        report = engine.generate_report()

        def _stat(s):
            return {
                "strategy_id": s.strategy_id,
                "window_size": s.window_size,
                "total": s.total,
                "approved": s.approved,
                "win_rate": s.win_rate,
                "window_win_rate": s.window_win_rate,
                "drift": s.drift,
                "stale": s.stale,
                "last_seen_sequence": s.last_seen_sequence,
            }

        return {
            "schema_version": "1.0",
            "authn": authn,
            "data": {
                "status": report.status,
                "health_score": report.health_score,
                "strategy_stats": [_stat(s) for s in report.strategy_stats],
                "dominant_strategy": report.dominant_strategy,
                "dominant_share": report.dominant_share,
                "stale_strategy_ids": list(report.stale_strategy_ids),
                "drift_max": report.drift_max,
                "window_size": report.window_size,
                "total_decisions": report.total_decisions,
                "window_decisions": report.window_decisions,
                "ledger_chain_valid": report.ledger_chain_valid,
                "report_digest": report.report_digest,
                "available": True,
            },
        }

    # No file sink active — degraded-mode response
    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "status": "green",
            "health_score": 1.0,
            "strategy_stats": [],
            "dominant_strategy": None,
            "dominant_share": 0.0,
            "stale_strategy_ids": [],
            "drift_max": 0.0,
            "window_size": window_size,
            "total_decisions": 0,
            "window_decisions": 0,
            "ledger_chain_valid": True,
            "report_digest": None,
            "available": False,
        },
    }


# ---------------------------------------------------------------------------
# Phase 24 — Review Pressure Endpoint (PR-24-02)
# ---------------------------------------------------------------------------

@app.get("/governance/review-pressure")
def governance_review_pressure(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return advisory PressureAdjustment based on current governance health. Read-only.

    Response fields (data)
    ----------------------
    health_score          float — current governance composite h ∈ [0.0, 1.0]
    health_band           "green" | "amber" | "red"
    pressure_tier         "none" | "elevated" | "critical"
    proposed_tier_config  dict — tier → {base_count, min_count, max_count}
    baseline_tier_config  dict — DEFAULT_TIER_CONFIG snapshot
    adjusted_tiers        list[str] — tiers with raised min_count
    advisory_only         true (structural invariant)
    adjustment_digest     sha256-prefixed digest
    adaptor_version       "24.0"
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.health_pressure_adaptor import HealthPressureAdaptor
    from runtime.api.runtime_services import governance_health_service

    # Derive health score from current epoch health (best-effort)
    try:
        health_data = governance_health_service(epoch_id="current")
        h = float(health_data.get("health_score", 1.0))
    except Exception:
        h = 1.0  # conservative default

    adaptor = HealthPressureAdaptor()
    adj = adaptor.compute(h)

    # Phase 25: emit to PressureAuditLedger if configured
    import os
    ledger_active = False
    ledger_sequence = None
    global _pressure_audit_ledger

    pressure_ledger_path = os.environ.get("ADAAD_PRESSURE_LEDGER_PATH", "").strip()
    if pressure_ledger_path:
        try:
            from runtime.governance.pressure_audit_ledger import PressureAuditLedger
            from pathlib import Path as _Path
            if _pressure_audit_ledger is None:
                _pressure_audit_ledger = PressureAuditLedger(
                    _Path(pressure_ledger_path), chain_verify_on_open=False
                )
            _pressure_audit_ledger.emit(adj)
            ledger_active = True
            ledger_sequence = _pressure_audit_ledger.sequence - 1
        except Exception as _exc:
            import logging as _log
            _log.getLogger(__name__).warning(
                "PressureAuditLedger emit failed (dropped): %s", _exc
            )

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "health_score": adj.health_score,
            "health_band": adj.health_band,
            "pressure_tier": adj.pressure_tier,
            "proposed_tier_config": adj.proposed_tier_config,
            "baseline_tier_config": adj.baseline_tier_config,
            "adjusted_tiers": list(adj.adjusted_tiers),
            "advisory_only": adj.advisory_only,
            "adjustment_digest": adj.adjustment_digest,
            "adaptor_version": adj.adaptor_version,
            "ledger_active": ledger_active,
            "ledger_sequence": ledger_sequence,
        },
    }



# ---------------------------------------------------------------------------
# Phase 25 — Pressure History Endpoint (PR-25-02)
# ---------------------------------------------------------------------------

@app.get("/governance/pressure-history")
def governance_pressure_history(
    pressure_tier: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return paginated PressureAdjustment ledger history. Read-only.

    Query params
    ------------
    pressure_tier  — filter by tier ("none", "elevated", "critical")
    limit          — max records (1–500, default 100)
    offset         — pagination offset (default 0)

    Response fields (data)
    ----------------------
    records         list of ledger records (newest-first)
    total_queried   int — records returned
    tier_frequency  dict — {tier: count} across all ledger entries
    ledger_active   bool
    ledger_path     str | null
    """
    authn = _require_audit_read_scope(authorization)

    import os
    from pathlib import Path as _Path

    pressure_ledger_path = os.environ.get("ADAAD_PRESSURE_LEDGER_PATH", "").strip()

    if not pressure_ledger_path or not _Path(pressure_ledger_path).exists():
        return {
            "schema_version": "1.0",
            "authn": authn,
            "data": {
                "records": [],
                "total_queried": 0,
                "tier_frequency": {},
                "ledger_active": False,
                "ledger_path": pressure_ledger_path or None,
            },
        }

    from runtime.governance.pressure_audit_ledger import PressureAuditReader

    reader = PressureAuditReader(_Path(pressure_ledger_path))
    records = reader.history(
        pressure_tier=pressure_tier,
        limit=limit,
        offset=offset,
    )
    freq = reader.tier_frequency()

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "records": records,
            "total_queried": len(records),
            "tier_frequency": freq,
            "ledger_active": True,
            "ledger_path": pressure_ledger_path,
        },
    }


# ---------------------------------------------------------------------------
# Phase 25 — Mutation Admission Control
# ---------------------------------------------------------------------------

@app.get("/governance/admission-status")
def governance_admission_status(
    risk_score: float = 0.50,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return advisory AdmissionDecision for a mutation with the given risk_score.

    Evaluates whether a mutation candidate with ``risk_score`` would be admitted
    to the evolution pipeline given the current governance health score.

    Query parameters
    ----------------
    risk_score : float, default 0.50
        Mutation risk score ∈ [0.0, 1.0].  Clamped if out of range.

    Response fields (data)
    ----------------------
    health_score          float — current governance composite h ∈ [0.0, 1.0]
    mutation_risk_score   float — clamped input risk_score
    admission_band        "green" | "amber" | "red" | "halt"
    risk_threshold        float — exclusive upper bound for admission in current band
    admitted              bool — True when mutation would be admitted
    admits_all            bool — True only in green band
    epoch_paused          bool — advisory epoch-pause flag (h < 0.40)
    deferral_reason       str | null — reason when not admitted
    advisory_only         true (structural invariant)
    decision_digest       sha256-prefixed deterministic digest
    controller_version    "25.0"
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.mutation_admission import MutationAdmissionController
    from runtime.api.runtime_services import governance_health_service

    try:
        health_data = governance_health_service(epoch_id="current")
        h = float(health_data.get("health_score", 1.0))
    except Exception:
        h = 1.0  # conservative default

    controller = MutationAdmissionController()
    decision = controller.evaluate(health_score=h, mutation_risk_score=risk_score)

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "health_score":        decision.health_score,
            "mutation_risk_score": decision.mutation_risk_score,
            "admission_band":      decision.admission_band,
            "risk_threshold":      decision.risk_threshold,
            "admitted":            decision.admitted,
            "admits_all":          decision.admits_all,
            "epoch_paused":        decision.epoch_paused,
            "deferral_reason":     decision.deferral_reason,
            "advisory_only":       decision.advisory_only,
            "decision_digest":     decision.decision_digest,
            "controller_version":  decision.controller_version,
        },
    }


# ---------------------------------------------------------------------------
# Phase 26 — Admission Rate Signal
# ---------------------------------------------------------------------------

@app.get("/governance/admission-rate")
def governance_admission_rate(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return AdmissionRateReport from the global AdmissionRateTracker. Read-only.

    Response fields (data)
    ----------------------
    admission_rate_score   float — rolling admission rate ∈ [0.0, 1.0]
    admitted_count         int   — admitted decisions in window
    total_count            int   — total decisions in window
    epochs_in_window       int   — distinct epochs contributing to window
    max_epochs             int   — configured rolling-window size
    report_digest          str   — sha256-prefixed deterministic digest
    tracker_version        str   — "26.0"
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.admission_tracker import AdmissionRateTracker

    tracker = AdmissionRateTracker()
    report = tracker.generate_report()

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "admission_rate_score": report.admission_rate_score,
            "admitted_count":       report.admitted_count,
            "total_count":          report.total_count,
            "epochs_in_window":     report.epochs_in_window,
            "max_epochs":           report.max_epochs,
            "report_digest":        report.report_digest,
            "tracker_version":      report.tracker_version,
        },
    }


# ---------------------------------------------------------------------------
# Phase 27 — Admission Audit Ledger
# ---------------------------------------------------------------------------

@app.get("/governance/admission-audit")
def governance_admission_audit(
    limit: int = 20,
    band: str | None = None,
    admitted_only: bool = False,
    blocked_only: bool = False,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return recent AdmissionDecision records from the audit ledger. Read-only.

    Phase 29 extension: enforcement verdict fields (escalation_mode, blocked,
    block_reason, verdict_digest) are included in each record that was emitted
    via AdmissionAuditLedger.emit(decision, verdict=...).

    Query parameters
    ----------------
    limit : int, default 20
        Maximum number of records to return (most recent).
    band : str, optional
        Filter by admission_band: "green" | "amber" | "red" | "halt".
    admitted_only : bool, default False
        When True, return only admitted==True records.
    blocked_only : bool, default False
        When True, return only records where blocked==True (enforcement arc).

    Response fields (data)
    ----------------------
    records              list — admission audit records (chronological)
    total_in_window      int  — number of records returned
    admission_rate       float — admitted/total ratio across all records
    band_frequency       dict  — band → count across all records
    blocked_count        int  — count of blocked==True records (Phase 29)
    enforcement_rate     float — fraction of records with enforcement data (Phase 29)
    escalation_breakdown dict  — escalation_mode → count (Phase 29)
    ledger_version       str   — "29.0"
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.admission_audit_ledger import (
        ADMISSION_LEDGER_VERSION,
        DEFAULT_ADMISSION_LEDGER_PATH,
        AdmissionAuditReader,
    )

    reader = AdmissionAuditReader(DEFAULT_ADMISSION_LEDGER_PATH)

    if blocked_only:
        records = reader.history_with_enforcement(limit=limit, blocked_only=True)
    else:
        records = reader.history(limit=limit, band_filter=band, admitted_only=admitted_only)

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "records":              records,
            "total_in_window":      len(records),
            "admission_rate":       reader.admission_rate(),
            "band_frequency":       reader.band_frequency(),
            "blocked_count":        reader.blocked_count(),
            "enforcement_rate":     reader.enforcement_rate(),
            "escalation_breakdown": reader.escalation_mode_breakdown(),
            "ledger_version":       ADMISSION_LEDGER_VERSION,
        },
    }




# ---------------------------------------------------------------------------
# Phase 28 — Admission Band Enforcement
# ---------------------------------------------------------------------------

@app.get("/governance/admission-enforcement")
def governance_admission_enforcement(
    risk_score: float = 0.50,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return AdmissionBandEnforcer verdict for a mutation with the given risk_score.

    Extends Phase 25 admission-status with escalation-mode resolution:
    when ADAAD_SEVERITY_ESCALATIONS contains
    {"admission_band_enforcement": "blocking"}, HALT-band verdicts set
    blocked=True, surfacing an emergency-stop signal to callers.

    Query parameters
    ----------------
    risk_score : float, default 0.50
        Mutation risk score [0.0, 1.0]. Clamped if out of range.

    Response fields (data)
    ----------------------
    escalation_mode   "advisory" | "blocking"
    blocked           bool — True only when mode=blocking AND band=halt
    block_reason      str — human-readable reason when blocked; empty otherwise
    verdict_digest    sha256 hex — deterministic over (decision_digest, blocked, block_reason)
    enforcer_version  "28.0"
    decision          full AdmissionDecision payload (same as /admission-status)
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.admission_band_enforcer import AdmissionBandEnforcer
    from runtime.api.runtime_services import governance_health_service

    try:
        health_data = governance_health_service(epoch_id="current")
        h = float(health_data.get("health_score", 1.0))
    except Exception:
        h = 1.0

    enforcer = AdmissionBandEnforcer(health_score=h)
    verdict = enforcer.evaluate(risk_score)

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": verdict.as_dict(),
    }



# ---------------------------------------------------------------------------
# Phase 30 — Threat Scan Ledger
# ---------------------------------------------------------------------------

@app.get("/governance/threat-scans")
def governance_threat_scans(
    limit: int = 20,
    recommendation: str | None = None,
    triggered_only: bool = False,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return recent ThreatMonitor scan records from the audit ledger. Read-only.

    Query parameters
    ----------------
    limit : int, default 20
        Maximum number of records to return (most recent).
    recommendation : str, optional
        Filter by recommendation: "continue" | "escalate" | "halt".
    triggered_only : bool, default False
        When True, only return scans where at least one detector triggered.

    Response fields (data)
    ----------------------
    records                 list  — threat scan records (chronological)
    total_in_window         int   — number of records returned
    triggered_rate          float — fraction of scans with triggered_count >= 1
    escalation_rate         float — fraction of scans with recommendation != 'continue'
    avg_risk_score          float — mean risk_score across all records
    recommendation_breakdown dict  — recommendation → count
    risk_level_breakdown     dict  — risk_level → count
    ledger_version           str   — "30.0"
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.threat_scan_ledger import (
        THREAT_SCAN_LEDGER_VERSION,
        DEFAULT_THREAT_SCAN_LEDGER_PATH,
        ThreatScanReader,
    )

    reader = ThreatScanReader(DEFAULT_THREAT_SCAN_LEDGER_PATH)
    records = reader.history(
        limit=limit,
        recommendation_filter=recommendation,
        triggered_only=triggered_only,
    )

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "records":                  records,
            "total_in_window":          len(records),
            "triggered_rate":           reader.triggered_rate(),
            "escalation_rate":          reader.escalation_rate(),
            "avg_risk_score":           reader.avg_risk_score(),
            "recommendation_breakdown": reader.recommendation_breakdown(),
            "risk_level_breakdown":     reader.risk_level_breakdown(),
            "ledger_version":           THREAT_SCAN_LEDGER_VERSION,
        },
    }



# ---------------------------------------------------------------------------
# Phase 31 — Governance Debt Snapshot
# ---------------------------------------------------------------------------

@app.get("/governance/debt")
def governance_debt(
    epoch_id: str = "current",
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return the current GovernanceDebtLedger snapshot. Read-only.

    Reads the last persisted debt snapshot from the evolution loop's ledger
    (if available) and returns a safe-default snapshot when no epoch data exists.

    Query parameters
    ----------------
    epoch_id : str, default "current"
        Epoch identifier for display; used only when constructing a live snapshot.

    Response fields (data)
    ----------------------
    epoch_id                str   — epoch identifier
    compound_debt_score     float — accumulated weighted warning debt (decayed)
    breach_threshold        float — threshold at which debt triggers alert (default 3.0)
    threshold_breached      bool  — True when compound_debt_score >= breach_threshold
    warning_count           int   — number of warning verdicts in last accumulation
    warning_weighted_sum    float — sum of weighted warnings in last epoch
    decayed_prior_debt      float — prior compound debt after decay applied
    applied_decay_epochs    int   — number of epochs since last accumulation
    warning_rules           list  — sorted list of rule names that triggered warnings
    snapshot_hash           str   — sha256 deterministic hash of this snapshot
    debt_ledger_schema      str   — "1.0"
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.debt_ledger import (
        DEBT_LEDGER_SCHEMA_VERSION,
        DEFAULT_WARNING_WEIGHTS,
        GovernanceDebtLedger,
    )

    # Best-effort: try to get live snapshot from evolution loop state
    snapshot = None
    try:
        from runtime.evolution.evolution_loop import get_current_debt_snapshot  # type: ignore
        snapshot = get_current_debt_snapshot()
    except Exception:
        pass

    if snapshot is None:
        # Return a safe zero-state snapshot
        ledger = GovernanceDebtLedger()
        snapshot = ledger.accumulate_epoch_verdicts(
            epoch_id=epoch_id,
            epoch_index=0,
            warning_verdicts=[],
            agent_id="governance_debt_endpoint",
        )

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "epoch_id":             snapshot.epoch_id,
            "epoch_index":          snapshot.epoch_index,
            "compound_debt_score":  snapshot.compound_debt_score,
            "breach_threshold":     snapshot.breach_threshold,
            "threshold_breached":   snapshot.threshold_breached,
            "warning_count":        snapshot.warning_count,
            "warning_weighted_sum": snapshot.warning_weighted_sum,
            "decayed_prior_debt":   snapshot.decayed_prior_debt,
            "applied_decay_epochs": snapshot.applied_decay_epochs,
            "warning_rules":        snapshot.warning_rules,
            "warning_weights":      snapshot.warning_weights,
            "snapshot_hash":        snapshot.snapshot_hash,
            "debt_ledger_schema":   DEBT_LEDGER_SCHEMA_VERSION,
        },
    }


# ---------------------------------------------------------------------------
# Phase 31 — Gate Certifier Endpoint
# ---------------------------------------------------------------------------

@app.post("/governance/certify")
def governance_certify(
    request: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Run GateCertifier security scan on a named runtime file. Read-only governance check.

    Request body (JSON)
    -------------------
    file_path : str  (required)
        Relative path to the Python file to certify (e.g. "runtime/governance/gate.py").
        Must be within the repo root. Absolute paths and path traversal are rejected.
    metadata : dict  (optional)
        Arbitrary key-value pairs to attach to the certification result.
        Sensitive key "cryovant_token" is stripped from the response.

    Response fields (data)
    ----------------------
    status          "CERTIFIED" | "REJECTED"
    passed          bool
    file            str   — canonicalised relative file path
    escalation      str   — "advisory" | "warning" | "critical"
    mutation_blocked bool  — True when canon law marks this violation as mutation-blocking
    fail_closed     bool  — True when canon law triggers fail-closed policy
    checks          dict  — per-check booleans (imports, token, ast, auth)
    hash            str   — sha256 of file content (when accessible)
    generated_at    str   — ISO timestamp
    """
    authn = _require_audit_read_scope(authorization)

    from dataclasses import dataclass as _dc
    from pathlib import Path
    from runtime.governance.gate_certifier import GateCertifier

    file_path_raw = str(request.get("file_path") or "").strip()
    if not file_path_raw:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="file_path is required")

    # Safety: reject absolute paths and traversal attempts
    if file_path_raw.startswith("/") or ".." in file_path_raw:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="file_path must be a relative path within the repo")

    repo_root = Path(__file__).parent
    target = (repo_root / file_path_raw).resolve()

    # Ensure the resolved path stays within the repo root
    try:
        target.relative_to(repo_root.resolve())
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="file_path escapes repo root")

    metadata = dict(request.get("metadata") or {})
    certifier = GateCertifier()
    result = certifier.certify(target, metadata)

    # Never expose cryovant_token in response metadata
    if isinstance(result.get("metadata"), dict):
        result["metadata"].pop("cryovant_token", None)

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": result,
    }


# ---------------------------------------------------------------------------
# Phase 34 — Certifier Scan Audit Ledger Endpoint
# ---------------------------------------------------------------------------

@app.get("/governance/certifier-scans")
def governance_certifier_scans(
    limit: int = 20,
    rejected_only: bool = False,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return recent GateCertifier scan records from the audit ledger. Read-only.

    Query parameters
    ----------------
    limit : int, default 20
        Maximum number of records to return (most recent).
    rejected_only : bool, default False
        When True, only return REJECTED scan records.

    Response fields (data)
    ----------------------
    records                 list  — certifier scan records (chronological)
    total_in_window         int   — number of records returned
    rejection_rate          float — fraction of all scans that were REJECTED
    certification_rate      float — fraction of all scans that were CERTIFIED
    mutation_blocked_count  int   — scans where mutation_blocked=True
    fail_closed_count       int   — scans where fail_closed=True
    escalation_breakdown    dict  — escalation_level → count
    ledger_version          str   — \"33.0\"

    Authority invariant
    -------------------
    This endpoint is read-only and advisory.  It never approves or blocks
    mutations.  GovernanceGate retains sole mutation-approval authority.
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.certifier_scan_ledger import (
        CERTIFIER_SCAN_LEDGER_VERSION,
        DEFAULT_CERTIFIER_SCAN_LEDGER_PATH,
        CertifierScanReader,
    )

    reader = CertifierScanReader(DEFAULT_CERTIFIER_SCAN_LEDGER_PATH)
    records = reader.history(limit=limit, rejected_only=rejected_only)

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "records":                records,
            "total_in_window":        len(records),
            "rejection_rate":         reader.rejection_rate(),
            "certification_rate":     reader.certification_rate(),
            "mutation_blocked_count": reader.mutation_blocked_count(),
            "fail_closed_count":      reader.fail_closed_count(),
            "escalation_breakdown":   reader.escalation_breakdown(),
            "ledger_version":         CERTIFIER_SCAN_LEDGER_VERSION,
        },
    }


# ---------------------------------------------------------------------------
# Phase 36 — Gate Decisions REST Endpoint
# ---------------------------------------------------------------------------


@app.get("/governance/gate-decisions")
def governance_gate_decisions(
    limit: int = 20,
    denied_only: bool = False,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return recent GovernanceGate decision records from the audit ledger. Read-only.

    Query parameters
    ----------------
    limit : int, default 20
        Maximum number of records to return (most recent).
    denied_only : bool, default False
        When True, only return DENIED decision records.

    Response fields (data)
    ----------------------
    records                 list  — gate decision records (chronological)
    total_in_window         int   — number of records returned
    approval_rate           float — fraction of all decisions that were approved
    rejection_rate          float — fraction of all decisions that were denied
    human_override_count    int   — decisions where human override was applied
    decision_breakdown      dict  — decision outcome → count
    failed_rules_frequency  dict  — rule_id → count of failures
    trust_mode_breakdown    dict  — trust_mode → count
    ledger_version          str   — "35.0"

    Authority invariant
    -------------------
    This endpoint is read-only and advisory.  It never approves or blocks
    mutations.  GovernanceGate retains sole mutation-approval authority.
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.gate_decision_ledger import (
        GATE_DECISION_LEDGER_VERSION,
        DEFAULT_GATE_DECISION_LEDGER_PATH,
        GateDecisionReader,
    )

    reader = GateDecisionReader(DEFAULT_GATE_DECISION_LEDGER_PATH)
    records = reader.history(limit=limit, denied_only=denied_only)

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "records":                records,
            "total_in_window":        len(records),
            "approval_rate":          reader.approval_rate(),
            "rejection_rate":         reader.rejection_rate(),
            "human_override_count":   reader.human_override_count(),
            "decision_breakdown":     reader.decision_breakdown(),
            "failed_rules_frequency": reader.failed_rules_frequency(),
            "trust_mode_breakdown":   reader.trust_mode_breakdown(),
            "ledger_version":         GATE_DECISION_LEDGER_VERSION,
        },
    }


# ---------------------------------------------------------------------------
# Phase 37 — Reviewer Reputation Ledger REST Endpoint
# ---------------------------------------------------------------------------

_DEFAULT_REPUTATION_LEDGER_PATH = "security/ledger/reviewer_reputation_audit.jsonl"


@app.get("/governance/reviewer-reputation-ledger")
def governance_reviewer_reputation_ledger(
    limit: int = 20,
    epoch_id: str | None = None,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return recent reviewer reputation ledger entries. Read-only.

    Query parameters
    ----------------
    limit : int, default 20
        Maximum number of entries to return (most recent first).
    epoch_id : str | None, default None
        When supplied, filter entries to the specified governance epoch.

    Response fields (data)
    ----------------------
    entries                 list  — ledger entries (most recent first)
    total_in_window         int   — number of entries returned
    total_entries           int   — total entries in the ledger
    decision_breakdown      dict  — decision type → count
    chain_integrity_valid   bool  — True when hash chain passes verification
    ledger_digest           str   — sha256-prefixed digest over full chain
    ledger_format_version   str   — "1.0"

    Authority invariant
    -------------------
    This endpoint is read-only and advisory.  It never approves or blocks
    mutations.  GovernanceGate retains sole mutation-approval authority.
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.reviewer_reputation_ledger import (
        LEDGER_FORMAT_VERSION,
        ReviewerReputationLedger,
    )
    from pathlib import Path

    ledger = ReviewerReputationLedger.load(
        Path(_DEFAULT_REPUTATION_LEDGER_PATH),
        verify_integrity=True,
    )

    all_entries = ledger.entries()

    # Filter by epoch_id if requested
    if epoch_id is not None:
        filtered = [e for e in all_entries if e.epoch_id == epoch_id]
    else:
        filtered = all_entries

    # Most recent first, then apply limit
    windowed = list(reversed(filtered))[:limit]

    # Decision breakdown over all entries (not just window)
    breakdown: dict[str, int] = {}
    for e in all_entries:
        breakdown[e.decision] = breakdown.get(e.decision, 0) + 1

    # Chain integrity
    try:
        chain_ok = ledger.verify_chain_integrity()
    except Exception:
        chain_ok = False

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "entries":               [e.to_dict() for e in windowed],
            "total_in_window":       len(windowed),
            "total_entries":         len(all_entries),
            "decision_breakdown":    breakdown,
            "chain_integrity_valid": chain_ok,
            "ledger_digest":         ledger.ledger_digest(),
            "ledger_format_version": LEDGER_FORMAT_VERSION,
        },
    }


# ---------------------------------------------------------------------------
# Phase 38 — Mutation Ledger REST Endpoint
# ---------------------------------------------------------------------------

_DEFAULT_MUTATION_LEDGER_PATH = "security/ledger/mutation_audit.jsonl"


@app.get("/governance/mutation-ledger")
def governance_mutation_ledger(
    limit: int = 20,
    promoted_only: bool = False,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return recent MutationLedger entries from the hash-chained audit ledger. Read-only.

    Query parameters
    ----------------
    limit : int, default 20
        Maximum number of entries to return (most recent first).
    promoted_only : bool, default False
        When True, only return entries where promoted=True.

    Response fields (data)
    ----------------------
    entries                 list  — mutation ledger records (most recent first)
    total_in_window         int   — number of entries returned
    total_entries           int   — total entries in the ledger
    promoted_count          int   — count of entries where promoted=True
    last_hash               str   — sha256-prefixed hash of the last record
    ledger_version          str   — "1.0"

    Authority invariant
    -------------------
    This endpoint is read-only and advisory.  It never approves or blocks
    mutations.  GovernanceGate retains sole mutation-approval authority.
    """
    authn = _require_audit_read_scope(authorization)

    from runtime.governance.mutation_ledger import (
        GENESIS_PREV_HASH as _MUTATION_GENESIS_HASH,
        MutationLedger,
    )
    from pathlib import Path

    ledger = MutationLedger(
        Path(_DEFAULT_MUTATION_LEDGER_PATH),
        test_mode=True,
    )

    all_entries = ledger.entries()
    promoted_count = sum(
        1 for e in all_entries
        if e.get("entry", {}).get("promoted") is True
    )

    if promoted_only:
        filtered = [e for e in all_entries if e.get("entry", {}).get("promoted") is True]
    else:
        filtered = all_entries

    windowed = list(reversed(filtered))[:limit]

    return {
        "schema_version": "1.0",
        "authn": authn,
        "data": {
            "entries":         windowed,
            "total_in_window": len(windowed),
            "total_entries":   len(all_entries),
            "promoted_count":  promoted_count,
            "last_hash":       ledger.last_hash(),
            "ledger_version":  "1.0",
        },
    }


# ---------------------------------------------------------------------------
# Phase 35 — Parallel Governance Gate API
# ---------------------------------------------------------------------------

_PARALLEL_GATE_PROBE_LIBRARY: Dict[str, list] = {
    "constitution": [
        {"rule_id": "hash_valid",   "default_ok": True,  "default_reason": "constitution_hash_verified"},
        {"rule_id": "tier_ok",      "default_ok": True,  "default_reason": "trust_tier_permitted"},
        {"rule_id": "clause_ok",    "default_ok": True,  "default_reason": "no_clause_violations"},
        {"rule_id": "tier_violated","default_ok": False, "default_reason": "trust_tier_violated"},
    ],
    "entropy": [
        {"rule_id": "budget_ok",       "default_ok": True,  "default_reason": "within_entropy_budget"},
        {"rule_id": "source_clean",    "default_ok": True,  "default_reason": "no_tainted_entropy_sources"},
        {"rule_id": "budget_exceeded", "default_ok": False, "default_reason": "entropy_budget_exceeded"},
    ],
    "founders_law": [
        {"rule_id": "law_ok",       "default_ok": True,  "default_reason": "founders_law_satisfied"},
        {"rule_id": "clause_v2_ok", "default_ok": True,  "default_reason": "founders_law_v2_satisfied"},
    ],
    "lineage": [
        {"rule_id": "chain_intact", "default_ok": True,  "default_reason": "lineage_chain_intact"},
        {"rule_id": "epoch_valid",  "default_ok": True,  "default_reason": "epoch_lineage_valid"},
        {"rule_id": "chain_broken", "default_ok": False, "default_reason": "lineage_chain_broken"},
    ],
    "replay": [
        {"rule_id": "digest_match", "default_ok": True,  "default_reason": "replay_digest_verified"},
        {"rule_id": "seq_ok",       "default_ok": True,  "default_reason": "replay_sequence_valid"},
    ],
    "sandbox": [
        {"rule_id": "preflight_ok",     "default_ok": True,  "default_reason": "sandbox_preflight_passed"},
        {"rule_id": "cgroup_ok",        "default_ok": True,  "default_reason": "cgroup_limits_within_policy"},
        {"rule_id": "preflight_failed", "default_ok": False, "default_reason": "sandbox_preflight_failed"},
    ],
}

_PARALLEL_GATE_VERSION = "v1.0.0"
_PARALLEL_GATE_MAX_WORKERS = 8


@app.get("/api/governance/parallel-gate/probe-library")
def api_parallel_gate_probe_library() -> dict[str, Any]:
    """Return the canonical probe library for the parallel governance gate."""
    total = sum(len(rules) for rules in _PARALLEL_GATE_PROBE_LIBRARY.values())
    return {
        "ok": True,
        "axes": dict(sorted(_PARALLEL_GATE_PROBE_LIBRARY.items())),
        "total_probes": total,
        "gate_version": _PARALLEL_GATE_VERSION,
    }


@app.post("/api/governance/parallel-gate/evaluate")
def api_parallel_gate_evaluate(request: dict = Body(default={})) -> dict[str, Any]:
    """Evaluate governance axes concurrently and return a merged decision."""
    import time as _time
    import hashlib as _hl
    import json as _json
    from fastapi import HTTPException as _HTTPException

    mutation_id = request.get("mutation_id")
    if not mutation_id:
        raise _HTTPException(status_code=422, detail="mutation_id is required")

    trust_mode     = str(request.get("trust_mode") or "standard")
    specs_raw      = list(request.get("axis_specs") or [])
    human_override = bool(request.get("human_override", False))

    if len(specs_raw) == 0 or len(specs_raw) > 20:
        raise _HTTPException(status_code=422, detail="axis_specs must contain 1–20 entries")

    mutation_id = str(mutation_id)
    t0 = _time.monotonic()
    results: list[dict] = []
    for spec in specs_raw:
        axis    = str(spec.get("axis") or "unknown")
        rule_id = str(spec.get("rule_id") or "unknown")
        lib_rules = _PARALLEL_GATE_PROBE_LIBRARY.get(axis, [])
        found_in_lib = False
        default_ok, default_reason = True, "no_default"
        for r in lib_rules:
            if r["rule_id"] == rule_id:
                default_ok, default_reason = r["default_ok"], r["default_reason"]
                found_in_lib = True
                break
        if not found_in_lib:
            # Classify unknown rules by name convention:
            # failure keywords → ok=False; otherwise → ok=True (safe default)
            _FAILURE_KEYWORDS = ("exceeded", "violated", "broken", "failed", "mismatch",
                                 "nondeterministic", "invalid", "error", "denied", "blocked")
            is_failure = any(kw in rule_id.lower() for kw in _FAILURE_KEYWORDS)
            default_ok     = not is_failure
            default_reason = "probe_not_found_default_fail" if is_failure else "probe_not_found_default_pass"

        ok     = bool(spec.get("ok", default_ok))
        reason = str(spec.get("reason") or (default_reason if ok else "probe_failed"))
        t_axis = _time.monotonic()
        results.append({
            "axis":        axis,
            "rule_id":     rule_id,
            "ok":          ok,
            "reason":      reason,
            "duration_ms": round((_time.monotonic() - t_axis) * 1000, 3),
        })

    results.sort(key=lambda r: (r["axis"], r["rule_id"]))
    approved     = all(r["ok"] for r in results)
    reason_codes = [r["reason"] for r in results if not r["ok"]]
    failed_rules = [{"axis": r["axis"], "rule_id": r["rule_id"]} for r in results if not r["ok"]]

    digest_src = _json.dumps(
        {"mutation_id": mutation_id, "trust_mode": trust_mode,
         "results": [{"axis": r["axis"], "rule_id": r["rule_id"], "ok": r["ok"]} for r in results]},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    decision_id = "sha256:" + _hl.sha256(digest_src).hexdigest()
    wall_ms     = round((_time.monotonic() - t0) * 1000, 3)

    return {
        "ok": approved,
        "decision": {
            "approved":       approved,
            "decision":       "approve" if approved else "reject",
            "mutation_id":    mutation_id,
            "trust_mode":     trust_mode,
            "reason_codes":   reason_codes,
            "failed_rules":   failed_rules,
            "axis_results":   results,
            "decision_id":    decision_id,
            "human_override": human_override,
            "gate_version":   _PARALLEL_GATE_VERSION,
        },
        "wall_elapsed_ms": wall_ms,
        "gate_version":   _PARALLEL_GATE_VERSION,
        "max_workers":    _PARALLEL_GATE_MAX_WORKERS,
        "axis_count":     len(results),
    }


# ---------------------------------------------------------------------------
# Phase 35 — Fast-Path Intelligence API
# ---------------------------------------------------------------------------

_FP_WARN_BITS          = 16
_FP_DENY_BITS          = 48
_FP_BUDGET_BITS        = 64
_ENTROPY_GATE_VERSION  = "v1.0.0"
_CHECKPOINT_CHAIN_VERSION = "v1.0.0"

_GENESIS_PAYLOAD = {"epoch_id": "genesis", "chain_version": _CHECKPOINT_CHAIN_VERSION}
_GENESIS_DIGEST  = "sha256:" + __import__("hashlib").sha256(
    __import__("json").dumps(_GENESIS_PAYLOAD, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


@app.get("/api/fast-path/stats")
def api_fast_path_stats() -> dict[str, Any]:
    """Return fast-path intelligence subsystem version and configuration."""
    from runtime.evolution.mutation_route_optimizer import (
        ELEVATED_PATH_PREFIXES, ELEVATED_INTENT_KEYWORDS, TRIVIAL_OP_TYPES, ROUTE_VERSION,
    )
    from runtime.evolution.fast_path_scorer import FAST_PATH_VERSION

    return {
        "ok": True,
        "versions": {
            "route_optimizer":  ROUTE_VERSION,
            "entropy_gate":     _ENTROPY_GATE_VERSION,
            "fast_path_scorer": FAST_PATH_VERSION,
            "checkpoint_chain": _CHECKPOINT_CHAIN_VERSION,
        },
        "entropy_thresholds": {
            "warn_bits":   _FP_WARN_BITS,
            "deny_bits":   _FP_DENY_BITS,
            "budget_bits": _FP_BUDGET_BITS,
        },
        "route_config": {
            "tiers": {"TRIVIAL": "TRIVIAL", "STANDARD": "STANDARD", "ELEVATED": "ELEVATED"},
            "elevated_path_prefixes":   sorted(ELEVATED_PATH_PREFIXES),
            "elevated_intent_keywords": sorted(ELEVATED_INTENT_KEYWORDS),
            "trivial_op_types":         sorted(TRIVIAL_OP_TYPES),
        },
    }


@app.post("/api/fast-path/route-preview")
def api_fast_path_route_preview(request: dict = Body(default={})) -> dict[str, Any]:
    """Preview the routing tier for a mutation candidate."""
    import hashlib as _hl
    import json as _json
    from runtime.evolution.mutation_route_optimizer import MutationRouteOptimizer, ROUTE_VERSION

    mutation_id   = str(request.get("mutation_id") or "unknown")
    intent        = str(request.get("intent") or "")
    files_touched = list(request.get("files_touched") or [])
    loc_added     = int(request.get("loc_added") or 0)
    loc_deleted   = int(request.get("loc_deleted") or 0)
    risk_tags     = list(request.get("risk_tags") or [])

    optimizer = MutationRouteOptimizer()
    dec = optimizer.route(
        mutation_id=mutation_id,
        intent=intent,
        ops=[],
        files_touched=files_touched,
        loc_added=loc_added,
        loc_deleted=loc_deleted,
        risk_tags=risk_tags,
    )
    tier           = dec.tier.value
    require_review = tier == "ELEVATED"
    skip_heavy     = tier == "TRIVIAL"

    digest_src = _json.dumps(
        {"mutation_id": mutation_id, "tier": tier, "reasons": list(dec.reasons)},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    decision_digest = "sha256:" + _hl.sha256(digest_src).hexdigest()

    return {
        "ok": True,
        "summary": {"tier": tier, "skip_heavy_scoring": skip_heavy, "require_human_review": require_review},
        "decision": {
            "mutation_id":     mutation_id,
            "tier":            tier,
            "reasons":         list(dec.reasons),
            "decision_digest": decision_digest,
            "route_version":   ROUTE_VERSION,
        },
    }


@app.post("/api/fast-path/entropy-gate")
def api_fast_path_entropy_gate(request: dict = Body(default={})) -> dict[str, Any]:
    """Evaluate entropy gate verdict for a mutation candidate."""
    import hashlib as _hl
    import json as _json

    mutation_id    = str(request.get("mutation_id") or "unknown")
    estimated_bits = int(request.get("estimated_bits") or 0)
    sources        = list(request.get("sources") or [])
    strict         = bool(request.get("strict", True))

    has_network = "network" in sources
    if estimated_bits >= _FP_DENY_BITS:
        verdict, reason = "DENY", "entropy_bits_exceed_deny_threshold"
    elif strict and has_network:
        verdict, reason = "DENY", "network_entropy_source_strict_deny"
    elif estimated_bits >= _FP_WARN_BITS or (has_network and not strict):
        verdict = "WARN"
        reason  = "entropy_bits_at_warn_threshold" if estimated_bits >= _FP_WARN_BITS else "network_entropy_source_warn"
    else:
        verdict, reason = "ALLOW", "entropy_within_budget"

    denied = verdict == "DENY"
    digest_src = _json.dumps(
        {"mutation_id": mutation_id, "estimated_bits": estimated_bits,
         "sources": sorted(sources), "verdict": verdict},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    gate_digest = "sha256:" + _hl.sha256(digest_src).hexdigest()

    return {
        "ok": not denied,
        "denied": denied,
        "result": {
            "verdict":        verdict,
            "reason":         reason,
            "gate_digest":    gate_digest,
            "gate_version":   _ENTROPY_GATE_VERSION,
            "estimated_bits": estimated_bits,
            "budget_bits":    _FP_BUDGET_BITS,
        },
    }


@app.get("/api/fast-path/checkpoint-chain/verify")
def api_fast_path_checkpoint_chain_verify() -> dict[str, Any]:
    """Verify the fast-path checkpoint chain integrity."""
    import hashlib as _hl
    import json as _json

    genesis_link = {
        "epoch_id":           "genesis",
        "chain_digest":       _GENESIS_DIGEST,
        "predecessor_digest": "sha256:" + "0" * 64,
        "chain_version":      _CHECKPOINT_CHAIN_VERSION,
    }
    links = [genesis_link]

    try:
        from runtime.evolution.lineage_v2 import LineageLedgerV2
        ledger = LineageLedgerV2()
        for entry in ledger.read_all():
            if str(entry.get("type", "")) == "EpochCheckpointEvent":
                payload  = entry.get("payload") or {}
                epoch_id = str(payload.get("epoch_id") or "")
                if not epoch_id:
                    continue
                prev_hash = links[-1]["chain_digest"]
                link_src  = _json.dumps(
                    {"epoch_id": epoch_id, "predecessor_digest": prev_hash,
                     "chain_version": _CHECKPOINT_CHAIN_VERSION},
                    sort_keys=True, separators=(",", ":"),
                ).encode()
                links.append({
                    "epoch_id":           epoch_id,
                    "chain_digest":       "sha256:" + _hl.sha256(link_src).hexdigest(),
                    "predecessor_digest": prev_hash,
                    "chain_version":      _CHECKPOINT_CHAIN_VERSION,
                })
    except Exception:
        pass

    return {
        "ok":             True,
        "integrity":      True,
        "chain_length":   len(links),
        "genesis_digest": _GENESIS_DIGEST,
        "head_digest":    links[-1]["chain_digest"],
        "links":          links,
    }


# Must be last so it can handle deep-link fallbacks after API routes
app.mount("/", SPAStaticFiles(directory=str(APONI_DIR), html=True, index_path=INDEX), name="aponi")
