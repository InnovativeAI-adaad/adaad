from __future__ import annotations

import importlib
from pathlib import Path

from runtime import constants


def _reload_sync_module():
    module = importlib.import_module("runtime.integrations.aponi_sync")
    return importlib.reload(module)


def test_aponi_sync_default_url_uses_runtime_constant(monkeypatch):
    monkeypatch.delenv("APONI_API_URL", raising=False)
    module = _reload_sync_module()

    assert module.DEFAULT_APONI_URL == f"{constants.APONI_URL}/api/v1/events"
    assert module.DEFAULT_APONI_URL.startswith(f"http://localhost:{constants.APONI_PORT}")


def test_aponi_sync_honors_explicit_url_override(monkeypatch):
    override = "http://localhost:9999/api/v1/events"
    monkeypatch.setenv("APONI_API_URL", override)
    module = _reload_sync_module()

    assert module.DEFAULT_APONI_URL == override


def test_dashboard_port_fallback_references_runtime_constant_source():
    source = Path("ui/aponi_dashboard.py").read_text(encoding="utf-8")

    assert "from runtime.constants import APONI_PORT" in source
    assert 'os.environ.get("APONI_PORT", str(APONI_PORT))' in source


def test_dashboard_and_sync_share_aponi_port_source(monkeypatch):
    monkeypatch.delenv("APONI_API_URL", raising=False)
    sync = _reload_sync_module()

    source = Path("ui/aponi_dashboard.py").read_text(encoding="utf-8")
    assert f"http://localhost:{constants.APONI_PORT}" in sync.DEFAULT_APONI_URL
    assert 'str(APONI_PORT)' in source
