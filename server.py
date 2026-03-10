from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException, Query
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

app = FastAPI(title="InnovativeAI-adaad Unified Server")
app.include_router(mutate_router)


@app.on_event("startup")
def _startup_checks() -> None:
    if not APONI_DIR.exists():
        raise RuntimeError("ui/aponi not found. Import APONI into ui/aponi first.")
    if not INDEX.exists():
        raise RuntimeError("ui/aponi/index.html not found. Verify APONI import.")


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
    snapshot = {"ok": not gate["locked"], "protocol": GATE_PROTOCOL, "gate": gate}
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
        },
    }


# Must be last so it can handle deep-link fallbacks after API routes
app.mount("/", SPAStaticFiles(directory=str(APONI_DIR), html=True, index_path=INDEX), name="aponi")
