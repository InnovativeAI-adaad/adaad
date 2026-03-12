# SPDX-License-Identifier: Apache-2.0
"""
Phase 56 fix tests — Cryovant gate does not block dashboard on initial load

Verifies the three invariants of the fix:
1. loadGate() never restores a locked state from localStorage (persisted lock cleared)
2. Backend-unreachable sets connecting state, NOT locked (overlay hidden)
3. Only a confirmed live 423 triggers setGateLocked()
4. HTML: overlay only wired to gate.locked, not to gate.connecting
5. setGateConnecting() function exists and is called in the right places

Test IDs: T56-G01..G08
"""

from __future__ import annotations
import re
import pytest


@pytest.fixture(scope="module")
def html():
    with open("ui/aponi/index.html", encoding="utf-8") as f:
        return f.read()


class TestGateInitialLoadFixT56G:

    def test_T56_G01_loadGate_clears_not_restores_lock(self, html):
        """T56-G01: loadGate() calls localStorage.removeItem, not getItem."""
        # The new loadGate must not call getItem (which would restore a stale lock)
        # It should call removeItem to clear any stale lock.
        load_gate_block = re.search(
            r"function loadGate\(\)\{(.+?)^\s{2}\}", html, re.S | re.M
        )
        assert load_gate_block, "loadGate() function not found"
        body = load_gate_block.group(1)
        assert "removeItem" in body, "loadGate() must call removeItem to clear stale lock"
        assert "gate.locked = false" in body, "loadGate() must initialise gate.locked to false"

    def test_T56_G02_loadGate_does_not_restore_locked_state(self, html):
        """T56-G02: loadGate() must not read gate.locked from localStorage."""
        load_gate_block = re.search(
            r"function loadGate\(\)\{(.+?)^\s{2}\}", html, re.S | re.M
        )
        assert load_gate_block
        body = load_gate_block.group(1)
        # Should not parse g.locked from stored value
        assert "g.locked" not in body, \
            "loadGate() must not restore gate.locked from localStorage"

    def test_T56_G03_setGateConnecting_defined(self, html):
        """T56-G03: setGateConnecting() function is defined."""
        assert "function setGateConnecting(" in html

    def test_T56_G04_setGateConnecting_does_not_set_locked(self, html):
        """T56-G04: setGateConnecting() sets gate.locked=false, not true."""
        block = re.search(
            r"function setGateConnecting\(\)\{(.+?)^\s{2}\}", html, re.S | re.M
        )
        assert block, "setGateConnecting() function not found"
        body = block.group(1)
        assert "gate.locked = false" in body
        assert "gate.locked = true" not in body

    def test_T56_G05_probe_health_unreachable_calls_connecting_not_locked(self, html):
        """T56-G05: probeHealth catch calls setGateConnecting, not setGateLocked(true)."""
        probe_block = re.search(
            r"async function probeHealth\(.+?\)\{(.+?)^\s{2}\}", html, re.S | re.M
        )
        assert probe_block
        body = probe_block.group(1)
        # The catch block must call setGateConnecting
        assert "setGateConnecting" in body
        # The catch block must NOT call setGateLocked(true, ... unreachable
        assert "Backend unreachable\"" not in body or "setGateLocked(true" not in body.split("setGateConnecting")[1]

    def test_T56_G06_overlay_only_shown_when_locked_not_connecting(self, html):
        """T56-G06: gateOverlay display:flex only inside gate.locked branch."""
        render_block = re.search(
            r"function renderGate\(\)\{(.+?)^\s{2}\}", html, re.S | re.M
        )
        assert render_block
        body = render_block.group(1)
        # Overlay must be set to flex inside the gate.locked branch only
        locked_branch = body.split("if (gate.locked)")[1] if "if (gate.locked)" in body else ""
        assert 'display = "flex"' in locked_branch, \
            "Overlay should be set to flex inside gate.locked branch"
        # And connecting branch must not show overlay
        connecting_branch = body.split("gate.connecting")[1] if "gate.connecting" in body else ""
        assert 'display = "flex"' not in connecting_branch.split("gate.locked")[0], \
            "Overlay must not show in connecting state"

    def test_T56_G07_hardrefresh_catch_uses_connecting_for_non_423(self, html):
        """T56-G07: hardRefresh catch only locks when error message is 'locked' (423)."""
        # The fix checks: if (_raw !== "locked") setGateConnecting()
        assert 'if (_raw !== "locked") setGateConnecting()' in html

    def test_T56_G08_gate_connecting_true_at_init(self, html):
        """T56-G08: Initial gate object has connecting:true."""
        gate_init = re.search(
            r"const gate = \{(.+?)\}", html
        )
        assert gate_init, "gate initialisation not found"
        body = gate_init.group(1)
        assert "connecting:true" in body, \
            "gate must initialise with connecting:true so overlay is never shown before first probe"
