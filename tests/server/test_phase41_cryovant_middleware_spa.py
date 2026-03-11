"""
Phase 41 — Cryovant Gate Middleware + SPA Index Fallback
=========================================================

Tests:
  T41-G01  Gate OPEN  → gate state = locked: False
  T41-G02  Gate LOCKED by env → gate state = locked: True, source: env
  T41-G03  Gate LOCKED by file → gate state = locked: True, source: file
  T41-G04  server.py _GATE_OPEN_PATHS includes /api/health, /api/version, /api/nexus/health
  T41-G05  server.py _GATE_PROTECTED_PREFIXES includes nexus/handshake, governance, fast-path
  T41-G06  cryovant_gate_middleware defined, returns 423 + X-ADAAD-GATE header
  T41-G07  _assert_gate_open() removed from nexus_handshake and nexus_agents (middleware handles it)
  T41-S01  SPAStaticFiles still mounted at /
  T41-S02  Lifespan creates stub index.html instead of raising RuntimeError
  T41-S03  CORSMiddleware applied with localhost origins
  T41-S04  __main__ entry point with uvicorn.run present
  T41-D01  aponi_dashboard.py has _read_gate_state()
  T41-D02  aponi_dashboard.py do_GET enforces gate (returns 423)
  T41-D03  aponi_dashboard.py serves index.html as SPA fallback for unknown paths
  T41-D04  aponi_dashboard.py _send_json accepts status_code kwarg
  T41-D05  aponi_dashboard.py _run_background method intact
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.regression_standard
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


# ── helpers ────────────────────────────────────────────────────────────────

def _read_dashboard_gate_fn(tmp_lock_path: Path):
    """Extract and exec _read_gate_state from aponi_dashboard.py in isolation."""
    from pathlib import Path as _P
    src = (REPO_ROOT / "ui" / "aponi_dashboard.py").read_text()
    lines = src.splitlines()
    fn_lines: list[str] = []
    in_fn = False
    for line in lines:
        if line.startswith("def _read_gate_state"):
            in_fn = True
        if in_fn:
            fn_lines.append(line)
            # A new top-level def/class after we've started collecting → stop
            if in_fn and len(fn_lines) > 3 and line and not line[0].isspace() and fn_lines[0] != line:
                fn_lines.pop()
                break

    ns = {
        "os": os,
        "time": time,
        "Path": _P,
        "_DASHBOARD_GATE_LOCK_FILE": tmp_lock_path,
        "_DASHBOARD_GATE_PROTOCOL": "adaad-gate/1.0",
        "Dict": dict,
        "Any": object,
    }
    exec("\n".join(fn_lines), ns)
    return ns["_read_gate_state"]


# ── T41-G: Gate state tests ─────────────────────────────────────────────────

class TestGateState:
    @pytest.fixture(autouse=True)
    def _clean_env(self):
        backup = os.environ.copy()
        yield
        os.environ.clear()
        os.environ.update(backup)

    def test_gate_open_by_default(self, tmp_path):
        """T41-G01: no env var + no lock file → locked=False."""
        os.environ.pop("ADAAD_GATE_LOCKED", None)
        os.environ.pop("ADAAD_GATE_REASON", None)
        fn = _read_dashboard_gate_fn(tmp_path / "nonexistent.lock")
        result = fn()
        assert result["locked"] is False
        assert result["source"] == "default"
        assert result["protocol"] == "adaad-gate/1.0"

    def test_gate_locked_by_env(self, tmp_path):
        """T41-G02: ADAAD_GATE_LOCKED=1 → locked=True, source=env."""
        os.environ["ADAAD_GATE_LOCKED"] = "1"
        os.environ["ADAAD_GATE_REASON"] = "scheduled maintenance"
        fn = _read_dashboard_gate_fn(tmp_path / "nonexistent.lock")
        result = fn()
        assert result["locked"] is True
        assert result["source"] == "env"
        assert "maintenance" in (result["reason"] or "")

    def test_gate_locked_by_file(self, tmp_path):
        """T41-G03: gate.lock file present → locked=True, source=file."""
        os.environ.pop("ADAAD_GATE_LOCKED", None)
        lock = tmp_path / "gate.lock"
        lock.write_text("test deployment lock", encoding="utf-8")
        fn = _read_dashboard_gate_fn(lock)
        result = fn()
        assert result["locked"] is True
        assert result["source"] == "file"
        assert "test deployment lock" in (result["reason"] or "")


# ── T41-G/S: server.py source-level checks ─────────────────────────────────

class TestServerConstants:
    @pytest.fixture(scope="class")
    def src(self):
        return (REPO_ROOT / "server.py").read_text()

    # Gate open paths
    def test_gate_open_paths_defined(self, src):
        """T41-G04: _GATE_OPEN_PATHS constant defined."""
        assert "_GATE_OPEN_PATHS" in src

    def test_gate_open_includes_health(self, src):
        assert '"/api/health"' in src

    def test_gate_open_includes_version(self, src):
        assert '"/api/version"' in src

    def test_gate_open_includes_nexus_health(self, src):
        assert '"/api/nexus/health"' in src

    # Gate protected prefixes
    def test_gate_protected_includes_handshake(self, src):
        """T41-G05: nexus/handshake is protected."""
        assert '"/api/nexus/handshake"' in src

    def test_gate_protected_includes_governance(self, src):
        assert '"/api/governance/"' in src

    def test_gate_protected_includes_fast_path(self, src):
        assert '"/api/fast-path/"' in src

    # Middleware shape
    def test_middleware_defined(self, src):
        """T41-G06: cryovant_gate_middleware present."""
        assert "async def cryovant_gate_middleware" in src

    def test_middleware_returns_423(self, src):
        assert "status_code=423" in src

    def test_middleware_sets_gate_header(self, src):
        assert '"X-ADAAD-GATE": "locked"' in src

    # Per-endpoint _assert_gate_open removed
    def test_handshake_no_assert_gate(self, src):
        """T41-G07: _assert_gate_open() removed from nexus_handshake."""
        lines = src.splitlines()
        fn_lines: list[str] = []
        in_fn = False
        for line in lines:
            if "def nexus_handshake" in line:
                in_fn = True
            if in_fn:
                fn_lines.append(line)
                if in_fn and len(fn_lines) > 3 and line.strip().startswith("@app.get"):
                    break
        assert "_assert_gate_open()" not in "\n".join(fn_lines)

    def test_agents_no_assert_gate(self, src):
        """T41-G07: _assert_gate_open() removed from nexus_agents."""
        lines = src.splitlines()
        fn_lines: list[str] = []
        in_fn = False
        for line in lines:
            if "def nexus_agents" in line:
                in_fn = True
            if in_fn:
                fn_lines.append(line)
                if in_fn and len(fn_lines) > 3 and line.strip().startswith("@app.get"):
                    break
        assert "_assert_gate_open()" not in "\n".join(fn_lines)

    # SPA and lifespan
    def test_spa_mount_present(self, src):
        """T41-S01: SPAStaticFiles mounted at /."""
        assert 'app.mount("/", SPAStaticFiles' in src

    def test_lifespan_creates_stub(self, src):
        """T41-S02: lifespan writes stub index.html instead of raising."""
        assert "INDEX.write_text" in src

    def test_lifespan_no_hard_raise(self, src):
        """T41-S02: old RuntimeError on missing index removed."""
        assert 'raise RuntimeError("ui/aponi/index.html not found' not in src

    # CORS
    def test_cors_middleware_present(self, src):
        """T41-S03: CORSMiddleware added."""
        assert "CORSMiddleware" in src
        assert "add_middleware" in src

    def test_cors_allows_localhost(self, src):
        assert "localhost" in src

    # __main__
    def test_main_block_present(self, src):
        """T41-S04: python server.py entry point."""
        assert 'if __name__ == "__main__"' in src

    def test_main_uses_uvicorn(self, src):
        assert "uvicorn.run" in src


# ── T41-D: aponi_dashboard.py checks ───────────────────────────────────────

class TestAponiDashboard:
    @pytest.fixture(scope="class")
    def src(self):
        return (REPO_ROOT / "ui" / "aponi_dashboard.py").read_text()

    def test_read_gate_state_defined(self, src):
        """T41-D01: _read_gate_state() defined in dashboard."""
        assert "def _read_gate_state" in src

    def test_gate_lock_file_constant(self, src):
        """T41-D01: _DASHBOARD_GATE_LOCK_FILE defined."""
        assert "_DASHBOARD_GATE_LOCK_FILE" in src

    def test_gate_enforced_in_do_get(self, src):
        """T41-D02: do_GET checks gate for protected paths."""
        assert "_DASHBOARD_GATE_PROTECTED_PREFIXES" in src
        assert "cryovant_gate_locked" in src

    def test_gate_returns_423(self, src):
        """T41-D02: dashboard returns 423."""
        assert "status_code=423" in src

    def test_spa_fallback_serves_index(self, src):
        """T41-D03: unknown paths get index.html."""
        assert "_aponi_index" in src
        assert "_send_html" in src

    def test_send_json_status_code_param(self, src):
        """T41-D04: _send_json has status_code kwarg."""
        assert "def _send_json(self, payload, *, status_code: int = 200)" in src

    def test_run_background_intact(self, src):
        """T41-D05: _run_background method not removed."""
        assert "def _run_background(self, fn, *args, **kwargs):" in src
