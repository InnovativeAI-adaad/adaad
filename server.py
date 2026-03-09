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


# Must be last so it can handle deep-link fallbacks after API routes
app.mount("/", SPAStaticFiles(directory=str(APONI_DIR), html=True, index_path=INDEX), name="aponi")
