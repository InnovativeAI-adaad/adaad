import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from runtime.mcp.server import create_app
from security import cryovant


def _jwt(secret: str, exp: int) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    msg = f"{header}.{payload}".encode()
    sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), msg, hashlib.sha256).digest()).decode().rstrip("=")
    return f"{header}.{payload}.{sig}"


def test_health_and_auth_and_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("ADAAD_MCP_JWT_SECRET", "secret")
    monkeypatch.setattr(cryovant, "KEYS_DIR", tmp_path)
    (tmp_path / "signing-key.pem").write_text("k", encoding="utf-8")
    app = create_app()
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.post("/mutation/rank", json={"mutation_ids": ["x"]}).status_code == 401
    expired = _jwt("secret", int(time.time()) - 10)
    assert client.post("/mutation/rank", json={"mutation_ids": ["x"]}, headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    ok = _jwt("secret", int(time.time()) + 500)
    assert client.get("/missing", headers={"Authorization": f"Bearer {ok}"}).status_code == 404


def test_propose_contracts(tmp_path, monkeypatch):
    monkeypatch.setenv("ADAAD_MCP_JWT_SECRET", "secret")
    monkeypatch.setattr(cryovant, "KEYS_DIR", tmp_path)
    (tmp_path / "signing-key.pem").write_text("k", encoding="utf-8")
    client = TestClient(create_app())
    tok = _jwt("secret", int(time.time()) + 500)
    hdr = {"Authorization": f"Bearer {tok}"}
    monkeypatch.setattr("runtime.mcp.proposal_validator.evaluate_mutation", lambda *_args, **_kwargs: {"passed": True, "verdicts": []})
    payload = {
        "agent_id": "claude-proposal-agent",
        "generation_ts": "2026-01-01T00:00:00Z",
        "intent": "x",
        "ops": [{"op": "replace", "value": "safe"}],
        "targets": [{"agent_id": "a", "path": "app/foo.py", "target_type": "file", "ops": []}],
        "signature": "s",
        "nonce": "n",
        "authority_level": "auto-execute",
    }
    resp = client.post("/mutation/propose", json=payload, headers=hdr)
    assert resp.status_code == 200
    assert resp.json()["authority_level"] == "governor-review"

    payload["targets"] = [{"agent_id": "a", "path": "security/cryovant.py", "target_type": "file", "ops": []}]
    assert client.post("/mutation/propose", json=payload, headers=hdr).status_code == 403

    payload["targets"] = [{"agent_id": "a", "path": "app/foo.py", "target_type": "file", "ops": []}]
    payload["ops"] = [{"op": "replace", "value": "eval('x')"}]
    assert client.post("/mutation/propose", json=payload, headers=hdr).status_code == 422


def test_startup_refuses_when_signing_key_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("ADAAD_MCP_JWT_SECRET", "secret")
    monkeypatch.setattr(cryovant, "KEYS_DIR", tmp_path)
    app = create_app()
    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass
