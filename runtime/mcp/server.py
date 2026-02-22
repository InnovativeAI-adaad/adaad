# SPDX-License-Identifier: Apache-2.0
"""FastAPI MCP proposal writer server."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from runtime.mcp.candidate_ranker import rank_candidates
from runtime.mcp.mutation_analyzer import analyze_mutation
from runtime.mcp.proposal_queue import append_proposal
from runtime.mcp.proposal_validator import ProposalValidationError, validate_proposal
from runtime.mcp.rejection_explainer import explain_rejection
from runtime.mcp.tools_registry import tools_list_response
from security import cryovant


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _verify_jwt(request: Request) -> None:
    if request.url.path == "/health":
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_jwt")
    token = auth.split(" ", 1)[1].strip()
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        message = f"{header_b64}.{payload_b64}".encode("utf-8")
        secret = os.environ.get("ADAAD_MCP_JWT_SECRET", "").encode("utf-8")
        if not secret:
            raise HTTPException(status_code=401, detail="jwt_secret_unconfigured")
        expected = base64.urlsafe_b64encode(hmac.new(secret, message, hashlib.sha256).digest()).decode("utf-8").rstrip("=")
        if not hmac.compare_digest(expected, signature_b64):
            raise HTTPException(status_code=401, detail="invalid_jwt")
        payload = json.loads(_b64url_decode(payload_b64))
        exp = int(payload.get("exp", 0) or 0)
        if exp <= 0 or exp < int(__import__("time").time()):
            raise HTTPException(status_code=401, detail="expired_jwt")
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=401, detail="invalid_jwt") from exc


@asynccontextmanager
async def lifespan(_app: FastAPI):
    key_path = cryovant.KEYS_DIR / "signing-key.pem"
    if not key_path.exists():
        raise RuntimeError("audit_log_signing_key_absent")
    yield


def create_app(server_name: str = "mcp-proposal-writer") -> FastAPI:
    app = FastAPI(title=server_name, lifespan=lifespan)

    @app.middleware("http")
    async def jwt_middleware(request: Request, call_next):
        try:
            _verify_jwt(request)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        return await call_next(request)

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {"ok": True, "server": server_name}

    @app.get("/tools/list")
    async def tools_list() -> Dict[str, Any]:
        return tools_list_response(server_name)

    @app.post("/mutation/propose")
    async def mutation_propose(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            request, verdict = validate_proposal(payload)
        except ProposalValidationError as exc:
            body: Dict[str, Any] = {"ok": False, "error": exc.code, "detail": exc.detail}
            if exc.code == "pre_check_failed":
                try:
                    body["verdicts"] = json.loads(exc.detail)
                except Exception:
                    pass
            raise HTTPException(status_code=exc.status_code, detail=body)
        proposal_id = str(uuid.uuid4())
        queue_entry = append_proposal(proposal_id=proposal_id, request=request)
        return {
            "ok": True,
            "proposal_id": proposal_id,
            "authority_level": request.authority_level,
            "verdict": verdict,
            "queue_hash": queue_entry["hash"],
        }

    @app.post("/mutation/analyze")
    async def mutation_analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
        return analyze_mutation(payload)

    @app.post("/mutation/explain-rejection")
    async def mutation_explain_rejection(payload: Dict[str, Any]) -> Dict[str, Any]:
        mutation_id = str(payload.get("mutation_id") or "")
        try:
            return explain_rejection(mutation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="mutation_not_found") from exc

    @app.post("/mutation/rank")
    async def mutation_rank(payload: Dict[str, Any]) -> Dict[str, Any]:
        mutation_ids = payload.get("mutation_ids")
        if not isinstance(mutation_ids, list):
            raise HTTPException(status_code=400, detail="mutation_ids_required")
        try:
            return rank_candidates([str(mid) for mid in mutation_ids])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MCP server")
    parser.add_argument("--server", default="mcp-proposal-writer")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8091)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(create_app(args.server), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
