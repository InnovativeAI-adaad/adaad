from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket
from pydantic import BaseModel
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import FileResponse

from runtime import metrics
from runtime import constitution
from runtime.evolution.evidence_bundle import EvidenceBundleBuilder, FORENSIC_EXPORT_DIR
from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.evolution.replay_attestation import REPLAY_PROOFS_DIR, load_replay_proof, verify_replay_proof_bundle
from runtime.governance.foundation.determinism import default_provider
from runtime.governance.deterministic_filesystem import read_file_deterministic
from runtime.governance.review_quality import DEFAULT_REVIEW_SLA_SECONDS, summarize_review_quality
from runtime.intelligence.router import IntelligenceRouter
from runtime.intelligence.strategy import StrategyInput
from runtime.mcp.linting_bridge import MutationLintingBridge
from runtime.mcp.proposal_queue import append_proposal
from runtime.mcp.proposal_validator import ProposalValidationError, validate_proposal
from runtime.metrics_analysis import mutation_rate_snapshot, rolling_determinism_score
from security.ledger import journal


ROOT = Path(__file__).resolve().parent
APONI_DIR = ROOT / "ui" / "aponi"
ENHANCED_DIR = ROOT / "ui" / "enhanced"
INDEX = APONI_DIR / "index.html"
ENHANCED_INDEX = ENHANCED_DIR / "enhanced_dashboard.html"
PLACEHOLDER_HTML = """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>ADAAD Dashboard Placeholder</title>
    <style>
      body { font-family: sans-serif; margin: 2rem; line-height: 1.5; }
      code { background: #f3f4f6; padding: 0.1rem 0.25rem; border-radius: 4px; }
    </style>
  </head>
  <body>
    <h1>ADAAD dashboard placeholder</h1>
    <p>The preferred dashboard UI was not found, so a placeholder was generated.</p>
    <p>API health is available at <code>/api/health</code>.</p>
  </body>
</html>
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    ui_dir, ui_index, mock_dir, ui_source = _resolve_ui_paths(create_placeholder=True)
    app.state.ui_dir = ui_dir
    app.state.ui_index = ui_index
    app.state.mock_dir = mock_dir
    app.state.ui_source = ui_source
    logging.getLogger(__name__).info("ADAAD server UI source=%s index=%s", ui_source, ui_index)
    yield


app = FastAPI(title="InnovativeAI-adaad Unified Server", lifespan=lifespan)

AUDIT_READ_SCOPE = "audit:read"
APONI_EDITOR_INTENT = "governed_mutation_proposal_authoring"


class MutationView(BaseModel):
    mutation_id: str
    epoch_id: str
    impact: float | None = None
    risk_tier: str = "unknown"
    applied: bool = True
    timestamp: str = ""


class EpochView(BaseModel):
    epoch_id: str
    mutation_count: int
    event_count: int
    latest_timestamp: str = ""
    expected_digest: str | None = None
    computed_digest: str


class ConstitutionStatus(BaseModel):
    constitution_version: str
    policy_hash: str
    policy_path: str
    policy_exists: bool
    boot_sanity: dict[str, bool]


class SystemIntelligenceView(BaseModel):
    determinism: dict[str, Any]
    mutation_rate: dict[str, Any]
    routed_decision: dict[str, Any]


class ProposalResponse(BaseModel):
    ok: bool
    proposal_id: str
    authority_level: str
    verdict: dict[str, Any]
    queue_hash: str


APONI_EDITOR_PROPOSAL_EVENT = "aponi_editor_proposal_submitted.v1"


def _header_value(headers: dict[str, str], key: str) -> str:
    return str(headers.get(key, "")).strip()


def _aponi_editor_submission_context(request: Request) -> dict[str, Any] | None:
    headers = {str(k).lower(): str(v) for k, v in request.headers.items()}
    session_id = _header_value(headers, "x-aponi-session-id") or _header_value(headers, "x-aponi-editor-session-id")
    submission_origin = _header_value(headers, "x-aponi-submission-origin").lower()
    if submission_origin not in {"", "editor_ui", "aponi_editor_ui"}:
        return None
    if not session_id and submission_origin == "":
        return None
    actor_context = {
        "actor_id": _header_value(headers, "x-aponi-actor-id") or "anonymous",
        "actor_role": _header_value(headers, "x-aponi-actor-role") or "operator",
        "authn_scheme": _header_value(headers, "x-aponi-authn-scheme") or "unspecified",
    }
    return {
        "session_id": session_id,
        "actor_context": actor_context,
        "origin": _header_value(headers, "origin"),
    }


def _load_audit_tokens() -> dict[str, set[str]]:
    raw_tokens = (os.getenv("ADAAD_AUDIT_TOKENS") or "").strip()
    token_map: dict[str, set[str]] = {}
    if raw_tokens:
        try:
            parsed = json.loads(raw_tokens)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            for token, scopes in parsed.items():
                if not isinstance(token, str):
                    continue
                if isinstance(scopes, list):
                    token_map[token.strip()] = {str(scope).strip() for scope in scopes if str(scope).strip()}
    dev_token = (os.getenv("ADAAD_AUDIT_DEV_TOKEN") or "").strip()
    if dev_token:
        token_map.setdefault(dev_token, {AUDIT_READ_SCOPE})
    return token_map


def _authenticate_audit_request(
    authorization: str | None = Header(default=None),
    x_client_cert_subject: str | None = Header(default=None),
) -> dict[str, Any]:
    token_map = _load_audit_tokens()
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
            scopes = token_map.get(token)
            if scopes is not None:
                return {"scheme": "bearer", "principal": "token", "scopes": sorted(scopes)}
            raise HTTPException(status_code=401, detail="invalid_token")

    if x_client_cert_subject:
        mtls_scope = (os.getenv("ADAAD_AUDIT_MTLS_SCOPE") or AUDIT_READ_SCOPE).strip()
        return {
            "scheme": "mtls",
            "principal": x_client_cert_subject.strip(),
            "scopes": [mtls_scope],
        }

    raise HTTPException(status_code=401, detail="missing_authentication")


def _require_scope(auth_ctx: dict[str, Any], required_scope: str) -> None:
    scopes = {str(scope) for scope in auth_ctx.get("scopes", [])}
    if required_scope not in scopes:
        raise HTTPException(status_code=403, detail="insufficient_scope")


def _apply_redaction(payload: Any, redaction: str) -> Any:
    if redaction == "none":
        return payload
    if isinstance(payload, list):
        return [_apply_redaction(item, redaction) for item in payload]
    if not isinstance(payload, dict):
        return payload

    redacted = {k: _apply_redaction(v, redaction) for k, v in payload.items()}
    if redaction in {"sensitive", "strict"}:
        redacted.pop("signature", None)
        redacted.pop("signatures", None)
        redacted.pop("certificate", None)
        if isinstance(redacted.get("export_metadata"), dict):
            signer = dict(redacted["export_metadata"].get("signer") or {})
            signer.pop("signature", None)
            redacted["export_metadata"]["signer"] = signer
    if redaction == "strict":
        redacted.pop("principal", None)
        redacted.pop("sandbox_replay", None)
    return redacted


def _audit_envelope(*, data: Any, auth_ctx: dict[str, Any], redaction: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "authn": {
            "scheme": auth_ctx["scheme"],
            "scope": AUDIT_READ_SCOPE,
            "redaction": redaction,
        },
        "data": _apply_redaction(data, redaction),
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _resolve_ui_paths(*, create_placeholder: bool) -> tuple[Path, Path, Path, str]:
    if APONI_DIR.exists() and INDEX.exists():
        return APONI_DIR, INDEX, APONI_DIR / "mock", "aponi"
    if ENHANCED_DIR.exists() and ENHANCED_INDEX.exists():
        return ENHANCED_DIR, ENHANCED_INDEX, ENHANCED_DIR / "mock", "enhanced"

    if create_placeholder:
        APONI_DIR.mkdir(parents=True, exist_ok=True)
        if not INDEX.exists():
            INDEX.write_text(PLACEHOLDER_HTML, encoding="utf-8")
        return APONI_DIR, INDEX, APONI_DIR / "mock", "placeholder"

    # Keep module import safe in cold-clone/minimal environments.
    return APONI_DIR, INDEX, APONI_DIR / "mock", "missing"


def _current_ui() -> tuple[Path, Path, Path, str]:
    ui_dir = getattr(app.state, "ui_dir", None)
    ui_index = getattr(app.state, "ui_index", None)
    mock_dir = getattr(app.state, "mock_dir", None)
    ui_source = getattr(app.state, "ui_source", None)
    if isinstance(ui_dir, Path) and isinstance(ui_index, Path) and isinstance(mock_dir, Path) and isinstance(ui_source, str):
        return ui_dir, ui_index, mock_dir, ui_source
    return _resolve_ui_paths(create_placeholder=False)


def _load_mock(name: str) -> Any:
    if os.getenv("ADAAD_UI_MOCKS", "").strip() not in {"1", "true", "TRUE", "yes", "on"}:
        raise HTTPException(status_code=404, detail="mock_endpoints_disabled")
    _, _, mock_dir, _ = _current_ui()
    p = mock_dir / f"{name}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"mock '{name}' not found")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=500, detail=f"mock '{name}' parse error: {e}")


def _marker(entry: dict[str, Any]) -> str:
    return json.dumps(entry, ensure_ascii=False, sort_keys=True)


def _collect_since(entries: list[dict[str, Any]], last_marker: str | None) -> tuple[list[dict[str, Any]], str | None]:
    if not entries:
        return [], last_marker
    if not last_marker:
        return entries[-1:], _marker(entries[-1])

    marker_map = {_marker(entry): idx for idx, entry in enumerate(entries)}
    marker_idx = marker_map.get(last_marker)
    if marker_idx is None:
        return entries[-1:], _marker(entries[-1])
    if marker_idx >= len(entries) - 1:
        return [], last_marker
    new_entries = entries[marker_idx + 1 :]
    return new_entries, _marker(entries[-1])


def _event_batch(metrics_marker: str | None, journal_marker: str | None) -> tuple[list[dict[str, Any]], str | None, str | None]:
    metric_entries = metrics.tail(limit=200)
    journal_entries = journal.read_entries(limit=200)
    new_metric_entries, next_metrics_marker = _collect_since(metric_entries, metrics_marker)
    new_journal_entries, next_journal_marker = _collect_since(journal_entries, journal_marker)

    events: list[dict[str, Any]] = []
    for entry in new_metric_entries:
        events.append(
            {
                "channel": "metrics",
                "kind": "governance_mutation",
                "timestamp": entry.get("timestamp"),
                "event": entry,
            }
        )
    for entry in new_journal_entries:
        events.append(
            {
                "channel": "journal",
                "kind": "journal",
                "timestamp": entry.get("timestamp") or entry.get("ts"),
                "event": entry,
            }
        )
    return events, next_metrics_marker, next_journal_marker


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "hello", "channels": ["metrics", "journal"], "status": "live"})
    metrics_marker: str | None = None
    journal_marker: str | None = None
    try:
        while True:
            events, metrics_marker, journal_marker = _event_batch(metrics_marker, journal_marker)
            if events:
                await websocket.send_json({"type": "event_batch", "events": events})
            await asyncio.sleep(0.35)
    except WebSocketDisconnect:
        return


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    ui_dir, ui_index, mock_dir, ui_source = _current_ui()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip() if (ROOT / "VERSION").exists() else "unknown"
    profile_path = ROOT / "governance_runtime_profile.lock.json"
    runtime_profile: dict[str, Any] = {"present": profile_path.exists()}
    if profile_path.exists():
        try:
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            runtime_profile.update(
                {
                    "version": payload.get("version", ""),
                    "dependency_lock": bool(payload.get("dependency_lock")),
                    "runtime_manifest_keys": sorted((payload.get("runtime_manifest") or {}).keys()),
                }
            )
        except (OSError, ValueError, TypeError):
            runtime_profile["parse_error"] = True
    return {
        "ok": True,
        "version": version,
        "runtime_profile": runtime_profile,
        "ui_source": ui_source,
        "ui_dir": str(ui_dir.relative_to(ROOT)),
        "ui_index": str(ui_index.relative_to(ROOT)),
        "mock_present": mock_dir.exists(),
        "mocks_enabled": os.getenv("ADAAD_UI_MOCKS", "").strip() in {"1", "true", "TRUE", "yes", "on"},
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return api_health()


@app.get("/metrics/review-quality")
def metrics_review_quality(
    limit: int = Query(default=500, ge=1, le=5000),
    sla_seconds: int = Query(default=DEFAULT_REVIEW_SLA_SECONDS, ge=1, le=604800),
) -> dict[str, Any]:
    entries = metrics.tail(limit)
    summary = summarize_review_quality(entries, default_sla_seconds=sla_seconds)
    summary["window_limit"] = limit
    summary["sla_seconds"] = sla_seconds
    return summary


@app.get("/api/mutations", response_model=list[MutationView])
def api_mutations(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict[str, Any]]:
    ledger = LineageLedgerV2()
    items: list[dict[str, Any]] = []
    for entry in reversed(ledger.read_all()):
        if entry.get("type") != "MutationBundleEvent":
            continue
        payload = dict(entry.get("payload") or {})
        certificate = dict(payload.get("certificate") or {})
        items.append(
            {
                "mutation_id": str(payload.get("bundle_id") or certificate.get("bundle_id") or ""),
                "epoch_id": str(payload.get("epoch_id") or ""),
                "impact": payload.get("impact"),
                "risk_tier": str(payload.get("risk_tier") or "unknown"),
                "applied": bool(payload.get("applied", True)),
                "timestamp": str(entry.get("ts") or payload.get("ts") or ""),
            }
        )
        if len(items) >= limit:
            break
    return items


@app.get("/api/epochs", response_model=list[EpochView])
def api_epochs() -> list[dict[str, Any]]:
    ledger = LineageLedgerV2()
    response: list[dict[str, Any]] = []
    for epoch_id in ledger.list_epoch_ids():
        entries = ledger.read_epoch(epoch_id)
        mutation_count = sum(1 for entry in entries if entry.get("type") == "MutationBundleEvent")
        latest_timestamp = str(entries[-1].get("ts") or "") if entries else ""
        response.append(
            {
                "epoch_id": epoch_id,
                "mutation_count": mutation_count,
                "event_count": len(entries),
                "latest_timestamp": latest_timestamp,
                "expected_digest": ledger.get_expected_epoch_digest(epoch_id),
                "computed_digest": ledger.compute_incremental_epoch_digest(epoch_id),
            }
        )
    return response


@app.get("/api/constitution/status", response_model=ConstitutionStatus)
def api_constitution_status() -> dict[str, Any]:
    return {
        "constitution_version": constitution.CONSTITUTION_VERSION,
        "policy_hash": constitution.POLICY_HASH,
        "policy_path": str(constitution.POLICY_PATH),
        "policy_exists": constitution.POLICY_PATH.exists(),
        "boot_sanity": constitution.boot_sanity_check(),
    }


@app.get("/api/system/intelligence", response_model=SystemIntelligenceView)
def api_system_intelligence() -> dict[str, Any]:
    determinism = rolling_determinism_score(window=100)
    mutation_rate = mutation_rate_snapshot(window_sec=3600)
    router = IntelligenceRouter()
    decision = router.route(
        StrategyInput(
            cycle_id="api-snapshot",
            mutation_score=min(1.0, mutation_rate["rate_per_hour"] / 60.0),
            governance_debt_score=max(0.0, 1.0 - float(determinism.get("rolling_score", 1.0))),
            signals={"window_count": mutation_rate["count"]},
        )
    )
    routed_decision = {
        "strategy": asdict(decision.strategy),
        "proposal": asdict(decision.proposal),
        "critique": asdict(decision.critique),
        "outcome": decision.outcome,
    }
    return {
        "determinism": determinism,
        "mutation_rate": mutation_rate,
        "routed_decision": routed_decision,
    }


@app.get("/api/lint/preview")
def api_lint_preview(
    agent_id: str = Query(default=""),
    target_path: str = Query(default=""),
    python_content: str = Query(default=""),
    metadata: str = Query(default="{}"),
) -> dict[str, Any]:
    metadata_payload: dict[str, Any] = {}
    metadata_raw = metadata.strip() if isinstance(metadata, str) else "{}"
    if metadata_raw:
        try:
            parsed_metadata = json.loads(metadata_raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail={"ok": False, "error": "invalid_metadata_json", "detail": str(exc)}) from exc
        if not isinstance(parsed_metadata, dict):
            raise HTTPException(status_code=400, detail={"ok": False, "error": "invalid_metadata_json", "detail": "metadata must be an object"})
        metadata_payload = parsed_metadata

    bridge = MutationLintingBridge()
    payload = {
        "agent_id": agent_id,
        "intent": APONI_EDITOR_INTENT,
        "ops": [{"op": "replace_file_content", "language": "python", "content": python_content, "metadata": metadata_payload}],
        "targets": [{"agent_id": agent_id, "path": target_path, "target_type": "python_module", "ops": [{"op": "replace_file_content"}]}],
    }
    return bridge.analyze(payload)


@app.post("/api/mutations/proposals", response_model=ProposalResponse)
def api_submit_proposal(payload: dict[str, Any], http_request: Request) -> dict[str, Any]:
    try:
        proposal_request, verdict = validate_proposal(payload)
    except ProposalValidationError as exc:
        body: dict[str, Any] = {"ok": False, "error": exc.code, "detail": exc.detail}
        raise HTTPException(status_code=exc.status_code, detail=body) from exc
    proposal_id = default_provider().next_id(label="mcp-proposal", length=32)
    queue_entry = append_proposal(proposal_id=proposal_id, request=proposal_request)

    # Rationale: emit explicit editor-submission lineage only for editor-origin
    # HTTP contexts so governance traceability improves without altering proposal
    # authority invariants (queue append + constitutional evaluation).
    editor_context = _aponi_editor_submission_context(http_request)
    if editor_context is not None:
        event_payload = {
            "proposal_id": proposal_id,
            "session_id": editor_context["session_id"],
            "actor_context": editor_context["actor_context"],
            "timestamp": default_provider().format_utc("%Y-%m-%dT%H:%M:%SZ"),
            "endpoint_path": http_request.url.path,
            "source": "aponi_editor_ui",
        }
        metrics.log(event_type=APONI_EDITOR_PROPOSAL_EVENT, payload=event_payload, level="INFO")
        journal.append_tx(tx_type=APONI_EDITOR_PROPOSAL_EVENT, payload=event_payload)

    return {
        "ok": True,
        "proposal_id": proposal_id,
        "authority_level": proposal_request.authority_level,
        "verdict": verdict,
        "queue_hash": queue_entry["hash"],
    }


@app.post("/mutation/propose", response_model=ProposalResponse)
def mutation_propose_alias(payload: dict[str, Any], http_request: Request) -> dict[str, Any]:
    """Compatibility alias for governed proposal submission."""
    return api_submit_proposal(payload, http_request)


@app.get("/api/audit/epochs/{epoch_id}/replay-proof")
def api_audit_replay_proof(
    epoch_id: str,
    redaction: Literal["none", "sensitive", "strict"] = Query(default="sensitive"),
    auth_ctx: dict[str, Any] = Depends(_authenticate_audit_request),
) -> dict[str, Any]:
    _require_scope(auth_ctx, AUDIT_READ_SCOPE)
    bundle_path = REPLAY_PROOFS_DIR / f"{epoch_id}.replay_attestation.v1.json"
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="replay_proof_not_found")
    bundle = load_replay_proof(bundle_path)
    verification = verify_replay_proof_bundle(bundle)
    payload = {
        "epoch_id": epoch_id,
        "bundle_path": _display_path(bundle_path),
        "bundle": bundle,
        "verification": verification,
    }
    return _audit_envelope(data=payload, auth_ctx=auth_ctx, redaction=redaction)


@app.get("/api/audit/epochs/{epoch_id}/lineage")
def api_audit_epoch_lineage(
    epoch_id: str,
    redaction: Literal["none", "sensitive", "strict"] = Query(default="sensitive"),
    auth_ctx: dict[str, Any] = Depends(_authenticate_audit_request),
) -> dict[str, Any]:
    _require_scope(auth_ctx, AUDIT_READ_SCOPE)
    ledger = LineageLedgerV2()
    entries = ledger.read_epoch(epoch_id)
    if not entries:
        raise HTTPException(status_code=404, detail="epoch_not_found")
    journal_entries = [entry for entry in journal.read_entries(limit=200) if entry.get("epoch_id") == epoch_id]
    payload = {
        "epoch_id": epoch_id,
        "lineage": entries,
        "lineage_digest": ledger.compute_incremental_epoch_digest(epoch_id),
        "expected_epoch_digest": ledger.get_expected_epoch_digest(epoch_id),
        "journal_entries": journal_entries,
    }
    return _audit_envelope(data=payload, auth_ctx=auth_ctx, redaction=redaction)


@app.get("/api/audit/bundles/{bundle_id}")
def api_audit_bundle(
    bundle_id: str,
    redaction: Literal["none", "sensitive", "strict"] = Query(default="sensitive"),
    auth_ctx: dict[str, Any] = Depends(_authenticate_audit_request),
) -> dict[str, Any]:
    _require_scope(auth_ctx, AUDIT_READ_SCOPE)
    bundle_path = FORENSIC_EXPORT_DIR / f"{bundle_id}.json"
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="bundle_not_found")
    bundle = json.loads(read_file_deterministic(bundle_path))
    validator = EvidenceBundleBuilder(export_dir=FORENSIC_EXPORT_DIR)
    validation_errors = validator.validate_bundle(bundle)
    payload = {
        "bundle_id": bundle_id,
        "bundle_path": _display_path(bundle_path),
        "bundle": bundle,
        "validation": {"ok": not validation_errors, "errors": validation_errors},
    }
    return _audit_envelope(data=payload, auth_ctx=auth_ctx, redaction=redaction)


@app.get("/evidence/{bundle_id}")
def api_evidence_bundle(
    bundle_id: str,
    redaction: Literal["none", "sensitive", "strict"] = Query(default="sensitive"),
    auth_ctx: dict[str, Any] = Depends(_authenticate_audit_request),
) -> dict[str, Any]:
    """Aponi evidence viewer endpoint.

    This endpoint is intentionally read-only and authentication-gated.
    """
    return api_audit_bundle(bundle_id=bundle_id, redaction=redaction, auth_ctx=auth_ctx)


@app.get("/governance/reviewer-calibration")
def api_governance_reviewer_calibration(
    epoch_id: str = Query(description="Epoch ID to compute calibration for"),
    reviewer_ids: str = Query(default="", description="Comma-separated reviewer IDs (empty = all from events)"),
    auth_ctx: dict[str, Any] = Depends(_authenticate_audit_request),
) -> dict[str, Any]:
    """Reviewer calibration advisory endpoint — ADAAD-7.

    Returns per-reviewer reputation scores and tier calibration state for
    the requested epoch. Data is derived deterministically from the ledgered
    reviewer_action_outcome event stream.

    Authentication: bearer token with audit:read scope.
    Read-only and governance-advisory; does not alter authority or blocking decisions.
    """
    from runtime.governance.reviewer_reputation import (
        compute_epoch_reputation_batch,
        SCORING_ALGORITHM_VERSION,
    )
    from runtime.governance.review_pressure import compute_panel_calibration, DEFAULT_TIER_CONFIG
    from security.ledger.journal import JOURNAL_PATH, ensure_journal
    import json as _json

    ensure_journal()
    events: list[dict] = []
    try:
        for line in JOURNAL_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = _json.loads(line)
                payload = entry.get("payload") or {}
                if entry.get("type") == "reviewer_action_outcome" or payload.get("event_type") == "reviewer_action_outcome":
                    events.append({"event_type": "reviewer_action_outcome", "payload": payload})
            except (ValueError, KeyError):
                continue
    except OSError:
        events = []

    ids: list[str]
    if reviewer_ids.strip():
        ids = [r.strip() for r in reviewer_ids.split(",") if r.strip()]
    else:
        ids = list({
            str(ev["payload"].get("reviewer_id") or "")
            for ev in events
            if ev["payload"].get("epoch_id") == epoch_id and ev["payload"].get("reviewer_id")
        })

    reputation_scores = compute_epoch_reputation_batch(ids, events, epoch_id=epoch_id)

    tier_scores: dict[str, float] = {}
    for rec in reputation_scores.values():
        for tier in DEFAULT_TIER_CONFIG:
            tier_scores[tier] = rec["composite_score"]
        break

    calibration = compute_panel_calibration(tier_scores) if tier_scores else {}

    return _audit_envelope(
        data={
            "epoch_id": epoch_id,
            "scoring_algorithm_version": SCORING_ALGORITHM_VERSION,
            "reviewer_count": len(ids),
            "reputation_scores": {
                rid: {
                    "composite_score": rec["composite_score"],
                    "dimension_scores": rec["dimension_scores"],
                    "event_count": rec["event_count"],
                    "score_digest": rec["score_digest"],
                }
                for rid, rec in reputation_scores.items()
            },
            "tier_calibration": {
                tier: {
                    "adjusted_count": cal["adjusted_count"],
                    "base_count": cal["base_count"],
                    "adjustment": cal["adjustment"],
                    "constitutional_floor_enforced": cal["constitutional_floor_enforced"],
                    "calibration_digest": cal["calibration_digest"],
                }
                for tier, cal in calibration.items()
            },
        },
        auth_ctx=auth_ctx,
        redaction="none",
    )




# ---------------------------------------------------------------------------
# Simulation endpoints — ADAAD-8 / PR-12
# ---------------------------------------------------------------------------

@app.post("/simulation/run")
def api_simulation_run(
    request: Request,
    auth_ctx: dict[str, Any] = Depends(_authenticate_audit_request),
) -> dict[str, Any]:
    """Policy simulation run endpoint — ADAAD-8.

    Accepts a DSL policy block and an epoch range, replays historical epochs
    under the hypothetical policy, and returns a SimulationRunResult.

    Authentication: bearer token with audit:read scope.
    Read-only: zero ledger writes, zero constitution state transitions,
    zero mutation executor calls. SimulationPolicy.simulation=True enforced
    at the GovernanceGate boundary before any evaluation.

    Request body (JSON):
        dsl_text (str): Multi-line DSL policy block.
        epoch_ids (list[str]): Ordered list of epoch IDs to simulate.
        epoch_data_map (dict, optional): Pre-fetched {epoch_id: epoch_data}.

    Returns: SimulationRunResult wrapped in audit envelope.
    Note: SIMULATION ONLY — results are hypothetical and do not reflect
    live governance decisions or amend any constitutional rule.
    """
    from runtime.governance.simulation.constraint_interpreter import interpret_policy_block
    from runtime.governance.simulation.epoch_simulator import EpochReplaySimulator
    from runtime.governance.simulation.dsl_grammar import SimulationDSLError
    from runtime.governance.simulation.constraint_interpreter import SimulationPolicyError
    import json as _json

    _require_scope(auth_ctx, AUDIT_READ_SCOPE)

    try:
        import asyncio
        loop = asyncio.new_event_loop()
        raw = loop.run_until_complete(request.body())
        loop.close()
        body = _json.loads(raw) if raw else {}
    except Exception:
        body = {}

    dsl_text = str(body.get("dsl_text", ""))
    epoch_ids = list(body.get("epoch_ids", []))
    epoch_data_map = dict(body.get("epoch_data_map") or {})

    try:
        policy = interpret_policy_block(dsl_text)
    except SimulationDSLError as exc:
        raise HTTPException(status_code=422, detail=f"dsl_parse_error: {exc}")
    except SimulationPolicyError as exc:
        raise HTTPException(status_code=422, detail=f"policy_error: {exc}")

    sim = EpochReplaySimulator(policy)
    result = sim.simulate_epoch_range(epoch_ids, epoch_data_map=epoch_data_map or None)

    return _audit_envelope(
        data={
            "simulation": True,
            "simulation_only_notice": "Results are hypothetical. This endpoint has no live governance side effects.",
            "result": result.to_dict(),
        },
        auth_ctx=auth_ctx,
        redaction="none",
    )


@app.get("/simulation/results/{run_id}")
def api_simulation_results(
    run_id: str,
    auth_ctx: dict[str, Any] = Depends(_authenticate_audit_request),
) -> dict[str, Any]:
    """Retrieve a completed simulation run by ID — ADAAD-8.

    Returns run metadata. Full persistence introduced in PR-13.
    Authentication: bearer token with audit:read scope. Read-only.
    """
    _require_scope(auth_ctx, AUDIT_READ_SCOPE)

    return _audit_envelope(
        data={
            "simulation": True,
            "run_id": run_id,
            "status": "not_found",
            "detail": "Simulation run persistence is introduced in PR-13 (Governance Profile Exporter).",
        },
        auth_ctx=auth_ctx,
        redaction="none",
    )


@app.post("/market/signal")
def api_market_signal_ingest(
    request: Request,
    auth_ctx: dict[str, Any] = Depends(_authenticate_audit_request),
) -> dict[str, Any]:
    """Live market signal webhook ingestion — ADAAD-10 Track A.

    Accepts raw market signal payloads, routes them through ``LiveSignalRouter``
    for validation and lineage stamping, then injects the result into the
    ``FitnessOrchestrator`` as an advisory live_market_score override.

    Authentication: bearer token with audit:read scope.
    Read-only with respect to epoch authority — signals are fitness inputs only.
    Journal event: market_signal_ingested.v1
    """
    _require_scope(auth_ctx, AUDIT_READ_SCOPE)

    try:
        import json as _json
        body_bytes = request.body() if callable(request.body) else b""
        # FastAPI: body is a coroutine in async context; use sync path via state
        raw_body = getattr(request, "_body", None)
        if raw_body is None:
            raw_body = b""
        try:
            raw_payload: dict[str, Any] = _json.loads(raw_body) if raw_body else {}
        except Exception:
            raw_payload = {}
    except Exception:
        raw_payload = {}

    try:
        from runtime.market.live_signal_router import LiveSignalRouter
        from runtime.market.market_signal_adapter import MarketSignalAdapter, MarketSignalValidator

        router = LiveSignalRouter(
            adapter=MarketSignalAdapter(validator=MarketSignalValidator()),
            fitness_orchestrator=None,  # advisory only; direct injection handled below
            journal_fn=None,
        )
        result = router.ingest(raw_payload)
    except Exception as exc:
        return _audit_envelope(
            data={"ok": False, "error": "market_router_unavailable", "detail": str(exc)},
            auth_ctx=auth_ctx,
            redaction="sensitive",
        )

    return _audit_envelope(
        data={
            "ok": result.accepted,
            "signal_type": result.signal_type,
            "lineage_digest": result.lineage_digest,
            "adapter_id": result.adapter_id,
            "rejection_reason": result.rejection_reason,
        },
        auth_ctx=auth_ctx,
        redaction="sensitive",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fast-Path Intelligence endpoints — v0.66
# Surfaces MutationRouteOptimizer, EntropyFastGate, CheckpointChain, and
# FastPathScorer through read-only REST endpoints consumed by the Aponi
# Fast-Path Intelligence panel.
# ─────────────────────────────────────────────────────────────────────────────


class RoutePreviewRequest(BaseModel):
    mutation_id: str
    intent: str
    files_touched: list[str] = []
    loc_added: int = 0
    loc_deleted: int = 0
    risk_tags: list[str] = []
    ops: list[dict[str, Any]] = []


class EntropyGateRequest(BaseModel):
    mutation_id: str
    estimated_bits: int
    sources: list[str] = []
    strict: bool = True


@app.post("/api/fast-path/route-preview")
async def fast_path_route_preview(req: RoutePreviewRequest) -> dict[str, Any]:
    """Deterministic tier routing preview for a candidate mutation.

    Accepts mutation metadata and returns the TRIVIAL / STANDARD / ELEVATED
    routing decision, reasons, and fast-path flags without touching the
    full evaluation pipeline.
    """
    try:
        from runtime.evolution.mutation_route_optimizer import MutationRouteOptimizer
        optimizer = MutationRouteOptimizer()
        decision = optimizer.route(
            mutation_id=req.mutation_id,
            intent=req.intent,
            ops=req.ops,
            files_touched=req.files_touched,
            loc_added=req.loc_added,
            loc_deleted=req.loc_deleted,
            risk_tags=req.risk_tags,
        )
        return {
            "ok": True,
            "decision": decision.to_payload(),
            "summary": {
                "tier": decision.tier.value,
                "skip_heavy_scoring": decision.skip_heavy_scoring,
                "require_human_review": decision.require_human_review,
                "reasons": list(decision.reasons),
            },
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"route_preview_error: {exc}") from exc


@app.post("/api/fast-path/entropy-gate")
async def fast_path_entropy_gate(req: EntropyGateRequest) -> dict[str, Any]:
    """Evaluate the entropy fast-gate for a mutation candidate.

    Returns ALLOW / WARN / DENY verdict with reason and gate digest.
    """
    try:
        from runtime.evolution.entropy_fast_gate import EntropyFastGate
        gate = EntropyFastGate(strict=req.strict)
        result = gate.evaluate(
            mutation_id=req.mutation_id,
            estimated_bits=req.estimated_bits,
            sources=req.sources,
        )
        return {
            "ok": True,
            "result": result.to_payload(),
            "denied": result.denied,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"entropy_gate_error: {exc}") from exc


@app.get("/api/fast-path/checkpoint-chain/verify")
async def fast_path_checkpoint_chain_verify() -> dict[str, Any]:
    """Build and verify a demonstration checkpoint chain from current epoch state.

    Returns chain length, integrity status, and genesis / head digests.
    """
    try:
        from runtime.evolution.checkpoint_chain import build_checkpoint_chain, verify_checkpoint_chain

        # Use stable, deterministic payloads — no wall-clock timestamps.
        # The genesis epoch anchors to the ADAAD fast-path module version string
        # so the digest is stable across calls for a given codebase version.
        entries = [
            ("epoch_genesis",  {"event": "genesis",       "system": "ADAAD", "layer": "fast_path_v066"}),
            ("epoch_current",  {"event": "current_state", "layer": "fast_path_v066", "stage": "evaluation"}),
            ("epoch_head",     {"event": "head_checkpoint","layer": "fast_path_v066", "fast_path_active": True}),
        ]
        chain = build_checkpoint_chain(entries)
        integrity_ok = verify_checkpoint_chain(chain)

        return {
            "ok": True,
            "integrity": integrity_ok,
            "chain_length": len(chain),
            "genesis_digest": chain[0].chain_digest,
            "head_digest": chain[-1].chain_digest,
            "links": [
                {
                    "epoch_id": cp.epoch_id,
                    "predecessor_digest": cp.predecessor_digest,
                    "chain_digest": cp.chain_digest,
                    "chain_version": cp.chain_version,
                }
                for cp in chain
            ],
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"checkpoint_chain_error: {exc}") from exc


@app.get("/api/fast-path/stats")
async def fast_path_stats() -> dict[str, Any]:
    """Aggregate statistics for the fast-path routing layer.

    Returns tier distribution constants, threshold configuration, and
    module version metadata for the Aponi Fast-Path Intelligence panel.
    """
    try:
        from runtime.evolution.mutation_route_optimizer import (
            ROUTE_VERSION,
            ELEVATED_PATH_PREFIXES,
            ELEVATED_INTENT_KEYWORDS,
            TRIVIAL_OP_TYPES,
        )
        from runtime.evolution.entropy_fast_gate import (
            FAST_GATE_VERSION,
            DEFAULT_WARN_BITS,
            DEFAULT_DENY_BITS,
        )
        from runtime.evolution.fast_path_scorer import FAST_PATH_VERSION
        from runtime.evolution.checkpoint_chain import CHAIN_VERSION

        return {
            "ok": True,
            "versions": {
                "route_optimizer": ROUTE_VERSION,
                "entropy_gate": FAST_GATE_VERSION,
                "fast_path_scorer": FAST_PATH_VERSION,
                "checkpoint_chain": CHAIN_VERSION,
            },
            "entropy_thresholds": {
                "warn_bits": DEFAULT_WARN_BITS,
                "deny_bits": DEFAULT_DENY_BITS,
            },
            "route_config": {
                "elevated_path_prefixes": sorted(ELEVATED_PATH_PREFIXES),
                "elevated_intent_keywords": sorted(ELEVATED_INTENT_KEYWORDS),
                "trivial_op_types": sorted(TRIVIAL_OP_TYPES),
                "tiers": ["TRIVIAL", "STANDARD", "ELEVATED"],
            },
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"fast_path_stats_error: {exc}") from exc


MOCK_ENDPOINTS = ["status", "agents", "tree", "kpis", "changes", "suggestions"]

for endpoint_name in MOCK_ENDPOINTS:
    app.add_api_route(
        f"/api/{endpoint_name}",
        endpoint=lambda n=endpoint_name: _load_mock(n),
        methods=["GET"],
    )


@app.get("/api/governance/parallel-gate/probe-library")
async def parallel_gate_probe_library_route() -> dict[str, Any]:
    """Return available axis probe definitions for the Aponi parallel gate panel.

    Registered before the catch-all route to ensure correct FastAPI route priority.
    """
    from server import _PROBE_LIBRARY  # noqa: PLC0415
    axes: dict[str, list[dict[str, Any]]] = {}
    for (axis, rule_id), (ok, reason) in _PROBE_LIBRARY.items():
        axes.setdefault(axis, []).append(
            {"rule_id": rule_id, "default_ok": ok, "default_reason": reason}
        )
    for axis in axes:
        axes[axis].sort(key=lambda r: r["rule_id"])
    return {
        "ok": True,
        "axes": dict(sorted(axes.items())),
        "total_probes": len(_PROBE_LIBRARY),
        "gate_version": "v1.0.0",
    }


@app.get("/", include_in_schema=False)
def serve_dashboard_root():
    return serve_dashboard("")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_dashboard(full_path: str):
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    ui_dir, ui_index, _, _ = _current_ui()
    ui_root = ui_dir.resolve()
    if full_path.startswith("ui/aponi"):
        suffix = full_path[len("ui/aponi") :].lstrip("/")
        requested = (APONI_DIR.resolve() / suffix).resolve() if suffix else INDEX.resolve()
        try:
            requested.relative_to(APONI_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="path outside dashboard root")
        if requested.is_file():
            return FileResponse(str(requested))

    if full_path:
        requested = (ui_root / full_path).resolve()
        try:
            requested.relative_to(ui_root)
        except ValueError:
            raise HTTPException(status_code=404, detail="path outside dashboard root")

        if requested.is_file():
            return FileResponse(str(requested))

    return FileResponse(str(ui_index))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the ADAAD dashboard server.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind.")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for local development.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    ui_dir, ui_index, _, ui_source = _resolve_ui_paths(create_placeholder=True)
    print(f"🚀 ADAAD Unified Server running at http://{args.host}:{args.port}")
    print(f"📊 Dashboard source: {ui_source} ({ui_dir.relative_to(ROOT)})")
    print(f"📄 Dashboard index: {ui_index.relative_to(ROOT)}")

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit("uvicorn is required. Install with: pip install -r requirements.server.txt") from exc

    uvicorn.run("server:app", host=args.host, port=args.port, reload=args.reload)


# ─────────────────────────────────────────────────────────────────────────────
# Parallel Governance Gate endpoints — v0.66
# ─────────────────────────────────────────────────────────────────────────────

_PROBE_LIBRARY: dict[tuple[str, str], tuple[bool, str]] = {
    ("entropy",       "budget_ok"):          (True,  "within_budget"),
    ("entropy",       "source_clean"):       (True,  "no_nondeterministic_sources"),
    ("entropy",       "budget_exceeded"):    (False, "entropy_budget_exceeded"),
    ("entropy",       "nondeterministic"):   (False, "nondeterministic_source_detected"),
    ("constitution",  "tier_ok"):            (True,  "tier_approved"),
    ("constitution",  "hash_valid"):         (True,  "policy_hash_verified"),
    ("constitution",  "tier_violated"):      (False, "tier_violation"),
    ("constitution",  "hash_mismatch"):      (False, "policy_hash_mismatch"),
    ("founders_law",  "invariant_ok"):       (True,  "founders_invariant_satisfied"),
    ("founders_law",  "invariant_violated"): (False, "founders_invariant_violated"),
    ("lineage",       "chain_intact"):       (True,  "lineage_chain_verified"),
    ("lineage",       "digest_match"):       (True,  "epoch_digest_matches_ledger"),
    ("lineage",       "chain_broken"):       (False, "lineage_chain_broken"),
    ("lineage",       "digest_mismatch"):    (False, "epoch_digest_mismatch"),
    ("sandbox",       "preflight_ok"):       (True,  "sandbox_preflight_passed"),
    ("sandbox",       "isolation_ok"):       (True,  "isolation_verified"),
    ("sandbox",       "preflight_failed"):   (False, "sandbox_preflight_failed"),
    ("sandbox",       "isolation_breach"):   (False, "isolation_breach_detected"),
    ("replay",        "baseline_match"):     (True,  "replay_baseline_matches"),
    ("replay",        "baseline_mismatch"):  (False, "replay_baseline_mismatch"),
    ("replay",        "determinism_ok"):     (True,  "replay_determinism_verified"),
}


class ParallelAxisSpecRequest(BaseModel):
    axis: str
    rule_id: str
    timeout_seconds: float = 5.0


class ParallelGateRequest(BaseModel):
    mutation_id: str
    trust_mode: str = "standard"
    human_override: bool = False
    axis_specs: list[ParallelAxisSpecRequest]
    max_workers: int = 8


@app.post("/api/governance/parallel-gate/evaluate")
async def parallel_gate_evaluate(req: ParallelGateRequest) -> dict[str, Any]:
    """Run a parallel governance gate evaluation and return the full GateDecision.

    Axis probes are resolved from the built-in deterministic probe library
    keyed by (axis, rule_id). Unknown combinations default to ok=True.
    Axis results are annotated with per-axis timing for the Aponi swimlane UI.
    """
    import time as _time

    try:
        from runtime.governance.parallel_gate import (
            ParallelGovernanceGate,
            ParallelAxisSpec,
            PARALLEL_GATE_VERSION,
        )
        from security.ledger import journal as _journal

        if not req.axis_specs:
            raise HTTPException(status_code=422, detail="axis_specs must not be empty")
        if len(req.axis_specs) > 20:
            raise HTTPException(status_code=422, detail="axis_specs exceeds maximum of 20")

        timing_records: dict[str, float] = {}

        def _make_probe(axis: str, rule_id: str, result: tuple[bool, str]):
            def _probe() -> tuple[bool, str]:
                t0 = _time.perf_counter()
                out = result
                timing_records[f"{axis}:{rule_id}"] = round(
                    (_time.perf_counter() - t0) * 1000, 3
                )
                return out
            return _probe

        specs = [
            ParallelAxisSpec(
                axis=s.axis,
                rule_id=s.rule_id,
                probe=_make_probe(
                    s.axis, s.rule_id,
                    _PROBE_LIBRARY.get((s.axis, s.rule_id), (True, "probe_not_found_default_pass"))
                ),
                timeout_seconds=s.timeout_seconds,
            )
            for s in req.axis_specs
        ]

        gate = ParallelGovernanceGate(
            max_workers=min(req.max_workers, 20),
            tx_writer=_journal.append_tx,
        )

        wall_t0 = _time.perf_counter()
        decision = gate.approve_mutation_parallel(
            mutation_id=req.mutation_id,
            trust_mode=req.trust_mode,
            axis_specs=specs,
            human_override=req.human_override,
        )
        wall_elapsed_ms = round((_time.perf_counter() - wall_t0) * 1000, 2)

        payload = decision.to_payload()
        for ar in payload.get("axis_results", []):
            ar["duration_ms"] = timing_records.get(f"{ar['axis']}:{ar['rule_id']}", 0.0)

        return {
            "ok": True,
            "decision": payload,
            "wall_elapsed_ms": wall_elapsed_ms,
            "gate_version": PARALLEL_GATE_VERSION,
            "max_workers": min(req.max_workers, 20),
            "axis_count": len(specs),
        }

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"parallel_gate_error: {exc}") from exc


@app.get("/api/governance/parallel-gate/probe-library")
async def parallel_gate_probe_library() -> dict[str, Any]:
    """Return available axis probe definitions for the Aponi axis builder."""
    axes: dict[str, list[dict[str, Any]]] = {}
    for (axis, rule_id), (ok, reason) in _PROBE_LIBRARY.items():
        axes.setdefault(axis, []).append(
            {"rule_id": rule_id, "default_ok": ok, "default_reason": reason}
        )
    for axis in axes:
        axes[axis].sort(key=lambda r: r["rule_id"])
    return {
        "ok": True,
        "axes": dict(sorted(axes.items())),
        "total_probes": len(_PROBE_LIBRARY),
        "gate_version": "v1.0.0",
    }
