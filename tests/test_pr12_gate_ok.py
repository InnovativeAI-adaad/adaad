# SPDX-License-Identifier: Apache-2.0
"""
PR #12 regression tests: gate_ok must always be present in health_report output.
"""

from __future__ import annotations

import json
import datetime as dt
import pytest
pytestmark = pytest.mark.regression_standard

from adaad.core.health import health_report


FIXED_CLOCK = lambda: dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)


def test_gate_ok_present_in_health_report() -> None:
    """gate_ok must always be present in health payload (PR #12 fix)."""
    payload = json.loads(health_report(clock=FIXED_CLOCK))
    assert "gate_ok" in payload


def test_gate_ok_default_is_true() -> None:
    """Default gate_ok value must be True (safe default)."""
    payload = json.loads(health_report(clock=FIXED_CLOCK))
    assert payload["gate_ok"] is True


def test_gate_ok_override_via_extra() -> None:
    """Orchestrator can override gate_ok=False via extra dict."""
    payload = json.loads(health_report(clock=FIXED_CLOCK, extra={"gate_ok": False}))
    assert payload["gate_ok"] is False


def test_gate_ok_kwarg_false() -> None:
    """gate_ok kwarg=False must reflect in payload."""
    payload = json.loads(health_report(clock=FIXED_CLOCK, gate_ok=False))
    assert payload["gate_ok"] is False


def test_existing_health_fields_preserved() -> None:
    """All v1 health fields must still be present after PR #12 fix."""
    payload = json.loads(health_report(clock=FIXED_CLOCK))
    assert payload["status"] == "ok"
    assert "timestamp_iso" in payload
    assert "timestamp_unix" in payload
    assert "timestamp" in payload
